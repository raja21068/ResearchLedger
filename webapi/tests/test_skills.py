"""Skill tools: discovery from skill folders and running a task through a skill."""
import os
import time
from pathlib import Path

from webapi.app import skills_catalog
from webapi.tests.test_api import H, client


def _fake_root(tmp: Path) -> Path:
    d = tmp / "7-grant-proposal"
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text('---\nname: grant-proposal\ndescription: "Draft a grant proposal. Use when user says x"\n---\n# Steps\n',
                                encoding="utf-8")
    (d / "template.md").write_text("T", encoding="utf-8")
    (tmp / ".claude" / "copy").mkdir(parents=True)
    (tmp / ".claude" / "copy" / "SKILL.md").write_text("---\nname: ignored\n---\n", encoding="utf-8")
    (tmp / "pack.zip").write_bytes(b"PK")
    return tmp


def test_scan_finds_unpacked_skills_and_skips_worktrees(tmp_path, monkeypatch):
    monkeypatch.setenv("RL_SKILL_ROOTS", str(_fake_root(tmp_path)))
    c = skills_catalog.catalog(refresh=True)
    assert [s["id"] for s in c["skills"]] == ["skill-grant-proposal"]
    s = c["skills"][0]
    assert s["category"] == "Grant Proposal" and s["description"] == "Draft a grant proposal."
    assert c["zipped_packages"] == 1


def test_task_through_skill_stages_a_copy_and_runs(tmp_path, monkeypatch):
    monkeypatch.setenv("RL_SKILL_ROOTS", str(_fake_root(tmp_path)))
    skills_catalog.catalog(refresh=True)
    p = client.post("/api/v1/projects", json={"title": "Skill project"}, headers=H).json()
    r = client.post(f"/api/v1/projects/{p['id']}/tasks", headers=H,
                    json={"prompt": "Write a proposal on X", "skill_id": "skill-grant-proposal"}).json()
    end = time.time() + 30
    while client.get(f"/api/v1/runs/{r['run_id']}").json()["status"] in {"queued", "running"} and time.time() < end:
        time.sleep(0.2)
    conv = client.get(f"/api/v1/conversations/{r['conversation_id']}").json()
    assert conv["title"].startswith("Grant proposal")
    assert ".skills/skill-grant-proposal/SKILL.md" in conv["runs"][0]["prompt"]
    staged = Path(os.environ["RL_WEB_DATA"]) / "projects" / p["id"] / "workspace" / ".skills" / "skill-grant-proposal"
    assert (staged / "template.md").is_file()
    # The staged copy is hidden from the file list.
    assert not any(f["path"].startswith(".skills") for f in client.get(f"/api/v1/projects/{p['id']}/files").json())
    skills_catalog.catalog(refresh=True)


def test_plain_task_and_unknown_skill():
    p = client.post("/api/v1/projects", json={"title": "Task project"}, headers=H).json()
    ok = client.post(f"/api/v1/projects/{p['id']}/tasks", json={"prompt": "hello"}, headers=H)
    assert ok.status_code == 201
    bad = client.post(f"/api/v1/projects/{p['id']}/tasks", json={"prompt": "x", "skill_id": "skill-nope"}, headers=H)
    assert bad.status_code == 404
