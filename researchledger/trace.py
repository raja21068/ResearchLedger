"""Provenance tracing: `researchledger trace <id>`.

Forward, from a claim or evidence id: paper -> claim -> evidence -> run ->
metrics -> artifact -> SHA-256. Reverse, from a run id: which evidence,
claims and manuscript sections depend on that run. This is what makes
"paper statement -> claim -> evidence -> run -> metrics -> raw artifact" a
question you can actually ask, in both directions, instead of a design
principle you have to take on faith.
"""

from __future__ import annotations

import json
import re

from .hashing import sha256_file
from .models import Evidence, load_claims, load_evidence
from .workspace import Workspace

_CHECK = "✓"
_CROSS = "✗"


def _load_run_manifest(ws: Workspace, run_id: str) -> dict | None:
    manifest_path = ws.runs_dir / run_id / "manifest.json"
    if not manifest_path.exists():
        return None
    try:
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _run_lines(ws: Workspace, run_id: str, indent: str) -> list[str]:
    manifest = _load_run_manifest(ws, run_id)
    if manifest is None:
        return [f"{indent}{run_id} (MISSING)"]

    lines = [f"{indent}{run_id} [{manifest.get('status')}]"]
    inner = indent + "    "
    seed = (manifest.get("randomness") or {}).get("seed")
    if seed is not None:
        lines.append(f"{inner}seed {seed}")

    run_dir = ws.runs_dir / run_id
    metrics_name = manifest.get("metrics")
    if metrics_name:
        metrics_path = run_dir / metrics_name
        if metrics_path.exists():
            try:
                metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
                if isinstance(metrics, dict):
                    for key, value in list(metrics.items())[:5]:
                        lines.append(f"{inner}{key} = {value}")
            except json.JSONDecodeError:
                pass
            lines.append(f"{inner}{metrics_name} {_CHECK}")
        else:
            lines.append(f"{inner}{metrics_name} {_CROSS} (missing)")

    artifacts = manifest.get("artifacts") or []
    if artifacts:
        verified = sum(
            1
            for a in artifacts
            if (run_dir / a["path"]).exists() and sha256_file(run_dir / a["path"]) == a.get("sha256")
        )
        mark = _CHECK if verified == len(artifacts) else _CROSS
        lines.append(f"{inner}artifact hashes {mark} ({verified}/{len(artifacts)})")
    return lines


def _manuscript_usage(ws: Workspace, claim_id: str) -> list[str]:
    lines: list[str] = []
    for paper_path in sorted(ws.papers_dir.glob("*/paper.md")) if ws.papers_dir.exists() else []:
        text = paper_path.read_text(encoding="utf-8")
        sections: list[str] = []
        current_section = "(preamble)"
        pattern = re.compile(rf"\b{re.escape(claim_id)}\b")
        for line in text.splitlines():
            heading = re.match(r"^#{1,6}\s+(.*)", line)
            if heading:
                current_section = heading.group(1).strip()
                continue
            if pattern.search(line) and current_section not in sections:
                sections.append(current_section)
        if sections:
            label = f"{paper_path.parent.name}/paper.md"
            lines.append(label)
            for section in sections:
                lines.append(f"    · {section}")
    return lines


def _evidence_block(ws: Workspace, evidence_id: str, evidence_map: dict[str, Evidence], indent: str) -> list[str]:
    ev = evidence_map.get(evidence_id)
    if ev is None:
        return [f"{indent}{evidence_id} (MISSING)"]
    lines = [f"{indent}{evidence_id} [{ev.status}]"]
    inner = indent + "    "
    if ev.runs:
        for run_id in ev.runs:
            lines.extend(_run_lines(ws, run_id, inner))
    else:
        lines.append(f"{inner}(no runs — {ev.source_kind or 'non-experimental'} evidence)")
    return lines


def trace_claim(ws: Workspace, claim_id: str) -> str:
    claims_map = load_claims(ws)
    evidence_map = load_evidence(ws)
    claim = claims_map.get(claim_id)
    if claim is None:
        return f"{claim_id} (MISSING — no such claim)"

    lines = [claim_id, f'"{claim.statement()}"' if claim.statement() else "", ""]
    for eid in claim.evidence:
        lines.extend(_evidence_block(ws, eid, evidence_map, ""))
        lines.append("")

    usage = _manuscript_usage(ws, claim_id)
    if usage:
        lines.append("Manuscript usage")
        for entry in usage:
            lines.append(f"    {entry}" if not entry.startswith(" ") else entry)

    return "\n".join(line for line in lines if line is not None).rstrip() + "\n"


def trace_evidence(ws: Workspace, evidence_id: str) -> str:
    evidence_map = load_evidence(ws)
    if evidence_id not in evidence_map:
        return f"{evidence_id} (MISSING — no such evidence)"
    return "\n".join(_evidence_block(ws, evidence_id, evidence_map, "")) + "\n"


def trace_run_reverse(ws: Workspace, run_id: str) -> str:
    """Reverse trace: everything that cites this run."""
    manifest = _load_run_manifest(ws, run_id)
    evidence_map = load_evidence(ws)
    claims_map = load_claims(ws)

    lines = [run_id]
    if manifest is None:
        lines.append("  (MISSING — no manifest.json)")
        return "\n".join(lines) + "\n"

    lines.append(
        f"status: {manifest.get('status')}, exit_code {manifest.get('exit_code')}, "
        f"seed {(manifest.get('randomness') or {}).get('seed')}"
    )
    lines.append("")

    citing_evidence = [ev for ev in evidence_map.values() if run_id in ev.runs]
    if not citing_evidence:
        lines.append("Depended on by: (nothing yet — no evidence cites this run)")
        return "\n".join(lines) + "\n"

    lines.append("Depended on by:")
    for ev in citing_evidence:
        lines.append(f"  {ev.id} [{ev.status}]")
        for cid in ev.supports:
            claim = claims_map.get(cid)
            status = f" [{claim.status}]" if claim else " (MISSING)"
            lines.append(f"      supports: {cid}{status}")
            usage = _manuscript_usage(ws, cid)
            for entry in usage:
                lines.append(f"          used in: {entry}")
    return "\n".join(lines) + "\n"


def trace(ws: Workspace, entity_id: str) -> str:
    entity_id = entity_id.strip().upper()
    if entity_id.startswith("C"):
        return trace_claim(ws, entity_id)
    if entity_id.startswith("E"):
        return trace_evidence(ws, entity_id)
    if entity_id.startswith("R"):
        return trace_run_reverse(ws, entity_id)
    raise ValueError(f"Unrecognized id: {entity_id!r} (expected C###, E### or R####)")
