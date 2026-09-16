---
name: research-narrative
description: "Build the single argument the paper makes — problem, prior limitations, gap, insight, solution — and bind every cited work and every claimed contribution to a specific role in that argument. Use when Results exist but no defensible statement of novelty has been written yet; or when The list of contributions reads as a list of activities rather than as verifiable claims; or when Related work reads as a paper-by-paper summary, or the gap is asserted without support."
---

# Research Narrative and Positioning

> Ported from the ConvFusion research-skill library (category: `academic-writing`; origin: paper/narrative (storyline, quality_check), paper/writing (contribution, related_work)). Ask/answer using this method whenever it applies to the current research workspace.

## Purpose

Build the single argument the paper makes — problem, prior limitations, gap, insight, solution — and bind every cited work and every claimed contribution to a specific role in that argument.

## When to Use

Use this skill when:

- Results exist but no defensible statement of novelty has been written yet.
- The list of contributions reads as a list of activities rather than as verifiable claims.
- Related work reads as a paper-by-paper summary, or the gap is asserted without support.
- A storyline draft exists and you need to know which part of it is weak before writing sections from it.

## Research Method

1. **State the arc as five linked claims**: problem context, what existing approaches do and cannot do, the specific gap, the insight that closes it, and the solution that follows. If a link needs more than one sentence, it is not yet an argument.
2. **Use the gap to choose the literature, not the reverse.** Work backwards from the gap to the works that establish it, and drop works that only decorate the narrative.
3. **Assign every citation a role** — establishes context, identifies the problem, shows a limitation, motivates the approach, supplies a baseline, supports a claim, establishes theory, or provides a benchmark — plus the place in the text where it is used. A citation with no role is removed.
4. **Convert contributions into verifiable claims.** Each one must name what is new, what it is compared against, and which experiment or ablation demonstrates it. Drop anything that cannot be checked.
5. **Write related work thematically, by mechanism family, not chronologically.** Synthesise several works per paragraph, state what the family cannot do, and reserve the closing paragraph for why existing methods do not solve the stated problem.
6. **Score the narrative on explicit criteria** (arc completeness, logical coherence, citation coverage, specificity) and iterate on the lowest-scoring criterion rather than on the passages that already read well.
7. **Re-check that the gap claim survives the corpus.** If a cited work already closes the gap, the contribution must be re-positioned, not re-worded.

## Reasoning Guidance

<!-- 迁移自旧模块提示词；具体推理要点见下方逐字来源。 -->

## Evidence Requirements

Every limitation attributed to prior work must cite the specific work and the location that supports it; the gap must rest on more than one work. Every contribution must map to a concrete experiment, ablation or analysis artefact. Citation keys must exist in the curated corpus — none may be invented. Contradictions between cited works are reported, not smoothed over.

## Expected Output

Produce:

- the narrative arc as five explicitly linked claims
- a citation table mapping cite_key to narrative role and to the location where it is used
- three to five verifiable contributions, each tied to the evidence that demonstrates it
- a thematically organised related-work draft ending in an explicit positioning statement
- a scored quality assessment naming the weakest criterion and the planned fix

## Workspace Conventions

If this method reads or writes structured workspace files (evidence/claims/decisions, plans, papers, outputs, LaTeX, literature search/download), follow the exact schemas in this plugin's `reference/` directory rather than improvising a format — see [research-assets.md](../../reference/research-assets.md), [plans.md](../../reference/plans.md), [papers.md](../../reference/papers.md), [outputs.md](../../reference/outputs.md), [latex.md](../../reference/latex.md), [literature-search.md](../../reference/literature-search.md), and [paper-fulltext-download.md](../../reference/paper-fulltext-download.md), whichever applies. The `research` skill's [SKILL.md](../research/SKILL.md) is the usual entry point that pulls the right context together first; if this skill was invoked on its own, check whether a `project.md` or `research-state.md` already exists in the workspace before assuming there is none.

## Reference Prompts

The original, more verbose source prompts this method was distilled from are kept in [reference.md](reference.md) for extra detail when the summary above isn't enough (exact length/format constraints, worked examples, etc).
