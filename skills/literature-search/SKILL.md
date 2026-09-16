---
name: literature-search
description: "Turn a research question into an executable retrieval strategy, and judge when the retrieved corpus is sufficient — rather than stopping at the first page of results. Use when You need literature coverage for a question that is not yet precise enough to search; or when A previous search returned results that look plausible but you cannot tell whether coverage is adequate; or when You are about to claim a gap and need to know the search was broad enough to support that claim."
---

# Literature Search

> Ported from the ConvFusion research-skill library (category: `literature`; origin: discovery/retrieval). Ask/answer using this method whenever it applies to the current research workspace.

## Purpose

Turn a research question into an executable retrieval strategy, and judge when the retrieved corpus is sufficient — rather than stopping at the first page of results.

## When to Use

Use this skill when:

- You need literature coverage for a question that is not yet precise enough to search.
- A previous search returned results that look plausible but you cannot tell whether coverage is adequate.
- You are about to claim a gap and need to know the search was broad enough to support that claim.

## Research Method

0. **Execute the queries — do not recall papers from memory.** Call the `research_literature_search` tool (OpenAlex) to obtain an actual retrieved set. It returns structured records **and a `provenance` block** (query, source, retrieval time, de-identified request URL, total hits) — a literature finding recorded without that provenance is not traceable, so record it. `total` is the number of matches and `returned` is only this page: a coverage claim needs the query set, not one page. If the tool reports a failure (missing key, HTTP error, timeout), say so — never present an empty result as "nothing was found". Without an API key it still works through OpenAlex's public pool at lower rate limits; the key lives in Settings → ConvFusion → Retrieval source.
1. **Rewrite the question into query terms.** Separate the concept terms from the setting terms (dataset, metric, domain). A query that mixes them returns either too much or too little.
2. **Expand deliberately, then constrain.** Expand along method synonyms and adjacent terminology; constrain by the setting. Record which expansions produced usable results — that is what makes the search reproducible.
3. **Assess coverage before curating.** For each sub-area the question implies, check whether it is represented in the retrieved set. Missing sub-areas mean the search is incomplete, not that the literature is thin.
4. **Iterate on the gaps**, not on the volume. A second pass driven by "which facet is under-represented" is worth more than a broader first query.
5. **Stop on saturation, and say so.** State the criterion you used (new queries stop adding new sub-areas) and record the queries that were run, so a later reviewer can re-run them.

## Reasoning Guidance

<!-- 迁移自旧模块提示词；具体推理要点见下方逐字来源。 -->

## Evidence Requirements

Record the queries, the databases/sources, the retrieval dates and the filtering rules. A coverage claim without the query set is not checkable. Never present your own summary of what the literature says as the evidence — cite the works.

## Expected Output

Produce:

- the query set with the expansion rationale
- a coverage assessment per sub-area the question implies
- the saturation criterion and whether it was reached
- the retrieval provenance (sources, dates, filters)

## Workspace Conventions

If this method reads or writes structured workspace files (evidence/claims/decisions, plans, papers, outputs, LaTeX, literature search/download), follow the exact schemas in this plugin's `reference/` directory rather than improvising a format — see [research-assets.md](../../reference/research-assets.md), [plans.md](../../reference/plans.md), [papers.md](../../reference/papers.md), [outputs.md](../../reference/outputs.md), [latex.md](../../reference/latex.md), [literature-search.md](../../reference/literature-search.md), and [paper-fulltext-download.md](../../reference/paper-fulltext-download.md), whichever applies. The `research` skill's [SKILL.md](../research/SKILL.md) is the usual entry point that pulls the right context together first; if this skill was invoked on its own, check whether a `project.md` or `research-state.md` already exists in the workspace before assuming there is none.

## Reference Prompts

The original, more verbose source prompts this method was distilled from are kept in [reference.md](reference.md) for extra detail when the summary above isn't enough (exact length/format constraints, worked examples, etc).
