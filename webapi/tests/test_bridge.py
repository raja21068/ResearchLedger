"""Claude app bridge: runs wait in a queue, a worker claims them, does the work, sends the reply back."""
import os
import subprocess
import sys
from pathlib import Path

import pytest

from webapi.tests.test_api import H, client


@pytest.fixture
def bridge_mode(monkeypatch):
    monkeypatch.setenv("RL_EXECUTOR", "bridge")


def _chat_run(prompt="Write a note"):
    p = client.post("/api/v1/projects", json={"title": "Bridge project"}, headers=H).json()
    c = client.post(f"/api/v1/projects/{p['id']}/conversations", json={}, headers=H).json()
    r = client.post(f"/api/v1/conversations/{c['id']}/runs", json={"prompt": prompt}, headers=H).json()
    return p, c, r


def test_queued_until_claimed_then_reply_and_files_come_back(bridge_mode):
    while client.post("/api/v1/bridge/next", headers=H).status_code == 200:
        pass  # drain anything queued by earlier tests
    p, c, r = _chat_run()
    assert client.get(f"/api/v1/runs/{r['id']}").json()["status"] == "queued"
    status = client.get("/api/v1/bridge/status").json()
    assert status["executor"] == "bridge" and status["queued"] >= 1

    task = client.post("/api/v1/bridge/next", headers=H).json()
    assert task["run_id"] == r["id"] and task["task"] == "Write a note" and "research agent" in task["instructions"]
    ws = Path(task["workspace"])
    assert client.get(f"/api/v1/runs/{r['id']}").json()["status"] == "running"
    assert client.get("/api/v1/bridge/status").json()["worker_connected"] is True

    assert client.post(f"/api/v1/bridge/runs/{r['id']}/event", json={"kind": "todos", "text": "- [x] read\n- > write"},
                       headers=H).status_code == 200
    (ws / "notes").mkdir(exist_ok=True)
    (ws / "notes" / "note.md").write_text("# Note\n", encoding="utf-8")
    done = client.post(f"/api/v1/bridge/runs/{r['id']}/done", json={"summary": "Wrote **notes/note.md**."}, headers=H).json()
    assert done["status"] == "succeeded" and done["result_text"].startswith("Wrote")

    run = client.get(f"/api/v1/runs/{r['id']}").json()
    assert "notes/note.md" in [a["path"] for a in run["artifacts"]]
    events = client.get(f"/api/v1/conversations/{c['id']}").json()["runs"][0]["events"]
    kinds = [e["kind"] for e in events]
    assert {"todos", "assistant_text", "artifacts", "done"} <= set(kinds)
    assert r["id"] in client.get(f"/api/v1/projects/{p['id']}/memory").json()["text"]


def test_follow_up_carries_earlier_turns(bridge_mode):
    p, c, r = _chat_run("First question")
    t1 = client.post("/api/v1/bridge/next", headers=H).json()
    client.post(f"/api/v1/bridge/runs/{t1['run_id']}/done", json={"summary": "First answer"}, headers=H)
    client.post(f"/api/v1/conversations/{c['id']}/runs", json={"prompt": "Second question"}, headers=H)
    t2 = client.post("/api/v1/bridge/next", headers=H).json()
    assert t2["earlier_turns"][-1] == {"user": "First question", "assistant": "First answer", "status": "succeeded"}
    client.post(f"/api/v1/bridge/runs/{t2['run_id']}/done", json={"summary": "ok"}, headers=H)


def test_cancel_queued_bridge_run(bridge_mode):
    _, _, r = _chat_run()
    assert client.post(f"/api/v1/runs/{r['id']}/cancel", headers=H).json()["status"] == "cancelled"
    while client.post("/api/v1/bridge/next", headers=H).status_code == 200:
        pass
    assert client.post("/api/v1/bridge/next", headers=H).status_code == 204


def test_worker_cli_reports_no_task_when_api_is_unreachable():
    env = dict(os.environ, RL_API_URL="http://127.0.0.1:9")
    out = subprocess.run([sys.executable, str(Path(__file__).parents[1] / "bridge_cli.py"), "next", "--wait", "0"],
                         capture_output=True, text=True, env=env)
    assert out.returncode != 0 and "Cannot reach the ResearchLedger API" in out.stderr
