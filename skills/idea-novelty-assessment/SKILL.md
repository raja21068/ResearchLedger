---
name: idea-novelty-assessment
description: "Judge how much of an idea is actually new by locating each claim-bearing part of it against the closest prior work, rather than scoring novelty from the proposal wording. Use when An idea is a candidate for commitment and its novelty must be defended; or when You suspect prior art exists but cannot tell which part of the idea it touches; or when A reviewer or collaborator claims the idea is a known technique under a new name."
---

# Idea Novelty Assessment

> Ported from the ConvFusion research-skill library (category: `innovation`; origin: conception/idea-evaluation, decision/novelty-evaluation). Ask/answer using this method whenever it applies to the current research workspace.

## Purpose

Judge how much of an idea is actually new by locating each claim-bearing part of it against the closest prior work, rather than scoring novelty from the proposal wording.

## When to Use

Use this skill when:

- An idea is a candidate for commitment and its novelty must be defended.
- You suspect prior art exists but cannot tell which part of the idea it touches.
- A reviewer or collaborator claims the idea is a known technique under a new name.

## Research Method

1. **Never assess novelty from the proposal text alone.** Retrieve the nearest works first. Novelty is a relation between the idea and the literature, not a property of the write-up.
2. **Decompose the idea into claim-bearing parts** — problem formulation, mechanism, training or evaluation procedure, and setting. Attribute each part to prior work or to the proposal. Most ideas are novel in one part and derivative in the rest; say which part is which.
3. **Name the closest work per part and the exact difference.** A difference counts as a novelty claim only if you can state what it changes measurably — accuracy under a regime, cost, sample efficiency, scope of applicability.
4. **Classify the novelty type:** new problem, new mechanism, new combination, new setting or regime, or new evidence about an existing method. For combination novelty, argue non-triviality: why the parts do not compose without new work.
5. **Run the obvious-extension test.** Ask whether a competent researcher who had read the closest work would produce this as the next routine step. If yes, the novelty is incremental, and it is better to say so than to inflate it.
6. **Compare against the current state of the art, not the field entry point.** Reviewers compare with the strongest recent result; comparing with an old baseline manufactures novelty that will not survive review.
7. **Report novelty as a claim with its support**, including the prior art that could not be excluded because of search limits. Absence of evidence is not evidence of novelty.

## Reasoning Guidance

<!-- 迁移自旧模块提示词；具体推理要点见下方逐字来源。 -->

## Evidence Requirements

Every differentiating claim must cite the specific work it differs from and the location of the relevant method or result in it. Unresolved prior art must be flagged rather than omitted. No novelty claim may rest on the result of a single search.

## Expected Output

Produce:

- per-part attribution of the idea to prior work or to the proposal
- the closest work per part with the exact measurable difference
- novelty type, including a non-triviality argument for combinations
- an incremental-versus-structural judgement with its reasoning
- prior art that could not be ruled out

## Workspace Conventions

If this method reads or writes structured workspace files (evidence/claims/decisions, plans, papers, outputs, LaTeX, literature search/download), follow the exact schemas in this plugin's `reference/` directory rather than improvising a format — see [research-assets.md](../../reference/research-assets.md), [plans.md](../../reference/plans.md), [papers.md](../../reference/papers.md), [outputs.md](../../reference/outputs.md), [latex.md](../../reference/latex.md), [literature-search.md](../../reference/literature-search.md), and [paper-fulltext-download.md](../../reference/paper-fulltext-download.md), whichever applies. The `research` skill's [SKILL.md](../research/SKILL.md) is the usual entry point that pulls the right context together first; if this skill was invoked on its own, check whether a `project.md` or `research-state.md` already exists in the workspace before assuming there is none.

## Reference Prompts

The original, more verbose source prompts this method was distilled from are kept in [reference.md](reference.md) for extra detail when the summary above isn't enough (exact length/format constraints, worked examples, etc).
