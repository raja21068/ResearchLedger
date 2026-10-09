#!/usr/bin/env python3
"""
Stage 3.5 contracting preprocessing.

This script builds compact, file-specific input contexts for the Stage 3.5
per-file contracting step. It does not call an LLM.

Inputs:
  - Stage-2 reconciling spec JSON (default: {output_dir}/reconciling_spec.json,
    fallback: {output_dir}/reconciling_dag.json)
  - Stage-3 architecting plan JSON (default: {output_dir}/architecting_plan.json,
    fallback: {output_dir}/architecting_structure.json)
  - Optional Stage-1 translating blueprint, used only for a very small fallback snippet.

Outputs:
  - {output_dir}/{preprocess_subdir}/{safe_file_name}_compact_context.json
  - {output_dir}/{preprocess_subdir}/index.json
  - {output_dir}/{preprocess_subdir}/all_compact_contexts.json

Design goals:
  - deterministic local slicing, not LLM-based summarization;
  - preserve all contract/handoff/API IDs required by the routed file;
  - avoid passing full paper/translating/reconciling/architecting to every file;
  - surface warnings when architecting or reconciling references are incomplete.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from copy import deepcopy
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple


# -----------------------------------------------------------------------------
# Basic IO / normalization
# -----------------------------------------------------------------------------


def safe_artifact_name(file_path: str) -> str:
    return (file_path or "").replace("\\", "_").replace("/", "_").replace(":", "_")


def normalize_file_path(file_path: str) -> str:
    return (file_path or "").replace("\\", "/").strip()


def normalize_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def ensure_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def sorted_list(values: Iterable[Any]) -> List[Any]:
    return sorted([v for v in values if v is not None], key=lambda x: str(x))


def load_json(path: str) -> Any:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def dump_json(path: str, payload: Any) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def first_existing(paths: Sequence[str], description: str) -> str:
    for path in paths:
        if path and os.path.isfile(path):
            return path
    print(f"[ERROR] Could not find {description}. Checked: {paths}")
    sys.exit(1)


def resolve_default_path(output_dir: str, explicit_path: str, candidates: Sequence[str], description: str) -> str:
    if explicit_path.strip():
        if not os.path.isfile(explicit_path):
            print(f"[ERROR] {description} not found: {explicit_path}")
            sys.exit(1)
        return explicit_path
    return first_existing([os.path.join(output_dir, c) for c in candidates], description)


def normalize_routing_structure(routing_structure: Any) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    if not isinstance(routing_structure, dict):
        return {}, []

    payload = routing_structure
    nested = routing_structure.get("routing_json")
    if isinstance(nested, dict) and isinstance(nested.get("file_tree"), list) and nested.get("file_tree"):
        payload = nested

    file_tree = payload.get("file_tree", [])
    if not isinstance(file_tree, list):
        file_tree = []
    return payload, file_tree


def build_file_maps(file_tree: Sequence[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    by_path: Dict[str, Dict[str, Any]] = {}
    for item in file_tree:
        if isinstance(item, dict) and item.get("file_path"):
            by_path[normalize_file_path(item["file_path"])] = item
    return by_path


def get_file_entry(file_tree_by_path: Dict[str, Dict[str, Any]], file_path: str) -> Optional[Dict[str, Any]]:
    return file_tree_by_path.get(normalize_file_path(file_path))


# -----------------------------------------------------------------------------
# Routing order
# -----------------------------------------------------------------------------


def topological_sort_file_tree(file_tree: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    file_order = [normalize_file_path(item.get("file_path")) for item in file_tree if item.get("file_path")]
    file_set = set(file_order)
    entry_by_path = {normalize_file_path(item["file_path"]): item for item in file_tree if item.get("file_path")}
    indegree = {p: 0 for p in file_order}
    adjacency = {p: [] for p in file_order}

    for item in file_tree:
        file_path = normalize_file_path(item.get("file_path"))
        if not file_path:
            continue
        for dep in ensure_list(item.get("internal_dependencies")):
            dep_path = normalize_file_path(dep)
            if dep_path in file_set:
                adjacency[dep_path].append(file_path)
                indegree[file_path] += 1

    ready = [p for p in file_order if indegree[p] == 0]
    sorted_paths: List[str] = []
    while ready:
        current = ready.pop(0)
        sorted_paths.append(current)
        for downstream in adjacency[current]:
            indegree[downstream] -= 1
            if indegree[downstream] == 0:
                ready.append(downstream)

    if len(sorted_paths) != len(file_order):
        unresolved = [p for p, d in indegree.items() if d > 0]
        print(f"[ERROR] Circular internal dependencies in routing plan: {unresolved}")
        sys.exit(1)

    return [entry_by_path[p] for p in sorted_paths]


def order_from_generation_order(routing_payload: Dict[str, Any], file_tree_by_path: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    generation_order = routing_payload.get("generation_order", [])
    if not isinstance(generation_order, list) or not generation_order:
        return []

    ordered_paths: List[str] = []
    for item in generation_order:
        if isinstance(item, dict) and item.get("file_path"):
            path = normalize_file_path(item["file_path"])
            if path in file_tree_by_path and path not in ordered_paths:
                ordered_paths.append(path)

    # Append any file missing from explicit generation_order in original file_tree order.
    for path in file_tree_by_path:
        if path not in ordered_paths:
            ordered_paths.append(path)

    return [file_tree_by_path[p] for p in ordered_paths]


# -----------------------------------------------------------------------------
# Stage-2 indexing
# -----------------------------------------------------------------------------


def map_list_by_field(items: Any, field_names: Sequence[str]) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    if not isinstance(items, list):
        return out
    for item in items:
        if not isinstance(item, dict):
            continue
        key = None
        for field in field_names:
            if item.get(field):
                key = str(item[field])
                break
        if key:
            out[key] = item
    return out


def map_object_contracts(object_contracts: Any) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    if isinstance(object_contracts, dict):
        for key, value in object_contracts.items():
            if isinstance(value, dict):
                name = str(value.get("name") or key)
                out[name] = value
                out[key] = value
            else:
                out[str(key)] = {"name": str(key), "value": value}
    elif isinstance(object_contracts, list):
        for item in object_contracts:
            if isinstance(item, dict):
                name = item.get("name")
                if name:
                    out[str(name)] = item
    return out


def build_stage2_indexes(stage2: Dict[str, Any]) -> Dict[str, Any]:
    method_nodes = []
    if isinstance(stage2.get("method_graph"), dict):
        method_nodes.extend(ensure_list(stage2.get("method_graph", {}).get("nodes")))
    method_nodes.extend(ensure_list(stage2.get("computation_graph")))

    return {
        "core_path_contracts": map_list_by_field(stage2.get("core_path_contracts", []), ["contract_id", "id"]),
        "runtime_boundary_contracts": map_list_by_field(stage2.get("runtime_boundary_contracts", []), ["boundary_id", "id"]),
        "formula_exactness_contracts": map_list_by_field(stage2.get("formula_exactness_contracts", []), ["formula_id", "id"]),
        "execution_flow": map_list_by_field(stage2.get("execution_flow", []), ["step_id", "id"]),
        "method_graph_nodes": map_list_by_field(method_nodes, ["id", "node_id"]),
        "object_contracts": map_object_contracts(stage2.get("object_contracts", {})),
        "evidence_index": map_list_by_field(stage2.get("evidence_index", []), ["id", "evidence_id"]),
    }


def collect_text(value: Any, max_len: int = 50000) -> str:
    try:
        text = json.dumps(value, ensure_ascii=False)
    except TypeError:
        text = str(value)
    return text[:max_len]


def extract_known_object_refs(value: Any, known_object_names: Iterable[str]) -> Set[str]:
    text_norm = normalize_key(collect_text(value))
    hits: Set[str] = set()
    for name in known_object_names:
        if not name:
            continue
        if normalize_key(name) and normalize_key(name) in text_norm:
            hits.add(name)
    return hits


# -----------------------------------------------------------------------------
# Routing indexing
# -----------------------------------------------------------------------------


def build_api_owner_map(file_tree: Sequence[Dict[str, Any]]) -> Dict[str, List[str]]:
    owners: Dict[str, List[str]] = {}
    for file_entry in file_tree:
        file_path = normalize_file_path(file_entry.get("file_path"))
        if not file_path:
            continue
        for api in ensure_list(file_entry.get("public_api")):
            if not isinstance(api, dict) or not api.get("name"):
                continue
            name = str(api["name"])
            owners.setdefault(name, []).append(file_path)
            owners.setdefault(f"{file_path}::{name}", []).append(file_path)
    return owners


def api_owned_by_file(api_name: str, target_file: str, api_owner_map: Dict[str, List[str]]) -> bool:
    target = normalize_file_path(target_file)
    return target in [normalize_file_path(p) for p in api_owner_map.get(str(api_name), [])]


def get_api_summaries(file_entry: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not file_entry:
        return []
    summaries = []
    for api in ensure_list(file_entry.get("public_api")):
        if isinstance(api, dict) and api.get("name"):
            summaries.append(
                {
                    "name": api.get("name"),
                    "kind": api.get("kind"),
                    "inputs": api.get("inputs", []),
                    "outputs": api.get("outputs", []),
                    "contract_refs": api.get("contract_refs", []),
                    "producer_or_consumer": api.get("producer_or_consumer", ""),
                    "contract": api.get("contract", ""),
                }
            )
    return summaries


def compact_file_summary(file_entry: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not file_entry:
        return {}
    return {
        "file_path": file_entry.get("file_path"),
        "module_role": file_entry.get("module_role"),
        "semantic_responsibility": file_entry.get("semantic_responsibility"),
        "owned_contracts": file_entry.get("owned_contracts", []),
        "owned_runtime_boundaries": file_entry.get("owned_runtime_boundaries", []),
        "owned_formula_contracts": file_entry.get("owned_formula_contracts", []),
        "public_api": get_api_summaries(file_entry),
        "consumes_objects": file_entry.get("consumes_objects", []),
        "produces_objects": file_entry.get("produces_objects", []),
        "active_modes": file_entry.get("active_modes", []),
    }


def relation_involves_file(relation: Dict[str, Any], target_file: str, fields: Sequence[str]) -> bool:
    target = normalize_file_path(target_file)
    for field in fields:
        value = relation.get(field)
        if isinstance(value, list):
            if target in [normalize_file_path(v) for v in value]:
                return True
        elif normalize_file_path(value) == target:
            return True
    return False


def contract_refs_from_item(item: Dict[str, Any]) -> Set[str]:
    refs: Set[str] = set()
    for field in ["contract_refs", "source_contract_refs", "affected_contracts", "owned_contracts"]:
        for ref in ensure_list(item.get(field)):
            if isinstance(ref, str) and ref.strip():
                refs.add(ref.strip())
    if isinstance(item.get("contract_id"), str):
        refs.add(item["contract_id"])
    return refs


# -----------------------------------------------------------------------------
# Reference collection and expansion
# -----------------------------------------------------------------------------


def init_refs() -> Dict[str, Set[str]]:
    return {
        "contracts": set(),
        "runtime_boundaries": set(),
        "formula_contracts": set(),
        "objects": set(),
        "execution_steps": set(),
        "method_nodes": set(),
        "handoffs": set(),
        "hazards": set(),
        "experiment_fields": set(),
        "open_design_choices": set(),
        "evidence": set(),
        "integrity_checks": set(),
    }


def add_refs_from_file_entry(refs: Dict[str, Set[str]], file_entry: Dict[str, Any]) -> None:
    refs["contracts"].update(map(str, ensure_list(file_entry.get("owned_contracts"))))
    refs["runtime_boundaries"].update(map(str, ensure_list(file_entry.get("owned_runtime_boundaries"))))
    refs["formula_contracts"].update(map(str, ensure_list(file_entry.get("owned_formula_contracts"))))
    refs["objects"].update(map(str, ensure_list(file_entry.get("consumes_objects"))))
    refs["objects"].update(map(str, ensure_list(file_entry.get("produces_objects"))))
    refs["experiment_fields"].update(map(str, ensure_list(file_entry.get("assigned_experiment_protocol_fields"))))
    refs["open_design_choices"].update(map(str, ensure_list(file_entry.get("assigned_open_design_choices"))))

    usage = file_entry.get("stage2_alignment_usage", {})
    if isinstance(usage, dict):
        refs["execution_steps"].update(map(str, ensure_list(usage.get("owned_execution_flow_steps"))))
        refs["method_nodes"].update(map(str, ensure_list(usage.get("owned_method_graph_nodes"))))
        refs["objects"].update(map(str, ensure_list(usage.get("owned_object_contracts"))))
        refs["runtime_boundaries"].update(map(str, ensure_list(usage.get("owned_runtime_boundary_contracts"))))
        refs["formula_contracts"].update(map(str, ensure_list(usage.get("owned_formula_exactness_contracts"))))
        refs["handoffs"].update(map(str, ensure_list(usage.get("owned_critical_handoffs"))))
        refs["objects"].update(map(str, ensure_list(usage.get("consumed_stage2_objects"))))
        refs["objects"].update(map(str, ensure_list(usage.get("produced_stage2_objects"))))

    for api in ensure_list(file_entry.get("public_api")):
        if isinstance(api, dict):
            refs["contracts"].update(map(str, ensure_list(api.get("contract_refs"))))


def include_routing_relations(
    refs: Dict[str, Set[str]],
    target_file: str,
    routing_payload: Dict[str, Any],
    file_tree_by_path: Dict[str, Dict[str, Any]],
    api_owner_map: Dict[str, List[str]],
) -> Dict[str, List[Dict[str, Any]]]:
    target = normalize_file_path(target_file)
    relevant = {
        "contract_ownership": [],
        "implementation_hazards": [],
        "critical_artifact_handoffs": [],
        "orchestrated_handoffs": [],
        "api_dependency_edges": [],
        "mode_gating": [],
        "generation_order": [],
        "unresolved_issues": [],
    }

    # contract_ownership: owner, producer API owner, consumer API owner, or referenced contract.
    for item in ensure_list(routing_payload.get("contract_ownership")):
        if not isinstance(item, dict):
            continue
        involved = normalize_file_path(item.get("owner_file")) == target
        for api in ensure_list(item.get("producer_apis")) + ensure_list(item.get("consumer_apis")):
            if api_owned_by_file(str(api), target, api_owner_map):
                involved = True
        if item.get("contract_id") in refs["contracts"]:
            involved = True
        if involved:
            relevant["contract_ownership"].append(item)
            if item.get("contract_id"):
                refs["contracts"].add(str(item["contract_id"]))
            for ref in contract_refs_from_item(item):
                refs["contracts"].add(ref)

    # hazards.
    for item in ensure_list(routing_payload.get("implementation_hazards")):
        if not isinstance(item, dict):
            continue
        source_refs = contract_refs_from_item(item)
        involved = (
            normalize_file_path(item.get("primary_owner")) == target
            or target in [normalize_file_path(v) for v in ensure_list(item.get("must_not_own"))]
            or bool(source_refs & refs["contracts"])
        )
        if involved:
            relevant["implementation_hazards"].append(item)
            if item.get("hazard_id"):
                refs["hazards"].add(str(item["hazard_id"]))
            refs["contracts"].update(source_refs)

    # critical handoffs.
    for key in ["critical_artifact_handoffs", "orchestrated_handoffs"]:
        for item in ensure_list(routing_payload.get(key)):
            if not isinstance(item, dict):
                continue
            source_refs = contract_refs_from_item(item)
            artifact = item.get("artifact")
            involved = (
                relation_involves_file(item, target, ["producer_file", "consumer_file", "orchestrator_file", "orchestrated_by"])
                or bool(source_refs & refs["contracts"])
                or (isinstance(artifact, str) and artifact in refs["objects"])
            )
            if involved:
                relevant[key].append(item)
                if item.get("handoff_id"):
                    refs["handoffs"].add(str(item["handoff_id"]))
                refs["contracts"].update(source_refs)
                if isinstance(artifact, str) and artifact:
                    refs["objects"].add(artifact)

    # dependency edges.
    for item in ensure_list(routing_payload.get("api_dependency_edges")):
        if not isinstance(item, dict):
            continue
        involved = relation_involves_file(item, target, ["consumer_file", "producer_file"])
        if involved:
            relevant["api_dependency_edges"].append(item)
            refs["contracts"].update(contract_refs_from_item(item))

    # mode gating.
    target_entry = file_tree_by_path.get(target, {})
    target_active_modes = set(map(str, ensure_list(target_entry.get("active_modes"))))
    for item in ensure_list(routing_payload.get("mode_gating")):
        if not isinstance(item, dict):
            continue
        mode = str(item.get("mode", ""))
        involved = (
            target in [normalize_file_path(v) for v in ensure_list(item.get("required_files"))]
            or target in [normalize_file_path(v) for v in ensure_list(item.get("disabled_files"))]
            or mode in target_active_modes
            or "all_modes" in target_active_modes
        )
        if involved:
            relevant["mode_gating"].append(item)

    # generation order entry.
    for item in ensure_list(routing_payload.get("generation_order")):
        if isinstance(item, dict) and normalize_file_path(item.get("file_path")) == target:
            relevant["generation_order"].append(item)

    # unresolved issues.
    for item in ensure_list(routing_payload.get("unresolved_issues")):
        if not isinstance(item, dict):
            continue
        affected = set(map(str, ensure_list(item.get("affected_contracts"))))
        text = collect_text(item).lower()
        involved = bool(affected & refs["contracts"]) or target.lower() in text
        if involved:
            relevant["unresolved_issues"].append(item)
            refs["contracts"].update(affected)

    return relevant


def expand_stage2_slice(
    refs: Dict[str, Set[str]],
    stage2: Dict[str, Any],
    indexes: Dict[str, Any],
    max_iterations: int = 3,
) -> Dict[str, Any]:
    known_object_names = set(indexes["object_contracts"].keys())
    included = {
        "core_path_contracts": [],
        "runtime_boundary_contracts": [],
        "formula_exactness_contracts": [],
        "object_contracts": {},
        "execution_flow_steps": [],
        "method_graph_nodes": [],
        "experiment_protocol_fields": {},
        "training_or_execution_contract": {},
        "evaluation_contract": {},
        "open_design_choices": [],
        "integrity_checks": [],
        "evidence_index": [],
        "workflow_contract_excerpt": {},
        "compact_handoff": {},
    }

    for _ in range(max_iterations):
        # Some routing fields use a generic key named contract_refs even when the
        # referenced ID is a runtime boundary (RB*) or formula contract (F*).
        # Re-classify those IDs before materializing the Stage-2 slice.
        for rid in list(refs["contracts"]):
            if rid in indexes["runtime_boundary_contracts"]:
                refs["runtime_boundaries"].add(rid)
            if rid in indexes["formula_exactness_contracts"]:
                refs["formula_contracts"].add(rid)

        old_state = json.dumps({k: sorted(v) for k, v in refs.items()}, sort_keys=True)

        # Core contracts.
        for cid in list(refs["contracts"]):
            obj = indexes["core_path_contracts"].get(cid)
            if obj:
                refs["evidence"].update(map(str, ensure_list(obj.get("evidence"))))
                refs["objects"].update(extract_known_object_refs(obj, known_object_names))

        # Boundaries.
        for bid, boundary in indexes["runtime_boundary_contracts"].items():
            affected = set(map(str, ensure_list(boundary.get("affected_contracts"))))
            obj_name = boundary.get("object")
            if bid in refs["runtime_boundaries"] or affected & refs["contracts"] or obj_name in refs["objects"]:
                refs["runtime_boundaries"].add(bid)
                refs["contracts"].update(affected)
                if obj_name:
                    refs["objects"].add(str(obj_name))
                refs["evidence"].update(map(str, ensure_list(boundary.get("evidence"))))

        # Formula contracts.
        for fid, formula in indexes["formula_exactness_contracts"].items():
            consumed = set(map(str, ensure_list(formula.get("consumed_objects"))))
            produced = set(map(str, ensure_list(formula.get("produced_objects"))))
            if fid in refs["formula_contracts"] or consumed & refs["objects"] or produced & refs["objects"]:
                refs["formula_contracts"].add(fid)
                refs["objects"].update(consumed | produced)
                refs["evidence"].update(map(str, ensure_list(formula.get("evidence"))))

        # Object contracts.
        normalized_object_keys = {normalize_key(k): k for k in indexes["object_contracts"]}
        for obj in list(refs["objects"]):
            if obj in indexes["object_contracts"]:
                item = indexes["object_contracts"][obj]
                refs["evidence"].update(map(str, ensure_list(item.get("evidence"))))
            else:
                norm = normalize_key(obj)
                if norm in normalized_object_keys:
                    refs["objects"].add(normalized_object_keys[norm])

        # Execution flow.
        for sid, step in indexes["execution_flow"].items():
            step_refs = set(map(str, ensure_list(step.get("contract_refs"))))
            step_objects = set(map(str, ensure_list(step.get("inputs")))) | set(map(str, ensure_list(step.get("outputs"))))
            if sid in refs["execution_steps"] or step_refs & refs["contracts"] or step_objects & refs["objects"]:
                refs["execution_steps"].add(sid)
                refs["contracts"].update(step_refs)
                refs["objects"].update(step_objects & known_object_names)
                refs["evidence"].update(map(str, ensure_list(step.get("evidence"))))

        # Method graph.
        for nid, node in indexes["method_graph_nodes"].items():
            node_refs = set(map(str, ensure_list(node.get("contract_refs"))))
            node_objects = set(map(str, ensure_list(node.get("inputs")))) | set(map(str, ensure_list(node.get("outputs"))))
            if nid in refs["method_nodes"] or node_refs & refs["contracts"] or node_objects & refs["objects"]:
                refs["method_nodes"].add(nid)
                refs["contracts"].update(node_refs)
                refs["objects"].update(node_objects & known_object_names)

        # Open design choices.
        for item in ensure_list(stage2.get("open_design_choices")):
            if not isinstance(item, dict):
                continue
            affected = set(map(str, ensure_list(item.get("affected_contracts"))))
            if affected & refs["contracts"] or str(item.get("item")) in refs["open_design_choices"]:
                if item.get("item"):
                    refs["open_design_choices"].add(str(item["item"]))
                refs["contracts"].update(affected)

        # Integrity checks.
        for item in ensure_list(stage2.get("integrity_checks")):
            if not isinstance(item, dict):
                continue
            check_refs = set(map(str, ensure_list(item.get("contract_refs"))))
            if check_refs & refs["contracts"] or item.get("severity") == "high":
                if item.get("check_id"):
                    refs["integrity_checks"].add(str(item["check_id"]))
                refs["contracts"].update(check_refs)

        new_state = json.dumps({k: sorted(v) for k, v in refs.items()}, sort_keys=True)
        if new_state == old_state:
            break

    # Materialize included Stage-2 objects.
    included["core_path_contracts"] = [indexes["core_path_contracts"][cid] for cid in sorted_list(refs["contracts"]) if cid in indexes["core_path_contracts"]]
    included["runtime_boundary_contracts"] = [indexes["runtime_boundary_contracts"][bid] for bid in sorted_list(refs["runtime_boundaries"]) if bid in indexes["runtime_boundary_contracts"]]
    included["formula_exactness_contracts"] = [indexes["formula_exactness_contracts"][fid] for fid in sorted_list(refs["formula_contracts"]) if fid in indexes["formula_exactness_contracts"]]

    for name in sorted_list(refs["objects"]):
        if name in indexes["object_contracts"]:
            included["object_contracts"][name] = indexes["object_contracts"][name]
        else:
            norm = normalize_key(name)
            for key, value in indexes["object_contracts"].items():
                if normalize_key(key) == norm:
                    included["object_contracts"][key] = value
                    break

    included["execution_flow_steps"] = [indexes["execution_flow"][sid] for sid in sorted_list(refs["execution_steps"]) if sid in indexes["execution_flow"]]
    included["method_graph_nodes"] = [indexes["method_graph_nodes"][nid] for nid in sorted_list(refs["method_nodes"]) if nid in indexes["method_graph_nodes"]]

    experiment_protocol = stage2.get("experiment_protocol", {})
    if isinstance(experiment_protocol, dict):
        for field in sorted_list(refs["experiment_fields"]):
            if field in experiment_protocol:
                included["experiment_protocol_fields"][field] = experiment_protocol[field]

    # Add heuristic experiment fields by role/contract.
    heuristic_fields = infer_experiment_fields(refs, experiment_protocol)
    for field in heuristic_fields:
        if isinstance(experiment_protocol, dict) and field in experiment_protocol:
            included["experiment_protocol_fields"].setdefault(field, experiment_protocol[field])

    training_contract = stage2.get("training_or_execution_contract", {})
    if should_include_training_contract(refs, included):
        included["training_or_execution_contract"] = training_contract if isinstance(training_contract, dict) else {}

    evaluation_contract = stage2.get("evaluation_contract", {})
    if should_include_evaluation_contract(refs, included):
        included["evaluation_contract"] = evaluation_contract if isinstance(evaluation_contract, dict) else {}

    for item in ensure_list(stage2.get("open_design_choices")):
        if not isinstance(item, dict):
            continue
        affected = set(map(str, ensure_list(item.get("affected_contracts"))))
        if affected & refs["contracts"] or str(item.get("item")) in refs["open_design_choices"]:
            included["open_design_choices"].append(item)

    for item in ensure_list(stage2.get("integrity_checks")):
        if not isinstance(item, dict):
            continue
        if str(item.get("check_id")) in refs["integrity_checks"]:
            included["integrity_checks"].append(item)

    for evid in sorted_list(refs["evidence"]):
        if evid in indexes["evidence_index"]:
            included["evidence_index"].append(indexes["evidence_index"][evid])

    included["workflow_contract_excerpt"] = compact_workflow_contract(stage2.get("workflow_contract", {}), refs)
    if isinstance(stage2.get("compact_handoff"), dict):
        included["compact_handoff"] = stage2["compact_handoff"]

    return included


def infer_experiment_fields(refs: Dict[str, Set[str]], experiment_protocol: Any) -> Set[str]:
    if not isinstance(experiment_protocol, dict):
        return set()
    available = set(experiment_protocol.keys())
    wanted: Set[str] = set()
    text = " ".join(sorted(refs["contracts"] | refs["objects"] | refs["execution_steps"] | refs["method_nodes"])).lower()
    if any(tok in text for tok in ["data", "query", "response", "scenario", "s1", "s2"]):
        wanted.update({"datasets", "data_processing", "splits_sampling", "preprocessing"})
    if any(tok in text for tok in ["prompt", "judgment", "target", "c1", "c2", "c7", "s3", "s6"]):
        wanted.update({"target_and_prompts", "loss_region"})
    if any(tok in text for tok in ["training", "checkpoint", "loss", "c4", "f1", "rb2", "s5"]):
        wanted.update({"hyperparameters", "loss_region", "target_and_prompts"})
    if any(tok in text for tok in ["eval", "metric", "c5", "s7"]):
        wanted.update({"splits_sampling", "metrics", "evaluation", "evaluation_protocol"})
    return wanted & available


def should_include_training_contract(refs: Dict[str, Set[str]], included: Dict[str, Any]) -> bool:
    haystack = " ".join(sorted(refs["contracts"] | refs["objects"] | refs["formula_contracts"] | refs["runtime_boundaries"] | refs["execution_steps"])).lower()
    return any(tok in haystack for tok in ["train", "loss", "checkpoint", "f1", "rb2", "c1", "c3", "c4", "s5"])


def should_include_evaluation_contract(refs: Dict[str, Set[str]], included: Dict[str, Any]) -> bool:
    haystack = " ".join(sorted(refs["contracts"] | refs["objects"] | refs["execution_steps"])).lower()
    return any(tok in haystack for tok in ["eval", "metric", "c5", "c7", "s6", "s7"])


def compact_workflow_contract(workflow_contract: Any, refs: Dict[str, Set[str]]) -> Dict[str, Any]:
    if not isinstance(workflow_contract, dict):
        return {}
    out = {
        "workflow_archetype": workflow_contract.get("workflow_archetype", {}),
        "main_execution_path": workflow_contract.get("main_execution_path", []),
        "core_artifacts": [],
        "external_protocol_required": workflow_contract.get("external_protocol_required", []),
        "forbidden_substitutions": workflow_contract.get("forbidden_substitutions", []),
    }
    core_artifacts = ensure_list(workflow_contract.get("core_artifacts"))
    if refs["objects"]:
        for artifact in core_artifacts:
            if normalize_key(artifact) in [normalize_key(o) for o in refs["objects"]] or any(normalize_key(o) in normalize_key(artifact) for o in refs["objects"]):
                out["core_artifacts"].append(artifact)
    else:
        out["core_artifacts"] = core_artifacts[:10]
    return out


# -----------------------------------------------------------------------------
# Dependency context and warnings
# -----------------------------------------------------------------------------


def build_dependency_context(
    target_file: str,
    target_entry: Dict[str, Any],
    routing_payload: Dict[str, Any],
    file_tree_by_path: Dict[str, Dict[str, Any]],
    relevant_routing: Dict[str, List[Dict[str, Any]]],
    api_owner_map: Dict[str, List[str]],
) -> Dict[str, Any]:
    target = normalize_file_path(target_file)
    upstream_paths: Set[str] = set()
    downstream_paths: Set[str] = set()
    orchestrator_paths: Set[str] = set()
    inferred_missing_edges: List[Dict[str, Any]] = []

    for dep in ensure_list(target_entry.get("internal_dependencies")):
        dep_norm = normalize_file_path(dep)
        if dep_norm:
            upstream_paths.add(dep_norm)

    for edge in relevant_routing.get("api_dependency_edges", []):
        consumer = normalize_file_path(edge.get("consumer_file"))
        producer = normalize_file_path(edge.get("producer_file"))
        if consumer == target and producer:
            upstream_paths.add(producer)
        if producer == target and consumer:
            downstream_paths.add(consumer)

    for handoff in relevant_routing.get("critical_artifact_handoffs", []):
        producer = normalize_file_path(handoff.get("producer_file"))
        consumer = normalize_file_path(handoff.get("consumer_file"))
        orchestrated_by = normalize_file_path(handoff.get("orchestrated_by"))
        if consumer == target and producer:
            upstream_paths.add(producer)
        if producer == target and consumer:
            downstream_paths.add(consumer)
        if orchestrated_by:
            orchestrator_paths.add(orchestrated_by)

    for handoff in relevant_routing.get("orchestrated_handoffs", []):
        producer = normalize_file_path(handoff.get("producer_file"))
        consumer = normalize_file_path(handoff.get("consumer_file"))
        orchestrator = normalize_file_path(handoff.get("orchestrator_file") or handoff.get("orchestrated_by"))
        if producer == target and consumer:
            downstream_paths.add(consumer)
        if consumer == target and producer:
            upstream_paths.add(producer)
        if orchestrator:
            orchestrator_paths.add(orchestrator)

    # Missing edge inference from contract_ownership producer_apis / consumer_apis.
    direct_edges = {
        (normalize_file_path(e.get("consumer_file")), normalize_file_path(e.get("producer_file")))
        for e in ensure_list(routing_payload.get("api_dependency_edges"))
        if isinstance(e, dict)
    }
    orchestrated_pairs = {
        (normalize_file_path(h.get("consumer_file")), normalize_file_path(h.get("producer_file")))
        for h in ensure_list(routing_payload.get("orchestrated_handoffs")) + ensure_list(routing_payload.get("critical_artifact_handoffs"))
        if isinstance(h, dict) and (h.get("orchestrated_by") or h.get("orchestrator_file"))
    }

    for ownership in ensure_list(routing_payload.get("contract_ownership")):
        if not isinstance(ownership, dict):
            continue
        producers = ensure_list(ownership.get("producer_apis"))
        consumers = ensure_list(ownership.get("consumer_apis"))
        for p_api in producers:
            for c_api in consumers:
                producer_files = [normalize_file_path(p) for p in api_owner_map.get(str(p_api), [])]
                consumer_files = [normalize_file_path(c) for c in api_owner_map.get(str(c_api), [])]
                for p_file in producer_files:
                    for c_file in consumer_files:
                        if not p_file or not c_file or p_file == c_file:
                            continue
                        if target not in {p_file, c_file}:
                            continue
                        if (c_file, p_file) not in direct_edges and (c_file, p_file) not in orchestrated_pairs:
                            inferred_missing_edges.append(
                                {
                                    "warning_id": "missing_dependency_or_orchestration_edge",
                                    "severity": "medium",
                                    "contract_id": ownership.get("contract_id"),
                                    "producer_api": p_api,
                                    "producer_file": p_file,
                                    "consumer_api": c_api,
                                    "consumer_file": c_file,
                                    "description": (
                                        f"Contract {ownership.get('contract_id')} names producer API {p_api} "
                                        f"and consumer API {c_api}, but routing has no direct api_dependency_edge "
                                        f"or orchestrated handoff from {c_file} to {p_file}."
                                    ),
                                    "recommended_analyzing_behavior": (
                                        "Treat this as a required cross-file call or require explicit orchestration/fail-fast behavior."
                                    ),
                                }
                            )
                            if c_file == target:
                                upstream_paths.add(p_file)
                            if p_file == target:
                                downstream_paths.add(c_file)

    # Files that depend on target via internal_dependencies.
    for other_path, other_entry in file_tree_by_path.items():
        if target in [normalize_file_path(d) for d in ensure_list(other_entry.get("internal_dependencies"))]:
            downstream_paths.add(other_path)

    upstream_paths.discard(target)
    downstream_paths.discard(target)
    orchestrator_paths.discard(target)

    return {
        "upstream_dependencies": [compact_file_summary(file_tree_by_path.get(p)) for p in sorted(upstream_paths)],
        "downstream_dependents": [compact_file_summary(file_tree_by_path.get(p)) for p in sorted(downstream_paths)],
        "orchestrators": [compact_file_summary(file_tree_by_path.get(p)) for p in sorted(orchestrator_paths)],
        "inferred_missing_edges": inferred_missing_edges,
    }


# -----------------------------------------------------------------------------
# Context validation
# -----------------------------------------------------------------------------


def validate_context(
    target_file: str,
    target_entry: Dict[str, Any],
    refs: Dict[str, Set[str]],
    stage2_slice: Dict[str, Any],
    relevant_routing: Dict[str, List[Dict[str, Any]]],
    dependency_context: Dict[str, Any],
    stage2_indexes: Dict[str, Any],
) -> Dict[str, Any]:
    missing: List[Dict[str, str]] = []
    warnings: List[Dict[str, Any]] = []

    included_contract_ids = {c.get("contract_id") for c in stage2_slice.get("core_path_contracts", []) if isinstance(c, dict)}
    included_boundary_ids = {b.get("boundary_id") for b in stage2_slice.get("runtime_boundary_contracts", []) if isinstance(b, dict)}
    included_formula_ids = {f.get("formula_id") for f in stage2_slice.get("formula_exactness_contracts", []) if isinstance(f, dict)}
    included_object_keys = set(stage2_slice.get("object_contracts", {}).keys())

    for cid in ensure_list(target_entry.get("owned_contracts")):
        if cid and cid not in included_contract_ids:
            missing.append({"type": "owned_contract", "ref": str(cid), "message": "Owned contract not found in Stage-2 core_path_contracts slice."})
    for bid in ensure_list(target_entry.get("owned_runtime_boundaries")):
        if bid and bid not in included_boundary_ids:
            missing.append({"type": "owned_runtime_boundary", "ref": str(bid), "message": "Owned runtime boundary not found in Stage-2 slice."})
    for fid in ensure_list(target_entry.get("owned_formula_contracts")):
        if fid and fid not in included_formula_ids:
            missing.append({"type": "owned_formula_contract", "ref": str(fid), "message": "Owned formula contract not found in Stage-2 slice."})
    for api in ensure_list(target_entry.get("public_api")):
        if isinstance(api, dict):
            for cid in ensure_list(api.get("contract_refs")):
                # Routing uses the generic field name contract_refs for core contracts,
                # runtime boundary IDs, and formula IDs. Treat all three as valid.
                if (
                    cid
                    and cid not in included_contract_ids
                    and cid not in included_boundary_ids
                    and cid not in included_formula_ids
                ):
                    missing.append({"type": "public_api_contract_ref", "ref": str(cid), "message": f"Public API {api.get('name')} references an ID not included in Stage-2 slice."})

    for obj in ensure_list(target_entry.get("consumes_objects")) + ensure_list(target_entry.get("produces_objects")):
        if obj and obj not in included_object_keys:
            # Object may be a routed artifact absent from Stage 2; warn, not fatal.
            warnings.append({"type": "object_contract_not_found", "ref": str(obj), "severity": "low", "message": "Routed object/artifact has no matching Stage-2 object_contract; keep routing semantics."})

    warnings.extend(dependency_context.get("inferred_missing_edges", []))

    # Produced artifact without observed consumer.
    produced = set(map(str, ensure_list(target_entry.get("produces_objects"))))
    if produced:
        consumed_by_handoff = {str(h.get("artifact")) for h in relevant_routing.get("critical_artifact_handoffs", []) if h.get("producer_file") == target_file}
        downstream_consumes = set()
        for dep in dependency_context.get("downstream_dependents", []):
            downstream_consumes.update(map(str, ensure_list(dep.get("consumes_objects"))))
        for artifact in produced:
            if artifact and artifact not in consumed_by_handoff and artifact not in downstream_consumes:
                warnings.append({"type": "produced_artifact_consumer_unclear", "ref": artifact, "severity": "medium", "message": "Target file produces this artifact, but no consumer was found in the compact relation graph."})

    return {
        "included_refs": {k: sorted_list(v) for k, v in refs.items()},
        "missing_refs": missing,
        "warnings": warnings,
    }


# -----------------------------------------------------------------------------
# Planning compact fallback
# -----------------------------------------------------------------------------


def read_planning_compact(path: str, max_chars: int = 12000) -> str:
    if not path or not os.path.isfile(path):
        return ""
    text = open(path, encoding="utf-8").read()
    # Prefer downstream handoff and core contracts sections if available.
    sections = []
    for heading in ["# 12. Downstream Handoff Checklist", "# 4. Core Path Contracts", "# 10. Missing Decisions"]:
        idx = text.find(heading)
        if idx >= 0:
            next_idx = text.find("\n# ", idx + 1)
            sections.append(text[idx: next_idx if next_idx >= 0 else len(text)])
    compact = "\n\n".join(sections).strip() or text[:max_chars]
    return compact[:max_chars]


# -----------------------------------------------------------------------------
# Top-level context builder
# -----------------------------------------------------------------------------


def build_global_compact_rules(stage2: Dict[str, Any], routing_payload: Dict[str, Any]) -> Dict[str, Any]:
    forbidden = []
    workflow = stage2.get("workflow_contract", {})
    if isinstance(workflow, dict):
        forbidden.extend(ensure_list(workflow.get("forbidden_substitutions")))
    for contract in ensure_list(stage2.get("core_path_contracts")):
        if isinstance(contract, dict):
            forbidden.extend(ensure_list(contract.get("forbidden_downgrades")))
    forbidden.extend(
        [
            "No placeholder, fake metric, synthetic data, random output, or silent fallback in core method paths.",
            "Unsupported core modes must be disabled or fail fast.",
            "No produced core artifact may remain unconsumed.",
            "External protocols must use explicit API/artifact/fail-fast handling, not heuristics.",
        ]
    )
    # De-duplicate while preserving order.
    seen = set()
    forbidden_unique = []
    for item in forbidden:
        key = str(item)
        if key and key not in seen:
            seen.add(key)
            forbidden_unique.append(key)

    return {
        "source_authority": "Stage 3 routing + relevant Stage 2 contracts are authoritative for analyzing. No full paper is included by default.",
        "routing_scope": routing_payload.get("routing_scope", {}),
        "forbidden_downgrades": forbidden_unique[:30],
        "dependency_rules": routing_payload.get("global_contracts", {}).get("dependency_direction", []),
        "runtime_boundary_rules": routing_payload.get("global_contracts", {}).get("runtime_boundary_rules", []),
        "external_protocol_policy": [
            "implement_external_api",
            "load_released_artifact",
            "follow_external_protocol",
            "fail_fast_if_unavailable",
        ],
        "mode_policy": ["Unsupported modes must be disabled or fail fast."],
        "handoff_to_analyzing": routing_payload.get("handoff_to_analyzing", {}),
    }


def build_compact_file_context(
    target_entry: Dict[str, Any],
    stage2: Dict[str, Any],
    routing_payload: Dict[str, Any],
    file_tree_by_path: Dict[str, Dict[str, Any]],
    stage2_indexes: Dict[str, Any],
    api_owner_map: Dict[str, List[str]],
    planning_compact: str = "",
) -> Dict[str, Any]:
    target_file = normalize_file_path(target_entry.get("file_path"))
    refs = init_refs()
    add_refs_from_file_entry(refs, target_entry)

    relevant_routing = include_routing_relations(refs, target_file, routing_payload, file_tree_by_path, api_owner_map)
    stage2_slice = expand_stage2_slice(refs, stage2, stage2_indexes)
    dependency_context = build_dependency_context(target_file, target_entry, routing_payload, file_tree_by_path, relevant_routing, api_owner_map)
    validation = validate_context(target_file, target_entry, refs, stage2_slice, relevant_routing, dependency_context, stage2_indexes)

    context = {
        "target_file_entry": target_entry,
        "relevant_stage2": stage2_slice,
        "relevant_routing": relevant_routing,
        "dependency_context": dependency_context,
        "global_compact_rules": build_global_compact_rules(stage2, routing_payload),
        "planning_compact_fallback": planning_compact,
        "context_validation": validation,
    }
    return context


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Build compact per-file contracting inputs from Stage-2/Stage-3 artifacts.")
    parser.add_argument("--output_dir", type=str, required=True, help="Pipeline output directory containing Stage-2/Stage-3 artifacts.")
    parser.add_argument("--reconciling_spec_path", type=str, default="", help="Stage-2 JSON. Default: {output_dir}/reconciling_spec.json then reconciling_dag.json.")
    parser.add_argument("--architecting_plan_path", type=str, default="", help="Stage-3 JSON. Default: {output_dir}/architecting_plan.json then architecting_structure.json.")
    parser.add_argument("--translating_blueprint_path", type=str, default="", help="Optional translating blueprint. Default: {output_dir}/translating_blueprint.txt if present.")
    parser.add_argument("--aligning_spec_path", type=str, default="", help="Deprecated alias of --reconciling_spec_path.")
    parser.add_argument("--routing_plan_path", type=str, default="", help="Deprecated alias of --architecting_plan_path.")
    parser.add_argument("--planning_blueprint_path", type=str, default="", help="Deprecated alias of --translating_blueprint_path.")
    parser.add_argument("--preprocess_subdir", type=str, default="contracting_preprocess_inputs", help="Subfolder under output_dir for compact contexts.")
    parser.add_argument("--target_files", nargs="*", default=[], help="Optional subset of routed files to preprocess.")
    parser.add_argument("--use_generation_order", action="store_true", help="Prefer routing_plan.generation_order over dependency topological sort.")
    parser.add_argument("--include_planning_compact", action="store_true", help="Include a small planning fallback snippet in each compact context.")
    args = parser.parse_args()

    output_dir = args.output_dir
    os.makedirs(output_dir, exist_ok=True)

    reconciling_path = resolve_default_path(
        output_dir,
        args.reconciling_spec_path or args.aligning_spec_path,
        ["reconciling_spec.json", "reconciling_dag.json", "aligning_spec.json", "aligning_dag.json"],
        "Stage-2 reconciling JSON",
    )
    architecting_path = resolve_default_path(
        output_dir,
        args.architecting_plan_path or args.routing_plan_path,
        ["architecting_plan.json", "architecting_structure.json", "routing_plan.json", "routing_structure.json", "routing_file_tree.json"],
        "Stage-3 architecting JSON",
    )

    translating_path = (
        args.translating_blueprint_path.strip()
        or args.planning_blueprint_path.strip()
        or (
            os.path.join(output_dir, "translating_blueprint.txt")
            if os.path.isfile(os.path.join(output_dir, "translating_blueprint.txt"))
            else os.path.join(output_dir, "planning_blueprint.txt")
        )
    )

    stage2 = load_json(reconciling_path)
    stage3 = load_json(architecting_path)
    routing_payload, file_tree = normalize_routing_structure(stage3)
    if not file_tree:
        print("[ERROR] Architecting plan has an empty file_tree.")
        sys.exit(1)

    file_tree_by_path = build_file_maps(file_tree)
    stage2_indexes = build_stage2_indexes(stage2)
    api_owner_map = build_api_owner_map(file_tree)

    if args.use_generation_order:
        sorted_entries = order_from_generation_order(routing_payload, file_tree_by_path)
        if not sorted_entries:
            print(
                "[WARN] generation_order missing or empty; falling back to dependency topological sort."
            )
            sorted_entries = topological_sort_file_tree(file_tree)
    else:
        sorted_entries = topological_sort_file_tree(file_tree)

    if args.target_files:
        target_set = {normalize_file_path(p) for p in args.target_files}
        sorted_entries = [entry for entry in sorted_entries if normalize_file_path(entry.get("file_path")) in target_set]
        missing_targets = target_set - {normalize_file_path(entry.get("file_path")) for entry in sorted_entries}
        if missing_targets:
            print(f"[ERROR] Requested target files not found in architecting file_tree: {sorted_list(missing_targets)}")
            sys.exit(1)

    planning_compact = read_planning_compact(translating_path) if args.include_planning_compact else ""

    preprocess_dir = os.path.join(output_dir, args.preprocess_subdir)
    os.makedirs(preprocess_dir, exist_ok=True)

    index_items = []
    all_contexts = []
    aggregate_warnings: List[Dict[str, Any]] = []

    for idx, entry in enumerate(sorted_entries, start=1):
        target_file = normalize_file_path(entry.get("file_path"))
        safe_name = safe_artifact_name(target_file)
        context = build_compact_file_context(
            target_entry=entry,
            stage2=stage2,
            routing_payload=routing_payload,
            file_tree_by_path=file_tree_by_path,
            stage2_indexes=stage2_indexes,
            api_owner_map=api_owner_map,
            planning_compact=planning_compact,
        )

        artifact_rel = f"{safe_name}_compact_context.json"
        artifact_path = os.path.join(preprocess_dir, artifact_rel)
        dump_json(artifact_path, context)

        warnings = context.get("context_validation", {}).get("warnings", [])
        missing = context.get("context_validation", {}).get("missing_refs", [])
        aggregate_warnings.extend(
            [{"file_path": target_file, **w} for w in warnings]
            + [{"file_path": target_file, **m} for m in missing]
        )

        index_item = {
            "order": idx,
            "file_path": target_file,
            "artifact": os.path.join(args.preprocess_subdir, artifact_rel),
            "owned_contracts": entry.get("owned_contracts", []),
            "owned_runtime_boundaries": entry.get("owned_runtime_boundaries", []),
            "owned_formula_contracts": entry.get("owned_formula_contracts", []),
            "warning_count": len(warnings),
            "missing_ref_count": len(missing),
        }
        index_items.append(index_item)
        all_contexts.append({"file_path": target_file, "context": context})
        print(f"[OK] {target_file} -> {artifact_path} (warnings={len(warnings)}, missing={len(missing)})")

    dump_json(os.path.join(preprocess_dir, "index.json"), {"items": index_items})
    dump_json(
        os.path.join(preprocess_dir, "all_compact_contexts.json"),
        {
            "metadata": {
                "reconciling_spec_path": reconciling_path,
                "architecting_plan_path": architecting_path,
                "translating_blueprint_path": translating_path if args.include_planning_compact else "",
                "context_count": len(all_contexts),
                "preprocess_subdir": args.preprocess_subdir,
            },
            "contexts": all_contexts,
        },
    )
    dump_json(
        os.path.join(preprocess_dir, "preprocess_summary.json"),
        {
            "file_count": len(index_items),
            "items": index_items,
            "aggregate_warnings": aggregate_warnings,
        },
    )
    print(f"[DONE] Wrote {len(index_items)} compact contexts to {preprocess_dir}")


if __name__ == "__main__":
    main()
