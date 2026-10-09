import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / "validation_study"


def test_real_history_source_cases_are_pinned_and_match_audit():
    audit = json.loads((STUDY / "SOURCE_AUDIT.json").read_text())
    by_id = {c["case_id"]: c for c in audit["cases"]}
    cases = sorted((STUDY / "source_cases").glob("RH*.json"))
    # The structural development pilot intentionally remains the original ten cases.
    assert len(cases) == 10
    assert len(by_id) >= len(cases)
    for path in cases:
        case = json.loads(path.read_text())
        src = case["source"]
        row = by_id[case["id"]]
        assert src["repository"] == row["repository"]
        assert src["base_commit"] == row["base_commit"]
        assert src["revision_commit"] == row["revision_commit"]
        assert len(src["base_commit"]) == 40
        assert len(src["revision_commit"]) == 40


def test_blind_annotation_packets_do_not_leak_authored_gold_or_system_outputs():
    packets = sorted((STUDY / "annotation_packets").glob("RH*.blind.json"))
    manifest = json.loads((STUDY / "annotation_packets" / "manifest.json").read_text())
    assert len(packets) == 10
    assert manifest["n_packets"] == 10
    for path in packets:
        packet = json.loads(path.read_text())
        assert "gold" not in packet
        assert "systems" not in packet
        assert "truth" not in packet
        assert packet["revision_event"]["targets"]
        assert all(
            v["value"] is None
            for k, v in packet["questions"].items()
            if k != "overall_sufficient_context"
        )


def test_semantic_replay_v2_covers_structural_cases_and_observes_changes():
    replay = json.loads((STUDY / "results" / "prr_executed_semantic_replay_v2.json").read_text())
    source_ids = {p.stem for p in (STUDY / "source_cases").glob("RH*.json")}
    replay_ids = {row["case_id"] for row in replay["cases"]}
    assert source_ids.issubset(replay_ids)
    assert {"RH11_SQUIDPY_PERMUTATION_NJOBS", "RH12_SKLEARN_SPARSE_QUANTILE_SUBSAMPLING", "RH13_SAELENS_ZERO_BOS"}.issubset(replay_ids)
    assert replay["n_cases"] == 13
    assert replay["n_semantic_changes_observed"] == 13
    assert replay["n_repositories"] == 9


def test_structural_pilot_remains_separate_from_expanded_semantic_replay():
    pilot = json.loads((STUDY / "results" / "prr_real_history_pilot.json").read_text())
    assert len(pilot["cases"]) == 10
    assert "authored" in pilot["pilot_scope"].lower() or "graph" in pilot["pilot_scope"].lower()


def test_transaction_fault_injection_passes_all_declared_checks():
    result = json.loads((STUDY / "results" / "transaction_fault_injection.json").read_text())
    assert result["n_checks"] == 6
    assert result["n_passed"] == 6
    assert result["checks"]["exhaustive_write_position_rollback"]["n_positions"] == 11
    assert result["checks"]["exhaustive_write_position_rollback"]["n_restored"] == 11
