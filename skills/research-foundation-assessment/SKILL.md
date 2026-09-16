---
name: research-foundation-assessment
description: "Assess the methodological foundation behind a researcher's stated skills, distinguishing claimed skills from demonstrated ones. Use when Deciding how much scaffolding a research plan needs; or when Matching a direction to a researcher's real strengths; or when Reviewing an artefact (paper, code, report) to infer the level of method."
---

# Research Foundation Assessment

> Ported from the ConvFusion research-skill library (category: `research-understanding`; origin: initiation/profile). Ask/answer using this method whenever it applies to the current research workspace.

## Purpose

Assess the methodological foundation behind a researcher's stated skills, distinguishing claimed skills from demonstrated ones.

## When to Use

Use this skill when:

- Deciding how much scaffolding a research plan needs.
- Matching a direction to a researcher's real strengths.
- Reviewing an artefact (paper, code, report) to infer the level of method.

## Research Method

1. **Extract the concrete methods used in the artefact** (not the topic it is about).
2. **Classify depth per method**: can use, can modify, can design from scratch. These are different capabilities.
3. **Note dependencies the researcher does not control** — a method that requires unavailable infrastructure is not a strength for planning purposes.
4. **Estimate the level of methodological rigour** visible in the artefact: baselines chosen, controls run, ablation logic.
5. **Translate into planning implications**: which parts of a plan can be delegated and which need support.

## Reasoning Guidance

<!-- 迁移自旧模块提示词；具体推理要点见下方逐字来源。 -->

## Evidence Requirements

Every capability claim must point at a specific artefact location (section, file, figure) that demonstrates it.

## Expected Output

Produce:

- methods with a depth classification each
- external dependencies that limit what can be assumed
- an assessment of methodological rigour with its basis
- planning implications

## Workspace Conventions

If this method reads or writes structured workspace files (evidence/claims/decisions, plans, papers, outputs, LaTeX, literature search/download), follow the exact schemas in this plugin's `reference/` directory rather than improvising a format — see [research-assets.md](../../reference/research-assets.md), [plans.md](../../reference/plans.md), [papers.md](../../reference/papers.md), [outputs.md](../../reference/outputs.md), [latex.md](../../reference/latex.md), [literature-search.md](../../reference/literature-search.md), and [paper-fulltext-download.md](../../reference/paper-fulltext-download.md), whichever applies. The `research` skill's [SKILL.md](../research/SKILL.md) is the usual entry point that pulls the right context together first; if this skill was invoked on its own, check whether a `project.md` or `research-state.md` already exists in the workspace before assuming there is none.

## Reference Prompts

The original, more verbose source prompts this method was distilled from are kept in [reference.md](reference.md) for extra detail when the summary above isn't enough (exact length/format constraints, worked examples, etc).
