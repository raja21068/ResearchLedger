---
name: literature-review
description: "Build an evidence-backed understanding of a research area — tasks, problems, methods, evidence, contradictions — rather than a list of paper summaries. Use when You need to know what the field actually knows before proposing anything; or when A direction is being considered and its novelty depends on what already exists; or when You are assembling the related-work argument."
---

# Literature Review

> Ported from the ConvFusion research-skill library (category: `literature`; origin: discovery/cognition). Ask/answer using this method whenever it applies to the current research workspace.

## Purpose

Build an evidence-backed understanding of a research area — tasks, problems, methods, evidence, contradictions — rather than a list of paper summaries.

## When to Use

Use this skill when:

- You need to know what the field actually knows before proposing anything.
- A direction is being considered and its novelty depends on what already exists.
- You are assembling the related-work argument.

## Research Method

1. **Extract per paper on fixed dimensions** (problem, method, evidence, limitation) so that papers become comparable rather than merely summarised.
2. **Group by mechanism, not by terminology.** Two papers with different names for the same idea are one method family.
3. **Surface contradictions explicitly.** Where two works disagree, the disagreement is the most valuable output of the review.
4. **Identify the dominant direction and why it dominates** — the field's consensus is the baseline any contribution is measured against.
5. **Separate admitted limitations from inferred ones**, and keep the inference labelled as yours.

## Reasoning Guidance

<!-- 迁移自旧模块提示词；具体推理要点见下方逐字来源。 -->

## Evidence Requirements

Every extracted claim must be traceable to a specific work and location. Contradictions must cite both sides. Do not generalise from a single paper to "the field".

## Expected Output

Produce:

- per-paper extraction on the fixed dimensions
- method families with their representative works
- explicit contradictions with both sides cited
- the dominant direction and the reason it dominates

## Workspace Conventions

If this method reads or writes structured workspace files (evidence/claims/decisions, plans, papers, outputs, LaTeX, literature search/download), follow the exact schemas in this plugin's `reference/` directory rather than improvising a format — see [research-assets.md](../../reference/research-assets.md), [plans.md](../../reference/plans.md), [papers.md](../../reference/papers.md), [outputs.md](../../reference/outputs.md), [latex.md](../../reference/latex.md), [literature-search.md](../../reference/literature-search.md), and [paper-fulltext-download.md](../../reference/paper-fulltext-download.md), whichever applies. The `research` skill's [SKILL.md](../research/SKILL.md) is the usual entry point that pulls the right context together first; if this skill was invoked on its own, check whether a `project.md` or `research-state.md` already exists in the workspace before assuming there is none.

## Reference Prompts

The original, more verbose source prompts this method was distilled from are kept in [reference.md](reference.md) for extra detail when the summary above isn't enough (exact length/format constraints, worked examples, etc).
