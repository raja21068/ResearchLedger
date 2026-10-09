import json

from researchledger.migrate import migrate_v1_to_v2
from researchledger.migrate import render as render_migration
from researchledger.models import Claim, Decision, Evidence
from researchledger.workspace import init_workspace

V1_EVIDENCE = """---
name: E001
type: experiment-evidence
status: supported
source_kind: experiment
supports: C001
---

# Evidence: E001

## Claim
The baseline is not robust.
"""

V1_CLAIM = """---
name: C001
type: research-claim
status: supported
evidence: E001
---

# Claim: C001

## Statement
The baseline is not robust to corruption.
"""


def _write_v1_workspace(tmp_path):
    ws = init_workspace(tmp_path)
    ws.evidence_dir.mkdir(parents=True, exist_ok=True)
    ws.claims_dir.mkdir(parents=True, exist_ok=True)
    (ws.evidence_dir / "E001.md").write_text(V1_EVIDENCE, encoding="utf-8")
    (ws.claims_dir / "C001.md").write_text(V1_CLAIM, encoding="utf-8")
    return ws


def test_migrate_rewrites_status_vocabulary_and_schema_version(tmp_path):
    ws = _write_v1_workspace(tmp_path)
    report = migrate_v1_to_v2(ws)

    assert report.evidence_migrated == 1
    assert report.claims_migrated == 1
    assert report.malformed == []

    ev = Evidence.load(ws.evidence_dir / "E001.md")
    assert ev.schema_version == "2.0"
    assert ev.status == "checked"  # v1 'supported' -> v2 'checked'
    assert ev.supports == ["C001"]

    cl = Claim.load(ws.claims_dir / "C001.md")
    assert cl.schema_version == "2.0"
    assert cl.status == "provisional"  # recomputed from 'checked' evidence, never blindly renamed
    assert cl.evidence == ["E001"]


def test_migrate_dry_run_does_not_touch_files(tmp_path):
    ws = _write_v1_workspace(tmp_path)
    original = (ws.evidence_dir / "E001.md").read_text(encoding="utf-8")

    report = migrate_v1_to_v2(ws, dry_run=True)

    assert report.evidence_migrated == 1
    assert (ws.evidence_dir / "E001.md").read_text(encoding="utf-8") == original
    assert not (ws.root / "backup").exists()
    assert not (ws.root / "migration-report.json").exists()


def test_migrate_creates_backup_and_report(tmp_path):
    ws = _write_v1_workspace(tmp_path)
    report = migrate_v1_to_v2(ws)

    assert report.backup_dir is not None
    assert (ws.root / report.backup_dir / "research" / "evidence" / "E001.md").exists()

    report_path = ws.root / "migration-report.json"
    assert report_path.exists()
    data = json.loads(report_path.read_text(encoding="utf-8"))
    assert data["evidence_migrated"] == 1


def test_migrate_is_idempotent_on_already_v2_files(tmp_path):
    ws = _write_v1_workspace(tmp_path)
    migrate_v1_to_v2(ws)
    second_report = migrate_v1_to_v2(ws)
    assert second_report.evidence_migrated == 0
    assert second_report.claims_migrated == 0
    assert second_report.already_v2 == 2


def test_migrate_rewrites_decisions_too(tmp_path):
    ws = _write_v1_workspace(tmp_path)
    ws.decisions_dir.mkdir(parents=True, exist_ok=True)
    (ws.decisions_dir / "D001.md").write_text(
        "---\nname: D001\ntype: research-decision\nstatus: decided\nevidence: E001\n---\n\n"
        "# Decision: D001\n\n## Decision\nProceed with the baseline.\n",
        encoding="utf-8",
    )

    report = migrate_v1_to_v2(ws)
    assert report.decisions_migrated == 1

    dec = Decision.load(ws.decisions_dir / "D001.md")
    assert dec.schema_version == "2.0"
    assert dec.evidence == ["E001"]


def test_migrate_flags_malformed_decision_without_aborting(tmp_path):
    ws = _write_v1_workspace(tmp_path)
    ws.decisions_dir.mkdir(parents=True, exist_ok=True)
    (ws.decisions_dir / "D002.md").write_bytes(b"\xff\xfe broken decision file")

    report = migrate_v1_to_v2(ws)
    assert report.claims_migrated == 1
    assert any("D002.md" in entry["path"] for entry in report.malformed)


def test_migrate_render_includes_backup_and_malformed_summary(tmp_path):
    ws = _write_v1_workspace(tmp_path)
    (ws.evidence_dir / "E002.md").write_bytes(b"\xff\xfe not valid utf-8")

    report = migrate_v1_to_v2(ws)
    text = render_migration(report)
    assert "1 evidence record(s) migrated" in text
    assert "1 file(s) require manual review" in text
    assert "E002.md" in text
    assert "Backup written to" in text


def test_migrate_flags_evidence_that_fails_to_load_after_parsing(tmp_path, monkeypatch):
    """Frontmatter parses fine (so the earlier OSError/UnicodeDecodeError
    guard doesn't fire), but Evidence.load itself still blows up — a
    defensive branch that's hard to trigger with a real file, so it's
    exercised directly."""
    import researchledger.migrate as migrate_module

    ws = _write_v1_workspace(tmp_path)

    def _boom(path):
        raise RuntimeError("unexpected shape")

    monkeypatch.setattr(migrate_module.Evidence, "load", staticmethod(_boom))
    report = migrate_v1_to_v2(ws)
    assert report.evidence_migrated == 0
    assert any("unexpected shape" in entry["reason"] for entry in report.malformed)


def test_migrate_flags_claim_that_fails_to_load_after_parsing(tmp_path, monkeypatch):
    import researchledger.migrate as migrate_module

    ws = _write_v1_workspace(tmp_path)

    def _boom(path):
        raise RuntimeError("unexpected claim shape")

    monkeypatch.setattr(migrate_module.Claim, "load", staticmethod(_boom))
    report = migrate_v1_to_v2(ws)
    assert report.claims_migrated == 0
    assert any("unexpected claim shape" in entry["reason"] for entry in report.malformed)


def test_migrate_flags_decision_that_fails_to_load_after_parsing(tmp_path, monkeypatch):
    import researchledger.migrate as migrate_module

    ws = _write_v1_workspace(tmp_path)
    ws.decisions_dir.mkdir(parents=True, exist_ok=True)
    (ws.decisions_dir / "D001.md").write_text(
        "---\nname: D001\ntype: research-decision\nstatus: decided\nevidence: E001\n---\n\n# Decision: D001\n",
        encoding="utf-8",
    )

    def _boom(path):
        raise RuntimeError("unexpected decision shape")

    monkeypatch.setattr(migrate_module.Decision, "load", staticmethod(_boom))
    report = migrate_v1_to_v2(ws)
    assert report.decisions_migrated == 0
    assert any("unexpected decision shape" in entry["reason"] for entry in report.malformed)


def test_migrate_already_v2_decision_is_left_alone(tmp_path):
    ws = _write_v1_workspace(tmp_path)
    ws.decisions_dir.mkdir(parents=True, exist_ok=True)
    (ws.decisions_dir / "D001.md").write_text(
        "---\nschema_version: '2.0'\nname: D001\ntype: research-decision\nstatus: decided\nevidence: [E001]\n---\n\n"
        "# Decision: D001\n",
        encoding="utf-8",
    )

    report = migrate_v1_to_v2(ws)
    assert report.decisions_migrated == 0
    assert report.already_v2 >= 1


def test_migrate_flags_malformed_files_without_aborting(tmp_path):
    ws = _write_v1_workspace(tmp_path)
    (ws.evidence_dir / "E002.md").write_bytes(b"\xff\xfe not valid utf-8 frontmatter")

    report = migrate_v1_to_v2(ws)
    assert report.evidence_migrated == 1  # E001 still migrates despite E002 being broken
    assert len(report.malformed) == 1
    assert "E002.md" in report.malformed[0]["path"]
