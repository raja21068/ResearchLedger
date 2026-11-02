"""Research loops: idea forge and review -> fix, driven through the Claude app bridge with offline fixtures."""
import json
import urllib.error
from pathlib import Path

import pytest

from webapi.app import autopilot, loops, refcheck
from webapi.tests.test_api import H, client
from webapi.tests.test_autopilot import _drain

GOOD = {f"10.1000/p{i}": f"Competing paper number {i} on verifiable oracles" for i in range(80)}


def fake_fetch(url):
    if "api.crossref.org" in url:
        doi = url.split("/works/")[1]
        if doi not in GOOD:
            raise urllib.error.HTTPError(url, 404, "nf", {}, None)
        return json.dumps({"message": {"title": [GOOD[doi]], "issued": {"date-parts": [[2025]]}}})
    raise OSError("offline")


@pytest.fixture
def bridge(monkeypatch):
    monkeypatch.setenv("RL_EXECUTOR", "bridge")
    monkeypatch.setattr(refcheck, "fetcher", lambda: fake_fetch)
    _drain()
    yield
    _drain()


def _project():
    return client.post("/api/v1/projects", json={"title": "Loop project"}, headers=H).json()["id"]


def _task():
    r = client.post("/api/v1/bridge/next", headers=H)
    assert r.status_code == 200, r.text
    return r.json()


def _do(files: dict, expect_kind: str | None = None):
    """Claim the queued move, write its files, finish it. Returns the task."""
    t = _task()
    if expect_kind:
        assert t["kind"] == expect_kind, t["kind"]
    ws = Path(t["workspace"])
    for rel, content in files.items():
        p = ws / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    client.post(f"/api/v1/bridge/runs/{t['run_id']}/done", json={"summary": "done", "claim": t["claim"]}, headers=H)
    return t


def _competitors(n, bad_doi=None):
    rows = [",".join(loops.COMPETITOR_COLS)]
    for i in range(n):
        doi = bad_doi if (bad_doi and i == 0) else f"10.1000/p{i}"
        title = GOOD.get(doi, "A paper that does not exist")
        rows.append(f"c{i},{title},2025,NeurIPS,{doi},,,1,does part of it")
    return "\n".join(rows) + "\n"


def _score(novelty, total_claim=None, flaws=()):
    crit = {k: round(v * 0.8) for k, v in loops.RUBRIC.items()}
    crit["novelty"] = novelty
    return json.dumps({"criteria": crit, "total": total_claim if total_claim is not None else sum(crit.values()),
                       "fatal_flaws": list(flaws), "closest_competitors": ["c1: same mechanism"], "verdict": "ok"})


def _get(pid, lid):
    return client.get(f"/api/v1/projects/{pid}/loops/{lid}", headers=H).json()


IDEA = "Use zero-knowledge proofs to let a VLM oracle attest which image regions it read. " * 5


@pytest.mark.parametrize("goal,files,loop", [
    ("Why is this idea not novel? attack it", [], "idea_forge"),
    ("generate a research idea on blockchain and LLM", [], "idea_forge"),
    ("Review my paper and fix it until it is clean", ["main.tex"], "review_fix"),
])
def test_classify_loops(goal, files, loop):
    d = autopilot.classify(goal, files)
    assert d["mode"] == "loop" and d["loop"] == loop


def test_classify_keeps_full_paper_and_plain_review():
    assert autopilot.classify("Write a full paper about this idea", [])["mode"] == "paper"
    assert autopilot.classify("review my paper and fix it", ["paper.pdf"])["mode"] == "recipe"


def test_idea_forge_until_pass(bridge):
    pid = _project()
    r = client.post(f"/api/v1/projects/{pid}/loops", json={"type": "idea_forge", "goal": "verifiable VLM oracles",
                                                          "idea_text": IDEA}, headers=H)
    assert r.status_code == 201, r.text
    lid = r.json()["id"]
    d = f"loops/{lid}"
    t = _do({f"{d}/round_1/competitors.csv": _competitors(55), f"{d}/round_1/attack.md": "closest: c1"},
            "loop:idea_forge:attack")
    assert "at least 50 papers" in t["task"] and "standing instructions" in t["instructions"]
    v = _get(pid, lid)
    ev = v["rounds"][0]["evidence"]
    assert ev["ok"] and ev["papers"] == 55 and ev["verified"] == 12 and v["move"] == "score"
    # Low score with a fatal flaw; the claimed total is wrong and gets recomputed.
    _do({f"{d}/round_1/scorecard.json": _score(8, total_claim=99, flaws=["c3 already does this"])})
    v = _get(pid, lid)
    m = v["rounds"][0]["metrics"]
    assert m["total"] != 99 and m["total_corrected"] and v["move"] == "redesign"
    _do({f"{d}/round_1/idea.md": "Redesigned: attest regions with succinct proofs and a new theory. " * 10})
    v = _get(pid, lid)
    assert v["round"] == 2 and v["move"] == "attack"
    _do({f"{d}/round_2/competitors.csv": _competitors(60), f"{d}/round_2/attack.md": "gap remains"})
    _get(pid, lid)
    _do({f"{d}/round_2/scorecard.json": _score(18)})
    v = _get(pid, lid)
    assert v["status"] == "finished" and v["stop_reason"].startswith("passed") and v["best_round"] == 2
    assert v["final_files"] == [f"{d}/round_1/idea.md"]
    inbox = client.get("/api/v1/inbox", headers=H).json()
    assert any(i["kind"] == "loop" and i["loop_id"] == lid for i in inbox["approve"])
    a = client.post(f"/api/v1/projects/{pid}/loops/{lid}/accept", headers=H).json()
    assert a["accepted"] and a["accepted_files"] == [f"ideas/final_idea_{lid}.md"]


def test_fabricated_reference_blocks_pass(bridge):
    pid = _project()
    lid = client.post(f"/api/v1/projects/{pid}/loops", json={"type": "idea_forge", "goal": "x", "idea_text": IDEA,
                                                            "params": {"verify_sample": 80}}, headers=H).json()["id"]
    d = f"loops/{lid}"
    _do({f"{d}/round_1/competitors.csv": _competitors(55, bad_doi="10.1000/invented"), f"{d}/round_1/attack.md": "a"})
    v = _get(pid, lid)
    ev = v["rounds"][0]["evidence"]
    assert not ev["ok"] and ev["fabricated_or_wrong"] == 1
    _do({f"{d}/round_1/scorecard.json": _score(19)})
    v = _get(pid, lid)
    assert v["status"] == "running" and v["move"] == "redesign"  # a perfect score cannot pass on a fake reference
    client.post(f"/api/v1/projects/{pid}/loops/{lid}/stop", headers=H)
    assert _get(pid, lid)["status"] == "stopped"


def test_too_few_papers_blocks_pass(bridge):
    pid = _project()
    lid = client.post(f"/api/v1/projects/{pid}/loops", json={"type": "idea_forge", "goal": "x", "idea_text": IDEA},
                      headers=H).json()["id"]
    d = f"loops/{lid}"
    _do({f"{d}/round_1/competitors.csv": _competitors(12), f"{d}/round_1/attack.md": "a"})
    ev = _get(pid, lid)["rounds"][0]["evidence"]
    assert not ev["ok"] and "only 12 papers" in ev["problems"][0]
    client.post(f"/api/v1/projects/{pid}/loops/{lid}/stop", headers=H)


TEX = r"""\documentclass{article}
\begin{document}
We claim our method is optimal in every setting.
The experiments use three datasets.
\end{document}
"""


def _concerns(rows):
    out = [",".join(loops.CONCERN_COLS)]
    for cid, sev, quote, ver in rows:
        out.append(f'{cid},{sev},Sec 1,overclaim,"{quote}",{ver},soften')
    return "\n".join(out) + "\n"


def test_review_fix_loop(bridge):
    pid = _project()
    tid = _task_ws(pid)
    (tid / "paper").mkdir(exist_ok=True)
    (tid / "paper" / "main.tex").write_text(TEX, encoding="utf-8")
    r = client.post(f"/api/v1/projects/{pid}/loops", json={"type": "review_fix", "manuscript": "paper/main.tex",
                                                          "external_review": "ChatGPT says: claims are too strong.",
                                                          "mode": "step"}, headers=H)
    assert r.status_code == 201, r.text
    lid = r.json()["id"]
    d = f"loops/{lid}"
    t = _do({f"{d}/round_1/concerns.csv": _concerns([("M1", "major", "our method is optimal in every setting", "VERIFIED"),
                                                     ("M2", "major", "this sentence is not in the paper", "VERIFIED")]),
             f"{d}/round_1/review.md": "r", f"{d}/round_1/scores.json": '{"overall": 4}'}, "loop:review_fix:review")
    assert "external_review.md" in t["task"]
    v = _get(pid, lid)
    m = v["rounds"][0]["metrics"]
    assert m["verified_major"] == 1 and m["downgraded"] == 1 and v["move"] == "plan"
    _do({f"{d}/round_1/fix_instructions.md": "## M1\nReplace 'optimal in every setting' with 'competitive'. " * 3,
         f"{d}/round_1/triage.csv": "id,action,reason\nM1,text_fix,overclaim\nM2,new_experiment,needs a run\n"})
    v = _get(pid, lid)
    assert v["rounds"][0]["moves"][1]["status"] == "done" and [e["id"] for e in v["needs_experiments"]] == ["M2"]
    fixed = loops._fixed_tex(loops.load(pid, lid), 1)
    # First attempt changes the template: rejected and retried automatically.
    _do({fixed: TEX.replace("{article}", "{report}"), fixed[:-4] + ".pdf": "%PDF"})
    v = _get(pid, lid)
    fix = v["rounds"][0]["moves"][2]
    assert fix["attempt"] == 2 and v["status"] == "running"
    t = _task()
    assert "documentclass" in t["task"] and "rejected" in t["task"]
    ws = Path(t["workspace"])
    (ws / fixed).write_text(TEX.replace("optimal in every setting", "competitive on the tested settings"), encoding="utf-8")
    (ws / (fixed[:-4] + ".pdf")).write_text("%PDF", encoding="utf-8")
    (ws / d / "round_1" / "closure.csv").write_text(
        "id,status,location,new_text\nM1,resolved,Sec 1,competitive on the tested settings\n", encoding="utf-8")
    client.post(f"/api/v1/bridge/runs/{t['run_id']}/done", json={"summary": "done", "claim": t["claim"]}, headers=H)
    v = _get(pid, lid)
    assert v["status"] == "paused" and v["rounds"][0]["fix"]["change_ratio"] == 0.2   # step mode waits for a click
    client.post(f"/api/v1/projects/{pid}/loops/{lid}/steer", json={"text": "keep the abstract as is"}, headers=H)
    client.post(f"/api/v1/projects/{pid}/loops/{lid}/continue", headers=H)
    t = _do({f"{d}/round_2/concerns.csv": _concerns([("m3", "minor", "three datasets", "VERIFIED")]),
             f"{d}/round_2/review.md": "r", f"{d}/round_2/scores.json": '{"overall": 7}'})
    assert "keep the abstract as is" in t["task"] and fixed in t["task"]
    v = _get(pid, lid)
    assert v["status"] == "finished" and v["stop_reason"].startswith("clean") and v["best_round"] == 2
    assert v["final_files"] == [fixed, fixed[:-4] + ".pdf"]


def _task_ws(pid):
    from webapi.app import workspace
    return workspace.project_root(pid)


def test_failed_move_is_retried_then_fails(bridge):
    pid = _project()
    lid = client.post(f"/api/v1/projects/{pid}/loops", json={"type": "idea_forge", "goal": "x", "idea_text": IDEA},
                      headers=H).json()["id"]
    _do({})
    assert _get(pid, lid)["status"] == "running"     # second attempt queued with the reason
    _do({})
    v = _get(pid, lid)
    assert v["status"] == "failed" and "missing" in v["stop_reason"]
    assert any(i.get("loop_id") == lid for i in client.get("/api/v1/inbox", headers=H).json()["retry"])
    client.post(f"/api/v1/projects/{pid}/loops/{lid}/retry", headers=H)
    assert _get(pid, lid)["status"] == "running"
    client.post(f"/api/v1/projects/{pid}/loops/{lid}/stop", headers=H)


def test_one_click_start_creates_loop(bridge):
    pid = _project()
    out = client.post(f"/api/v1/projects/{pid}/autopilot/start",
                      json={"goal": "Why is my idea not novel? Attack it and redesign", "files": []}, headers=H).json()
    assert out["mode"] == "loop" and out["url"].endswith(out["loop_id"])
    t = _task()
    assert t["kind"] == "loop:idea_forge:seed"
    client.post(f"/api/v1/bridge/runs/{t['run_id']}/done", json={"summary": "x", "claim": t["claim"]}, headers=H)
    client.post(f"/api/v1/projects/{pid}/loops/{out['loop_id']}/stop", headers=H)


def test_preferences_round_trip(bridge):
    p = client.get("/api/v1/preferences", headers=H).json()
    assert p["enabled"] and any("surgical" in r.lower() or "surgically" in r.lower() for r in p["rules"])
    client.put("/api/v1/preferences", json={"enabled": False, "rules": p["rules"]}, headers=H)
    pid = _project()
    client.post(f"/api/v1/projects/{pid}/loops", json={"type": "idea_forge", "goal": "x", "idea_text": IDEA}, headers=H)
    t = _task()
    assert "standing instructions" not in t["instructions"]
    client.post(f"/api/v1/bridge/runs/{t['run_id']}/done", json={"summary": "x", "claim": t["claim"]}, headers=H)
    assert client.post("/api/v1/preferences/reset", headers=H).json()["enabled"]


TEX_T = r"""\documentclass{article}
\begin{document}
\begin{abstract}Our method reaches 81.2\% accuracy.\end{abstract}
We claim our method is the best.
\begin{table}\begin{tabular}{ll}Ours & 81.2 \\ Base & 77.4 \\\end{tabular}\end{table}
\end{document}
"""
SCORES = '{"quality": %s, "impact": %s, "novelty": %s, "methods": %s, "readiness": %s, "overall": 7}'


def _review_round(d, n, quote, scores, sev="major"):
    return {f"{d}/round_{n}/concerns.csv": _concerns([(f"M{n}", sev, quote, "VERIFIED")]),
            f"{d}/round_{n}/review.md": "r", f"{d}/round_{n}/scores.json": SCORES % scores}


def _start_rf(pid, tex=TEX_T):
    ws = _task_ws(pid)
    (ws / "paper").mkdir(exist_ok=True)
    (ws / "paper" / "main.tex").write_text(tex, encoding="utf-8")
    (ws / "results").mkdir(exist_ok=True)
    (ws / "results" / "main.json").write_text('{"acc": 0.8123, "baseline": 77.41}', encoding="utf-8")
    return client.post(f"/api/v1/projects/{pid}/loops", json={"type": "review_fix", "manuscript": "paper/main.tex"},
                       headers=H).json()["id"]


def test_fix_may_not_introduce_untraced_numbers(bridge):
    pid = _project()
    lid = _start_rf(pid)
    d = f"loops/{lid}"
    _do(_review_round(d, 1, "We claim our method is the best", (6, 6, 6, 6, 6)))
    _get(pid, lid)
    _do({f"{d}/round_1/fix_instructions.md": "## M1\nSoften the claim and add the gain. " * 4,
         f"{d}/round_1/triage.csv": "id,action,reason\nM1,text_fix,overclaim\n"})
    _get(pid, lid)
    fixed = loops._fixed_tex(loops.load(pid, lid), 1)
    invented = TEX_T.replace("Base & 77.4", "Base & 77.4 \\\\ Strong & 79.9")    # 79.9 is in no result file
    _do({fixed: invented, fixed[:-4] + ".pdf": "%PDF",
         f"{d}/round_1/closure.csv": "id,status,location,new_text\nM1,resolved,T1,Strong & 79.9\n"})
    v = _get(pid, lid)
    fx = v["rounds"][0]["moves"][2]
    assert fx["attempt"] == 2 and "79.9" in fx["last_error"] and v["status"] == "running"
    # Second attempt narrows the claim, but the closure claims text that is not in the paper.
    _do({fixed: TEX_T.replace("the best", "competitive on two benchmarks"), fixed[:-4] + ".pdf": "%PDF",
         f"{d}/round_1/closure.csv": "id,status,location,new_text\nM1,resolved,S1,we added a new robustness study\n"})
    v = _get(pid, lid)
    assert v["status"] == "failed" and "new_text is not in the revised" in v["stop_reason"]
    client.post(f"/api/v1/projects/{pid}/loops/{lid}/stop", headers=H)


def _plan_and_fix(pid, lid, d, n, action, new_text_sub, closure):
    _do({f"{d}/round_{n}/fix_instructions.md": "## fix\nSoften. " * 20,
         f"{d}/round_{n}/triage.csv": f"id,action,reason\nM{n},{action},needs work\n"})
    _get(pid, lid)
    st = loops.load(pid, lid)
    new = (_task_ws(pid) / loops._manuscript_for(st, n)).read_text(encoding="utf-8").replace(*new_text_sub)
    fixed = loops._fixed_tex(st, n)
    _do({fixed: new, fixed[:-4] + ".pdf": "%PDF", f"{d}/round_{n}/closure.csv": closure})
    return _get(pid, lid)


def test_review_fix_targets_met(bridge):
    pid = _project()
    lid = _start_rf(pid)
    d = f"loops/{lid}"
    _do(_review_round(d, 1, "We claim our method is the best", (6, 6, 6, 6, 6)))
    _get(pid, lid)
    v = _plan_and_fix(pid, lid, d, 1, "text_fix", ("the best", "competitive"),
                      "id,status,location,new_text\nM1,resolved,S1,our method is competitive\n")
    assert v["rounds"][0]["fix"]["gate"]["ready"] is not None and v["move"] == "review"
    _do({f"{d}/round_2/concerns.csv": _concerns([("m9", "minor", "accuracy", "VERIFIED")]),
         f"{d}/round_2/review.md": "r", f"{d}/round_2/scores.json": SCORES % (8.2, 9.1, 8.5, 8.4, 7.5)})
    v = _get(pid, lid)
    assert v["status"] == "finished" and v["stop_reason"].startswith("targets met")


def test_review_fix_plateau_names_experiments(bridge):
    pid = _project()
    lid = _start_rf(pid)
    d = f"loops/{lid}"
    _do(_review_round(d, 1, "We claim our method is the best", (5, 6, 5, 4, 5)))
    _get(pid, lid)
    _plan_and_fix(pid, lid, d, 1, "new_experiment", ("the best", "competitive"), "id,status,location,new_text\nM1,open,S1,\n")
    _do(_review_round(d, 2, "We claim our method is competitive", (5, 6, 5, 4.2, 5)))
    v = _get(pid, lid)
    assert v["status"] == "finished" and v["stop_reason"].startswith("plateau") and "M1" in v["stop_reason"]
    assert "M1" in (_task_ws(pid) / d / "needs_experiments.md").read_text(encoding="utf-8")
