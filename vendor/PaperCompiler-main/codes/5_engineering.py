"""
Stage 5 unified: sequential full-file engineering.

Uses Stage 1 blueprint, Stage 2 DAG, Stage 3 architecting, and Stage 4 contracting only (no stub artifacts).
Each file is generated in topological order with ALL previously implemented files
in the prompt.
"""
from openai import OpenAI
import argparse
import copy
import json
import os
import re
import sys

from tqdm import tqdm

from utils import (
    extract_code_from_content,
    print_response,
    print_log_cost,
    load_accumulated_cost,
    save_accumulated_cost,
    add_paper_reference_args,
    load_paper_content,
    format_paper_for_prompt,
    build_paper_reference_block,
)


parser = argparse.ArgumentParser()
parser.add_argument("--paper_name", type=str)
parser.add_argument("--gpt_version", type=str, default="o3-mini")
parser.add_argument("--output_dir", type=str, default="")
parser.add_argument("--output_repo_dir", type=str, default="")
add_paper_reference_args(parser)
parser.add_argument(
    "--translating_blueprint_path",
    type=str,
    default="",
    help="Stage-1 blueprint; default: {output_dir}/translating_blueprint.txt",
)
parser.add_argument(
    "--reconciling_dag_path",
    type=str,
    default="",
    help="Stage-2 DAG JSON; default: {output_dir}/reconciling_dag.json",
)
parser.add_argument(
    "--architecting_structure_path",
    type=str,
    default="",
    help="Stage-3 architecting JSON; default: {output_dir}/architecting_structure.json",
)
parser.add_argument(
    "--contracting_contract_path",
    type=str,
    default="",
    help="Stage-4 implementation contracting JSON; default: {output_dir}/contracting_implementation_contract.json",
)
parser.add_argument(
    "--reference_registry_path",
    type=str,
    default="",
    help="Stage-1.5 reference registry JSON; default: {output_dir}/reference_registry.json when present.",
)
parser.add_argument("--planning_blueprint_path", type=str, default="", help="Deprecated alias of --translating_blueprint_path.")
parser.add_argument("--aligning_dag_path", type=str, default="", help="Deprecated alias of --reconciling_dag_path.")
parser.add_argument("--routing_structure_path", type=str, default="", help="Deprecated alias of --architecting_structure_path.")
parser.add_argument("--analyzing_contract_path", type=str, default="", help="Deprecated alias of --contracting_contract_path.")

args = parser.parse_args()
client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

paper_name = args.paper_name
gpt_version = args.gpt_version
output_dir = args.output_dir
output_repo_dir = args.output_repo_dir.strip()
if not output_repo_dir:
    output_repo_dir = f"{output_dir}/final_repo"

translating_blueprint_path = args.translating_blueprint_path.strip() or args.planning_blueprint_path.strip()
if not translating_blueprint_path:
    preferred = f"{output_dir}/translating_blueprint.txt"
    fallback = f"{output_dir}/planning_blueprint.txt"
    translating_blueprint_path = preferred if os.path.isfile(preferred) else fallback

reconciling_dag_path = args.reconciling_dag_path.strip() or args.aligning_dag_path.strip()
if not reconciling_dag_path:
    preferred = f"{output_dir}/reconciling_dag.json"
    fallback = f"{output_dir}/aligning_dag.json"
    reconciling_dag_path = preferred if os.path.isfile(preferred) else fallback

architecting_structure_path = args.architecting_structure_path.strip() or args.routing_structure_path.strip()
if not architecting_structure_path:
    preferred = f"{output_dir}/architecting_structure.json"
    fallback = f"{output_dir}/routing_structure.json"
    architecting_structure_path = preferred if os.path.isfile(preferred) else fallback

contracting_contract_path = args.contracting_contract_path.strip() or args.analyzing_contract_path.strip()
if not contracting_contract_path:
    preferred = f"{output_dir}/contracting_implementation_contract.json"
    fallback = f"{output_dir}/analyzing_implementation_contract.json"
    contracting_contract_path = preferred if os.path.isfile(preferred) else fallback

reference_registry_path = args.reference_registry_path.strip()
if not reference_registry_path:
    default_reference_registry = f"{output_dir}/reference_registry.json"
    if os.path.isfile(default_reference_registry):
        reference_registry_path = default_reference_registry


def require_file(file_path, hint):
    if not os.path.isfile(file_path):
        print(f"[ERROR] File not found: {file_path}. {hint}")
        sys.exit(1)


def read_text_file(file_path):
    with open(file_path, encoding="utf-8") as f:
        return f.read()


def load_json_file(file_path):
    with open(file_path, encoding="utf-8") as f:
        return json.load(f)


def safe_artifact_name(file_path):
    return file_path.replace("\\", "_").replace("/", "_").replace(":", "_")


def normalize_routing_structure(routing_structure):
    if not isinstance(routing_structure, dict):
        return {}, []

    routing_payload = routing_structure
    nested = routing_structure.get("routing_json")
    if isinstance(nested, dict):
        nested_tree = nested.get("file_tree")
        if isinstance(nested_tree, list) and nested_tree:
            routing_payload = nested

    file_tree = routing_payload.get("file_tree", [])
    if not isinstance(file_tree, list):
        file_tree = []
    return routing_payload, file_tree


def normalize_contracting_contract(contract_obj):
    if not isinstance(contract_obj, dict):
        return {"per_file_contracts": []}
    if "implementation_analysis" in contract_obj and isinstance(
        contract_obj["implementation_analysis"], dict
    ):
        return contract_obj["implementation_analysis"]
    return contract_obj


def normalize_reference_registry(reference_obj):
    if isinstance(reference_obj, list):
        return reference_obj
    if isinstance(reference_obj, dict):
        maybe_list = reference_obj.get("reference_registry")
        if isinstance(maybe_list, list):
            return maybe_list
    return []


def normalize_file_path_for_match(file_path):
    return (file_path or "").replace("\\", "/").strip().lower()


def build_contract_index(contracting_payload):
    contracts = contracting_payload.get("per_file_contracts", [])
    if not isinstance(contracts, list):
        contracts = []
    index = {}
    for contract in contracts:
        if not isinstance(contract, dict):
            continue
        file_path = contract.get("file_path", "")
        if file_path:
            index[normalize_file_path_for_match(file_path)] = contract
    return index


def contract_for_file(target_file_path, contract_index):
    return contract_index.get(normalize_file_path_for_match(target_file_path), {})


def build_contract_reference(sorted_entries, contract_index, done_file_paths, target_file_path):
    done_set = {normalize_file_path_for_match(path) for path in done_file_paths}
    target_norm = normalize_file_path_for_match(target_file_path)
    completed = []
    downstream_expected = []
    target_contract = {}
    for entry in sorted_entries:
        path = entry.get("file_path", "")
        norm = normalize_file_path_for_match(path)
        contract = contract_index.get(norm, {})
        if not contract:
            continue
        if norm == target_norm:
            target_contract = contract
        elif norm in done_set:
            completed.append(contract)
        else:
            downstream_expected.append(contract)
    return json.dumps(
        {
            "target_contract": target_contract,
            "completed_same_stage_contracts": completed,
            "downstream_expected_contracts_for_unimplemented_files": downstream_expected,
            "cross_file_contract_rules": [
                "Strictly preserve public API names, call signatures, artifact names, schema semantics, tensor/object layout, checkpoint/state content, and producer-consumer direction from Stage-4 contracts.",
                "Completed same-stage contracts describe interfaces that already exist and must be imported/called exactly as written.",
                "Downstream expected contracts describe future consumers and expected artifacts; current code must produce outputs compatible with them.",
                "If a contract mismatch is unavoidable, fail fast at the boundary instead of silently renaming symbols, changing schemas, or substituting a heuristic.",
                "Keep logic coherent across files: every produced artifact must be consumable by its listed downstream file, and every consumed artifact must come from an implemented or orchestrated producer.",
            ],
        },
        ensure_ascii=False,
        indent=2,
    )


def topological_sort_file_tree(file_tree):
    file_order = [item["file_path"] for item in file_tree]
    file_set = set(file_order)
    entry_by_path = {item["file_path"]: item for item in file_tree}
    indegree = {file_path: 0 for file_path in file_order}
    adjacency = {file_path: [] for file_path in file_order}

    for item in file_tree:
        file_path = item["file_path"]
        for dependency in item.get("internal_dependencies", []):
            if dependency not in file_set:
                continue
            adjacency[dependency].append(file_path)
            indegree[file_path] += 1

    ready = [file_path for file_path in file_order if indegree[file_path] == 0]
    sorted_paths = []
    while ready:
        current = ready.pop(0)
        sorted_paths.append(current)
        for downstream in adjacency[current]:
            indegree[downstream] -= 1
            if indegree[downstream] == 0:
                ready.append(downstream)

    if len(sorted_paths) != len(file_order):
        unresolved = [p for p, d in indegree.items() if d > 0]
        print(
            "[ERROR] Circular internal dependencies in architecting_structure.json: "
            f"{unresolved}"
        )
        sys.exit(1)

    return [entry_by_path[file_path] for file_path in sorted_paths]


def is_launcher_file(file_entry):
    path = file_entry.get("file_path", "").lower()
    responsibility = (file_entry.get("semantic_responsibility") or "").lower()
    if re.search(r"\b(entry point|entrypoint|launcher|main script)\b", responsibility):
        return True
    base = os.path.basename(path)
    if base in ("train.py", "main.py", "run.py", "__main__.py"):
        return True
    if "scripts/" in path and base.endswith(".py") and "train" in base:
        return True
    return False


def prioritize_launcher_last(sorted_entries):
    regular = [e for e in sorted_entries if not is_launcher_file(e)]
    launchers = [e for e in sorted_entries if is_launcher_file(e)]
    return regular + launchers


def build_stage1_and_2_summary(stage1_text, aligning_dag):
    node_hparams = {}
    legacy_graph = aligning_dag.get("computation_graph", [])
    for node in legacy_graph:
        node_id = node.get("node_id")
        if node_id:
            node_hparams[node_id] = node.get("hyperparameters", {})
    method_graph = aligning_dag.get("method_graph", {})
    for node in method_graph.get("nodes", []):
        node_id = node.get("id")
        if node_id and node_id not in node_hparams:
            node_hparams[node_id] = {
                "operation": node.get("operation"),
                "condition": node.get("condition"),
            }
    return json.dumps(
        {
            "stage1_blueprint_text": stage1_text,
            "stage2_workflow_contract": aligning_dag.get("workflow_contract", {}),
            "stage2_global_tensors": aligning_dag.get("global_tensors", {}),
            "stage2_artifact_contracts": aligning_dag.get("artifact_contracts", {}),
            "stage2_object_contracts": aligning_dag.get("object_contracts", {}),
            "stage2_node_hyperparameters": node_hparams,
        },
        ensure_ascii=False,
        indent=2,
    )


def build_assigned_dag_json(file_entry, aligning_nodes_by_id):
    assigned_ids = file_entry.get("assigned_dag_nodes", [])
    matched = []
    missing = []
    for node_id in assigned_ids:
        node_obj = aligning_nodes_by_id.get(node_id)
        if node_obj is None:
            missing.append(node_id)
        else:
            matched.append(node_obj)
    return json.dumps(
        {
            "assigned_node_ids": assigned_ids,
            "assigned_formulas": matched,
            "missing_node_ids": missing,
        },
        ensure_ascii=False,
        indent=2,
    )


def build_implemented_code_block(done_file_paths, done_file_dict):
    if not done_file_paths:
        return "(no prior files implemented yet)"
    chunks = []
    for file_path in done_file_paths:
        code = done_file_dict.get(file_path, "")
        chunks.append(f"## {file_path}\n```python\n{code}\n```\n")
    return "\n".join(chunks)


def build_integration_rules(file_entry, is_launcher):
    rules = [
        "Import and call classes/functions from [IMPLEMENTED CODE FILES]; do not reimplement them under new names.",
        "Treat Stage-4 implementation contracts as cross-file interface contracts, not optional guidance.",
        "Match artifact schemas, public API names, tensor/object semantics, state/checkpoint fields, and producer-consumer direction across files.",
        "Current file outputs must satisfy [DOWNSTREAM EXPECTED STAGE-4 CONTRACTS] for files that have not been generated yet.",
        "All neural components must be torch.nn.Module subclasses where applicable.",
        "Tensor shapes across modules must match: if the model applies variate subsampling, return indices or aligned targets so the trainer loss uses consistent shapes.",
        "Do not use identity attention (output equals input) or duplicate block stacks when a module already exists in prior files.",
    ]
    if is_launcher:
        rules.extend(
            [
                "LAUNCHER: Wire run/config, core/model, engine/trainer (and data modules if routed).",
                "LAUNCHER: Do not invent torch.randn synthetic training pipelines unless the paper explicitly uses synthetic data.",
                "LAUNCHER: build_model / load_data must use the implemented modules from prior files, not parallel simplified copies.",
            ]
        )
    rules.extend(
        [
            "If architecting marks a hazard as external_protocol_required or unresolved_core_protocol for this file, implement only a typed interface and raise NotImplementedError at the unresolved core step.",
            "Do not replace unresolved core protocols with zlib/synthetic/mock heuristics unless routing explicitly allows full_implementation.",
        ]
    )
    return "\n".join(f"- {r}" for r in rules)


def build_engineering_system_msg(paper_format):
    return {
        "role": "system",
        "content": f"""You are an expert ML engineer reproducing a paper as a modular PyTorch repository.
You receive the paper ({paper_format}), implementation blueprint, tensor DAG summary, project architecting, Stage-4 implementation contracts, and all previously implemented Python files.
Write ONE complete file per turn. Code must be executable, typed where practical, and faithful to the paper.
Stage-4 contracts are strict cross-file contracts. Preserve public API names, artifact schemas, tensor/object semantics, state/checkpoint fields, and producer-consumer direction across files.
Stage-1.5 reference registry is directly extracted raw information from original paper text and has higher priority than secondary references.
If other references contain mistakes/omissions, you MUST strictly follow Stage-1.5 raw information.
If Stage-1.5 provides long formulas or long prompts that clearly correspond to gaps/citation markers in other references, you MUST directly use Stage-1.5 raw information.
Use completed Stage-4 contracts to call already generated upstream files exactly. Use downstream expected Stage-4 contracts to produce artifacts and APIs future files can consume without schema drift.
When architecting marks a core protocol as external/unresolved, implement an explicit interface and raise NotImplementedError instead of heuristic substitution.
When architecting lists critical artifact handoffs for a file, the producer must expose the artifact and the consumer must actually apply it; generated parameters, latents, metadata, or stochastic states must not be silently ignored.
Output ONLY one ```python code block containing the full file. No markdown outside the block.""",
    }


def build_file_hazard_json(target_file_path, routing_payload):
    hazards = routing_payload.get("implementation_hazards", [])
    if not isinstance(hazards, list):
        hazards = []
    relevant = []
    for hazard in hazards:
        if not isinstance(hazard, dict):
            continue
        primary_owner = hazard.get("primary_owner")
        must_not_own = hazard.get("must_not_own", [])
        if primary_owner == target_file_path or target_file_path in must_not_own:
            relevant.append(
                {
                    "hazard_id": hazard.get("hazard_id"),
                    "implementation_status": hazard.get("implementation_status"),
                    "allowed_coding_behavior": hazard.get("allowed_coding_behavior"),
                    "contract": hazard.get("contract"),
                    "primary_owner": primary_owner,
                    "must_not_own": must_not_own,
                }
            )
    return json.dumps(relevant, ensure_ascii=False, indent=2)


def build_file_handoff_json(target_file_path, routing_payload):
    handoffs = routing_payload.get("critical_artifact_handoffs", [])
    if not isinstance(handoffs, list):
        handoffs = []
    relevant = []
    for handoff in handoffs:
        if not isinstance(handoff, dict):
            continue
        if target_file_path in (
            handoff.get("producer_file"),
            handoff.get("consumer_file"),
        ):
            relevant.append(handoff)
    return json.dumps(relevant, ensure_ascii=False, indent=2)


def build_reference_registry_json(reference_registry):
    return json.dumps(
        {
            "reference_registry": reference_registry,
            "source_note": "Directly extracted raw information from original paper text.",
            "hard_priority_rules": [
                "If other references contain mistakes or omissions, strictly follow this raw information.",
                "If this registry provides long formulas or long prompts that clearly correspond to gaps/citation markers in other references, directly use this registry raw information.",
            ],
        },
        ensure_ascii=False,
        indent=2,
    )


def build_write_msg(
    target_file_path,
    file_entry,
    paper_reference_block,
    stage1_and_2_json,
    routing_structure_json,
    contract_reference_json,
    reference_registry_json,
    implemented_code_block,
    done_file_paths,
    is_launcher,
    file_hazards_json,
    file_handoffs_json,
):
    assigned_dag_json = file_entry.get("_assigned_dag_json", "{}")
    integration_rules = build_integration_rules(file_entry, is_launcher)
    responsibility = file_entry.get("semantic_responsibility", "")
    internal_deps = file_entry.get("internal_dependencies", [])

    return [
        {
            "role": "user",
            "content": f"""{paper_reference_block}

-----

## Stage 1 Blueprint + Stage 2 DAG summary
{stage1_and_2_json}

-----

## Stage 3 Project architecting (full file tree)
{routing_structure_json}

-----

## Stage 4 Implementation Contracts (target, completed upstream, and downstream expected)
{contract_reference_json}

-----

## Stage 1.5 Reference Registry (directly extracted raw information from original paper)
{reference_registry_json}

Reference priority rules:
- Treat Stage 1.5 reference registry as directly extracted raw information from original paper text.
- If any other references contain mistakes or omissions, you MUST strictly follow this raw information.
- If this registry contains long formulas or long prompts that clearly correspond to gaps/citation markers in other references, you MUST directly use this registry raw information.

-----

## Implemented code files (read-only; already written)
{implemented_code_block}

-----

# Target file: `{target_file_path}`

## Semantic responsibility
{responsibility}

## Expected internal imports (from architecting)
{json.dumps(internal_deps, ensure_ascii=False)}

## Assigned DAG nodes for this file
{assigned_dag_json}

## Cross-file integration rules
{integration_rules}

## File-specific hazard constraints
{file_hazards_json}

## File-specific critical artifact handoffs
{file_handoffs_json}

-----

# Instruction
Already implemented: {done_file_paths}
Implement ONLY `{target_file_path}` as a complete Python module.
1. One file only; complete implementations (no pass/TODO placeholders).
2. Reuse prior modules via imports; match their public APIs and tensor contracts.
3. Follow the paper when routing or blueprint conflicts with shortcuts.
4. Strong typing and explicit defaults for hyperparameters.
5. No circular imports; config modules must not import core/engine.
6. If this file consumes a critical handoff artifact, implement the consuming API and actually use the artifact; do not compute or accept it and then call a fallback path that ignores it.
7. If this file produces a critical handoff artifact, expose it through the routed public API with enough metadata for the listed consumer.
8. If [DOWNSTREAM EXPECTED STAGE-4 CONTRACTS] require this file's output, make that output compatible now; do not defer schema decisions to future files.
9. If completed contracts and generated code conflict, prefer the generated code for actual call signatures but preserve the contract semantics by adding adapters or fail-fast validation in this file.
10. Do not silently change interface names, artifact names, or intermediate representation structure across files.

## Code: {target_file_path}
```python
# {target_file_path}
...
```""",
        }
    ]


def api_call(msg, gpt_version):
    if "o3-mini" in gpt_version:
        return client.chat.completions.create(
            model=gpt_version,
            reasoning_effort="high",
            messages=msg,
        )
    return client.chat.completions.create(model=gpt_version, messages=msg)


require_file(
    translating_blueprint_path,
    "Run 1_translating.py first or set --translating_blueprint_path.",
)
require_file(
    reconciling_dag_path,
    "Run 2_reconciling.py first or set --reconciling_dag_path.",
)
require_file(
    architecting_structure_path,
    "Run 3_architecting.py first or set --architecting_structure_path.",
)
require_file(
    contracting_contract_path,
    "Run 4_contracting.py first or set --contracting_contract_path.",
)

stage1_text = read_text_file(translating_blueprint_path)
aligning_dag = load_json_file(reconciling_dag_path)
routing_structure = load_json_file(architecting_structure_path)
routing_payload, file_tree = normalize_routing_structure(routing_structure)
contracting_payload = normalize_contracting_contract(load_json_file(contracting_contract_path))
contract_index = build_contract_index(contracting_payload)
reference_registry = []
if reference_registry_path:
    if not os.path.isfile(reference_registry_path):
        print(
            "[ERROR] reference_registry_path was provided but file not found: "
            f"{reference_registry_path}"
        )
        sys.exit(1)
    reference_registry = normalize_reference_registry(load_json_file(reference_registry_path))

if not file_tree:
    print("[ERROR] architecting_structure.json has an empty file_tree.")
    sys.exit(1)

paper_content = load_paper_content(args)
paper_reference_block = build_paper_reference_block(
    format_paper_for_prompt(paper_content, args.paper_format)
)
stage1_and_2_json = build_stage1_and_2_summary(stage1_text, aligning_dag)
routing_structure_json = json.dumps(routing_payload, ensure_ascii=False, indent=2)

aligning_nodes_by_id = {}
for node in aligning_dag.get("computation_graph", []):
    node_id = node.get("node_id")
    if node_id:
        aligning_nodes_by_id[node_id] = node
for node in aligning_dag.get("method_graph", {}).get("nodes", []):
    node_id = node.get("id")
    if node_id and node_id not in aligning_nodes_by_id:
        aligning_nodes_by_id[node_id] = node

sorted_entries = prioritize_launcher_last(topological_sort_file_tree(file_tree))
for entry in sorted_entries:
    entry["_assigned_dag_json"] = build_assigned_dag_json(entry, aligning_nodes_by_id)

topological_order = [e["file_path"] for e in sorted_entries]

artifact_output_dir = f"{output_dir}/unified_engineering_artifacts"
os.makedirs(artifact_output_dir, exist_ok=True)
os.makedirs(output_repo_dir, exist_ok=True)

done_file_dict = {}
done_file_paths = []
engineering_index = {
    "project_name": routing_payload.get("project_name", paper_name),
    "topological_order": topological_order,
    "mode": "unified_engineering",
    "files": [],
}

code_msg = [build_engineering_system_msg(args.paper_format)]
total_accumulated_cost = load_accumulated_cost(f"{output_dir}/accumulated_cost.json")

for file_entry in tqdm(sorted_entries):
    target_file_path = file_entry["file_path"]
    is_launcher = is_launcher_file(file_entry)
    current_stage = f"[UnifiedEngineering] {target_file_path}"
    print(current_stage)

    trajectories = copy.deepcopy(code_msg)
    implemented_block = build_implemented_code_block(done_file_paths, done_file_dict)
    write_msg = build_write_msg(
        target_file_path=target_file_path,
        file_entry=file_entry,
        paper_reference_block=paper_reference_block,
        stage1_and_2_json=stage1_and_2_json,
        routing_structure_json=routing_structure_json,
        contract_reference_json=build_contract_reference(
            sorted_entries,
            contract_index,
            done_file_paths,
            target_file_path,
        ),
        reference_registry_json=build_reference_registry_json(reference_registry),
        implemented_code_block=implemented_block,
        done_file_paths=done_file_paths,
        is_launcher=is_launcher,
        file_hazards_json=build_file_hazard_json(target_file_path, routing_payload),
        file_handoffs_json=build_file_handoff_json(target_file_path, routing_payload),
    )
    trajectories.extend(write_msg)

    completion = api_call(trajectories, gpt_version)
    completion_json = json.loads(completion.model_dump_json())
    message = completion.choices[0].message

    print_response(completion_json)
    total_accumulated_cost = print_log_cost(
        completion_json, gpt_version, current_stage, output_dir, total_accumulated_cost
    )

    safe_name = safe_artifact_name(target_file_path)
    with open(
        f"{artifact_output_dir}/{safe_name}_engineering.txt", "w", encoding="utf-8"
    ) as f:
        f.write(message.content or "")
    with open(
        f"{artifact_output_dir}/{safe_name}_engineering_response.json",
        "w",
        encoding="utf-8",
    ) as f:
        json.dump([completion_json], f, ensure_ascii=False)

    code = extract_code_from_content(message.content or "")
    if not code:
        code = (message.content or "").strip()

    target_output_path = f"{output_repo_dir}/{target_file_path}"
    os.makedirs(os.path.dirname(target_output_path) or ".", exist_ok=True)
    with open(target_output_path, "w", encoding="utf-8") as f:
        f.write(code)

    done_file_dict[target_file_path] = code
    done_file_paths.append(target_file_path)
    engineering_index["files"].append(
        {
            "file_path": target_file_path,
            "output_path": target_output_path,
            "is_launcher": is_launcher,
            "status": "implemented",
        }
    )

with open(f"{output_dir}/unified_engineering_index.json", "w", encoding="utf-8") as f:
    json.dump(engineering_index, f, ensure_ascii=False, indent=2)

save_accumulated_cost(f"{output_dir}/accumulated_cost.json", total_accumulated_cost)
