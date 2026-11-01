"""API tests with the scripted Claude stand-in (no network, no model calls)."""
import json
import os
import sys
import tempfile
import time
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
os.environ["RL_WEB_DATA"] = tempfile.mkdtemp(prefix="rl-web-test-")
os.environ["RL_CLAUDE_CMD"] = json.dumps([sys.executable, str(HERE / "fake_claude.py")])
os.environ["RL_EXECUTOR"] = "cli"  # test_bridge.py switches to the Claude app bridge explicitly

from fastapi.testclient import TestClient  # noqa: E402

from webapi.app.main import app  # noqa: E402

H = {"x-rl-client": "test"}
client = TestClient(app)


def wait(run_id, timeout=20):
    end = time.time() + timeout
    while time.time() < end:
        r = client.get(f"/api/v1/runs/{run_id}").json()
        if r["status"] in {"succeeded", "failed", "cancelled"}:
            return r
        time.sleep(0.1)
    raise AssertionError("run did not finish")


@pytest.fixture
def conv():
    p = client.post("/api/v1/projects", json={"title": "Test project"}, headers=H).json()
    c = client.post(f"/api/v1/projects/{p['id']}/conversations", json={}, headers=H).json()
    return p, c


def test_mutations_require_client_header():
    assert client.post("/api/v1/projects", json={"title": "x"}).status_code == 403


def test_dashboard_starts_from_real_records():
    d = client.get("/api/v1/dashboard").json()
    assert set(d["counts"]) == {"projects", "runs", "running", "artifacts", "reviews"}


def test_run_lifecycle_events_artifacts_and_resume(conv):
    p, c = conv
    run = client.post(f"/api/v1/conversations/{c['id']}/runs", json={"prompt": "Draft a paper"}, headers=H).json()
    done = wait(run["id"])
    assert done["status"] == "succeeded"
    assert done["artifacts"][0]["path"] == "manuscript/main.md"
    assert len(done["artifacts"][0]["sha256"]) == 64
    kinds = [e["kind"] for e in client.get(f"/api/v1/conversations/{c['id']}").json()["runs"][0]["events"]]
    assert {"init", "assistant_text", "tool_use", "tool_result", "result", "artifacts", "done", "todos"} <= set(kinds)
    # The CLI session id is stored and passed back with --resume on the follow-up.
    run2 = client.post(f"/api/v1/conversations/{c['id']}/runs", json={"prompt": "Revise"}, headers=H).json()
    assert wait(run2["id"])["result_text"] == "Done (resumed=True)"


def test_failed_cli_result_is_never_reported_as_success(conv):
    _, c = conv
    run = client.post(f"/api/v1/conversations/{c['id']}/runs", json={"prompt": "FAIL now"}, headers=H).json()
    done = wait(run["id"])
    assert done["status"] == "failed" and "Failed on purpose" in done["error"]


def test_cancel_and_one_active_run_per_conversation(conv):
    _, c = conv
    run = client.post(f"/api/v1/conversations/{c['id']}/runs", json={"prompt": "SLOW"}, headers=H).json()
    time.sleep(1.0)
    busy = client.post(f"/api/v1/conversations/{c['id']}/runs", json={"prompt": "x"}, headers=H)
    assert busy.status_code == 409
    assert client.post(f"/api/v1/runs/{run['id']}/cancel", headers=H).status_code == 200
    assert wait(run["id"])["status"] == "cancelled"


def test_sse_stream_replays_and_ends(conv):
    _, c = conv
    run = client.post(f"/api/v1/conversations/{c['id']}/runs", json={"prompt": "Draft"}, headers=H).json()
    wait(run["id"])
    with client.stream("GET", f"/api/v1/runs/{run['id']}/events") as s:
        body = "".join(s.iter_text())
    assert "event: init" in body and "event: end" in body


def test_path_traversal_rejected(conv):
    p, _ = conv
    for bad in ["../secret.txt", "..\\x", "/etc/passwd", "C:/Windows/win.ini"]:
        r = client.get(f"/api/v1/projects/{p['id']}/files/raw", params={"path": bad})
        assert r.status_code == 400, bad


def test_upload_preview_and_docx_export(conv):
    p, _ = conv
    up = client.post(f"/api/v1/projects/{p['id']}/files", headers=H,
                     files={"file": ("draft.md", b"# T\n\n## Intro\n\nHello\n", "text/markdown")})
    assert up.status_code == 201 and up.json()["path"] == "uploads/draft.md"
    bad = client.post(f"/api/v1/projects/{p['id']}/files", headers=H,
                      files={"file": ("run.exe", b"MZ", "application/octet-stream")})
    assert bad.status_code == 415
    ex = client.post(f"/api/v1/projects/{p['id']}/export", json={"path": "uploads/draft.md", "to": "docx"},
                     headers=H)
    assert ex.status_code == 200 and ex.json()["path"] == "uploads/draft.docx"
    pv = client.get(f"/api/v1/projects/{p['id']}/files/preview", params={"path": "uploads/draft.docx"}).json()
    assert pv["kind"] == "docx" and "Intro" in pv["html"]
    raw = client.get(f"/api/v1/projects/{p['id']}/files/raw", params={"path": "uploads/draft.md"})
    assert raw.headers["content-security-policy"] == "sandbox"


def test_registry_is_honest():
    agents = client.get("/api/v1/agents").json()
    statuses = {a["status"] for a in agents}
    assert statuses <= {"integrated", "available_standalone", "optional", "planned", "disabled"}
    integrated = [a for a in agents if a["status"] == "integrated"]
    assert all(a["implementation_present"] for a in integrated)
