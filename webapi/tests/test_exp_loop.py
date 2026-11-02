"""Experiment loop: pre-registered plan -> code -> server run after a click -> analysis checked against the criteria."""
import json
import time

from webapi.tests.test_api import H, client
from webapi.tests.test_loops import _do, _get, _project, bridge  # noqa: F401  (fixture)

PLAN = {"experiments": [
    {"id": "E1", "question": "Does the verifier beat the baseline?", "hypothesis": "ours > base",
     "slots": ["e1_ours", "e1_base"], "baselines": "keyword matcher", "data": "data/toy.csv",
     "command": "python code/experiments/e1.py", "expected_minutes": 1,
     "success": {"slot": "e1_ours", "op": ">", "than": "e1_base"}},
    {"id": "E2", "question": "Scale to 7B?", "hypothesis": "holds at 7B", "slots": ["e2_f1"], "runnable": False,
     "blocker": "needs a GPU with 40 GB"},
]}

SCRIPT = """import json, pathlib
out = pathlib.Path('results'); out.mkdir(exist_ok=True)
for slot, v in {'e1_ours': 0.81, 'e1_base': 0.74}.items():
    (out / f'{slot}.json').write_text(json.dumps({'slot_id': slot, 'value': v, 'unit': 'F1', 'seed': 7}))
print('done')
"""
BROKEN = "import json\nraise SystemExit('dataset not found')\n"


def _start(pid, **kw):
    r = client.post(f"/api/v1/projects/{pid}/loops", json={"type": "experiment",
                                                          "experiments_text": "Reviewer 2: compare against a keyword baseline.",
                                                          **kw}, headers=H)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _wait_run(pid, lid, timeout=60):
    t0 = time.time()
    while time.time() - t0 < timeout:
        v = _get(pid, lid)
        if v["move"] != "run":
            return v
        time.sleep(0.3)
    raise AssertionError("server run did not finish")


def test_experiment_loop_end_to_end(bridge):
    pid = _project()
    lid = _start(pid)
    d = f"loops/{lid}"
    t = _do({f"{d}/round_1/exp_plan.json": json.dumps(PLAN), f"{d}/round_1/design.md": "plan"}, "loop:experiment:design")
    assert "pre-registered" in t["task"] and "keyword baseline" not in t["task"]  # the request is a file it reads
    v = _get(pid, lid)
    assert v["move"] == "code" and v["preregistration"]["experiments"][0]["criterion"] == "e1_ours > e1_base"
    assert v["pending"] == ["E1"]  # E2 is blocked, never run
    _do({"code/experiments/e1.py": SCRIPT, f"{d}/round_1/code.md": "how"}, "loop:experiment:code")
    v = _get(pid, lid)
    # Running code always waits for the user's click.
    assert v["status"] == "paused" and v["awaiting"] == "run" and "python code/experiments/e1.py" in v["paused_reason"]
    inbox = client.get("/api/v1/inbox", headers=H).json()
    assert any(i.get("loop_id") == lid for i in inbox["approve"])
    client.post(f"/api/v1/projects/{pid}/loops/{lid}/continue", headers=H)
    v = _wait_run(pid, lid)
    assert v["move"] == "analyze", v
    run = v["rounds"][0]["run"]
    assert run["ok"] == 1 and run["measured_now"] == 2 and run["jobs"][0]["exit_code"] == 0
    # The analysis may not contradict the pre-registered criterion, nor quote numbers that were never measured.
    _do({f"{d}/round_1/verdicts.json": json.dumps({"E1": {"verdict": "not_supported", "reason": "x"}}),
         f"{d}/round_1/analysis.md": "## E1\nOurs reached 0.95 F1."})
    v = _get(pid, lid)
    analyze = v["rounds"][0]["moves"][-1]
    assert analyze["status"] == "running" and "marked not_supported" in analyze["last_error"]
    assert "0.95" in analyze["last_error"]
    _do({f"{d}/round_1/verdicts.json": json.dumps({"E1": {"verdict": "supported", "reason": "0.81 vs 0.74"}}),
         f"{d}/round_1/analysis.md": "## E1\nOurs 0.81 vs baseline 0.74 F1 (seed 7).\n## E2\nBlocked: no GPU."})
    v = _get(pid, lid)
    assert v["status"] == "finished", v
    assert "1 of 1 experiment(s) measured" in v["stop_reason"] and "supported: E1" in v["stop_reason"]
    assert "blocked (cannot run here): E2" in v["stop_reason"]
    assert f"{d}/round_1/analysis.md" in v["final_files"] and "results/e1_ours.json" in v["final_files"]
    m = v["measured"]["e1_ours"]
    assert m["value"] == 0.81 and m["script"] == "code/experiments/e1.py" and len(m["script_sha256"]) == 64


def test_code_move_may_not_write_results(bridge):
    pid = _project()
    lid = _start(pid)
    d = f"loops/{lid}"
    _do({f"{d}/round_1/exp_plan.json": json.dumps(PLAN), f"{d}/round_1/design.md": "plan"})
    _get(pid, lid)
    _do({"code/experiments/e1.py": SCRIPT, f"{d}/round_1/code.md": "how",
         "results/e1_ours.json": json.dumps({"slot_id": "e1_ours", "value": 0.99})})
    v = _get(pid, lid)
    code = v["rounds"][0]["moves"][1]
    assert code["move"] == "code" and "only the approved run may write them" in code["last_error"]
    client.post(f"/api/v1/projects/{pid}/loops/{lid}/stop", headers=H)


def test_bad_plan_is_rejected(bridge):
    pid = _project()
    lid = _start(pid)
    d = f"loops/{lid}"
    bad = {"experiments": [{"id": "E1", "hypothesis": "h", "slots": ["a"], "command": "bash run.sh"},
                           {"id": "E2", "hypothesis": "h", "slots": ["b"], "command": "python ../outside.py",
                            "success": {"slot": "b", "op": ">", "value": 1}},
                           {"id": "E3", "hypothesis": "h", "slots": ["c"], "runnable": False}]}
    _do({f"{d}/round_1/exp_plan.json": json.dumps(bad), f"{d}/round_1/design.md": "plan"})
    err = _get(pid, lid)["rounds"][0]["moves"][0]["last_error"]
    assert "`python <script.py> [args]`" in err and "inside the workspace" in err and "no blocker" in err
    client.post(f"/api/v1/projects/{pid}/loops/{lid}/stop", headers=H)


def test_failing_script_goes_back_to_code_then_stops(bridge):
    pid = _project()
    lid = _start(pid, params={"max_rounds": 2})
    d = f"loops/{lid}"
    _do({f"{d}/round_1/exp_plan.json": json.dumps(PLAN), f"{d}/round_1/design.md": "plan"})
    _get(pid, lid)
    _do({"code/experiments/e1.py": BROKEN, f"{d}/round_1/code.md": "how"})
    _get(pid, lid)
    client.post(f"/api/v1/projects/{pid}/loops/{lid}/continue", headers=H)
    v = _wait_run(pid, lid)
    assert v["round"] == 2 and v["move"] == "code" and v["rounds"][0]["run"]["failed"] == 1
    t = _do({"code/experiments/e1.py": BROKEN, f"{d}/round_2/code.md": "still"}, "loop:experiment:code")
    assert "dataset not found" in t["task"] and "do not weaken the experiment" in t["task"]
    v = _get(pid, lid)
    assert v["status"] == "paused" and v["awaiting"] == "run"
    client.post(f"/api/v1/projects/{pid}/loops/{lid}/continue", headers=H)
    v = _wait_run(pid, lid)
    assert v["status"] == "finished" and "still failing: E1" in v["stop_reason"]
    assert not v.get("measured")
