---
name: research-domain-profiling
description: "Infer a researcher's domains and their confidence from how they describe their own work, so that direction choice can be matched to real strengths. Use when Onboarding a new research project; or when The research context lacks a clear domain profile; or when Choosing between directions that demand different kinds of expertise."
---

# Research Domain Profiling

> Ported from the ConvFusion research-skill library (category: `research-understanding`; origin: initiation/profile). Ask/answer using this method whenever it applies to the current research workspace.

## Purpose

Infer a researcher's domains and their confidence from how they describe their own work, so that direction choice can be matched to real strengths.

## When to Use

Use this skill when:

- Onboarding a new research project.
- The research context lacks a clear domain profile.
- Choosing between directions that demand different kinds of expertise.

## Research Method

1. **Read the description for demonstrated work, not claimed labels.** "I have published on calibration" outweighs "I am interested in robotics".
2. **Assign per-domain confidence**, and say what raised or lowered it. A flat list of domains with equal weight is not a profile.
3. **Describe the foundation**, not the job title: what methods the researcher can actually execute unaided.
4. **Separate adjacent-domain competence from primary domain.** Adjacency determines which collaborations or literature transfers.
5. **Record preferences that constrain direction choice** (risk appetite, theory vs systems, time budget, venue target).

## Reasoning Guidance

<!-- 迁移自旧模块提示词；具体推理要点见下方逐字来源。 -->

## Evidence Requirements

Domain confidence should be tied to evidence in the description or in prior artefacts. Do not infer seniority from writing style.

## Expected Output

Produce:

- domains with per-domain confidence and the basis for it
- a foundation description (what can be executed unaided)
- adjacent competences
- preferences that should constrain direction choice

## Workspace Conventions

If this method reads or writes structured workspace files (evidence/claims/decisions, plans, papers, outputs, LaTeX, literature search/download), follow the exact schemas in this plugin's `reference/` directory rather than improvising a format — see [research-assets.md](../../reference/research-assets.md), [plans.md](../../reference/plans.md), [papers.md](../../reference/papers.md), [outputs.md](../../reference/outputs.md), [latex.md](../../reference/latex.md), [literature-search.md](../../reference/literature-search.md), and [paper-fulltext-download.md](../../reference/paper-fulltext-download.md), whichever applies. The `research` skill's [SKILL.md](../research/SKILL.md) is the usual entry point that pulls the right context together first; if this skill was invoked on its own, check whether a `project.md` or `research-state.md` already exists in the workspace before assuming there is none.

## Reference Prompts

The original, more verbose source prompts this method was distilled from are kept in [reference.md](reference.md) for extra detail when the summary above isn't enough (exact length/format constraints, worked examples, etc).
