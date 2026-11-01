"""Paper Studio: stage path, engine references, approval gates, re-run reopening later stages."""
import json
import os
from pathlib import Path

import pytest

from webapi.app import paper_studio
from webapi.app.config import REPO_ROOT
from webapi.tests.test_api import H, client


@pytest.fixture
def bridge_mode(monkeypatch):
    monkeypatch.setenv("RL_EXECUTOR", "bridge")


def _ws(pid):
    return Path(os.environ["RL_WEB_DATA"]) / "projects" / pid / "workspace"


def _paper(ptype="research_article", venue="iclr2025"):
    p = client.post("/api/v1/projects", json={"title": "Paper project"}, headers=H).json()
    r = client.post(f"/api/v1/projects/{p['id']}/paper", json={"type": ptype, "venue": venue, "topic": "VLM oracles"},
                    headers=H)
    assert r.status_code == 201, r.text
    return p["id"], r.json()


def _finish(task, files, summary="ok"):
    ws = Path(task["workspace"])
    for f in files:
        (ws / f).parent.mkdir(parents=True, exist_ok=True)
        (ws / f).write_text("x", encoding="utf-8")
    client.post(f"/api/v1/bridge/runs/{task['run_id']}/done", json={"summary": summary}, headers=H)


def test_every_engine_file_referenced_by_a_stage_exists():
    missing = [e for t in paper_studio.PAPER_TYPES.values() for s in t["stages"] for e in s["engines"]
               if not (REPO_ROOT / e).exists()]
    assert missing == []
    for v in paper_studio.VENUES.values():
        assert v["template"] is None or (REPO_ROOT / v["template"] / "template.tex").is_file()


def test_stage_gates_run_approve_and_reopen(bridge_mode):
    while client.post("/api/v1/bridge/next", headers=H).status_code == 200:
        pass
    pid, view = _paper()
    st = {s["id"]: s["status"] for s in view["stages"]}
    assert st["idea"] == "ready" and st["literature"] == "locked"
    assert client.post(f"/api/v1/projects/{pid}/paper/stages/literature/run", json={}, headers=H).status_code == 400

    client.post(f"/api/v1/projects/{pid}/paper/stages/idea/run", json={"notes": "focus on insurance"}, headers=H)
    task = client.post("/api/v1/bridge/next", headers=H).json()
    assert "idea-discovery-v5" in task["task"] and "focus on insurance" in task["task"] and "paper/idea.md" in task["task"]
    # Approving before outputs exist is refused.
    assert client.post(f"/api/v1/projects/{pid}/paper/stages/idea/approve", headers=H).status_code == 400
    _finish(task, ["paper/idea.md"])
    v = client.get(f"/api/v1/projects/{pid}/paper").json()
    assert {s["id"]: s["status"] for s in v["stages"]}["idea"] == "needs_review"
    v = client.post(f"/api/v1/projects/{pid}/paper/stages/idea/approve", headers=H).json()
    st = {s["id"]: s["status"] for s in v["stages"]}
    assert st["idea"] == "approved" and st["literature"] == "ready"

    client.post(f"/api/v1/projects/{pid}/paper/stages/literature/run", json={}, headers=H)
    t2 = client.post("/api/v1/bridge/next", headers=H).json()
    assert "literature_review_agent.py" in t2["task"] and "iclr2025" in t2["task"]
    _finish(t2, ["paper/refs.bib"])  # literature.md missing
    st = {s["id"]: s["status"] for s in client.get(f"/api/v1/projects/{pid}/paper").json()["stages"]}
    assert st["literature"] == "incomplete"

    # Asking for changes to the idea re-opens later stages.
    client.post(f"/api/v1/projects/{pid}/paper/stages/idea/run", json={"feedback": "narrower scope"}, headers=H)
    t3 = client.post("/api/v1/bridge/next", headers=H).json()
    assert "narrower scope" in t3["task"]
    _finish(t3, ["paper/idea.md"])
    st = {s["id"]: s["status"] for s in client.get(f"/api/v1/projects/{pid}/paper").json()["stages"]}
    assert st["idea"] == "needs_review" and st["literature"] == "locked"


def test_choose_brainstorm_idea_writes_idea_md():
    pid, _ = _paper()
    (_ws(pid) / "ideas").mkdir(parents=True, exist_ok=True)
    (_ws(pid) / "ideas" / "ideas.json").write_text(json.dumps({"ideas": [
        {"id": "I2", "title": "Whitepaper figures vs code", "pitch": "p", "problem": "q", "hypothesis": "h",
         "falsifier": {"metric": "m", "threshold": "10 %", "statement": "s"}}]}), encoding="utf-8")
    v = client.post(f"/api/v1/projects/{pid}/paper/choose-idea/I2", headers=H).json()
    assert (_ws(pid) / "paper" / "idea.md").read_text(encoding="utf-8").startswith("# Whitepaper figures vs code")
    assert {s["id"]: s["status"] for s in v["stages"]}["idea"] == "needs_review"


def test_review_paper_has_its_own_path():
    pid, view = _paper("review_paper", "journal")
    assert [s["id"] for s in view["stages"]] == ["scope", "search", "synthesis", "write", "review", "revise"]
    assert client.post(f"/api/v1/projects/{pid}/paper", json={"type": "review_paper"}, headers=H).status_code == 400
