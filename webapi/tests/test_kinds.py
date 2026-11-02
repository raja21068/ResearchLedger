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


def test_steps_menu_is_one_list_for_console_and_gui():
    r = client.get("/api/v1/steps", headers=H).json()
    assert [s["n"] for s in r["steps"]] == [1, 2, 3, 4, 5, 6, 7]
    assert all(s["href"] and s["console"] and s["engines"] for s in r["steps"])
    for s in r["steps"]:
        assert f"{s['n']}. {s['name']}" in r["menu"]
    assert "8. Guided paper" in r["menu"] and "0. Status" in r["menu"]


def test_start_steps_from_files_or_text():
    p = client.post("/api/v1/projects", json={"title": "steps", "kind": "quick"}, headers=H).json()["id"]
    up = lambda name, body: client.post(f"/api/v1/projects/{p}/files?folder=uploads", headers=H,
                                        files={"file": (name, body.encode(), "text/plain")}).json()["path"]
    go = lambda sid, **b: client.post(f"/api/v1/projects/{p}/steps/{sid}/start", json=b, headers=H)
    # Missing input -> one plain sentence saying what to add.
    r = go("check")
    assert r.status_code == 400 and ".tex" in r.json()["detail"]
    assert "paper" in go("review").json()["detail"]
    # Idea from a topic -> idea loop; experiments from text -> experiment loop.
    assert "/loops/" in go("idea", text="zero-knowledge proofs for AI oracles").json()["url"]
    assert "/loops/" in go("experiments", text="Compare with a keyword baseline").json()["url"]
    # Review with a .tex and pasted ChatGPT review -> review and fix loop.
    tex = up("main.tex", "\\documentclass{article}\\begin{document}x\\end{document}")
    assert "/loops/" in go("review", files=[tex], text="Reviewer: no baseline.").json()["url"]
    # Code from pasted text -> recipe chat.
    assert "?conv=" in go("code", text="A method that verifies VLM outputs on-chain.", options={"framework": "any"}).json()["url"]
    assert go("check", files=[tex]).json()["url"].startswith("/quality?")


def test_upload_zip_unpacks_safely():
    import io, zipfile
    p = client.post("/api/v1/projects", json={"title": "zip", "kind": "quick"}, headers=H).json()["id"]
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("paper/main.tex", "x"); z.writestr("../evil.tex", "x"); z.writestr("__MACOSX/a.tex", "x")
        z.writestr("paper/run.exe", "x")
    r = client.post(f"/api/v1/projects/{p}/files?folder=uploads&unzip=true", headers=H,
                    files={"file": ("draft.zip", buf.getvalue(), "application/zip")}).json()
    assert r["files"] == ["uploads/draft/paper/main.tex"]
