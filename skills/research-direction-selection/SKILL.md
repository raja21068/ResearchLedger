---
name: research-direction-selection
description: "Choose which direction to commit to from an evaluated portfolio, with the criteria and trade-offs recorded so the choice can be defended or revisited rather than re-argued from scratch. Use when Several evaluated ideas compete for the same time and resources; or when A direction must be committed to and the rejection reasons are not written down; or when Two candidates look comparable and the decision keeps being reopened."
---

# Research Direction Selection

> Ported from the ConvFusion research-skill library (category: `research-decision`; origin: conception/idea-evaluation, conception/idea-selection). Ask/answer using this method whenever it applies to the current research workspace.

## Purpose

Choose which direction to commit to from an evaluated portfolio, with the criteria and trade-offs recorded so the choice can be defended or revisited rather than re-argued from scratch.

## When to Use

Use this skill when:

- Several evaluated ideas compete for the same time and resources.
- A direction must be committed to and the rejection reasons are not written down.
- Two candidates look comparable and the decision keeps being reopened.

## Research Method

1. **Fix the criteria and their weights before looking at the ranking.** State the axes — novelty, feasibility, expected impact, cost, strategic fit — and the weight each carries, plus who set them. Criteria chosen after seeing the scores are rationalisation, not criteria.
2. **Score on independent axes and keep the vector.** A single blended score hides the trade-off that the decision actually is. Report the score per axis rather than one number.
3. **Check score grounding before comparing anything.** Any axis whose score cannot be tied to an artefact — a closest-work comparison, a resource estimate, a risk register — must be marked low-confidence and excluded from the deciding comparison.
4. **Eliminate dominated candidates explicitly and record why:** dominated on every axis, unfalsifiable, or resting on a gap that is already closed. The rejected list is what shows the selection was principled.
5. **Keep the top two or three, then choose one.** Name what the runner-up would win on and the condition under which the decision should be revisited — that condition is the trigger for reversing it later.
6. **State the decision dependencies.** If the chosen direction rests on an unverified assumption (a dataset exists, a method scales, a licence permits use), record it as a decision risk rather than hiding it in optimism.
7. **Write the rationale for a reader who disagrees**, listing the trade-offs accepted rather than only the winner's merits.

## Reasoning Guidance

<!-- 迁移自旧模块提示词；具体推理要点见下方逐字来源。 -->

## Evidence Requirements

Every score on every axis must cite the artefact it came from. The criteria weights and their provenance must be recorded before the scores are compared. Rejected candidates must be logged with the axis or gate that eliminated them.

## Expected Output

Produce:

- the criteria and weights, fixed before scoring
- per-candidate score vectors with a confidence note per axis
- the rejected/dominated list with reasons
- the chosen direction and what it commits
- the runner-up, its winning axis, and the revisit trigger

## Workspace Conventions

If this method reads or writes structured workspace files (evidence/claims/decisions, plans, papers, outputs, LaTeX, literature search/download), follow the exact schemas in this plugin's `reference/` directory rather than improvising a format — see [research-assets.md](../../reference/research-assets.md), [plans.md](../../reference/plans.md), [papers.md](../../reference/papers.md), [outputs.md](../../reference/outputs.md), [latex.md](../../reference/latex.md), [literature-search.md](../../reference/literature-search.md), and [paper-fulltext-download.md](../../reference/paper-fulltext-download.md), whichever applies. The `research` skill's [SKILL.md](../research/SKILL.md) is the usual entry point that pulls the right context together first; if this skill was invoked on its own, check whether a `project.md` or `research-state.md` already exists in the workspace before assuming there is none.

## Reference Prompts

The original, more verbose source prompts this method was distilled from are kept in [reference.md](reference.md) for extra detail when the summary above isn't enough (exact length/format constraints, worked examples, etc).
