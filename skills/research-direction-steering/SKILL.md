---
name: research-direction-steering
description: "Guide a researcher from a vague interest toward concrete, researchable directions — without prescribing a workflow, and without pretending the first candidate is the answer. Use when The user expresses interest but no well-formed direction; or when Several candidate directions exist but none has been made precise; or when The user is choosing between directions and needs the trade-offs surfaced."
---

# Research Direction Steering

> Ported from the ConvFusion research-skill library (category: `research-decision`; origin: initiation/conversation, incubation). Ask/answer using this method whenever it applies to the current research workspace.

## Purpose

Guide a researcher from a vague interest toward concrete, researchable directions — without prescribing a workflow, and without pretending the first candidate is the answer.

## When to Use

Use this skill when:

- The user expresses interest but no well-formed direction.
- Several candidate directions exist but none has been made precise.
- The user is choosing between directions and needs the trade-offs surfaced.

## Research Method

1. **Extract what actually interests the user** from how they describe the problem, not from the labels they use. Interest in 'robustness' may mean evaluation methodology rather than model design.
2. **Expand into distinct directions**, each stated as something that could be researched. Directions that differ only in dataset or scale are the same direction.
3. **Make each direction concrete enough to judge**: what would be built, what would be compared, what result would matter.
4. **Surface the trade-offs** — novelty against feasibility, ceiling against variance — and let the user's stated preferences decide rather than an aggregate score.
5. **Identify what would have to be true** for each direction to succeed, so the user can judge which assumptions they are willing to bet on.
6. **Rank with reasoning retained.** A ranking whose reasoning is discarded cannot be revisited when the situation changes.

## Reasoning Guidance

<!-- 迁移自旧模块提示词；具体推理要点见下方逐字来源。 -->

## Evidence Requirements

Novelty or feasibility claims about a direction need a basis (a gap in the literature, an available artefact). Do not assert that a direction is unexplored without saying what was searched.

## Expected Output

Produce:

- the user's actual interests, restated precisely
- candidate directions that are genuinely distinct
- per-direction what-would-be-built / what-would-be-compared / what-result-matters
- the trade-offs and the assumptions each direction bets on
- a ranking with its reasoning

## Workspace Conventions

If this method reads or writes structured workspace files (evidence/claims/decisions, plans, papers, outputs, LaTeX, literature search/download), follow the exact schemas in this plugin's `reference/` directory rather than improvising a format — see [research-assets.md](../../reference/research-assets.md), [plans.md](../../reference/plans.md), [papers.md](../../reference/papers.md), [outputs.md](../../reference/outputs.md), [latex.md](../../reference/latex.md), [literature-search.md](../../reference/literature-search.md), and [paper-fulltext-download.md](../../reference/paper-fulltext-download.md), whichever applies. The `research` skill's [SKILL.md](../research/SKILL.md) is the usual entry point that pulls the right context together first; if this skill was invoked on its own, check whether a `project.md` or `research-state.md` already exists in the workspace before assuming there is none.

## Reference Prompts

The original, more verbose source prompts this method was distilled from are kept in [reference.md](reference.md) for extra detail when the summary above isn't enough (exact length/format constraints, worked examples, etc).
