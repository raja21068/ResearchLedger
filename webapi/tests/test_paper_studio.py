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


# ---------------------------------------------------------------- Run experiments (measured results)
LOG = """# Experimental log
| slot_id | metric | unit | dataset | method | value |
| --- | --- | --- | --- | --- | --- |
| acc_main | accuracy | % | D1 | ours | TBD |
| acc_base | accuracy | % | D1 | baseline | TBD |
| f1_main | F1 | - | D1 | ours | TBD |
"""


def test_experiments_stage_follows_code_and_collects_only_valid_results():
    from webapi.app import experiments
    pid, view = _paper()
    ids = [s["id"] for s in view["stages"]]
    assert ids.index("experiments") == ids.index("code") + 1 and ids.index("write") == ids.index("experiments") + 1
    root = _ws(pid)
    (root / "paper").mkdir(exist_ok=True)
    (root / "paper" / "experimental_log.md").write_text(LOG, encoding="utf-8")
    (root / "results").mkdir()
    (root / "results" / "acc_main.json").write_text(json.dumps({"slot_id": "acc_main", "value": 91.2, "seed": 1}))
    (root / "results" / "acc_base.json").write_text(json.dumps({"slot_id": "wrong", "value": 80}))  # name mismatch
    (root / "results" / "extra.json").write_text(json.dumps({"slot_id": "extra", "value": 1}))  # undeclared
    (root / "results" / "f1_main.json").write_text("not json")
    out = experiments.collect(root, "run_x")
    assert out["measured"] == 1 and out["pending"] == 2 and len(out["issues"]) == 3
    text = (root / "paper" / "experimental_log.md").read_text(encoding="utf-8")
    assert "| acc_main | accuracy | % | D1 | ours | 91.2 |" in text
    assert text.count("TBD") == 2  # unmeasured slots stay TBD
    prov = json.loads((root / "results" / "provenance.json").read_text())
    assert prov["acc_main"]["run_id"] == "run_x" and len(prov["acc_main"]["sha256"]) == 64
    # idempotent
    assert experiments.collect(root, "run_x")["measured"] == 1


def test_approving_experiments_collects_results(bridge_mode):
    while client.post("/api/v1/bridge/next", headers=H).status_code == 200:
        pass
    pid, _ = _paper()
    root = _ws(pid)
    st = json.loads((root / "paper" / "studio.json").read_text())
    for sid in ("idea", "literature", "method", "code"):
        st["stages"][sid] = {"approved_at": "2026-01-01T00:00:00+00:00"}
    (root / "paper" / "studio.json").write_text(json.dumps(st))
    (root / "paper" / "experimental_log.md").write_text(LOG, encoding="utf-8")
    client.post(f"/api/v1/projects/{pid}/paper/stages/experiments/run", json={}, headers=H)
    task = client.post("/api/v1/bridge/next", headers=H).json()
    assert "results/run_log.md" in task["task"] and "Do NOT edit" in task["task"]
    (root / "results").mkdir(exist_ok=True)
    (root / "results" / "acc_main.json").write_text(json.dumps({"slot_id": "acc_main", "value": 7}))
    _finish(task, ["results/run_log.md"])
    v = client.post(f"/api/v1/projects/{pid}/paper/stages/experiments/approve", headers=H).json()
    assert v["collected"]["measured"] == 1 and v["results"]["measured"] == 1
    assert "| 7 |" in (root / "paper" / "experimental_log.md").read_text(encoding="utf-8")
    assert client.post(f"/api/v1/projects/{pid}/paper/collect-results", headers=H).json()["measured"] == 1


def test_experiments_run_gets_python_tool_only_for_that_kind():
    from webapi.app import claude_runner
    from webapi.app.config import settings
    if not settings.claude_cmd:
        pytest.skip("claude not installed")
    assert "Bash(python:*)" in claude_runner.build_command(None, None, kind="paper:experiments")
    assert "Bash(python:*)" not in claude_runner.build_command(None, None, kind="paper:code")


# ---------------------------------------------------------------- review <-> revise loop
MATRIX = ("id,reviewer,severity,location,concern,quote,verification,minimum_fix,closure_criterion\n"
          "C1,R1,major,sec 3,Claim too strong,q,VERIFIED,fix,c\n"
          "C2,R2,minor,sec 4,Typo,q,VERIFIED,fix,c\n"
          "C3,R2,major,sec 5,Maybe wrong,q,UNVERIFIED,fix,c\n")


def _approved_up_to_revise(pid):
    root = _ws(pid)
    st = json.loads((root / "paper" / "studio.json").read_text())
    for sid in st["stages"]:
        st["stages"][sid] = {"approved_at": "2026-01-01T00:00:00+00:00"}
    (root / "paper" / "studio.json").write_text(json.dumps(st))
    return root


def test_review_loop_runs_until_no_verified_major_concern_is_open(bridge_mode):
    from webapi.app import review_loop
    while client.post("/api/v1/bridge/next", headers=H).status_code == 200:
        pass
    pid, _ = _paper()
    root = _approved_up_to_revise(pid)
    (root / "review").mkdir(exist_ok=True)
    # Refused until round 1 has a closure file.
    assert client.post(f"/api/v1/projects/{pid}/paper/review-rounds", headers=H).status_code == 400
    (root / "review" / "concern_matrix.csv").write_text(MATRIX, encoding="utf-8")
    (root / "review" / "closure.csv").write_text("id,status,evidence\nC1,open,x\nC2,resolved,y\nC3,open,z\n")
    (root / "paper").mkdir(exist_ok=True)
    (root / "paper" / "main_revised.tex").write_text("x")
    s = review_loop.summarize(root)
    assert s["rounds"][0]["open_verified_major"] == 1 and s["stop_reason"] is None  # C3 is UNVERIFIED: not counted

    r = client.post(f"/api/v1/projects/{pid}/paper/review-rounds", headers=H)
    assert r.status_code == 201
    assert r.json()["loop"]["running_round"] == 2
    assert client.post(f"/api/v1/projects/{pid}/paper/review-rounds", headers=H).status_code == 400  # already running
    task = client.post("/api/v1/bridge/next", headers=H).json()
    assert "round 2 of 3" in task["task"] and "review/round_2/closure.csv" in task["task"]
    assert "paper/main_revised.tex" in task["task"] and "C1" in task["task"]
    (root / "review" / "round_2").mkdir()
    (root / "review" / "round_2" / "concern_matrix.csv").write_text(MATRIX, encoding="utf-8")
    (root / "review" / "round_2" / "closure.csv").write_text("id,status,evidence\nC1,resolved,a\nC2,resolved,b\nC3,open,c\n")
    client.post(f"/api/v1/bridge/runs/{task['run_id']}/done", json={"summary": "ok"}, headers=H)
    v = client.get(f"/api/v1/projects/{pid}/paper").json()["loop"]
    assert v["stop_reason"] == "no verified major concern is open" and v["can_start"] is False
    assert [c["status"] for c in v["rounds"][1]["concerns"]] == ["resolved", "resolved", "open"]
    assert client.post(f"/api/v1/projects/{pid}/paper/review-rounds", headers=H).status_code == 400


def test_review_loop_stops_after_three_rounds():
    from webapi.app import review_loop
    pid, _ = _paper()
    root = _ws(pid)
    for n in (1, 2, 3):
        f = review_loop.round_files(n)
        (root / f["matrix"]).parent.mkdir(parents=True, exist_ok=True)
        (root / f["matrix"]).write_text(MATRIX, encoding="utf-8")
        (root / f["closure"]).write_text("id,status,evidence\nC1,open,x\n")
    s = review_loop.summarize(root)
    assert s["last_round"] == 3 and "3 rounds done" in s["stop_reason"]
