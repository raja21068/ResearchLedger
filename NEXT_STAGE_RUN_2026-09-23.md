# Next-stage validation run — 2026-09-23

This continuation advances the project from isolated semantic replays to a complete **tracked revision lifecycle inside ResearchLedger**.

## What was added and executed

For each of the 13 historical semantic-revision cases across nine repositories, the study now runs the old and revised behavior as separate immutable ResearchLedger runs. The old run is frozen as verified evidence supporting a claim, the historical revision supersedes that old evidence through the transaction layer, and the revised run is then attached as replacement evidence and verified.

The lifecycle tested is:

`old tool output -> immutable run -> verified evidence -> supported claim -> historical revision -> old evidence superseded -> claim loses support -> revised tool output -> replacement evidence -> verified -> claim recovered`

The manuscript provenance marker is also moved from the old evidence id to the replacement evidence id, so the paper audit can be checked before revision, after invalidation, and after recovery.

## Executed result

- Historical cases: **13**
- Repositories: **9**
- Old/new output hash changed as expected: **13/13**
- Full ledger lifecycle completed correctly: **13/13**
- Final workspace validation errors: **0 in every case**
- Old state: claim `supported`, paper backed by verified evidence
- After supersession: claim `hypothesis`, old explicit manuscript evidence marker reported stale
- After replacement verification: claim `supported`, manuscript no longer stale when it cites the replacement evidence

Each case has two immutable run manifests, three committed revision journals (old-evidence verification, old-evidence supersession, replacement-evidence verification), artifact hashes, timing fields, and the before/stale/recovered paper-audit state.

Descriptively in this local proxy run, the median transaction-only time from revision request to the safe invalidated state was about **9.6 ms**, and the median recovery bookkeeping time after the revised tool output already existed was about **15.0 ms**. Median old/new proxy tool runs were about **2.9–3.0 s**, dominated by local process/environment capture. These timings are implementation diagnostics only; they are not presented as a Paper2Agent or production performance benchmark.

## Important scientific boundary

This is a **bridge/conformance experiment**, not the final external validation. The executable command is a deterministic `paper_agent_proxy.py` exposing the already-audited historical semantic fixtures. It is not a Paper2Agent-generated MCP server, and the claim/evidence binding is author-constructed rather than produced by blind independent annotators.

The result therefore supports the narrower statement that ResearchLedger can carry an old/new scientific-software semantic change through its own immutable run ledger, evidence state, claim state, transactional invalidation, paper provenance audit, and recovery path without leaving the old explicitly cited evidence admissible.

It does **not** yet support the broader statement that independently generated real paper agents remain scientifically valid under arbitrary upstream revision.

## Annotation tooling added

The blind annotation workflow now supports:

- pairwise scoring;
- round-level aggregation across two annotator directories;
- field-level exact agreement and Jaccard summaries;
- pooled object-level Cohen's kappa;
- adjudication-template generation containing only annotator disagreements, never system predictions or authored gold.

No human labels were fabricated or auto-filled.

## Software validation

The v2.2 build was tested in non-overlapping chunks because a monolithic invocation exceeds the command-time budget in this environment.

| Test group | Result |
|---|---:|
| Models / validator / revision / revision CLI / tracked trajectories / paper validation / validation study | 88/88 |
| Atomic / CLI / CLI errors / environment / evidence / examples / hook / indexer / migration / report | 68/68 |
| Reproduce | 14/14 |
| Runner | 20/20 |
| Skill wiring / trace / workspace | 16/16 |
| **Total** | **206/206** |

`ruff` and `mypy` executables are not installed in this runtime, so no new lint/type-check claim is made.

## Remaining decisive external study

The next step is now narrower and easier to execute because the downstream ledger path is already instrumented:

1. obtain actual old and new repository checkouts;
2. generate/freeze the executable paper-agent package at the old commit;
3. execute pre-specified scientific tasks through that agent and persist outputs/claims;
4. replay the genuine revision and regenerate/re-execute the agent as required by each baseline;
5. give the old/new source, outputs, task context, and object descriptions to two blind annotators;
6. adjudicate disagreements without revealing system predictions;
7. evaluate stale-assertion escape, false invalidation, recovery correctness, selective recomputation, and time-to-safe-state with repository-clustered uncertainty.

The current v2.2 package contains the ledger, trajectory, annotation, and analysis scaffolding needed for that external run.
