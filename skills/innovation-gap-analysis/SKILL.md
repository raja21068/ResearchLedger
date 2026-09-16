---
name: innovation-gap-analysis
description: "Turn a literature landscape into the specific unresolved problems, methodological limitations and contradictions that a contribution could target — and separate structural gaps from areas that are merely unfamiliar to you. Use when A literature review or landscape exists and you need to know what is still open in it; or when You are about to generate ideas and want them aimed at real gaps rather than at topics; or when A gap is being claimed in a proposal and must survive the question \"has this already been done?\"."
---

# Innovation Gap Analysis

> Ported from the ConvFusion research-skill library (category: `innovation`; origin: conception/understanding, conception/gap-discovery). Ask/answer using this method whenever it applies to the current research workspace.

## Purpose

Turn a literature landscape into the specific unresolved problems, methodological limitations and contradictions that a contribution could target — and separate structural gaps from areas that are merely unfamiliar to you.

## When to Use

Use this skill when:

- A literature review or landscape exists and you need to know what is still open in it.
- You are about to generate ideas and want them aimed at real gaps rather than at topics.
- A gap is being claimed in a proposal and must survive the question "has this already been done?".

## Research Method

1. **Re-derive the gap from the landscape, not from one paper.** A gap is a statement about the field, so it must rest on the multi-work picture (settled vs contested results, method families). If the search has not reached saturation, say so before claiming anything is unresolved.
2. **Classify each candidate gap by type.** An untested assumption; a contradiction between works; a limitation the authors themselves admit; a capability that exists but not under this setting; a problem no method addresses at all. The type determines what evidence would close the gap.
3. **Test each gap for resolution before recording it.** Search recent literature specifically for work that already addresses it. A gap that has been closed and merely not read is not a gap — record the closest existing work next to every claimed gap.
4. **Separate structural from incidental gaps.** A gap that persists across many groups and settings is structural; one that exists because a single paper used a small dataset is incidental. Structural gaps support a contribution; incidental ones support at most a paper.
5. **Name the mechanism that produces the gap.** "No method handles X" is a description; "existing methods assume Y, which fails when X" is a mechanism, and it predicts what a solution must change. Prefer mechanistic gap statements.
6. **Rank by consequence, not by ease of filling.** For each gap state what becomes possible if it is closed and which existing result would be overturned. A gap that changes nothing measurable is not worth a project.
7. **Record contradiction pairs explicitly.** When two works disagree, keep both citations and state the condition under which each could be right — that condition is frequently the research question.

## Reasoning Guidance

<!-- 迁移自旧模块提示词；具体推理要点见下方逐字来源。 -->

## Evidence Requirements

Every gap must cite the works that define the boundary of current capability plus the closest work that approaches it. Contradiction claims must cite both sides. The search coverage that licenses the word "unresolved" must be recorded, and anything the search could not rule out must be flagged as such.

## Expected Output

Produce:

- the gap list with each gap classified by type and mechanism
- closest existing work per gap, with the exact difference
- contradiction pairs with the condition under which each side holds
- a consequence-based ranking of the gaps
- an explicit statement of what the search could not exclude

## Workspace Conventions

If this method reads or writes structured workspace files (evidence/claims/decisions, plans, papers, outputs, LaTeX, literature search/download), follow the exact schemas in this plugin's `reference/` directory rather than improvising a format — see [research-assets.md](../../reference/research-assets.md), [plans.md](../../reference/plans.md), [papers.md](../../reference/papers.md), [outputs.md](../../reference/outputs.md), [latex.md](../../reference/latex.md), [literature-search.md](../../reference/literature-search.md), and [paper-fulltext-download.md](../../reference/paper-fulltext-download.md), whichever applies. The `research` skill's [SKILL.md](../research/SKILL.md) is the usual entry point that pulls the right context together first; if this skill was invoked on its own, check whether a `project.md` or `research-state.md` already exists in the workspace before assuming there is none.

## Reference Prompts

The original, more verbose source prompts this method was distilled from are kept in [reference.md](reference.md) for extra detail when the summary above isn't enough (exact length/format constraints, worked examples, etc).
