---
name: paper-architecture
description: "Decide the section skeleton, the scope and length budget of each section, and the order in which sections are written — before any prose exists, so that sections cannot overlap or drift in length. Use when Starting a manuscript, or re-targeting an existing one from a conference template to an IEEE Transactions template; or when Section drafts exist but their scopes overlap, or the manuscript is under or over the page limit; or when You are about to write sections and need to know which evidence each one is allowed to use."
---

# Paper Architecture

> Ported from the ConvFusion research-skill library (category: `academic-writing`; origin: paper/writing (outline, chapter_writer)). Ask/answer using this method whenever it applies to the current research workspace.

## Purpose

Decide the section skeleton, the scope and length budget of each section, and the order in which sections are written — before any prose exists, so that sections cannot overlap or drift in length.

## When to Use

Use this skill when:

- Starting a manuscript, or re-targeting an existing one from a conference template to an IEEE Transactions template.
- Section drafts exist but their scopes overlap, or the manuscript is under or over the page limit.
- You are about to write sections and need to know which evidence each one is allowed to use.

## Research Method

1. **Fix the venue template before the skeleton.** A 4-6 page EI conference paper merges sections and stays terse; an 8-12 page IEEE Transactions paper expects subsections and depth. Choose the template first — it determines the section count, not the reverse.
2. **Write the outline as one line per section, each naming the question it answers and the artefact it draws on** (problem statement, method, results table, literature corpus). A section that cannot name its evidence is not ready to be planned.
3. **Assign an explicit length budget per section** and keep a running total against the page or word limit. Record the budget numerically, because every later length check is measured against it.
4. **Decide which sections split into subsections and which merge** (method: architecture, components, formulation; experiments: setup, comparison, ablation, analysis), and state the reason next to the decision.
5. **Fix the writing order and the carry-forward rule.** Write in an order that satisfies dependencies, and pass already-written text forward so terminology, claims and citation keys stay consistent instead of being re-invented per section.
6. **Audit the outline for duplication and omission** before drafting: two sections covering the same claim, or a claim from the narrative that no section owns, mean the skeleton is wrong.

## Reasoning Guidance

<!-- 迁移自旧模块提示词；具体推理要点见下方逐字来源。 -->

## Evidence Requirements

The outline must be derived from the actual research state — problem, method and experiment artefacts — not from a generic template; each section line must name the artefact it will use. Section budgets must be recorded as numbers so compliance can be checked rather than argued.

## Expected Output

Produce:

- the section skeleton with each section's question, scope and word budget
- the subsection map, with each merge or split decision and its reason
- the writing order plus the cross-section context that must be carried forward
- an outline audit listing duplicated claims and claims no section covers

## Workspace Conventions

If this method reads or writes structured workspace files (evidence/claims/decisions, plans, papers, outputs, LaTeX, literature search/download), follow the exact schemas in this plugin's `reference/` directory rather than improvising a format — see [research-assets.md](../../reference/research-assets.md), [plans.md](../../reference/plans.md), [papers.md](../../reference/papers.md), [outputs.md](../../reference/outputs.md), [latex.md](../../reference/latex.md), [literature-search.md](../../reference/literature-search.md), and [paper-fulltext-download.md](../../reference/paper-fulltext-download.md), whichever applies. The `research` skill's [SKILL.md](../research/SKILL.md) is the usual entry point that pulls the right context together first; if this skill was invoked on its own, check whether a `project.md` or `research-state.md` already exists in the workspace before assuming there is none.

## Reference Prompts

The original, more verbose source prompts this method was distilled from are kept in [reference.md](reference.md) for extra detail when the summary above isn't enough (exact length/format constraints, worked examples, etc).
