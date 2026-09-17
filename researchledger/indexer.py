"""Builds `.researchledger/index.json`: a small, precomputed summary of the
research graph that the UserPromptSubmit hook reads instead of re-scanning
and re-parsing every ledger file on every prompt (point 16 of the v2 spec).

Recomputed by `researchledger index`, and automatically refreshed at the end
of `run`, `validate`, and `migrate` — any command that could have changed
the graph. A workspace that never runs the CLI simply has no index yet; the
hook's fallback scan (hooks/inject_research_context.py) covers that case.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from .atomic import atomic_write_json
from .models import load_claims, load_evidence
from .validator import list_runs, validate
from .workspace import Workspace

INDEX_SCHEMA_VERSION = "2.0"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _count_glob(directory: Path, pattern: str) -> int:
    return len(list(directory.glob(pattern))) if directory.exists() else 0


def build_index(ws: Workspace) -> dict:
    evidence = load_evidence(ws)
    claims = load_claims(ws)
    runs = list_runs(ws)
    result = validate(ws)

    evidence_status_counts: dict[str, int] = {}
    for ev in evidence.values():
        evidence_status_counts[ev.status] = evidence_status_counts.get(ev.status, 0) + 1

    claim_status_counts: dict[str, int] = {}
    for cl in claims.values():
        claim_status_counts[cl.status] = claim_status_counts.get(cl.status, 0) + 1

    top_issues = [
        {"level": i.level, "code": i.code, "message": i.message}
        for i in (result.errors + result.warnings)[:5]
    ]

    file_counts = {
        "evidence": _count_glob(ws.evidence_dir, "E*.md"),
        "claims": _count_glob(ws.claims_dir, "C*.md"),
        "decisions": _count_glob(ws.decisions_dir, "D*.md"),
        "runs": len(runs),
        "papers": _count_glob(ws.papers_dir, "*/paper.md"),
    }

    return {
        "schema_version": INDEX_SCHEMA_VERSION,
        "generated_at": _now(),
        "file_counts": file_counts,
        "counts": result.counts,
        "evidence_status_counts": evidence_status_counts,
        "claim_status_counts": claim_status_counts,
        "literature_evidence": sum(1 for ev in evidence.values() if ev.source_kind == "literature"),
        "metrics": result.metrics,
        "errors": len(result.errors),
        "warnings": len(result.warnings),
        "top_issues": top_issues,
    }


def write_index(ws: Workspace) -> Path:
    index = build_index(ws)
    path = ws.root / ".researchledger" / "index.json"
    atomic_write_json(path, index)
    return path
