"""Experiment laboratory: receipts with code/data/environment fingerprints, repeats as new records that never change
the project's results, run comparison, and experiment lineage."""
import json

from webapi.app import loops, workspace
from webapi.tests.test_api import H, client, wait
from webapi.tests.test_paper_studio import _ready_for_experiments

SCRIPT = ("import json, pathlib\npathlib.Path('results').mkdir(exist_ok=True)\n"
          "pathlib.Path('results/acc_main.json').write_text(json.dumps({'slot_id': 'acc_main', 'value': VALUE}))\n")


def _run_paper_experiment():
    pid, root = _ready_for_experiments()
    (root / "code" / "exp.py").write_text(SCRIPT.replace("VALUE", "7"), encoding="utf-8")
    (root / "data").mkdir(exist_ok=True)
    (root / "data" / "tiny.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    (root / "code" / "jobs.json").write_text(json.dumps(
        {"jobs": [{"id": "E1", "command": "python code/exp.py", "slots": ["acc_main"], "timeout_minutes": 1}]}))
    v = client.post(f"/api/v1/projects/{pid}/paper/stages/experiments/run", json={}, headers=H).json()
    rid = next(s for s in v["stages"] if s["id"] == "experiments")["run_id"]
    assert wait(rid)["status"] == "succeeded"
    return pid, root, rid


def test_every_run_leaves_a_receipt_with_fingerprints():
    pid, root, rid = _run_paper_experiment()
    rc = json.loads((root / "results" / "receipts" / f"{rid}.json").read_text(encoding="utf-8"))
    assert rc["run_id"] == rid and rc["experiment"] == "paper"
    fp = rc["receipt"]
    assert len(fp["code"]["tree_sha256"]) == 64 and any(f["path"] == "code/exp.py" for f in fp["code"]["files"])
    assert fp["data"]["count"] == 1 and fp["environment"]["python"]
    lab = client.get(f"/api/v1/projects/{pid}/lab").json()
    assert any(e["id"] == "paper" for e in lab["experiments"])
    run = next(r for r in lab["runs"] if r["run_id"] == rid)
    assert run["values"] == {"acc_main": 7} and run["ok"] and not run["legacy"]
    # the live view gets one event per job state
    from webapi.app.main import store
    states = [e["payload"]["state"] for e in store.events_after(rid) if e["kind"] == "job"]
    assert states[:1] == ["queued"] and "running" in states and states[-1] == "done"


def test_repeat_is_a_new_record_and_does_not_change_results():
    pid, root, rid = _run_paper_experiment()
    (root / "code" / "exp.py").write_text(SCRIPT.replace("VALUE", "8"), encoding="utf-8")  # code changed since
    r = client.post(f"/api/v1/projects/{pid}/lab/runs/{rid}/repeat", headers=H)
    assert r.status_code == 201, r.text
    rid2 = r.json()["run_id"]
    assert rid2 != rid and wait(rid2)["status"] == "succeeded"
    assert json.loads((root / "results" / "acc_main.json").read_text())["value"] == 7  # project results untouched
    rc2 = client.get(f"/api/v1/projects/{pid}/lab/runs/{rid2}").json()
    assert rc2["repeat_of"] == rid and rc2["jobs"][0]["slots"]["acc_main"]["value"] == 8
    cmp = client.get(f"/api/v1/projects/{pid}/lab/compare", params={"a": rid, "b": rid2}).json()
    assert cmp["same_values"] is False and cmp["slots"][0]["diff"] == 1
    assert cmp["code_same"] is False and cmp["changed_files"]["code"] == ["code/exp.py"] and cmp["data_same"] is True
    # both receipts are still there
    assert {rid, rid2} <= {x["run_id"] for x in client.get(f"/api/v1/projects/{pid}/lab").json()["runs"]}


def test_lineage_links_and_refuses_cycles():
    pid = client.post("/api/v1/projects", json={"title": "Lineage"}, headers=H).json()["id"]
    root = workspace.project_root(pid)
    for lid in ("lop_a", "lop_b"):
        d = root / "loops" / lid
        d.mkdir(parents=True)
        (d / "state.json").write_text(json.dumps({"id": lid, "type": "experiment", "goal": lid, "status": "finished",
                                                  "rounds": {}, "inputs": {}}), encoding="utf-8")
    assert client.post(f"/api/v1/projects/{pid}/lab/parent", json={"loop_id": "lop_b", "parent": "lop_a"},
                       headers=H).status_code == 200
    bad = client.post(f"/api/v1/projects/{pid}/lab/parent", json={"loop_id": "lop_a", "parent": "lop_b"}, headers=H)
    assert bad.status_code == 400 and "loop of parents" in bad.text
    nodes = {n["id"]: n for n in client.get(f"/api/v1/projects/{pid}/lab").json()["experiments"]}
    assert nodes["lop_b"]["parent"] == "lop_a" and loops.load(pid, "lop_b")["parent"] == "lop_a"


def test_old_run_logs_still_show_as_legacy_runs():
    pid = client.post("/api/v1/projects", json={"title": "Legacy"}, headers=H).json()["id"]
    d = workspace.project_root(pid) / "loops" / "lop_old" / "round_1"
    d.mkdir(parents=True)
    (d / "run_log.json").write_text(json.dumps({"run_id": "run_old1", "finished_at": "2026-11-01T00:00:00+00:00",
                                                "jobs": [{"id": "E1", "exit_code": 0, "ok": True, "slots": {
                                                    "x": {"ok": True, "value": 3}}}]}), encoding="utf-8")
    runs = client.get(f"/api/v1/projects/{pid}/lab").json()["runs"]
    assert runs[0]["run_id"] == "run_old1" and runs[0]["legacy"] and runs[0]["experiment"] == "lop_old"
