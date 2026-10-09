from openai import OpenAI
import json
from tqdm import tqdm
import argparse
import os
from utils import (
    print_response,
    print_log_cost,
    load_accumulated_cost,
    save_accumulated_cost,
    extract_blueprint_json,
    prepare_llm_json_source,
    add_paper_reference_args,
    load_paper_content,
    format_paper_for_prompt,
)

parser = argparse.ArgumentParser()

parser.add_argument('--paper_name',type=str)
parser.add_argument('--gpt_version',type=str)
add_paper_reference_args(parser)
parser.add_argument('--output_dir',type=str, default="")

args    = parser.parse_args()

client = OpenAI(api_key = os.environ["OPENAI_API_KEY"])

paper_name = args.paper_name
gpt_version = args.gpt_version
paper_format = args.paper_format
output_dir = args.output_dir
if output_dir:
    os.makedirs(output_dir, exist_ok=True)

paper_content = load_paper_content(args)
paper_content_str = format_paper_for_prompt(paper_content, paper_format)

blueprint_msg = [
    {
    "role": "system",
    "content": f"""
You are an expert machine learning research engineer and reproduction translator.

Your task is to read a machine learning paper and produce a faithful, implementation-aware Translating Blueprint for downstream paper-to-code generation.

This is the TRANSLATING stage (S1) only. You are generating the artifact guiding REFERENCE EXTRACTION stage (S1.5), RECONCILING stage (S2), and following stages.

Stage goal:
- Extract paper facts as completely and faithfully as possible.
- Reorganize the paper into a reproduction task map.
- Build an initial paper-level execution skeleton from raw inputs to final reported outputs.
- Identify high-risk objects, missing decisions, external protocols, branch/mode distinctions, and evaluation dependencies that later stages must reconcile.
- Directly preserve all short or medium-length implementation-critical raw information in S1.
- Create stable reference requests only for long, bulky, or verbatim raw content that should be extracted by a later Reference Extraction step for final code-writing use.

Your responsibilities:
1. Understand the paper exactly as written.
2. Identify the paper's main reproduction target and paper-level execution lifecycle.
3. Extract implementation-critical facts, tables, formulas, algorithms, target formats, protocols, dataset/evaluation settings, and missing details.
4. Identify candidate core requirements and high-risk paper objects that must not be lost later.
5. Separate paper facts, external protocol references, missing information, and implementation guesses.
6. Create reference request IDs only for long, bulky, or verbatim raw content that later Engineering/Coding may need to insert exactly or parse structurally.

Your non-responsibilities:
- Do NOT design a final file tree.
- Do NOT assign exact files, classes, functions, APIs, owners, or callsites.
- Do NOT write code.
- Do NOT finalize producer-consumer schemas beyond what the paper explicitly states.
- Do NOT finalize artifact invariants that require downstream reconciliation.
- Do NOT silently choose runnable defaults for missing paper details.
- Do NOT turn external protocols into heuristic substitutes.
- Do NOT force the paper into a standard data/model/train/eval template.
- Do NOT hide short or medium-length formulas, metric definitions, algorithm steps, table rows, or target formats behind Reference Requests. Extract them directly in S1.
- Do NOT include long raw prompts, large tables, large appendix excerpts, or bulk benchmark settings directly in this blueprint. Create Reference Extraction Requests for those long materials instead.

SOURCE DISCIPLINE:
For implementation-relevant claims, use these tags:
- [PAPER_EXPLICIT]&#58; directly stated in the paper text.
- [TABLE_EXTRACTED]&#58; extracted from a table or appendix table.
- [FIGURE_OR_ALGORITHM]&#58; extracted from a figure, pseudocode, diagram, or algorithm block.
- [EXTERNAL_PROTOCOL_REF]&#58; explicitly delegated to another paper, repository, benchmark, API, dataset convention, simulator, or protocol.
- [INFERRED_FOR_IMPLEMENTATION]&#58; a necessary implementation interpretation not claimed by the paper.
- [NOT_PROVIDED_IN_PAPER]&#58; required for implementation but not specified.
- [NOT_APPLICABLE_FOR_TASK]&#58; concept does not apply to this paper's workflow.

STRICT RULES:
- Do NOT replace external protocol references with [NOT_PROVIDED_IN_PAPER]. Preserve the exact delegation statement.
- Do NOT turn an implementation guess into a paper fact.
- Do NOT invent hyperparameters, dataset splits, preprocessing, optimizer details, architecture choices, scheduler details, missing-value handling, checkpointing, early stopping, decoding details, prompt text, or benchmark formats.
- If a bullet mixes paper facts and inferred choices, split it into separate bullets.
- If the paper says a detail follows another benchmark, repository, official code, prior work, API, simulator, or external protocol, preserve that delegation and list affected implementation areas.
- If a detail is ambiguous, state the ambiguity and downstream risk.
- If the paper contains implementation-critical formulas, equations, short algorithm steps, target formats, metric definitions, or short table rows, extract the raw information directly in S1.
- If the paper contains long prompts, large templates, large appendix tables, long algorithm blocks, many benchmark rows, or bulky modality-specific settings, summarize the key facts in S1 and create a Reference Extraction Request for S1.5.
- Do not write vague references such as “see Table 4” unless either:
  1. the relevant short content is directly extracted in S1, or
  2. a stable Reference Request ID is created for long/bulk extraction by S1.5.
- If the paper is not centered on tensors, use task-appropriate objects such as prompts, messages, judgments, documents, trajectories, replay buffers, simulator states, retrieved items, generated samples, bitstreams, metadata, indexes, labels, references, or metrics.
- Keep evidence quotes short, but preserve exact wording for subtle protocols, target formats, metric definitions, formulas, or external delegation statements.
- Do not include hidden chain-of-thought. Only output concise evidence notes and the final blueprint.
- Directly output all short or medium-length implementation-critical raw information in S1. Do not defer it to S1.5.
- If a formula, metric definition, target format, table row, or algorithm step is short enough to fit compactly, extract it directly rather than creating a Reference Request.
- Only create S1.5 requests for long, bulky, or exact-format-sensitive material that would otherwise bloat S1.
- If a paper-stated detail is partly present in a long table and partly missing, split it into:
  1. paper-stated compact facts extracted in S1;
  2. long table extraction request in Section 10.3 if needed;
  3. remaining missing detail in Section 10.1.
  
TEXT-ONLY / FIGURE DISCIPLINE:
- The provided paper is parsed markdown/text. You cannot inspect visual contents inside image files, diagrams, plots, or figure panels unless those details appear in the markdown text, caption, surrounding paragraph, table, or OCR-provided text.
- If a figure is represented only as an image placeholder, do NOT infer its visual internals.
- If only the caption is available, extract only caption-level facts and mark source availability as caption_only.
- If the needed details are inside an unavailable image, mark them as [NOT_PROVIDED_IN_PAPER] for this text-only run, with source availability image_unavailable.
- Do NOT create a normal S1.5 extraction request for image-only visual internals. S1.5 also reads text/markdown, not pixels.
- If a figure's architecture, diagram, or procedure is also described in text or table form, extract those text/table facts directly and cite the figure/table locator.
- For every implementation-critical figure reference, explicitly state whether the useful information came from text_available, table_available, caption_only, or image_unavailable.

REFERENCE REQUEST POLICY:
S1.5 is not part of the intermediate planning dependency chain. Reconciling and Architecting must be able to proceed using S1 alone.

S1 directly stores all short or medium-length implementation-critical raw information, including:
- core formulas and equations;
- short algorithm steps;
- short metric definitions;
- short table rows;
- target/output formats;
- short external delegation statements;
- key dataset or benchmark settings if they fit compactly.

S1.5 is only for long, bulky, or verbatim source material needed later for Contracting/Engineering/Coding, such as:
- long prompts, templates, system/user messages, or target output formats;
- large tables with many rows, modality settings, hyperparameters, block schedules, dataset splits, or benchmark settings;
- long algorithm blocks or pseudocode that are too large to include directly;
- large metric/evaluation tables;
- dataset schema examples or benchmark file formats that are too long to include directly;
- long or fragile external delegation passages.

Do NOT create Reference Requests for ordinary short facts, short formulas, short equations, short metric definitions, short algorithm steps, or short table rows. Extract those directly in S1.

For core formulas and structural mechanisms:
- Include the formula's role and raw compact expression directly in S1.
- Include summation/indexing/normalization conditions directly if they are short enough.
- Create a Reference Request only if the formula, derivation, or algorithm block is too long or too structured to include compactly.
- Do not use S1.5 as a placeholder for formulas that later code must implement.

For missing or external details:
- If the paper does not provide the detail, mark it as [NOT_PROVIDED_IN_PAPER] and do not pretend S1.5 can extract it.
- If the paper delegates the detail to another work, repository, protocol, benchmark, API, or dataset convention, mark it as [EXTERNAL_PROTOCOL_REF].
- For external details, directly extract the paper's own delegation statement if it is short. Create a Reference Request only for a long or fragile delegation passage.
- Missing details and external protocols are not the same as Reference Requests. Keep them separate.

Every Large/Verbatim Reference Request must have:
- stable Reference Request ID;
- source locator, such as section, appendix, table, algorithm, equation, prompt block, or caption;
- requested extraction target;
- source availability: text_available, table_available, caption_only, external_delegation_only;
- intended downstream use;
- whether exact content should be copied, structured, or summarized.

Do not use source availability image_unavailable for normal extraction requests; image_unavailable belongs in Missing Decisions / Text-Unavailable Details.

OUTPUT FORMAT:
- Output only Markdown.
- Use the exact section headings requested by the user prompt.
- Use compact bullets and tables.
- Prefer precise extraction over broad summary.
- Translating should be detailed enough for later Reconciling and Architecting, but should not become a routing/file-tree specification.
"""
},
    {
    "role": "user",
    "content": f"""
Below is the full text of a machine learning research paper in {paper_format} format.

[PAPER CONTENT START]
{paper_content_str}
[PAPER CONTENT END]

TASK:
Create a faithful Translating Blueprint for downstream paper-to-code generation.

The blueprint must help later stages generate a runnable codebase that reproduces the paper's main method and experiments without silently replacing the paper's core idea with a generic approximation.

Do NOT overfit to a fixed ML schema. The paper's actual execution lifecycle determines the structure.

Use the sections below exactly.

# 1. Paper Identity and Scope

Include:
- Paper/task type.
- Implementation archetype. Choose one or combine several if needed:
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
- Main problem setting.
- Main proposed method.
- Primary reproduction target.
- Reproduction modes if applicable:
  - full_raw_data_rebuild
  - train_from_released_or_precomputed_artifacts
  - inference_or_evaluation_only
  - ablation_or_analysis_only
- What is optional, ablation-only, baseline-only, or analysis-only.

For auxiliary components, state whether they are:
- required for full reproduction,
- required only when rebuilding data from raw sources,
- optional if released artifacts are available,
- baseline-only or ablation-only.

Keep this section factual. Do not propose files or APIs.

# 2. Scope Partition

Separate the paper into:

## Main Reproduction Target
Minimal method and experiment path required to reproduce the main paper result.

## Required Auxiliary Components
Components that are not the proposed model itself but are required for the main reproduction path, such as:
- data generation,
- scenario/task classification,
- simulator,
- retrieval index construction,
- tokenizer/prompt construction,
- augmentation protocol,
- pretrained backbone protocol,
- external evaluator,
- official benchmark loader,
- codec or external coding protocol.

## Optional Extensions
Efficiency variants, training tricks, plug-in modules, robustness tests, or generality experiments.

## Ablations and Analysis
Ablation-only, visualization-only, sensitivity-only, interpretation-only, or diagnostic components.

## Baselines
External methods or baseline models that must not be merged into the proposed method.

For each item, include short evidence or section/table reference.

# 3. Initial Execution Skeleton

Describe the paper's workflow from raw inputs to final reported outputs.

Use an ordered list. Each step must include:
- Step ID and name.
- Trigger / when this step runs.
- Input objects.
- Output objects.
- Persistent artifacts, if any.
- Next step that consumes the output.
- Whether the step is paper_fact, external_protocol_ref, or implementation_choice.
- Whether the step is required for:
  - full_raw_data_rebuild,
  - train_from_released_or_precomputed_artifacts,
  - inference_or_evaluation_only,
  - ablation_or_analysis_only if relevant.
- Parallel, alternative, optional, or ablation branch behavior if relevant.
- What fails if the step is omitted or replaced.

Do not force lifecycle into data/model/train/eval. Use the paper's real loop, such as:
- GPT-4 data generation -> filtering/reformatting -> supervised fine-tuning -> generative evaluation,
- view generation -> contrastive/equivariance loss -> linear probe,
- pretrained model adaptation -> mapping update -> evaluation,
- retrieval index construction -> query loop -> metric computation,
- simulator rollout -> policy update -> evaluation,
- compression encode -> bitstream metadata -> decode -> rate-distortion metrics.

For parallel workflows, include the branch under the relevant step rather than creating a separate section. Examples:
- pairwise vs single-response evaluation;
- patch vs non-patch compression;
- training from raw data vs loading released artifacts;
- full reproduction vs ablation-only mode.

# 4. Candidate Core Requirements for Reconciling

This section replaces final implementation contracts. Do not finalize files, APIs, or callsites.

Create a compact table of 5 to 12 candidate requirements that later Reconciling must turn into executable contracts.

Each row must contain:
- Requirement ID.
- Requirement type:
  - supervision_target
  - contribution_minimum
  - artifact_handoff
  - external_protocol
  - runtime_boundary
  - formula_exactness
  - preprocessing_protocol
  - evaluation_protocol
  - checkpoint_or_state
  - other
- Paper role.
- Paper evidence.
- Candidate producer role if directly implied by the paper.
- Candidate consumer role if directly implied by the paper.
- Minimum paper-stated behavior.
- Common downgrade or shortcut risk.
- What Reconciling must resolve.

Use this section to prevent common failures:
- Training a generative model on label-only targets when the paper trains on full generated text.
- Providing a setter or config option for a core algorithm without computing and consuming the artifact.
- Simulating a tuning objective when the paper runs real short-run training/evaluation.
- Treating CLIP or other pretrained systems as generic classifiers when text/image protocol is required.
- Applying augmentations in the wrong tensor layout/device space.
- Omitting required normalization/preprocessing after prompt or augmentation operations.
- Replacing an external protocol with a heuristic while still claiming full reproduction.
- Implementing a formula syntactically while producing an object in the wrong mathematical space.
- Creating a runtime flow that passes dummy or placeholder artifacts through the main reproduction path.

For each candidate requirement, the “What Reconciling must resolve” field should identify unresolved cross-object, mode, evaluation, or runtime questions. Examples:
- whether a produced object must be a full parameter vector or only a latent vector;
- whether an external protocol blocks full reproduction or permits a smoke-test mode;
- which output range or normalization a metric consumes;
- which branch is main-path and which is ablation-only.

If a proposed method has multiple named core modes, strategies, or algorithms, state whether faithful reproduction requires all of them or whether a declared minimal subset is acceptable. If only a subset is implemented, unsupported modes must be disabled or fail fast, not silently routed to a generic fallback.

# 5. Data, Inputs, Targets, and Experiment Protocol

Extract task-specific inputs and outputs.

Include what applies:
- Dataset names, subsets, sizes, splits, sampling rules.
- Prompt/message formats.
- Full supervised target format, if any.
- Labels, ratings, critiques, references, rewards, trajectories, retrieved documents, generated samples, bitstreams, metadata, indexes, or other target objects.
- Train/validation/test split protocol.
- Data cleaning/filtering rules.
- Tokenization, preprocessing, normalization, scaling, augmentation, masking, padding.
- Batch construction and shuffling only if stated.
- External protocol references.

Important:
- For supervised or generative training, explicitly separate:
  - model input,
  - supervised target,
  - loss-bearing region/tokens/objects,
  - non-loss prompt/context region.
- If the model is trained to generate natural language, the target must be described as full text, not compressed into a label unless the paper explicitly does so.
- If a table defines short prompt templates, output formats, dataset rows, settings, or benchmark protocols, extract the raw content directly here when compact.
- If a table or prompt block is too long, extract the key facts here and add it to Section 10.3 as a Large/Verbatim Reference Request.
- If details are missing but required, list them under Section 10.1 Missing Decisions, not as S1.5 extraction requests.

# 6. Proposed Method or Algorithm Blueprint

Describe the proposed core method step by step.

This may be:
- neural architecture,
- training algorithm,
- data-generation pipeline,
- evaluation harness,
- retrieval pipeline,
- optimization loop,
- environment interaction loop,
- compression/decompression workflow,
- simulator,
- attack/defense procedure,
- agent loop,
- benchmark construction protocol.

For each major component:
- Name.
- Role in the main method.
- Inputs.
- Outputs.
- Operation details.
- Training vs inference behavior, if different.
- Hyperparameters stated by the paper.
- Source tag.
- Missing details or ambiguity.
- Whether it is core, optional, ablation-only, or baseline-only.
- How it connects to the Initial Execution Skeleton.

For proposed contributions, state the minimum paper-stated behavior that counts as faithful, without deciding files or APIs.
For example:
- A mapping method must include both computation and downstream consumption.
- A data-generation method must either call the external generator or load generated artifacts.
- A tuning method must evaluate actual model/data behavior if the paper does.
- A same-augmentation method must guarantee identical transform parameters, not merely similar distributions.
- A compression method must produce the paper's compressed object or clearly preserve the external protocol boundary.

Avoid repeating the full execution skeleton. Focus on method mechanics and paper evidence.

# 7. Mathematical, Object, and Runtime Details

List implementation-critical mathematical or runtime objects as paper-stated facts and unresolved questions.

Use task-appropriate entries:
- Tensor / object name.
- Meaning.
- Shape or structure if stated by the paper.
- Layout convention if relevant, such as CHW/HWC or sequence/message structure.
- dtype/device/preprocessing stage if relevant and stated.
- Paper-stated producer or source, if any.
- Paper-stated consumer or use, if any.
- Required invariant if explicitly stated.
- Formula or algorithm step.
- Source tag.
- What later Reconciling must determine, if implementation requires more detail.

For formulas:
- Transcribe exact equations when important.
- State summation/indexing conditions if given, such as excluding diagonal pairs.
- State normalization denominator or averaging convention if given.
- State whether a practical variant is explicitly allowed by the paper.
- If exact notation or a multi-line derivation is short enough to include compactly, extract it directly here.
- Create a Section 10.3 Large/Verbatim Reference Request only when the formula, derivation, or algorithm block is too long or too structured to include compactly.

For core implementation formulas:
- Include the raw compact formula and its workflow role directly in this section.
- If the formula is central to training, inference, encoding, decoding, evaluation, or state update, do not leave it only as a Reference Request.
- If the exact formula is short or medium length, output it directly here.
- Do not write only “see Equation X” for a formula that later code must implement.
- Create a Section 10.3 Large/Verbatim Reference Request only if the formula, derivation, or algorithm block is too long or too structured to include compactly.
- If the paper gives a formula but its engineering realization is uncertain, separate:
  - paper-stated formula,
  - missing implementation detail,
  - what Reconciling must resolve.
- If the exact formula is short or medium length, output it directly here.
- Create a Section 10.3 Large/Verbatim Reference Request only if the formula, derivation, or algorithm block is too long or too structured to include compactly.
- If the paper gives a formula but its engineering realization is uncertain, separate:
  - paper-stated formula,
  - missing implementation detail,
  - what Reconciling must resolve.

For figures or diagrams:
- Extract only what is available in markdown text, caption, surrounding paragraph, or table.
- If figure internals are image-only, do not infer them.
- Mark image-only missing visual details in Section 10.1, not as normal S1.5 extraction requests.
- If a figure is cited as evidence, explicitly state whether the evidence is text_available, table_available, caption_only, or image_unavailable.

Do not invent consumer-defined shape contracts here unless the paper states them directly. Flag them as questions for Reconciling instead.

# 8. Training or Execution Protocol

Adapt this section to the paper.

If training exists, extract:
- Objective/loss/reward/update rule.
- Optimizer/solver if stated.
- Learning rate/schedule if stated.
- Batch size.
- Epochs/steps.
- Weight decay, betas, eps, gradient clipping, AMP, warmup, scheduler if stated.
- Seeds/repeated runs/statistical reporting if stated.
- Hardware/framework if stated.
- Validation/model selection/checkpointing if stated.
- Training-only tricks.
- Which parameters are trainable vs frozen.
- Any coordinate descent, alternating optimization, inner/outer loop, or per-instance inference loop.
- Which artifacts are persisted for later modes, if stated.

If no training loop exists:
- Mark training fields [NOT_APPLICABLE_FOR_TASK].
- Describe the actual execution loop.

Critical checks:
- Do not confuse evaluation metrics with training loss.
- Do not invent default optimizer details.
- If a runnable implementation would need defaults, list them later as missing decisions, not as paper facts.
- If the paper’s training loop has multiple branches or modes, describe them under the relevant step rather than making a separate architecture.

# 9. Evaluation Protocol

Extract:
- Metrics.
- Inputs consumed by each metric.
- Which execution step produces each metric input.
- Test protocol.
- Validation protocol if any.
- Aggregation over datasets, tasks, horizons, seeds, episodes, prompts, samples, bitrates, or models.
- Number of runs / averaging / standard deviation.
- Postprocessing, parsing, masking, or special metric handling.
- Normalization, scale, denominator, unit, or value range assumptions.
- Tables that define settings or results.
- Which baselines are comparison-only.

For generative outputs, include required parsing formats.
For geometric or mathematical metrics, include exact formula conditions.
For compression or codec tasks, distinguish:
- true bitstream/rate-derived metrics,
- KL or estimated rate,
- decoded output distortion,
- any proxy that is not acceptable for final paper metrics.

For benchmark protocols delegated externally, preserve the delegation and affected code areas.

If exact metric formulas, parsing formats, output templates, or evaluation table rows are short, output them directly here.
Create Section 10.3 Large/Verbatim Reference Requests only for long or bulky metric tables, parsing templates, or output formats.

# 10. Missing Decisions, External Protocols, and Large/Verbatim Reference Requests

Keep the following three subsections separate. Do not combine them into one table.

## 10.1 Missing Decisions and Text-Unavailable Details

Use this subsection only for details required for implementation but not provided in the paper text/markdown, or details hidden in unavailable images.

Create a table with:
- Item ID.
- Missing detail.
- Source tag: usually [NOT_PROVIDED_IN_PAPER] or [INFERRED_FOR_IMPLEMENTATION].
- Source locator if relevant.
- Source availability:
  - not_provided
  - image_unavailable
  - caption_only_insufficient
  - partial_in_table_remaining_missing
- Why it matters.
- Affected downstream area.
- Safe handling policy:
  - expose_as_config
  - require_user_input
  - fail_fast_if_unavailable
  - implement_minimal_subset_and_disable_unsupported_modes
  - record_absence
- Forbidden unsafe fallback.

Rules:
- Do not put paper-stated text/table/formula content here.
- Do not put external protocols here.
- Do not claim S1.5 can extract missing information.
- If a detail is partly present in a table but still incomplete, write the paper-stated part in the relevant main section and mark only the remaining unknown part here as partial_in_table_remaining_missing.
- If a figure is only an image placeholder and the needed visual details are absent from text/caption/table, record it here as image_unavailable.
- If caption text is sufficient, extract the caption-level fact in the main blueprint and do not invent hidden visual details.

## 10.2 External Protocols and Delegated Details

Use this subsection only for details explicitly delegated to another work, repository, benchmark, API, simulator, dataset convention, or external tool.

Create a table with:
- Item ID.
- Delegated detail.
- Source tag: [EXTERNAL_PROTOCOL_REF].
- Exact delegation statement if short.
- Source locator.
- Source availability:
  - text_available
  - external_delegation_only
- Why it matters.
- Affected downstream area.
- Safe handling policy:
  - implement_external_api
  - load_released_artifact
  - fail_fast_if_unavailable
  - record_external_delegation
- Forbidden unsafe fallback.
- Large Reference Request ID only if the delegation passage is too long or fragile.

Rules:
- Do not mark external protocols as [NOT_PROVIDED_IN_PAPER].
- Do not place [EXTERNAL_PROTOCOL_REF] rows in Section 10.1.
- Do not create normal S1.5 extraction requests for implementation details that exist only in external papers/repos.
- Extract the paper’s own delegation statement directly if it is short.
- If the paper only names an external method without details, record that as external_delegation_only.
- Do not classify standard cited background methods as external protocols unless the paper delegates implementation-critical details to them.

## 10.3 Large or Verbatim Reference Requests for S1.5

Use this subsection only for raw content that exists in the provided paper text/markdown and is too long, bulky, or exact-format-sensitive to include directly in S1.

Create a table with:
- Reference Request ID.
- Content type:
  - long_prompt_or_output_format
  - large_table_or_modality_settings
  - long_algorithm_or_pseudocode
  - large_metric_or_benchmark_table
  - dataset_schema_or_file_format
  - long_external_delegation_passage
  - other
- Source locator: section/table/algorithm/equation/appendix/caption.
- Source availability:
  - text_available
  - table_available
  - caption_only
  - external_delegation_only
- Requested extraction target.
- Intended final use:
  - final_coding_reference
  - prompt_template_injection
  - config_table_injection
  - metric_parser_reference
  - dataset_loader_reference
  - documentation_only
- Whether S1 already contains the compact facts needed for Reconciling/Architecting: yes/no.
- Extraction mode:
  - copy_verbatim
  - structure_as_table
  - summarize_with_exact_fields

Rules:
- Do not include short formulas here; output them directly in Section 7.
- Do not include ordinary short table rows here; output them directly in relevant sections.
- Do not include missing decisions here.
- Do not include external-only implementation details here.
- Do not include image-only visual details here.
- S1.5 is for final raw-material insertion during Contracting/Engineering/Coding, not for core intermediate planning. Reconciling and Architecting should not require S1.5 to understand the method.

# 11. Candidate Implementation Roles, Not Architecture

Give high-level role hints only. Do NOT design the final file tree.

Only list roles directly implied by the paper workflow. Keep this section concise.

For each role:
- Role name.
- Why this role exists in the paper workflow.
- Paper objects it touches.
- Critical risk for later Architecting or Contracting.
- What it must not fake or silently replace.

Examples of role names:
- data_generation_or_loader
- prompt_or_template_builder
- target_builder_or_masker
- augmentation_pipeline
- pretrained_backbone_wrapper
- core_model_or_algorithm
- mapping_or_adapter
- training_or_execution_runner
- evaluator_or_metric
- checkpoint_or_state_manager
- external_protocol_interface
- codec_or_bitstream_interface

Do not assign exact files, classes, functions, owners, or APIs. Architecting will decide exact files and module boundaries later.

# 12. Downstream Handoff Checklist

End with a concise checklist for Reconciling, Architecting, Contracting, and Engineering.

Include:
- Main execution path in one line.
- Core artifacts that must exist.
- Candidate core requirements that must be reconciled into executable contracts.
- Training-only vs inference-only differences.
- Required external protocols and acceptable modes.
- Forbidden downgrades.
- Missing decisions that must remain visible.
- High-risk runtime boundaries, such as tensor layout, device movement, preprocessing order, prompt/target boundary, checkpoint content, bitstream metadata, or metric parsing.
- Any Section 10.3 Large/Verbatim Reference Request IDs that should be processed by S1.5 for later final coding use.

For Section 10.3 Reference Request IDs, group them by downstream purpose:
- long_prompt_or_output_format;
- large_table_or_modality_settings;
- large_metric_or_benchmark_table;
- dataset_schema_or_file_format;
- long_algorithm_or_pseudocode;
- long_external_delegation_passage;
- documentation_only.

Do not list short formulas, missing decisions, external-only implementation details, or image-unavailable visual details as S1.5 extraction dependencies.

OUTPUT REQUIREMENTS:
- Output only the Markdown blueprint.
- Keep quotes short.
- Prefer faithful extraction over speculation.
- Use tables when they make facts easier to parse.
- Avoid long generic prose.
- Avoid repeating the same information across sections.
- If uncertain, explicitly mark uncertainty instead of guessing.
- Directly output all short or medium-length implementation-critical paper facts in S1.
- Do not include large raw reference content; create Section 10.3 requests only for long or bulky content.
- Before finalizing, check:
  1. Main method, required auxiliaries, optional extensions, ablations, and baselines are separated.
  2. Initial Execution Skeleton covers the full path from raw inputs to final reported outputs.
  3. Candidate Core Requirements include the paper's key supervision, optimization, encoding, decoding, or evaluation signal.
  4. Evaluation metrics are linked to the objects they consume and the step that produces those objects.
  5. External protocols are separated from missing decisions.
  6. Short implementation-critical formulas, metric definitions, algorithm steps, and table rows are directly extracted, not deferred to S1.5.
  7. Long/bulky prompts, tables, algorithms, templates, or benchmark settings are assigned Section 10.3 Reference Request IDs only when direct inclusion would be too long.
  8. External protocols are separated from missing decisions.
  9. Image-only details are marked unavailable rather than inferred.
  10. Long/bulky prompts, tables, algorithms, or templates are assigned Section 10.3 Reference Request IDs only when direct inclusion would be too long.
  11. Image-only details are marked unavailable rather than inferred.
  12. Defaults and missing details are isolated from paper facts.
  13. No standard ML template has been forced onto a non-standard workflow.
"""
}
]

def api_call(msg, gpt_version):
    if "o3-mini" in gpt_version:
        completion = client.chat.completions.create(
            model=gpt_version, 
            reasoning_effort="high",
            messages=msg
        )
    else:
        completion = client.chat.completions.create(
            model=gpt_version, 
            messages=msg
        )

    return completion 

responses = []
trajectories = []
total_accumulated_cost = 0

current_stage = "[Translating] Implementation blueprint"
print(current_stage)

trajectories.extend(blueprint_msg)

completion = api_call(trajectories, gpt_version)

# response
completion_json = json.loads(completion.model_dump_json())

# print and logging
print_response(completion_json)
temp_total_accumulated_cost = print_log_cost(completion_json, gpt_version, current_stage, output_dir, total_accumulated_cost)
total_accumulated_cost = temp_total_accumulated_cost

responses.append(completion_json)

# trajectories
message = completion.choices[0].message
trajectories.append({'role': message.role, 'content': message.content})


# save
save_accumulated_cost(f"{output_dir}/accumulated_cost.json", total_accumulated_cost)

os.makedirs(output_dir, exist_ok=True)

with open(f'{output_dir}/translating_response.json', 'w') as f:
    json.dump(responses, f)

with open(f'{output_dir}/translating_trajectories.json', 'w', encoding='utf-8') as f:
    json.dump(trajectories, f)

_blueprint_raw = message.content or ""
_blueprint_body = prepare_llm_json_source(_blueprint_raw)
with open(f'{output_dir}/translating_blueprint.txt', 'w', encoding='utf-8') as f:
    f.write(_blueprint_body)

_blueprint_obj, _blueprint_json_str = extract_blueprint_json(_blueprint_raw)
if _blueprint_obj is not None:
    with open(f'{output_dir}/translating_blueprint.json', 'w', encoding='utf-8') as f:
        json.dump(_blueprint_obj, f, ensure_ascii=False, indent=2)
elif _blueprint_json_str:
    with open(f'{output_dir}/translating_blueprint_raw.txt', 'w', encoding='utf-8') as f:
        f.write(_blueprint_json_str)
