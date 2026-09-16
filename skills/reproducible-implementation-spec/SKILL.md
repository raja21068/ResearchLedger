---
name: reproducible-implementation-spec
description: "Turn a settled design into implementation requirements precise enough that an independent run reproduces the numbers: pinned environment, controlled randomness, deterministic data handling, complete configuration, and a fixed artefact layout. Use when The design is settled and code must be written by a person or a coding agent; or when Results exist but cannot be regenerated from the repository and its documentation; or when A baseline or component must be reimplemented faithfully rather than approximately."
---

# Reproducible Implementation Specification

> Ported from the ConvFusion research-skill library (category: `experiment`; origin: experiment/method, experiment/dataset, experiment/analysis). Ask/answer using this method whenever it applies to the current research workspace.

## Purpose

Turn a settled design into implementation requirements precise enough that an independent run reproduces the numbers: pinned environment, controlled randomness, deterministic data handling, complete configuration, and a fixed artefact layout.

## When to Use

Use this skill when:

- The design is settled and code must be written by a person or a coding agent.
- Results exist but cannot be regenerated from the repository and its documentation.
- A baseline or component must be reimplemented faithfully rather than approximately.

## Research Method

1. **Freeze the environment.** Record language and runtime, framework and library versions or a lockfile, hardware assumptions, and external data or pretrained checkpoints with their identifiers. Latest version is not a specification.
2. **Make randomness explicit and controlled.** Enumerate every stochastic source — shuffling, splitting, initialisation, dropout, sampling, augmentation, library defaults — and require one seed to control all of them, so a run is reproducible per seed and varied deliberately across seeds.
3. **Specify deterministic data handling.** Load from pinned sources, preprocess deterministically, store split assignments instead of recomputing them differently each run, and ensure caching never silently changes the data.
4. **Specify the training and evaluation contract.** Entry points, config schema, metric computation, checkpoint selection rule, and output layout: one run directory per method, config and seed, containing config, log, metrics and predictions. A rerun must not depend on mutable state left by earlier runs.
5. **Require smoke tests and fail-loud behaviour.** A short subset run before the full run, assertions on data shapes, splits and metric ranges, and hard failure on missing data or diverging loss instead of silent fallback. Any simulated or fallback result must be flagged in the artefacts, never mixed with real runs.
6. **Verify by re-execution, not by inspection.** Reproduction means a clean checkout plus the documented command regenerates the reported metrics within a stated tolerance. Record that comparison, including any deviation, as the reproducibility evidence.

## Reasoning Guidance

<!-- 迁移自旧模块提示词；具体推理要点见下方逐字来源。 -->

## Evidence Requirements

Pinned dependency versions, exact commands, seeds, config files, checkpoint identifiers and per-run metric logs. The artefact layout must let a third party map every reported number to a run directory, and any rerun that fails to match must be reported with the observed difference rather than dropped.

## Expected Output

Produce:

- environment and lockfile specification with hardware assumptions
- seed and determinism policy covering every stochastic source
- deterministic data pipeline requirements
- run-directory layout, config schema, smoke-test and fail-loud requirements
- re-execution comparison record with tolerances and deviations

## Workspace Conventions

If this method reads or writes structured workspace files (evidence/claims/decisions, plans, papers, outputs, LaTeX, literature search/download), follow the exact schemas in this plugin's `reference/` directory rather than improvising a format — see [research-assets.md](../../reference/research-assets.md), [plans.md](../../reference/plans.md), [papers.md](../../reference/papers.md), [outputs.md](../../reference/outputs.md), [latex.md](../../reference/latex.md), [literature-search.md](../../reference/literature-search.md), and [paper-fulltext-download.md](../../reference/paper-fulltext-download.md), whichever applies. The `research` skill's [SKILL.md](../research/SKILL.md) is the usual entry point that pulls the right context together first; if this skill was invoked on its own, check whether a `project.md` or `research-state.md` already exists in the workspace before assuming there is none.

## Reference Prompts

The original, more verbose source prompts this method was distilled from are kept in [reference.md](reference.md) for extra detail when the summary above isn't enough (exact length/format constraints, worked examples, etc).
