"""Workflow tests. The researchctl ones run the REAL Factory/ResearchLedger code (no model calls)."""
import time

from webapi.tests.test_api import H, client


def _project():
    return client.post("/api/v1/projects", json={"title": "Workflow project"}, headers=H).json()


def _wait(run_id, timeout=180):
    end = time.time() + timeout
    while time.time() < end:
        r = client.get(f"/api/v1/runs/{run_id}").json()
        if r["status"] in {"succeeded", "failed", "cancelled"}:
            return r
        time.sleep(0.3)
    raise AssertionError("workflow did not finish")


def test_registry_lists_every_section():
    wfs = client.get("/api/v1/workflows").json()
    assert {w["section"] for w in wfs} == {"discover", "analyze", "manuscripts", "review", "evidence"}
    assert all("build" not in w and "prompt" not in w for w in wfs)


def test_real_factory_status_initializes_workspace():
    p = _project()
    r = client.post(f"/api/v1/projects/{p['id']}/workflows/pipeline_status", json={"values": {}}, headers=H).json()
    run = _wait(r["run_id"])
    assert run["status"] == "succeeded", run["error"]
    assert '"state": "INITIALIZED"' in run["result_text"]
    files = [f["path"] for f in client.get(f"/api/v1/projects/{p['id']}/files").json()]
    assert "state.json" in files


def test_blocked_ledger_report_is_a_completed_report_not_a_crash():
    p = _project()
    r = client.post(f"/api/v1/projects/{p['id']}/workflows/ledger_report", json={"values": {}}, headers=H).json()
    run = _wait(r["run_id"])
    assert run["status"] == "succeeded"
    assert '"status": "BLOCKED"' in run["result_text"]


def test_inputs_are_validated_before_launch():
    p = _project()
    url = f"/api/v1/projects/{p['id']}/workflows"
    assert client.post(f"{url}/idea_generation", json={"values": {}}, headers=H).status_code == 400
    assert client.post(f"{url}/idea_generation", json={"values": {"topic": "x", "idea_count": "99"}},
                       headers=H).status_code == 400
    assert client.post(f"{url}/protocol_lock", json={"values": {"confirm": False}}, headers=H).status_code == 400
    assert client.post(f"{url}/quick_review", json={"values": {"manuscript": "../x.pdf"}}, headers=H).status_code == 400
    assert client.post(f"{url}/quick_review", json={"values": {"manuscript": "missing.pdf"}}, headers=H).status_code == 400


def test_claude_workflow_runs_with_its_task_prompt():
    p = _project()
    r = client.post(f"/api/v1/projects/{p['id']}/workflows/literature_review",
                    json={"values": {"topic": "MRI robustness"}}, headers=H).json()
    run = _wait(r["run_id"])
    assert run["status"] == "succeeded"
    conv = client.get(f"/api/v1/conversations/{r['conversation_id']}").json()
    assert "literature/literature_matrix.csv" in conv["runs"][0]["prompt"]
    assert conv["title"].startswith("Literature review")


def test_brainstorm_stages_idea_v5_rules_and_asks_for_idea_cards():
    import os
    from pathlib import Path
    from webapi.app.workflows import IDEA_V5_ZIP
    p = _project()
    r = client.post(f"/api/v1/projects/{p['id']}/workflows/brainstorm",
                    json={"values": {"areas": "Blockchain, LLM, VLM", "n_ideas": "3"}}, headers=H).json()
    run = _wait(r["run_id"])
    prompt = client.get(f"/api/v1/conversations/{r['conversation_id']}").json()["runs"][0]["prompt"]
    assert "ideas/ideas.json" in prompt and "READY_FOR_MVE" in prompt and "Blockchain, LLM, VLM" in prompt
    staged = Path(os.environ["RL_WEB_DATA"]) / "projects" / p["id"] / "workspace" / ".skills" / "idea-discovery-v5"
    if IDEA_V5_ZIP.is_file():
        assert (staged / "SKILL.md").is_file() and not (staged / "scripts").exists()
    assert run["status"] == "succeeded"


def test_progress_reflects_workspace_files():
    p = _project()
    up = client.post(f"/api/v1/projects/{p['id']}/files", headers=H, params={"folder": "review"},
                     files={"file": ("quick_review.md", b"# Review\n", "text/markdown")})
    assert up.status_code == 201
    steps = {s["step"]: s for s in client.get(f"/api/v1/projects/{p['id']}/progress").json()}
    assert steps["05"]["state"] == "done" and steps["01"]["state"] == "not_started"
