"""Methodology lock for Paper Studio (docs/RESEARCHLEDGER_OS_BLUEPRINT.md; user's manuscript-first advice).

When the "Method & experiment plan" stage is approved, the protocol (`paper/protocol.md`) and the declared result
slots (the slot_id | metric | unit | dataset | method columns of `paper/experimental_log.md`, never the values) are
fingerprinted and a copy is kept in `paper/locked/`. Later stages cannot be approved or run while either differs
from the lock. A change needs an amendment: a recorded reason, the experiments it affects, and your approval, which
creates the next lock version. The locked copies are never overwritten.

Pure file functions here; paper_studio.py owns the stored state and the gates.
"""
from __future__ import annotations

import difflib
import hashlib
import json
import re
from pathlib import Path

from . import experiments, quality

PROTOCOL = "paper/protocol.md"
LOG = experiments.LOG
LOCKED_DIR = "paper/locked"
PLANNED_TABLES = "paper/planned_tables.md"
DRAFT = "paper/pre_experiment_draft.md"
FORBIDDEN_SECTIONS = re.compile(r"^#{1,4}\s*(results?|conclusions?|findings)\b", re.I | re.M)


def _norm(text: str) -> str:
    return re.sub(r"[ \t]+", " ", re.sub(r"\r\n?", "\n", text)).strip()


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def read_slots(root: Path) -> list[dict]:
    """Declared slots without their values, sorted by id."""
    log = root / LOG
    if not log.is_file():
        return []
    rows = experiments.parse_slots(log.read_text(encoding="utf-8"))
    return sorted(({k: r[k] for k in ("slot_id", "metric", "unit", "dataset", "method")} for r in rows),
                  key=lambda r: r["slot_id"])


def fingerprint(root: Path) -> dict:
    p = root / PROTOCOL
    text = _norm(p.read_text(encoding="utf-8", errors="replace")) if p.is_file() else ""
    slots = read_slots(root)
    return {"protocol_sha256": _sha(text) if text else None,
            "slots_sha256": _sha(json.dumps(slots, sort_keys=True)) if slots else None, "slots": slots}


def take(root: Path, version: int) -> dict:
    """Snapshot the current protocol and slots as lock version `version`."""
    fp = fingerprint(root)
    if not fp["protocol_sha256"]:
        raise ValueError("paper/protocol.md is missing, so there is nothing to lock")
    d = root / LOCKED_DIR
    d.mkdir(parents=True, exist_ok=True)
    (d / f"protocol.v{version}.md").write_text((root / PROTOCOL).read_text(encoding="utf-8", errors="replace"),
                                               encoding="utf-8")
    (d / f"slots.v{version}.json").write_text(json.dumps(fp["slots"], indent=2), encoding="utf-8")
    return {"version": version, "protocol_sha256": fp["protocol_sha256"], "slots_sha256": fp["slots_sha256"],
            "protocol_file": f"{LOCKED_DIR}/protocol.v{version}.md", "slots_file": f"{LOCKED_DIR}/slots.v{version}.json"}


def compare(root: Path, lock: dict) -> dict:
    """How the current protocol and slots differ from a lock."""
    fp = fingerprint(root)
    locked_slots = {s["slot_id"]: s for s in json.loads((root / lock["slots_file"]).read_text(encoding="utf-8"))}
    now_slots = {s["slot_id"]: s for s in fp["slots"]}
    added = sorted(set(now_slots) - set(locked_slots))
    removed = sorted(set(locked_slots) - set(now_slots))
    changed = sorted(k for k in set(now_slots) & set(locked_slots) if now_slots[k] != locked_slots[k])
    protocol_changed = fp["protocol_sha256"] != lock["protocol_sha256"]
    diff = []
    if protocol_changed:
        old = (root / lock["protocol_file"]).read_text(encoding="utf-8", errors="replace").splitlines()
        cur = (root / PROTOCOL).read_text(encoding="utf-8", errors="replace").splitlines() if (root / PROTOCOL).is_file() else []
        diff = [l for l in difflib.unified_diff(old, cur, "locked", "now", n=1, lineterm="")][:120]
    return {"changed": protocol_changed or bool(added or removed or changed), "protocol_changed": protocol_changed,
            "slots_added": added, "slots_removed": removed, "slots_changed": changed, "diff": diff}


def restore(root: Path, lock: dict) -> dict:
    """Put the locked protocol back. Declared slots are put back too, but only while none has a measured value."""
    (root / PROTOCOL).write_text((root / lock["protocol_file"]).read_text(encoding="utf-8"), encoding="utf-8")
    note = None
    cur = compare(root, lock)
    if cur["slots_added"] or cur["slots_removed"] or cur["slots_changed"]:
        log = root / LOG
        text = log.read_text(encoding="utf-8") if log.is_file() else ""
        if any(str(r["value"]).strip().upper() != "TBD" for r in experiments.parse_slots(text)):
            note = ("The declared result slots differ from the lock and some already hold measured values, so they were "
                    "not changed automatically. Revert them by hand, or record an amendment.")
        else:
            locked = json.loads((root / lock["slots_file"]).read_text(encoding="utf-8"))
            rows = ["| slot_id | metric | unit | dataset | method | value |", "|---|---|---|---|---|---|"]
            rows += [f"| {s['slot_id']} | {s['metric']} | {s['unit']} | {s['dataset']} | {s['method']} | TBD |"
                     for s in locked]
            log.write_text("# Experimental log\n\n" + "\n".join(rows) + "\n", encoding="utf-8")
    return {"slots_note": note, **compare(root, lock)}


def planned_tables(root: Path) -> str:
    """Empty result tables built from the declared slots: one table per dataset, methods as rows, metrics as
    columns, every cell 'Pending'. Deterministic; no model, no numbers."""
    slots = read_slots(root)
    lines = ["# Planned result tables", "",
             "Generated from the declared result slots in `paper/experimental_log.md`. Every cell is **Pending** until a "
             "recorded run measures it. Metrics, units, datasets and methods are fixed by the locked protocol.", ""]
    if not slots:
        return "\n".join(lines + ["No result slots are declared yet.", ""])
    for dataset in sorted({s["dataset"] for s in slots}):
        rows = [s for s in slots if s["dataset"] == dataset]
        metrics = sorted({(s["metric"], s["unit"]) for s in rows})
        methods = sorted({s["method"] for s in rows})
        head = "| Method | " + " | ".join(f"{m} ({u})" if u and u not in {"-", "—"} else m for m, u in metrics) + " |"
        lines += [f"## Dataset: {dataset or '(unspecified)'}", "", head, "|---|" + "---|" * len(metrics)]
        for method in methods:
            cells = []
            for m, u in metrics:
                hit = next((s for s in rows if s["method"] == method and (s["metric"], s["unit"]) == (m, u)), None)
                cells.append(f"Pending (`{hit['slot_id']}`)" if hit else "n/a")
            lines.append(f"| {method} | " + " | ".join(cells) + " |")
        lines.append("")
    return "\n".join(lines)


def draft_report(root: Path) -> dict:
    """Checks on the pre-experiment draft: it must not contain results. Advisory: shown to the user, never silent."""
    p = root / DRAFT
    if not p.is_file():
        return {"exists": False, "result_numbers": [], "forbidden_sections": []}
    text = p.read_text(encoding="utf-8", errors="replace")
    body = re.sub(r"`[^`]*`", " ", text)  # inline code (slot ids, commands) is not a number
    nums = [m.group(1) for m in quality._NUM.finditer(body)]
    return {"exists": True, "result_numbers": sorted(set(nums))[:30],
            "forbidden_sections": [m.group(0).strip() for m in FORBIDDEN_SECTIONS.finditer(text)]}
