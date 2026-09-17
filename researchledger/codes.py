"""The RL-code registry: every validator finding has a stable, documented code.

Numbering: RL0xx schema/id, RL1xx graph edges & constraints, RL2xx artifacts,
RL3xx provenance/status, RL4xx manuscript. See reference/run-ledger.md for the
prose description of each code. `STRICT_ESCALATES` lists warning codes that
become build-failing errors under `validate --strict` (they're deliberately
*not* baseline errors, because they can reflect a deliberate, reviewed
decision rather than a mistake — e.g. a claim still citing evidence that has
since been superseded while a replacement is being written).
"""

from __future__ import annotations

RL001_BAD_ID = "RL001"
RL003_SCHEMA_INVALID = "RL003"
RL004_MALFORMED_RUN_MANIFEST = "RL004"
RL005_MALFORMED_RECORD = "RL005"
RL006_MANIFEST_IDENTITY_MISMATCH = "RL006"

RL101_BROKEN_EDGE = "RL101"
RL102_ASYMMETRIC_EDGE = "RL102"
RL110_EMPIRICAL_CLAIM_WITHOUT_EVIDENCE = "RL110"
RL111_EXPERIMENTAL_EVIDENCE_WITHOUT_RUN = "RL111"
RL112_RUN_WITHOUT_ARTIFACT = "RL112"
RL120_CLAIM_BASED_ON_REJECTED_EVIDENCE = "RL120"

RL201_MISSING_ARTIFACT = "RL201"
RL202_HASH_MISMATCH = "RL202"
RL203_UNSAFE_PATH = "RL203"
RL210_ENVIRONMENT_MISSING = "RL210"
RL211_RUN_FAILED = "RL211"
RL212_MISSING_INPUT = "RL212"
RL213_INPUT_HASH_MISMATCH = "RL213"
RL214_MISSING_METRICS_FILE = "RL214"
RL215_METRICS_HASH_MISMATCH = "RL215"
RL216_MISSING_ENVIRONMENT_FILE = "RL216"
RL217_ENVIRONMENT_DIGEST_MISMATCH = "RL217"
RL220_CHAIN_BROKEN = "RL220"
RL221_LEGACY_UNCHAINED_RUN = "RL221"

RL301_SUPERSESSION_MISMATCH = "RL301"
RL302_SUPERSEDED_DEPENDENCY = "RL302"
RL303_MISSING_REPRODUCTION = "RL303"
RL310_STATUS_DRIFT = "RL310"

RL401_BROKEN_PROVENANCE = "RL401"
RL402_UNSUPPORTED_ASSERTION = "RL402"

# Warning-level codes that flip to error severity under `--strict`.
STRICT_ESCALATES = frozenset({RL302_SUPERSEDED_DEPENDENCY, RL310_STATUS_DRIFT})

DESCRIPTIONS = {
    RL001_BAD_ID: "malformed id",
    RL003_SCHEMA_INVALID: "frontmatter/manifest fails JSON Schema validation (covers status vocabulary too)",
    RL004_MALFORMED_RUN_MANIFEST: "a run's manifest.json exists but could not be parsed at all",
    RL005_MALFORMED_RECORD: "an evidence/claim/decision file exists but could not be parsed at all",
    RL006_MANIFEST_IDENTITY_MISMATCH: "a run's manifest.json run_id does not match its directory name",
    RL101_BROKEN_EDGE: "reference to a nonexistent id",
    RL102_ASYMMETRIC_EDGE: "cross-reference is not mirrored on both sides",
    RL110_EMPIRICAL_CLAIM_WITHOUT_EVIDENCE: "empirical claim has no evidence edge",
    RL111_EXPERIMENTAL_EVIDENCE_WITHOUT_RUN: "experiment/computation evidence has no run edge",
    RL112_RUN_WITHOUT_ARTIFACT: "evidence reports a run that produced no artifacts",
    RL120_CLAIM_BASED_ON_REJECTED_EVIDENCE: "claim's only supporting evidence is contradicted/invalidated",
    RL201_MISSING_ARTIFACT: "manifest-listed artifact is missing on disk",
    RL202_HASH_MISMATCH: "artifact content no longer matches its recorded hash",
    RL203_UNSAFE_PATH: "a manifest-listed artifact path escapes the run directory or is a symlink",
    RL210_ENVIRONMENT_MISSING: "run has no environment.json",
    RL211_RUN_FAILED: "evidence cites a run that did not complete successfully",
    RL212_MISSING_INPUT: "manifest-listed input dataset is missing on disk",
    RL213_INPUT_HASH_MISMATCH: "input dataset content no longer matches its recorded hash",
    RL214_MISSING_METRICS_FILE: "run's recorded metrics.json is missing on disk",
    RL215_METRICS_HASH_MISMATCH: "metrics.json content no longer matches its recorded hash",
    RL216_MISSING_ENVIRONMENT_FILE: "run's recorded environment.json is missing on disk",
    RL217_ENVIRONMENT_DIGEST_MISMATCH: "environment.json content no longer matches environment_digest",
    RL220_CHAIN_BROKEN: "a run's previous_run_hash does not match the prior run's actual manifest",
    RL221_LEGACY_UNCHAINED_RUN: "run predates the tamper-evident chain (no previous_run_hash recorded)",
    RL301_SUPERSESSION_MISMATCH: "supersedes/superseded_by edge is not symmetric",
    RL302_SUPERSEDED_DEPENDENCY: "claim depends on superseded evidence",
    RL303_MISSING_REPRODUCTION: "run-backed evidence has no reproduction note",
    RL310_STATUS_DRIFT: "recorded claim status disagrees with the recomputed status",
    RL401_BROKEN_PROVENANCE: "manuscript provenance marker references a nonexistent id",
    RL402_UNSUPPORTED_ASSERTION: "quantitative manuscript assertion has no provenance marker",
}
