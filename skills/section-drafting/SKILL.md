---
name: section-drafting
description: "Turn the research state into complete section prose that respects each section's function, length budget and citation contract, with every quantitative statement traceable to a result. Use when The outline and narrative exist and a specific section must now be produced as prose; or when A section note, method sketch or results table must become publishable text; or when A section is outside its length budget or repeats another section."
---

# Section Drafting from Evidence

> Ported from the ConvFusion research-skill library (category: `academic-writing`; origin: paper/writing (title, abstract, intro, method, experiment, conclusion)). Ask/answer using this method whenever it applies to the current research workspace.

## Purpose

Turn the research state into complete section prose that respects each section's function, length budget and citation contract, with every quantitative statement traceable to a result.

## When to Use

Use this skill when:

- The outline and narrative exist and a specific section must now be produced as prose.
- A section note, method sketch or results table must become publishable text.
- A section is outside its length budget or repeats another section.

## Research Method

1. **Fix the section contract first**: the reader question it answers, the evidence it may use, its length budget, and whether citations are allowed — the abstract and conclusion introduce no new citations, the introduction and related work are citation-dense.
2. **Title and abstract are compression, not summary.** The title names the method and the problem in 10-15 words; the abstract states problem, method, one quantitative result and its significance, defines acronyms at first use, and carries no citations.
3. **The introduction follows the narrative arc and commits early**: state the problem quickly, place the gap within the first paragraphs, introduce the method before the contributions, then close with the contributions and a short paper-organisation paragraph that matches the real outline.
4. **Method explains why before what.** Describe the architecture, then each component, then the formulation and design rationale; every design choice needs a justification and enough implementation detail to reproduce it. Keep simple symbols inline in the prose and whole formulas as named equation placeholders — never emit raw display math.
5. **Experiments report claim, number, interpretation.** Give a reproducible setup (data, metrics, hardware, hyperparameters), compare fairly against baselines, explain why the method wins rather than only by how much, and include an ablation that isolates each component.
6. **The conclusion answers the question the introduction posed**, restates what was demonstrated, and gives concrete next steps; it introduces no new result and no new analysis.
7. **Self-check before emitting**: length inside budget, every citation key present in the curated corpus, no number that contradicts the result artefacts, and no paragraph that duplicates another section.

## Reasoning Guidance

<!-- 迁移自旧模块提示词；具体推理要点见下方逐字来源。 -->

## Evidence Requirements

Every quantitative statement must trace to a result artefact (table, figure, run log) and every citation to a curated work. Claims about design choices must trace to a decision actually taken or an experiment actually run. Numbers in the abstract must appear in the body with the same value. Anything the section needed but the research state lacked is reported as a gap rather than filled in.

## Expected Output

Produce:

- section prose at the target length, depth and paragraph granularity
- inline citations on exact curated cite_keys, at logically correct locations
- equation placeholders and figure cross-references for the apparatus step
- a note of any evidence the section required but the research state did not contain

## Workspace Conventions

If this method reads or writes structured workspace files (evidence/claims/decisions, plans, papers, outputs, LaTeX, literature search/download), follow the exact schemas in this plugin's `reference/` directory rather than improvising a format — see [research-assets.md](../../reference/research-assets.md), [plans.md](../../reference/plans.md), [papers.md](../../reference/papers.md), [outputs.md](../../reference/outputs.md), [latex.md](../../reference/latex.md), [literature-search.md](../../reference/literature-search.md), and [paper-fulltext-download.md](../../reference/paper-fulltext-download.md), whichever applies. The `research` skill's [SKILL.md](../research/SKILL.md) is the usual entry point that pulls the right context together first; if this skill was invoked on its own, check whether a `project.md` or `research-state.md` already exists in the workspace before assuming there is none.

## Reference Prompts

The original, more verbose source prompts this method was distilled from are kept in [reference.md](reference.md) for extra detail when the summary above isn't enough (exact length/format constraints, worked examples, etc).
