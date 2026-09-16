---
name: result-analysis
description: "Turn raw run outputs into defensible findings: what the numbers say against the pre-declared thresholds, which figures the argument needs, and what the study cannot conclude. Use when Runs finished and metrics and predictions exist, but a narrative is still needed; or when Deciding which figures and tables the paper actually requires; or when Consolidating several sub-experiments into one coherent result set."
---

# Result Analysis & Finding Extraction

> Ported from the ConvFusion research-skill library (category: `analysis`; origin: experiment/analysis, experiment/summary). Ask/answer using this method whenever it applies to the current research workspace.

## Purpose

Turn raw run outputs into defensible findings: what the numbers say against the pre-declared thresholds, which figures the argument needs, and what the study cannot conclude.

## When to Use

Use this skill when:

- Runs finished and metrics and predictions exist, but a narrative is still needed.
- Deciding which figures and tables the paper actually requires.
- Consolidating several sub-experiments into one coherent result set.

## Research Method

1. **Assemble results from artefacts.** Build the run table from run directories (config, seed, metrics, predictions) and reconcile it against the design: every planned run present, every reported number traceable. Missing or extra runs are findings in themselves.
2. **Read results against the pre-declared thresholds.** Compare the primary metric with the declared success margin and the strongest baseline, and state the outcome as supported, not supported or inconclusive rather than narrating the best-looking number.
3. **Separate stable findings from single-run observations.** A difference seen once, or only at the best epoch, is not a finding. For every finding state the evidence it rests on and its spread across seeds and settings.
4. **Explain mechanism, not only ordering.** For each finding give the result that makes it plausible — ablation row, error pattern, training curve — and mark any explanation that is inference rather than measurement.
5. **Choose figures from the argument.** One figure per claim: main comparison, contribution ablation, behavioural evidence. Specify data source, chart type and message, and drop figures that decorate without carrying an argument. Figure values must be generated from run artefacts, never retyped.
6. **State limitations and negative results.** Enumerate what the evidence does not cover — settings, scales, failure modes — including runs that did not work. An honest limitation section is part of the result, not an afterthought.

## Reasoning Guidance

<!-- 迁移自旧模块提示词；具体推理要点见下方逐字来源。 -->

## Evidence Requirements

Every reported number maps to a run directory and a metric computation, and every figure regenerates from artefacts. Findings must state the comparison and variance they rest on, inferred explanations must be labelled as inference, and no value may come from a pre-run simulation once real runs exist.

## Expected Output

Produce:

- reconciled results table by run and seed
- findings with the evidence and spread each rests on
- figure and table plan with data sources and captions
- limitations and negative results
- claim-support verdict per intended claim

## Workspace Conventions

If this method reads or writes structured workspace files (evidence/claims/decisions, plans, papers, outputs, LaTeX, literature search/download), follow the exact schemas in this plugin's `reference/` directory rather than improvising a format — see [research-assets.md](../../reference/research-assets.md), [plans.md](../../reference/plans.md), [papers.md](../../reference/papers.md), [outputs.md](../../reference/outputs.md), [latex.md](../../reference/latex.md), [literature-search.md](../../reference/literature-search.md), and [paper-fulltext-download.md](../../reference/paper-fulltext-download.md), whichever applies. The `research` skill's [SKILL.md](../research/SKILL.md) is the usual entry point that pulls the right context together first; if this skill was invoked on its own, check whether a `project.md` or `research-state.md` already exists in the workspace before assuming there is none.

## Reference Prompts

The original, more verbose source prompts this method was distilled from are kept in [reference.md](reference.md) for extra detail when the summary above isn't enough (exact length/format constraints, worked examples, etc).
