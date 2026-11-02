"""File versions: uploads, agent runs, edits on disk and deletions are all kept; restore never loses later versions."""
import time

from fastapi.testclient import TestClient

from webapi.app import versions, workspace
from webapi.app.main import app, store

H = {"x-rl-client": "test"}
client = TestClient(app)


def _project():
    return client.post("/api/v1/projects", json={"title": "Versions"}, headers=H).json()["id"]


def _upload(pid, name, data):
    r = client.post(f"/api/v1/projects/{pid}/files", headers=H, files={"file": (name, data, "text/markdown")})
    assert r.status_code == 201, r.text
    return r.json()


def _history(pid, path):
    return client.get(f"/api/v1/projects/{pid}/files/history", params={"path": path}).json()


def test_reupload_keeps_the_earlier_version_and_no_v1_copies():
    pid = _project()
    assert _upload(pid, "notes.md", b"first")["version"] == 1
    assert _upload(pid, "notes.md", b"second")["version"] == 2
    h = _history(pid, "uploads/notes.md")
    assert [v["version"] for v in h["versions"]] == [2, 1] and h["current_version"] == 2
    assert not (workspace.project_root(pid) / "uploads" / "notes.v1.md").exists()
    old = client.get(f"/api/v1/projects/{pid}/files/version", params={"path": "uploads/notes.md", "version": 1})
    assert old.status_code == 200 and old.content == b"first"


def test_restore_adds_a_new_version_and_keeps_later_ones():
    pid = _project()
    _upload(pid, "a.md", b"one")
    _upload(pid, "a.md", b"two")
    r = client.post(f"/api/v1/projects/{pid}/files/restore", json={"path": "uploads/a.md", "version": 1}, headers=H)
    assert r.status_code == 200 and r.json()["current_version"] == 3
    assert (workspace.project_root(pid) / "uploads" / "a.md").read_bytes() == b"one"
    h = _history(pid, "uploads/a.md")
    assert [(v["version"], v["author_kind"]) for v in h["versions"]] == [(3, "restore"), (2, "user"), (1, "user")]
    # restoring is itself undoable: version 2 is still there
    client.post(f"/api/v1/projects/{pid}/files/restore", json={"path": "uploads/a.md", "version": 2}, headers=H)
    assert (workspace.project_root(pid) / "uploads" / "a.md").read_bytes() == b"two"


def test_edits_on_disk_are_saved_before_a_restore():
    pid = _project()
    _upload(pid, "b.md", b"v1")
    p = workspace.project_root(pid) / "uploads" / "b.md"
    time.sleep(0.02)
    p.write_bytes(b"edited by hand")
    client.post(f"/api/v1/projects/{pid}/files/restore", json={"path": "uploads/b.md", "version": 1}, headers=H)
    contents = [client.get(f"/api/v1/projects/{pid}/files/version",
                           params={"path": "uploads/b.md", "version": v["version"]}).content
                for v in _history(pid, "uploads/b.md")["versions"]]
    assert b"edited by hand" in contents


def test_sync_records_agent_changes_and_deletions_with_the_run():
    pid = _project()
    root = workspace.project_root(pid)
    (root / "paper").mkdir()
    (root / "paper" / "main.tex").write_text("draft", encoding="utf-8")
    (root / "paper" / "old.tex").write_text("old", encoding="utf-8")
    versions.sync(store, pid, "external")
    ts = time.strftime("%Y-%m-%dT%H:%M:%S")
    conv = client.post(f"/api/v1/projects/{pid}/conversations", json={}, headers=H).json()
    store.exec("INSERT INTO runs(id,project_id,conversation_id,prompt,status,provider,created_at) "
               "VALUES ('run_vtest',?,?,'p','running','claude_code_cli',?)", (pid, conv["id"], ts))
    time.sleep(0.02)
    (root / "paper" / "main.tex").write_text("draft, revised by the agent", encoding="utf-8")
    (root / "paper" / "old.tex").unlink()
    out = versions.sync(store, pid, "agent", "run_vtest")
    assert out == {"saved": ["paper/main.tex"], "deleted": ["paper/old.tex"]}
    h = versions.history(store, pid, "paper/main.tex")
    assert h["versions"][0]["author_kind"] == "agent" and h["versions"][0]["run_id"] == "run_vtest"
    gone = versions.history(store, pid, "paper/old.tex")
    assert gone["deleted_at"] and gone["versions"][0]["sha256"]  # content still kept
    assert versions.object_path(gone["versions"][0]["sha256"]).read_bytes() == b"old"
    # a deleted file can be brought back
    versions.restore(store, pid, "paper/old.tex", 1)
    assert (root / "paper" / "old.tex").read_text(encoding="utf-8") == "old"
    assert versions.history(store, pid, "paper/old.tex")["deleted_at"] is None


def test_unchanged_files_are_not_versioned_twice_and_build_files_are_skipped():
    pid = _project()
    root = workspace.project_root(pid)
    (root / "x.md").write_text("same", encoding="utf-8")
    (root / "main.aux").write_text("aux", encoding="utf-8")
    versions.sync(store, pid, "external")
    assert versions.sync(store, pid, "external") == {"saved": [], "deleted": []}
    assert len(versions.history(store, pid, "x.md")["versions"]) == 1
    assert versions.history(store, pid, "main.aux")["versions"] == []


def test_restore_is_refused_while_an_agent_works_in_the_project():
    pid = _project()
    _upload(pid, "c.md", b"1")
    conv = client.post(f"/api/v1/projects/{pid}/conversations", json={}, headers=H).json()
    store.exec("INSERT INTO runs(id,project_id,conversation_id,prompt,status,provider,created_at) "
               "VALUES ('run_busy',?,?,'p','running','claude_code_cli','2026-01-01T00:00:00')", (pid, conv["id"]))
    r = client.post(f"/api/v1/projects/{pid}/files/restore", json={"path": "uploads/c.md", "version": 1}, headers=H)
    assert r.status_code == 409
    store.exec("UPDATE runs SET status='cancelled' WHERE id='run_busy'")


def test_stored_copies_are_read_only_and_verified():
    pid = _project()
    _upload(pid, "d.md", b"content")
    sha = _history(pid, "uploads/d.md")["versions"][0]["sha256"]
    p = versions.object_path(sha)
    assert p.read_bytes() == b"content"
    import os, stat
    assert not os.stat(p).st_mode & stat.S_IWRITE


def test_trash_lists_deleted_files_and_restore_brings_them_back():
    pid = _project()
    _upload(pid, "gone.md", b"keep me")
    (workspace.project_root(pid) / "uploads" / "gone.md").unlink()
    t = client.get(f"/api/v1/projects/{pid}/files/trash").json()
    assert [r["path"] for r in t] == ["uploads/gone.md"]
    r = client.post(f"/api/v1/projects/{pid}/files/restore", json={"path": "uploads/gone.md", "version": 1}, headers=H)
    assert r.status_code == 200
    assert client.get(f"/api/v1/projects/{pid}/files/trash").json() == []


def test_compare_shows_changed_lines():
    pid = _project()
    _upload(pid, "c.md", b"a\nb\nc\n")
    _upload(pid, "c.md", b"a\nB\nc\nd\n")
    d = client.get(f"/api/v1/projects/{pid}/files/compare", params={"path": "uploads/c.md", "old": 1, "new": 2}).json()
    assert d["added"] == 2 and d["removed"] == 1
    assert {"tag": "replace", "a": ["b"], "b": ["B"], "a_start": 2, "b_start": 2} in d["blocks"]
    now_ = client.get(f"/api/v1/projects/{pid}/files/compare", params={"path": "uploads/c.md", "old": 2}).json()
    assert now_["added"] == 0 and now_["removed"] == 0


def test_rename_moves_the_history_with_the_file():
    pid = _project()
    _upload(pid, "r.md", b"1")
    _upload(pid, "r.md", b"2")
    r = client.post(f"/api/v1/projects/{pid}/files/rename", json={"path": "uploads/r.md", "new_path": "paper/r.md"},
                    headers=H)
    assert r.status_code == 200, r.text
    root = workspace.project_root(pid)
    assert (root / "paper" / "r.md").read_bytes() == b"2" and not (root / "uploads" / "r.md").exists()
    assert len(_history(pid, "paper/r.md")["versions"]) == 2
    bad = client.post(f"/api/v1/projects/{pid}/files/rename", json={"path": "paper/r.md", "new_path": "paper/r.pdf"},
                      headers=H)
    assert bad.status_code == 400


def test_damaged_zip_unpacks_nothing():
    import io
    import zipfile
    from webapi.app.workspace import PathError, unzip_into
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("a.md", "x" * 1000)
        z.writestr("b.md", "y" * 1000)
    data = bytearray(buf.getvalue())
    data[60:80] = b"\x00" * 20  # corrupt the first member's compressed bytes
    import tempfile
    from pathlib import Path
    d = Path(tempfile.mkdtemp())
    (d / "in.zip").write_bytes(bytes(data))
    try:
        unzip_into(d / "in.zip", d / "out")
    except PathError:
        pass
    assert not (d / "out").exists() or not any((d / "out").rglob("*"))
    assert not [p for p in d.iterdir() if p.name.startswith(".unzip_")]


def test_backup_is_verified_and_audit_finds_damage():
    from webapi.app import backup
    pid = _project()
    _upload(pid, "z.md", b"precious")
    b = client.post("/api/v1/backups", headers=H)
    assert b.status_code == 201 and len(b.json()["db_sha256"]) == 64
    assert any(r["id"] == b.json()["id"] and r["present"] for r in client.get("/api/v1/backups").json()["backups"])
    a = client.get("/api/v1/integrity", params={"project_id": pid, "full": True}).json()
    assert a["ok"] and a["database_ok"] and a["checked_versions"] >= 1
    sha = _history(pid, "uploads/z.md")["versions"][0]["sha256"]
    p = versions.object_path(sha)
    import os, stat
    os.chmod(p, stat.S_IREAD | stat.S_IWRITE)
    p.write_bytes(b"tampered")
    a = backup.audit(store, pid, None)
    assert not a["ok"] and sha in a["damaged"]


def test_artifacts_now_require_a_real_project():
    import sqlite3
    sql = store.one("SELECT sql FROM sqlite_master WHERE name='artifacts'")["sql"]
    assert "project_id TEXT NOT NULL REFERENCES projects" in sql
    try:
        store.exec("INSERT INTO artifacts(run_id, project_id, path, sha256, size, change, created_at) "
                   "VALUES ('nope','nope','x','',0,'created','t')")
        raise AssertionError("an artifact for a missing project was accepted")
    except sqlite3.IntegrityError:
        pass
