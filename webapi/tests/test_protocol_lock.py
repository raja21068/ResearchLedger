"""Methodology lock: approving the plan freezes the protocol and declared slots; changes block later stages until an
approved amendment; planned tables come from the slots; the draft must not contain results; old projects are unchanged."""
import json

from webapi.app import memory_store, paper_studio, protocol_lock
from webapi.app.main import store
from webapi.tests.test_api import H, client
from webapi.tests.test_paper_studio import _paper, _ws

PROTOCOL = "# Protocol\n\nDatasets: D1. Baselines: B1. Metric: accuracy. Seeds: 3. Falsifier: ours <= B1.\n"
LOG = ("# Experimental log\n| slot_id | metric | unit | dataset | method | value |\n| --- | --- | --- | --- | --- | --- |\n"
       "| acc_ours | accuracy | % | D1 | ours | TBD |\n| acc_base | accuracy | % | D1 | B1 | TBD |\n"
       "| f1_ours | F1 | - | D1 | ours | TBD |\n")


def _method_ready():
    pid, _ = _paper()
    root = _ws(pid)
    st = json.loads((root / "paper" / "studio.json").read_text())
    for sid in ("idea", "literature"):
        st["stages"][sid] = {"approved_at": "2026-01-01T00:00:00+00:00"}
    (root / "paper" / "studio.json").write_text(json.dumps(st))
    (root / "paper" / "protocol.md").write_text(PROTOCOL, encoding="utf-8")
    (root / "paper" / "experimental_log.md").write_text(LOG, encoding="utf-8")
    return pid, root


def _locked():
    pid, root = _method_ready()
    r = client.post(f"/api/v1/projects/{pid}/paper/stages/method/approve", headers=H)
    assert r.status_code == 200, r.text
    return pid, root


def _lock(pid):
    return client.get(f"/api/v1/projects/{pid}/paper/lock").json()


def test_new_research_papers_have_a_draft_stage_after_method_and_approving_method_locks_the_plan():
    pid, root = _locked()
    ids = [s["id"] for s in client.get(f"/api/v1/projects/{pid}/paper").json()["stages"]]
    assert ids.index("draft") == ids.index("method") + 1 and ids.index("draft") < ids.index("code")
    lk = _lock(pid)
    assert lk["locked"] and lk["version"] == 1 and not lk["changed"] and lk["planned_tables"]
    assert (root / "paper" / "locked" / "protocol.v1.md").read_text(encoding="utf-8") == PROTOCOL
    assert any("Protocol locked" in m["title"] for m in memory_store.search(store, pid, domains=["decision"]))
    tables = (root / "paper" / "planned_tables.md").read_text(encoding="utf-8")
    assert "Pending (`acc_ours`)" in tables and "| ours |" in tables and "TBD" not in tables
    assert "n/a" in tables  # B1 has no F1 slot


def test_changing_the_protocol_or_slots_blocks_later_stages_until_an_amendment_is_approved():
    pid, root = _locked()
    st = json.loads((root / "paper" / "studio.json").read_text())
    st["stages"]["draft"] = {"approved_at": "2026-01-02T00:00:00+00:00"}   # so Code is next in line
    (root / "paper" / "studio.json").write_text(json.dumps(st))
    (root / "paper" / "protocol.md").write_text(PROTOCOL.replace("Seeds: 3", "Seeds: 1"), encoding="utf-8")
    lk = _lock(pid)
    assert lk["changed"] and lk["protocol_changed"] and any("Seeds: 1" in l for l in lk["diff"])
    blocked = client.post(f"/api/v1/projects/{pid}/paper/stages/code/run", json={}, headers=H)
    assert blocked.status_code == 400 and "changed after the plan was locked" in blocked.text
    assert client.post(f"/api/v1/projects/{pid}/paper/stages/code/approve", headers=H).status_code == 400
    # an amendment needs a real reason
    short = client.post(f"/api/v1/projects/{pid}/paper/lock/amendments", json={"reason": "meh"}, headers=H)
    assert short.status_code == 400
    am = client.post(f"/api/v1/projects/{pid}/paper/lock/amendments", headers=H,
                     json={"reason": "One seed is enough for the pilot; the full run keeps three.", "affects": "all experiments"})
    assert am.status_code == 201 and am.json()["pending"]
    twice = client.post(f"/api/v1/projects/{pid}/paper/lock/amendments", json={"reason": "again, long enough"}, headers=H)
    assert twice.status_code == 400 and "already waiting" in twice.text
    # the stages after Method had been approved: approving the amendment reopens them
    st = json.loads((root / "paper" / "studio.json").read_text())
    st["stages"]["code"] = {"approved_at": "2026-01-02T00:00:00+00:00"}
    (root / "paper" / "studio.json").write_text(json.dumps(st))
    out = client.post(f"/api/v1/projects/{pid}/paper/lock/amendments/A1/decision", json={"approve": True}, headers=H).json()
    assert out["version"] == 2 and not out["changed"] and out["amendments"][0]["status"] == "approved"
    assert out["amendments"][0]["version_after"] == 2 and out["amendments"][0]["affects"] == "all experiments"
    assert "approved_at" not in json.loads((root / "paper" / "studio.json").read_text())["stages"]["code"]
    assert (root / "paper" / "locked" / "protocol.v1.md").read_text(encoding="utf-8") == PROTOCOL  # v1 is kept
    assert "Seeds: 1" in (root / "paper" / "locked" / "protocol.v2.md").read_text(encoding="utf-8")


def test_rejecting_an_amendment_or_restoring_puts_the_locked_protocol_back():
    pid, root = _locked()
    (root / "paper" / "protocol.md").write_text("# Protocol\n\nDatasets: D2.\n", encoding="utf-8")
    client.post(f"/api/v1/projects/{pid}/paper/lock/amendments", headers=H, json={"reason": "Switch to dataset D2, it is easier."})
    out = client.post(f"/api/v1/projects/{pid}/paper/lock/amendments/A1/decision", json={"approve": False}, headers=H).json()
    assert not out["changed"] and out["amendments"][0]["status"] == "rejected"
    assert (root / "paper" / "protocol.md").read_text(encoding="utf-8") == PROTOCOL
    (root / "paper" / "protocol.md").write_text("# edited again\n", encoding="utf-8")
    assert _lock(pid)["changed"]
    assert client.post(f"/api/v1/projects/{pid}/paper/lock/restore", headers=H).json()["changed"] is False


def test_declared_slot_changes_are_detected_and_restored_only_while_unmeasured():
    pid, root = _locked()
    (root / "paper" / "experimental_log.md").write_text(LOG.replace("| accuracy | % | D1 | ours", "| balanced accuracy | % | D1 | ours")
                                                         + "| extra | AUC | - | D1 | ours | TBD |\n", encoding="utf-8")
    lk = _lock(pid)
    assert lk["slots_changed"] == ["acc_ours"] and lk["slots_added"] == ["extra"] and not lk["protocol_changed"]
    # changing only a value (a measurement arriving) is not a change of the plan
    (root / "paper" / "experimental_log.md").write_text(LOG.replace("| ours | TBD |", "| ours | 91.2 |", 1), encoding="utf-8")
    assert not _lock(pid)["changed"]
    (root / "paper" / "experimental_log.md").write_text(LOG.replace("| accuracy | % | D1 | ours", "| balanced accuracy | % | D1 | ours"),
                                                         encoding="utf-8")
    out = client.post(f"/api/v1/projects/{pid}/paper/lock/restore", headers=H).json()
    assert out["changed"] is False and out["slots_note"] is None
    (root / "paper" / "experimental_log.md").write_text(LOG.replace("| ours | TBD |", "| ours | 91.2 |", 1).replace(
        "| accuracy | % | D1 | ours", "| balanced accuracy | % | D1 | ours"), encoding="utf-8")
    out = client.post(f"/api/v1/projects/{pid}/paper/lock/restore", headers=H).json()
    assert out["slots_note"] and "measured values" in out["slots_note"] and out["changed"]


def test_rerunning_the_method_stage_starts_a_fresh_lock_and_old_projects_are_unchanged():
    pid, root = _locked()
    client.post(f"/api/v1/projects/{pid}/paper/stages/method/run", json={}, headers=H)
    state = json.loads((root / "paper" / "studio.json").read_text())
    assert "lock" not in state and state["lock_history"][0]["version"] == 1
    # a project created before this feature has no draft stage and no lock gate
    old, _ = _paper()
    oroot = _ws(old)
    st = json.loads((oroot / "paper" / "studio.json").read_text())
    st.pop("pre_draft")
    st["stages"].pop("draft", None)
    (oroot / "paper" / "studio.json").write_text(json.dumps(st))
    ids = [s["id"] for s in client.get(f"/api/v1/projects/{old}/paper").json()["stages"]]
    assert "draft" not in ids and _lock(old)["locked"] is False


def test_a_plan_approved_before_locking_existed_can_be_locked_by_the_user():
    pid, root = _method_ready()
    assert client.post(f"/api/v1/projects/{pid}/paper/lock", headers=H).status_code == 400   # not approved yet
    st = json.loads((root / "paper" / "studio.json").read_text())
    st["stages"]["method"] = {"approved_at": "2026-01-01T00:00:00+00:00"}
    (root / "paper" / "studio.json").write_text(json.dumps(st))
    lk = _lock(pid)
    assert lk["method_approved"] and not lk["locked"]
    assert client.post(f"/api/v1/projects/{pid}/paper/lock", headers=H).status_code == 201
    assert _lock(pid)["locked"] and client.post(f"/api/v1/projects/{pid}/paper/lock", headers=H).status_code == 400


def test_the_pre_experiment_draft_must_not_contain_results():
    pid, root = _locked()
    assert protocol_lock.draft_report(root)["exists"] is False
    (root / "paper" / "pre_experiment_draft.md").write_text(
        "# Title\n## Introduction\nWe plan 3 seeds and use `acc_ours`.\n## Results\nOurs reaches 91.2% accuracy.\n"
        "## Conclusion\nIt works.\n", encoding="utf-8")
    rep = _lock(pid)["draft"]
    assert rep["exists"] and "91.2" in rep["result_numbers"] and "3" not in rep["result_numbers"]
    assert sorted(h.lstrip("# ").lower() for h in rep["forbidden_sections"]) == ["conclusion", "results"]
    (root / "paper" / "pre_experiment_draft.md").write_text("# Title\n## Introduction\nPlan with 3 seeds.\n", encoding="utf-8")
    rep = _lock(pid)["draft"]
    assert rep["result_numbers"] == [] and rep["forbidden_sections"] == []


def test_the_draft_stage_prompt_forbids_results_and_protocol_changes():
    stage = paper_studio.PRE_DRAFT
    assert "Do NOT write a Results" in stage["task"] and "Do not change the protocol" in stage["task"]
    assert stage["outputs"] == ["paper/pre_experiment_draft.md"]
