"""Mission control: honest task states (interrupted, what a queued task waits for), heartbeats, job progress,
paper pipelines; and the worker's automatic heartbeat stops on its own."""
from webapi.app import mission
from webapi.app.db import now
from webapi.app.main import store
from webapi.tests.test_api import H, client
from webapi.tests.test_lab import _run_paper_experiment


def _project_conv(title="Mission"):
    pid = client.post("/api/v1/projects", json={"title": title}, headers=H).json()["id"]
    cid = client.post(f"/api/v1/projects/{pid}/conversations", json={}, headers=H).json()["id"]
    return pid, cid


def _run(rid, pid, cid, status, kind="claude_code", provider="claude_code_cli", error=None):
    store.exec("INSERT INTO runs(id,project_id,conversation_id,kind,prompt,status,provider,created_at,started_at,error) "
               "VALUES (?,?,?,?,?,?,?,?,?,?)", (rid, pid, cid, kind, "p", status, provider, now(),
                                                now() if status != "queued" else None, error))


def test_labels_are_plain_words():
    assert mission.label("loop:idea_forge:attack") == "Idea loop · paper search"
    assert mission.label("loop:experiment:run") == "Experiment loop · run on this computer"
    assert mission.label("paper:experiments") == "Paper · experiments"
    assert mission.label("repeat") == "Repeat run"


def test_restart_casualties_show_as_interrupted_not_failed():
    pid, cid = _project_conv()
    _run("run_mc_int", pid, cid, "failed", error="server restarted while run was active")
    _run("run_mc_bad", pid, cid, "failed", error="script crashed")
    m = client.get("/api/v1/mission").json()
    assert "run_mc_int" in {t["id"] for t in m["tasks"]["interrupted"]}
    assert "run_mc_bad" in {t["id"] for t in m["tasks"]["failed"]}
    assert all(not t["can_cancel"] for t in m["tasks"]["interrupted"])


def test_queued_task_says_what_it_waits_for(monkeypatch):
    monkeypatch.setenv("RL_EXECUTOR", "bridge")
    pid, cid = _project_conv()
    _run("run_mc_busy", pid, cid, "running")
    _run("run_mc_wait", pid, cid, "queued")
    m = client.get("/api/v1/mission").json()
    q = next(t for t in m["tasks"]["queued"] if t["id"] == "run_mc_wait")
    assert q["waiting_for"] == "another agent task in this project" and q["can_cancel"]
    for rid in ("run_mc_busy", "run_mc_wait"):
        store.exec("UPDATE runs SET status='cancelled' WHERE id=?", (rid,))


def test_server_runs_and_paper_pipelines_appear():
    pid, root, rid = _run_paper_experiment()
    m = client.get("/api/v1/mission").json()
    done = next(t for t in m["tasks"]["completed"] if t["id"] == rid)
    assert done["label"] == "Paper · experiments" and done["agent"] is False and done["link"].endswith("/paper")
    pipe = next(p for p in m["pipelines"] if p["project_id"] == pid)
    assert any(s["id"] == "experiments" for s in pipe["stages"])


def test_worker_heartbeat_stops_when_the_task_is_no_longer_running(monkeypatch):
    from webapi import bridge_cli
    calls = []

    def fake_call(method, path, body=None):
        calls.append(path)
        if len(calls) == 1:
            raise SystemExit("server down")  # first ping fails: keep trying
        return 409, "run is not running"

    monkeypatch.setattr(bridge_cli, "call", fake_call)
    monkeypatch.setattr(bridge_cli, "HEARTBEAT_S", 0)
    monkeypatch.setattr(bridge_cli.time, "sleep", lambda s: None)
    bridge_cli._heartbeat("run_x")
    assert len(calls) == 2 and calls[0] == "/bridge/runs/run_x/event"
