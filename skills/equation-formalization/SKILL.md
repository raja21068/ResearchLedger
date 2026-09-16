---
name: equation-formalization
description: "Convert prose descriptions of mathematics into a typed, uniquely labelled equation set that renders deterministically and stays consistent with the notation used in the surrounding text. Use when The method describes computations in words but the paper needs numbered equations; or when The same quantity is written several different ways across sections; or when Equations must be referenced by number, or rendered from a deterministic template rather than as free-form LaTeX."
---

# Equation Formalization

> Ported from the ConvFusion research-skill library (category: `academic-writing`; origin: paper/writing (equation), paper/equation (equation)). Ask/answer using this method whenever it applies to the current research workspace.

## Purpose

Convert prose descriptions of mathematics into a typed, uniquely labelled equation set that renders deterministically and stays consistent with the notation used in the surrounding text.

## When to Use

Use this skill when:

- The method describes computations in words but the paper needs numbered equations.
- The same quantity is written several different ways across sections.
- Equations must be referenced by number, or rendered from a deterministic template rather than as free-form LaTeX.

## Research Method

1. **Inventory the mathematics the method actually performs**: core computation, objective or loss, optimisation or update rule, normalisation or activation, aggregation, and any complexity statement. Each is a candidate equation — do not invent ones the text does not describe.
2. **Map each candidate to the closest standard equation type**, using a custom type only when nothing fits, so standard structures render deterministically instead of being re-typed.
3. **Give every equation a unique id and a unique label** of the form eq:name, and keep them stable once the text references them.
4. **Declare the variables** — symbol, meaning, dimension — taking definitions from the method text rather than inventing them.
5. **Emit structured objects, never raw display math.** Simple symbols stay inline in the prose; whole formulas become named placeholders that the renderer resolves.
6. **Cross-check in both directions**: every placeholder used in the text exists in the equation set, and every equation in the set is referenced from the text at least once.
7. **Verify naming consistency** so a symbol means the same thing in every section and in every figure caption.

## Reasoning Guidance

<!-- 迁移自旧模块提示词；具体推理要点见下方逐字来源。 -->

## Evidence Requirements

Each equation must be traceable to the sentence of the method text that describes it, and variable definitions must come from the method or the notation list. Custom LaTeX may use only standard commands and must not introduce notation the surrounding text does not define.

## Expected Output

Produce:

- the equation set: id, type, description, variables, label and section for each entry
- a mapping from each prose sentence to the equation it produced
- the inline-versus-placeholder decision for each symbol
- a consistency report between the equation set and the text

## Workspace Conventions

If this method reads or writes structured workspace files (evidence/claims/decisions, plans, papers, outputs, LaTeX, literature search/download), follow the exact schemas in this plugin's `reference/` directory rather than improvising a format — see [research-assets.md](../../reference/research-assets.md), [plans.md](../../reference/plans.md), [papers.md](../../reference/papers.md), [outputs.md](../../reference/outputs.md), [latex.md](../../reference/latex.md), [literature-search.md](../../reference/literature-search.md), and [paper-fulltext-download.md](../../reference/paper-fulltext-download.md), whichever applies. The `research` skill's [SKILL.md](../research/SKILL.md) is the usual entry point that pulls the right context together first; if this skill was invoked on its own, check whether a `project.md` or `research-state.md` already exists in the workspace before assuming there is none.

## Reference Prompts

The original, more verbose source prompts this method was distilled from are kept in [reference.md](reference.md) for extra detail when the summary above isn't enough (exact length/format constraints, worked examples, etc).
