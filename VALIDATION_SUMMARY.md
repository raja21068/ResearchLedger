# ResearchLedger v2.2 journal-validation build

## Added since v2.1

This build keeps the v2.1 support-set and transactional revision machinery and adds the next bridge toward external validation:

- ledger-integrated old/new tracked trajectories for all 13 historical semantic-revision cases;
- immutable run capture and artifact hashing for both sides of every trajectory;
- persisted old evidence -> supersession -> replacement-evidence recovery;
- manuscript provenance audit before invalidation, after invalidation, and after recovery;
- a manuscript-evidence scoping fix so recovered claims are not permanently marked stale solely because historical superseded evidence remains in the claim record;
- resumable per-case trajectory checkpoints;
- annotation-round aggregation and adjudication-template generation;
- correction of the RH04 Squidpy narrative (no 0.05 threshold crossing).

## Software validation

The complete local test inventory was run in five non-overlapping batches:

- models / validator / revision / revision CLI / tracked trajectories / paper validation / validation study: **88 passed**;
- atomic / CLI / CLI errors / environment / evidence / examples / hook / indexer / migration / report: **68 passed**;
- reproduce: **14 passed**;
- runner: **20 passed**;
- skill wiring / trace / workspace: **16 passed**.

**Total: 206 passed, 0 failed across 22 test modules.**

`ruff` and `mypy` are not installed in this execution environment, so this build makes no new lint or type-check result claim.

## Real-history semantic evidence

The semantic replay remains **13/13 expected old/new changes across nine repositories**. The cases cover normalization, statistical variance, defaults, calibration, feature subsampling, tokenization, PCA setup, duplicated data, reproducibility under work partitioning, sparse quantile estimation, and BOS-token handling.

These remain narrow semantic replays, not whole-repository reproductions.

## New tracked-trajectory bridge experiment

`validation_study/trajectory_runner.py` executes the old and revised behavior for every historical case as separate ResearchLedger runs and then exercises the complete persisted lifecycle.

Result:

- **13/13** cases produced different old/new artifact hashes;
- **13/13** began with a `supported` claim backed by verified old evidence;
- **13/13** moved to `hypothesis` after the old evidence was transactionally superseded;
- **13/13** manuscript audits explicitly citing the old evidence reported stale usage after supersession;
- **13/13** recovered to a `supported` claim after replacement evidence was verified;
- **13/13** manuscript audits recovered after the provenance marker was changed to the replacement evidence;
- every final workspace had **0 validation errors**.

Each case retains two immutable run manifests, artifact hashes, three committed revision journals, audit snapshots, and timing fields.

The executable is a deterministic paper-agent proxy built from the historical semantic fixtures. It is explicitly not a Paper2Agent-generated MCP. This experiment therefore strengthens implementation integration but does not count as independent end-to-end external validation.

## Transaction evidence

The existing deterministic fault-injection suite remains **6/6**, including exact rollback restoration at **11/11** tested entity-write failure positions, interrupted-transaction recovery, alternative-support preservation, and concurrent independent writers.

## Structural pilot

The authored ten-event dependency-graph pilot remains development evidence:

| System | Exact event match | Claim recall | Claim precision | Claim escape |
|---|---:|---:|---:|---:|
| No revision state | 0.00 | 0.00 | — | 1.00 |
| Full rebuild | 0.40 | 1.00 | 0.625 | 0.00 |
| Downstream reachability | 0.40 | 1.00 | 0.625 | 0.00 |
| Flat binary edges | 0.60 | 0.60 | 1.00 | 0.40 |
| Support-set provenance | 1.00 | 1.00 | 1.00 | 0.00 |
| Full ResearchLedger semantics | 1.00 | 1.00 | 1.00 | 0.00 |

The support-set baseline matching full ResearchLedger on impact identification means those gains belong to support semantics, not transactionality.

## Independent-annotation readiness

The annotation tooling now supports blank-packet generation, pairwise scoring, whole-round aggregation, pooled object-level Cohen's kappa, and adjudication-template generation. The adjudication templates expose annotator disagreements only; they do not include system predictions or authored gold.

No human agreement statistic is claimed because no independent human round has yet been completed.

## Remaining confirmatory boundary

The decisive external study still requires actual old/new repository execution with real paper-agent generation/frozen outputs and two blind independent annotators plus adjudication. The pre-registration continues to require at least 60 revision events from at least 15 repositories, matched-registration and native-registration analyses, strong logical baselines, and repository-clustered uncertainty.
