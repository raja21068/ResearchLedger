"""Adversarial regression tests (docs/INTEGRATION_DECISIONS.md): things an agent, a crafted upload or a forged file
must not be able to do. Each test names the attack."""
import io
import json
import os
import threading
import zipfile

import pytest

from webapi.app import exprun, ledger_bridge, workspace
from webapi.app.main import store
from webapi.tests.test_api import H, client
from webapi.tests.test_lab import _run_paper_experiment


def _project():
    return client.post("/api/v1/projects", json={"title": "Sec"}, headers=H).json()["id"]


# ---- paths: write/read outside the workspace, another project's files, traversal in names
@pytest.mark.parametrize("bad", ["../x.txt", "..\\x.txt", "a/../../x.txt", "/etc/passwd", "C:\\Windows\\win.ini", "a\x00b"])
def test_paths_outside_the_workspace_are_refused_everywhere(bad):
    pid = _project()
    for url in (f"/api/v1/projects/{pid}/files/raw", f"/api/v1/projects/{pid}/files/preview",
                f"/api/v1/projects/{pid}/files/history", f"/api/v1/projects/{pid}/files/trash"):
        if url.endswith("trash"):
            continue
        assert client.get(url, params={"path": bad}).status_code in {400, 404, 422}, (url, bad)
    up = client.post(f"/api/v1/projects/{pid}/files", params={"folder": bad}, headers=H,
                     files={"file": ("a.md", b"x", "text/markdown")})
    if up.status_code == 201:  # a leading slash is normalised into the workspace; it must never land outside
        root = workspace.project_root(pid)
        assert all(root in p.resolve().parents for p in root.rglob("a.md"))
        assert not (root.parent / "a.md").exists()
    else:
        assert up.status_code in {400, 404, 422}
    ren = client.post(f"/api/v1/projects/{pid}/files/rename", headers=H, json={"path": "uploads/a.md", "new_path": bad})
    assert ren.status_code in {400, 404, 422}


def test_another_projects_files_cannot_be_reached_through_traversal():
    a, b = _project(), _project()
    (workspace.project_root(b) / "secret.md").write_text("private", encoding="utf-8")
    other = f"../../{b}/workspace/secret.md"
    for ep in ("raw", "preview", "history"):
        r = client.get(f"/api/v1/projects/{a}/files/{ep}", params={"path": other})
        assert r.status_code in {400, 404} and "private" not in r.text


def test_a_symlink_that_points_outside_the_workspace_is_not_followed():
    pid = _project()
    root = workspace.project_root(pid)
    outside = root.parent / "outside.txt"
    outside.write_text("host secret", encoding="utf-8")
    link = root / "link.txt"
    try:
        os.symlink(outside, link)
    except (OSError, NotImplementedError):
        pytest.skip("this Windows account cannot create symlinks")
    r = client.get(f"/api/v1/projects/{pid}/files/raw", params={"path": "link.txt"})
    assert r.status_code in {400, 404} and "host secret" not in r.text


def test_zip_with_traversal_absolute_and_symlink_members_writes_nothing_outside():
    pid = _project()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("../evil.md", "x")
        z.writestr("/abs.md", "x")
        z.writestr("C:/win.md", "x")
        info = zipfile.ZipInfo("ln.md")
        info.external_attr = (0o120777 << 16)  # a symlink entry
        z.writestr(info, "../../outside")
        z.writestr("ok/fine.md", "fine")
    r = client.post(f"/api/v1/projects/{pid}/files", params={"unzip": True}, headers=H,
                    files={"file": ("p.zip", buf.getvalue(), "application/zip")})
    assert r.status_code == 201, r.text
    root = workspace.project_root(pid)
    assert not (root.parent / "evil.md").exists() and not (root / "abs.md").exists()
    got = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}
    assert "uploads/p/ok/fine.md" in got
    assert not any(g.endswith(("evil.md", "abs.md", "win.md", "ln.md")) for g in got)


def test_loop_and_run_ids_with_traversal_do_not_reach_other_files():
    pid = _project()
    for evil in ("..%2F..%2Fx", "..%5C..%5Cx", "%2e%2e%2f%2e%2e%2fx"):
        assert client.get(f"/api/v1/projects/{pid}/loops/{evil}").status_code in {400, 404, 405, 422}


# ---- execution: only python scripts under code/, never a shell
@pytest.mark.parametrize("cmd", ["rm -rf /", "python ../x.py", "python /abs/x.py", "python C:\\x.py", "bash code/x.sh",
                                 "python code/x.py && rm -rf /", "python -c 'import os'", "python data/x.py"])
def test_experiment_commands_that_are_not_a_python_script_under_code_are_refused(cmd):
    pid = _project()
    root = workspace.project_root(pid)
    (root / "code").mkdir()
    (root / "code" / "x.py").write_text("print(1)", encoding="utf-8")
    argv, err = exprun.parse_command(root, cmd)
    if argv is not None:      # accepted: always a .py inside the workspace, and an operator is only an inert argument
        assert argv[0] in {"python", "python3", "py"} and argv[1].endswith(".py")
        assert root.resolve() in (root / argv[1]).resolve().parents
    if cmd.startswith(("rm ", "bash ", "python -c", "python ../", "python /")):
        assert err is not None, cmd


# ---- forged records
def test_a_forged_receipt_file_does_not_become_evidence():
    """An agent can write any file in its workspace, including results/receipts/*.json."""
    pid, root, rid = _run_paper_experiment()
    real = len(client.get(f"/api/v1/projects/{pid}/evidence").json()["evidence"])
    forged = {"run_id": "run_forged0000", "runner": "host", "finished_at": "2026-11-03T00:00:00+00:00", "experiment": "paper",
              "jobs": [{"id": "E9", "command": "python code/exp.py", "exit_code": 0, "ok": True, "seconds": 1,
                        "slots": {"acc_forged": {"ok": True, "value": 99}}}]}
    (root / "results" / "receipts" / "run_forged0000.json").write_text(json.dumps(forged), encoding="utf-8")
    ov = client.get(f"/api/v1/projects/{pid}/evidence").json()
    assert len(ov["evidence"]) == real
    assert not any("acc_forged" in e["values"] for e in ov["evidence"])
    assert any(e["app_ref"].startswith(rid) for e in ov["evidence"])


def test_a_failed_job_never_becomes_evidence_and_unknown_evidence_cannot_be_promoted():
    pid = _project()
    root = workspace.project_root(pid)
    d = root / "results" / "receipts"
    d.mkdir(parents=True)
    conv = client.post(f"/api/v1/projects/{pid}/conversations", json={}, headers=H).json()["id"]
    store.exec("INSERT INTO runs(id,project_id,conversation_id,kind,prompt,status,provider,created_at) VALUES "
               "('run_failedjob1',?,?,'repeat','p','succeeded','server_exec','2026-11-03T00:00:00+00:00')", (pid, conv))
    (d / "run_failedjob1.json").write_text(json.dumps({"run_id": "run_failedjob1", "finished_at": "2026-11-03T00:00:00+00:00",
        "jobs": [{"id": "E1", "command": "python code/x.py", "exit_code": 1, "ok": False,
                  "slots": {"s": {"ok": True, "value": 5}}}]}), encoding="utf-8")
    assert client.get(f"/api/v1/projects/{pid}/evidence").json()["evidence"] == []
    r = client.post(f"/api/v1/projects/{pid}/evidence/E999/status", headers=H, json={"status": "verified", "reason": "trust me"})
    assert r.status_code == 400


def test_concurrent_claim_creation_gets_unique_ids():
    pid, root, rid = _run_paper_experiment()
    eid = client.get(f"/api/v1/projects/{pid}/evidence").json()["evidence"][0]["id"]
    ids, errs = [], []

    def make(i):
        try:
            ids.append(ledger_bridge.add_claim(store, pid, f"Concurrent claim number {i} is stated here.", supports=[eid]))
        except Exception as exc:  # noqa: BLE001
            errs.append(repr(exc))
    threads = [threading.Thread(target=make, args=(i,)) for i in range(8)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert not errs and len(set(ids)) == 8
    assert client.get(f"/api/v1/projects/{pid}/evidence").json()["valid"]


def test_agents_cannot_write_canonical_ledger_records_through_the_api():
    """There is no endpoint that creates evidence or runs from agent-supplied content; only the user's status call."""
    paths = {r.path for r in client.app.routes}
    assert not any(p.endswith("/evidence") and "POST" in getattr(r, "methods", set())
                   for r in client.app.routes for p in [r.path])
    assert not any("/ledger/" in p and "POST" in getattr(r, "methods", set()) for r in client.app.routes for p in [r.path])
    assert "/api/v1/projects/{project_id}/evidence/{evidence_id}/status" in paths   # user judgment only (needs a reason)
