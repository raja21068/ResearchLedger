"""Papers vs quick jobs: the project kind drives the sidebar's two lists."""
from webapi.tests.test_api import H, client


def test_quick_job_and_promotion():
    q = client.post("/api/v1/projects", json={"title": "Review TDSC submission", "kind": "quick"}, headers=H).json()
    p = client.post("/api/v1/projects", json={"title": "My paper"}, headers=H).json()
    assert q["kind"] == "quick" and p["kind"] == "paper"
    quick = {x["id"] for x in client.get("/api/v1/projects?kind=quick", headers=H).json()}
    papers = {x["id"] for x in client.get("/api/v1/projects?kind=paper", headers=H).json()}
    assert q["id"] in quick and q["id"] not in papers and p["id"] in papers
    assert client.post("/api/v1/projects", json={"title": "x", "kind": "other"}, headers=H).status_code == 422
    r = client.patch(f"/api/v1/projects/{q['id']}", json={"kind": "paper"}, headers=H).json()
    assert r["kind"] == "paper"


def test_classify_preview_and_repeat():
    c = lambda **b: client.post("/api/v1/autopilot/classify", json=b, headers=H).json()
    assert c(goal="write a full paper about zk oracles")["tool"] == "Write a paper (Paper Studio)"
    assert c(goal="review this", filenames=["main.tex"], repeat="review")["loop"] == "review_fix"
    bad = c(goal="review this", filenames=["paper.pdf"], repeat="review")
    assert bad["mode"] == "invalid" and ".tex" in bad["why"]
    assert c(goal="zk proofs for oracles", repeat="idea")["tool"] == "Improve an idea"


def test_starting_a_paper_makes_it_a_paper_project():
    q = client.post("/api/v1/projects", json={"title": "idea", "kind": "quick"}, headers=H).json()
    r = client.post(f"/api/v1/projects/{q['id']}/paper", json={"type": "research_article", "venue": "journal",
                                                               "topic": "x"}, headers=H)
    assert r.status_code == 201, r.text
    assert client.get(f"/api/v1/projects/{q['id']}", headers=H).json()["kind"] == "paper"


def test_dismiss_a_decision():
    from webapi.app import loops as lp
    p = client.post("/api/v1/projects", json={"title": "dismiss"}, headers=H).json()
    lid = client.post(f"/api/v1/projects/{p['id']}/loops", json={"type": "idea_forge", "goal": "x", "idea_text": "y" * 300},
                      headers=H).json()["id"]
    client.post(f"/api/v1/projects/{p['id']}/loops/{lid}/stop", headers=H)
    st = lp.load(p["id"], lid)
    st.update(status="finished", stop_reason="test")
    lp._save(p["id"], st)
    item = next(i for i in client.get("/api/v1/inbox", headers=H).json()["approve"] if i.get("loop_id") == lid)
    after = client.post("/api/v1/inbox/dismiss", json={"key": item["key"]}, headers=H).json()
    assert not any(i.get("loop_id") == lid for i in after["approve"])
