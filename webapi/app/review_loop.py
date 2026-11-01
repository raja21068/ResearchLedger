"""Review <-> revise loop (up to 3 rounds) for Paper Studio.

Round 1 is the normal Review + Revise stages. Rounds 2 and 3 are started by the user from the
Revise stage: one agent task re-reviews the latest revised manuscript, revises it and records,
for every earlier concern, whether it is resolved. The loop stops when no VERIFIED major concern
is still open, or after round 3. The stop decision is computed here from the CSV files, not
trusted from the agent's prose.

Files (workspace-relative):
  round 1: review/concern_matrix.csv, review/closure.csv, paper/main_revised.tex
  round N: review/round_N/concern_matrix.csv, review/round_N/closure.csv,
           paper/main_revised_rN.tex (+ .pdf), review/round_N/response_letter.md
"""
from __future__ import annotations

import csv
from pathlib import Path

from . import claude_runner, workspace
from .config import REPO_ROOT
from .db import Store, new_id, now

MAX_ROUNDS = 3
SKILL = "D:/AutoResearch/academic-research-skills-offline/3- paper-writing/Master_Auto_Review_Loop_SKILL.md"
LEAN = "vendor/20- Paper Review Agent/Referee-Lean-v2/core"
MAJOR = {"major", "critical", "high", "blocker"}


def round_files(n: int) -> dict[str, str]:
    if n == 1:
        return {"matrix": "review/concern_matrix.csv", "closure": "review/closure.csv",
                "tex": "paper/main_revised.tex", "pdf": "paper/main_revised.pdf",
                "response": "review/response_letter.md"}
    return {"matrix": f"review/round_{n}/concern_matrix.csv", "closure": f"review/round_{n}/closure.csv",
            "tex": f"paper/main_revised_r{n}.tex", "pdf": f"paper/main_revised_r{n}.pdf",
            "response": f"review/round_{n}/response_letter.md"}


def _rows(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    with path.open(encoding="utf-8", newline="") as f:
        return [{(k or "").strip().lower(): (v or "").strip() for k, v in r.items()} for r in csv.DictReader(f)]


def _is_verified_major(row: dict) -> bool:
    return row.get("severity", "").lower() in MAJOR and row.get("verification", "").upper() == "VERIFIED"


def summarize(root: Path) -> dict:
    """Per-round concerns with resolved/open status, and why the loop stops (or not)."""
    rounds, stop, last = [], None, 0
    for n in range(1, MAX_ROUNDS + 1):
        files = round_files(n)
        matrix = _rows(root / files["matrix"])
        if not matrix:
            break
        closure = {r.get("id", ""): r for r in _rows(root / files["closure"])}
        concerns = []
        for r in matrix:
            c = closure.get(r.get("id", ""), {})
            status = c.get("status", "").lower()
            concerns.append({"id": r.get("id", ""), "severity": r.get("severity", ""),
                             "verification": r.get("verification", "").upper(), "concern": r.get("concern", "")[:300],
                             "status": "resolved" if status == "resolved" else "open",
                             "evidence": c.get("evidence", "")[:300], "verified_major": _is_verified_major(r)})
        open_vm = sum(1 for c in concerns if c["verified_major"] and c["status"] == "open")
        closed = bool(closure)
        rounds.append({"round": n, "concerns": concerns, "closed": closed, "open_verified_major": open_vm,
                       "has_revision": (root / files["tex"]).is_file()})
        last = n
        if closed and open_vm == 0:
            stop = "no verified major concern is open"
            break
        if closed and n == MAX_ROUNDS:
            stop = f"{MAX_ROUNDS} rounds done; {open_vm} verified major concern(s) still open"
    return {"rounds": rounds, "stop_reason": stop, "last_round": last,
            "latest_tex": next((round_files(r["round"])["tex"] for r in reversed(rounds) if r["has_revision"]), None)}


def _prompt(n: int, prev_tex: str, prev_matrix: str, open_ids: list[str]) -> str:
    f = round_files(n)
    engines = [SKILL, f"{REPO_ROOT / LEAN}/LEAN_CORE_REVIEWER_PROMPT.md", f"{REPO_ROOT / LEAN}/INDEPENDENT_VERIFIER_PROMPT.md",
               f"{REPO_ROOT / LEAN}/SEVERITY_ACTIONABILITY.md", str(REPO_ROOT / "skills/manuscript-revision/SKILL.md")]
    return (f"Paper Studio — review ↔ revise loop, round {n} of {MAX_ROUNDS}.\n"
            "Engine instructions — read first (the Master Auto Review Loop skill is the method; run the paper mode, "
            "without Codex or other external backends):\n" + "\n".join(f"- {e}" for e in engines) +
            f"\n\nCurrent manuscript: `{prev_tex}`. Previous concerns: `{prev_matrix}`. "
            f"Still-open concern ids to look at first: {', '.join(open_ids) or '(none)'}.\n\n"
            f"Task: (1) Re-review the current manuscript with the Referee-Lean perspectives and independent verifier; quote "
            f"the passage for every major concern and mark it VERIFIED, UNVERIFIED or REJECTED. Write `{f['matrix']}` "
            "(id,reviewer,severity,location,concern,quote,verification,minimum_fix,closure_criterion). Reuse earlier ids "
            "for the same concern; new ones get new ids. (2) Revise: write the revised manuscript to "
            f"`{f['tex']}` (keep `{prev_tex}` unchanged), compile `{f['pdf']}`. Fix VERIFIED concerns first; only "
            "wording, structure, claims and presentation — do not add experiments or numbers that are not in "
            "`results/*.json`. (3) Write `" + f["closure"] + "` (id,status,evidence) with status `resolved` or `open` "
            "for EVERY concern id in the matrix, with the changed location as evidence. (4) Write `" + f["response"] +
            "`. Never average scores or predict acceptance. Never hide an unresolved concern. "
            "Keep a TodoWrite checklist. Never invent data, results or citations.")


def next_round(store: Store, project_id: str, state: dict, save) -> dict:
    """Queue the next loop round. `save(project_id, state)` persists studio.json."""
    root = workspace.project_root(project_id)
    s = summarize(root)
    if not s["rounds"] or not s["rounds"][0]["closed"]:
        raise ValueError("finish the Revise stage (with review/closure.csv) before starting more rounds")
    if s["stop_reason"]:
        raise ValueError("the loop has stopped: " + s["stop_reason"])
    closed = [r for r in s["rounds"] if r["closed"]]
    n = closed[-1]["round"] + 1  # a round that wrote its matrix but never closed is simply redone
    if n > MAX_ROUNDS:
        raise ValueError("maximum rounds reached")
    loop = state.setdefault("loop", {})
    prev = loop.get(str(n))
    if prev and prev.get("run_id"):
        run = store.one("SELECT status FROM runs WHERE id=?", (prev["run_id"],))
        if run and run["status"] in {"queued", "running"}:
            raise ValueError(f"round {n} is already running")
    last = closed[-1]
    prev_files = round_files(last["round"])
    base_tex = next((round_files(r["round"])["tex"] for r in reversed(closed) if r["has_revision"]), "paper/main.tex")
    prompt = _prompt(n, base_tex, prev_files["matrix"],
                     [c["id"] for c in last["concerns"] if c["status"] == "open"])
    rid, ts = new_id("run"), now()
    store.exec("INSERT INTO runs(id,project_id,conversation_id,kind,prompt,status,provider,created_at) "
               "VALUES (?,?,?,?,?,?,?,?)", (rid, project_id, state["conversation_id"], f"paper:review_round_{n}", prompt,
                                           "queued", "claude_code_cli", ts))
    loop[str(n)] = {"run_id": rid, "started_at": ts}
    save(project_id, state)
    store.log_activity(project_id, "paper_review_round_started", f"{n} {rid}")
    claude_runner.start_run(store, rid)
    return {"round": n, "run_id": rid}
