"""Measured results for Paper Studio: `results/<slot>.json` -> `paper/experimental_log.md`.

The "Run experiments" stage has the agent execute `code/`; this module is the deterministic
half. It reads every `results/*.json`, checks it against the slots declared in the experimental
log, writes the measured value into the log's table, and records where each value came from in
`results/provenance.json` (file, SHA-256, run id). A slot with no valid results file keeps `TBD`.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import datetime
from pathlib import Path

from .db import now

LOG = "paper/experimental_log.md"
PROVENANCE = "results/provenance.json"
_SEP = re.compile(r"^\s*\|?\s*:?-{2,}")


def _cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def parse_slots(text: str) -> list[dict]:
    """Rows of the slot table: slot_id | metric | unit | dataset | method | value."""
    slots = []
    for i, line in enumerate(text.splitlines()):
        if "|" not in line or _SEP.match(line):
            continue
        c = _cells(line)
        if len(c) < 6 or c[0].lower() in {"slot_id", "slot"}:
            continue
        if not re.fullmatch(r"[A-Za-z0-9_.\-]+", c[0]):
            continue
        slots.append({"line": i, "slot_id": c[0], "metric": c[1], "unit": c[2], "dataset": c[3],
                      "method": c[4], "value": c[5]})
    return slots


def _read_result(path: Path) -> tuple[dict | None, str | None]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None, "not valid JSON"
    if not isinstance(data, dict):
        return None, "not a JSON object"
    if str(data.get("slot_id", "")) != path.stem:
        return None, f"slot_id does not match the file name ({data.get('slot_id')!r})"
    v = data.get("value")
    if isinstance(v, bool) or v is None or (isinstance(v, float) and not math.isfinite(v)):
        return None, "value is missing or not a finite number/string"
    if not isinstance(v, (int, float, str)):
        return None, "value must be a number or short string"
    return data, None


def _epoch(iso: str | None) -> float | None:
    try:
        return datetime.fromisoformat(iso).timestamp() if iso else None
    except ValueError:
        return None


def collect(root: Path, run_id: str | None = None, since: str | None = None) -> dict:
    """Fill the log from results/*.json. Returns {slots, measured, pending, issues}.

    `since` (ISO time the run was created): a results file last written before it was not produced by this run, so
    it is never attributed to `run_id`; an unchanged file keeps the provenance it already had."""
    log = root / LOG
    if not log.is_file():
        return {"slots": 0, "measured": 0, "pending": 0, "issues": [f"{LOG} is missing"]}
    text = log.read_text(encoding="utf-8")
    slots = parse_slots(text)
    declared = {s["slot_id"] for s in slots}
    results_dir = root / "results"
    found, issues = {}, []
    for p in sorted(results_dir.glob("*.json")) if results_dir.is_dir() else []:
        if p.name == "provenance.json":
            continue
        data, err = _read_result(p)
        if err:
            issues.append(f"results/{p.name}: {err}")
        elif p.stem not in declared:
            issues.append(f"results/{p.name}: slot '{p.stem}' is not declared in the experimental log")
        else:
            found[p.stem] = (p, data)
    lines = text.splitlines()
    since_ts = _epoch(since)
    prov_path = root / PROVENANCE
    try:
        prov = json.loads(prov_path.read_text(encoding="utf-8")) if prov_path.is_file() else {}
    except json.JSONDecodeError:
        prov = {}
    for s in slots:
        if s["slot_id"] not in found:
            continue
        p, data = found[s["slot_id"]]
        value = data["value"]
        cells = _cells(lines[s["line"]])
        cells[5] = str(value)
        lines[s["line"]] = "| " + " | ".join(cells) + " |"
        sha = hashlib.sha256(p.read_bytes()).hexdigest()
        attributed = run_id
        if since_ts is not None and p.stat().st_mtime < since_ts:
            old = prov.get(s["slot_id"])
            if old and old.get("sha256") == sha:
                continue  # unchanged file from an earlier run: keep its provenance as it was
            attributed = None
            issues.append(f"results/{p.name}: written before this run started, so it is not attributed to it")
        prov[s["slot_id"]] = {"file": f"results/{p.name}", "value": value, "unit": data.get("unit"),
                              "seed": data.get("seed"), "source": data.get("source"), "location": data.get("location"), "sha256": sha,
                              "run_id": attributed, "collected_at": now()}
    if found:
        log.write_text("\n".join(lines) + ("\n" if text.endswith("\n") else ""), encoding="utf-8")
        prov_path.parent.mkdir(parents=True, exist_ok=True)
        prov_path.write_text(json.dumps(prov, indent=2), encoding="utf-8")
    return {"slots": len(slots), "measured": len(found), "pending": len(slots) - len(found),
            "issues": issues, "measured_slots": sorted(found)}


def summary(root: Path) -> dict:
    """Read-only counts for the UI (no files changed)."""
    log = root / LOG
    if not log.is_file():
        return {"slots": 0, "measured": 0, "pending": 0}
    slots = parse_slots(log.read_text(encoding="utf-8"))
    measured = sum(1 for s in slots if (root / "results" / f"{s['slot_id']}.json").is_file())
    return {"slots": len(slots), "measured": measured, "pending": len(slots) - measured}
