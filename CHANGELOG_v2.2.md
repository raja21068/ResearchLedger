# ResearchLedger v2.2 development changelog

- Preserved v2.1 AND/OR claim support sets and transactional evidence revision.
- Added a ledger-integrated tracked-trajectory bridge experiment: all 13 historical semantic cases now execute old and revised behavior as separate immutable ResearchLedger runs, bind old outputs to verified evidence/claims, supersede old evidence, then recover the claim with revised verified evidence.
- Added a deterministic `paper_agent_proxy.py` used only for the bridge experiment. It is explicitly not a Paper2Agent-generated MCP server.
- Added `trajectory_runner.py` with resumable per-case checkpoints and result aggregation.
- Added manuscript-provenance recovery semantics: a claim that retains superseded historical evidence is no longer permanently flagged stale after new live verified evidence replaces it; explicit `evidence=...` markers still flag a specifically cited superseded record.
- Added annotation-round aggregation and adjudication-template generation without exposing system predictions or authored gold.
- Corrected the RH04 Squidpy Geary replay narrative: p changes from ~0.0444 to ~0.0209, but both values are below 0.05; the case is a material calibration shift, not a threshold crossing.
- Expanded the complete local test inventory to **206/206 passing tests** across 22 test modules, executed in non-overlapping chunks.
- Kept the evidence boundary explicit: tracked proxy trajectories strengthen ledger integration/conformance but do not replace full old/new repository + Paper2Agent trajectories or independent human annotation.
