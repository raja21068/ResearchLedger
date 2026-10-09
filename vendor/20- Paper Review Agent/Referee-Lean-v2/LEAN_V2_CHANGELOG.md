# Referee Lean v2 — Change Log

- Added selectable `lean` and `legacy` scientific pipelines.
- Lean is the new default for initial review.
- Reduced default initial-review DAG from 22 stages to 7.
- Reduced standing scientific reasoning roles to Core Reviewer, Specialist Executor, and Independent Verifier.
- Moved steelman generation to the independent verifier.
- Replaced default red-team, disagreement, trajectory, reliability, pairwise-ranking and journal-calibration passes with deterministic or optional behavior.
- Preserved fail-closed anchor verification, external citation verification, frozen-hash verification, provenance, checkpoints, validation harnesses, benchmark corpora and legacy path.
- Added Lean v2 prompts and architecture documentation.
- Non-initial review modes continue to use the legacy DAG for backward compatibility in this release.
