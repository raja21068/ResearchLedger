---
name: problem-definition
description: "Convert a research interest into a falsifiable research problem: a question whose answer would change what we do, and which could turn out to be false. Use when A domain and some signals exist, but no committable research question does; or when A direction is stated so broadly that any result could be claimed to support it; or when You need to decide whether two candidate directions are actually the same problem."
---

# Problem Definition

> Ported from the ConvFusion research-skill library (category: `research-understanding`; origin: initiation/conversation, incubation). Ask/answer using this method whenever it applies to the current research workspace.

## Purpose

Convert a research interest into a falsifiable research problem: a question whose answer would change what we do, and which could turn out to be false.

## When to Use

Use this skill when:

- A domain and some signals exist, but no committable research question does.
- A direction is stated so broadly that any result could be claimed to support it.
- You need to decide whether two candidate directions are actually the same problem.

## Research Method

1. **State the problem as a question, not a topic.** "Geometry-conditioned adaptation" is a topic; "does conditioning the adapter on egocentric geometry change navigation performance when topology is held fixed?" is a problem.
2. **Name the comparison.** Every research problem implies a baseline or a null. If you cannot name what the answer is compared against, the problem is not yet defined.
3. **Specify the setting.** Dataset, model class, metric, deployment constraint — whatever the answer is conditional on. A problem that is true in every setting is usually not research.
4. **State the falsification condition.** What observation would show the answer is "no"? If nothing could, the problem is unfalsifiable and should be rewritten.
5. **Check separability.** If the problem bundles two independent questions, split it — bundled questions produce uninterpretable results.
6. **Write the seed down**, with topic, question, setting and falsification condition, so planning can act on it.

## Reasoning Guidance

<!-- 迁移自旧模块提示词；具体推理要点见下方逐字来源。 -->

## Evidence Requirements

The setting you specify should be justified: if you claim a dataset or metric is the standard one, that claim needs a literature basis. Falsification conditions must be concrete enough that someone else could check them.

## Expected Output

Produce:

- the research question, stated as a question
- the comparison / baseline it is against
- the setting it is conditional on
- the falsification condition
- a note on whether it needed splitting into sub-questions

## Workspace Conventions

If this method reads or writes structured workspace files (evidence/claims/decisions, plans, papers, outputs, LaTeX, literature search/download), follow the exact schemas in this plugin's `reference/` directory rather than improvising a format — see [research-assets.md](../../reference/research-assets.md), [plans.md](../../reference/plans.md), [papers.md](../../reference/papers.md), [outputs.md](../../reference/outputs.md), [latex.md](../../reference/latex.md), [literature-search.md](../../reference/literature-search.md), and [paper-fulltext-download.md](../../reference/paper-fulltext-download.md), whichever applies. The `research` skill's [SKILL.md](../research/SKILL.md) is the usual entry point that pulls the right context together first; if this skill was invoked on its own, check whether a `project.md` or `research-state.md` already exists in the workspace before assuming there is none.

## Reference Prompts

The original, more verbose source prompts this method was distilled from are kept in [reference.md](reference.md) for extra detail when the summary above isn't enough (exact length/format constraints, worked examples, etc).
