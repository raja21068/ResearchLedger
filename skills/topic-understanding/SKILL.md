---
name: topic-understanding
description: "Turn an unstructured input — a paper, repository, dataset, conversation, half-formed idea — into a precise statement of what is actually being researched: its source type, domain, and substantive content. Use when A new piece of material enters the project and you do not yet know how to treat it; or when The user describes an interest in vague terms and you must find the research inside it; or when You are about to search the literature but the question itself is still unclear."
---

# Topic Understanding

> Ported from the ConvFusion research-skill library (category: `research-understanding`). Ask/answer using this method whenever it applies to the current research workspace.

## Purpose

Turn an unstructured input — a paper, repository, dataset, conversation, half-formed idea — into a precise statement of what is actually being researched: its source type, domain, and substantive content.

## When to Use

Use this skill when:

- A new piece of material enters the project and you do not yet know how to treat it.
- The user describes an interest in vague terms and you must find the research inside it.
- You are about to search the literature but the question itself is still unclear.

## Research Method

1. **Classify the input's source type.** Paper, patent, code, dataset, conversation, experiment log, report, or other. Treatment differs: a dataset claim needs different support from a conversation claim. If ambiguous, say so rather than defaulting silently.
2. **Identify the domain at the level a researcher would name it** (e.g. "Robotics (Embodied AI)", not "Computer Science"). The domain determines which literature is relevant and which baselines count.
3. **Separate what the input states from what it implies.** List explicitly: stated problems, methods, results, limitations, claimed future work. Do not merge these into one summary — their differences are where research questions come from.
4. **Extract research signals.** A signal is something that could become a research direction: an admitted limitation, a contradiction with another work, a missing evaluation dimension, an untested assumption.
5. **Assemble a research seed** — domain + problem + signals — expressed so a later step can build a direction from it. If the material cannot support a seed, state what is missing.

## Reasoning Guidance

<!-- 迁移自旧模块提示词；具体推理要点见下方逐字来源。 -->

## Evidence Requirements

Every claim about what the material says must be traceable to the material (section, figure, file path). Domain and source-type judgements should state their basis. Never let an agent-generated summary become the only record of a source.

## Expected Output

Produce:

- source type and domain, with the basis for each
- a problem / method / limitation / future-work breakdown that keeps them separate
- extracted research signals
- a research seed, or an explicit statement of what is missing to form one

## Workspace Conventions

If this method reads or writes structured workspace files (evidence/claims/decisions, plans, papers, outputs, LaTeX, literature search/download), follow the exact schemas in this plugin's `reference/` directory rather than improvising a format — see [research-assets.md](../../reference/research-assets.md), [plans.md](../../reference/plans.md), [papers.md](../../reference/papers.md), [outputs.md](../../reference/outputs.md), [latex.md](../../reference/latex.md), [literature-search.md](../../reference/literature-search.md), and [paper-fulltext-download.md](../../reference/paper-fulltext-download.md), whichever applies. The `research` skill's [SKILL.md](../research/SKILL.md) is the usual entry point that pulls the right context together first; if this skill was invoked on its own, check whether a `project.md` or `research-state.md` already exists in the workspace before assuming there is none.

## Reference Prompts

The original, more verbose source prompts this method was distilled from are kept in [reference.md](reference.md) for extra detail when the summary above isn't enough (exact length/format constraints, worked examples, etc).
