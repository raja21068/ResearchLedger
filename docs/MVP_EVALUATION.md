# ResearchLedger OS MVP: four-week evaluation

**Decision this document serves:** keep expanding the web app, or stop. It follows the user's MVP advice (2 Nov
2026):
- build only four modules: workspace, agent control, provenance-aware memory, experiment tracking;
- test them on **one real research project** from idea to manuscript review;
- stop expanding if the GUI does not make research measurably easier than the CLI workflow.

**Until the trial ends, no new modules are built.** P5 (Docker runner), P6 (manuscript side panel), P7 (knowledge
graph) and P8 (Codex, parallel agents) wait. Bug fixes found during the trial are allowed.

## The MVP as built (2 Nov 2026)

| Module | Where |
|---|---|
| Research workspace | website: projects, 7-step pipeline, Paper Studio, files with versions/trash/backups |
| Agent control | Mission control (`/mission`), Decisions inbox, Claude app bridge with automatic heartbeat |
| Research memory | Memory page; failed ideas and pre-registered verdicts recorded automatically with sources |
| Experiment tracking | Experiments page (`/projects/{id}/lab`): receipts, fingerprints, compare, repeat; Evidence page (C/E/R ledger) |

## The six criteria: test and honest baseline

| Criterion (user's) | How it is tested during the trial | Baseline today (before the trial) |
|---|---|---|
| **Workflow coordination**: can manage a complete research project through the GUI | The trial project goes idea → paper search and score → pilot → experiments → paper → review **without typing a command**, except starting the server and `/rl-worker`. Every time a terminal command is needed, it is logged below as a gap. | **Not shown yet.** The drug-discovery idea went from idea to pilot, but steps were driven from this console. No paper has gone end to end through the GUI since the new modules. |
| **Agent visibility**: every running task has inspectable status and logs | During the trial, spot-check every task in Mission control: does it show its state, its last report and a way to open its full log? Count tasks without. | Mission control shows state, the last report and heartbeat for every run. **Gap:** for app-worker tasks, the "log" is what the worker reports (steps, summary), not a full transcript. |
| **Memory retrieval**: relevant previous decisions with source references | At the start of each new idea round, check that the agent's output **mentions** the earlier failures listed on the Memory page (e.g. "certified property range failed E2/E3"). Count rounds where a recorded failure was repeated without comment. | Memories exist with sources (5 for the drug project). **Not yet observed** whether agents actually use them: no agent round has run since memory v2. |
| **Experiment traceability**: every displayed result links to its run and artifacts | Every number in the trial paper's experimental log must open to its receipt (Experiments page) and its sealed run (Evidence page). Count numbers without. | New runs: receipt + sealed run + evidence. **Gap:** the pilot predates fingerprints (shown as "before fingerprints"); a Repeat would give it a full receipt. |
| **Recovery**: interrupted workflows can resume safely | Once during the trial, restart the server while a task runs. Expected: shown as interrupted (server runs) or re-queued (agent tasks); nothing duplicated or silently lost; work resumes from its page. | Restart requeues agent tasks and marks server runs interrupted. **Gap:** no checkpoint *inside* a task; an interrupted agent task starts its step again from the beginning. |
| **Maintenance**: existing tests and invariants intact | Every change during the trial keeps all suites green. | Web app 138 passed; ledger 209 passed; CLI tests pass except 10 Windows-only symlink tests that also fail without these changes. The ledger validator received 2 documented fixes (RL110/RL120 on withdrawn and contradicted claims). |

## Comparison with the CLI workflow

Measured from records, not impressions:
- **Time:** wall-clock per stage, from `runs.created_at` → `finished_at`, plus the time waiting for the user (Decisions).
- **Interventions:** the number of terminal commands needed (gap log below).
- **Repeats avoided:** idea rounds where a recorded failure was cited and avoided, against rounds that repeated one.
- **Traceability:** the share of paper numbers linked to a run and receipt.

The DeFi paper (Paper Studio, mostly before these modules) is the reference point. Its numbers were not traced to
sealed runs.

## Trial project

The paused C5 idea ("How big should a molecular fingerprint be? Data-size-aware fingerprint budgets for ADMET") in
the drug-discovery project. It is laptop-sized, has a 63-paper search started, and directly reuses the pilot's
lesson. Path:
1. Paper search
2. Score
3. Redesign or pass
4. Pilot (pre-registered)
5. Full experiments
6. Paper Studio
7. Review → revise

## Gap log (fill during the trial)

| Date | Step | What needed the terminal or failed | Fixed? |
|---|---|---|---|
| 2 Nov | start | Agent tasks run only while an app worker polls. The C5 search had been re-queued twice (silent for 15 minutes each time) before the trial started, so a third silence would have failed it. Here I acted as the worker from this console. | not fixed: needs a connected `/rl-worker` session, or the CLI executor |
| 2 Nov | claiming | One claim was lost between two commands (the task was re-queued), and had to be claimed again. Cause not found. | open |
| 2 Nov | C5 round 1 | Paper search, score and redesign all ran through the loop's own state machine and were accepted by the server's checks. The competitor list has 46 verified papers, below the 50 the plan asks for; the shortfall is stated in the attack. | n/a |
| 2 Nov | memory use | The redesign read `memory/remembered.md` and applied the locality pilot's lessons (validate on a known answer; state a falsifier). This is one observation, made by the agent writing this log, so it counts as weak evidence for the memory criterion. | n/a |

## Stop rule

After four weeks:
- **Continue** the GUI if the trial paper reached review through the GUI, with at most a handful of terminal steps,
  and every paper number traced to a run.
- **Stop expanding** (keep only maintenance) if the trial needed the console for most steps, or if traceability or
  memory reuse did not happen in practice.
