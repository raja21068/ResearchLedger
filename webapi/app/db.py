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
"""

TERMINAL_STATES = {"succeeded", "failed", "cancelled"}


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


class Store:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self._lock = threading.Lock()
        with self.conn() as c:
            c.executescript(SCHEMA)
            # A server restart orphans any in-flight run: record that honestly.
            c.execute("UPDATE runs SET status='failed', error='server restarted while run was active', "
                      "finished_at=? WHERE status IN ('queued','running')", (now(),))

    @contextmanager
    def conn(self):
        with self._lock:
            c = sqlite3.connect(self.path)
            c.row_factory = sqlite3.Row
            c.execute("PRAGMA foreign_keys=ON")
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
