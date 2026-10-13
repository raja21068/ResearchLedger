"""Schema and semantic validation helpers for Idea Discovery V5."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from utils import log


def validate_json(data: Any, schema_path: str | Path, *, raise_on_error: bool = True) -> list[str]:
    """Validate data against a JSON Schema. Returns human-readable errors."""
    schema_path = Path(schema_path)
    with schema_path.open("r", encoding="utf-8") as f:
        schema = json.load(f)
    errors: list[str] = []
    try:
        from jsonschema import Draft202012Validator
        validator = Draft202012Validator(schema)
        for err in sorted(validator.iter_errors(data), key=lambda e: list(e.absolute_path)):
            path = ".".join(str(p) for p in err.absolute_path) or "$"
            errors.append(f"{path}: {err.message}")
    except ImportError:
        # Minimal fallback: enforce required top-level keys and expected top-level type.
        expected = schema.get("type")
        if expected == "object" and not isinstance(data, dict):
            errors.append("$: expected object")
        elif expected == "array" and not isinstance(data, list):
            errors.append("$: expected array")
        if isinstance(data, dict):
            for key in schema.get("required", []):
                if key not in data:
                    errors.append(f"$: missing required key '{key}'")
        log.warning("jsonschema is not installed; used minimal validation only")

    if errors and raise_on_error:
        raise ValueError("Schema validation failed: " + " | ".join(errors[:12]))
    return errors


def validate_semantics(stage: str, data: Any) -> list[str]:
    """Checks important scientific invariants not expressible cleanly in JSON Schema."""
    issues: list[str] = []
    if stage == "paper_record" and isinstance(data, dict):
        if not data.get("title"):
            issues.append("paper title is missing")
        if not data.get("paper_id"):
            issues.append("paper_id is missing")
        if not isinstance(data.get("claims", []), list):
            issues.append("claims must be a list")
        lim = data.get("limitations", {})
        if isinstance(lim, dict) and not lim.get("inferred"):
            issues.append("at least one inferred limitation is required")
    elif stage == "gap_analysis" and isinstance(data, dict):
        for gap in data.get("gaps", []):
            gid = gap.get("gap_id", "?")
            ev = gap.get("evidence", {})
            if not any(ev.get(k) for k in ("source", "empty_cells", "related_papers", "conflict_ids")):
                issues.append(f"{gid}: no traceable evidence")
            s = gap.get("scoring", {})
            a, b, c = s.get("impact"), s.get("feasibility"), s.get("novelty")
            if all(isinstance(x, (int, float)) for x in (a, b, c)):
                expected = a * b * c
                if s.get("priority_score") != expected:
                    issues.append(f"{gid}: priority_score {s.get('priority_score')} != {expected}")
    elif stage == "idea_report" and isinstance(data, dict):
        gap_ids = {x.get("gap_id") for x in data.get("traceability_matrix", [])}
        for idea in data.get("ideas", []):
            iid = idea.get("idea_id", "?")
            if not idea.get("source_gap"):
                issues.append(f"{iid}: missing source_gap")
            elif gap_ids and idea.get("source_gap") not in gap_ids:
                issues.append(f"{iid}: source_gap absent from traceability matrix")
            h = idea.get("hypothesis", {})
            if not h.get("statement") or not h.get("null_hypothesis"):
                issues.append(f"{iid}: hypothesis/null hypothesis incomplete")
            eo = idea.get("expected_outcomes", {})
            if not eo.get("if_negative"):
                issues.append(f"{iid}: negative-result value missing")
    return issues
