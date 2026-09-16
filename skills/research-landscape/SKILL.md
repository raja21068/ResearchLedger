---
name: research-landscape
description: "Synthesise the reviewed literature into a landscape: what is settled, what is contested, what is moving — the picture a newcomer needs to place a contribution. Use when The reviewed corpus needs to become a navigable picture rather than a pile of extractions; or when You need to place a proposed contribution relative to the field; or when You are deciding which sub-area is worth entering."
---

# Research Landscape

> Ported from the ConvFusion research-skill library (category: `literature`; origin: discovery/cognition, synthesis). Ask/answer using this method whenever it applies to the current research workspace.

## Purpose

Synthesise the reviewed literature into a landscape: what is settled, what is contested, what is moving — the picture a newcomer needs to place a contribution.

## When to Use

Use this skill when:

- The reviewed corpus needs to become a navigable picture rather than a pile of extractions.
- You need to place a proposed contribution relative to the field.
- You are deciding which sub-area is worth entering.

## Research Method

1. **Map the sub-areas** and the works that define each. A landscape with undefined regions is a reading list, not a landscape.
2. **Mark what is settled vs contested.** Settled results constrain the contribution; contested ones are where work is possible.
3. **Track trends as direction of movement**, and say what evidence supports the trend — a trend asserted from one paper is a guess.
4. **Identify challenges and their persistence.** A challenge that has survived several attempts is a different opportunity from a newly appeared one.
5. **State the unexploited combinations** where two mature lines have not been combined, and why the combination is not trivial.

## Reasoning Guidance

<!-- 迁移自旧模块提示词；具体推理要点见下方逐字来源。 -->

## Evidence Requirements

Sub-area boundaries and settled/contested labels must cite the works that justify them. Trend claims need multiple supporting works and a time basis.

## Expected Output

Produce:

- sub-areas with defining works
- settled vs contested results
- trends with their supporting evidence
- persistent challenges and unexploited combinations

## Workspace Conventions

If this method reads or writes structured workspace files (evidence/claims/decisions, plans, papers, outputs, LaTeX, literature search/download), follow the exact schemas in this plugin's `reference/` directory rather than improvising a format — see [research-assets.md](../../reference/research-assets.md), [plans.md](../../reference/plans.md), [papers.md](../../reference/papers.md), [outputs.md](../../reference/outputs.md), [latex.md](../../reference/latex.md), [literature-search.md](../../reference/literature-search.md), and [paper-fulltext-download.md](../../reference/paper-fulltext-download.md), whichever applies. The `research` skill's [SKILL.md](../research/SKILL.md) is the usual entry point that pulls the right context together first; if this skill was invoked on its own, check whether a `project.md` or `research-state.md` already exists in the workspace before assuming there is none.

## Reference Prompts

The original, more verbose source prompts this method was distilled from are kept in [reference.md](reference.md) for extra detail when the summary above isn't enough (exact length/format constraints, worked examples, etc).
