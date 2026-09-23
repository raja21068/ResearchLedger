import json

from researchledger.models import Claim, Evidence
from researchledger.validate_paper import audit_paper
from researchledger.workspace import init_workspace


def _seed_graph(ws, *, evidence_status="verified", run_exit_code=0):
    run_dir = ws.runs_dir / "R0001"
    run_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema_version": "2.0",
        "run_id": "R0001",
        "status": "completed" if run_exit_code == 0 else "failed",
        "started_at": "2026-01-01T00:00:00Z",
        "finished_at": "2026-01-01T00:00:05Z",
        "command": "python train.py",
        "command_argv": ["python", "train.py"],
        "working_directory": ".",
        "git": {"commit": "abc123", "dirty": False},
        "randomness": {"seed": 42},
        "targets": {"claims": [], "plan": None},
        "environment": "environment.json",
        "environment_digest": "sha256:" + "0" * 64,
        "hardware": {},
        "env_vars": {},
        "metrics": "metrics.json",
        "artifacts": [],
        "timeout": None,
        "attempts": [{"attempt": 1, "exit_code": run_exit_code, "timed_out": False}],
        "exit_code": run_exit_code,
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    ws.evidence_dir.mkdir(parents=True, exist_ok=True)
    ev = Evidence(
        id="E001", path=ws.evidence_dir / "E001.md", schema_version="2.0", name="E001",
        status=evidence_status, source_kind="experiment", supports=["C001"], runs=["R0001"],
        body="# Evidence: E001\n",
    )
    ev.path.write_text(ev.render(), encoding="utf-8")

    ws.claims_dir.mkdir(parents=True, exist_ok=True)
    cl = Claim(
        id="C001", path=ws.claims_dir / "C001.md", schema_version="2.0", name="C001",
        status="supported", evidence=["E001"],
        body="# Claim: C001\n\n## Statement\nThe method improves F1 by 4.8 points.\n",
    )
    cl.path.write_text(cl.render(), encoding="utf-8")


def test_linked_and_verified_assertion_is_fully_backed(tmp_path):
    ws = init_workspace(tmp_path)
    _seed_graph(ws)
    paper_path = tmp_path / "paper.md"
    paper_path.write_text(
        "# Title\n\nOur method improved F1 by 4.8 percentage points.\n<!-- rl:claim=C001 -->\n",
        encoding="utf-8",
    )

    result = audit_paper(ws, paper_path)
    assert result.quantitative_assertions == 1
    assert result.linked_to_claims == 1
    assert result.backed_by_verified_evidence == 1
    assert result.backed_by_reproducible_runs == 1
    assert result.unsupported == 0
    assert result.stale_evidence_usage == 0


def test_unmarked_quantitative_sentence_is_unsupported(tmp_path):
    ws = init_workspace(tmp_path)
    paper_path = tmp_path / "paper.md"
    paper_path.write_text("# Title\n\nAccuracy reached 91.4%.\n", encoding="utf-8")

    result = audit_paper(ws, paper_path)
    assert result.quantitative_assertions == 1
    assert result.unsupported == 1
    assert result.linked_to_claims == 0


def test_stale_evidence_usage_is_flagged(tmp_path):
    ws = init_workspace(tmp_path)
    _seed_graph(ws, evidence_status="superseded")
    paper_path = tmp_path / "paper.md"
    paper_path.write_text(
        "Our method improved F1 by 4.8 points.\n<!-- rl:claim=C001 -->\n",
        encoding="utf-8",
    )

    result = audit_paper(ws, paper_path)
    assert result.stale_evidence_usage == 1
    assert result.backed_by_verified_evidence == 0  # superseded, not verified


def test_inline_code_digits_do_not_count_as_quantitative(tmp_path):
    ws = init_workspace(tmp_path)
    paper_path = tmp_path / "paper.md"
    paper_path.write_text(
        "See `research/evidence/E001.md` and `research/decisions/D001.md` for details.\n",
        encoding="utf-8",
    )

    result = audit_paper(ws, paper_path)
    assert result.quantitative_assertions == 0


def test_wrapped_sentence_across_two_lines_counts_once_and_finds_the_marker(tmp_path):
    ws = init_workspace(tmp_path)
    paper_path = tmp_path / "paper.md"
    paper_path.write_text(
        "Our method improved F1 by 4.8 percentage points over the strongest\n"
        "published baseline on this benchmark.\n"
        "<!-- rl:claim=C001 -->\n",
        encoding="utf-8",
    )

    result = audit_paper(ws, paper_path)
    assert result.quantitative_assertions == 1
    assert result.linked_to_claims == 1
    assert result.unsupported == 0


def test_heading_and_table_lines_are_not_counted(tmp_path):
    ws = init_workspace(tmp_path)
    paper_path = tmp_path / "paper.md"
    paper_path.write_text("## 4.2 Results\n\n| Model | F1 |\n|---|---|\n| Ours | 0.9 |\n", encoding="utf-8")

    result = audit_paper(ws, paper_path)
    assert result.quantitative_assertions == 0


def test_recovered_claim_with_new_verified_evidence_is_not_permanently_stale(tmp_path):
    ws = init_workspace(tmp_path)
    _seed_graph(ws, evidence_status="superseded")

    ev2 = Evidence(
        id="E002", path=ws.evidence_dir / "E002.md", schema_version="2.0", name="E002",
        status="verified", source_kind="experiment", supports=["C001"], runs=["R0001"],
        body="# Evidence: E002\n",
    )
    ev2.path.write_text(ev2.render(), encoding="utf-8")
    claim = Claim.load(ws.claims_dir / "C001.md")
    claim.evidence.append("E002")
    claim.status = "supported"
    claim.path.write_text(claim.render(), encoding="utf-8")

    paper_path = tmp_path / "paper.md"
    paper_path.write_text(
        "Our method improved F1 by 4.8 points.\n<!-- rl:claim=C001 -->\n",
        encoding="utf-8",
    )
    result = audit_paper(ws, paper_path)
    assert result.stale_evidence_usage == 0
    assert result.backed_by_verified_evidence == 1


def test_explicit_stale_evidence_marker_remains_stale_after_claim_recovery(tmp_path):
    ws = init_workspace(tmp_path)
    _seed_graph(ws, evidence_status="superseded")

    ev2 = Evidence(
        id="E002", path=ws.evidence_dir / "E002.md", schema_version="2.0", name="E002",
        status="verified", source_kind="experiment", supports=["C001"], runs=["R0001"],
        body="# Evidence: E002\n",
    )
    ev2.path.write_text(ev2.render(), encoding="utf-8")
    claim = Claim.load(ws.claims_dir / "C001.md")
    claim.evidence.append("E002")
    claim.status = "supported"
    claim.path.write_text(claim.render(), encoding="utf-8")

    old_paper = tmp_path / "old.md"
    old_paper.write_text(
        "Our method improved F1 by 4.8 points.\n<!-- rl:claim=C001 evidence=E001 -->\n",
        encoding="utf-8",
    )
    old_result = audit_paper(ws, old_paper)
    assert old_result.stale_evidence_usage == 1
    assert old_result.backed_by_verified_evidence == 0

    new_paper = tmp_path / "new.md"
    new_paper.write_text(
        "Our method improved F1 by 4.8 points.\n<!-- rl:claim=C001 evidence=E002 -->\n",
        encoding="utf-8",
    )
    new_result = audit_paper(ws, new_paper)
    assert new_result.stale_evidence_usage == 0
    assert new_result.backed_by_verified_evidence == 1
