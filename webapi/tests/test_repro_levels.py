"""Reproducibility levels are earned from recorded repeats only; independent replication is never automatic."""
import json

from webapi.tests.test_api import H, client, wait
from webapi.tests.test_lab import SCRIPT, _run_paper_experiment


def _repeat(pid, rid):
    r = client.post(f"/api/v1/projects/{pid}/lab/runs/{rid}/repeat", headers=H)
    assert r.status_code == 201, r.text
    rid2 = r.json()["run_id"]
    assert wait(rid2)["status"] == "succeeded"
    return rid2


def _level(pid, rid):
    runs = client.get(f"/api/v1/projects/{pid}/lab").json()["runs"]
    return next(r for r in runs if r["run_id"] == rid)["reproducibility"]


def test_a_single_run_is_level_one_and_says_nothing_about_repeating():
    pid, root, rid = _run_paper_experiment()
    lv = _level(pid, rid)
    assert lv["level"] == 1 and lv["label"] == "run once" and "never decided by the software" in lv["independent_replication"]
    ev = client.get(f"/api/v1/projects/{pid}/evidence").json()["evidence"][0]
    assert ev["repeatability"]["label"] == "run once"


def test_same_code_data_environment_and_values_is_level_two():
    pid, root, rid = _run_paper_experiment()
    rid2 = _repeat(pid, rid)
    lv = _level(pid, rid)
    assert lv["level"] == 2 and lv["repeats"][0] == {"run_id": rid2, "result": "same values", "same_environment": True}
    assert _level(pid, rid2)["label"] == "a repeat"
    assert client.get(f"/api/v1/projects/{pid}/evidence").json()["evidence"][0]["repeatability"]["level"] == 2


def test_same_values_in_a_different_environment_is_level_three():
    pid, root, rid = _run_paper_experiment()
    rid2 = _repeat(pid, rid)
    p = root / "results" / "receipts" / f"{rid2}.json"
    rc = json.loads(p.read_text(encoding="utf-8"))
    rc["receipt"]["environment"]["python"] = "3.99.0 (another machine)"
    p.write_text(json.dumps(rc), encoding="utf-8")
    lv = _level(pid, rid)
    assert lv["level"] == 3 and lv["repeats"][0]["same_environment"] is False


def test_a_repeat_with_changed_code_proves_nothing_and_different_values_are_reported():
    pid, root, rid = _run_paper_experiment()
    (root / "code" / "exp.py").write_text(SCRIPT.replace("VALUE", "8"), encoding="utf-8")
    rid2 = _repeat(pid, rid)                      # code changed after the original run
    lv = _level(pid, rid)
    assert lv["level"] == 1 and "not comparable" in lv["repeats"][0]["result"]
    (root / "code" / "exp.py").write_text(SCRIPT.replace("VALUE", "7"), encoding="utf-8")
    rid3 = _repeat(pid, rid)                      # same code again, then make the recorded value differ
    p = root / "results" / "receipts" / f"{rid3}.json"
    rc = json.loads(p.read_text(encoding="utf-8"))
    rc["jobs"][0]["slots"]["acc_main"]["value"] = 7.5
    p.write_text(json.dumps(rc), encoding="utf-8")
    lv = _level(pid, rid)
    assert lv["label"] == "not reproduced" and lv["not_reproduced"] is True
