---
name: research-topic-ranking
description: "Rank candidate research topics on separated dimensions and state the reasoning, so that the choice can be revisited rather than re-argued. Use when Several candidate topics exist and one must be chosen; or when A topic is being questioned and it is unclear whether to continue or change; or when The user has stated preferences (risk, timeline, venue) that should constrain the choice."
---

# Research Topic Ranking

> Ported from the ConvFusion research-skill library (category: `research-decision`; origin: initiation/incubation). Ask/answer using this method whenever it applies to the current research workspace.

## Purpose

Rank candidate research topics on separated dimensions and state the reasoning, so that the choice can be revisited rather than re-argued.

## When to Use

Use this skill when:

- Several candidate topics exist and one must be chosen.
- A topic is being questioned and it is unclear whether to continue or change.
- The user has stated preferences (risk, timeline, venue) that should constrain the choice.

## Research Method

1. **Enumerate all candidates first**, including weak ones — a candidate never written down cannot be compared.
2. **Score on separated dimensions**: novelty, feasibility, expected impact, cost, risk. A single blended score hides exactly the trade-off the decision turns on.
3. **Apply the user's preferences as constraints, not tie-breakers.** If low risk is prioritised, a high-ceiling high-variance topic fails regardless of ceiling — and say so.
4. **Find the critical path** for each candidate: the single dependency that, if unavailable, kills it.
5. **Prefer topics that survive their own failure** — a negative result that still informs beats a failure that yields nothing.
6. **Record the ranking with its reasoning and the preferences that drove it**, so it can be reconsidered when assumptions change.

## Reasoning Guidance

<!-- 迁移自旧模块提示词；具体推理要点见下方逐字来源。 -->

## Evidence Requirements

Feasibility claims should reference what makes them feasible. Risk claims should name the specific failure. Novelty claims should cite the gap analysis or literature that establishes them.

## Expected Output

Produce:

- all candidates, including rejected ones
- per-dimension scores rather than one aggregate
- critical path and fallback per leading candidate
- the ranking with the reasoning and driving preferences

## Workspace Conventions

If this method reads or writes structured workspace files (evidence/claims/decisions, plans, papers, outputs, LaTeX, literature search/download), follow the exact schemas in this plugin's `reference/` directory rather than improvising a format — see [research-assets.md](../../reference/research-assets.md), [plans.md](../../reference/plans.md), [papers.md](../../reference/papers.md), [outputs.md](../../reference/outputs.md), [latex.md](../../reference/latex.md), [literature-search.md](../../reference/literature-search.md), and [paper-fulltext-download.md](../../reference/paper-fulltext-download.md), whichever applies. The `research` skill's [SKILL.md](../research/SKILL.md) is the usual entry point that pulls the right context together first; if this skill was invoked on its own, check whether a `project.md` or `research-state.md` already exists in the workspace before assuming there is none.

## Reference Prompts

The original, more verbose source prompts this method was distilled from are kept in [reference.md](reference.md) for extra detail when the summary above isn't enough (exact length/format constraints, worked examples, etc).
