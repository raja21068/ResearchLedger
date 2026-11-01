"""Document tools: compare, targeted edit proposals (apply replaces exactly one passage), submission package."""
import json
import os
import zipfile
from pathlib import Path

import pytest

from webapi.tests.test_api import H, client

P1 = "The proposed method clearly outperforms every baseline on all datasets."
TEX = r"\section{Results}" + "\n" + P1 + r" See \cite{a}." + "\n\nSecond paragraph stays.\n"


@pytest.fixture
def paper(monkeypatch):
    monkeypatch.setenv("RL_EXECUTOR", "bridge")
    while client.post("/api/v1/bridge/next", headers=H).status_code == 200:
        pass
    p = client.post("/api/v1/projects", json={"title": "docs"}, headers=H).json()
    client.post(f"/api/v1/projects/{p['id']}/paper", json={"type": "research_article", "venue": "journal", "topic": "t"},
                headers=H)
    ws = Path(os.environ["RL_WEB_DATA"]) / "projects" / p["id"] / "workspace"
    (ws / "paper").mkdir(exist_ok=True)
    (ws / "paper" / "main.tex").write_text(TEX, encoding="utf-8")
    return p["id"], ws


def test_compare(paper):
    pid, ws = paper
    (ws / "paper" / "main_revised.tex").write_text(TEX.replace("clearly ", ""), encoding="utf-8")
    r = client.get(f"/api/v1/projects/{pid}/paper/compare", params={"a": "paper/main.tex", "b": "paper/main_revised.tex"}).json()
    assert r["added"] == 1 and r["removed"] == 1 and not r["identical"]
    assert client.get(f"/api/v1/projects/{pid}/paper/compare", params={"a": "../x", "b": "paper/main.tex"}).status_code == 400


def test_edit_proposal_apply_and_guards(paper):
    pid, ws = paper
    url = f"/api/v1/projects/{pid}/paper/edits"
    assert client.post(url, json={"file": "paper/main.tex", "selection": "not in file at all, sorry"}, headers=H).status_code == 400
    assert client.post(url, json={"file": "paper/main.tex", "selection": "short"}, headers=H).status_code == 400
    r = client.post(url, json={"file": "paper/main.tex", "selection": P1, "instruction": "tone down"}, headers=H)
    assert r.status_code == 201, r.text
    eid = r.json()["edit_id"]
    assert client.get(url).json()[0]["status"] == "waiting"
    assert client.post(f"{url}/{eid}/apply", headers=H).status_code == 400  # no proposal yet
    task = client.post("/api/v1/bridge/next", headers=H).json()
    assert f"paper/edits/{eid}.json" in task["task"] and "tone down" in task["task"] and P1 in task["task"]
    # Agent writes a proposal that sneaks in a new number.
    (ws / "paper" / "edits").mkdir(exist_ok=True)
    (ws / "paper" / "edits" / f"{eid}.json").write_text(json.dumps({
        "file": "paper/main.tex", "original": P1, "revised": "The method improves on most baselines by 12 points.",
        "rationale": "softer"}), encoding="utf-8")
    item = client.get(url).json()[0]
    assert item["status"] == "proposed" and any("12" in w for w in item["warnings"])
    assert client.post(f"{url}/{eid}/apply", headers=H).status_code == 200
    new = (ws / "paper" / "main.tex").read_text(encoding="utf-8")
    assert "improves on most baselines" in new and "Second paragraph stays." in new and P1 not in new
    assert (ws / "paper" / "edits" / "backups" / f"{eid}_main.tex").read_text(encoding="utf-8") == TEX
    assert client.get(url).json()[0]["status"] == "applied"
    assert client.post(f"{url}/{eid}/apply", headers=H).status_code == 400  # not twice


def test_package_contains_files_and_warns_about_placeholders(paper):
    pid, ws = paper
    (ws / "paper" / "main.tex").write_text(TEX + r"\PFVAL{acc}" + "\n", encoding="utf-8")
    (ws / "paper" / "refs.bib").write_text("@misc{a, title={x}}", encoding="utf-8")
    (ws / "paper" / "figures").mkdir()
    (ws / "paper" / "figures" / "f1.png").write_bytes(b"png")
    r = client.post(f"/api/v1/projects/{pid}/paper/package", headers=H)
    assert r.status_code == 201, r.text
    body = r.json()
    assert "main.tex" in body["files"] and "refs.bib" in body["files"] and "figures/f1.png" in body["files"]
    assert any("placeholder" in w for w in body["warnings"]) and any("PDF" in w for w in body["warnings"])
    with zipfile.ZipFile(ws / body["path"]) as z:
        assert "MANIFEST.json" in z.namelist()
        assert json.loads(z.read("MANIFEST.json"))["files"]["main.tex"]


def test_package_needs_a_manuscript():
    p = client.post("/api/v1/projects", json={"title": "empty"}, headers=H).json()
    assert client.post(f"/api/v1/projects/{p['id']}/paper/package", headers=H).status_code == 400
