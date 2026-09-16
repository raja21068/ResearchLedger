---
name: evaluation-protocol
description: "Decide what is measured, how each metric is computed, and what counts as success, so that a number produced by the pipeline can be trusted as evidence about the hypothesis. Use when The design names metrics but not their definitions or computation; or when The same metric name is computed differently across the works you compare against; or when Before implementation, to make sure the code will emit the quantities the claims need."
---

# Evaluation Protocol & Metric Design

> Ported from the ConvFusion research-skill library (category: `experiment`; origin: experiment/design, experiment/analysis, experiment/method). Ask/answer using this method whenever it applies to the current research workspace.

## Purpose

Decide what is measured, how each metric is computed, and what counts as success, so that a number produced by the pipeline can be trusted as evidence about the hypothesis.

## When to Use

Use this skill when:

- The design names metrics but not their definitions or computation.
- The same metric name is computed differently across the works you compare against.
- Before implementation, to make sure the code will emit the quantities the claims need.

## Research Method

1. **Map each claim to a metric.** For every statement the paper will make, name the quantity that would support or refute it. Claims with no measurable quantity are either dropped or explicitly marked qualitative.
2. **Fix the primary metric before seeing results**, and treat secondary metrics as supporting only. Choosing the primary after seeing results is post-hoc selection by another name.
3. **Pin each metric to an implementation.** State the formula, averaging mode (micro or macro), label handling, thresholds and reference implementation. Ambiguous names such as accuracy or F1 must be disambiguated, and the computing library version recorded.
4. **Specify the evaluation loop and reporting granularity.** State which splits are used, how often evaluation runs, whether selection is per-seed or best-epoch, and that test data is touched once at the end. Report per-seed values, not only the best.
5. **Declare success and failure thresholds in advance**, including the minimum effect worth claiming and any absolute floor such as beating the trivial baseline. Thresholds belong to the design, not to the later narrative.
6. **Require machine-readable outputs from the implementation.** Evaluation code must write metrics and per-example predictions in a documented schema, one row per run, seed and example, so that later comparison, significance testing and error analysis work from artefacts rather than from prose.

## Reasoning Guidance

<!-- 迁移自旧模块提示词；具体推理要点见下方逐字来源。 -->

## Evidence Requirements

Metric definitions with reference implementation and version, per-run and per-seed raw outputs, the claim-to-metric mapping, and thresholds declared before the run. A metric value is not evidence unless the code, data version and config that produced it are identifiable.

## Expected Output

Produce:

- claim-to-metric mapping with qualitative claims marked
- primary and secondary metric definitions with reference implementations
- evaluation schedule and split usage
- pre-declared success, failure and minimum-effect thresholds
- required output schema for the implementation

## Workspace Conventions

If this method reads or writes structured workspace files (evidence/claims/decisions, plans, papers, outputs, LaTeX, literature search/download), follow the exact schemas in this plugin's `reference/` directory rather than improvising a format — see [research-assets.md](../../reference/research-assets.md), [plans.md](../../reference/plans.md), [papers.md](../../reference/papers.md), [outputs.md](../../reference/outputs.md), [latex.md](../../reference/latex.md), [literature-search.md](../../reference/literature-search.md), and [paper-fulltext-download.md](../../reference/paper-fulltext-download.md), whichever applies. The `research` skill's [SKILL.md](../research/SKILL.md) is the usual entry point that pulls the right context together first; if this skill was invoked on its own, check whether a `project.md` or `research-state.md` already exists in the workspace before assuming there is none.

## Reference Prompts

The original, more verbose source prompts this method was distilled from are kept in [reference.md](reference.md) for extra detail when the summary above isn't enough (exact length/format constraints, worked examples, etc).
