# Continuation validation run — 2026-09-23

This run continued the journal-strength validation work on the uploaded ResearchLedger bundle.

## Executed analyses

- Expanded real-history semantic replay: **13/13 expected semantic changes observed across 9 repositories**.
- Transaction fault injection: **6/6 checks passed**, including rollback at every one of 11 tested entity-write positions and concurrent independent writers.
- Authored structural pilot bootstrap regenerated with repository-clustered resampling.
- Blind annotation packets regenerated for the original 10 source cases. These remain blank study materials and are not evidence of independent agreement.

## Full software test suite

The full test suite was run in chunks because a single monolithic command exceeds the execution environment's command timeout. All 21 test modules were covered.

| Test group | Result |
|---|---:|
| Models / validator / revision / CLI revision | 72/72 |
| Atomic / CLI / CLI errors / environment / evidence / examples / hook / indexer / migration / report | 68/68 |
| Reproduce | 14/14 |
| Runner | 20/20 |
| Skill wiring / trace / paper validation / validation study / workspace | 27/27 |
| **Total** | **201/201** |

## Structural pilot results

The authored 10-event structural pilot still gives: support-set provenance and TRL 10/10 exact impact identification; flat binary edges 6/10; downstream reachability and full rebuild 4/10 exact because they over-invalidate alternative-support cases. Repository-clustered bootstrap gives a median TRL-minus-binary claim-recall difference of 0.40 with 95% bootstrap interval approximately [0.111, 0.700]. The support-set baseline remains identical to TRL on impact identification, so these gains should be attributed to support semantics rather than transactionality.

## Interpretation boundary

This materially strengthens implementation confidence and the real-history connection, but it still does **not** constitute independent external validation. The remaining decisive study is a full old-commit -> executable paper agent -> frozen outputs/claims -> historical correction -> re-execution trajectory with two blind human annotators and adjudication. Those human labels cannot be legitimately manufactured inside this automated run.

## Tooling note

`ruff` and `mypy` executables were not installed in this runtime, so no new lint/type-check result is claimed here.
