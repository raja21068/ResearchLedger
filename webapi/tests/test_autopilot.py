"""One-click autopilot: goal classification, auto-advance after approval, approvals inbox."""
from pathlib import Path

import pytest

from webapi.app import autopilot
from webapi.tests.test_api import H, client


@pytest.fixture
def bridge_mode(monkeypatch):
    monkeypatch.setenv("RL_EXECUTOR", "bridge")
    monkeypatch.setenv("RL_PAPER_AUTOPILOT", "1")


def _drain():
    """Claim and finish anything queued, so no half-done claims leak into other tests."""
    while True:
        r = client.post("/api/v1/bridge/next", headers=H)
        if r.status_code != 200:
            return
        t = r.json()
        client.post(f"/api/v1/bridge/runs/{t['run_id']}/done", json={"summary": "cleanup", "claim": t.get("claim")}, headers=H)


def _finish(task, files):
    ws = Path(task["workspace"])
    for f in files:
        (ws / f).parent.mkdir(parents=True, exist_ok=True)
        (ws / f).write_text("x", encoding="utf-8")
    client.post(f"/api/v1/bridge/runs/{task['run_id']}/done", json={"summary": "Stage done.", "claim": task.get("claim")}, headers=H)


def _project(title="Autopilot project"):
    return client.post("/api/v1/projects", json={"title": title}, headers=H).json()["id"]


@pytest.mark.parametrize("goal,files,mode,target", [
    ("Write a full paper on verifiable VLM oracles", [], "paper", "research_article"),
    ("I need a survey paper on federated learning", [], "paper", "review_paper"),
    ("Turn my PhD thesis into a journal article", ["thesis.pdf"], "paper", "thesis_to_paper"),
    ("Help me answer the reviewer comments", ["paper.pdf", "comments.docx"], "paper", "revision_rebuttal"),
    ("", ["manuscript.pdf"], "recipe", "review_paper"),
    ("make slides for my talk", ["paper.pdf"], "recipe", "make_slides"),
    ("what is a good baseline for this task?", [], "director", None),
])
def test_classify(goal, files, mode, target):
    d = autopilot.classify(goal, files)
    assert d["mode"] == mode and d.get("paper_type", d.get("recipe")) == target and d["why"]


def test_paper_autopilot_starts_first_stage_and_advances_after_approval(bridge_mode):
    _drain()
    pid = _project()
    out = client.post(f"/api/v1/projects/{pid}/autopilot/start", json={"goal": "Write a paper on chart-reading VLMs"},
                      headers=H).json()
    assert out["mode"] == "paper" and out["url"].endswith("/paper")
    v = client.get(f"/api/v1/projects/{pid}/paper").json()
    assert v["autopilot"] is True and v["stages"][0]["status"] == "running"
    t1 = client.post("/api/v1/bridge/next", headers=H).json()
    _finish(t1, v["stages"][0]["outputs"])
    inbox = client.get("/api/v1/inbox").json()
    assert any(i["project_id"] == pid and i["stage_id"] == v["stages"][0]["id"] for i in inbox["approve"])
    v = client.post(f"/api/v1/projects/{pid}/paper/stages/{v['stages'][0]['id']}/approve", headers=H).json()
    assert v["stages"][1]["status"] == "running"  # next stage started by itself
    t2 = client.post("/api/v1/bridge/next", headers=H).json()
    assert "Started automatically by Autopilot" in t2["task"]
    _finish(t2, v["stages"][1]["outputs"])


def test_autopilot_off_waits_for_the_user(bridge_mode):
    _drain()
    pid = _project()
    client.post(f"/api/v1/projects/{pid}/paper", json={"type": "research_article", "topic": "x"}, headers=H)
    t = client.post("/api/v1/bridge/next", headers=H).json()
    v = client.put(f"/api/v1/projects/{pid}/paper/autopilot", json={"on": False}, headers=H).json()
    assert v["autopilot"] is False
    _finish(t, v["stages"][0]["outputs"])
    v = client.post(f"/api/v1/projects/{pid}/paper/stages/{v['stages'][0]['id']}/approve", headers=H).json()
    assert v["stages"][1]["status"] == "ready"


def test_one_click_review_and_director_fallback(bridge_mode):
    _drain()
    pid = _project()
    up = client.post(f"/api/v1/projects/{pid}/files", headers=H, params={"folder": "uploads"},
                     files={"file": ("manuscript.pdf", b"%PDF-1.4", "application/pdf")}).json()["path"]
    out = client.post(f"/api/v1/projects/{pid}/autopilot/start", json={"files": [up]}, headers=H).json()
    assert out["mode"] == "recipe" and out["recipe"] == "review_paper" and "conv=" in out["url"]
    out = client.post(f"/api/v1/projects/{pid}/autopilot/start", json={"goal": "which dataset should I use?"}, headers=H).json()
    assert out["mode"] == "director" and "conv=" in out["url"]
    # A recipe whose required input is missing sends the user to its upload page instead.
    out = client.post(f"/api/v1/projects/{pid}/autopilot/start", json={"goal": "make slides for my talk"}, headers=H).json()
    assert out["mode"] == "recipe" and out["url"].startswith("/do/make_slides")
    _drain()
