# Storage and database architecture

Status: Phases 0 and 1 are done, Phase 2 is done except dataset records, and Phase 4 is done except project export/import. Phases 3 and 5–7 are planned. This document is the contract the storage work is
built against. It covers the schema, layout, APIs, concurrency, versioning, backup and migration.

## 1. Where we are (checked against the code, November 2026)

ResearchLedger keeps two stores, and that split stays:

- **SQLite** (`webapi_data/researchledger_web.sqlite3`) holds projects, conversations, runs, run events, artifacts and
  activity. It is accessed through `webapi/app/db.py`.
- **The filesystem** (`webapi_data/projects/<project_id>/workspace/`) holds everything a person or agent works on:
  manuscripts, data, code, results, figures and loops.

An external review rated this 4.5/10 as a release candidate. I checked each claim against the source:

| Claim | Verdict | Status |
|---|---|---|
| `snapshot()` uses mtime + size; `diff_snapshot()` misses deletions | true | **fixed in Phase 0** |
| Paper Studio `collect()` credits any existing `results/*.json` to the current run | true | **fixed in Phase 0** |
| No WAL, ad-hoc migrations, few indexes | true | **fixed in Phase 0** (WAL, `schema_migrations`, indexes) |
| Two runs in different conversations of one project can edit the same files | true | **mitigated in Phase 0** (one agent task per project at a time); full isolation is Phase 3 |
| `artifacts.project_id` has no foreign key | true | Phase 1 (needs a table rebuild) |
| One global Python lock serialises all DB access | true | kept for now (one process, SQLite writes are serial anyway); revisit in Phase 1 |
| No file versions, trash, rename/move, backups | true | Phases 2 and 4 |
| Experiment scripts run on the host, not sandboxed | true | see §8; this is a design decision for the user |
| The standalone `researchledger` package has stronger provenance (atomic writes, locks, hash-chained manifests) | true | Phase 5: the web app should reuse it, not duplicate it |
| CI: V5 tests miss `requests`; Windows `researchctl --help` crashes on `→` | true | **fixed in Phase 0** (`referee` extra; console-safe output) |
| CI does not run `webapi/tests` or the frontend typecheck/build | true | **fixed in Phase 0** (two new jobs) |

## 2. Principles

1. **Never lose a version.** Every content a file has had, and that a run or a person wrote, is kept by its SHA-256
   until the user empties the trash or a retention rule they set removes it.
2. **The database records relationships and history. The object store keeps content. The workspace is the working
   copy.** Any one of the three can be rebuilt from the other two, plus the journal.
3. **Agents propose, the user (or a rule the user set) merges.** No agent writes straight into the shared working copy
   once Phase 3 lands.
4. **Results count only if their provenance holds.** A result is tied to the run that wrote it, the code version, the
   inputs and the exit code. This is already true for the experiment loop and, after Phase 0, for Paper Studio
   `collect()`.
5. **Local-first.** Keep SQLite and plain files. No server database, no cloud dependency.

## 3. Directory layout (target)

```
webapi_data/
  database/
    researchledger.sqlite3        (moved from webapi_data/ by migration; old path kept as a fallback for one release)
    backups/                      (SQLite online backups, rotated)
  objects/sha256/ab/cdef...       (immutable content, written once, read-only)
  projects/<project_id>/
    workspace/                    (the working copy: unchanged layout, so existing paths keep working)
    staging/<run_id>/             (Phase 3: an agent's private copy and its proposed changes)
    trash/                        (Phase 2: metadata only; content stays in objects/)
  journal/                        (write-ahead intent records for multi-step file operations)
  logs/
```

The workspace sub-folders (`paper/`, `code/`, `data/`, `results/`, `figures/`, `loops/`, `memory/`) stay as they are.
Renaming them would break every engine prompt, so the review's suggested folder names are not adopted.

## 4. Schema (target; additive migrations only)

The existing tables stay. New tables:

```sql
CREATE TABLE blobs (                 -- one row per distinct content
  sha256 TEXT PRIMARY KEY, size INTEGER NOT NULL, created_at TEXT NOT NULL,
  verified_at TEXT);                 -- last integrity audit
CREATE TABLE files (                 -- logical file = a path inside a project
  id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
  path TEXT NOT NULL, current_version INTEGER, deleted_at TEXT,
  UNIQUE(project_id, path));
CREATE TABLE file_versions (
  file_id TEXT NOT NULL REFERENCES files(id), version INTEGER NOT NULL,
  sha256 TEXT NOT NULL REFERENCES blobs(sha256), size INTEGER NOT NULL,
  author_kind TEXT NOT NULL,         -- user | agent | server_exec | restore
  run_id TEXT REFERENCES runs(id), note TEXT, created_at TEXT NOT NULL,
  PRIMARY KEY(file_id, version));
CREATE TABLE run_inputs  (run_id TEXT NOT NULL REFERENCES runs(id), file_id TEXT NOT NULL REFERENCES files(id),
                          version INTEGER NOT NULL, PRIMARY KEY(run_id, file_id));
CREATE TABLE run_outputs (run_id TEXT NOT NULL REFERENCES runs(id), file_id TEXT NOT NULL REFERENCES files(id),
                          version INTEGER NOT NULL, change TEXT NOT NULL, PRIMARY KEY(run_id, file_id));
CREATE TABLE leases (                -- Phase 3: who may write where
  project_id TEXT NOT NULL REFERENCES projects(id), scope TEXT NOT NULL,   -- '*' or a path prefix
  run_id TEXT NOT NULL REFERENCES runs(id), expires_at TEXT NOT NULL, PRIMARY KEY(project_id, scope));
CREATE TABLE datasets (
  id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id), file_id TEXT REFERENCES files(id),
  source_url TEXT, doi TEXT, license TEXT, citation TEXT, original_name TEXT,
  imported_at TEXT NOT NULL, notes TEXT);
CREATE TABLE audit_events (id INTEGER PRIMARY KEY AUTOINCREMENT, project_id TEXT, ts TEXT NOT NULL,
                           actor TEXT NOT NULL, action TEXT NOT NULL, detail TEXT NOT NULL);
CREATE TABLE backups (id TEXT PRIMARY KEY, created_at TEXT NOT NULL, path TEXT NOT NULL,
                      db_sha256 TEXT NOT NULL, objects INTEGER NOT NULL, verified_at TEXT);
```

- `artifacts` becomes a view over `run_outputs` joined with `file_versions`. The old table is kept read-only for
  history.
- `artifacts.project_id` gets its foreign key through the standard SQLite rebuild: create the new table, copy, drop,
  rename, all inside one migration transaction.

**Migrations** (`schema_migrations`, introduced in Phase 0):
- Steps are numbered, append-only, and safe to re-run on a database that already has their effect.
- A step never edits or reorders an earlier one.
- Before any step that rebuilds a table, the server takes an online backup (`sqlite3.Connection.backup`).

## 5. Versioning algorithm

**Write path:** `storage.write(project, path, bytes, author, run_id)`.
1. Hash the content. If `objects/sha256/<h>` is missing, write it to a temp file in the same folder, `fsync`, then
   `os.replace` it into place and make it read-only.
2. In one transaction:
   - upsert the `blobs` row;
   - get or create the `files` row;
   - if the current version already has this hash, stop (no-op);
   - otherwise insert a `file_versions` row (version + 1) and set `current_version`.
3. Write the working copy atomically (temp file + `os.replace`).
4. A journal record written before step 1 and removed after step 3 makes the operation restartable. On startup, any
   leftover journal entry is either completed or rolled back. Both are safe, because objects are immutable and the
   DB step is one transaction.

**Agent and process writes** happen outside this API (Claude Code edits files directly). They are captured after the
run:
- the hash-based `diff_snapshot()` from Phase 0 lists created, modified and deleted files;
- each change becomes a `file_versions` row with `author_kind = agent` and the run id;
- a deletion becomes `files.deleted_at`.

So history is complete even for writes the server did not perform.

**Other operations:**
- **Restore** version k: write its blob as a new version with `author_kind = restore`. Later versions are never
  removed.
- **Rename/move:** update `files.path` in one transaction and move the working copy, with an `audit_events` row.
- **Trash:** set `deleted_at` and remove the working copy; the blob stays. Emptying the trash deletes only blobs that
  no remaining version references.

Uploads replace today's `.v1/.v2` suffix renames: a re-upload is simply a new version of the same path.

## 6. Concurrency model

- **Phase 0 (done):** one agent task per project at a time, in both executors.
  - Bridge `claim()` skips queued runs whose project already has a running agent task.
  - The CLI executor takes a per-project lock.
  - Queued work waits; nothing is rejected.
- **Phase 3 (isolation):**
  - Each agent run gets `staging/<run_id>/`, a copy of the workspace at start (hard links where the OS allows, since
    objects are immutable), plus a record of the base version of every file (`run_inputs`).
  - When the run ends, its changes are computed against that base.
  - **Merge** a changed file automatically if its current version still equals the base version. If not, it is a
    conflict: the user sees both versions side by side and picks one or edits. Text files get a three-way merge
    proposal.
  - Leases are optional fences for long tasks, for example "the writing agent owns `paper/`". A lease held by another
    run makes a merge into its scope wait, never fail silently.
  - With isolation in place, the one-task-per-project rule can be relaxed so loops in the same project run in
    parallel.
- **Database:** WAL mode, `busy_timeout` 15 s and `synchronous=NORMAL` (Phase 0). The global Python lock remains
  until Phase 1 moves to one connection per thread with short transactions.

## 7. Backup, export and integrity

- **Automatic backup** on server start and daily:
  - an SQLite online backup into `database/backups/`, plus the list of object hashes;
  - the last 14 are kept;
  - each is verified by reopening it and running `PRAGMA integrity_check`.
- **Project export:** a zip with the project's DB rows (JSON), its working copy and the objects of all versions, plus
  a manifest with every hash. **Import** re-hashes everything before accepting it.
- **Integrity audit** (on demand, and weekly):
  - re-hash a sample of objects (all of them on request);
  - check that every DB path exists and every working-copy file has a current version row;
  - report orphans. It never deletes automatically.

## 8. Executing experiment code (decision needed)

There are three ways experiment code runs today, and they do not share one boundary:

| Path | How it runs | Approval | Provenance |
|---|---|---|---|
| Factory S4 (`factory/`) | Docker | CLI workflow | run manifests in `researchledger/` |
| Experiment loop (`webapi/app/exprun.py`) | host Python, `subprocess.Popen` | user click per run | `run_log.json`: script hash, exit code, fresh-results check |
| Paper Studio "Run experiments" stage | the agent itself runs `python` (CLI mode grants `Bash(python:*)` and `pip install`; in bridge mode the Claude app worker runs it) | stage approval only, after the fact | `collect()` with the run-start freshness check (Phase 0) |
| **now (Phase 6):** Paper Studio "Run experiments" | the execution service runs `code/jobs.json` on the host | user approves the listed commands before they run | `run_log.json`; only slots measured by that run are entered |

A second review said Paper Studio "cannot run Python because its tools are LaTeX-only". That is not accurate:
`claude_runner.EXTRA_TOOLS_BY_KIND` grants Python and pip to `paper:experiments`. The real problem is the one in the
table: the agent executes code outside the experiment loop's approval gate and run log.

**Target: one execution service.**
- Factory, Paper Studio and the experiment loops all submit a job: script path, arguments, declared inputs, expected
  result slots and a time limit.
- The service runs it in the chosen runner, captures inputs, outputs, hashes and the exit code, and is the only path
  that may write `results/`.
- Paper Studio's experiment stage then writes and plans code, but submits runs instead of executing them.

**Runner choice.** Today an approved script runs on the host as the user's account. The review recommends Docker for every run, with no
network, CPU, memory and time limits, and only the workspace mounted.

I agree with the goal, but I recommend a **pluggable runner** instead of "Docker or nothing":
- **Docker** when it is available, as the default: workspace mounted, `--network none` unless the plan declares a
  download step, resource limits, pinned image.
- **Host** only after an explicit per-run approval that says plainly "runs on this computer without a sandbox".
- `run_log.json` records which runner was used.

Reason: the target user runs on a Windows laptop where Docker Desktop is often absent or heavy. Refusing to run would
push them to run scripts by hand, with no provenance at all. **This is the user's decision.** Until it is made, the
current approval gate stays.

### Versions as built (Phase 1)

- **What is versioned:** every workspace file up to 64 MB, except LaTeX build files. Larger files are listed but not
  copied, which is the known gap for big datasets.
- **Disk use:** the first time a project is synced, every file is copied once into `objects/`. After that, only new
  content is stored, and identical contents are shared.
- **Attribution:**
  - before a run, changes made outside any run are saved as `external`;
  - after it, changes are saved as `agent` or `server_exec` with the run id;
  - only one agent task runs per project (Phase 0), so a change in that window belongs to that run. Edits made by
    hand during a run are the one exception: they are attributed to the run too.
- **Deletions:** a deleted file is marked `deleted_at`, its content stays, and Restore brings it back.

## 9. Workflow state and memory

**Workflow state today:**
- SQLite holds runs and events;
- JSON files hold loop state and Paper Studio state;
- Markdown holds memory;
- background threads drive the loops.

None of this is wrong in itself, but nothing owns the lifecycle. **Target:** a `tasks` table as the one authority for
every unit of work (agent turn, loop move, experiment job, Director step).
- **Record:** id, kind, parent, state, inputs, outputs, attempt, lease and checkpoint.
- **Loop and Paper Studio JSON** stay as *views* of task results, so the files remain readable by people and engines.
- **Recovery:** on restart, every non-terminal task is resumed or re-queued from its checkpoint. This already happens
  for bridge tasks.
- **Retries:** idempotent by task id. A move that already wrote its outputs is never run twice.

**Memory.** `memory/research_memory.md` stays as the readable summary. Underneath it, a small typed store
(`memory_items`) holds:
- kind: fact | assumption | decision | failed_approach | source_claim;
- the source (run, file, DOI);
- status: active | superseded | contradicted;
- links to C/E/R ledger ids.

The Markdown is generated from these items. No vector database; SQLite FTS5 is enough for search at this scale.

## 10. The five contracts

These are adopted from the review, and the phases above implement them:
1. Every agent task is structured and carries explicit permissions.
2. Every execution has a persistent id, state, inputs and outputs (the `tasks` table, plus `run_inputs` and
   `run_outputs`).
3. Every artifact has a verifiable origin and version (`file_versions`).
4. Every reported result traces to a real execution or a named external source (the execution service, `collect()`
   freshness, the C/E/R ledger).
5. Every important workflow survives an interruption (journal plus task checkpoints).

## 11. Phases

| Phase | Content | Done when |
|---|---|---|
| 0 ✅ | provenance freshness in `collect()`; hash-based snapshots with deletions; WAL, indexes, `schema_migrations`; one agent task per project; CI fixes + webapi/frontend CI jobs; honest agent registry | 105 webapi tests pass, including the 6 in `test_storage.py` |
| 1 ✅ | object store + `blobs/files/file_versions/audit_events` (migration 3, `webapi/app/versions.py`); versions captured before and after every agent run (CLI and bridge), server experiment run and upload; re-uploads become versions instead of `.v1` copies; ZIP import is all-or-nothing (limits checked first, unpacked in a temp folder, files it overwrites saved first); `artifacts.project_id` foreign key (migration 4; rows of missing projects kept in `artifacts_orphaned`); an automatic database copy before any migration. **Not done, by decision:** moving the DB to `database/` (no safety gain, breaks existing setups) and a separate write-ahead journal (every write is already object-first then one DB transaction, so a crash leaves at most an unreferenced object, which the integrity check reports) | 13 tests in `test_versions.py`; migration 4 tested on a copy of the live database (86 of 86 artifacts kept) |
| 2 (mostly ✅) | history, view, restore, side-by-side compare, rename/move (history moves with the file) and a Trash page; restore and rename are refused while an agent works in the project, and unsaved edits are saved first. **Left:** dataset records (source, DOI, licence) | restore never loses later versions (tested) |
| 3 | per-run staging, base-version tracking, conflict detection, merge UI, leases | two parallel runs on one project never lose a change (test) |
| 4 (mostly ✅) | automatic verified database backups (at start-up if older than a day, then daily, last 14 kept; `webapi/app/backup.py`), Back up now, and a read-only integrity check that re-hashes saved versions (Settings → Backups and safety check). **Left:** project export/import | a damaged stored version is detected (tested) |
| 5 | reuse the `researchledger` package's atomic writes, locks and hash-chained run manifests; link files to C/E/R claims and evidence | one provenance implementation, used by both the CLI and the web app |
| 6 (execution ✅) | **done:** one execution service (`exprun.py`) for the experiment loop and Paper Studio: Paper Studio's Run experiments stage no longer starts an agent; it runs `code/jobs.json` (checked: python scripts under `code/`, declared slots, ≤30 min) after the user approves the commands on screen, installs `code/requirements.txt` as a required first job, and only slots that run measured enter the paper; agents get no Python permission. **Left:** Factory S4 (CLI, Docker) still has its own runner; the Docker/host choice (§8) waits for the user; the `tasks` table with checkpoints (§9) | a results file not written by the recorded run is never entered (tested) |
| 7 | typed memory items behind `research_memory.md` (§9); cross-project search with FTS5 | a superseded decision is never shown as current |

Phase 0 also corrected the agent registry: the Research Director was listed as "planned" although
`webapi/app/director.py` implements it. A test now fails if an "integrated" entry points at missing code, or a
"planned" entry has an implementation.

**Not planned now:** PostgreSQL, Redis, Kubernetes, vector databases and more agents. None of them fixes the problems
above.

## 12. Repository hygiene (decision needed)

On the feature branch:
- 61 build files are tracked: `.aux/.log/.bcf/.fls/.pyc` and `__pycache__`;
- so are 8 ZIP archives and 102 files under `Paper/`.

Build outputs should be untracked (`git rm --cached`) and ignored. The `Paper/` folder and the ZIPs are the user's own
material, so whether they stay in the repository, move to a separate branch, or are dropped from the PR is the
user's call. They are left as they are until then.
