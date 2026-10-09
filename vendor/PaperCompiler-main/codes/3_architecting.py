from openai import OpenAI
import argparse
import json
import os
import sys

from utils import (
    extract_planning,
    extract_routing_json,
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
add_paper_reference_args(parser)
parser.add_argument(
    "--translating_blueprint_path",
    type=str,
    default="",
    help="Stage-1 blueprint text; default: {output_dir}/translating_blueprint.txt",
)
parser.add_argument(
    "--reconciling_spec_path",
    type=str,
    default="",
    help="Stage-2 reconciling spec JSON; default: {output_dir}/reconciling_spec.json",
)
parser.add_argument("--planning_blueprint_path", type=str, default="", help="Deprecated alias of --translating_blueprint_path.")
parser.add_argument("--aligning_spec_path", type=str, default="", help="Deprecated alias of --reconciling_spec_path.")

args = parser.parse_args()

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

paper_name = args.paper_name
gpt_version = args.gpt_version
output_dir = args.output_dir

translating_blueprint_path = args.translating_blueprint_path.strip() or args.planning_blueprint_path.strip()
if not translating_blueprint_path:
    preferred = f"{output_dir}/translating_blueprint.txt"
    fallback = f"{output_dir}/planning_blueprint.txt"
    translating_blueprint_path = preferred if os.path.isfile(preferred) else fallback

reconciling_spec_path = args.reconciling_spec_path.strip() or args.aligning_spec_path.strip()
if not reconciling_spec_path:
    preferred = f"{output_dir}/reconciling_spec.json"
    fallback = f"{output_dir}/aligning_spec.json"
    reconciling_spec_path = preferred if os.path.isfile(preferred) else fallback

if not os.path.isfile(translating_blueprint_path):
    print(
        f"[ERROR] Blueprint not found: {translating_blueprint_path}. "
        "Run 1_translating.py first or set --translating_blueprint_path."
    )
    sys.exit(1)

if not os.path.isfile(reconciling_spec_path):
    print(
        f"[ERROR] Reconciling spec not found: {reconciling_spec_path}. "
        "Run 2_reconciling.py first or set --reconciling_spec_path."
    )
    sys.exit(1)

with open(translating_blueprint_path, encoding="utf-8") as f:
    stage1_json = f.read()

with open(reconciling_spec_path, encoding="utf-8") as f:
    stage2_json = f.read()

paper_content = load_paper_content(args)
paper_reference_block = build_paper_reference_block(
    format_paper_for_prompt(paper_content, args.paper_format)
)

routing_msg = [
    {
        "role": "system",
        "content": """
You are an expert software architect for ML research reproduction projects.

Task: Stage 3 Project Architecting and Implementation Ownership Planning.

This is the ARCHITECTING stage only.

You are NOT writing code or stubs.
You are NOT re-reading or re-interpreting the original paper.
You are NOT changing the method described by Stage 2.
You are NOT adding new paper facts.
You are NOT producing per-file implementation details; that belongs to the analyzing and coding stages.

Return exactly one valid JSON object. No markdown. No prose outside JSON.

SOURCE PRIORITY:
1. Stage 2 Implementation Alignment Spec. This is authoritative.
2. Stage 1 compact handoff or planning summary, only for context and only when consistent with Stage 2.
3. Routing-level implementation inference, only for file organization, public API boundaries, dependency direction, generation order, and file granularity.

DO NOT use original paper text in this stage.
If Stage 2 seems wrong, vague, incomplete, or too weak to prevent an incorrect implementation, do not silently fix it from memory. Record the issue in unresolved_issues and route a fail-fast, explicit blocker, or minimal-subset-disabled behavior.

STAGE-3 PURPOSE:
Assign Stage-2 contracts, objects, execution steps, runtime boundaries, formula contracts, external protocols, experiment fields, open design choices, and integrity checks to concrete implementation files and public APIs.

Your output must enable later stages to:
- generate files in a safe dependency order,
- avoid duplicated or missing logic,
- avoid circular imports,
- keep files at reasonable size,
- preserve every core contract,
- ensure produced artifacts are consumed,
- keep external protocols explicit,
- fail fast rather than silently using unsupported placeholders.

CORE PRINCIPLE:
Design files from Stage-2 contracts outward.
A file exists because it owns a coherent set of Stage-2 contracts, artifacts, APIs, runtime boundaries, formulas, external protocols, or orchestration responsibilities.

Do not force standard folders such as data/model/train/eval if Stage 2 implies paper-specific modules.
Use generic folders only when they naturally match the alignment spec.

ROUTING RESPONSIBILITIES:
1. Define a practical file tree.
2. Assign every Stage-2 core_path_contract to exactly one primary owner.
3. Assign every Stage-2 execution_flow step to exactly one primary owner unless Stage 2 marks it optional.
4. Assign every Stage-2 method_graph node to exactly one primary owner unless optional.
5. Assign every object/artifact with cross-stage use to a producer and one or more consumers.
6. Assign every runtime_boundary_contract to an owner.
7. Assign every formula_exactness_contract to an owner.
8. Assign every external protocol or open design choice to an owner and fail-fast policy.
9. Define public APIs at a routing level: names, inputs, outputs, contract_refs, producer_or_consumer role, and dependency notes.
10. Define api_dependency_edges and generation_order so coding can proceed without circular imports.
11. Define mode gating: which files/APIs are active for each reproduction mode and which unsupported modes must fail fast.
12. Define cross-file invariants that analyzing/coding must preserve.
13. Define unresolved issues when Stage 2 is too vague to support safe routing.

FILE TREE GRANULARITY RULES:
- Target 8-16 Python files for most projects.
- Use 5-8 files for small algorithmic or metric-only papers.
- Use 12-18 files for multi-mode, external-protocol, tuning/search, agent, retrieval, or benchmark-construction workflows.
- Avoid more than 20 files unless Stage 2 clearly requires it; if exceeded, explain why in file_granularity_checks.
- Avoid one giant file that owns unrelated contracts, external protocols, training, evaluation, and reporting together.
- Avoid tiny files for one-line helpers or generic utilities.
- Do not create generic logger/misc/helper files unless Stage 2 explicitly requires them or multiple routed files need a shared nontrivial utility.
- A file should usually own at least one meaningful Stage-2 contract, artifact, boundary, formula, external protocol, or API group.
- Keep tightly coupled operations together when splitting would obscure the paper method.
- Split components when they have distinct state, lifecycle, external protocol, runtime boundary, formula exactness, or reuse boundary.

FILE SIZE BUDGET GUIDANCE:
For each file, estimate complexity:
- small: <=150 lines expected, simple config/types/wrappers.
- medium: 150-400 lines expected, normal modules.
- large: 400-700 lines expected, complex runner/trainer/evaluator.
- too_large: likely >700 lines; split unless strongly justified.

No file should be marked too_large unless unavoidable.
If a file is large, specify a split recommendation or justify why it remains cohesive.

DEPENDENCY RULES:
- internal_dependencies means this file imports those files.
- api_dependency_edges must use consumer -> producer direction:
  consumer_file imports producer_file symbols.
- Artifact flow is NOT automatically import dependency.
  For example, if module A produces an object and module B consumes it, a runner may orchestrate A then B without B importing A.
- Prefer orchestration modules to connect independent components when direct imports would over-couple low-level modules.
- The dependency graph must be acyclic.
- Config and shared types should have no internal project dependencies.
- Low-level modules must not import runners/orchestrators.
- Data/input modules must not import training/evaluation runners.
- Core method modules must not import trainer/evaluator/runner unless Stage 2 explicitly requires a coupled loop.
- Evaluators may import model/core modules and metrics, but core modules should not import evaluators.
- Runner/orchestrator files may import components to wire the experiment and should usually be generated last.
- Tuning/search modules must not create circular imports with training. If tuning needs short-run training, route a lower-level trial_runner, train_step, or experiment_runner API that both can use safely.
- External protocol interfaces should be leaf-like wrappers when possible.

PUBLIC API RULES:
Each public API must include:
- name,
- kind,
- inputs,
- outputs,
- contract_refs,
- producer_or_consumer role,
- dependency_notes,
- contract.

Do not specify code internals.
Do not write algorithms in full.
Do not create APIs that merely expose a setter for a core artifact unless another routed API computes that artifact and a runtime consumer is specified.
Do not claim support for a mode/strategy through config values alone.

CONSUMER API / DEPENDENCY CONSISTENCY RULE:
For every item in contract_ownership.consumer_apis:
- identify the file that owns the consumer API;
- add a matching api_dependency_edge if the consumer file imports the producer file;
- or add an orchestrated_handoff note if a runner calls both producer and consumer without direct import;
- ensure generation_order places producer dependencies before consumer files or places the orchestrator after both.

If a consumer API is named but no file owns it, add unresolved_issues.

CORE CONTRACT ROUTING RULES:
For each core_path_contract:
- assign exactly one owner_file;
- list producer APIs and consumer APIs;
- state runtime_call_site;
- state active_modes;
- state fail_fast behavior;
- include it in coverage_matrix.

A core contract is not satisfied by:
- a config enum that is never consumed;
- a setter without a routed producer;
- a placeholder interface;
- a simulated objective when real model/data evaluation is required;
- a generic fallback for a named core mode;
- a wrapper whose output semantics do not match the contract;
- an artifact that is produced but never consumed.

WEAK CONTRACT RULE:
If Stage 2 contains weak phrases for a core contribution, such as:
- "one or more",
- "as needed",
- "optional",
- "simplified",
- "one strategy",
- "generic module",
- "can be implemented",
- "external setter",
- "mapping_config only",
- "placeholder if unavailable",
then route conservatively:
1. record an unresolved_issue,
2. require either full mode coverage or explicit minimal-subset mode gating,
3. require unsupported modes to fail fast or be disabled,
4. forbid silent fallback to a generic implementation.

MULTI-MODE / MULTI-STRATEGY RULES:
If Stage 2 says full reproduction requires multiple named modes, strategies, mappings, losses, branches, protocols, or evaluators:
- either route all required modes to owners, producer APIs, consumer APIs, and runtime call sites;
- or route a declared minimal subset and explicitly disable/fail-fast unsupported modes.
Do not silently route unsupported modes to a generic fallback.
Do not claim support through config values alone.

RUNTIME BOUNDARY RULES:
For each runtime_boundary_contract:
- assign owner_file;
- assign upstream producer and downstream consumer;
- state where the transition occurs;
- state forbidden transition;
- ensure the owner is neither too low-level nor too high-level;
- include the boundary in file_tree.owned_runtime_boundaries and coverage_matrix.runtime_boundary_contracts.

Examples:
- prompt/context tokens -> target/loss tokens;
- raw image -> augmentation -> normalization -> device transfer -> model input;
- source logits -> mapped target logits;
- generated judgment -> training target;
- checkpoint state -> inference/evaluation state;
- tuning result -> final training/model construction;
- retrieval index built -> query-time retrieval;
- simulator state -> reward/metric computation.

CORE RUNTIME ARTIFACT HANDOFF RULE:
Every core artifact that is produced for a later step must appear in critical_artifact_handoffs, especially:
- target text or labels,
- augmented/transformed inputs,
- normalized embeddings,
- logits,
- mappings/adapters,
- retrieved items,
- tuning/search results,
- checkpoints/states,
- metric inputs,
- generated samples,
- external protocol outputs.

If an artifact is produced and consumed only inside the same file, it may be omitted from critical_artifact_handoffs only if it is not cross-file and not a Stage-2 core artifact. Otherwise include it.

FORMULA EXACTNESS RULES:
For each formula_exactness_contract:
- assign owner_file;
- route required inputs and outputs;
- route any masking/indexing/denominator/aggregation/tie-break/determinant correction requirements;
- do not bury formula exactness only in comments.
If exact details are unknown_from_paper, route the open design choice to config or fail-fast policy.

EXTERNAL PROTOCOL RULES:
For external_protocol or unresolved_core_protocol:
- route explicit interface files/APIs;
- specify allowed coding behavior:
  - full_implementation
  - follow_external_protocol
  - load_released_artifact
  - implement_external_api
  - interface_with_explicit_blocker
  - fail_fast_if_unavailable
- do not route heuristic replacements as core implementations.

MODE GATING RULES:
Every file and major API must specify active_modes:
- full_raw_data_rebuild
- train_from_released_or_precomputed_artifacts
- inference_or_evaluation_only
- ablation_or_analysis_only
- all_modes

If a file/API is not active in a mode, specify whether it is:
- disabled
- optional
- external_artifact_required
- fail_fast_if_called

ORCHESTRATION RULES:
If a pipeline requires sequencing multiple independent components, create an orchestration file such as:
- main.py,
- experiment_runner.py,
- train_runner.py,
- inference_runner.py,
- pipeline.py,
only when needed.

The orchestrator should:
- import lower-level producer/consumer components,
- call them in the correct order,
- enforce mode gating and fail-fast conditions,
- pass artifacts between components,
- be generated last or near last.

Do not force an orchestrator if the project is small and one existing runner can safely own orchestration.

OUTPUT JSON SCHEMA:
{
  "project_name": "string",

  "routing_scope": {
    "main_method": "string",
    "included_components": [],
    "optional_components_as_hooks": [],
    "excluded_or_deferred_components": [],
    "baselines_policy": "string",
    "analysis_policy": "string",
    "source_authority": "Stage 2 alignment spec is authoritative; no original paper text used in routing."
  },

  "global_contracts": {
    "dependency_direction": [],
    "object_conventions": [],
    "runtime_boundary_rules": [],
    "single_owner_rules": [],
    "fact_boundary_rules": [],
    "stage2_authority_rules": [],
    "file_granularity_rules": [],
    "artifact_flow_vs_import_rules": []
  },

  "mode_gating": [
    {
      "mode": "full_raw_data_rebuild | train_from_released_or_precomputed_artifacts | inference_or_evaluation_only | ablation_or_analysis_only",
      "required_files": [],
      "disabled_files": [],
      "external_artifacts_required": [],
      "fail_fast_conditions": []
    }
  ],

  "implementation_hazards": [
    {
      "hazard_id": "string",
      "description": "string",
      "source_contract_refs": [],
      "fact_class": "paper_fact | external_contract | implementation_choice | unresolved",
      "implementation_status": "implementable_now | follow_external_protocol | load_released_artifact | implement_external_api | interface_only | unresolved_core_protocol | expose_as_config | minimal_subset_only",
      "primary_owner": "relative/path.py",
      "must_not_own": [],
      "contract": "string",
      "allowed_coding_behavior": "full_implementation | follow_external_protocol | load_released_artifact | implement_external_api | interface_with_explicit_blocker | fail_fast_if_unavailable | expose_as_config | disable_unsupported_modes",
      "downstream_failure_if_wrong": "string"
    }
  ],

  "contract_ownership": [
    {
      "contract_id": "string",
      "owner_file": "relative/path.py",
      "producer_apis": [],
      "consumer_apis": [],
      "runtime_call_site": "relative/path.py::symbol or description",
      "active_modes": [],
      "fail_fast_behavior": "string",
      "notes": "string"
    }
  ],

  "critical_artifact_handoffs": [
    {
      "handoff_id": "string",
      "artifact": "string",
      "source_contract_refs": [],
      "producer_file": "relative/path.py",
      "consumer_file": "relative/path.py",
      "producer_api": "string",
      "consumer_api": "string",
      "runtime_call_site": "string",
      "scope": "global | per_instance | per_batch | per_step | per_episode | other",
      "required_invariant": "string",
      "forbidden_implementation": "string",
      "status": "implementable | external_core_protocol | unresolved",
      "active_modes": [],
      "orchestrated_by": "relative/path.py or empty"
    }
  ],

  "api_dependency_edges": [
    {
      "consumer_file": "relative/path.py",
      "producer_file": "relative/path.py",
      "imports": [],
      "reason": "string",
      "contract_refs": []
    }
  ],

  "orchestrated_handoffs": [
    {
      "orchestrator_file": "relative/path.py",
      "producer_file": "relative/path.py",
      "consumer_file": "relative/path.py",
      "artifact": "string",
      "producer_api": "string",
      "consumer_api": "string",
      "reason_no_direct_import": "string",
      "contract_refs": []
    }
  ],

  "generation_order": [
    {
      "order": 1,
      "file_path": "relative/path.py",
      "reason": "string",
      "depends_on": []
    }
  ],

  "file_tree": [
    {
      "file_path": "relative/path.py",
      "module_role": "free-form role derived from Stage-2 contracts",
      "semantic_responsibility": "string",
      "active_modes": [],
      "disabled_or_fail_fast_modes": [
        {
          "mode": "string",
          "behavior": "disabled | optional | external_artifact_required | fail_fast_if_called",
          "reason": "string"
        }
      ],
      "estimated_size": "small | medium | large | too_large",
      "split_or_merge_rationale": "string",
      "owned_contracts": [],
      "owned_runtime_boundaries": [],
      "owned_formula_contracts": [],
      "must_implement": [],
      "must_not_implement": [],
      "public_api": [
        {
          "name": "string",
          "kind": "class | function | dataclass | constant | config_object",
          "inputs": [],
          "outputs": [],
          "contract_refs": [],
          "producer_or_consumer": "producer | consumer | both | orchestrator | config",
          "dependency_notes": "string",
          "contract": "string"
        }
      ],
      "stage2_alignment_usage": {
        "owned_execution_flow_steps": [],
        "owned_method_graph_nodes": [],
        "owned_object_contracts": [],
        "owned_runtime_boundary_contracts": [],
        "owned_formula_exactness_contracts": [],
        "owned_critical_handoffs": [],
        "consumed_stage2_objects": [],
        "produced_stage2_objects": []
      },
      "consumes_objects": [],
      "produces_objects": [],
      "assigned_experiment_protocol_fields": [],
      "assigned_open_design_choices": [],
      "internal_dependencies": [],
      "source_evidence": [],
      "risk_notes": []
    }
  ],

  "coverage_matrix": {
    "core_path_contracts": [
      {
        "contract_id": "string",
        "primary_owner": "relative/path.py",
        "runtime_call_site": "string",
        "secondary_consumers": []
      }
    ],
    "execution_flow_steps": [
      {
        "id": "string",
        "primary_owner": "relative/path.py",
        "secondary_consumers": []
      }
    ],
    "method_graph_nodes": [
      {
        "id": "string",
        "primary_owner": "relative/path.py",
        "secondary_consumers": []
      }
    ],
    "object_contracts": [
      {
        "name": "string",
        "producer": "relative/path.py",
        "consumers": []
      }
    ],
    "runtime_boundary_contracts": [
      {
        "boundary_id": "string",
        "owner": "relative/path.py",
        "upstream_file": "relative/path.py",
        "downstream_file": "relative/path.py"
      }
    ],
    "formula_exactness_contracts": [
      {
        "formula_id": "string",
        "owner": "relative/path.py",
        "consumers": []
      }
    ],
    "critical_artifact_handoffs": [
      {
        "handoff_id": "string",
        "producer_file": "relative/path.py",
        "consumer_file": "relative/path.py"
      }
    ],
    "experiment_protocol_fields": [
      {
        "field": "string",
        "primary_owner": "relative/path.py"
      }
    ],
    "open_design_choices": [
      {
        "item": "string",
        "owner": "relative/path.py",
        "policy": "string"
      }
    ],
    "hazards": [
      {
        "hazard_id": "string",
        "primary_owner": "relative/path.py"
      }
    ]
  },

  "dependency_graph_checks": [
    {
      "check_id": "string",
      "description": "string",
      "status": "pass | needs_attention",
      "related_files": []
    }
  ],

  "file_granularity_checks": [
    {
      "check_id": "string",
      "description": "string",
      "status": "pass | needs_attention",
      "related_files": [],
      "recommendation": "string"
    }
  ],

  "unresolved_issues": [
    {
      "issue_id": "string",
      "description": "string",
      "severity": "high | medium | low",
      "source": "planning | aligning | routing",
      "recommended_handling": "string",
      "affected_contracts": []
    }
  ],

  "handoff_to_analyzing": {
    "routing_summary": "string",
    "highest_priority_files": [],
    "contracts_requiring_extra_attention": [],
    "runtime_boundaries_requiring_extra_attention": [],
    "formula_contracts_requiring_extra_attention": [],
    "files_that_should_be_generated_last": [],
    "external_or_unresolved_blockers": []
  }
}

VALIDATION BEFORE OUTPUT:
- Stage 2 is the authority; original paper text is not used in routing.
- Every Stage-2 core_path_contract has exactly one primary owner.
- Every Stage-2 execution_flow step has exactly one primary owner unless optional.
- Every Stage-2 method_graph node has exactly one primary owner unless optional.
- Every Stage-2 object/artifact with downstream use has producer and consumers.
- Every Stage-2 runtime_boundary_contract has an owner and transition location.
- Every Stage-2 formula_exactness_contract has an owner.
- Every critical artifact handoff has producer_file, consumer_file, producer_api, consumer_api, runtime_call_site, required_invariant, forbidden_implementation.
- Every core runtime artifact that crosses files appears in critical_artifact_handoffs or orchestrated_handoffs.
- Every consumer_api in contract_ownership has either a matching api_dependency_edge or orchestrated_handoff.
- generation_order is consistent with api_dependency_edges.
- Artifact flow is not mistaken for direct import dependency when orchestration is more appropriate.
- Every experiment/config field needed for code generation has an owner.
- Every open_design_choice has an owner and safe policy.
- Every hazard has exactly one primary owner and clear must_not_own boundaries.
- Every external_protocol or unresolved_core_protocol has allowed_coding_behavior that forbids heuristic substitution.
- Unsupported core modes fail fast or are disabled.
- No config enum, setter, wrapper, simulated objective, generic fallback, or placeholder is routed as satisfying a core contract.
- No generated artifact, transformed parameter, metadata, state, index, prompt target, mapping, metric input, tuning result, or checkpoint is left without a consumer if Stage 2 marks it implementation-critical.
- No file owns unrelated contracts that would likely exceed a reasonable file size.
- No file is tiny without owning a meaningful contract/API group.
- Dependency graph is acyclic.
- Runner/orchestrator files are generated last or near last.
- No file tree category overrides Stage-2 semantics.
- Ambiguous upstream facts or weak Stage-2 contracts are listed in unresolved_issues, not silently implemented.
- Output valid JSON only.
"""
    },
    {
        "role": "user",
        "content": f"""
Below are the Stage 2 implementation alignment spec and, optionally, the Stage 1 compact planning handoff.

Use Stage 2 as the authoritative source.
Use Stage 1 only for context if it is consistent with Stage 2.
Do not use the original paper text in this stage.

[STAGE 2: IMPLEMENTATION ALIGNMENT SPEC]
{stage2_json}

[OPTIONAL STAGE 1: COMPACT PLANNING HANDOFF]
{stage1_json}

TASK:
Create the Stage-3 routing plan by assigning the Stage-2 alignment spec to files, APIs, owners, dependencies, generation order, mode gating, and cross-file contracts.

Focus on:
- practical file tree design,
- strict use of Stage-2 core contracts,
- implementation hazard ownership,
- public APIs for later analyzing/coding,
- producer/consumer APIs for critical artifact handoffs,
- runtime boundary ownership,
- formula exactness ownership,
- dependency direction and generation order,
- distinction between artifact flow and direct imports,
- prevention of duplicated, missing, or unconsumed logic,
- mode gating and fail-fast behavior,
- file granularity control,
- unresolved issue reporting when Stage 2 is too weak or ambiguous.

Do not create a new workflow.
Do not force a standard ML project template when Stage 2 implies paper-specific modules.
Do not include code or stubs.

Return exactly one valid JSON object following the schema in the system message.
"""
    }
]


def api_call(msg, gpt_version):
    if "o3-mini" in gpt_version:
        completion = client.chat.completions.create(
            model=gpt_version,
            reasoning_effort="high",
            messages=msg,
        )
    else:
        completion = client.chat.completions.create(
            model=gpt_version,
            messages=msg,
        )
    return completion


responses = []
trajectories = []
total_accumulated_cost = load_accumulated_cost(f"{output_dir}/accumulated_cost.json")

current_stage = "[Architecting] File tree from blueprint + DAG"
print(current_stage)

trajectories.extend(routing_msg)
completion = api_call(trajectories, gpt_version)

completion_json = json.loads(completion.model_dump_json())
print_response(completion_json)
temp_total_accumulated_cost = print_log_cost(
    completion_json, gpt_version, current_stage, output_dir, total_accumulated_cost
)
total_accumulated_cost = temp_total_accumulated_cost
responses.append(completion_json)

message = completion.choices[0].message
trajectories.append({"role": message.role, "content": message.content})

save_accumulated_cost(f"{output_dir}/accumulated_cost.json", total_accumulated_cost)

os.makedirs(output_dir, exist_ok=True)

with open(f"{output_dir}/architecting_response.json", "w", encoding="utf-8") as f:
    json.dump(responses, f, ensure_ascii=False)

with open(f"{output_dir}/architecting_trajectories.json", "w", encoding="utf-8") as f:
    json.dump(trajectories, f, ensure_ascii=False)

_traj_path = f"{output_dir}/architecting_trajectories.json"
_context_lst = extract_planning(_traj_path)
_routing_body = _context_lst[0] if _context_lst else ""
with open(f"{output_dir}/architecting_plan.txt", "w", encoding="utf-8") as f:
    f.write(_routing_body)

_routing_obj, _json_str = extract_routing_json(_routing_body)
if _routing_obj is not None:
    with open(f"{output_dir}/architecting_plan.json", "w", encoding="utf-8") as f:
        json.dump(_routing_obj, f, ensure_ascii=False, indent=2)
else:
    if _json_str:
        with open(f"{output_dir}/architecting_plan_raw.txt", "w", encoding="utf-8") as f:
            f.write(_json_str)
    print(
        "[ERROR] Failed to parse architecting JSON from LLM output. "
        "Expected top-level key: file_tree. "
        f"See {output_dir}/architecting_plan.txt"
    )
    sys.exit(1)
