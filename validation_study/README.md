# Journal-validation study bundle

This directory contains the empirical scaffolding for testing **revision integrity** in ResearchLedger. It is intentionally split into mechanism/conformance evidence, real-history semantic replay, and materials that require independent human annotation. The distinction matters: no result in this directory should be described as independent external validation until the blind packets have been annotated by people who did not author the ledger graphs and until full old/new executable trajectories have been run.

## What has been executed here

### Real-history semantic replay

`results/prr_executed_semantic_replay_v2.json` contains **13 historical semantic revisions across 9 repositories**. For each case, the narrow changed behavior documented by the upstream commit is replayed locally. All 13 show the expected old/new semantic change.

The original ten cases cover POP-TOOLS, Scanpy, Squidpy, TabPFN, SAELens, Compass, scvi-tools, and Seurat. Three additional cases broaden the failure modes:

- **RH11 Squidpy permutation reproducibility:** the old chunk-local RNG makes later permutations depend on work partitioning; the revised per-permutation `SeedSequence` design is invariant to the tested one-vs-two-chunk split.
- **RH12 scikit-learn sparse QuantileTransformer:** on the upstream regression fixture, the installed pre-fix path creates a degenerate quantile vector for the 501-nonzero sparse column; patching only the historical commit's `_sparse_fit` logic restores a non-degenerate estimate using 500 nonzero samples.
- **RH13 SAELens BOS token 0:** the old truthiness check treats BOS id `0` as absent, while the revised explicit `None` check preserves the token.

These are **semantic replays**, not whole-repository reproductions. The `replay_mode` field on every case states whether the replay is direct code, configuration, numeric formula, package-runtime-plus-patch, or another narrower form.

A supplemental PyMC underflow diagnostic is stored separately and is **not counted** among the 13 executed old/new cases because the installed PyMC/ArviZ combination cannot import cleanly in this container.


### Ledger-integrated tracked proxy trajectories

`results/tracked_trajectory_proxy.json` adds a bridge experiment over the same 13 historical semantic cases. Each old and revised behavior is executed as a separate immutable ResearchLedger run with artifact hashes. The old run is frozen as verified evidence supporting a claim, then transactionally superseded when the historical revision is introduced. The revised run becomes replacement evidence and is verified, recovering the claim and the manuscript provenance audit.

Result: **13/13 old/new artifact hashes differ and 13/13 trajectories complete the expected supported -> hypothesis -> supported lifecycle with zero final validation errors.**

This remains a conformance/bridge result. The executable command is `paper_agent_proxy.py`, a deterministic wrapper around the semantic fixtures, not a Paper2Agent-generated MCP server. The claim/evidence binding is study-authored rather than independently annotated.

The per-case workspaces under `tracked_trajectory_workspaces/` retain the immutable run manifests and revision journals. `trajectory_runner.py` uses per-case result checkpoints so interrupted execution can resume without re-running completed cases.

### Transaction fault injection

`results/transaction_fault_injection.json` executes six checks against the new multi-file revision transaction. All six pass:

1. ordinary two-entity commit reaches `committed`;
2. a forced failure on the second entity write restores exact pre-image hashes and marks the transaction `rolled_back`;
3. a simulated process crash in `applying` is recovered from the journal and restores the pre-image;
4. loss of one alternative support path leaves a claim `supported` when another sufficient path remains;
5. an 11-file transaction is faulted at **every entity-write position (11/11)** and every trial restores all original file hashes;
6. two independent revision CLI processes launched concurrently both commit, leaving both evidence/claim pairs in the expected final states.

This supports a claim about the implemented **application-level transaction protocol under the tested local fault model**. It is not a distributed-database durability claim and does not establish behavior under storage-device failure, network partitions, or hostile writers.

### Authored structural pilot and bootstrap

`results/prr_real_history_pilot.json` is the earlier 10-event structural pilot with authored gold graphs. `results/repository_clustered_bootstrap.json` provides repository-clustered bootstrap summaries for that pilot. These uncertainty intervals describe the **authored pilot only**; they are not independent external-validation confidence intervals.

A useful result from the structural pilot is that the AND/OR support-set baseline and the full transactional model are identical on impact identification (10/10 exact), while flat binary edges miss conjunctive dependencies and downstream reachability over-invalidates alternative support. That means the manuscript should attribute impact-identification gains to support semantics, and test the transaction layer separately using rollback/freshness/recovery evidence such as the fault-injection study above.

## Independent-annotation materials

`annotation_packets/` contains blind packets that omit gold labels and system predictions. They are designed for two independent annotators plus adjudication. The current packets are study materials only; **no human agreement or adjudicated gold result exists yet**.

The final external-validation study should report, separately, agreement and adjudicated labels for dependency existence, dependency type, support-group membership, claim impact, and assertion impact.

## Remaining work before a high-level-journal claim

The highest-value missing experiment is a true trajectory replay:

`old commit -> executable paper agent -> frozen outputs/claims -> historical correction -> revised agent/re-execution -> independently adjudicated impact`

For a journal-scale study, expand beyond the pilot to approximately 15–30 repositories and 60–100+ revision events, pre-specify the primary comparisons, and report repository-clustered uncertainty. Include a full-rebuild baseline, reachability provenance, flat binary dependencies, an AND/OR/ATMS-or-Boolean-provenance-style baseline, and the transactional system. Primary endpoints should include stale-assertion escape, false invalidation, recovery correctness, and selective recomputation cost.

## Reproduce the local analyses

From the repository root:

```bash
PYTHONPATH=. python validation_study/analysis/expanded_semantic_replay.py
PYTHONPATH=. python validation_study/analysis/transaction_fault_injection.py
PYTHONPATH=. python validation_study/trajectory_runner.py   # cached/resumable after first execution
python validation_study/analysis/bootstrap_repository_clustered.py
PYTHONPATH=. python validation_study/annotation_tool.py generate
PYTHONPATH=. pytest -q tests/test_models.py tests/test_validator.py tests/test_revision.py tests/test_cli_revision.py tests/test_tracked_trajectory.py
```

The full repository test suite was executed successfully in chunks: **206/206 tests passed** across all 22 test modules. A monolithic invocation exceeds this environment's per-command time limit because some historical runner/reproduction tests intentionally wait or retry, so the suite was partitioned without omitting test modules.
