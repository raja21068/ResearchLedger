"""An evidence-aware audit: model scores are not peer review or publication approval.

This audit is intentionally conservative. Neither a clean Docker exit nor a high
self-review score proves a method valid, a result genuine, or a citation correct.
"""
from __future__ import annotations

import json
from pathlib import Path

from factory.io import atomic_json, atomic_text
from factory.pipeline.orchestrator import Orchestrator


def read_object(path):
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def audit(project, context=None, write=True):
    project = Path(project).resolve()
    ctl = Orchestrator(project, context)
    completed = ctl.completed()
    code_result = read_object(project / "4_code" / "results.json")
    review = read_object(project / "5_refine" / "report.json")
    data_dir = project / "_inputs" / "data"
    has_data = data_dir.is_dir() and any(p.is_file() for p in data_dir.rglob("*"))
    # Unresolved is usually a list, not an object.
    try:
        unresolved_raw = json.loads((project / "4_code" / "unresolved.json").read_text())
    except (OSError, ValueError):
        unresolved_raw = []
    unresolved_count = len(unresolved_raw) if isinstance(unresolved_raw, list) else None
    sandbox_meta = all(code_result.get(key) for key in ("image", "repo_sha256", "command"))
    scientific_caveats = [
        "The sandbox proves execution isolation and reports exit status, not scientific correctness.",
        "Model-generated experimental implementations must be independently inspected and reproduced.",
        "Model self-review scores do not substitute for independent peer review or verified novelty.",
        "References, ethics, statistics, baselines and claims need human and/or independent checks.",
    ]
    issues = []
    if "S4" not in completed:
        issues.append("No valid, input-bound executed-code checkpoint for S4")
    if "S5" not in completed:
        issues.append("Final manuscript refinement has not met the automated score thresholds")
    if not sandbox_meta:
        issues.append("Results lack complete sandbox/repository provenance metadata")
    if code_result.get('scale') not in ('pilot', 'validation_data_attempt'):
        issues.append('Experiment scale not explicitly recorded')
    if code_result.get('scale') == 'validation_data_attempt':
        issues.append('Validation-data usage is a generated-code attestation, not independently checked')
    if unresolved_count is None or unresolved_count > 0:
        issues.append(f"Unresolved methodological choices: {unresolved_count if unresolved_count is not None else 'unknown'}")
    if not has_data:
        issues.append("No user-supplied dataset detected; verify whether synthetic data were used")
    else:
        issues.append("Dataset files are present but their actual use and rights were not verified")
    issue_flags = [{"severity": "review_required", "issue": issue} for issue in issues]
    from factory.integrations.ledger import enabled, ledger_report
    ledger = ledger_report(project) if enabled(context) else None
    if ledger is not None and ledger.get("status") != "PASS":
        issues.append("ResearchLedger provenance validation failed or evidence run receipt is missing")
    if ledger is not None and ledger.get("independently_verified_evidence", 0) == 0:
        issues.append("No independently verified evidence recorded; checked pilot results are not proof")
    issue_flags = [{"severity": "review_required", "issue": issue} for issue in issues]
    from factory.science.gates import audit as science_audit
    science = science_audit(project, context)
    result = {
        "schema_version": 2,
        "science_integrity": science,
        "project": project.name,
        "verified_stages": list(completed),
        "effective_state": ctl.effective_state(completed),
        "automated_thresholds_met": "S5" in completed and review.get("status") == "TARGET_REACHED",
        "scientific_status": "PILOT_OR_UNVERIFIED" if code_result else "NOT_EVALUATED",
        "publication_ready": False,
        "results_scale": code_result.get("scale", "unknown"),
        "dataset_files_present": has_data,
        "unresolved_count": unresolved_count,
        "researchledger": ledger,
        "warnings": issue_flags,
        "limitations": scientific_caveats,
        "manual_gates": ["Verify primary references, citations and prior-art claims",
                         "Reproduce all metrics and figures using independent execution",
                         "Check data lineage, dataset permissions and synthetic-versus-real labeling",
                         "Audit uncertainty, baselines, robustness, ablations and statistics",
                         "Check research ethics, conflicts, anonymization and target venue rules",
                         "Obtain independent domain-expert assessment"],
    }
    if write:
        directory = project / "control"
        directory.mkdir(parents=True, exist_ok=True)
        atomic_json(directory / "quality_report.json", result)
        lines = ["# Paper Factory quality and evidence audit", "", f"Project: `{project.name}`", "",
                 f"Verified pipeline state: **{result['effective_state']}**", "",
                 f"Automated review thresholds reached: **{result['automated_thresholds_met']}**", "",
                 "**Publication readiness: NOT CERTIFIED.** No automated score can confer it.", "",
                 "## Outstanding evidence / review items", ""]
        lines += [f"- {w['issue']}" for w in issue_flags] or ["- No additional machine-detectable issues."]
        lines += ["", "## Mandatory independent checks", ""]
        lines += [f"- {gate}" for gate in result["manual_gates"]]
        lines += ["", "## Boundaries of the audit", ""]
        lines += [f"- {item}" for item in scientific_caveats]
        atomic_text(directory / "quality_report.md", "\n".join(lines) + "\n")
    return result
