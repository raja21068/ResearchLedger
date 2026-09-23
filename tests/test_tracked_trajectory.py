import json
from pathlib import Path

from researchledger.models import Claim, Evidence
from researchledger.validate_paper import audit_paper
from researchledger.workspace import Workspace
from validation_study.annotation_tool import adjudication_template, aggregate_dirs, make_packet


ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / "validation_study"


def test_tracked_proxy_trajectories_cover_all_13_cases_and_recover():
    result = json.loads((STUDY / "results" / "tracked_trajectory_proxy.json").read_text())
    assert result["n_cases"] == 13
    assert result["n_repositories"] == 9
    assert result["n_output_changes"] == 13
    assert result["n_lifecycle_ok"] == 13
    for row in result["cases"]:
        assert row["output_changed"] is True
        assert row["claim_state_before_revision"] == "supported"
        assert row["claim_state_after_old_evidence_superseded"] == "hypothesis"
        assert row["claim_state_after_recovery"] == "supported"
        assert row["paper_audit_before"]["backed_by_verified_evidence"] == 1
        assert row["paper_audit_after_invalidation"]["stale_evidence_usage"] == 1
        assert row["paper_audit_after_recovery"]["stale_evidence_usage"] == 0
        assert row["paper_audit_after_recovery"]["backed_by_verified_evidence"] == 1
        assert row["final_validation_errors"] == 0


def test_tracked_workspaces_have_two_immutable_runs_and_committed_revision_journals():
    result = json.loads((STUDY / "results" / "tracked_trajectory_proxy.json").read_text())
    for row in result["cases"]:
        root = STUDY / "tracked_trajectory_workspaces" / row["case_id"]
        ws = Workspace(root)
        for rid in (row["old_run_id"], row["new_run_id"]):
            manifest = json.loads((ws.runs_dir / rid / "manifest.json").read_text())
            assert manifest["status"] == "completed"
            assert manifest["git"]["commit"] == row["harness_git_commit"]
            assert any(a["path"].endswith("result.json") for a in manifest["artifacts"])
        revs = root / ".researchledger" / "revisions"
        phases = [json.loads(p.read_text())["phase"] for p in revs.glob("*/manifest.json")]
        assert len(phases) == 3
        assert phases == ["committed", "committed", "committed"] or set(phases) == {"committed"}


def test_annotation_round_aggregation_and_adjudication_template(tmp_path):
    case = json.loads((STUDY / "source_cases" / "RH02_SCANPY_SPARSE_NORMALIZE_TOTAL.json").read_text())
    a = make_packet(case)
    b = make_packet(case)
    a["questions"]["affected_claims"]["value"] = ["C_SPARSE"]
    b["questions"]["affected_claims"]["value"] = ["C_SPARSE", "C_ROBUST"]
    for field in ("unaffected_claims", "affected_decisions", "affected_assertions"):
        a["questions"][field]["value"] = []
        b["questions"][field]["value"] = []

    da = tmp_path / "a"; db = tmp_path / "b"
    da.mkdir(); db.mkdir()
    pa = da / "x.json"; pb = db / "x.json"
    pa.write_text(json.dumps(a)); pb.write_text(json.dumps(b))

    summary = aggregate_dirs(da, db)
    assert summary["n_trajectories"] == 1
    assert summary["fields"]["affected_claims"]["exact_agreement_rate"] == 0.0
    assert summary["fields"]["affected_claims"]["mean_jaccard"] == 0.5

    adjudication = adjudication_template(pa, pb)
    assert adjudication["trajectory_id"] == case["id"]
    assert "affected_claims" in adjudication["disagreements"]
    assert adjudication["disagreements"]["affected_claims"]["adjudicated_value"] is None
    assert "systems" not in adjudication and "gold" not in adjudication
