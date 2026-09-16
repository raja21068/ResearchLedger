---
name: literature-screening
description: "Decide which retrieved works actually belong in the corpus, using stated criteria rather than relevance impressions, so that later synthesis rests on a defensible set. Use when A retrieval pass returned more works than can be read or cited; or when You must justify why a work was included or excluded; or when Duplicate or near-duplicate works from different queries need resolving."
---

# Literature Screening

> Ported from the ConvFusion research-skill library (category: `literature`; origin: discovery/curation). Ask/answer using this method whenever it applies to the current research workspace.

## Purpose

Decide which retrieved works actually belong in the corpus, using stated criteria rather than relevance impressions, so that later synthesis rests on a defensible set.

## When to Use

Use this skill when:

- A retrieval pass returned more works than can be read or cited.
- You must justify why a work was included or excluded.
- Duplicate or near-duplicate works from different queries need resolving.

## Research Method

1. **Fix the inclusion criteria before screening** — venue tier, recency window, task/setting match, whether the work reports results at all. Criteria chosen after looking at the results are not criteria.
2. **Score on separate axes** (quality, relevance, diversity) rather than one blended score. A highly relevant weak work and a weakly relevant strong work fail for different reasons.
3. **Resolve duplicates at the work level**, not the record level: preprints, venue versions and extended versions are one contribution.
4. **Verify before trusting.** If a work is load-bearing for a gap claim, check that it says what the abstract implies — abstracts overstate.
5. **Record every exclusion with its reason.** The excluded set is what shows the screening was principled.

## Reasoning Guidance

<!-- 迁移自旧模块提示词；具体推理要点见下方逐字来源。 -->

## Evidence Requirements

Each retained work needs its inclusion basis; each excluded work needs its exclusion reason. Any claim attributed to a work must be traceable to a specific location in it, not to its abstract.

## Expected Output

Produce:

- the inclusion/exclusion criteria, stated in advance
- per-work scores on the separate axes
- the retained corpus with the basis for each retention
- the exclusion log with reasons

## Workspace Conventions

If this method reads or writes structured workspace files (evidence/claims/decisions, plans, papers, outputs, LaTeX, literature search/download), follow the exact schemas in this plugin's `reference/` directory rather than improvising a format — see [research-assets.md](../../reference/research-assets.md), [plans.md](../../reference/plans.md), [papers.md](../../reference/papers.md), [outputs.md](../../reference/outputs.md), [latex.md](../../reference/latex.md), [literature-search.md](../../reference/literature-search.md), and [paper-fulltext-download.md](../../reference/paper-fulltext-download.md), whichever applies. The `research` skill's [SKILL.md](../research/SKILL.md) is the usual entry point that pulls the right context together first; if this skill was invoked on its own, check whether a `project.md` or `research-state.md` already exists in the workspace before assuming there is none.

## Reference Prompts

The original, more verbose source prompts this method was distilled from are kept in [reference.md](reference.md) for extra detail when the summary above isn't enough (exact length/format constraints, worked examples, etc).
