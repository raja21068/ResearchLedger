"""Lessons from other projects reach an agent only as labelled, unverified hints."""
from webapi.app import memory_store, workspace
from webapi.app.main import store
from webapi.tests.test_api import H, client


def _proj(title):
    return client.post("/api/v1/projects", json={"title": title}, headers=H).json()["id"]


def _text(pid):
    memory_store.render(store, pid)
    return (workspace.project_root(pid) / "memory" / "remembered.md").read_text(encoding="utf-8")


def test_a_related_projects_lesson_appears_labelled_as_not_checked_here():
    a, b = _proj("Fingerprint budget scaling for molecules"), _proj("Molecular fingerprint budget study two")
    memory_store.add(store, a, "failure", "Fingerprint budget is irrelevant for trees",
                     "Tree ensembles ignored the fingerprint budget in the pilot.", "user",
                     evidence=[{"kind": "file", "ref": "results/pilot.json"}])
    text = _text(b)
    assert "Lessons from other projects (not checked for this project)" in text
    assert "Fingerprint budget is irrelevant for trees" in text and "Fingerprint budget scaling for molecules" in text
    assert "never cite one as evidence" in text
    assert "results/pilot.json" in text                       # provenance travels with it
    assert "Lessons from other projects" not in _text(a) or "Fingerprint budget is irrelevant" not in \
        _text(a).split("Lessons from other projects")[-1]      # never echoed back to its owner as a "foreign" lesson


def test_unrelated_projects_stay_isolated_and_unapproved_lessons_never_travel():
    a, b, c = _proj("Glacier retreat satellite imagery"), _proj("Tokenizer vocabulary scaling"), _proj("Satellite glacier mapping")
    memory_store.add(store, a, "failure", "Cloud cover ruins glacier masks", "Masks failed under cloud.", "user")
    memory_store.add(store, a, "strategy", "Proposed only", "Agent suggestion not yet approved glacier.", "agent")
    assert "Cloud cover" not in _text(b)                       # different topic: nothing
    other = _text(c)
    assert "Cloud cover ruins glacier masks" in other and "Proposed only" not in other   # proposed memories stay home
    memory_store.add(store, a, "literature", "Glacier survey paper", "Some glacier paper.", "user")
    assert "Glacier survey paper" not in _text(c)             # papers are not lessons; they stay in their project
