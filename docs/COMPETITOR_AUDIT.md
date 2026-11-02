# Competitor audit: what to adopt from systems similar to ResearchLedger

Checked on 2 November 2026 by reading each project's **source code** through the GitHub API (read-only; nothing was
downloaded or run). This audit started from an AI-written list of competitors, so first: what exists.

## 1. Which of the suggested systems are real

| Suggested | What I found | Audited? |
|---|---|---|
| **OpenResearch** | Real: `alphaXiv/OpenResearch`, MIT, Rust + React, about 7.8k stars, active (last push 31 Oct 2026) | yes |
| **Hope Agent** | Real: `shiwenwen/hope-agent`, MIT, Rust/Tauri, about 1.9k stars, active | yes (memory) |
| **"Hermes Loop"** | No project by that name. The nearest is **Hermes Workspace** (`outsourc-e/hermes-workspace`, MIT, about 6.8k stars), a GUI for Hermes Agent | yes, as a stand-in |
| **"myxos"** | Only a description on the OpenSSI project page. No public repository found (GitHub repos named myxos are unrelated OS course projects) | no: no code to read |
| **"ResearchOS" (Mastra + PGlite)** | Not found. Several unrelated "ResearchOS" repos exist; none uses Mastra or PGlite | no |
| **EvoScientist** | Real paper, arXiv 2603.08127 (March 2026) | design only, from the paper |

Treat the earlier list's capability claims for the unconfirmed systems as unverified. Two of its claims were wrong
for the systems that do exist (see Hermes Workspace below).

## 2. What each one actually does (from the code)

### OpenResearch: the closest direct competitor
- **Storage:** one SQLite file (`orx.db`) in WAL mode with a busy timeout (`src/store.rs`). Migrations are a list of
  `ALTER TABLE` statements whose errors are ignored ("duplicate column" means already applied), plus
  `PRAGMA user_version` for a few steps.
  - ResearchLedger's numbered `schema_migrations` table with a backup before each upgrade is stricter.
- **Experiments are git branches:** `local_experiments` has `branch_name`, `run_command` and **`parent_experiment_id`**,
  so experiments form a **lineage tree**. Each run records its **`commit_sha`**, `exit_code`, `result_markdown` and
  logs. Code history is git; there is no separate file-version store.
- **Leases:** `chat_turn_leases(claim_token, heartbeat_at)` and a data-directory move lease. This is the same idea as
  ResearchLedger's bridge claim tokens, but with a heartbeat instead of a fixed 15-minute timeout.
- **Execution backends:** local, SSH, Slurm, Kubernetes, Modal, Ray, Hugging Face Jobs, and its own managed compute
  (`src/jobs/`). Local runs are plain processes with cancel and log streaming. I found no sandbox in
  `src/jobs/localbox.rs`.
- **GUI:** experiment table, experiment lineage view, run banner, artifacts tab
  (`ui/src/components/ExperimentLineage.tsx`, `ExperimentsTable.tsx`, `ArtifactsTab.tsx`).
- **Not there:** paper writing, peer review, claim/evidence ledger, novelty checks.

### Hope Agent: the best memory design found
- **Memory as claims** (`crates/ha-core/src/memory/claims/types.rs`). Each claim has:
  - **scope:** global, agent or project;
  - **type:** project fact, standing rule, reference, preference, task pattern, and so on;
  - subject–predicate–object;
  - confidence and its source: derived, adjusted by the model, or confirmed by the user;
  - **status:** active, superseded, expired, archived or *needs review*;
  - `supersedes_claim_id`, validity dates and `source_run_id`.
- **A separate evidence table:** source type (message, file, tool result, URL, manual), an evidence class (from
  "user confirmed" down to "assistant inferred"), and a short quote.
- **A review inbox for conflicting claims,** and **"dreaming":** periodic consolidation that promotes or merges
  memories. It uses SQLite with FTS5 and vector search.

### Hermes Workspace (the "Hermes Loop" stand-in)
- **Approvals are a stub.** `src/lib/approvals-store.ts` begins "Stub — exec approvals are not used in Hermes
  Workspace" and every function is a no-op. The claimed "human approval workflows" are not there.
- **Memory is plain Markdown files** written under the workspace (`src/routes/api/memory/write.ts`, `.md` only).
- **Useful:** scheduled jobs with pause and resume (`src/lib/jobs-api.ts`), and a swarm and Kanban view of workers.
  It works as a general agent cockpit, not as a reference for research provenance.

### EvoScientist (paper)
- **Three roles:** a researcher agent, an engineer agent, and an evolution manager that, after each task, writes two
  persistent memories:
  - **ideation memory:** promising *and failed* research directions;
  - **experimentation memory:** reusable execution strategies.
- **Reported result:** an ablation where experiment success rates rose after this "evolution". These are the authors'
  figures; not checked here.

## 3. Side by side (ResearchLedger after today's work)

| Capability | ResearchLedger | OpenResearch | Hope Agent | Hermes Workspace |
|---|---|---|---|---|
| Database | SQLite, WAL, numbered migrations, backup before upgrade, daily verified backups | SQLite, WAL, ignore-error migrations | SQLite + FTS5 + vectors | backend's |
| File history | content-addressed versions, compare, restore, trash | git commits per experiment branch | n/a | none found |
| Experiment execution | one service, approval per run, script hash, fresh-results check | many backends, no sandbox found | general tools | general |
| Experiment lineage | loop rounds, no parent links between experiments | **parent experiment tree + commit per run** | — | — |
| Parallel agents per project | one at a time (safe), isolation planned | **one git worktree per experiment** | sessions | swarm workers |
| Research memory | `research_memory.md` + run summaries | SQL record of experiments | **typed claims, evidence, review inbox** | Markdown files |
| Failed-idea memory | outcomes exist (loop attacks, pilot verdicts) but are not reused | — | — | — |
| Claim/evidence ledger, paper writing, peer review, novelty checks | **yes** | no | no | no |
| Approvals | per stage, per experiment run | — | permission modes | **stub** |

## 4. What to adopt, and what not to (my recommendation)

**Adopt:**
1. **Hope Agent's claim model for research memory** (planned as Phase 7):
   - a `memory_items` table with scope (project or global), type (fact, decision, standing rule, *failed approach*,
     source claim), status (active, superseded, needs review), `supersedes`, `source_run_id`;
   - a separate evidence table pointing to files, runs, DOIs and the C/E/R ledger;
   - `research_memory.md` becomes generated from it, and conflicts go to the existing Decisions inbox.
2. **EvoScientist's failed-direction memory, fed automatically.** ResearchLedger already produces exactly this data:
   - every idea-loop attack and score;
   - every pre-registered pilot verdict (for example today's: "certified property range" failed E2 and E3 because
     the reference overfits).
   - Record them as `failed_approach` items so the next idea round reads them instead of repeating them.
3. **OpenResearch's experiment lineage.** Add `parent_experiment` to experiment loops, record a code-tree hash for
   each run (the file-version store already has every file's hash), and show a tree view. This is a small change with
   high value for "what led to what".
4. **Heartbeat leases** instead of the fixed 15-minute stale timeout for bridge tasks. Today's pilot showed the cost:
   a long install made a claimed task go stale and requeue.

**Do not adopt:**
- **PostgreSQL, a vector database or a knowledge-graph server.** Both real competitors that run locally (OpenResearch,
  Hope Agent) use SQLite, and Hope Agent gets search from FTS5. Nothing here needs a server database.
- **Remote compute backends** (Slurm, Kubernetes, Modal). They are out of scope for laptop-scale research.
- **Hermes-style approvals.** There is nothing to copy; ResearchLedger's gates are already real.
- **Copying another GUI wholesale.** ResearchLedger's distinctive parts (ledger, review, novelty, paper stages) have no
  counterpart in these systems.

## 5. Suggested order

| # | Work | Why first |
|---|---|---|
| 1 | Research memory v2: typed items + evidence, auto-fed with failed directions from loops and pilots | biggest gap versus the best design found; the data already exists |
| 2 | Experiment lineage: parent links, code hash per run, tree view | small, makes results traceable across attempts |
| 3 | Heartbeat leases for agent tasks | fixes a failure seen today |
| 4 | Per-run workspace isolation (Phase 3), possibly via git worktrees like OpenResearch | needed before running agents in parallel on one project |

Sources: [OpenResearch](https://github.com/alphaXiv/OpenResearch) ·
[Hope Agent](https://github.com/shiwenwen/hope-agent) ·
[Hermes Workspace](https://github.com/outsourc-e/hermes-workspace) ·
[EvoScientist, arXiv 2603.08127](https://arxiv.org/abs/2603.08127) · [OpenSSI (myxos mention)](https://openssi.dev/)
