---
name: research-intent-assessment
description: "Judge whether an input is a genuine research request, a direction suggestion, or ordinary dialogue — and decide how much research machinery it warrants. Use when It is unclear whether the user wants research work or just conversation; or when A message could be read as either a new research direction or a passing remark; or when You are about to spend significant effort and want to confirm the intent first."
---

# Research Intent Assessment

> Ported from the ConvFusion research-skill library (category: `research-understanding`; origin: initiation/gate). Ask/answer using this method whenever it applies to the current research workspace.

## Purpose

Judge whether an input is a genuine research request, a direction suggestion, or ordinary dialogue — and decide how much research machinery it warrants.

## When to Use

Use this skill when:

- It is unclear whether the user wants research work or just conversation.
- A message could be read as either a new research direction or a passing remark.
- You are about to spend significant effort and want to confirm the intent first.

## Research Method

1. **Read the input against the current research state.** A remark about a limitation is often a direction suggestion, not a request to run analysis.
2. **Classify explicitly** into: dialogue (answer and continue), suggestion (offer candidate directions), or activation (commit to research work). Name the evidence for the classification.
3. **Calibrate confidence honestly.** A confident misclassification costs more than an explicit "this is ambiguous, here are the two readings".
4. **Check scientific-ness.** Not every request is answerable by research; say when it is an engineering or writing request instead.
5. **Match effort to intent.** Do not start a full literature search for a passing question; do not answer a real research request with a paragraph of prose.

## Reasoning Guidance

<!-- 迁移自旧模块提示词；具体推理要点见下方逐字来源。 -->

## Evidence Requirements

The classification should quote the specific part of the input that drove it. When intent is ambiguous, record both readings rather than silently choosing.

## Expected Output

Produce:

- the intent class, with confidence and the evidence for it
- whether the request is scientific at all
- what the next research action would be, if the intent is activation

## Workspace Conventions

If this method reads or writes structured workspace files (evidence/claims/decisions, plans, papers, outputs, LaTeX, literature search/download), follow the exact schemas in this plugin's `reference/` directory rather than improvising a format — see [research-assets.md](../../reference/research-assets.md), [plans.md](../../reference/plans.md), [papers.md](../../reference/papers.md), [outputs.md](../../reference/outputs.md), [latex.md](../../reference/latex.md), [literature-search.md](../../reference/literature-search.md), and [paper-fulltext-download.md](../../reference/paper-fulltext-download.md), whichever applies. The `research` skill's [SKILL.md](../research/SKILL.md) is the usual entry point that pulls the right context together first; if this skill was invoked on its own, check whether a `project.md` or `research-state.md` already exists in the workspace before assuming there is none.

## Reference Prompts

The original, more verbose source prompts this method was distilled from are kept in [reference.md](reference.md) for extra detail when the summary above isn't enough (exact length/format constraints, worked examples, etc).
