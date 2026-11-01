"""Research Director: plan written by the agent, approval gate, sequential execution in the same chat."""
import time

from webapi.tests.test_api import H, client


def _wait(run_id, timeout=120):
    end = time.time() + timeout
    while time.time() < end:
        r = client.get(f"/api/v1/runs/{run_id}").json()
        if r["status"] in {"succeeded", "failed", "cancelled"}:
            return r
        time.sleep(0.3)
    raise AssertionError("run did not finish")


def _chat():
    p = client.post("/api/v1/projects", json={"title": "Director project"}, headers=H).json()
    return p, client.post(f"/api/v1/projects/{p['id']}/conversations", json={}, headers=H).json()


def test_director_plans_then_runs_steps_only_after_approval():
    p, c = _chat()
    turn = client.post(f"/api/v1/conversations/{c['id']}/director", json={"prompt": "Review the literature"}, headers=H).json()
    assert turn["kind"] == "director"
    _wait(turn["id"])
    plan = client.get(f"/api/v1/conversations/{c['id']}/plan").json()
    assert [s["workflow"] for s in plan["plan"]["steps"]] == ["literature_review", "pipeline_status"]
    assert plan["plan_run"] is None  # nothing ran yet: approval gate
    runs_before = len(client.get(f"/api/v1/conversations/{c['id']}").json()["runs"])
    assert runs_before == 1

    plan_run = client.post(f"/api/v1/conversations/{c['id']}/plan/approve", headers=H).json()
    done = _wait(plan_run["id"])
    assert done["status"] == "succeeded", done["error"]
    runs = client.get(f"/api/v1/conversations/{c['id']}").json()["runs"]
    kinds = [r["kind"] for r in runs]
    assert kinds[:2] == ["director", "plan"] and "workflow:literature_review" in kinds and "workflow:pipeline_status" in kinds
    steps = [e["payload"] for e in runs[1]["events"] if e["kind"] == "plan_step" and e["payload"]["status"] == "succeeded"]
    assert [s["index"] for s in steps] == [0, 1]


def test_plan_with_human_only_tool_is_refused():
    p, c = _chat()
    turn = client.post(f"/api/v1/conversations/{c['id']}/director", json={"prompt": "BADPLAN lock it"}, headers=H).json()
    _wait(turn["id"])
    r = client.post(f"/api/v1/conversations/{c['id']}/plan/approve", headers=H)
    assert r.status_code == 400 and "human-only" in r.json()["detail"]


def test_approve_without_plan_is_refused():
    p, c = _chat()
    assert client.post(f"/api/v1/conversations/{c['id']}/plan/approve", headers=H).status_code == 400
