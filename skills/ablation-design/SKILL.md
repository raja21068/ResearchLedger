---
name: ablation-design
description: "Design the experiments that show which part of a method causes the effect, so a gain is attributed to a mechanism rather than to the whole system, extra capacity, or tuning luck. Use when A method combines several components and the paper will claim each of them helps; or when A reviewer would ask which component actually drove the improvement; or when Deciding whether an extra component justifies its complexity and compute cost."
---

# Ablation & Contribution Isolation

> Ported from the ConvFusion research-skill library (category: `experiment`; origin: experiment/design, experiment/simulation, experiment/summary). Ask/answer using this method whenever it applies to the current research workspace.

## Purpose

Design the experiments that show which part of a method causes the effect, so a gain is attributed to a mechanism rather than to the whole system, extra capacity, or tuning luck.

## When to Use

Use this skill when:

- A method combines several components and the paper will claim each of them helps.
- A reviewer would ask which component actually drove the improvement.
- Deciding whether an extra component justifies its complexity and compute cost.

## Research Method

1. **Enumerate contributions as removable units.** List every component or design decision the paper will claim, and define the exact variant in which it is removed or replaced by a neutral equivalent. If a component cannot be removed, say so and drop the claim attached to it.
2. **Run one factor at a time first, then interactions.** Vary one factor per run with everything else at the full configuration, and add combined-removal runs where two components plausibly interact. Keep the full model as the reference row for every comparison.
3. **Control for capacity, not only structure.** When removing a component also changes parameter count or compute, add a size-matched or compute-matched control so the effect is attributed to the mechanism rather than to added capacity.
4. **Define the measurement and decision for each ablation before running.** Reuse the primary metric and the same protocol as the main comparison, state what magnitude of drop would count as evidence that the component matters, and state what a null result would mean.
5. **Rank ablations by how much they change the interpretation and prune the rest.** Drop runs that only confirm the obvious, and report the run budget so a reader can judge coverage.
6. **Keep every result traceable to its variant.** Each ablation run must carry the config diff from the full model plus its own metrics and predictions, so the summary table is regenerable from artefacts rather than hand-assembled.

## Reasoning Guidance

<!-- 迁移自旧模块提示词；具体推理要点见下方逐字来源。 -->

## Evidence Requirements

One recorded config diff per ablation run, a full-model reference under an identical protocol, and per-run metrics for both. A claim of the form that component X contributes requires the corresponding ablation row together with its variance.

## Expected Output

Produce:

- list of claimed contributions with their exact removal definition
- ablation matrix with the full model as reference
- interaction runs and capacity-matched controls
- per-run decision criteria declared before execution
- run budget with pruning rationale

## Workspace Conventions

If this method reads or writes structured workspace files (evidence/claims/decisions, plans, papers, outputs, LaTeX, literature search/download), follow the exact schemas in this plugin's `reference/` directory rather than improvising a format — see [research-assets.md](../../reference/research-assets.md), [plans.md](../../reference/plans.md), [papers.md](../../reference/papers.md), [outputs.md](../../reference/outputs.md), [latex.md](../../reference/latex.md), [literature-search.md](../../reference/literature-search.md), and [paper-fulltext-download.md](../../reference/paper-fulltext-download.md), whichever applies. The `research` skill's [SKILL.md](../research/SKILL.md) is the usual entry point that pulls the right context together first; if this skill was invoked on its own, check whether a `project.md` or `research-state.md` already exists in the workspace before assuming there is none.

## Reference Prompts

The original, more verbose source prompts this method was distilled from are kept in [reference.md](reference.md) for extra detail when the summary above isn't enough (exact length/format constraints, worked examples, etc).
