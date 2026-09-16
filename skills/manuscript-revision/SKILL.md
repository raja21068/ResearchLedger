---
name: manuscript-revision
description: "Raise a complete draft to a consistent, formal academic register without changing a single claim, number, citation or placeholder — and keep the change set auditable. Use when All sections are drafted and the prose quality is uneven across them; or when Terminology, notation or metric names drift between sections, tables and captions; or when A self-check or reviewer report lists clarity problems while the scientific content is settled."
---

# Manuscript Revision and Style

> Ported from the ConvFusion research-skill library (category: `academic-writing`; origin: paper/polishing (chapter_polisher, style)). Ask/answer using this method whenever it applies to the current research workspace.

## Purpose

Raise a complete draft to a consistent, formal academic register without changing a single claim, number, citation or placeholder — and keep the change set auditable.

## When to Use

Use this skill when:

- All sections are drafted and the prose quality is uneven across them.
- Terminology, notation or metric names drift between sections, tables and captions.
- A self-check or reviewer report lists clarity problems while the scientific content is settled.

## Research Method

1. **Revise in a fixed order: terminology and notation, then paragraph-level flow, then sentence register.** Fixing sentences before the term set is settled means doing the work twice.
2. **Standardise the term set first** — method name, dataset names, metric names, symbols — and apply the chosen form everywhere, including tables and figure captions.
3. **Rewrite for flow with explicit connectives**, replacing implicit jumps between sentences with contrast, consequence or addition, and giving each paragraph one topic sentence.
4. **Strip generated-text artefacts** such as "Firstly, Secondly, Thirdly", "In conclusion", empty intensifiers and rhetorical triplets, and replace informal phrasing with the formal equivalent.
5. **Protect the invariants.** Numbers, metrics, citation keys, equation placeholders and figure or table labels must survive unchanged; a polishing pass that alters one of them is a defect, not an edit.
6. **Constrain length to roughly ten percent of the original** and re-measure after each pass, so revision never silently expands or truncates the paper.
7. **Record the diff** — what changed and why — and flag any place where clarity would have required a content decision instead of deciding it unilaterally.

## Reasoning Guidance

<!-- 迁移自旧模块提示词；具体推理要点见下方逐字来源。 -->

## Evidence Requirements

Revision must preserve meaning: every number, metric, citation key, equation placeholder and cross-reference label stays unchanged, and the revision record shows what was altered. When a sentence cannot be made clear without changing its claim, the claim returns to the narrative step rather than being quietly rewritten.

## Expected Output

Produce:

- polished section text with the technical content intact
- the list of terminology and notation standardisations applied
- the list of places where clarity would have required a content decision
- the measured length change per section

## Workspace Conventions

If this method reads or writes structured workspace files (evidence/claims/decisions, plans, papers, outputs, LaTeX, literature search/download), follow the exact schemas in this plugin's `reference/` directory rather than improvising a format — see [research-assets.md](../../reference/research-assets.md), [plans.md](../../reference/plans.md), [papers.md](../../reference/papers.md), [outputs.md](../../reference/outputs.md), [latex.md](../../reference/latex.md), [literature-search.md](../../reference/literature-search.md), and [paper-fulltext-download.md](../../reference/paper-fulltext-download.md), whichever applies. The `research` skill's [SKILL.md](../research/SKILL.md) is the usual entry point that pulls the right context together first; if this skill was invoked on its own, check whether a `project.md` or `research-state.md` already exists in the workspace before assuming there is none.

## Reference Prompts

The original, more verbose source prompts this method was distilled from are kept in [reference.md](reference.md) for extra detail when the summary above isn't enough (exact length/format constraints, worked examples, etc).
