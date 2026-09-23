# Updated manuscript — v2.2 journal-validation integration

This revision updates the supplied AutoResearch-Ledger manuscript to reflect the executed ResearchLedger v2.2 validation evidence without extending the claims beyond what the study supports.

## Main changes

- Retitled the manuscript to **“AutoResearch-Ledger: Transactional Revision Integrity for Executable Research Agents.”**
- Rewrote the abstract around the current evidence stack and its external-validity boundary.
- Added **Paper2Agent (Nature, 2026)** to Related Work and explicitly separated executable-tool reliability from persisted scientific-state revision.
- Reframed the confirmatory study around the preregistered minimum of **60 genuine semantic revision events from at least 15 repositories**, with blind independent annotation and repository-clustered uncertainty.
- Updated the evidence hierarchy to distinguish:
  - confirmatory real paper-agent validation (not executed),
  - 13-case tracked historical proxy trajectories,
  - authored structural pilot,
  - local transaction fault injection,
  - mechanism diagnostics,
  - integrated software tests.
- Added the executed 13-case tracked lifecycle:
  - 13/13 historical semantic changes reproduced across nine repositories;
  - 13/13 old/new artifact hashes changed;
  - 13/13 claims followed `supported -> hypothesis -> supported`;
  - 13/13 explicit manuscript uses of superseded evidence were flagged stale and recovered after replacement citation;
  - zero final validation errors in every case;
  - median local transaction-only time to safe state 9.6 ms and recovery bookkeeping 15.0 ms (proxy diagnostic only).
- Added the local transaction evidence: **6/6 checks**, including exact pre-image restoration at **11/11** tested entity-write failure positions.
- Preserved the authored 10-event structural-pilot result and clarified its attribution: support-set provenance already matches full TRL on impact identification, so the logical gain belongs to AND/OR support semantics; transactions contribute atomicity, rollback, recovery, freshness/serialization and auditable history.
- Updated software conformance to **206/206 tests across 22 modules**.
- Corrected all interpretation language so the paper does **not** claim end-to-end validity of real Paper2Agent agents or independent human construct validation.
- Updated the confirmatory evaluation figure to match the preregistered baseline set.
- Updated the Supplement with the tracked-proxy table, v2.2 test inventory, new reproducibility hashes/commands and Paper2Agent comparison row.

## Important remaining boundary

The manuscript still does not report the decisive external experiment: old commit -> generated Paper2Agent MCP (or equivalent real paper agent) -> frozen outputs/claims -> genuine historical correction -> regenerated/re-executed agent -> two blind independent annotators + adjudication. The paper states this explicitly.
