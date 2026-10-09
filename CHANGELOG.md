## 2.0.1 — Post-release forensic code and packaging audit (2026-10-08)

- Restore missing ResearchLedger hooks, quickstart examples and validation-study fixtures so the complete shipped test suite can execute.
- Reject unsafe Docker mount symlinks (including parent-directory and nested paths).
- Bound isolated-repeat tolerances; reject forged/unsafe comparison settings on subsequent checks.
- Preserve existing repository SHA-256 hashes while switching to streaming, symlink-safe hashing.
- Put new workspaces in a user-writable location by default, with an environment override and legacy-checkout compatibility.
- Validate malformed DOI registry entries explicitly, and clarify that a recorded run is not proof of a successful reproduction.
- Add post-audit regression tests and a detailed audit report, including limitations.

# Release history

## 2.0.0 — Evidence-first integration (2026-10-08)

- Added a mode selector: `exploration` or opt-in `validation`. Older exploration projects retain the v1 execution path.
- Added prospective operator-authored protocol scaffolds and hash-bound protocol/idea/dataset locks, enforced before the manuscript skeleton and experiments in validation mode.
- Added explicit Crossref DOI resolution with bounded responses and tamper-checked metadata receipts; nearest-prior-art matrix with operator acknowledgement.
- Added quantitative claim contracts requiring named metric slots, a population/scope statement, real metric values from the linked S4 ResearchLedger run, and source/receipt hash consistency.
- Added validation-data experiment prompts prohibiting silent synthetic fallback, with required registered seed reporting, dataset-use attestation and measured sample count.
- Added descriptive multi-seed arithmetic checks that reject inconsistent metric aggregates without claiming inferential significance.
- Added isolated repeat of the same generated experiment in restricted Docker, with numeric/series/per-seed comparison and receipt checks. No host execution and no automatic promotion to scientifically verified evidence.
- Added science integrity gates before S5 in validation mode, advisory science audit for all projects, new CLI commands, and stage-scoped checkpoint signatures to permit prospective research records between stages.
- Added regression tests for locks, tampering, metadata spoofing, declared-claim coverage, seed arithmetic, Docker repeat and checkpoint boundaries.

### Not yet implemented

A true experiment-before-draft stage redesign, independent replication by a second implementation, verified literature *findings*, fully automatic review of prose, unbiased statistical inference, leakage classifiers, and a visual monitoring dashboard. See `docs/EVIDENCE_FIRST_V2.md`.

## 1.0.0

First Paper Factory v0.2 + ResearchLedger v2.2 integration with Docker experiment import and tamper-checked evidence ledger.
