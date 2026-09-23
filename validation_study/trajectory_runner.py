#!/usr/bin/env python3
"""Ledger-integrated tracked trajectory replay.

For each of the 13 historical semantic replay cases this harness executes the
old and revised tool behavior as *separate immutable ResearchLedger runs*, binds
the old result to evidence and a claim, supersedes the old evidence after the
historical revision, binds the revised result as replacement evidence, and
verifies that manuscript provenance recovers when its evidence marker is moved
to the replacement evidence.

This is a bridge experiment, not the confirmatory Paper2Agent study.  The tool
being executed is ``paper_agent_proxy.py`` (a deterministic semantic proxy),
not a Paper2Agent-generated MCP server, and the claim/evidence binding is
constructed by the study authors rather than independent annotators.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STUDY = Path(__file__).resolve().parent
RESULTS = STUDY / "results"
WORKSPACES = STUDY / "tracked_trajectory_workspaces"
PROXY_SOURCE = STUDY / "paper_agent_proxy.py"
REPLAY_SOURCE = STUDY / "run_semantic_replay.py"
EXPANDED_SOURCE = STUDY / "analysis" / "expanded_semantic_replay.py"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from researchledger.evidence import create_evidence  # noqa: E402
from researchledger.hashing import sha256_file  # noqa: E402
from researchledger.models import Claim, load_claims  # noqa: E402
from researchledger.revision import apply_evidence_revision  # noqa: E402
from researchledger.runner import run_command  # noqa: E402
from researchledger.validate_paper import audit_paper  # noqa: E402
from researchledger.validator import validate  # noqa: E402
from researchledger.workspace import init_workspace  # noqa: E402


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _load_cases() -> list[dict]:
    p = RESULTS / "prr_executed_semantic_replay_v2.json"
    if not p.exists():
        raise RuntimeError(f"missing {p}; run analysis/expanded_semantic_replay.py first")
    return json.loads(p.read_text(encoding="utf-8"))["cases"]


def _git_init(path: Path) -> str:
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "validation@example.invalid"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "ResearchLedger validation"], cwd=path, check=True)
    subprocess.run(["git", "add", "."], cwd=path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "Freeze proxy trajectory harness"], cwd=path, check=True)
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=path, text=True).strip()


def _copy_proxy_runtime(workspace: Path) -> Path:
    runtime = workspace / "proxy_runtime"
    (runtime / "analysis").mkdir(parents=True, exist_ok=True)
    shutil.copy2(PROXY_SOURCE, runtime / "paper_agent_proxy.py")
    shutil.copy2(REPLAY_SOURCE, runtime / "run_semantic_replay.py")
    shutil.copy2(EXPANDED_SOURCE, runtime / "analysis" / "expanded_semantic_replay.py")
    (runtime / "analysis" / "__init__.py").write_text("", encoding="utf-8")
    return runtime / "paper_agent_proxy.py"


def _artifact_sha(manifest: dict, suffix: str = "result.json") -> str | None:
    for a in manifest.get("artifacts", []):
        if a.get("path", "").endswith(suffix):
            return a.get("sha256")
    return None


def _write_claim(ws, statement: str) -> Claim:
    path = ws.claims_dir / "C001.md"
    claim = Claim(
        id="C001",
        path=path,
        schema_version="2.0",
        name="Frozen historical result remains admissible",
        status="hypothesis",
        evidence=[],
        support_sets=[],
        contradicts=[],
        body=f"# Claim: Frozen historical result\n\n## Statement\n{statement}\n",
        raw_frontmatter={"created_at": _now(), "updated_at": _now()},
    )
    path.write_text(claim.render(), encoding="utf-8")
    return claim


def _write_paper(ws, evidence_id: str, case_number: int, case_id: str) -> Path:
    pdir = ws.papers_dir / "main"
    pdir.mkdir(parents=True, exist_ok=True)
    paper = pdir / "paper.md"
    # Contains a digit so validate-paper treats it as a quantitative assertion.
    paper.write_text(
        "# Tracked revision trajectory\n\n"
        f"For validation case {case_number}, the frozen result for {case_id} is admissible under the currently cited evidence.\n"
        f"<!-- rl:claim=C001 evidence={evidence_id} -->\n",
        encoding="utf-8",
    )
    return paper


def _audit_dict(audit) -> dict:
    return {
        "quantitative_assertions": audit.quantitative_assertions,
        "linked_to_claims": audit.linked_to_claims,
        "backed_by_verified_evidence": audit.backed_by_verified_evidence,
        "backed_by_reproducible_runs": audit.backed_by_reproducible_runs,
        "unsupported": audit.unsupported,
        "stale_evidence_usage": audit.stale_evidence_usage,
    }


def run_case(case: dict, case_number: int, *, clean: bool = True) -> dict:
    case_id = case["case_id"]
    ws_root = WORKSPACES / case_id
    if clean and ws_root.exists():
        shutil.rmtree(ws_root)
    ws_root.mkdir(parents=True, exist_ok=True)
    ws = init_workspace(ws_root)
    proxy = _copy_proxy_runtime(ws_root)
    (ws_root / "project.md").write_text(f"# Validation trajectory {case_id}\n", encoding="utf-8")
    harness_commit = _git_init(ws_root)

    statement = (
        f"The frozen result for {case_id} is admissible for the pinned historical source state."
    )
    _write_claim(ws, statement)

    t0 = time.perf_counter()
    old_manifest = run_command(
        ws,
        [sys.executable, str(proxy), "--case", case_id, "--version", "old"],
        cwd=ws_root,
        claims=["C001"],
    )
    old_run_time = time.perf_counter() - t0
    old_evidence = create_evidence(
        ws,
        from_run=old_manifest["run_id"],
        supports=["C001"],
        source_kind="computation",
        status="checked",
        name=f"Old frozen output for {case_id}",
    )
    promote_old = apply_evidence_revision(ws, {old_evidence.id: "verified"}, reason="freeze old result")
    claim_before = load_claims(ws)["C001"].status
    paper = _write_paper(ws, old_evidence.id, case_number, case_id)
    audit_before = _audit_dict(audit_paper(ws, paper))

    t1 = time.perf_counter()
    new_manifest = run_command(
        ws,
        [sys.executable, str(proxy), "--case", case_id, "--version", "new"],
        cwd=ws_root,
        claims=["C001"],
    )
    new_run_time = time.perf_counter() - t1

    t2 = time.perf_counter()
    invalidate_old = apply_evidence_revision(
        ws,
        {old_evidence.id: "superseded"},
        reason=(
            f"historical revision {case['base_commit'][:12]} -> {case['revision_commit'][:12]}"
        ),
    )
    time_to_safe_state = time.perf_counter() - t2
    claim_after_invalidation = load_claims(ws)["C001"].status
    audit_stale = _audit_dict(audit_paper(ws, paper))

    t3 = time.perf_counter()
    new_evidence = create_evidence(
        ws,
        from_run=new_manifest["run_id"],
        supports=["C001"],
        source_kind="computation",
        status="checked",
        name=f"Revised frozen output for {case_id}",
    )
    promote_new = apply_evidence_revision(ws, {new_evidence.id: "verified"}, reason="verify revised result")
    _write_paper(ws, new_evidence.id, case_number, case_id)
    recovery_time = time.perf_counter() - t3
    claim_after_recovery = load_claims(ws)["C001"].status
    audit_recovered = _audit_dict(audit_paper(ws, paper))

    final_validation = validate(ws)
    old_sha = _artifact_sha(old_manifest)
    new_sha = _artifact_sha(new_manifest)

    return {
        "case_id": case_id,
        "repository": case["repository"],
        "base_commit": case["base_commit"],
        "revision_commit": case["revision_commit"],
        "replay_mode": case["replay_mode"],
        "trajectory_mode": "ledger-integrated-paper-agent-proxy",
        "harness_git_commit": harness_commit,
        "old_run_id": old_manifest["run_id"],
        "new_run_id": new_manifest["run_id"],
        "old_output_sha256": old_sha,
        "new_output_sha256": new_sha,
        "output_changed": bool(old_sha and new_sha and old_sha != new_sha),
        "old_evidence": old_evidence.id,
        "new_evidence": new_evidence.id,
        "claim_state_before_revision": claim_before,
        "claim_state_after_old_evidence_superseded": claim_after_invalidation,
        "claim_state_after_recovery": claim_after_recovery,
        "paper_audit_before": audit_before,
        "paper_audit_after_invalidation": audit_stale,
        "paper_audit_after_recovery": audit_recovered,
        "promotion_transaction": promote_old["txid"],
        "invalidation_transaction": invalidate_old["txid"],
        "recovery_transaction": promote_new["txid"],
        "old_tool_seconds": old_run_time,
        "new_tool_seconds": new_run_time,
        "time_to_safe_state_seconds": time_to_safe_state,
        "recovery_seconds_excluding_tool_execution": recovery_time,
        "final_validation_errors": len(final_validation.errors),
        "final_validation_warnings": len(final_validation.warnings),
        "lifecycle_ok": (
            claim_before == "supported"
            and claim_after_invalidation == "hypothesis"
            and claim_after_recovery == "supported"
            and audit_before["backed_by_verified_evidence"] == 1
            and audit_stale["stale_evidence_usage"] == 1
            and audit_stale["backed_by_verified_evidence"] == 0
            and audit_recovered["stale_evidence_usage"] == 0
            and audit_recovered["backed_by_verified_evidence"] == 1
            and not final_validation.errors
        ),
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Run ledger-integrated old/new proxy trajectories.")
    p.add_argument("--case", action="append", dest="case_ids", help="Run only this case id (repeatable)")
    p.add_argument("--fresh", action="store_true", help="Ignore cached per-case results and rerun selected cases")
    args = p.parse_args(argv)

    RESULTS.mkdir(parents=True, exist_ok=True)
    WORKSPACES.mkdir(parents=True, exist_ok=True)
    case_results_dir = RESULTS / "tracked_trajectory_cases"
    case_results_dir.mkdir(parents=True, exist_ok=True)
    all_cases = _load_cases()
    selected = [c for c in all_cases if not args.case_ids or c["case_id"] in set(args.case_ids)]
    if args.case_ids:
        missing = sorted(set(args.case_ids) - {c["case_id"] for c in selected})
        if missing:
            raise SystemExit(f"unknown case id(s): {', '.join(missing)}")

    for case in selected:
        case_id = case["case_id"]
        cache = case_results_dir / f"{case_id}.json"
        if cache.exists() and not args.fresh:
            print(f"[cached] {case_id}", flush=True)
            continue
        case_number = next(i for i, c in enumerate(all_cases, start=1) if c["case_id"] == case_id)
        print(f"[{case_number}/{len(all_cases)}] {case_id}", flush=True)
        row = run_case(case, case_number, clean=True)
        cache.write_text(json.dumps(row, indent=2) + "\n", encoding="utf-8")

    # Aggregate every completed case so partial/resumed invocations are useful.
    rows = []
    for case in all_cases:
        cache = case_results_dir / f"{case['case_id']}.json"
        if cache.exists():
            rows.append(json.loads(cache.read_text(encoding="utf-8")))

    payload = {
        "schema": "researchledger-tracked-trajectory-proxy-1",
        "scope": (
            "Thirteen historical semantic revisions executed as separate old/new immutable "
            "ResearchLedger runs, with persisted evidence/claim invalidation and recovery. "
            "The executable tool is a deterministic paper-agent proxy, not a Paper2Agent MCP, "
            "and claim bindings are author-constructed; this is therefore a bridge/conformance "
            "experiment rather than independent external validation."
        ),
        "n_cases": len(rows),
        "n_output_changes": sum(r["output_changed"] for r in rows),
        "n_lifecycle_ok": sum(r["lifecycle_ok"] for r in rows),
        "n_repositories": len({r["repository"] for r in rows}),
        "cases": rows,
    }
    out = RESULTS / "tracked_trajectory_proxy.json"
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    cols = [
        "case_id", "repository", "output_changed", "claim_state_before_revision",
        "claim_state_after_old_evidence_superseded", "claim_state_after_recovery",
        "time_to_safe_state_seconds", "lifecycle_ok",
    ]
    lines = [",".join(cols)]
    for r in rows:
        lines.append(",".join(str(r[c]).lower() if isinstance(r[c], bool) else str(r[c]) for c in cols))
    (RESULTS / "tracked_trajectory_proxy_summary.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps({k: payload[k] for k in ("n_cases", "n_repositories", "n_output_changes", "n_lifecycle_ok")}, indent=2))
    return 0 if payload["n_lifecycle_ok"] == payload["n_cases"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
