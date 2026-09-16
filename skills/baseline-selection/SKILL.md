---
name: baseline-selection
description: "Choose the comparisons that make a result meaningful: the strongest published methods on the same task plus trivial and structural controls, each run under one protocol so differences are attributable to the method. Use when A new method is proposed and must be placed against the state of the art; or when The candidate baseline list consists of whatever was easiest to reimplement; or when Expected baseline numbers are needed before implementation to judge whether the expected gain justifies the work."
---

# Baseline Selection & Comparison Protocol

> Ported from the ConvFusion research-skill library (category: `experiment`; origin: experiment/design, experiment/method). Ask/answer using this method whenever it applies to the current research workspace.

## Purpose

Choose the comparisons that make a result meaningful: the strongest published methods on the same task plus trivial and structural controls, each run under one protocol so differences are attributable to the method.

## When to Use

Use this skill when:

- A new method is proposed and must be placed against the state of the art.
- The candidate baseline list consists of whatever was easiest to reimplement.
- Expected baseline numbers are needed before implementation to judge whether the expected gain justifies the work.

## Research Method

1. **Derive the comparison from the claim.** The baseline must differ from your method in exactly the factor the contribution claims. If it differs in data, tuning budget or compute, the comparison does not test the claim.
2. **Cover the tiers.** Include at least a trivial reference (majority class, random, last value), a standard strong method, the current state of the art in this exact setting, and a variant of your own method with the contribution removed. A baseline set that omits the strongest published method is not a comparison.
3. **Source each baseline from a paper, not from intuition.** Record the paper, its reported values and the exact setting (data version, split, metric definition, compute), and flag every mismatch with your setting. Values you had to estimate must be marked as estimates.
4. **Freeze one evaluation protocol.** Same data version, splits, preprocessing, metric implementation and tuning budget for every method. Unequal tuning is the most common way comparisons become unfair; state the protocol once and apply it verbatim.
5. **Pre-compute expected results and a decision margin.** Give each baseline realistic expected values with a plausible range, and decide in advance how large a gap counts as a real improvement rather than run-to-run variation. If the predicted margin is not clearly above that threshold, revisit the design before implementing.
6. **Specify what the implementation must guarantee.** Each baseline must run from a documented config, use the shared data pipeline and metric code, and emit raw predictions so the comparison can be recomputed. Anything not faithfully reimplementable is reported as cited-only rather than silently approximated.

## Reasoning Guidance

<!-- 迁移自旧模块提示词；具体推理要点见下方逐字来源。 -->

## Evidence Requirements

For every baseline: the source paper or implementation with a link, the protocol it was run under, its config, and its raw outputs. Reported baseline numbers must be either reproduced locally or explicitly attributed to the source with setting differences noted.

## Expected Output

Produce:

- baseline set organised by tier, with the justification for each member
- per-baseline source and expected metric range
- one frozen comparison protocol applied to all methods
- the pre-declared improvement margin
- implementation requirements per baseline, including cited-only entries

## Workspace Conventions

If this method reads or writes structured workspace files (evidence/claims/decisions, plans, papers, outputs, LaTeX, literature search/download), follow the exact schemas in this plugin's `reference/` directory rather than improvising a format — see [research-assets.md](../../reference/research-assets.md), [plans.md](../../reference/plans.md), [papers.md](../../reference/papers.md), [outputs.md](../../reference/outputs.md), [latex.md](../../reference/latex.md), [literature-search.md](../../reference/literature-search.md), and [paper-fulltext-download.md](../../reference/paper-fulltext-download.md), whichever applies. The `research` skill's [SKILL.md](../research/SKILL.md) is the usual entry point that pulls the right context together first; if this skill was invoked on its own, check whether a `project.md` or `research-state.md` already exists in the workspace before assuming there is none.

## Reference Prompts

The original, more verbose source prompts this method was distilled from are kept in [reference.md](reference.md) for extra detail when the summary above isn't enough (exact length/format constraints, worked examples, etc).
