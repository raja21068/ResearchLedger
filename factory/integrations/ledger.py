"""Paper Factory → ResearchLedger adapter.

This adapter imports already executed Docker artifacts into ResearchLedger;
it never invokes generated code on the host. Records distinguish computed
pilot observations from independently verified experimental evidence.
"""
from __future__ import annotations

import json
from pathlib import Path

from factory.io import atomic_json
from factory.pipeline.provenance import hash_file
from researchledger.atomic import atomic_write_text
from researchledger.evidence import create_evidence
from researchledger.models import Claim, load_evidence
from researchledger.runner import record_external_execution
from researchledger.validator import validate
from researchledger.workspace import Workspace, init_workspace, ledger_lock, next_id

IDEA_RECEIPT = "control/ledger_idea.json"
RUN_RECEIPT = "control/ledger_s4_receipt.json"


def enabled(context: dict | None) -> bool:
    return bool((context or {}).get("ledger_enabled", False))


def record_idea(project: Path) -> dict:
    """Register each distinct selected hypothesis without claiming support."""
    project = Path(project).resolve()
    idea = project / "1_idea" / "idea.md"
    if not idea.is_file() or idea.is_symlink():
        raise ValueError("cannot ledger-record a missing or symlinked idea")
    digest = hash_file(idea)
    receipt_file = project / IDEA_RECEIPT
    if receipt_file.is_file():
        old = json.loads(receipt_file.read_text(encoding="utf-8"))
        if old.get("idea_sha256") == digest and (project / "research" / "claims" / f"{old['claim_id']}.md").is_file():
            return old

    ws = init_workspace(project)
    lines = idea.read_text(encoding="utf-8").splitlines()
    name = next((ln[2:].strip() for ln in lines if ln.startswith("# ")), "Research hypothesis")
    body = "## Statement\n\n" + idea.read_text(encoding="utf-8") + "\n"
    with ledger_lock(ws):
        claim_id = next_id(ws.claims_dir, "C", 3)
        claim = Claim(id=claim_id, path=ws.claims_dir / f"{claim_id}.md", schema_version="2.0",
                      name=name, status="hypothesis", body=body,
                      raw_frontmatter={"created_at": __import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat()})
        atomic_write_text(claim.path, claim.render())
    receipt = {"schema_version": 1, "claim_id": claim_id, "idea_sha256": digest,
               "scientific_status": "HYPOTHESIS_NOT_VALIDATED"}
    atomic_json(receipt_file, receipt)
    return receipt


def _checked_sandbox_result(project: Path) -> tuple[dict, dict]:
    from factory.steps.code import artifact_ok
    valid, reason = artifact_ok(project)
    if not valid:
        raise ValueError(f"result contract failed: {reason}")
    data = json.loads((project / "4_code" / "results.json").read_text(encoding="utf-8"))
    attempts = data.get("attempts")
    if not isinstance(attempts, list) or not attempts:
        raise ValueError("no container attempt provenance available")
    good = attempts[-1]
    if (good.get("install") == "FAIL" or good.get("run") != "PASS" or
            good.get("returncode") != 0 or good.get("problems")):
        raise ValueError("last sandbox execution was not successful")
    if not data.get("image") or not data.get("repo_sha256"):
        raise ValueError("missing Docker image or repository digest")
    if data.get('scale') == 'validation_data_attempt':
        from factory.steps.code import _validate_data_attestation
        _validate_data_attestation(project, data)
    elif data.get('scale') != 'pilot':
        raise ValueError('unrecognized result scale')
    return data, good


def import_docker_run(project: Path, context: dict | None = None, *, force_new: bool = False) -> dict:
    """Seal validated S4 outputs and link *checked*, not verified, evidence."""
    project = Path(project).resolve()
    data, attempt = _checked_sandbox_result(project)
    ws = init_workspace(project)
    results_path = project / "4_code" / "results.json"
    old_file = project / RUN_RECEIPT
    if old_file.is_file() and not force_new:
        old = json.loads(old_file.read_text(encoding="utf-8"))
        valid, _ = verify_run_receipt(project)
        if valid and old.get("results_sha256") == hash_file(results_path):
            return old  # direct import is idempotent; real stage reruns use force_new

    idea_file = project / IDEA_RECEIPT
    supports = []
    if idea_file.is_file():
        idea_receipt = json.loads(idea_file.read_text(encoding="utf-8"))
        idea_path = project / "1_idea" / "idea.md"
        if idea_path.is_file() and hash_file(idea_path) == idea_receipt.get("idea_sha256"):
            supports = [idea_receipt["claim_id"]]

    artifacts = [project / "2_paper" / "results_spec.json", results_path,
                 project / "4_code" / "experimental_log.generated.md",
                 project / "4_code" / "unresolved.json"]
    for artifact in artifacts:
        if not artifact.is_file() or artifact.is_symlink():
            raise ValueError(f"required experimental artifact missing or symlinked: {artifact}")

    # Store the original measured result contract unmodified, including series.
    # Recording external execution is NOT a second run and NOT independent reproduction.
    from factory.steps.code import tree_hash
    from factory.pipeline.provenance import output_signature
    repo = project / "4_code" / "repo"
    if not repo.is_dir() or any(p.is_symlink() for p in repo.rglob("*")):
        raise ValueError("missing repository or symlink within generated repository")
    if tree_hash(repo) != data["repo_sha256"]:
        raise ValueError("generated code repository no longer matches recorded hash")
    manifest = record_external_execution(
        ws,
        command=data.get("command") or ["python", "pf_run.py"],
        metrics_path=results_path,
        artifact_paths=artifacts,
        execution={"status": "PASS", "exit_code": 0, "image": data["image"],
                   "repo_sha256": data["repo_sha256"], "source_output_sha256": hash_file(results_path),
                   "source_spec_sha256": hash_file(project / "2_paper" / "results_spec.json"),
                   "source_S4_outputs_sha256": output_signature(project, "S4"),
                   "sandbox_attempt": attempt, "method": "paper_factory_docker",
                   "timeout": int((context or {}).get("code_timeout", 3600)),
                   "input_data_sha256": _dataset_hash(project),
                   "synthetic_or_real_unverified": True},
        claims=supports,
    )
    evidence = create_evidence(ws, from_run=manifest["run_id"], supports=supports,
                               source_kind="experiment", status="checked",
                               name=("Paper Factory validation-data execution (not independently verified)"
                                     if data['scale'] == 'validation_data_attempt'
                                     else "Paper Factory isolated pilot experiment"))
    receipt = {"schema_version": 1, "run_id": manifest["run_id"], "evidence_id": evidence.id,
               "claim_ids": supports, "results_sha256": hash_file(results_path),
               "manifest_sha256": hash_file(ws.runs_dir / manifest["run_id"] / "manifest.json"),
               "evidence_sha256": hash_file(evidence.path),
               "science_status": "CHECKED_EXECUTION_NOT_VERIFIED_OR_REPRODUCED"}
    atomic_json(old_file, receipt)
    return receipt


def _dataset_hash(project: Path) -> str | None:
    from researchledger.hashing import sha256_path
    data = project / "_inputs" / "data"
    if data.is_symlink() or (data.is_dir() and any(p.is_symlink() for p in data.rglob('*'))):
        raise ValueError('dataset symlinks are forbidden for evidence provenance')
    return sha256_path(data) if data.exists() else None


def verify_run_receipt(project: Path) -> tuple[bool, str]:
    """Fail closed on tampering, stale measurements and severed claim edges."""
    project = Path(project).resolve()
    path = project / RUN_RECEIPT
    try:
        if not path.is_file() or path.is_symlink():
            return False, "missing research ledger S4 receipt"
        receipt = json.loads(path.read_text(encoding="utf-8"))
        rid, eid = receipt["run_id"], receipt["evidence_id"]
        ws = Workspace(project)
        manifest_path = ws.runs_dir / rid / "manifest.json"
        evidence_path = ws.evidence_dir / f"{eid}.md"
        results_path = project / "4_code" / "results.json"
        if (not manifest_path.is_file() or manifest_path.is_symlink() or
                not evidence_path.is_file() or evidence_path.is_symlink() or
                not results_path.is_file() or results_path.is_symlink()):
            return False, "missing or symlinked ledger record"
        if (receipt["manifest_sha256"] != hash_file(manifest_path) or
                receipt["evidence_sha256"] != hash_file(evidence_path) or
                receipt["results_sha256"] != hash_file(results_path)):
            return False, "ledger receipt or source result hash mismatch"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        origin = manifest.get("external_provenance", {})
        from factory.steps.code import tree_hash
        repo = project / "4_code" / "repo"
        if not repo.is_dir() or any(p.is_symlink() for p in repo.rglob("*")):
            return False, "generated repository absent or unsafe"
        source_data = json.loads(results_path.read_text(encoding="utf-8"))
        if (origin.get("repo_sha256") != tree_hash(repo) or
                origin.get("repo_sha256") != source_data.get("repo_sha256") or
                origin.get("image") != source_data.get("image") or
                origin.get("source_spec_sha256") != hash_file(project / "2_paper" / "results_spec.json") or
                origin.get("input_data_sha256") != _dataset_hash(project)):
            return False, "dataset, experiment implementation, image or results contract changed"
        if (manifest.get("run_id") != rid or not manifest.get("external_execution") or
                manifest.get("exit_code") != 0 or manifest.get("replay_supported") is not False or
                manifest.get("metrics_sha256") != hash_file(ws.runs_dir / rid / "metrics.json")):
            return False, "imported run manifest invalid or metrics changed"
        ev = load_evidence(ws).get(eid)
        if not ev or rid not in ev.runs or ev.status not in {"checked", "verified"}:
            return False, "evidence record absent, unlinked, or invalidated"
        if sorted(ev.supports) != sorted(receipt.get("claim_ids") or []):
            return False, "claim support links disagree with receipt"
        result = validate(ws)
        if result.errors:
            return False, "ledger validation errors: " + "; ".join(issue.code for issue in result.errors[:5])
        return True, "run and linked checked evidence verified for integrity; independent reproduction not established"
    except (OSError, ValueError, TypeError, KeyError, IndexError) as exc:
        return False, str(exc)


def ledger_report(project: Path) -> dict:
    project = Path(project).resolve()
    ws = Workspace(project)
    if not ws.is_workspace():
        return {"status": "NOT_INITIALIZED", "scientific_status": "UNVERIFIED", "issues": []}
    result = validate(ws)
    receipt_ok, receipt_note = verify_run_receipt(project)
    from researchledger.models import load_claims, load_evidence
    claims, evidence = load_claims(ws), load_evidence(ws)
    return {"status": "PASS" if not result.errors and receipt_ok else "BLOCKED",
            "graph_integrity": not bool(result.errors), "s4_receipt_valid": receipt_ok,
            "receipt_detail": receipt_note, "counts": result.counts,
            "claim_statuses": {key: value.status for key, value in claims.items()},
            "evidence_statuses": {key: value.status for key, value in evidence.items()},
            "independently_verified_evidence": sum(ev.status == "verified" for ev in evidence.values()),
            "independent_reproduction_status": "NOT_AUTOMATICALLY_ASSESSED",
            "scientific_status": "NOT_INDEPENDENTLY_VERIFIED",
            "issues": [{"code": item.code, "severity": item.level, "message": item.message}
                       for item in result.issues]}
