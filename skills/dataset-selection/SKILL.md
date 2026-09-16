---
name: dataset-selection
description: "Choose datasets that can actually support the claim — right construct, right scale, right licence, obtainable — and specify the preprocessing, splitting and statistics the pipeline must produce so the data is auditable. Use when The design is fixed and the open question is which data can answer it; or when A candidate dataset is popular in the field but its domain, splits or licence may not match the claim; or when You need a data pipeline whose processed outputs can be regenerated and inspected."
---

# Dataset Selection & Data Pipeline Specification

> Ported from the ConvFusion research-skill library (category: `experiment`; origin: experiment/dataset, experiment/method (data collection)). Ask/answer using this method whenever it applies to the current research workspace.

## Purpose

Choose datasets that can actually support the claim — right construct, right scale, right licence, obtainable — and specify the preprocessing, splitting and statistics the pipeline must produce so the data is auditable.

## When to Use

Use this skill when:

- The design is fixed and the open question is which data can answer it.
- A candidate dataset is popular in the field but its domain, splits or licence may not match the claim.
- You need a data pipeline whose processed outputs can be regenerated and inspected.

## Research Method

1. **Derive dataset requirements from the claim, not from habit.** List the constructs that must be present (labels, modalities, domains, languages), the required scale, and any distribution the claim depends on. A dataset missing a required construct cannot support the claim no matter how standard it is.
2. **Survey candidates and record provenance.** For each candidate record source, version or commit, licence and terms, size, available splits, known biases, and the works that use it. Prefer version-pinned, publicly downloadable, well-documented sources so the pipeline can be rerun.
3. **Check comparability with the baselines.** Use the same data version, splits and preprocessing that produced the baseline numbers; where you deviate, state the deviation and why the comparison remains valid.
4. **Design the split and guard against leakage.** Fix ratios and a seed, split by the correct unit (subject, document, time) so near-duplicates cannot cross splits, and verify that no test material informed training or tuning.
5. **Specify preprocessing and statistics as requirements for the implementation.** The pipeline must be deterministic, must report per-split sample counts, class balance, missing-value and length distributions, and must write processed data in a documented format while retaining the raw source.
6. **State the fallback when data is unavailable.** If a source cannot be downloaded or licensed, either substitute a documented alternative or generate a clearly-labelled synthetic dataset for dry runs. Never let fabricated values be presented later as measurements.

## Reasoning Guidance

<!-- 迁移自旧模块提示词；具体推理要点见下方逐字来源。 -->

## Evidence Requirements

Dataset identity (source, version, licence, access date), per-split counts, and a hash or checksum of the processed artefacts. Any claim about data scale or distribution must point at a computed statistic, not an estimate. Simulated or synthetic data must be labelled at every downstream use.

## Expected Output

Produce:

- dataset requirement list derived from the research question
- selected datasets with provenance, licence and comparability notes
- split protocol with the splitting unit and a deterministic seed
- preprocessing and statistics requirements handed to implementation
- fallback plan for unavailable or unusable data

## Workspace Conventions

If this method reads or writes structured workspace files (evidence/claims/decisions, plans, papers, outputs, LaTeX, literature search/download), follow the exact schemas in this plugin's `reference/` directory rather than improvising a format — see [research-assets.md](../../reference/research-assets.md), [plans.md](../../reference/plans.md), [papers.md](../../reference/papers.md), [outputs.md](../../reference/outputs.md), [latex.md](../../reference/latex.md), [literature-search.md](../../reference/literature-search.md), and [paper-fulltext-download.md](../../reference/paper-fulltext-download.md), whichever applies. The `research` skill's [SKILL.md](../research/SKILL.md) is the usual entry point that pulls the right context together first; if this skill was invoked on its own, check whether a `project.md` or `research-state.md` already exists in the workspace before assuming there is none.

## Reference Prompts

The original, more verbose source prompts this method was distilled from are kept in [reference.md](reference.md) for extra detail when the summary above isn't enough (exact length/format constraints, worked examples, etc).
