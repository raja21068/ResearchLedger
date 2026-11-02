"""A server restart must not throw away agent tasks waiting for (or claimed by) the Claude app worker."""
import tempfile
from pathlib import Path

from webapi.app.db import Store, now


def _seed(path: Path):
    s = Store(path)
    ts = now()
    s.exec("INSERT INTO projects(id,title,created_at,updated_at) VALUES ('prj_1','p',?,?)", (ts, ts))
    s.exec("INSERT INTO conversations(id,project_id,title,created_at,updated_at) VALUES ('cnv_1','prj_1','c',?,?)", (ts, ts))
    for rid, status, provider in [("run_q", "queued", "claude_code_cli"), ("run_r", "running", "claude_code_cli"),
                                  ("run_x", "running", "server_exec")]:
        s.exec("INSERT INTO runs(id,project_id,conversation_id,prompt,status,provider,created_at) VALUES (?,?,?,?,?,?,?)",
               (rid, "prj_1", "cnv_1", "p", status, provider, ts))


def test_bridge_restart_keeps_agent_tasks():
    path = Path(tempfile.mkdtemp()) / "db.sqlite3"
    _seed(path)
    s = Store(path, keep_agent_runs=True)
    st = {r["id"]: r["status"] for r in s.all("SELECT id, status FROM runs")}
    assert st == {"run_q": "queued", "run_r": "queued", "run_x": "failed"}
    assert any("server restarted" in e["payload"] for e in s.all("SELECT payload FROM run_events WHERE run_id='run_r'"))


def test_cli_restart_fails_orphans():
    path = Path(tempfile.mkdtemp()) / "db.sqlite3"
    _seed(path)
    s = Store(path)
    assert {r["status"] for r in s.all("SELECT status FROM runs")} == {"failed"}
