# ResearchLedger OS: combined blueprint

**Date:** 2 November 2026. This document merges two inputs:
- the user's *ResearchLedger OS Architecture Blueprint v1.0*;
- the source-level competitor audit (`docs/COMPETITOR_AUDIT.md`), checked against what the `feature/web-app-paper-studio`
  branch actually contains today.

For each item it says: **built**, **partly built** or **missing**, where it lives, and what to do next. Where the two
inputs disagree, the decision and the reason are stated.

---

## 1. Principle (agreed)

> The GUI is the control plane. The Python research engine and the ResearchLedger evidence layer stay the
> authority on scientific state.

The aim is not more agents. It is research that survives interruptions, remembers what failed, and shows where
every result came from. Automated checks are never presented as proof of correctness, novelty, replication or
publication readiness.

## 2. Competitors: verified facts (2 November 2026)

| System | Exists? | Licence / size | What is worth taking |
|---|---|---|---|
| OpenResearch (`alphaXiv/OpenResearch`) | yes | MIT, ~7.8k★, Rust | experiment **lineage tree** (`parent_experiment_id`), commit hash per run, heartbeat leases, experiments table UI |
| FAROS (`OpenNSWM-Lab/FAROS`) | yes | MIT, ~3k★, Python | **pluggable sandbox**: Docker with `--network none` plus CPU and memory limits, subprocess fallback (`backend/app/code/sandbox/`); workflow declared as a JSON blueprint; evidence gate before drafting |
| Hope Agent (`shiwenwen/hope-agent`) | yes | MIT, ~1.9k★, Rust | **memory as claims** with scope, status (active, superseded, needs review), supersedes link, separate evidence table, review inbox |
| ResearchOS (`Karbo123/ResearchOS`) | yes | **no licence**, 0★, TypeScript + Mastra | ideas only: approvals tab, memory-graph modal. **Its code must not be copied** (no licence = all rights reserved) |
| Hermes Mission Control (`JaimeMarques/hermes-mission-control`) | yes | MIT, 0★ | layout ideas for a mission-control dashboard (kanban, sessions, cron, spend) |
| Hermes Workspace (`outsourc-e/hermes-workspace`) | yes | MIT, ~6.8k★ | the approval store is an empty stub and memory is Markdown files: **not** a reference for approvals |
| myxos (openssi.dev/myxos) | page only | no public code found | the *campaign → run → session* separation, as a concept |
| EvoScientist (arXiv 2603.08127) | paper | — | separate memories for **failed directions** and **reusable execution strategies** |

Star counts are from the GitHub API on the date above. They show visibility, not quality. Two systems in the first
list ("ResearchOS on PGlite", "Hermes Loop") were described with features their code does not have, so every claim
here comes from reading source, not from READMEs.

## 3. Where ResearchLedger stands against the blueprint

| Blueprint item | Status | Where / note |
|---|---|---|
| React GUI, project dashboard, project workspace | **built** | `frontend/` (Next.js): home, `/projects/[id]/home`, Paper Studio, Loops, Quality, Settings |
| FastAPI application boundary | **built** | `webapi/app/main.py` |
| One owner per state | **mostly** | app DB = projects, runs, events; files = object store; Paper Studio stages = `paper/studio.json`; loops = `loops/*/state.json`. **Gap:** the web app does not use the C/E/R ledger (§5, P3) |
| Approval gates | **built** | Decisions inbox, per-stage approve, per-run approval of experiment commands |
| Live updates (SSE) | **built per run** | `/runs/{id}/events`; no project-wide stream yet |
| Runtime adapters: Claude Code | **built** | app bridge + CLI; **Codex: missing** |
| Experiment execution with receipts | **built** | `exprun.py`: one service, approved commands, script SHA-256, exit code, fresh-results check, `run_log.json` |
| Docker isolation for web runs | **missing (decision)** | the CLI's Factory S4 uses Docker; web runs on the host after approval |
| File versions, restore, trash, backups | **built** | `versions.py`, `backup.py`; daily verified backups |
| Workflow task states, recovery | **partial** | restart requeues bridge tasks; no `tasks` table, no `interrupted` or `recovery_required` states |
| Persistent research memory (5 domains) | **built (P1)** | `webapi/app/memory_store.py`, Memory page; `research_memory.md` kept as "Project notes" |
| Failure memory | **built (P1)** | idea scorecards and pre-registered verdicts are recorded automatically and shown to agents |
| Experiment laboratory (tree, compare, repeat) | **partial** | loop rounds and run logs; no lineage, no dataset or environment hash, no repeat-as-new-record |
| Evidence and integrity page | **partial** | Quality page, `results/provenance.json`; not linked to C###/E###/R#### |
| Manuscript + review workspace | **built** | Paper Studio, review↔revise loop, reference check; **missing:** claim-trace side panel |
| Knowledge graph | **missing** | defer until records are stable (agreed) |
| Multi-agent parallel work on one project | **safe but serial** | one agent per project at a time; isolation planned |

## 4. Where the two inputs differ, and the decision

1. **Versioning owner: Git or the object store.**
   - The blueprint makes "project Git repository" the owner of code and manuscript versions.
   - ResearchLedger now has a content-addressed version store that also covers data, PDFs and Word files, and needs
     no Git knowledge from the user.
   - **Decision:** the object store stays the owner, which follows the blueprint's own rule of one owner per state.
     Git is optional, through a "commit this project to Git" export, and OpenResearch-style lineage records a
     code-tree hash rather than a Git commit.
2. **Docker.**
   - The blueprint requires Docker for every experiment. Most Windows laptops don't have it.
   - **Decision:** follow FAROS's pattern. Use the Docker backend (no network, CPU, memory and time limits) when
     Docker is installed, and the host only after an approval that says "no sandbox". Every receipt records which
     runner was used. **This still needs the user's yes.**
3. **Database.** Both inputs say SQLite now and PostgreSQL only when measured concurrency demands it. Agreed. No
   Mastra, no second orchestration framework.
4. **Pause and resume of agents.** The blueprint is right that controls must not be shown unless the runtime supports
   them. Claude Code tasks can be cancelled, not paused, so the GUI must not show a Pause button.

## 5. Combined roadmap (in order)

| # | Work | Takes from | Done when |
|---|---|---|---|
| **P1 ✅** | **Research memory v2** (done 2 Nov 2026: migration 5, `memory_store.py`, `/memory` page, Decisions, 7 tests). Store memories by domain (literature, decision, experiment, failure, strategy). Records look like Hope Agent's claims: scope, status, supersedes link, source run and evidence rows. Failures from idea loops and pilots are fed in automatically. Agents propose memories; the user approves them in Decisions. Agents receive relevant memories, with their sources, in every task. A **Memory** page lets you search, filter, see what replaced what, and see conflicts. `research_memory.md` is generated from the records. | blueprint §6, Hope Agent, EvoScientist | an agent starting a new idea round is shown "certified property range failed E2/E3 because the reference overfits", with a link to the analysis |
| **P2** | **Experiment laboratory.** Add parent links between experiments. Each receipt adds a code-tree hash, a dataset hash, the Python version and package versions. Repeating a run creates a new record. A tree view, compare runs, and a live task list with an execution log (like the *Research Execution* screenshot). | OpenResearch, blueprint §7 p.5 | every number shown links to its run, code hash and data hash |
| **P3** | **Connect to the C/E/R ledger.** Measured slots become `E###` evidence. Claims found in the manuscript become `C###` and are bound to evidence. An Evidence page uses the ledger's own status words (checked, provisional, verified). | blueprint §8, existing `researchledger/` | a manuscript claim opens its evidence chain |
| **P4** | **Mission control.** A `tasks` table (states: queued, running, awaiting_approval, completed, failed, cancelled, interrupted, recovery_required) with heartbeat leases. One page shows every agent and run: role, project, state, elapsed time, last events, logs, cancel. A stage pipeline is drawn like the *Orchestra* screenshot, but only real states and real controls are shown. | myxos (concept), OpenResearch leases, blueprint §10–11 | a server restart shows interrupted work as *interrupted*, never silently gone |
| **P5** | **Runner choice.** A Docker backend following FAROS's pattern, with the host as fallback. | FAROS | needs the user's decision (§4.2) |
| **P6** | **Manuscript side panel.** Next to the draft: sources, sections drafted, how well each claim is supported, *Trace evidence*, and suggested commands (like the *Cite-Agent* screenshot). | blueprint §7 p.6 | each sentence with a number shows its evidence or a warning |
| **P7** | **Knowledge graph view** over the relational records: papers, ideas, experiments, claims, evidence, decisions (like the *Paperoni* screenshot). | blueprint §7 p.7 | every edge opens its source record |
| **P8** | Codex adapter; per-run workspace isolation so agents can work on one project in parallel; then resource scheduling. | blueprint §10.2, OpenResearch worktrees | — |

**Not planned:** PostgreSQL, vector or graph servers, Mastra, remote clusters, multi-user accounts, copying ResearchOS
code.

## 6. Acceptance checks kept from the blueprint

These are kept as written:
- failed experiments remain retrievable;
- conflicting memories are visible;
- memory updates preserve history;
- each run links to its code and configuration;
- interrupted runs are recovered or explicitly marked;
- repeating a run creates a new record;
- existing C/E/R identifiers stay compatible;
- no automated result is labelled publication-ready;
- approval gates cannot be bypassed from the GUI;
- secrets never appear in logs;
- backups can be restored.

Each phase above adds its tests to `webapi/tests/` and runs in CI.
