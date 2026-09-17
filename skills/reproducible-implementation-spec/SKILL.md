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

1. **Freeze the environment.** Record language and runtime, framework and library versions or a lockfile, hardware assumptions, and external data or pretrained checkpoints with their identifiers. Latest version is not a specification. `researchledger run` (see below) captures most of this automatically per run — Python version, installed packages, CPU/GPU/driver/CUDA info, a content digest of the whole environment record — but a lockfile and checkpoint identifiers are still yours to pin; the run capture verifies what actually ran, it doesn't substitute for specifying what should.
2. **Make randomness explicit and controlled.** Enumerate every stochastic source — shuffling, splitting, initialisation, dropout, sampling, augmentation, library defaults — and require one seed to control all of them, so a run is reproducible per seed and varied deliberately across seeds. Pass the declared seed to `researchledger run --seed <n>` so it's recorded in the manifest — this records *intent*, it does not itself seed anything; the implementation must still actually apply the seed to every enumerated source.
3. **Specify deterministic data handling.** Load from pinned sources, preprocess deterministically, store split assignments instead of recomputing them differently each run, and ensure caching never silently changes the data. If the input dataset itself needs to be pinned (not just the code), pass it to `researchledger run --data <path>` (repeatable, file or directory) — it gets content-hashed into the manifest, so a silently-changed dataset shows up as a validation failure (`RL213`) instead of a silent discrepancy.
4. **Specify the training and evaluation contract.** Entry points, config schema, metric computation, checkpoint selection rule, and output layout: one run directory per method, config and seed, containing config, log, metrics and predictions. A rerun must not depend on mutable state left by earlier runs. **Don't hand-roll this layout** — `researchledger run -- <command>` already provides it: an immutable `research/runs/R<NNNN>/` with `manifest.json`, `environment.json`, `command.txt`, `stdout.log`/`stderr.log`, and a `metrics.json`/`artifacts/` the command writes into via `$RESEARCHLEDGER_RUN_DIR`/`$RESEARCHLEDGER_ARTIFACTS_DIR`. Specify the command and what it must write there, not a competing directory scheme.
5. **Require smoke tests and fail-loud behaviour.** A short subset run before the full run, assertions on data shapes, splits and metric ranges, and hard failure on missing data or diverging loss instead of silent fallback. Any simulated or fallback result must be flagged in the artefacts, never mixed with real runs. A run that fails outright is still worth capturing as a run (`researchledger run` records its non-zero exit code and logs) — don't discard the record just because the attempt failed.
6. **Verify by re-execution, not by inspection.** Reproduction means a clean checkout plus the documented command regenerates the reported metrics within a stated tolerance. Record that comparison, including any deviation, as the reproducibility evidence. Do this by actually running `researchledger reproduce <run_id>` — it checks out the run's exact git commit into an isolated worktree, re-executes, and reports `REPRODUCED ✓`/`✗` per metric against the stated tolerance; add `--repeat N` when the metric has real run-to-run noise, so the comparison is against the observed spread, not one arbitrary rerun. Quote its output as the reproducibility evidence — don't paraphrase "it should reproduce" from reading the code.

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

**This skill's whole point is executed by the `researchledger` CLI, not just described by it** — see [run-ledger.md](../../reference/run-ledger.md) for the full command reference, the run-manifest schema, and the reproduction algorithm. If `research/runs/` doesn't exist yet, run `Bash researchledger init` first. Once a run produces the numbers a claim needs, hand off to `evidence-assessment`/`researchledger evidence create` to turn it into a linked evidence record — this skill's job stops at "the run is captured and reproducible," not at writing the evidence file.

## Reference Prompts

The original, more verbose source prompts this method was distilled from are kept in [reference.md](reference.md) for extra detail when the summary above isn't enough (exact length/format constraints, worked examples, etc).
