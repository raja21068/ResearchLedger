"""Manuscript trace (docs/RESEARCHLEDGER_OS_BLUEPRINT.md §5 P6): for a .tex manuscript, where does each reported
number come from, and how well is it backed?

Read-only. Builds on the existing number matching in quality.py (numbers in tables and the abstract are matched to
values in results/*.json at the precision they are written) and adds the chain behind each match:
result file (slot) -> recorded run -> ledger evidence (E###) with its status.

A number is
- backed:   matches a measured result whose evidence you have checked or verified in the ledger;
- recorded: matches a measured result from a recorded run that is still only "observed" (not reviewed by you);
- measured: matches a results file but no recorded run or evidence is known for it;
- untraced: matches no measured result at all. Design values (a pre-registered threshold, a planned sample size)
  are expected here; a number that claims a finding is worth checking.
Placeholders (TBD, [RESULT: ...], [CITATION NEEDED]) are listed separately and are never counted as numbers.
Nothing here proves a number is correct: it shows where it came from and how far it has been reviewed.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from . import experiments, ledger_bridge, quality, workspace
from .db import Store

PLACEHOLDER = re.compile(r"\bTBD\b|\[RESULT:[^\]]*\]|\[CITATION NEEDED\]|\bXX(?:\.X+)?\b|\bplaceholder\b", re.I)
EVIDENCE_RANK = {"verified": 3, "checked": 2, "observed": 1}


def _slots(root: Path) -> dict[str, dict]:
    """Measured result files: slot id -> {value, unit, file}. Run logs and receipts are not results."""
    out = {}
    rdir = root / "results"
    for p in sorted(rdir.glob("*.json")) if rdir.is_dir() else []:
        if p.name == "provenance.json":
            continue
        data, err = experiments._read_result(p)
        if not err and isinstance(data["value"], (int, float)):
            out[p.stem] = {"value": float(data["value"]), "unit": data.get("unit"), "file": f"results/{p.name}"}
    return out


def _prov(root: Path) -> dict:
    try:
        return json.loads((root / experiments.PROVENANCE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _evidence_by_slot(store: Store, project_id: str) -> dict[str, dict]:
    """slot id -> the best ledger evidence that recorded it (most reviewed, then newest)."""
    try:
        ledger_bridge.safe_sync(store, project_id)
        ov = ledger_bridge.overview(store, project_id)
    except Exception:  # noqa: BLE001 — a missing or damaged ledger only means "no evidence known"
        return {}
    best: dict[str, dict] = {}
    for e in ov["evidence"]:
        for slot in e["values"]:
            cur = best.get(slot)
            key = (EVIDENCE_RANK.get(e["status"], 0), e["id"])
            if e["status"] in EVIDENCE_RANK and (not cur or key > (EVIDENCE_RANK.get(cur["status"], 0), cur["id"])):
                best[slot] = {"id": e["id"], "status": e["status"], "run": (e["app_ref"] or "").split(":")[0] or None,
                              "ledger_run": e["runs"][0] if e["runs"] else None}
    return best


def trace(store: Store, project_id: str, tex_rel: str) -> dict:
    root = workspace.project_root(project_id)
    tex_path = workspace.resolve(project_id, tex_rel)
    if tex_path.suffix.lower() != ".tex" or not tex_path.is_file():
        raise ValueError("choose a .tex manuscript in this project")
    tex = tex_path.read_text(encoding="utf-8", errors="replace")
    slots, prov, evid = _slots(root), _prov(root), _evidence_by_slot(store, project_id)

    numbers, used = [], set()
    for n in quality.reported_numbers(tex):
        x = n["value"]
        match = [s for s, v in slots.items() if quality.traced(x, [v["value"]])]
        item = {"value": x, "where": n["where"], "context": n["context"][:160], "slot": None, "backing": "untraced"}
        if match:
            # prefer the slot whose own value is closest to the printed value
            slot = min(match, key=lambda s: abs(slots[s]["value"] - float(x)))
            e = evid.get(slot)
            run = (e or {}).get("run") or (prov.get(slot) or {}).get("run_id")
            used.add(slot)
            item.update(slot=slot, file=slots[slot]["file"], unit=slots[slot]["unit"], run=run,
                        evidence=e and {"id": e["id"], "status": e["status"]},
                        other_slots=[s for s in match if s != slot][:3],
                        backing=("backed" if e and EVIDENCE_RANK[e["status"]] >= 2 else "recorded" if e
                                 else "measured"))
        numbers.append(item)

    t = quality.strip_comments(tex)
    placeholders = [{"line": i + 1, "text": line.strip()[:140]} for i, line in enumerate(t.splitlines())
                    if PLACEHOLDER.search(line)][:60]
    counts = {k: sum(1 for n in numbers if n["backing"] == k) for k in ("backed", "recorded", "measured", "untraced")}
    profile = quality.tex_profile(tex, None)
    slot_rows = [{"slot": s, "value": v["value"], "unit": v["unit"], "file": v["file"],
                  "used": s in used, "evidence": evid.get(s) and {"id": evid[s]["id"], "status": evid[s]["status"]},
                  "run": (evid.get(s) or {}).get("run") or (prov.get(s) or {}).get("run_id")}
                 for s, v in sorted(slots.items())]
    notes = []
    if counts["untraced"]:
        notes.append(f"{counts['untraced']} number(s) in tables or the abstract match no measured result. Planned "
                     "values such as thresholds and sample sizes are expected here; any number that claims a finding "
                     "should be checked, since it may have been typed in by hand.")
    if numbers and counts["backed"] == 0:
        notes.append("None of the reported numbers is backed by evidence you have checked or verified yet. "
                     "Review the evidence on the Evidence page.")
    if not slots:
        notes.append("This project has no measured result files yet, so no number can be traced.")
    return {"path": tex_rel, "numbers": numbers, "counts": counts, "reported": len(numbers),
            "placeholders": placeholders, "slots": slot_rows, "unused_slots": [r["slot"] for r in slot_rows if not r["used"]],
            "sources": profile["references_approx"], "sections": profile["sections"], "tables": profile["tables"],
            "figures": profile["figures"], "words": profile["words"], "notes": notes}
