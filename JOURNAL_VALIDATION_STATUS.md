# Journal-validation status — v2.2

## Current evidence level

ResearchLedger now has four explicitly separated evidence layers:

| Layer | Current status | What it supports |
|---|---|---|
| Formal/implementation conformance | **206/206 tests passed** in non-overlapping chunks | Support-set logic, transaction protocol, provenance audit behavior, tracked-trajectory scaffolding, and the rest of the tested implementation behave as specified locally |
| Real-history semantic replay | **13/13** expected changes across **9 repositories** | The study is tied to genuine historical scientific-software revisions rather than only synthetic graph mutations |
| Ledger-integrated tracked proxy trajectories | **13/13** old/new output changes and **13/13** complete invalidation/recovery lifecycles | Old outputs can be frozen as immutable runs/evidence, superseded transactionally after revision, and replaced with revised evidence while manuscript provenance recovers |
| Transaction fault injection | **6/6** checks; **11/11** write-position rollback trials | Local multi-file revision commits, rollback, crash recovery, and lock serialization behave as designed under the tested fault model |
| Independent construct validation | **Not yet executed** | Still required before claiming that independent annotators agree with the registered real research dependencies |
| Full Paper2Agent old/new trajectory replay | **Not yet executed** | Still required before claiming end-to-end protection of actual executable paper-agent outputs |

## What changed in v2.2

The main new experiment is no longer only a formula/configuration replay. Each of the 13 historical semantic cases is now passed through the ResearchLedger lifecycle as two separate immutable runs. The old result is attached to verified evidence and a supported claim, the historical revision supersedes that evidence through the transaction layer, and the corrected output is attached as new evidence and verified. All 13 trajectories reach the expected safe and recovered states.

This is a stronger implementation-level bridge to the final study, but the executable tool remains a deterministic **paper-agent proxy**, not a Paper2Agent-generated MCP server. The claim/evidence binding is also authored by the study, not independently annotated.

## Provenance-audit correction

A recovered claim can legitimately retain superseded evidence in its history. The paper audit therefore no longer treats the mere presence of any historical superseded evidence as permanently stale when a live verified replacement exists. When a manuscript marker explicitly cites `evidence=E###`, that exact evidence is still audited: explicitly citing a superseded record remains stale until the marker is changed to the replacement evidence.

This behavior is directly exercised by the 13 tracked trajectories.

## Data-quality correction retained

The RH04 Squidpy Geary fixture changes the analytic p-value from approximately **0.0444 to 0.0209**. Both values are below 0.05. The corrected materials describe this as a material inferential-calibration shift, **not** a threshold crossing.

## Publication claim supported by the current bundle

A restrained claim is:

> We implemented AND/OR support-set revision semantics and an application-level multi-file revision transaction in ResearchLedger. Across thirteen narrow replays of genuine historical scientific-software revisions from nine repositories, the changed semantics were observable locally. When these old/new behaviors were executed as separate immutable ResearchLedger runs, all thirteen trajectories correctly moved from verified old evidence and a supported claim, through supersession of the old evidence and loss of claim support, to verified replacement evidence and a recovered claim. In separate authored structural tests, support-set semantics avoided the constructed over- and under-invalidation errors of reachability and flat binary baselines. Under deterministic local fault injection, the transaction layer restored exact pre-images at all eleven tested entity-write failure positions and recovered an interrupted transaction.

Do **not** extend this to “therefore real paper agents remain scientifically valid under revision.” The full Paper2Agent old/new replay and independent human adjudication needed for that statement have not been run.

## Interpretation decomposition

The structural pilot still shows that support-set provenance without transactions reaches the same 10/10 impact-identification result as the full transactional condition on the authored graph cases. Therefore:

- AND/OR support semantics explain selective logical invalidation;
- transactions explain atomic multi-file state revision, rollback, crash recovery, freshness/serialization, and auditable history;
- end-to-end protection additionally depends on dependency registration and assertion binding quality;
- the tracked proxy study verifies that these mechanisms compose in the implemented ResearchLedger lifecycle, but it does not independently validate the upstream dependency graph.

## Next decisive external study

1. Select at least 15 repositories and at least 60 genuine semantic revision events for the confirmatory sample.
2. Freeze the old commits and generate/execute real paper-agent tools on pre-specified tasks.
3. Persist the old outputs and claims in ResearchLedger.
4. Replay the historical corrections and regenerate/re-execute as required by each baseline.
5. Give source/diff, old/new outputs, task context, and object descriptions to two blind annotators; adjudicate disagreements without exposing system predictions.
6. Evaluate matched-registration and native-registration conditions separately.
7. Report stale-assertion escape, false invalidation, recovery correctness, selective recomputation, and time-to-safe-state with repository-clustered uncertainty.

The v2.2 bundle now contains the trajectory runner, resumable per-case checkpoints, blind-packet generator, agreement aggregation, and adjudication-template tooling needed to carry out that study once actual paper-agent checkouts/packages and human annotators are available.
