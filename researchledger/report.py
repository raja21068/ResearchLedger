"""Renders a ValidationResult as the `researchledger validate` / `report`
text or JSON output.
"""

from __future__ import annotations

import json

from .validator import ValidationResult

_LABEL_WIDTH = 28


def _plural(count: int, noun: str) -> str:
    return f"{count} {noun}" if count == 1 else f"{count} {noun}s"


def render_text(result: ValidationResult, *, strict: bool = False) -> str:
    lines = ["ResearchLedger Integrity Check", "─" * 40, ""]

    lines.append(f"{'Claims':<{_LABEL_WIDTH}}{result.counts.get('claims', 0):>4}")
    lines.append(f"{'Evidence records':<{_LABEL_WIDTH}}{result.counts.get('evidence', 0):>4}")
    lines.append(f"{'Runs':<{_LABEL_WIDTH}}{result.counts.get('runs', 0):>4}")
    lines.append(f"{'Decisions':<{_LABEL_WIDTH}}{result.counts.get('decisions', 0):>4}")
    lines.append("")

    metric_labels = [
        ("cross_reference_integrity", "Cross-reference integrity"),
        ("run_backed_evidence", "Run-backed evidence"),
        ("artifact_verification", "Artifact verification"),
        ("quantitative_claim_coverage", "Quantitative claim coverage"),
        ("reproducible_runs", "Reproducible runs"),
        ("chain_integrity", "Chain integrity"),
    ]
    for key, label in metric_labels:
        value = result.metrics.get(key, 0.0)
        lines.append(f"{label:<{_LABEL_WIDTH}}{value:>5.1f}%")

    errors = result.effective_errors(strict)
    warnings = result.effective_warnings(strict)
    escalated = [i for i in errors if i.level == "warning"] if strict else []

    if errors:
        lines.append("")
        lines.append("ERROR")
        for issue in errors:
            suffix = " (warning promoted by --strict)" if issue in escalated else ""
            lines.append(f"  {issue.code} {issue.message}{suffix}")
    if warnings:
        lines.append("")
        lines.append("WARNING")
        for issue in warnings:
            lines.append(f"  {issue.code} {issue.message}")

    lines.append("")
    lines.append(f"Result: {'PASS' if result.passed(strict) else 'FAIL'}")
    lines.append(f"{_plural(len(warnings), 'warning')}, {_plural(len(errors), 'error')}")
    return "\n".join(lines)


def render_json(result: ValidationResult, *, strict: bool = False) -> str:
    errors = result.effective_errors(strict)
    warnings = result.effective_warnings(strict)
    payload = {
        "counts": result.counts,
        "metrics": result.metrics,
        "strict": strict,
        "passed": result.passed(strict),
        "errors": [{"code": i.code, "message": i.message} for i in errors],
        "warnings": [{"code": i.code, "message": i.message} for i in warnings],
    }
    return json.dumps(payload, indent=2)
