"""Evidence ledger bridge: recorded runs become sealed ledger runs with observed evidence; pre-registered verdicts
become claims bound to that evidence; only the user's review changes evidence status, and claim status follows the
ledger's own rules."""
import json

from webapi.app import workspace
from webapi.tests.test_api import H, client
from webapi.tests.test_lab import _run_paper_experiment


def _ev(pid):
    return client.get(f"/api/v1/projects/{pid}/evidence").json()


def test_recorded_runs_become_observed_evidence_in_a_valid_ledger():
    pid, root, rid = _run_paper_experiment()
    ov = _ev(pid)
    assert ov["valid"], ov["issues"]
    assert len(ov["evidence"]) == 1 and ov["evidence"][0]["status"] == "observed"
    assert ov["evidence"][0]["values"] == {"acc_main": 7} and ov["evidence"][0]["app_ref"] == f"{rid}:E1"
    assert ov["runs"][0]["reproducibility"] == "NOT_INDEPENDENTLY_REPRODUCED"
    assert (root / "research" / "runs" / ov["runs"][0]["id"] / "manifest.json").is_file()
    again = _ev(pid)  # idempotent
    assert len(again["evidence"]) == 1 and again["sync"]["evidence_added"] == 0


def test_claim_status_follows_the_users_review_of_evidence():
    pid, root, rid = _run_paper_experiment()
    eid = _ev(pid)["evidence"][0]["id"]
    r = client.post(f"/api/v1/projects/{pid}/claims", headers=H,
                    json={"statement": "Our method reaches 7 on the main metric.", "supports": [eid]})
    assert r.status_code == 201
    cid = r.json()["id"]
    claim = lambda: next(c for c in _ev(pid)["claims"] if c["id"] == cid)  # noqa: E731
    assert claim()["status"] == "provisional"  # observed support only
    bad = client.post(f"/api/v1/projects/{pid}/evidence/{eid}/status", headers=H, json={"status": "verified", "reason": " "})
    assert bad.status_code == 400 and "why" in bad.text
    ok = client.post(f"/api/v1/projects/{pid}/evidence/{eid}/status", headers=H,
                     json={"status": "verified", "reason": "Repeated run gave the same value."})
    assert ok.status_code == 200, ok.text
    assert claim()["status"] == "supported"
    blocked = client.post(f"/api/v1/projects/{pid}/evidence/{eid}/status", headers=H,
                          json={"status": "invalidated", "reason": "bug"})
    assert blocked.status_code == 400 and f"only support of claim {cid}" in blocked.text
    assert client.post(f"/api/v1/projects/{pid}/claims/{cid}/withdraw", headers=H,
                       json={"reason": "The script had a bug."}).status_code == 200
    assert client.post(f"/api/v1/projects/{pid}/evidence/{eid}/status", headers=H,
                       json={"status": "invalidated", "reason": "bug"}).status_code == 200
    assert claim()["status"] == "withdrawn" and _ev(pid)["valid"]
    t = client.get(f"/api/v1/projects/{pid}/ledger/trace/{cid}").json()
    assert eid in t["text"]
    assert client.post(f"/api/v1/projects/{pid}/evidence/{eid}/status", headers=H,
                       json={"status": "supported", "reason": "x"}).status_code == 400


def test_preregistered_verdicts_become_claims_bound_to_their_runs():
    pid = client.post("/api/v1/projects", json={"title": "Ledger loop"}, headers=H).json()["id"]
    root = workspace.project_root(pid)
    base = root / "loops" / "lop_pre1"
    (base / "round_1").mkdir(parents=True)
    (base / "state.json").write_text(json.dumps({"id": "lop_pre1", "type": "experiment", "goal": "g", "status": "finished",
                                                 "created_at": "2026-11-02T00:00:00+00:00", "rounds": {}}), encoding="utf-8")
    (base / "preregistration.json").write_text(json.dumps({"experiments": [
        {"id": "E1", "question": "Valid?", "hypothesis": "Never overclaims.", "success": {"slot": "v", "op": "<=", "value": 0}},
        {"id": "E2", "question": "Powerful?", "hypothesis": "Detects range 1.", "success": {"slot": "p", "op": ">=", "value": 0.8}}]}),
        encoding="utf-8")
    (base / "round_1" / "verdicts.json").write_text(json.dumps({"E1": {"verdict": "supported"}, "E2": {"verdict": "not_supported"}}),
                                                    encoding="utf-8")
    (base / "round_1" / "run_log.json").write_text(json.dumps({"run_id": "run_pre1", "finished_at": "2026-11-02T01:00:00+00:00",
        "jobs": [{"id": "E1", "command": "python code/x.py --exp E1", "exit_code": 0, "ok": True, "slots": {"v": {"ok": True, "value": 0}}},
                 {"id": "E2", "command": "python code/x.py --exp E2", "exit_code": 0, "ok": True, "slots": {"p": {"ok": True, "value": 0.0}}}]}),
        encoding="utf-8")
    ov = _ev(pid)
    assert ov["valid"], ov["issues"]
    claims = {c["name"].split(":")[0]: c for c in ov["claims"]}
    assert claims["E1"]["status"] == "provisional" and len(claims["E1"]["evidence"]) == 1
    assert claims["E2"]["status"] == "hypothesis" and len(claims["E2"]["contradicts"]) == 1  # observed: weak
    e2 = claims["E2"]["contradicts"][0]
    r = client.post(f"/api/v1/projects/{pid}/evidence/{e2}/status", headers=H,
                    json={"status": "checked", "reason": "Read the analysis; the verdict follows the locked rule."})
    assert r.status_code == 200, r.text
    claims = {c["name"].split(":")[0]: c for c in _ev(pid)["claims"]}
    assert claims["E2"]["status"] == "contradicted"
    assert _ev(pid)["sync"] == {"evidence_added": 0, "claims_added": 0}
