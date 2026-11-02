"""Storage integrity: result provenance freshness, content-based change detection, migrations, per-project runs."""
import json
import os
import tempfile
import time
from pathlib import Path

from webapi.app import bridge, experiments, workspace
from webapi.app.db import MIGRATIONS, Store, now

LOG = ("| slot_id | metric | unit | dataset | method | value |\n|---|---|---|---|---|---|\n"
       "| s_old | acc | % | d | m | TBD |\n| s_new | acc | % | d | m | TBD |\n")


def _result(root: Path, slot: str, value: float) -> Path:
    p = root / "results" / f"{slot}.json"
    p.parent.mkdir(exist_ok=True)
    p.write_text(json.dumps({"slot_id": slot, "value": value}), encoding="utf-8")
    return p


def test_collect_does_not_attribute_older_results_to_a_new_run():
    root = Path(tempfile.mkdtemp())
    (root / "paper").mkdir()
    (root / "paper" / "experimental_log.md").write_text(LOG, encoding="utf-8")
    old = _result(root, "s_old", 1.0)
    os.utime(old, (time.time() - 3600, time.time() - 3600))  # written an hour before the run
    run_started = now()
    _result(root, "s_new", 2.0)
    out = experiments.collect(root, "run_b", run_started)
    prov = json.loads((root / "results" / "provenance.json").read_text(encoding="utf-8"))
    assert prov["s_new"]["run_id"] == "run_b"
    assert prov["s_old"]["run_id"] is None
    assert any("s_old.json" in i and "before this run" in i for i in out["issues"])


def test_collect_keeps_earlier_provenance_of_unchanged_files():
    root = Path(tempfile.mkdtemp())
    (root / "paper").mkdir()
    (root / "paper" / "experimental_log.md").write_text(LOG, encoding="utf-8")
    p = _result(root, "s_old", 1.0)
    experiments.collect(root, "run_a")
    os.utime(p, (time.time() - 3600, time.time() - 3600))
    experiments.collect(root, "run_b", now())
    prov = json.loads((root / "results" / "provenance.json").read_text(encoding="utf-8"))
    assert prov["s_old"]["run_id"] == "run_a"


def test_diff_snapshot_is_content_based_and_reports_deletions():
    pid = f"prj_snap{int(time.time() * 1000)}"
    root = workspace.project_root(pid)
    (root / "same.txt").write_text("abc", encoding="utf-8")
    (root / "edit.txt").write_text("abc", encoding="utf-8")
    (root / "gone.txt").write_text("x", encoding="utf-8")
    before = workspace.snapshot(pid)
    time.sleep(0.05)
    (root / "same.txt").write_text("abc", encoding="utf-8")   # rewritten, identical content
    (root / "edit.txt").write_text("abd", encoding="utf-8")   # same size, different content
    (root / "gone.txt").unlink()
    (root / "new.txt").write_text("n", encoding="utf-8")
    changes = dict(workspace.diff_snapshot(pid, before))
    assert changes == {"edit.txt": "modified", "gone.txt": "deleted", "new.txt": "created"}


def test_migrations_are_recorded_once_and_wal_is_on():
    path = Path(tempfile.mkdtemp()) / "db.sqlite3"
    Store(path)
    s = Store(path)  # reopening must not re-run or duplicate migrations
    rows = s.all("SELECT version FROM schema_migrations ORDER BY version")
    assert [r["version"] for r in rows] == [v for v, _, _ in MIGRATIONS]
    assert s.one("PRAGMA journal_mode")["journal_mode"] == "wal"
    assert s.one("SELECT name FROM sqlite_master WHERE type='index' AND name='runs_project_status'")


def test_bridge_hands_out_one_task_per_project_at_a_time():
    s = Store(Path(tempfile.mkdtemp()) / "db.sqlite3")
    ts = now()
    for pid in ("prj_a", "prj_b"):
        s.exec("INSERT INTO projects(id,title,created_at,updated_at) VALUES (?,?,?,?)", (pid, pid, ts, ts))
        s.exec("INSERT INTO conversations(id,project_id,title,created_at,updated_at) VALUES (?,?,?,?,?)",
               ("cnv_" + pid, pid, "c", ts, ts))
    for rid, pid, status in [("run_1", "prj_a", "running"), ("run_2", "prj_a", "queued"), ("run_3", "prj_b", "queued")]:
        s.exec("INSERT INTO runs(id,project_id,conversation_id,prompt,status,provider,created_at) "
               "VALUES (?,?,?,?,?,?,?)", (rid, pid, "cnv_" + pid, "p", status, "claude_code_cli", ts))
    got = s.one("SELECT * FROM runs WHERE status='queued' AND provider='claude_code_cli' "
                "AND project_id NOT IN (SELECT project_id FROM runs WHERE status='running' "
                "AND provider='claude_code_cli') ORDER BY created_at LIMIT 1")
    assert got["id"] == "run_3"
    task = bridge.claim(s)
    assert task and task["run_id"] == "run_3"
    assert bridge.claim(s) is None  # run_2 waits: its project already has a running task
