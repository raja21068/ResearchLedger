# Referee Lean v2 — Implementation Report

## Implemented

- Added a selectable `lean` pipeline while preserving `legacy` for A/B testing.
- CLI defaults to `--pipeline lean`; programmatic `ReviewConfig()` remains legacy-default for backward compatibility.
- Lean initial review uses exactly seven stages:
  1. `L01_ingest`
  2. `L02_core_review`
  3. `L03_targeted_evidence`
  4. `L04_targeted_specialists`
  5. `L05_hard_evidence_gate`
  6. `L06_independent_verify`
  7. `L07_finalize`
- Scientific reasoning is reduced to three roles: Core Reviewer, reusable Specialist Executor, and Independent Verifier.
- Steelmanning moved out of the generator and into the independent verifier.
- Literature search is driven by bounded questions emitted by the core reviewer; no separate literature-planning LLM is required in Lean mode.
- Specialist agents are replaced by one reusable executor that dynamically loads existing skill families.
- Red-team, separate steelman, disagreement, independent-trajectory consensus, repeatability, pairwise priority and journal-calibration calls are removed from the Lean default path.
- Major-concern ranking is deterministic (`claim centrality × verifier-adjusted confidence`).
- Finalization introduces no new scientific concerns.

## Preserved hard safeguards

- Manuscript content remains untrusted data.
- Runtime-owned canonical IDs for claims, anchors and concerns.
- Exact manuscript-anchor integrity checking.
- Opened-content requirement for decisive external evidence.
- Independent citation identity/proposition verification.
- Fail-closed handling of unresolved external verification.
- Minimum-resolution and closure-criterion requirements.
- Independent verifier identity/context separation.
- Frozen manuscript/claim/anchor/concern hashes for admitted concerns.
- Global invariant validation before final review export.
- Checkpoints, provenance artifacts, benchmark corpus, mutation/evaluation infrastructure and legacy pipeline.

## Compatibility

Non-initial workflows (revision, rebuttal, meta-review, editorial screen, reproducibility mode) continue to use the mature legacy DAG in this release. Lean v2 focuses on the initial scientific review path first so it can be benchmarked cleanly before the same reduction is applied to other modes.

## Validation performed for this package

- Python compileall: passed.
- Full bundled pytest suite: passed (60 test files; all tests pass).
- Added Lean v2 end-to-end smoke test: passed.
- Package validator: passed.
- Evidence-lock deterministic eval: 5/5 passed.
- Runtime/source scientific assets: synchronized.
- Package manifest and SHA-256 checksums: rebuilt.
- Validation release manifest: refrozen as `Referee-Validation-v2-lean`.

## Scientific-performance caveat

These checks establish software integrity and preservation of the evidence-lock invariants. They do **not** establish that Lean v2 has higher scientific-review precision/recall/F1 than the legacy Referee, CMU Paper Reviewer, Stanford Agentic Reviewer, or human experts. The next scientific validation step is an A/B benchmark of `--pipeline lean` versus `--pipeline legacy` on the same real-paper expert benchmark.
