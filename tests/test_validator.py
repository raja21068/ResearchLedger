import hashlib
import json

from researchledger import codes
from researchledger.environment import environment_digest as compute_environment_digest
from researchledger.hashing import sha256_file
from researchledger.models import Claim, Decision, Evidence
from researchledger.validator import validate
from researchledger.workspace import init_workspace


def _write_evidence(ws, eid, **kwargs):
    kwargs.setdefault("schema_version", "2.0")
    ev = Evidence(id=eid, path=ws.evidence_dir / f"{eid}.md", **kwargs)
    ws.evidence_dir.mkdir(parents=True, exist_ok=True)
    ev.path.write_text(ev.render(), encoding="utf-8")
    return ev


def _write_claim(ws, cid, **kwargs):
    kwargs.setdefault("schema_version", "2.0")
    body = kwargs.pop("body", None)
    cl = Claim(id=cid, path=ws.claims_dir / f"{cid}.md", **kwargs)
    if body is not None:
        cl.body = body
    ws.claims_dir.mkdir(parents=True, exist_ok=True)
    cl.path.write_text(cl.render(), encoding="utf-8")
    return cl


def _write_decision(ws, did, **kwargs):
    kwargs.setdefault("schema_version", "2.0")
    dec = Decision(id=did, path=ws.decisions_dir / f"{did}.md", **kwargs)
    ws.decisions_dir.mkdir(parents=True, exist_ok=True)
    dec.path.write_text(dec.render(), encoding="utf-8")
    return dec


def _write_run(
    ws, run_id, *, exit_code=0, commit="abc123def456", artifacts=None, metrics="metrics.json",
    previous_run_hash=None,
):
    run_dir = ws.runs_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    environment = {"python_version": "3.11.0", "platform": "test", "packages": []}
    (run_dir / "environment.json").write_text(json.dumps(environment), encoding="utf-8")

    metrics_sha256 = None
    if metrics:
        (run_dir / metrics).write_text(json.dumps({"metric": 1}), encoding="utf-8")
        metrics_sha256 = sha256_file(run_dir / metrics)

    manifest = {
        "schema_version": "2.0",
        "run_id": run_id,
        "status": "completed" if exit_code == 0 else "failed",
        "started_at": "2026-01-01T00:00:00Z",
        "finished_at": "2026-01-01T00:00:05Z",
        "command": "python train.py",
        "command_argv": ["python", "train.py"],
        "working_directory": ".",
        "git": {"commit": commit, "dirty": False},
        "randomness": {"seed": 42},
        "targets": {"claims": [], "plan": None},
        "environment": "environment.json",
        "environment_digest": compute_environment_digest(environment),
        "hardware": {},
        "env_vars": {},
        "metrics": metrics,
        "metrics_sha256": metrics_sha256,
        "artifacts": artifacts or [],
        "inputs": [],
        "timeout": None,
        "attempts": [{"attempt": 1, "exit_code": exit_code, "timed_out": False}],
        "exit_code": exit_code,
        "previous_run_hash": previous_run_hash,
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return run_dir


def test_clean_workspace_has_no_errors_or_warnings(tmp_path):
    ws = init_workspace(tmp_path)
    _write_run(ws, "R0001")
    _write_claim(ws, "C001", name="C001", status="supported", evidence=["E001"])
    _write_evidence(
        ws,
        "E001",
        name="E001",
        status="verified",
        source_kind="experiment",
        supports=["C001"],
        runs=["R0001"],
        body="# Evidence: E001\n\n## Reproducibility\nresearchledger reproduce R0001\n",
    )

    result = validate(ws)
    assert result.errors == []
    assert result.warnings == []
    assert result.counts == {"claims": 1, "evidence": 1, "runs": 1, "decisions": 0}


def test_v1_style_file_fails_schema_validation(tmp_path):
    ws = init_workspace(tmp_path)
    ws.evidence_dir.mkdir(parents=True, exist_ok=True)
    (ws.evidence_dir / "E001.md").write_text(
        "---\n"
        "name: E001\n"
        "type: experiment-evidence\n"
        "status: supported\n"  # v1 status word, invalid in v2
        "source_kind: experiment\n"
        "supports: C001\n"  # v1 comma-string, not a v2 array
        "---\n\n# Evidence: E001\n",
        encoding="utf-8",
    )
    result = validate(ws)
    assert any(i.code == codes.RL003_SCHEMA_INVALID for i in result.errors)
    assert not result.passed()


def test_broken_edge_is_an_error(tmp_path):
    ws = init_workspace(tmp_path)
    _write_claim(ws, "C002", name="C002", status="hypothesis", evidence=["E999"])

    result = validate(ws)
    assert any(
        i.code == codes.RL101_BROKEN_EDGE and "C002 references nonexistent evidence E999" in i.message
        for i in result.errors
    )
    assert not result.passed()


def test_asymmetric_edge_is_a_warning(tmp_path):
    ws = init_workspace(tmp_path)
    _write_claim(ws, "C001", name="C001", status="hypothesis", evidence=[])
    _write_evidence(ws, "E002", name="E002", status="checked", source_kind="observation", supports=["C001"])

    result = validate(ws)
    assert any(i.code == codes.RL102_ASYMMETRIC_EDGE for i in result.warnings)
    assert result.errors == []


def test_artifact_hash_mismatch_is_an_error(tmp_path):
    ws = init_workspace(tmp_path)
    run_dir = _write_run(ws, "R0001", artifacts=[{"path": "artifacts/results.csv", "sha256": "0" * 64}])
    (run_dir / "artifacts").mkdir(parents=True, exist_ok=True)
    (run_dir / "artifacts" / "results.csv").write_text("real content", encoding="utf-8")

    result = validate(ws)
    assert any(i.code == codes.RL202_HASH_MISMATCH for i in result.errors)


def test_evidence_referencing_missing_run_is_an_error(tmp_path):
    ws = init_workspace(tmp_path)
    _write_evidence(ws, "E003", name="E003", status="checked", source_kind="experiment", runs=["R0099"])

    result = validate(ws)
    assert any(i.code == codes.RL101_BROKEN_EDGE and "R0099" in i.message for i in result.errors)


def test_experimental_evidence_without_run_is_an_error(tmp_path):
    ws = init_workspace(tmp_path)
    _write_evidence(ws, "E004", name="E004", status="checked", source_kind="experiment", runs=[])

    result = validate(ws)
    assert any(i.code == codes.RL111_EXPERIMENTAL_EVIDENCE_WITHOUT_RUN for i in result.errors)


def test_proposed_experimental_evidence_without_run_is_allowed(tmp_path):
    ws = init_workspace(tmp_path)
    _write_evidence(ws, "E005", name="E005", status="proposed", source_kind="experiment", runs=[])

    result = validate(ws)
    assert not any(i.code == codes.RL111_EXPERIMENTAL_EVIDENCE_WITHOUT_RUN for i in result.issues)


def test_run_without_artifact_or_metrics_is_a_warning(tmp_path):
    ws = init_workspace(tmp_path)
    _write_run(ws, "R0001", metrics=None, artifacts=[])
    _write_evidence(ws, "E006", name="E006", status="verified", source_kind="experiment", runs=["R0001"])

    result = validate(ws)
    assert any(i.code == codes.RL112_RUN_WITHOUT_ARTIFACT for i in result.warnings)


def test_claim_based_on_rejected_evidence_is_an_error(tmp_path):
    ws = init_workspace(tmp_path)
    _write_claim(ws, "C007", name="C007", status="contradicted", evidence=["E007"])
    _write_evidence(ws, "E007", name="E007", status="invalidated", source_kind="experiment", supports=["C007"])

    result = validate(ws)
    assert any(i.code == codes.RL120_CLAIM_BASED_ON_REJECTED_EVIDENCE for i in result.errors)


def test_empirical_claim_without_evidence_is_an_error(tmp_path):
    ws = init_workspace(tmp_path)
    _write_claim(ws, "C008", name="C008", status="supported", evidence=[])

    result = validate(ws)
    assert any(i.code == codes.RL110_EMPIRICAL_CLAIM_WITHOUT_EVIDENCE for i in result.errors)


def test_hypothesis_without_evidence_is_allowed(tmp_path):
    ws = init_workspace(tmp_path)
    _write_claim(ws, "C009", name="C009", status="hypothesis", evidence=[])

    result = validate(ws)
    assert not any(i.code == codes.RL110_EMPIRICAL_CLAIM_WITHOUT_EVIDENCE for i in result.issues)


def test_status_drift_is_a_warning(tmp_path):
    ws = init_workspace(tmp_path)
    _write_claim(ws, "C010", name="C010", status="hypothesis", evidence=["E010"])
    _write_evidence(ws, "E010", name="E010", status="verified", source_kind="observation", supports=["C010"])

    result = validate(ws)
    drift = [i for i in result.warnings if i.code == codes.RL310_STATUS_DRIFT]
    assert drift and "implies 'supported'" in drift[0].message


def test_superseded_dependency_is_a_warning(tmp_path):
    ws = init_workspace(tmp_path)
    _write_claim(ws, "C001", name="C001", status="supported", evidence=["E001"])
    _write_evidence(ws, "E001", name="E001", status="superseded", source_kind="experiment", supports=["C001"])

    result = validate(ws)
    assert any(i.code == codes.RL302_SUPERSEDED_DEPENDENCY for i in result.warnings)


def test_missing_reproduction_command_is_a_warning(tmp_path):
    ws = init_workspace(tmp_path)
    _write_run(ws, "R0001")
    _write_evidence(
        ws, "E011", name="E011", status="checked", source_kind="experiment",
        runs=["R0001"], body="# Evidence: E011\n",
    )

    result = validate(ws)
    assert any(i.code == codes.RL303_MISSING_REPRODUCTION for i in result.warnings)


def test_run_failed_is_an_error(tmp_path):
    ws = init_workspace(tmp_path)
    _write_run(ws, "R0001", exit_code=1)
    _write_evidence(ws, "E012", name="E012", status="checked", source_kind="experiment", runs=["R0001"])

    result = validate(ws)
    assert any(i.code == codes.RL211_RUN_FAILED for i in result.errors)


def test_decision_referencing_missing_evidence_is_an_error(tmp_path):
    ws = init_workspace(tmp_path)
    _write_decision(ws, "D001", name="D001", status="decided", evidence=["E404"])

    result = validate(ws)
    assert any(i.code == codes.RL101_BROKEN_EDGE and "D001" in i.message for i in result.errors)


def test_strict_escalates_status_drift_to_a_failure(tmp_path):
    ws = init_workspace(tmp_path)
    _write_claim(ws, "C010", name="C010", status="hypothesis", evidence=["E010"])
    _write_evidence(ws, "E010", name="E010", status="verified", source_kind="observation", supports=["C010"])

    result = validate(ws)
    assert result.passed(strict=False) is True
    assert result.passed(strict=True) is False


def test_supersedes_nonexistent_evidence_is_an_error(tmp_path):
    ws = init_workspace(tmp_path)
    _write_evidence(ws, "E020", name="E020", status="checked", source_kind="observation", supersedes="E999")

    result = validate(ws)
    assert any(i.code == codes.RL101_BROKEN_EDGE and "supersedes nonexistent" in i.message for i in result.errors)


def test_supersession_backlink_mismatch_is_a_warning(tmp_path):
    ws = init_workspace(tmp_path)
    _write_evidence(ws, "E021", name="E021", status="superseded", source_kind="observation")
    _write_evidence(ws, "E022", name="E022", status="checked", source_kind="observation", supersedes="E021")

    result = validate(ws)
    assert any(i.code == codes.RL301_SUPERSESSION_MISMATCH and "superseded_by" in i.message for i in result.warnings)


def test_supersession_old_status_not_superseded_is_a_warning(tmp_path):
    ws = init_workspace(tmp_path)
    _write_evidence(ws, "E023", name="E023", status="checked", source_kind="observation", superseded_by="E024")
    _write_evidence(ws, "E024", name="E024", status="checked", source_kind="observation", supersedes="E023")

    result = validate(ws)
    messages = [i.message for i in result.warnings if i.code == codes.RL301_SUPERSESSION_MISMATCH]
    assert any("not 'superseded'" in m for m in messages)


def test_superseded_by_referencing_missing_evidence_is_an_error(tmp_path):
    ws = init_workspace(tmp_path)
    _write_evidence(ws, "E025", name="E025", status="superseded", source_kind="observation", superseded_by="E404")

    result = validate(ws)
    assert any(i.code == codes.RL101_BROKEN_EDGE and "superseded_by" in i.message for i in result.errors)


def test_corrupt_run_manifest_is_reported_not_silently_dropped(tmp_path):
    """A corrupted manifest.json must never just vanish from the report —
    that was a real, confirmed bug: validate() used to catch the
    JSONDecodeError, drop the run entirely, and report a clean PASS."""
    ws = init_workspace(tmp_path)
    run_dir = ws.runs_dir / "R0001"
    run_dir.mkdir(parents=True)
    (run_dir / "manifest.json").write_text("{not valid json", encoding="utf-8")

    result = validate(ws)  # must not raise
    assert result.counts["runs"] == 0  # it can't be parsed, so it can't be counted as a run...
    assert any(
        i.code == codes.RL004_MALFORMED_RUN_MANIFEST and "R0001" in i.message for i in result.errors
    )  # ...but its existence and corruption must show up as a hard error.
    assert not result.passed()


def test_two_chain_roots_is_an_error(tmp_path):
    ws = init_workspace(tmp_path)
    _write_run(ws, "R0001", previous_run_hash=None)
    _write_run(ws, "R0002", previous_run_hash=None)

    result = validate(ws)
    assert any(
        i.code == codes.RL220_CHAIN_BROKEN and "chain root already exists" in i.message for i in result.errors
    )


def test_chain_branch_detected_when_two_runs_claim_the_same_predecessor(tmp_path):
    ws = init_workspace(tmp_path)
    _write_run(ws, "R0001", previous_run_hash=None)
    root_hash = "sha256:" + hashlib.sha256((ws.runs_dir / "R0001" / "manifest.json").read_bytes()).hexdigest()
    _write_run(ws, "R0002", previous_run_hash=root_hash)
    _write_run(ws, "R0003", previous_run_hash=root_hash)

    result = validate(ws)
    assert any(i.code == codes.RL220_CHAIN_BROKEN and "chain branch detected" in i.message for i in result.errors)


def test_run_manifest_failing_schema_validation_is_an_error(tmp_path):
    ws = init_workspace(tmp_path)
    run_dir = ws.runs_dir / "R0001"
    run_dir.mkdir(parents=True)
    # Valid JSON, but missing every required run.schema.json field.
    (run_dir / "manifest.json").write_text('{"status": "completed"}', encoding="utf-8")

    result = validate(ws)
    assert any(i.code == codes.RL003_SCHEMA_INVALID and "R0001" in i.message for i in result.errors)


def test_schema_invalid_claim_and_decision(tmp_path):
    ws = init_workspace(tmp_path)
    ws.claims_dir.mkdir(parents=True, exist_ok=True)
    (ws.claims_dir / "C001.md").write_text(
        "---\nname: C001\ntype: research-claim\nstatus: hypothesis\n---\n\n# Claim: C001\n",
        encoding="utf-8",
    )  # missing schema_version
    ws.decisions_dir.mkdir(parents=True, exist_ok=True)
    (ws.decisions_dir / "D001.md").write_text(
        "---\nname: D001\ntype: research-decision\nstatus: decided\n---\n\n# Decision: D001\n",
        encoding="utf-8",
    )  # missing schema_version

    result = validate(ws)
    messages = [i.message for i in result.errors if i.code == codes.RL003_SCHEMA_INVALID]
    assert any("C001" in m for m in messages)
    assert any("D001" in m for m in messages)


def test_bad_ids_for_every_entity_type(tmp_path):
    ws = init_workspace(tmp_path)
    _write_claim(ws, "CBAD", name="CBAD", status="hypothesis")
    _write_evidence(ws, "EBAD", name="EBAD", status="observed", source_kind="observation")
    _write_decision(ws, "DBAD", name="DBAD", status="decided")
    run_dir = ws.runs_dir / "RBAD"
    run_dir.mkdir(parents=True)
    (run_dir / "manifest.json").write_text('{"artifacts": [], "inputs": []}', encoding="utf-8")

    result = validate(ws)
    bad_id_messages = [i.message for i in result.errors if i.code == codes.RL001_BAD_ID]
    assert any("CBAD" in m for m in bad_id_messages)
    assert any("EBAD" in m for m in bad_id_messages)
    assert any("DBAD" in m for m in bad_id_messages)
    assert any("RBAD" in m for m in bad_id_messages)


def test_claim_contradicts_nonexistent_evidence_is_an_error(tmp_path):
    ws = init_workspace(tmp_path)
    _write_claim(ws, "C030", name="C030", status="hypothesis", contradicts=["E999"])

    result = validate(ws)
    assert any(
        i.code == codes.RL101_BROKEN_EDGE and "nonexistent contradicting evidence" in i.message
        for i in result.errors
    )


def test_claim_contradicts_asymmetric_is_a_warning(tmp_path):
    ws = init_workspace(tmp_path)
    _write_claim(ws, "C031", name="C031", status="hypothesis", contradicts=["E031"])
    _write_evidence(ws, "E031", name="E031", status="checked", source_kind="observation")

    result = validate(ws)
    assert any(
        i.code == codes.RL102_ASYMMETRIC_EDGE and "does not list C031 back" in i.message for i in result.warnings
    )


def test_evidence_contradicts_nonexistent_claim_is_an_error(tmp_path):
    ws = init_workspace(tmp_path)
    _write_evidence(ws, "E032", name="E032", status="checked", source_kind="observation", contradicts=["C999"])

    result = validate(ws)
    assert any(
        i.code == codes.RL101_BROKEN_EDGE and "contradicts nonexistent claim" in i.message for i in result.errors
    )


def test_evidence_contradicts_asymmetric_is_a_warning(tmp_path):
    ws = init_workspace(tmp_path)
    _write_evidence(ws, "E033", name="E033", status="checked", source_kind="observation", contradicts=["C033"])
    _write_claim(ws, "C033", name="C033", status="hypothesis")

    result = validate(ws)
    assert any(
        i.code == codes.RL102_ASYMMETRIC_EDGE and "does not list E033 back" in i.message for i in result.warnings
    )


def test_run_without_environment_field_is_a_warning(tmp_path):
    ws = init_workspace(tmp_path)
    run_dir = ws.runs_dir / "R0001"
    run_dir.mkdir(parents=True)
    (run_dir / "manifest.json").write_text('{"exit_code": 0, "artifacts": [], "inputs": []}', encoding="utf-8")

    result = validate(ws)
    assert any(i.code == codes.RL210_ENVIRONMENT_MISSING for i in result.warnings)


def test_missing_artifact_file_is_an_error(tmp_path):
    ws = init_workspace(tmp_path)
    _write_run(ws, "R0001", artifacts=[{"path": "artifacts/gone.csv", "sha256": "0" * 64}])

    result = validate(ws)
    assert any(i.code == codes.RL201_MISSING_ARTIFACT for i in result.errors)


def test_matching_artifact_hash_counts_toward_verification(tmp_path):
    ws = init_workspace(tmp_path)
    run_dir = ws.runs_dir / "R0001"
    artifacts_dir = run_dir / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    (artifacts_dir / "ok.csv").write_text("real content", encoding="utf-8")
    from researchledger.hashing import sha256_file

    real_hash = sha256_file(artifacts_dir / "ok.csv")
    _write_run(ws, "R0001", artifacts=[{"path": "artifacts/ok.csv", "sha256": real_hash}])

    result = validate(ws)
    assert result.metrics["artifact_verification"] == 100.0


def test_input_path_resolves_relative_to_workspace_root_when_working_directory_is_relative(tmp_path):
    ws = init_workspace(tmp_path)
    (tmp_path / "data.csv").write_text("hello", encoding="utf-8")
    run_dir = ws.runs_dir / "R0001"
    run_dir.mkdir(parents=True)
    manifest = {
        "schema_version": "2.0", "run_id": "R0001", "status": "completed",
        "started_at": "2026-01-01T00:00:00Z", "finished_at": "2026-01-01T00:00:05Z",
        "command": "x", "command_argv": ["x"],
        "working_directory": ".",  # relative -- forces the ws.root fallback
        "git": {"commit": None, "dirty": None}, "randomness": {"seed": None},
        "targets": {"claims": [], "plan": None}, "environment": "environment.json",
        "artifacts": [], "inputs": [{"path": "data.csv", "sha256": "0" * 64}],
        "timeout": None, "attempts": [], "exit_code": 0,
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    result = validate(ws)
    # The path resolves (via ws.root) and is found, but the hash is wrong.
    assert any(i.code == codes.RL213_INPUT_HASH_MISMATCH for i in result.errors)
    assert not any(i.code == codes.RL212_MISSING_INPUT for i in result.issues)


def test_provenance_marker_with_explicit_evidence_group(tmp_path):
    ws = init_workspace(tmp_path)
    _write_claim(ws, "C040", name="C040", status="hypothesis")
    paper_dir = ws.papers_dir / "main"
    paper_dir.mkdir(parents=True, exist_ok=True)
    (paper_dir / "paper.md").write_text(
        "Our method improved F1 by 4.8 points.\n<!-- rl: claim=C040 evidence=E999 -->\n",
        encoding="utf-8",
    )

    result = validate(ws)
    assert any(
        i.code == codes.RL401_BROKEN_PROVENANCE and "nonexistent evidence E999" in i.message for i in result.errors
    )


def test_legacy_run_without_chain_field_is_a_warning_not_an_error(tmp_path):
    ws = init_workspace(tmp_path)
    run_dir = ws.runs_dir / "R0001"
    run_dir.mkdir(parents=True)
    # Write a manifest that predates the chain feature entirely (no key at all).
    legacy_manifest = {
        "schema_version": "2.0", "run_id": "R0001", "status": "completed",
        "started_at": "2026-01-01T00:00:00Z", "finished_at": "2026-01-01T00:00:05Z",
        "command": "python x.py", "command_argv": ["python", "x.py"], "working_directory": ".",
        "git": {"commit": None, "dirty": None}, "randomness": {"seed": None},
        "targets": {"claims": [], "plan": None}, "environment": "environment.json",
        "artifacts": [], "timeout": None, "attempts": [{"attempt": 1, "exit_code": 0, "timed_out": False}],
        "exit_code": 0,
    }
    (run_dir / "manifest.json").write_text(json.dumps(legacy_manifest), encoding="utf-8")

    result = validate(ws)
    assert any(i.code == codes.RL221_LEGACY_UNCHAINED_RUN for i in result.warnings)
    assert not any(i.code == codes.RL220_CHAIN_BROKEN for i in result.issues)


def test_tampered_run_history_breaks_the_chain(tmp_path):
    ws = init_workspace(tmp_path)
    import sys as _sys

    from researchledger.runner import run_command

    first = run_command(ws, [_sys.executable, "-c", "pass"])
    run_command(ws, [_sys.executable, "-c", "pass"])

    # Tamper with the first run's manifest after the fact.
    first_manifest_path = ws.runs_dir / first["run_id"] / "manifest.json"
    tampered = json.loads(first_manifest_path.read_text(encoding="utf-8"))
    tampered["exit_code"] = 1
    first_manifest_path.write_text(json.dumps(tampered), encoding="utf-8")

    result = validate(ws)
    assert any(i.code == codes.RL220_CHAIN_BROKEN for i in result.errors)


def test_input_dataset_hash_mismatch_is_an_error(tmp_path):
    ws = init_workspace(tmp_path)
    dataset = tmp_path / "data.csv"
    dataset.write_text("original", encoding="utf-8")
    _write_run(ws, "R0001")
    manifest_path = ws.runs_dir / "R0001" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["inputs"] = [{"path": str(dataset), "sha256": "0" * 64}]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    result = validate(ws)
    assert any(i.code == codes.RL213_INPUT_HASH_MISMATCH for i in result.errors)


def test_missing_input_dataset_is_an_error(tmp_path):
    ws = init_workspace(tmp_path)
    _write_run(ws, "R0001")
    manifest_path = ws.runs_dir / "R0001" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["inputs"] = [{"path": str(tmp_path / "gone.csv"), "sha256": "0" * 64}]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    result = validate(ws)
    assert any(i.code == codes.RL212_MISSING_INPUT for i in result.errors)


def test_manuscript_provenance_broken_reference_is_an_error(tmp_path):
    ws = init_workspace(tmp_path)
    paper_dir = ws.papers_dir / "main"
    paper_dir.mkdir(parents=True, exist_ok=True)
    (paper_dir / "paper.md").write_text(
        "# Title\n\nOur method improved F1 by 4.8 points.\n<!-- rl:claim=C999 -->\n",
        encoding="utf-8",
    )

    result = validate(ws)
    assert any(i.code == codes.RL401_BROKEN_PROVENANCE for i in result.errors)


def test_chained_run_may_legitimately_point_at_a_legacy_run(tmp_path):
    """Regression test for a confirmed bug: the chain-hash lookup was built
    from chain-aware runs only, so a brand-new chained run pointing at the
    workspace's last *legacy* run (exactly how the chain is meant to
    bootstrap) reported RL220 as if history had been altered."""
    ws = init_workspace(tmp_path)
    legacy_dir = _write_run(ws, "R0001")
    legacy_hash = "sha256:" + hashlib.sha256((legacy_dir / "manifest.json").read_bytes()).hexdigest()
    _write_run(ws, "R0002", previous_run_hash=legacy_hash)

    result = validate(ws)
    assert result.errors == []
    assert result.metrics["chain_integrity"] == 100.0


def test_metrics_hash_mismatch_is_an_error(tmp_path):
    ws = init_workspace(tmp_path)
    run_dir = _write_run(ws, "R0001")
    (run_dir / "metrics.json").write_text('{"metric": 999}', encoding="utf-8")  # now disagrees with the recorded hash

    result = validate(ws)
    assert any(i.code == codes.RL215_METRICS_HASH_MISMATCH for i in result.errors)


def test_missing_metrics_file_is_an_error(tmp_path):
    ws = init_workspace(tmp_path)
    run_dir = _write_run(ws, "R0001")
    (run_dir / "metrics.json").unlink()

    result = validate(ws)
    assert any(i.code == codes.RL214_MISSING_METRICS_FILE for i in result.errors)


def test_environment_digest_mismatch_is_an_error(tmp_path):
    ws = init_workspace(tmp_path)
    run_dir = _write_run(ws, "R0001")
    (run_dir / "environment.json").write_text('{"tampered": true}', encoding="utf-8")

    result = validate(ws)
    assert any(i.code == codes.RL217_ENVIRONMENT_DIGEST_MISMATCH for i in result.errors)


def test_missing_environment_file_is_an_error(tmp_path):
    ws = init_workspace(tmp_path)
    run_dir = _write_run(ws, "R0001")
    (run_dir / "environment.json").unlink()

    result = validate(ws)
    assert any(i.code == codes.RL216_MISSING_ENVIRONMENT_FILE for i in result.errors)


def test_malformed_evidence_is_reported_not_crashed_on(tmp_path):
    ws = init_workspace(tmp_path)
    ws.evidence_dir.mkdir(parents=True, exist_ok=True)
    (ws.evidence_dir / "E001.md").write_text(
        "---\nname: E001\nstatus: checked\n  bad indent: [broken\n---\nbody\n", encoding="utf-8"
    )

    result = validate(ws)  # must not raise
    assert any(i.code == codes.RL005_MALFORMED_RECORD and "E001.md" in i.message for i in result.errors)


def test_malformed_claim_is_reported_not_crashed_on(tmp_path):
    ws = init_workspace(tmp_path)
    ws.claims_dir.mkdir(parents=True, exist_ok=True)
    (ws.claims_dir / "C001.md").write_text(
        "---\nname: C001\nstatus: hypothesis\n  bad indent: [broken\n---\nbody\n", encoding="utf-8"
    )

    result = validate(ws)  # must not raise
    assert any(i.code == codes.RL005_MALFORMED_RECORD and "C001.md" in i.message for i in result.errors)


def test_malformed_decision_is_reported_not_crashed_on(tmp_path):
    ws = init_workspace(tmp_path)
    ws.decisions_dir.mkdir(parents=True, exist_ok=True)
    (ws.decisions_dir / "D001.md").write_text(
        "---\nname: D001\nstatus: decided\n  bad indent: [broken\n---\nbody\n", encoding="utf-8"
    )

    result = validate(ws)  # must not raise
    assert any(i.code == codes.RL005_MALFORMED_RECORD and "D001.md" in i.message for i in result.errors)


def test_manifest_run_id_mismatch_is_an_error(tmp_path):
    ws = init_workspace(tmp_path)
    run_dir = _write_run(ws, "R0001")
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    manifest["run_id"] = "R9999"
    (run_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    result = validate(ws)
    assert any(i.code == codes.RL006_MANIFEST_IDENTITY_MISMATCH for i in result.errors)


def test_artifact_path_traversal_is_rejected(tmp_path):
    ws = init_workspace(tmp_path)
    _write_run(ws, "R0001", artifacts=[{"path": "../../../../etc/passwd", "sha256": "0" * 64}])

    result = validate(ws)
    assert any(i.code == codes.RL203_UNSAFE_PATH for i in result.errors)
    # a rejected path must never be reported as "missing" instead — that
    # would imply the validator tried to open it, which is exactly what
    # RL203 exists to prevent.
    assert not any(i.code == codes.RL201_MISSING_ARTIFACT for i in result.issues)


def test_artifact_symlink_is_rejected(tmp_path):
    ws = init_workspace(tmp_path)
    run_dir = _write_run(ws, "R0001", artifacts=[{"path": "artifacts/link.csv", "sha256": "0" * 64}])
    artifacts_dir = run_dir / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    target = tmp_path / "outside.csv"
    target.write_text("real content", encoding="utf-8")
    try:
        (artifacts_dir / "link.csv").symlink_to(target)
    except OSError:
        import pytest

        pytest.skip("symlink creation is not permitted on this machine/OS")

    result = validate(ws)
    assert any(i.code == codes.RL203_UNSAFE_PATH for i in result.errors)


def test_validator_accepts_bidirectional_support_sets(tmp_path):
    ws = init_workspace(tmp_path)
    _write_run(ws, "R0001")
    _write_run(ws, "R0002")
    _write_claim(
        ws, "C020", name="C020", status="supported",
        evidence=["E001", "E002"], support_sets=[["E001", "E002"]],
    )
    for eid, rid in (("E001", "R0001"), ("E002", "R0002")):
        _write_evidence(
            ws, eid, name=eid, status="verified", source_kind="experiment",
            supports=["C020"], runs=[rid],
            body=f"# Evidence: {eid}\n\n## Reproducibility\nresearchledger reproduce {rid}\n",
        )
    result = validate(ws)
    assert not any(i.code == codes.RL101_BROKEN_EDGE for i in result.errors)
    assert not any(i.code == codes.RL102_ASYMMETRIC_EDGE for i in result.warnings)
    assert not any(i.code == codes.RL310_STATUS_DRIFT for i in result.warnings)


def test_validator_flags_missing_support_set_member(tmp_path):
    ws = init_workspace(tmp_path)
    _write_claim(
        ws, "C021", name="C021", status="hypothesis",
        evidence=["E001", "E404"], support_sets=[["E001", "E404"]],
    )
    _write_evidence(ws, "E001", name="E001", status="proposed", source_kind="observation", supports=["C021"])
    result = validate(ws)
    assert any(i.code == codes.RL101_BROKEN_EDGE and "E404" in i.message for i in result.errors)
