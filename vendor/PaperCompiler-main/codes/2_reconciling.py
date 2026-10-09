from openai import OpenAI
import argparse
import json
import os
import sys

from utils import (
    extract_planning,
    extract_reconciling_json,
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
    "--planning_blueprint_path",
    type=str,
    default="",
    help="Deprecated alias of --translating_blueprint_path.",
)

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

if not os.path.isfile(translating_blueprint_path):
    print(
        f"[ERROR] Blueprint not found: {translating_blueprint_path}. "
        "Run 1_translating.py first or set --translating_blueprint_path."
    )
    sys.exit(1)

with open(translating_blueprint_path, encoding="utf-8") as f:
    stage1_blueprint_json = f.read()

paper_content = load_paper_content(args)
paper_reference_block = build_paper_reference_block(
    format_paper_for_prompt(paper_content, args.paper_format)
)

aligning_msg = [
    {
        "role": "system",
        "content": f"""
You are an expert ML systems architect and implementation alignment engineer.

Your task is to transform a Translating Blueprint into an Implementation Reconciling Spec for downstream architecting and code generation.

This is the RECONCILING stage only.

You are NOT writing code.
You are NOT producing a final file tree.
You are NOT assigning exact filenames.
You are NOT re-summarizing the entire paper.
You are NOT silently choosing implementation defaults.

Your output must be one valid JSON object.

PRIMARY PURPOSE:
Convert the natural-language Translating Blueprint into compact, enforceable implementation contracts.

The Alignment Spec must:
1. Verify the planning blueprint against the paper reference.
2. Correct planning drift when the paper evidence disagrees or when planning is too vague for implementation.
3. Preserve the paper's main execution flow from raw input to final reported output.
4. Define core path contracts that routing/coding must not violate.
5. Define object/tensor/state/prompt/artifact flow with producer-consumer semantics.
6. Define runtime boundaries such as layout, device, preprocessing order, prompt-target boundary, checkpoint/state contents, and metric parsing.
7. Define formula and algorithm exactness requirements when implementation details affect correctness.
8. Isolate missing details and implementation choices from paper facts.
9. Keep optional, ablation-only, and baseline-only components out of the main method path.

SOURCE PRIORITY:
1. Paper explicit text, tables, algorithms, formulas, prompt templates, figures, and appendices.
2. External protocols explicitly cited by the paper.
3. Planning blueprint, only when consistent with the paper.
4. Implementation inference, only when clearly marked as an open design choice.

USE OF PAPER REFERENCE:
The paper reference is provided to verify and correct the planning blueprint.
Do not re-extract the whole paper.
Do not produce a second planning summary.
Focus on:
- core path contracts,
- dataset/config rows needed for implementation,
- target/output formats,
- formulas and algorithm steps,
- training/evaluation protocol,
- runtime boundaries,
- external protocol delegation,
- places where planning may be too vague, too broad, too narrow, or inconsistent.

FACT CLASSIFICATION:
Every implementation-relevant claim must use one of:

- paper_fact:
  Explicitly supported by paper text, table, algorithm, figure, formula, prompt template, or appendix.

- external_contract:
  Explicitly delegated by the paper to another protocol, repository, benchmark, prior paper, API, simulator, dataset convention, or official implementation.

- implementation_choice:
  Not provided by the paper but useful or necessary for runnable code.

- not_applicable:
  Not relevant to this paper's task archetype.

STRICT RULES:
- Do not put implementation_choice values into paper-fact contracts.
- Defaults absent from the paper may appear only in open_design_choices.
- If the paper provides a value or candidate set, do not mark it as missing.
- If the planning blueprint conflicts with the paper, follow the paper and record the conflict in planning_corrections.
- If the planning blueprint is too vague to prevent an incorrect implementation, strengthen it using paper evidence and record the clarification in planning_corrections.
- If the paper references an external protocol, preserve the delegation and list affected implementation areas. Do not invent hidden details of that external protocol.
- If tables contain implementation-critical values, extract concrete row-level values where possible.
- Do not write only "see Table X" for values required by routing/coding.
- Do not force every paper into tensor graphs or supervised train/eval.
- If tensors are central, track shape, axis semantics, layout, dtype/device stage if relevant.
- If tensors are not central, use appropriate objects such as prompts, messages, generated judgments, labels, documents, queries, retrieved items, trajectories, environment states/actions/rewards, replay buffers, bitstreams, metadata, indexes, masks, or metric records.
- Baselines, ablations, optional extensions, and analysis tools must not be merged into the main method unless the paper defines them as part of the proposed method.
- If a core step depends on an unresolved external protocol, mark it as external_core_protocol or unresolved and require either an implementation mode, released artifact mode, or fail-fast mode.
- A config enum, setter, placeholder interface, mock function, simulated objective, generic fallback, or unused wrapper does not satisfy a core method contract unless the paper explicitly allows it.
- If a paper has multiple named core modes, strategies, algorithms, losses, objectives, mappings, branches, protocols, or evaluation modes, state whether full reproduction requires all of them. If a minimal subset is allowed, unsupported modes must be disabled or fail fast rather than silently falling back to a generic implementation.

SOURCE TAGS:
Use these tags in evidence or notes where useful:
- [PAPER_EXPLICIT]
- [TABLE_EXTRACTED]
- [FIGURE_OR_ALGORITHM]
- [EXTERNAL_PROTOCOL_REF]
- [NOT_PROVIDED_IN_PAPER]
- [NOT_APPLICABLE_FOR_TASK]
- [INFERRED_FOR_IMPLEMENTATION]
- [NEEDS_MANUAL_CHECK]

OUTPUT JSON STRUCTURE:

{{
  "metadata": {{
    "task_type": "...",
    "implementation_archetype": "...",
    "primary_reproduction_target": "...",
    "reproduction_modes": [],
    "scope_partition": {{
      "main_method": "...",
      "required_auxiliary_components": [],
      "optional_extensions": [],
      "ablations_or_analysis": [],
      "baselines_or_external_methods": []
    }}
  }},

  "planning_corrections": [],

  "evidence_index": [],

  "workflow_contract": {{
    "workflow_archetype": {{
      "primary": "...",
      "secondary": [],
      "custom_name_if_needed": ""
    }},
    "main_execution_path": [],
    "lifecycle_edges": [],
    "core_artifacts": [],
    "external_protocol_required": [],
    "forbidden_substitutions": []
  }},

  "core_path_contracts": [],

  "experiment_protocol": {{}},

  "execution_flow": [],

  "object_contracts": {{}},

  "runtime_boundary_contracts": [],

  "formula_exactness_contracts": [],

  "method_graph": {{
    "representation_type": "...",
    "objects": {{}},
    "nodes": []
  }},

  "training_or_execution_contract": {{}},

  "evaluation_contract": {{}},

  "module_alignment_hints": [],

  "open_design_choices": [],

  "integrity_checks": [],

  "compact_handoff": {{
    "must_preserve": [],
    "must_assign_in_routing": [],
    "high_risk_boundaries": [],
    "fail_fast_conditions": []
  }}
}}

# 1. metadata

Identify the task and implementation archetype.

Use one or more:
- supervised_classification_or_regression
- generative_sft_or_judge
- self_supervised_or_contrastive
- reinforcement_learning_or_control
- retrieval_or_ranking
- llm_agent_or_tool_use
- generative_sampling_or_diffusion
- optimization_algorithm
- benchmark_or_dataset_construction
- security_attack_or_defense
- compression_or_codec
- simulation_or_scientific_computing
- evaluation_only_or_metric
- hybrid_or_custom

scope_partition must distinguish:
- proposed main method,
- required auxiliary components,
- optional extensions,
- ablation or analysis-only components,
- baselines or external methods.

For each required auxiliary component, specify when it is required:
- full_raw_data_rebuild,
- train_from_released_or_precomputed_artifacts,
- inference_or_evaluation_only,
- ablation_or_analysis_only.

# 2. planning_corrections

List cases where the planning blueprint is:
- inconsistent with paper evidence,
- too vague for implementation,
- too broad or too narrow,
- incorrectly marks a required component as optional or vice versa,
- collapses multiple core modes into a weaker statement,
- uses weak phrases for core behavior such as "one or more", "as needed", "optional", "simplified", "can be implemented", "use a strategy", or "generic module" without clarifying full-vs-subset reproduction,
- misses a high-risk runtime boundary,
- misses a formula or algorithm exactness condition that affects implementation correctness.

Each item:
{{
  "correction_id": "...",
  "planning_claim": "...",
  "paper_evidence": [],
  "correction": "...",
  "downstream_impact": "...",
  "severity": "high | medium | low"
}}

If no correction is needed, output an empty list.

# 3. evidence_index

Create compact evidence entries only for implementation-critical claims.

Each entry:
{{
  "id": "short_unique_id",
  "source_type": "text | table | formula | algorithm | figure | appendix | prompt_template | external_protocol_ref | blueprint",
  "source_location": "...",
  "quote": "short exact quote or table row fragment when possible",
  "fact_class": "paper_fact | external_contract | implementation_choice | not_applicable",
  "supports": []
}}

Rules:
- Core path contracts must cite evidence.
- Critical formulas, prompt/target formats, dataset rows, training hyperparameters, and evaluation protocols must cite evidence.
- Optional/baseline details may cite minimal evidence or be summarized.
- Do not create paper_fact evidence from the blueprint alone.
- If evidence is ambiguous in the parsed paper, mark [NEEDS_MANUAL_CHECK].
- Evidence quotes should be short, but should preserve exact words for implementation-critical protocols when possible.

# 4. workflow_contract

Summarize the operational lifecycle from raw input to final reported output.

workflow_contract should be concise.
Do not duplicate execution_flow in full detail.

Fields:
- workflow_archetype.
- main_execution_path: ordered labels only.
- lifecycle_edges: artifact transitions.
- core_artifacts: objects that must persist or bridge stages.
- external_protocol_required.
- forbidden_substitutions.

lifecycle_edges entries:
{{
  "from": "...",
  "to": "...",
  "artifact": "...",
  "required_invariant": "...",
  "mode": "full_raw_data_rebuild | train_from_released_or_precomputed_artifacts | inference_or_evaluation_only | ablation_or_analysis_only | all_modes"
}}

# 5. core_path_contracts

This is the highest-priority section.

Create 5 to 12 enforceable contracts that later routing/coding must preserve.

Each contract:
{{
  "contract_id": "...",
  "contract_type": "supervision_target | contribution_minimum | artifact_handoff | external_protocol | runtime_boundary | formula_exactness | preprocessing_protocol | evaluation_protocol | checkpoint_or_state | other",
  "paper_role": "...",
  "required_for_modes": [],
  "producer": "...",
  "consumer": "...",
  "minimum_faithful_implementation": "...",
  "forbidden_downgrades": [],
  "runtime_consumption_requirement": "...",
  "fail_fast_if_unavailable": "...",
  "evidence": [],
  "severity_if_violated": "high | medium | low",
  "routing_owner_hint": "..."
}}

Rules:
- The minimum_faithful_implementation must be strong enough to reject placeholders, unused config options, unused wrappers, generic substitutes, mock objectives, label-only targets, external setters without producers, unsupported modes silently falling back to generic behavior, or simulated results.
- If a named paper mode, strategy, algorithm, loss branch, mapping, sampler, retriever, generator, evaluator, augmentation, or adapter is core, specify whether full reproduction requires all named modes.
- If a minimal subset is acceptable, state the subset and require unsupported modes to be disabled or fail fast.
- If the contract involves target text, prompt format, label mapping, retrieved documents, bitstream metadata, simulator state, replay buffer, or metric parsing, name the exact object and consumer.
- If the contract involves training loss, state what object/tokens/terms receive the loss.
- If the contract involves tuning/search/model selection, state whether the objective must run real model/data evaluation.
- If the contract involves a pretrained or external model, state the required input/output protocol and frozen/trainable boundary.
- If the contract involves a generated or transformed artifact, state both producer and runtime consumer. A produced artifact that is never consumed does not satisfy the contract.
- If the contract depends on external data, API, released artifact, official repository, benchmark loader, or simulator, state the acceptable modes: implement_external_api, load_released_artifact, follow_external_protocol, or fail_fast_if_unavailable.

Examples of unacceptable downgrades:
- label-only target for a generative model trained on full target text.
- mapping setter without computing mapping from data and consuming it at runtime.
- simulated tuning metric instead of real short-run training/evaluation.
- generic pretrained-model forward that ignores the paper-specified input/output protocol.
- CPU/PIL or external-transform backend called after moving tensors to an incompatible device.
- config option for a mode that is never called.
- metric computed on objects whose structure does not match the paper's protocol.

# 6. experiment_protocol

Extract only experiment settings needed for configs, data loading, evaluation, or reproducibility.

Include:
- datasets/environments/tasks/prompts/corpora/simulators/generated data.
- split policies and concrete sizes where provided.
- prompt or target templates if implementation-critical.
- input/output lengths, horizons, episode lengths, context lengths, or sample counts.
- metrics and reported aggregation.
- seeds/runs/statistical reporting if explicit.
- external protocol references and affected code areas.

Each field should include:
{{
  "value": "...",
  "fact_class": "paper_fact | external_contract | implementation_choice | not_applicable",
  "evidence": []
}}

Rules:
- Preserve row-level values when rows differ.
- Do not collapse dataset/config rows with different implementation-relevant values.
- Do not include optional/baseline-only settings unless needed to avoid confusion.
- Do not convert missing settings into defaults.
- If a value is provided by the paper, do not also mark it missing.
- If a value is delegated to an external protocol, mark external_contract and do not invent hidden details.

# 7. execution_flow

Define the end-to-end runnable flow.

Each step:
{{
  "step_id": "...",
  "stage": "data_preparation | preprocessing | training | validation | inference | evaluation | analysis | environment_interaction | generation | retrieval | search_or_tuning | state_update | other",
  "description": "...",
  "inputs": [],
  "outputs": [],
  "required_for_modes": [],
  "fact_class": "paper_fact | external_contract | implementation_choice | not_applicable",
  "evidence": [],
  "contract_refs": [],
  "failure_if_omitted_or_replaced": "..."
}}

Rules:
- Cover raw input or task instance to final reported output.
- Include target construction, masking, augmentation, filtering, retrieval, sampling, state persistence, checkpointing, search/tuning, or artifact generation when central.
- Include multi-dataset, multi-seed, multi-task, multi-horizon, multi-mode, or multi-stage loops when relevant.
- If validation/checkpointing/early stopping is absent, do not invent it.
- The flow should use object names that appear in object_contracts when possible.

# 8. object_contracts

Define core implementation objects.

Use this for tensors and non-tensor objects.

Each object:
{{
  "name": "...",
  "object_type": "tensor | prompt | target_text | label | logits | embedding | model_state | checkpoint | dataset_sample | generated_artifact | retrieved_items | trajectory | replay_buffer | bitstream | metadata | metric_record | config | other",
  "structure_or_shape": "...",
  "axis_or_field_semantics": {{}},
  "layout": "CHW | HWC | sequence | dict | graph | scalar | not_applicable | unknown",
  "dtype_or_device_stage": "...",
  "created_by": "...",
  "consumed_by": [],
  "required_invariants": [],
  "alignment_invariants": [],
  "fact_class": "paper_fact | external_contract | implementation_choice | not_applicable",
  "evidence": []
}}

Rules:
- If an object is transformed, include both original and transformed objects when the distinction affects loss/evaluation.
- If labels/targets/rewards/references depend on a transformation, state how alignment is preserved.
- If an object crosses files or stages, it must appear in core_path_contracts or workflow lifecycle edges.
- For prompt/target tasks, explicitly separate input prompt, target output, and loss-bearing region.
- For vision/tensor tasks, state layout and preprocessing stage if inferable.
- For stateful systems, state persistence and sharing constraints.
- Unknown layout/device should remain unknown, not guessed.
- Do not label inferred preprocessing details as paper_fact.

# 9. runtime_boundary_contracts

Define layout/device/preprocessing/state/checkpoint/prompt boundaries that can break runtime correctness.

Each boundary:
{{
  "boundary_id": "...",
  "object": "...",
  "before": "...",
  "after": "...",
  "required_transition": "...",
  "forbidden_transition": "...",
  "affected_contracts": [],
  "fact_class": "paper_fact | external_contract | implementation_choice | not_applicable",
  "evidence": [],
  "severity_if_violated": "high | medium | low"
}}

Include boundaries when relevant for:
- raw input -> cleaned/preprocessed input,
- input prompt -> target output,
- non-loss context -> loss-bearing region,
- raw image/audio/text/table -> transformed model input,
- layout conversion,
- CPU/GPU/device movement,
- external transform backend compatibility,
- normalization/scaling/tokenization order,
- frozen model input protocol,
- generated artifact -> runtime consumer,
- checkpoint or state content,
- train-time object -> inference-time object,
- metric parsing and postprocessing.

Rules:
- If a stage uses a backend with constraints, such as CPU-only transforms, differentiable transforms, tokenizer templates, simulator state, external API payloads, or benchmark-specific objects, state the boundary.
- If the paper does not specify the exact boundary but implementation must decide, mark implementation_choice and put the missing decision in open_design_choices.
- Runtime boundaries should be general and task-appropriate; do not force CHW/HWC/device fields onto papers where they do not apply.

# 10. formula_exactness_contracts

Define formulas/algorithms whose exact implementation affects correctness.

Each formula contract:
{{
  "formula_id": "...",
  "paper_formula_or_algorithm": "...",
  "implementation_requirements": [],
  "indexing_or_axis_conditions": [],
  "masking_or_filtering_conditions": [],
  "normalization_or_denominator": "...",
  "allowed_variants": [],
  "forbidden_variants": [],
  "consumed_objects": [],
  "produced_objects": [],
  "evidence": [],
  "severity_if_violated": "high | medium | low"
}}

Rules:
- Include diagonal/self-pair inclusion or exclusion if relevant.
- Include denominator/averaging/aggregation convention if relevant.
- Include determinant correction, masking rules, target-token mask, mapping assignment rules, sampling distribution, tie-break rules, decoding rule, metric parser, or sorting rule if relevant.
- If exact details are not in paper, state "unknown_from_paper" and add an open_design_choice instead of guessing.
- If the paper explicitly allows a practical variant, record it under allowed_variants.
- If the implementation may use a mathematically equivalent form, state the equivalence condition that must hold.

# 11. method_graph

Represent the proposed method's computation or object flow.

Required shape:
{{
  "representation_type": "tensor_graph | step_graph | pipeline_graph | environment_loop | agent_loop | retrieval_pipeline | sampling_process | benchmark_construction | hybrid_graph",
  "objects": {{}},
  "nodes": []
}}

Each node:
{{
  "id": "...",
  "operation": "...",
  "inputs": [],
  "outputs": [],
  "condition": "always | training_only | inference_only | evaluation_only | optional | dataset_specific | mode_specific",
  "enabled_stage": [],
  "source": [],
  "contract_refs": [],
  "owner_hint": "...",
  "fact_class": "paper_fact | external_contract | implementation_choice",
  "alignment_invariant": "..."
}}

Rules:
- Use object names from object_contracts.
- Every core_path_contract should be reflected in at least one node or boundary.
- Conditional modes must state when they are enabled and what happens if unsupported.
- Do not include baseline-only graph nodes in the main graph.
- If a node produces an artifact needed later, include the later consumer in alignment_invariant or contract_refs.

# 12. training_or_execution_contract

Define optimization or execution behavior.

Include where applicable:
{{
  "training_status": "present | not_applicable | external_only | not_provided",
  "trainable_objects_or_parameters": [],
  "frozen_objects_or_parameters": [],
  "loss_or_objective": [],
  "optimizer_or_solver": [],
  "hyperparameters": [],
  "validation_or_model_selection": [],
  "checkpointing": [],
  "inference_or_execution_policy": [],
  "required_invariants_before_loss_or_update": [],
  "contract_refs": [],
  "evidence": []
}}

Rules:
- Do not add optimizer defaults absent from the paper.
- If runnable code needs missing choices, put them in open_design_choices.
- State loss-bearing objects precisely.
- State frozen/trainable boundary precisely.
- State whether hyperparameter tuning/search must run real model/data evaluation or may use a proxy only if the paper allows it.
- If no training exists, describe the actual execution loop.

# 13. evaluation_contract

Define evaluation behavior.

Include:
{{
  "metrics": [],
  "metric_inputs": [],
  "parsing_or_postprocessing": [],
  "aggregation": [],
  "test_protocol": [],
  "baseline_policy": "...",
  "contract_refs": [],
  "evidence": []
}}

Rules:
- Metrics must consume objects compatible with object_contracts.
- Preserve setting dimensions such as dataset, horizon, seed, task, episode, prompt, model, bitrate, or sample count.
- If evaluation follows external benchmark protocol, mark external_contract.
- For generative outputs, include parsing formats.
- For geometric/mathematical metrics, include exact formula conditions.
- Baselines are comparison targets unless the paper requires implementing them for the main method.

# 14. module_alignment_hints

Provide routing hints, not final file names.

Each item:
{{
  "module_role": "data | preprocessing | model | adapter | mapping | trainer | evaluator | config | indexer | retriever | generator | prompt_builder | target_builder | masker | tuner | state_manager | agent_runner | environment | simulator | attacker | benchmark_builder | analysis | external_interface | other",
  "must_own": [],
  "must_not_own": [],
  "inputs": [],
  "outputs": [],
  "contract_refs": [],
  "shape_or_object_constraints": [],
  "source": []
}}

Rules:
- State ownership boundaries for operations likely to be duplicated, omitted, or misplaced.
- Do not assign exact filenames.
- Do not create modules for optional/baseline-only components unless needed as disabled hooks.
- A module hint should not introduce new paper facts absent from contracts or evidence.

# 15. open_design_choices

List missing, delegated, or configurable details.

Each item:
{{
  "item": "...",
  "paper_status": "NOT_PROVIDED_IN_PAPER | EXTERNAL_PROTOCOL_REF | NOT_APPLICABLE_FOR_TASK",
  "why_it_matters": "...",
  "affected_contracts": [],
  "allowed_policy": "expose_as_config | require_user_input | follow_external_protocol | load_released_artifact | implement_external_api | fail_fast_if_unavailable | implement_minimal_subset_and_disable_unsupported_modes | candidate_default_if_needed | not_applicable",
  "candidate_defaults": [
    {{
      "value": "...",
      "source": "INFERRED_FOR_IMPLEMENTATION",
      "use_condition": "only if runnable default is required"
    }}
  ],
  "forbidden_unsafe_fallback": "..."
}}

Rules:
- Do not include paper-provided values as open missing choices.
- Prefer expose_as_config, follow_external_protocol, load_released_artifact, or fail_fast_if_unavailable.
- Candidate defaults must never be represented as paper facts.
- If a value is externally delegated, do not override it with a candidate default unless explicitly required for a minimal runnable stub, and mark that stub as not full reproduction.

# 16. integrity_checks

List checks downstream stages must enforce.

Each item:
{{
  "check_id": "...",
  "description": "...",
  "severity": "high | medium | low",
  "applies_to": ["planning", "aligning", "routing", "analyzing", "coding", "audit", "evaluation"],
  "contract_refs": []
}}

Include checks for:
- planning corrections are applied.
- every core_path_contract has producer, consumer, runtime consumption, forbidden downgrades, and evidence.
- weak planning phrases for core algorithms are converted into full-vs-subset requirements.
- every core artifact has explicit producer and consumer.
- external protocols are not replaced by heuristic substitutes.
- unsupported core modes fail fast or are disabled.
- no label-only target replaces full target text.
- no simulated search/tuning/objective replaces real model/data evaluation when the paper requires it.
- no config enum, setter, or wrapper replaces an implemented producer-consumer artifact.
- generated/transformed artifacts are actually consumed downstream.
- tensor/object layouts match before loss/objective/metric computation.
- runtime boundaries such as device movement, preprocessing order, prompt-target boundary, checkpoint content, state persistence, and metric parsing are preserved.
- formula exactness constraints such as masking, indexing, denominator, aggregation, and allowed variants are not lost.
- optional/ablation/baseline components are not merged into the main path.
- inferred defaults remain isolated in open_design_choices.

# 17. compact_handoff

Create a compact summary for routing.

Fields:
{{
  "must_preserve": [],
  "must_assign_in_routing": [],
  "high_risk_boundaries": [],
  "fail_fast_conditions": []
}}

This should be short and contain only the highest-priority information.

FINAL SELF-CHECK BEFORE OUTPUT:
Before producing the JSON, verify:
1. Is the output valid JSON only?
2. Did any default absent from the paper enter a paper_fact contract? If yes, move it to open_design_choices.
3. Did any paper-provided value get marked NOT_PROVIDED_IN_PAPER? If yes, fix it.
4. Are planning drifts corrected and recorded?
5. Are core_path_contracts enforceable enough to reject placeholders, setter-only implementations, generic fallbacks, simulated objectives, unused config modes, and unsupported silent fallbacks?
6. If the paper has multiple named core modes/strategies/branches, does the spec say whether full reproduction requires all of them or a declared subset?
7. Are runtime boundaries explicit when layout, device, preprocessing order, token boundary, checkpoint/state content, external protocol payload, or metric parsing can break correctness?
8. Do formula_exactness_contracts specify indexing/masking/denominator/aggregation/allowed variants when those affect correctness?
9. Does every implementation-relevant paper_fact cite evidence?
10. Are optional/baseline/ablation components separated from the main method?
11. Is the compact_handoff short enough for routing to consume?

Now produce the JSON object.
"""
    },
    {
        "role": "user",
        "content": f"""
Below are the Planning Blueprint and a paper reference block.

Use the Planning Blueprint as the main input.
Use the paper reference block only to verify, correct, and provide evidence for implementation-critical claims.

[PLANNING BLUEPRINT START]
{stage1_blueprint_json}
[PLANNING BLUEPRINT END]

[PAPER REFERENCE BLOCK START]
{paper_reference_block}
[PAPER REFERENCE BLOCK END]

Transform them into the Implementation Alignment Spec following the system instructions.

Return only valid JSON.
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

current_stage = "[Reconciling] Implementation Reconciling Spec"
print(current_stage)

trajectories.extend(aligning_msg)
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

with open(f"{output_dir}/reconciling_response.json", "w", encoding="utf-8") as f:
    json.dump(responses, f, ensure_ascii=False)

with open(f"{output_dir}/reconciling_trajectories.json", "w", encoding="utf-8") as f:
    json.dump(trajectories, f, ensure_ascii=False)

_traj_path = f"{output_dir}/reconciling_trajectories.json"
_context_lst = extract_planning(_traj_path)
_align_body = _context_lst[0] if _context_lst else ""
with open(f"{output_dir}/reconciling_spec.txt", "w", encoding="utf-8") as f:
    f.write(_align_body)

_dag_obj, _json_str = extract_reconciling_json(_align_body)
if _dag_obj is not None:
    with open(f"{output_dir}/reconciling_spec.json", "w", encoding="utf-8") as f:
        json.dump(_dag_obj, f, ensure_ascii=False, indent=2)
else:
    if _json_str:
        with open(f"{output_dir}/reconciling_spec_raw.txt", "w", encoding="utf-8") as f:
            f.write(_json_str)
    print(
        "[ERROR] Failed to parse reconciling JSON from LLM output. "
        "Expected keys: method_graph + core_path_contracts (or legacy global_tensors + computation_graph). "
        f"See {output_dir}/reconciling_spec.txt"
    )
    sys.exit(1)
