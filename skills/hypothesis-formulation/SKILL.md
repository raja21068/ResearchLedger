---
name: hypothesis-formulation
description: "Turn a selected idea into a hypothesis precise enough to be wrong: named variables, a comparison, a predicted effect worth caring about, and the conditions under which it holds. Use when A direction has been chosen and the experiment must be made testable; or when An aim is written as a goal (\"study X\", \"improve Y\") rather than a claim; or when An experiment is planned but no result could count as evidence against it."
---

# Hypothesis Formulation

> Ported from the ConvFusion research-skill library (category: `innovation`; origin: conception/structuring, conception/innovation-state-synthesis). Ask/answer using this method whenever it applies to the current research workspace.

## Purpose

Turn a selected idea into a hypothesis precise enough to be wrong: named variables, a comparison, a predicted effect worth caring about, and the conditions under which it holds.

## When to Use

Use this skill when:

- A direction has been chosen and the experiment must be made testable.
- An aim is written as a goal ("study X", "improve Y") rather than a claim.
- An experiment is planned but no result could count as evidence against it.

## Research Method

1. **Write the hypothesis as a directional statement.** "Under condition Z, changing X raises Y relative to comparison C" — not "study X" and not "improve Y". A hypothesis with no direction cannot be wrong in an informative way.
2. **Name the independent variable, the dependent measure and the comparison.** If any of the three is missing, the hypothesis cannot be tested as written, and the missing element is the real work item.
3. **State the effect size that would matter.** "Better" without a magnitude cannot be separated from noise after the experiment is run; name the smallest difference that would change a decision.
4. **State the boundary conditions.** Regimes, datasets, scales, hardware. The hypothesis should predict where the effect weakens or reverses; a hypothesis that must hold everywhere is untestable.
5. **Split conjunctions.** A hypothesis containing "and" usually bundles two claims, so a partial failure becomes uninterpretable. Split it into separately checkable claims.
6. **Make it refutable by one experiment.** Name the observation that would falsify it and verify that the planned measurement could actually produce that observation.
7. **Rank the hypothesis against its alternatives.** Include the null and the trivial explanation — the effect comes from extra capacity, compute or tuning rather than from the mechanism. The experiment must be able to separate the mechanism from the confound.

## Reasoning Guidance

<!-- 迁移自旧模块提示词；具体推理要点见下方逐字来源。 -->

## Evidence Requirements

The hypothesis must cite the gap and the closest-work analysis that motivate it. Boundary conditions must be justified from prior evidence, not asserted. The refutation test must be concrete enough that another researcher could run it.

## Expected Output

Produce:

- hypotheses written as directional statements
- variables, comparison and the effect size that matters
- boundary conditions derived from prior evidence
- the concrete refutation test
- competing trivial explanations and how the experiment separates them

## Workspace Conventions

If this method reads or writes structured workspace files (evidence/claims/decisions, plans, papers, outputs, LaTeX, literature search/download), follow the exact schemas in this plugin's `reference/` directory rather than improvising a format — see [research-assets.md](../../reference/research-assets.md), [plans.md](../../reference/plans.md), [papers.md](../../reference/papers.md), [outputs.md](../../reference/outputs.md), [latex.md](../../reference/latex.md), [literature-search.md](../../reference/literature-search.md), and [paper-fulltext-download.md](../../reference/paper-fulltext-download.md), whichever applies. The `research` skill's [SKILL.md](../research/SKILL.md) is the usual entry point that pulls the right context together first; if this skill was invoked on its own, check whether a `project.md` or `research-state.md` already exists in the workspace before assuming there is none.

## Reference Prompts

The original, more verbose source prompts this method was distilled from are kept in [reference.md](reference.md) for extra detail when the summary above isn't enough (exact length/format constraints, worked examples, etc).
