---
name: resource-requirement-estimation
description: "Estimate what a plan demands in hardware-agnostic terms, namely compute, storage, data, human skills and time by phase, and identify the binding bottleneck and the scaling behaviour before any vendor or part number is chosen. Use when A pipeline exists and its feasibility must be established before committing to it; or when Someone proposes a specific GPU model before the requirement has been stated; or when You need to know which phase or resource constrains the schedule."
---

# Resource Requirement Estimation

> Ported from the ConvFusion research-skill library (category: `research-management`; origin: resource/resource_estimation, resource/instance_selection). Ask/answer using this method whenever it applies to the current research workspace.

## Purpose

Estimate what a plan demands in hardware-agnostic terms, namely compute, storage, data, human skills and time by phase, and identify the binding bottleneck and the scaling behaviour before any vendor or part number is chosen.

## When to Use

Use this skill when:

- A pipeline exists and its feasibility must be established before committing to it.
- Someone proposes a specific GPU model before the requirement has been stated.
- You need to know which phase or resource constrains the schedule.
- A plan is being scaled up (more seeds, more data, a larger model) and the cost curve is unknown.

## Research Method

1. **Express compute as a requirement, not a product.** Report relative compute units (A100-equivalent = 1.0), GPU-hours and required parallelism. Naming a GPU model at this stage hides whether the requirement is 40 or 40,000 GPU-hours and pre-empts the selection decision.
2. **Derive GPU-hours from the run list.** Take the run count including seeds, sweeps and ablations, multiply by hours per run from the pipeline estimate, and divide by the parallel efficiency you are willing to assume. Show the arithmetic; it is the only part of the estimate a reviewer can audit.
3. **Size storage in tiers.** Hot working storage, checkpoint storage (runs x checkpoint size x retention), cold archive, and log volume per run. Checkpoint storage is routinely the largest term and the one most often omitted.
4. **Specify the dataset requirement as an acquisition plan.** Total volume, sample count, modalities, preprocessing needs, and the source: existing corpus, synthesis, purchase, or collaboration. Each path needs an owner and a lead time; "a public dataset" is not an acquisition plan.
5. **Estimate time by phase and state the assumption each phase rests on** (data preparation, implementation, training, evaluation). Convert the pipeline critical path into wall-clock weeks, including the serialisation that cannot be removed.
6. **Name the bottleneck explicitly.** Identify the single resource that binds the plan, whether GPU-hours, a scarce dataset, one specific skill, or strictly sequential runs, and give its severity. If everything is listed as a bottleneck, none has been identified.
7. **State how the estimate scales.** Give the marginal cost of doubling runs, data or model size and the point at which the plan stops being feasible. This is what makes the estimate usable for descoping rather than merely informative.

## Reasoning Guidance

<!-- 迁移自旧模块提示词；具体推理要点见下方逐字来源。 -->

## Evidence Requirements

Compute, storage and time figures must show their derivation from run counts, model sizes and dataset sizes. Dataset claims must name the actual source and its access conditions. Every phase estimate must carry the assumption it depends on. Never present a vendor-specific part number as a requirement.

## Expected Output

Produce:

- compute requirement (compute units, GPU-hours, parallelism) with its derivation
- storage requirement by tier, with checkpoint retention stated
- dataset requirement and acquisition plan with sources, owners and lead times
- time estimate by phase plus the human skills the plan assumes
- the binding bottleneck with its severity, and the scaling behaviour of the estimate

## Workspace Conventions

If this method reads or writes structured workspace files (evidence/claims/decisions, plans, papers, outputs, LaTeX, literature search/download), follow the exact schemas in this plugin's `reference/` directory rather than improvising a format — see [research-assets.md](../../reference/research-assets.md), [plans.md](../../reference/plans.md), [papers.md](../../reference/papers.md), [outputs.md](../../reference/outputs.md), [latex.md](../../reference/latex.md), [literature-search.md](../../reference/literature-search.md), and [paper-fulltext-download.md](../../reference/paper-fulltext-download.md), whichever applies. The `research` skill's [SKILL.md](../research/SKILL.md) is the usual entry point that pulls the right context together first; if this skill was invoked on its own, check whether a `project.md` or `research-state.md` already exists in the workspace before assuming there is none.

## Reference Prompts

The original, more verbose source prompts this method was distilled from are kept in [reference.md](reference.md) for extra detail when the summary above isn't enough (exact length/format constraints, worked examples, etc).
