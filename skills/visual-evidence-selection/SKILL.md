---
name: visual-evidence-selection
description: "Choose which figures belong in the paper so that each one carries information the tables and prose do not, and so the figure count stays within the venue limit. Use when More candidate figures were collected than the paper can hold; or when A candidate figure repeats the comparison a table already makes; or when A result is argued in the text but never visualised."
---

# Visual Evidence Selection

> Ported from the ConvFusion research-skill library (category: `academic-writing`; origin: paper/artifacts (figure_selector)). Ask/answer using this method whenever it applies to the current research workspace.

## Purpose

Choose which figures belong in the paper so that each one carries information the tables and prose do not, and so the figure count stays within the venue limit.

## When to Use

Use this skill when:

- More candidate figures were collected than the paper can hold.
- A candidate figure repeats the comparison a table already makes.
- A result is argued in the text but never visualised.

## Research Method

1. **Read the experiments section first** to learn which figures the argument already refers to and which narrative the text emphasises.
2. **Inventory the tables and what they already show.** A table carrying the main quantitative comparison removes the need for a figure of the same numbers.
3. **Prefer the different angle**: training curves, qualitative or case-study examples, ablations the table only summarises, or a method overview the text describes but never draws.
4. **Rank the survivors by how much of the argument they support** and cut to the venue limit, ordered most important first.
5. **Record every rejected candidate with its reason** so the selection can be defended, and list the results that still lack a visual.
6. **Check each selected figure against its caption**: the caption states what the reader should conclude, not merely what the axes are.

## Reasoning Guidance

<!-- 迁移自旧模块提示词；具体推理要点见下方逐字来源。 -->

## Evidence Requirements

Selected items must be identifiers that exist in the collected candidate set — none may be invented. Each selected figure must be tied to a claim in the text and must not duplicate information a table already carries. Rejected candidates and the reason for rejection are recorded.

## Expected Output

Produce:

- the ordered list of selected figure ids, most important first
- the rejected candidates with the reason for each rejection
- a caption outline stating the intended conclusion for every selected figure
- the list of results that remain unvisualised

## Workspace Conventions

If this method reads or writes structured workspace files (evidence/claims/decisions, plans, papers, outputs, LaTeX, literature search/download), follow the exact schemas in this plugin's `reference/` directory rather than improvising a format — see [research-assets.md](../../reference/research-assets.md), [plans.md](../../reference/plans.md), [papers.md](../../reference/papers.md), [outputs.md](../../reference/outputs.md), [latex.md](../../reference/latex.md), [literature-search.md](../../reference/literature-search.md), and [paper-fulltext-download.md](../../reference/paper-fulltext-download.md), whichever applies. The `research` skill's [SKILL.md](../research/SKILL.md) is the usual entry point that pulls the right context together first; if this skill was invoked on its own, check whether a `project.md` or `research-state.md` already exists in the workspace before assuming there is none.

## Reference Prompts

The original, more verbose source prompts this method was distilled from are kept in [reference.md](reference.md) for extra detail when the summary above isn't enough (exact length/format constraints, worked examples, etc).
