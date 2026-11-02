"""SQLite persistence for projects, conversations, runs and append-only run events.

Scientific records (claims, evidence, runs) stay in the existing ResearchLedger
formats inside each project workspace; this store only holds application state.
"""
from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
  id TEXT PRIMARY KEY, title TEXT NOT NULL, description TEXT NOT NULL DEFAULT '',
  domain TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'active',
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS conversations (
  id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
  title TEXT NOT NULL, claude_session_id TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS runs (
  id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
  conversation_id TEXT NOT NULL REFERENCES conversations(id),
  kind TEXT NOT NULL DEFAULT 'claude_code', prompt TEXT NOT NULL, status TEXT NOT NULL,
  provider TEXT NOT NULL, model TEXT, created_at TEXT NOT NULL, started_at TEXT, finished_at TEXT,
  exit_code INTEGER, error TEXT, result_text TEXT, cost_usd REAL, duration_ms INTEGER);
CREATE TABLE IF NOT EXISTS run_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL REFERENCES runs(id),
  ts TEXT NOT NULL, kind TEXT NOT NULL, payload TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS run_events_run ON run_events(run_id, id);
CREATE TABLE IF NOT EXISTS artifacts (
  id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL REFERENCES runs(id),
  project_id TEXT NOT NULL, path TEXT NOT NULL, sha256 TEXT NOT NULL, size INTEGER NOT NULL,
  change TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS activity (
  id INTEGER PRIMARY KEY AUTOINCREMENT, project_id TEXT, ts TEXT NOT NULL,
  kind TEXT NOT NULL, detail TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS schema_migrations (
  version INTEGER PRIMARY KEY, name TEXT NOT NULL, applied_at TEXT NOT NULL);
"""


def _add_project_kind(c: sqlite3.Connection) -> None:
    # 'paper' = a long project with stages; 'quick' = a one-off job (review a PDF, check references, ...).
    if "kind" not in {r[1] for r in c.execute("PRAGMA table_info(projects)")}:
        c.execute("ALTER TABLE projects ADD COLUMN kind TEXT NOT NULL DEFAULT 'paper'")


def _add_indexes(c: sqlite3.Connection) -> None:
    c.executescript("""
CREATE INDEX IF NOT EXISTS conversations_project ON conversations(project_id);
CREATE INDEX IF NOT EXISTS runs_project_status ON runs(project_id, status);
CREATE INDEX IF NOT EXISTS runs_conversation_status ON runs(conversation_id, status);
CREATE INDEX IF NOT EXISTS artifacts_run ON artifacts(run_id);
CREATE INDEX IF NOT EXISTS artifacts_project_path ON artifacts(project_id, path);
CREATE INDEX IF NOT EXISTS activity_project ON activity(project_id, id);
""")


def _add_file_versions(c: sqlite3.Connection) -> None:
    # Content lives in objects/sha256/ (see versions.py); these tables record which path had which content.
    c.executescript("""
CREATE TABLE IF NOT EXISTS blobs (
  sha256 TEXT PRIMARY KEY, size INTEGER NOT NULL, created_at TEXT NOT NULL, verified_at TEXT);
CREATE TABLE IF NOT EXISTS files (
  id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id), path TEXT NOT NULL,
  current_version INTEGER, deleted_at TEXT, mtime REAL, size INTEGER, UNIQUE(project_id, path));
CREATE TABLE IF NOT EXISTS file_versions (
  file_id TEXT NOT NULL REFERENCES files(id), version INTEGER NOT NULL,
  sha256 TEXT NOT NULL REFERENCES blobs(sha256), size INTEGER NOT NULL, author_kind TEXT NOT NULL,
  run_id TEXT REFERENCES runs(id), note TEXT, created_at TEXT NOT NULL, PRIMARY KEY(file_id, version));
CREATE INDEX IF NOT EXISTS file_versions_run ON file_versions(run_id);
CREATE TABLE IF NOT EXISTS audit_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT, project_id TEXT, ts TEXT NOT NULL, actor TEXT NOT NULL,
  action TEXT NOT NULL, detail TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS audit_events_project ON audit_events(project_id, id);
""")


def _backups_and_artifact_fk(c: sqlite3.Connection) -> None:
    c.execute("CREATE TABLE IF NOT EXISTS backups (id TEXT PRIMARY KEY, created_at TEXT NOT NULL, path TEXT NOT NULL, "
              "db_sha256 TEXT NOT NULL, objects INTEGER NOT NULL, verified_at TEXT, reason TEXT)")
    # artifacts.project_id had no foreign key; SQLite can only add one by rebuilding the table. Rows whose project
    # no longer exists are kept in artifacts_orphaned instead of being dropped.
    sql = c.execute("SELECT sql FROM sqlite_master WHERE name='artifacts'").fetchone()[0]
    if "project_id TEXT NOT NULL REFERENCES projects" in sql:
        return
    c.executescript("""
CREATE TABLE artifacts_new (
  id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL REFERENCES runs(id),
  project_id TEXT NOT NULL REFERENCES projects(id), path TEXT NOT NULL, sha256 TEXT NOT NULL, size INTEGER NOT NULL,
  change TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS artifacts_orphaned AS SELECT * FROM artifacts WHERE 0;
INSERT INTO artifacts_orphaned SELECT * FROM artifacts
  WHERE project_id NOT IN (SELECT id FROM projects) OR run_id NOT IN (SELECT id FROM runs);
INSERT INTO artifacts_new SELECT * FROM artifacts
  WHERE project_id IN (SELECT id FROM projects) AND run_id IN (SELECT id FROM runs);
DROP TABLE artifacts;
ALTER TABLE artifacts_new RENAME TO artifacts;
CREATE INDEX IF NOT EXISTS artifacts_run ON artifacts(run_id);
CREATE INDEX IF NOT EXISTS artifacts_project_path ON artifacts(project_id, path);
""")


def _add_memory_store(c: sqlite3.Connection) -> None:
    # Research memory v2 (memory_store.py): typed, sourced, append-only history; FTS5 index for search.
    c.executescript("""
CREATE TABLE IF NOT EXISTS memory_items (
  id TEXT PRIMARY KEY, project_id TEXT REFERENCES projects(id),
  domain TEXT NOT NULL CHECK (domain IN ('literature','decision','experiment','failure','strategy')),
  title TEXT NOT NULL, content TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('proposed','active','needs_review','superseded','rejected')),
  origin TEXT NOT NULL CHECK (origin IN ('system','user','agent')), source_key TEXT UNIQUE,
  confidence TEXT NOT NULL DEFAULT 'unassessed', tags TEXT NOT NULL DEFAULT '[]',
  supersedes TEXT REFERENCES memory_items(id), conflict_with TEXT REFERENCES memory_items(id),
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS memory_items_project ON memory_items(project_id, status, domain);
CREATE TABLE IF NOT EXISTS memory_evidence (
  id INTEGER PRIMARY KEY AUTOINCREMENT, item_id TEXT NOT NULL REFERENCES memory_items(id),
  kind TEXT NOT NULL, ref TEXT NOT NULL, quote TEXT, created_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS memory_evidence_item ON memory_evidence(item_id);
CREATE TABLE IF NOT EXISTS memory_history (
  id INTEGER PRIMARY KEY AUTOINCREMENT, item_id TEXT NOT NULL REFERENCES memory_items(id),
  ts TEXT NOT NULL, actor TEXT NOT NULL, action TEXT NOT NULL, detail TEXT NOT NULL);
CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(item_id UNINDEXED, title, content, tags);
""")


def _add_ledger_links(c: sqlite3.Connection) -> None:
    # Which app record (server run job, pre-registered experiment) became which ledger id (R####, E###, C###).
    c.execute("CREATE TABLE IF NOT EXISTS ledger_links (project_id TEXT NOT NULL REFERENCES projects(id), "
              "kind TEXT NOT NULL, app_ref TEXT NOT NULL, ledger_id TEXT NOT NULL, created_at TEXT NOT NULL, "
              "PRIMARY KEY(project_id, kind, app_ref))")


# Ordered, append-only. Each step must be safe on a database that already has its effect (older databases
# were migrated ad hoc before this table existed). Never edit or reorder a released step; add a new one.
MIGRATIONS = [(1, "projects.kind", _add_project_kind), (2, "query indexes", _add_indexes),
              (3, "file versions", _add_file_versions),
              (4, "backups table, artifacts.project_id foreign key", _backups_and_artifact_fk),
              (5, "research memory v2", _add_memory_store),
              (6, "evidence ledger links", _add_ledger_links)]

TERMINAL_STATES = {"succeeded", "failed", "cancelled"}


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


class Store:
    def __init__(self, path: Path, keep_agent_runs: bool = False):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self._lock = threading.Lock()
        with self.conn() as c:
            # WAL: readers do not block the writer and a crash mid-write cannot corrupt the main file.
            c.execute("PRAGMA journal_mode=WAL")
            c.executescript(SCHEMA)
            done = {r[0] for r in c.execute("SELECT version FROM schema_migrations")}
            pending = [v for v, _, _ in MIGRATIONS if v not in done]
            if pending and c.execute("SELECT COUNT(*) FROM projects").fetchone()[0]:
                # an existing database is about to change shape: keep a copy of it as it was
                bdir = path.parent / "backups"
                bdir.mkdir(parents=True, exist_ok=True)
                out = sqlite3.connect(bdir / f"before-migration-{min(pending)}-{uuid.uuid4().hex[:6]}.sqlite3")
                c.commit()
                c.backup(out)
                out.close()
            for version, name, step in MIGRATIONS:
                if version not in done:
                    step(c)
                    c.execute("INSERT INTO schema_migrations(version, name, applied_at) VALUES (?,?,?)",
                              (version, name, now()))
            ts = now()
            if keep_agent_runs:
                # Claude app bridge: agent tasks live in the queue, not in this process, so a restart loses nothing.
                # A task a worker had claimed goes back to the queue (its claim token was in memory).
                for r in c.execute("SELECT id FROM runs WHERE status='running' AND provider='claude_code_cli'").fetchall():
                    c.execute("UPDATE runs SET status='queued', started_at=NULL WHERE id=?", (r[0],))
                    c.execute("INSERT INTO run_events(run_id,ts,kind,payload) VALUES (?,?,?,?)",
                              (r[0], ts, "status", json.dumps({"text": "Re-queued: the server restarted"})))
                c.execute("UPDATE runs SET status='failed', error='server restarted while run was active', "
                          "finished_at=? WHERE status IN ('queued','running') AND provider!='claude_code_cli'", (ts,))
            else:
                # A process-run task (CLI agent, server experiment run) died with the server: record that honestly.
                c.execute("UPDATE runs SET status='failed', error='server restarted while run was active', "
                          "finished_at=? WHERE status IN ('queued','running')", (ts,))

    @contextmanager
    def conn(self):
        with self._lock:
            c = sqlite3.connect(self.path, timeout=15)  # wait for another process's write instead of failing
            c.row_factory = sqlite3.Row
            c.execute("PRAGMA foreign_keys=ON")
            c.execute("PRAGMA synchronous=NORMAL")  # safe with WAL; fewer fsyncs
            try:
                yield c
                c.commit()
            finally:
                c.close()

    # -- generic helpers --------------------------------------------------
    def one(self, sql: str, args=()) -> dict | None:
        with self.conn() as c:
            row = c.execute(sql, args).fetchone()
            return dict(row) if row else None

    def all(self, sql: str, args=()) -> list[dict]:
        with self.conn() as c:
            return [dict(r) for r in c.execute(sql, args).fetchall()]

    def exec(self, sql: str, args=()) -> int:
        with self.conn() as c:
            return c.execute(sql, args).lastrowid

    # -- domain helpers ---------------------------------------------------
    def log_activity(self, project_id: str | None, kind: str, detail: str) -> None:
        self.exec("INSERT INTO activity(project_id, ts, kind, detail) VALUES (?,?,?,?)",
                  (project_id, now(), kind, detail))

    def add_event(self, run_id: str, kind: str, payload: dict) -> int:
        return self.exec("INSERT INTO run_events(run_id, ts, kind, payload) VALUES (?,?,?,?)",
                         (run_id, now(), kind, json.dumps(payload, ensure_ascii=False)))

    def events_after(self, run_id: str, after: int = 0, limit: int = 500) -> list[dict]:
        rows = self.all("SELECT id, ts, kind, payload FROM run_events WHERE run_id=? AND id>? "
                        "ORDER BY id LIMIT ?", (run_id, after, limit))
        for r in rows:
            r["payload"] = json.loads(r["payload"])
        return rows

    def update_run(self, run_id: str, **fields) -> None:
        cols = ", ".join(f"{k}=?" for k in fields)
        self.exec(f"UPDATE runs SET {cols} WHERE id=?", (*fields.values(), run_id))
        if fields.get("status") in {"succeeded", "failed", "cancelled"}:
            from . import agent_receipts  # every finished agent task leaves a server-written receipt
            agent_receipts.safe_write(self, run_id)
