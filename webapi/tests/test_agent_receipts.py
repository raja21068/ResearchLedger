"""Every finished agent task leaves a receipt the server wrote, outside the workspace, that detects hand edits."""
import json
import uuid

from webapi.app import agent_receipts, bridge, workspace
from webapi.app.main import store
from webapi.tests.test_api import H, client


def _task(pid):
    conv = client.post(f"/api/v1/projects/{pid}/conversations", json={}, headers=H).json()["id"]
    rid = "run_rc" + uuid.uuid4().hex[:8]
    store.exec("INSERT INTO runs(id,project_id,conversation_id,kind,prompt,status,provider,created_at,started_at) VALUES "
               "(?,?,?,'paper:write','write it','running','claude_code','2026-11-03T00:00:00+00:00','2026-11-03T00:00:01+00:00')",
               (rid, pid, conv))
    store.exec("INSERT INTO artifacts(run_id,project_id,path,sha256,size,change,created_at) VALUES (?,?,?,?,?,?,?)",
               (rid, pid, "paper/draft.md", "ab" * 32, 12, "written", "2026-11-03T00:00:02+00:00"))
    return rid


def test_a_finished_task_gets_a_server_written_receipt_outside_the_workspace():
    pid = client.post("/api/v1/projects", json={"title": "Rcpt"}, headers=H).json()["id"]
    rid = _task(pid)
    assert agent_receipts.read(pid, rid) is None            # nothing until the task is final
    store.update_run(rid, status="succeeded", finished_at="2026-11-03T00:01:00+00:00", result_text="done")
    rec = client.get(f"/api/v1/projects/{pid}/agent-receipts/{rid}").json()
    assert rec["written_by"] == "server" and rec["parent"] == {"type": "paper_stage", "id": "write"}
    assert rec["artifacts"][0]["path"] == "paper/draft.md" and rec["artifacts"][0]["sha256"] == "ab" * 32
    assert rec["status"] == "succeeded" and rec["intact"] is True and rec["result_sha256"]
    assert not list(workspace.project_root(pid).rglob(f"{rid}.json"))     # not somewhere an agent can reach


def test_a_receipt_is_a_record_it_is_not_rewritten_and_hand_edits_are_detected():
    pid = client.post("/api/v1/projects", json={"title": "Rcpt2"}, headers=H).json()["id"]
    rid = _task(pid)
    store.update_run(rid, status="failed", finished_at="2026-11-03T00:01:00+00:00", error="boom")
    first = agent_receipts.path_for(pid, rid).read_text(encoding="utf-8")
    store.update_run(rid, status="succeeded")                # a later change must not rewrite history
    assert agent_receipts.path_for(pid, rid).read_text(encoding="utf-8") == first
    edited = json.loads(first)
    edited["status"] = "succeeded"
    agent_receipts.path_for(pid, rid).write_text(json.dumps(edited), encoding="utf-8")
    assert client.get(f"/api/v1/projects/{pid}/agent-receipts/{rid}").json()["intact"] is False
    assert client.get(f"/api/v1/projects/{pid}/agent-receipts").json()["receipts"][0]["intact"] is False


def test_receipt_lookup_rejects_odd_ids_and_other_projects():
    a = client.post("/api/v1/projects", json={"title": "A"}, headers=H).json()["id"]
    b = client.post("/api/v1/projects", json={"title": "B"}, headers=H).json()["id"]
    rid = _task(a)
    store.update_run(rid, status="succeeded", finished_at="2026-11-03T00:01:00+00:00")
    assert client.get(f"/api/v1/projects/{b}/agent-receipts/{rid}").status_code == 404
    assert client.get(f"/api/v1/projects/{a}/agent-receipts/..%2F..%2Fx").status_code == 404
