---
name: research-idea-generation
description: "Produce a portfolio of genuinely distinct candidate research ideas, each attacking a named gap through a stated mechanism — instead of several rewordings of one idea. Use when A ranked set of gaps exists and you need candidate ways to close them; or when An existing idea list looks broad but every entry shares the same mechanism; or when You need cross-domain candidates and want their validity conditions made explicit."
---

# Research Idea Generation

> Ported from the ConvFusion research-skill library (category: `innovation`; origin: conception/idea-generation). Ask/answer using this method whenever it applies to the current research workspace.

## Purpose

Produce a portfolio of genuinely distinct candidate research ideas, each attacking a named gap through a stated mechanism — instead of several rewordings of one idea.

## When to Use

Use this skill when:

- A ranked set of gaps exists and you need candidate ways to close them.
- An existing idea list looks broad but every entry shares the same mechanism.
- You need cross-domain candidates and want their validity conditions made explicit.

## Research Method

1. **Fix the generation target before generating.** For each gap write the one-sentence change in capability the idea must produce. An idea that cannot state this is a restatement of existing work, however appealing it sounds.
2. **Generate across mechanisms, not within one.** For each gap, produce candidates from at least three different mechanism families — change the representation, change the training signal, change the inference procedure, change the evaluation setting. Mechanism diversity is what makes the later portfolio decision meaningful.
3. **Force cross-domain transfer to declare itself.** For at least one candidate per gap, name the source field and the imported mechanism, then state what must be re-derived for the import to be valid. Unexamined analogy is the most common source of fake novelty.
4. **Check the closest work while writing the idea, not after.** If you cannot name what differs from the nearest existing method and why that difference should matter, drop the candidate rather than keeping it with vague novelty language.
5. **State the falsifiable claim for each idea.** Write the observation that would show it does not work. An idea whose claim cannot fail is not researchable; it is a programme of work.
6. **Keep the idea separate from its implementation.** Record mechanism and claim only. Architecture, dataset and schedule belong to planning, and committing to them now silently deletes alternatives.
7. **Stop at coverage, not at a count.** Stop when every selected gap has at least one candidate from each plausible mechanism family; report the gaps that produced nothing and why, rather than padding the list.

## Reasoning Guidance

<!-- 迁移自旧模块提示词；具体推理要点见下方逐字来源。 -->

## Evidence Requirements

Each idea must reference the gap it addresses and the closest work it must be distinguished from. Any cross-domain import must name its source and what was re-derived. No idea may be justified by trend or popularity alone.

## Expected Output

Produce:

- candidate ideas, each with its gap, mechanism family and core claim
- the closest-work comparison that distinguishes each idea
- a falsification condition per idea
- cross-domain imports with their validity conditions
- gaps that yielded no viable candidate, with the reason

## Workspace Conventions

If this method reads or writes structured workspace files (evidence/claims/decisions, plans, papers, outputs, LaTeX, literature search/download), follow the exact schemas in this plugin's `reference/` directory rather than improvising a format — see [research-assets.md](../../reference/research-assets.md), [plans.md](../../reference/plans.md), [papers.md](../../reference/papers.md), [outputs.md](../../reference/outputs.md), [latex.md](../../reference/latex.md), [literature-search.md](../../reference/literature-search.md), and [paper-fulltext-download.md](../../reference/paper-fulltext-download.md), whichever applies. The `research` skill's [SKILL.md](../research/SKILL.md) is the usual entry point that pulls the right context together first; if this skill was invoked on its own, check whether a `project.md` or `research-state.md` already exists in the workspace before assuming there is none.

## Reference Prompts

The original, more verbose source prompts this method was distilled from are kept in [reference.md](reference.md) for extra detail when the summary above isn't enough (exact length/format constraints, worked examples, etc).
