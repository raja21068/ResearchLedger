---
name: comparative-analysis
description: "Decide whether observed differences between methods are real and meaningful — same protocol, quantified uncertainty, significance where the design supports it — instead of reading a ranking off a single table. Use when A results table exists and you must say which differences matter; or when The improvement over the strongest baseline is small relative to run-to-run variation; or when Some baseline numbers come from papers run under a different setting."
---

# Comparative Analysis & Significance

> Ported from the ConvFusion research-skill library (category: `analysis`; origin: experiment/analysis, experiment/simulation, experiment/prompts (baseline builder)). Ask/answer using this method whenever it applies to the current research workspace.

## Purpose

Decide whether observed differences between methods are real and meaningful — same protocol, quantified uncertainty, significance where the design supports it — instead of reading a ranking off a single table.

## When to Use

Use this skill when:

- A results table exists and you must say which differences matter.
- The improvement over the strongest baseline is small relative to run-to-run variation.
- Some baseline numbers come from papers run under a different setting.

## Research Method

1. **Verify comparability before comparing.** Confirm every row used the same data version, splits, preprocessing, metric implementation and tuning budget. Rows that did not are marked not-directly-comparable and excluded from claims until reproduced.
2. **Report uncertainty with every number.** Give per-seed values, a mean with standard deviation or confidence interval, and the number of runs. A bare mean cannot support a difference claim; prefer uncertainty on the difference over uncertainty on each method separately.
3. **Test the difference where the design allows.** Use paired comparisons across seeds or splits, report effect size alongside the test statistic, correct for multiple comparisons when many pairs are tested, and use non-parametric tests when the sample is small or normality is doubtful. If the design cannot support a test, say so rather than quoting a number.
4. **Check the robustness of the ranking.** Repeat under secondary metrics, across seeds, and on the hardest and easiest subsets. A ranking that flips under reasonable variation is reported as a tie, not a win.
5. **Quantify practical significance.** Relate the delta to the meaningful range of the metric, the spread of the baseline and the added compute. A statistically real but negligible gain is described as such.
6. **Attribute every comparison to its source.** For reproduced baselines cite the run directory; for cited numbers state the paper, its setting and the direction of any mismatch. Never mix reproduced and cited values in one column without labelling.

## Reasoning Guidance

<!-- 迁移自旧模块提示词；具体推理要点见下方逐字来源。 -->

## Evidence Requirements

The per-run values behind every aggregate, the test used with its assumptions, the number of comparisons corrected for, and the run or paper source of each row. Comparison tables must separate reproduced from cited numbers and state the comparability of every row.

## Expected Output

Produce:

- comparability-checked comparison table with uncertainty
- significance and effect-size results with the test and corrections used
- robustness checks across metrics, seeds and subsets
- practical-significance statement relative to cost and metric range
- explicit list of rows excluded from comparison and why

## Workspace Conventions

If this method reads or writes structured workspace files (evidence/claims/decisions, plans, papers, outputs, LaTeX, literature search/download), follow the exact schemas in this plugin's `reference/` directory rather than improvising a format — see [research-assets.md](../../reference/research-assets.md), [plans.md](../../reference/plans.md), [papers.md](../../reference/papers.md), [outputs.md](../../reference/outputs.md), [latex.md](../../reference/latex.md), [literature-search.md](../../reference/literature-search.md), and [paper-fulltext-download.md](../../reference/paper-fulltext-download.md), whichever applies. The `research` skill's [SKILL.md](../research/SKILL.md) is the usual entry point that pulls the right context together first; if this skill was invoked on its own, check whether a `project.md` or `research-state.md` already exists in the workspace before assuming there is none.

## Reference Prompts

The original, more verbose source prompts this method was distilled from are kept in [reference.md](reference.md) for extra detail when the summary above isn't enough (exact length/format constraints, worked examples, etc).
