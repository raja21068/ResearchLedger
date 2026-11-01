"""Smart recipes: engines resolve, stored prompts are injected, inputs are checked, suggestions route sensibly."""
import zipfile
from pathlib import Path

import pytest

from webapi.app import recipes
from webapi.tests.test_api import H, client


@pytest.fixture
def bridge_mode(monkeypatch):
    monkeypatch.setenv("RL_EXECUTOR", "bridge")


@pytest.fixture
def library(tmp_path, monkeypatch):
    lib = tmp_path / "prompts"
    lib.mkdir()
    for r in recipes.R.values():
        for p in r["prompts"]:
            (lib / p).write_text(f"STORED PROMPT {p}", encoding="utf-8")
    monkeypatch.setattr(recipes, "PROMPTS", lib)
    return lib


def _project_with(files):
    p = client.post("/api/v1/projects", json={"title": "Recipe project"}, headers=H).json()
    paths = []
    for name, data in files:
        r = client.post(f"/api/v1/projects/{p['id']}/files", headers=H, params={"folder": "uploads"},
                        files={"file": (name, data, "application/octet-stream")})
        assert r.status_code == 201, r.text
        paths.append(r.json()["path"])
    return p["id"], paths


def test_every_recipe_is_public_and_complete():
    rs = client.get("/api/v1/recipes").json()
    assert {r["id"] for r in rs} == set(recipes.R)
    for r in rs:
        assert r["inputs"] and r["outputs"] and r["engines"]


def test_suggestions_route_by_files_and_words():
    s = lambda f, t="": client.post("/api/v1/recipes/suggest", json={"filenames": f, "text": t}, headers=H).json()  # noqa: E731
    assert s(["my_manuscript.pdf"])[0]["id"] == "review_paper"
    assert s(["paper.docx", "reviewer_comments.docx"])[0]["id"] == "respond_to_reviewers"
    assert s(["mine.pdf", "reference_q1.pdf"], "make it look like this style")[0]["id"] == "match_reference_style"
    assert s([], "brainstorm ideas on blockchain and LLM")[0]["id"] == "generate_ideas"
    assert s(["a.pdf", "b.pdf", "c.pdf"])[0]["id"] == "understand_papers"


def test_review_recipe_runs_with_engine_and_stored_prompt(bridge_mode, library):
    while client.post("/api/v1/bridge/next", headers=H).status_code == 200:
        pass
    pid, paths = _project_with([("paper.pdf", b"%PDF-1.4")])
    r = client.post(f"/api/v1/projects/{pid}/recipes/review_paper/run", headers=H,
                    json={"files": {"paper": paths}, "options": {"journal": "IEEE TNNLS"}})
    assert r.status_code == 201, r.text
    task = client.post("/api/v1/bridge/next", headers=H).json()
    assert "STORED PROMPT 8-1. REVIEWER SIMULATION.txt" in task["task"]
    assert "IEEE TNNLS" in task["task"] and "uploads/paper.pdf" in task["task"]
    if recipes.engine_dir("beihang_referee"):
        assert "BEIHANG_REFEREE_PROMPT.md" in task["task"]
    client.post(f"/api/v1/bridge/runs/{task['run_id']}/done", json={"summary": "ok"}, headers=H)


def test_missing_required_upload_and_wrong_type_are_refused(library):
    pid, paths = _project_with([("notes.csv", b"a,b\n")])
    url = f"/api/v1/projects/{pid}/recipes"
    assert client.post(f"{url}/review_paper/run", json={"files": {}}, headers=H).status_code == 400
    bad = client.post(f"{url}/review_paper/run", json={"files": {"paper": paths}}, headers=H)
    assert bad.status_code == 400 and "expected" in bad.json()["detail"]
    assert client.post(f"{url}/generate_ideas/run", json={"options": {}}, headers=H).status_code == 400


def test_zipped_engine_is_unpacked_once_and_safely(tmp_path, monkeypatch):
    z = tmp_path / "agent.zip"
    with zipfile.ZipFile(z, "w") as f:
        f.writestr("agent/SKILL.md", "# skill")
        f.writestr("../evil.txt", "x")
        f.writestr("agent/$out/junk.md", "x")
    monkeypatch.setitem(recipes.ENGINES, "test_zip", {"label": "t", "kind": "zip", "path": z, "entry": ["agent/SKILL.md"]})
    d = recipes.engine_dir("test_zip")
    assert (d / "agent" / "SKILL.md").is_file()
    assert not (d.parent / "evil.txt").exists() and not (d / "agent" / "$out").exists()
    mtime = (d / "agent" / "SKILL.md").stat().st_mtime_ns
    assert recipes.engine_dir("test_zip") == d and (d / "agent" / "SKILL.md").stat().st_mtime_ns == mtime
