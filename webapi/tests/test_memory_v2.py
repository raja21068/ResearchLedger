"""Research memory v2: sourced memories, approval of agent proposals, corrections that keep history, conflicts,
search, and failed directions fed in automatically from recorded loop outcomes."""
import json

from fastapi.testclient import TestClient

from webapi.app import memory_store, workspace
from webapi.app.main import app, store

H = {"x-rl-client": "test"}
client = TestClient(app)


def _project():
    return client.post("/api/v1/projects", json={"title": "Memory"}, headers=H).json()["id"]


def test_user_memory_is_active_sourced_and_reaches_agents():
    pid = _project()
    r = client.post(f"/api/v1/projects/{pid}/memory", headers=H, json={
        "domain": "decision", "title": "Use scaffold splits", "content": "Random splits overstate accuracy.",
        "sources": [{"kind": "doi", "ref": "10.1000/example"}]})
    assert r.status_code == 201 and r.json()["status"] == "active"
    item = client.get(f"/api/v1/memory/{r.json()['id']}").json()
    assert item["evidence"][0]["ref"] == "10.1000/example" and item["history"][0]["action"] == "created"
    text = (workspace.project_root(pid) / "memory" / "remembered.md").read_text(encoding="utf-8")
    assert "Use scaffold splits" in text and "doi: 10.1000/example" in text


def test_agent_proposals_wait_for_the_user_and_show_in_decisions():
    pid = _project()
    p = workspace.project_root(pid) / "memory" / "proposals.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"memories": [{"domain": "failure", "title": "Hash folding hurt small sets",
                                           "content": "Collisions at 1024 bits.", "sources": [{"kind": "file", "ref": "logs/x.json"}]},
                                          {"domain": "bogus", "title": "x", "content": "y"}]}), encoding="utf-8")
    assert memory_store.ingest_proposals(store, pid, None) == 1 and not p.exists()
    m = memory_store.search(store, pid, statuses=["proposed"])[0]
    assert m["origin"] == "agent"
    inbox = client.get("/api/v1/inbox").json()
    assert any(x.get("memory_id") == m["id"] for x in inbox["approve"])
    assert "Hash folding" not in (workspace.project_root(pid) / "memory" / "remembered.md").read_text(encoding="utf-8")
    r = client.post(f"/api/v1/memory/{m['id']}/decision", json={"approve": True}, headers=H)
    assert r.json()["status"] == "active"
    assert "Hash folding" in (workspace.project_root(pid) / "memory" / "remembered.md").read_text(encoding="utf-8")


def test_correction_supersedes_and_keeps_the_old_version():
    pid = _project()
    old = memory_store.add(store, pid, "strategy", "Tune radius by CV", "Always tune.", "user")
    r = client.post(f"/api/v1/memory/{old['id']}/correct", json={"content": "Tune only above 2k molecules."}, headers=H)
    new = r.json()
    assert new["supersedes"] == old["id"] and new["status"] == "active"
    o = client.get(f"/api/v1/memory/{old['id']}").json()
    assert o["status"] == "superseded" and o["superseded_by"] == new["id"] and o["content"] == "Always tune."


def test_same_title_is_flagged_as_a_possible_conflict():
    pid = _project()
    a = memory_store.add(store, pid, "decision", "Primary metric", "Use AUROC.", "user")
    b = memory_store.add(store, pid, "decision", "primary metric!", "Use AUPRC.", "user")
    assert b["status"] == "needs_review" and b["conflict_with"] == a["id"]


def test_search_finds_by_words_and_keeps_projects_apart():
    p1, p2 = _project(), _project()
    memory_store.add(store, p1, "literature", "Sort and Slice beats hashing", "Frequency selection of ECFP.", "user")
    memory_store.add(store, None, "strategy", "Pre-register before running", "Lock criteria first.", "user")
    hits = client.get("/api/v1/memory", params={"project_id": p1, "q": "hashing"}).json()
    assert [h["title"] for h in hits] == ["Sort and Slice beats hashing"]
    other = client.get("/api/v1/memory", params={"project_id": p2}).json()
    titles = {h["title"] for h in other}
    assert "Sort and Slice beats hashing" not in titles and "Pre-register before running" in titles


def test_loop_outcomes_become_failure_memories_once():
    pid = _project()
    root = workspace.project_root(pid)
    base = root / "loops" / "lop_test1"
    (base / "round_1").mkdir(parents=True)
    (base / "idea_0.md").write_text("# Certified property range\n", encoding="utf-8")
    (base / "round_1" / "scorecard.json").write_text("{}", encoding="utf-8")
    (base / "state.json").write_text(json.dumps({
        "id": "lop_test1", "type": "idea_forge", "params": {"target_total": 75}, "status": "finished",
        "rounds": {"1": {"metrics": {"total": 57, "fatal_flaws": ["method is known"], "verdict": "Not novel."}}}}),
        encoding="utf-8")
    exp = root / "loops" / "lop_test2"
    (exp / "round_1").mkdir(parents=True)
    (exp / "preregistration.json").write_text(json.dumps({"experiments": [
        {"id": "E2", "question": "Does the bound have power?", "hypothesis": "r_hat >= 1 for TPSA"}]}), encoding="utf-8")
    (exp / "round_1" / "verdicts.json").write_text(json.dumps({"E2": {"verdict": "not_supported", "reason": "never 1"}}),
                                                   encoding="utf-8")
    (exp / "state.json").write_text(json.dumps({"id": "lop_test2", "type": "experiment", "status": "finished",
                                                "rounds": {"1": {}}}), encoding="utf-8")
    assert memory_store.ingest_loops(store, pid) == 2
    assert memory_store.ingest_loops(store, pid) == 0  # idempotent
    fails = memory_store.search(store, pid, domains=["failure"])
    titles = {f["title"] for f in fails}
    assert "Idea did not pass: Certified property range" in titles
    assert any(t.startswith("E2 not supported") for t in titles)
    text = (root / "memory" / "remembered.md").read_text(encoding="utf-8")
    assert "Failed or rejected directions" in text and "loops/lop_test2/round_1/verdicts.json" in text


def test_bad_input_is_refused_in_plain_words():
    pid = _project()
    r = client.post(f"/api/v1/projects/{pid}/memory", headers=H, json={"domain": "rumour", "title": "x", "content": "y"})
    assert r.status_code == 400 and "domain must be one of" in r.text


def _review_files(root):
    (root / "paper").mkdir(exist_ok=True)
    (root / "review").mkdir(exist_ok=True)
    (root / "paper" / "main.tex").write_text(
        "We compare against nothing. The model is best. All values are placeholders.", encoding="utf-8")
    (root / "paper" / "main_revised.tex").write_text(
        "We compare against baseline B1 with identical splits. This is a study protocol.", encoding="utf-8")
    (root / "review" / "concern_matrix.csv").write_text(
        "id,reviewer,severity,location,concern,quote,verification,minimum_fix,closure_criterion\n"
        "MC1,Methodology,Major,Results,No baseline comparison is reported,We compare against nothing,VERIFIED,Add a justified baseline,Baseline present\n"
        "MC2,Methodology,Major,Results,Claims are too strong,The model is best,UNVERIFIED,Narrow the claim,Narrowed\n"
        "MC3,Statistics,Major,Abstract,Quote is not in the manuscript,this sentence does not exist anywhere,VERIFIED,Fix,Done\n"
        "MC4,Statistics,Minor,Intro,Placeholders everywhere,All values are placeholders,VERIFIED,Fill them or say protocol,Stated\n",
        encoding="utf-8")


def test_only_verified_findings_with_real_quotes_become_memories_and_resolution_supersedes():
    pid = _project()
    root = workspace.project_root(pid)
    _review_files(root)
    assert memory_store.ingest_reviews(store, pid) == 2           # MC1 and MC4 only
    assert memory_store.ingest_reviews(store, pid) == 0           # idempotent
    open_items = memory_store.search(store, pid, domains=["failure"], statuses=["active"])
    assert sorted(m["title"][:30] for m in open_items) == ["Reviewer finding (major, open)", "Reviewer finding (minor, open)"]
    titles = " ".join(m["title"] for m in memory_store.search(store, pid, statuses=["active"]))
    assert "Claims are too strong" not in titles and "does not exist" not in titles
    # the finding is resolved later; the closure's text is (or is not) in the revised manuscript
    (root / "review" / "closure.csv").write_text(
        "id,status,evidence\nMC1,resolved,\"Added baseline B1 with identical splits (main_revised.tex).\"\n", encoding="utf-8")
    assert memory_store.ingest_reviews(store, pid) == 1
    mc1 = [m for m in memory_store.search(store, pid, statuses=["superseded"]) if "No baseline" in m["title"]]
    assert len(mc1) == 1 and "open" in mc1[0]["title"]
    resolved = [m for m in memory_store.search(store, pid, domains=["strategy"], statuses=["active"])][0]
    d = client.get(f"/api/v1/memory/{resolved['id']}").json()
    assert d["supersedes"] == mc1[0]["id"] and "Lesson:" in d["content"] and "reported by the agent" in d["content"]
    assert any(e["kind"] == "file" and e["ref"] == "review/concern_matrix.csv" for e in d["evidence"])
    text = (root / "memory" / "remembered.md").read_text(encoding="utf-8")
    assert "Reviewer finding (major, resolved)" in text and "Reviewer finding (minor, open)" in text
    assert "No baseline comparison is reported" in text and text.count("Reviewer finding (major") == 1
