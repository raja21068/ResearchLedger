# Storage and database architecture

Status: specification. Phase 0 is done; Phases 1–5 are planned. This document is the contract the storage work is
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

Today an approved script runs on the host as the user's account. The review recommends Docker for every run, with no
network, CPU, memory and time limits, and only the workspace mounted.

I agree with the goal, but I recommend a **pluggable runner** instead of "Docker or nothing":
- **Docker** when it is available, as the default: workspace mounted, `--network none` unless the plan declares a
  download step, resource limits, pinned image.
- **Host** only after an explicit per-run approval that says plainly "runs on this computer without a sandbox".
- `run_log.json` records which runner was used.

Reason: the target user runs on a Windows laptop where Docker Desktop is often absent or heavy. Refusing to run would
push them to run scripts by hand, with no provenance at all. **This is the user's decision.** Until it is made, the
current approval gate stays.

## 9. Phases

| Phase | Content | Done when |
|---|---|---|
| 0 ✅ | provenance freshness in `collect()`; hash-based snapshots with deletions; WAL, indexes, `schema_migrations`; one agent task per project; CI fixes + webapi/frontend CI jobs | 104 webapi tests pass, including the 5 new ones in `test_storage.py` |
| 1 | object store + `blobs/files/file_versions`; atomic upload path; ZIP import into versions with rollback; FK rebuild for `artifacts`; DB moved to `database/` | every write path creates versions; a crash-injection test leaves no partial state |
| 2 | history, compare, restore, rename/move, trash in the API and file panel; dataset records | restore never loses later versions (tests) |
| 3 | per-run staging, base-version tracking, conflict detection, merge UI, leases | two parallel runs on one project never lose a change (test) |
| 4 | automatic verified backups, project export/import, startup journal recovery, integrity audit | restore from backup reproduces every hash |
| 5 | reuse the `researchledger` package's atomic writes, locks and hash-chained run manifests; link files to C/E/R claims and evidence | one provenance implementation, used by both the CLI and the web app |

## 10. Repository hygiene (decision needed)

On the feature branch:
- 61 build files are tracked: `.aux/.log/.bcf/.fls/.pyc` and `__pycache__`;
- so are 8 ZIP archives and 102 files under `Paper/`.

Build outputs should be untracked (`git rm --cached`) and ignored. The `Paper/` folder and the ZIPs are the user's own
material, so whether they stay in the repository, move to a separate branch, or are dropped from the PR is the
user's call. They are left as they are until then.
