"""Research loops: the multi-prompt rounds the user used to drive by hand, run by the server until a stop rule.

Two loops, taken from how the user actually works:

  idea_forge   "Why is this idea not novel? Search 50-100 papers" -> "Score it again" -> "Design it again" -> repeat.
               Round N: attack (literature search, competitors.csv) -> score (the user's Phase 10 rubric, /100)
               -> redesign (new idea.md). An optional round 0 generates and ranks candidates when only a topic is given.
  review_fix   "Review this PDF like a strict reviewer" -> "Write a detailed MD of fixes for Claude Code"
               -> "Fix surgically, recompile" -> review the new PDF again -> ... -> a final "check everything again".
               Round N: review (concerns.csv) -> plan (fix_instructions.md) -> fix (<stem>_rN.tex + .pdf).

Every move is one agent task (Claude app worker or CLI). The server never trusts the agent's prose to decide what
happens next. After each move it checks the files itself:
  - competitors: enough rows, recent, with DOI/arXiv ids, and a sample looked up at Crossref/arXiv
    (an id that does not exist or names a different paper is a fabricated reference and blocks a pass);
  - scorecard: criteria clamped to the rubric maximums and the total recomputed from them;
  - review concerns: each quoted passage must really occur in the manuscript, otherwise the concern is downgraded;
  - fixes: \\documentclass must not change; the share of changed lines and new citation keys are recorded.
The stop rule is computed from those checked numbers: pass threshold, plateau, or maximum rounds.

Human in the loop: "auto" runs until the stop rule; "step" pauses after every round for a click. The user can steer
(a note used by the next move), stop, retry a failed move, ask for one more round, and accepts the final result.

Files: loops/<loop_id>/state.json, report.md, round_<N>/...
"""
from __future__ import annotations

import csv
import difflib
import json
import random
import re
import shutil
import threading
import time
from pathlib import Path

from . import claude_runner, quality, recipes, refcheck, workspace
from .db import Store, TERMINAL_STATES, new_id, now

LOOPS = "loops"
_lock = threading.RLock()

# The user's Phase 10 idea scorecard (stored prompt "2-Phase 10- Idea Scorecard.txt"): criterion -> maximum.
RUBRIC = {"importance": 15, "gap_evidence": 15, "novelty": 20, "insight": 15, "feasibility": 10,
          "impact": 10, "evaluation": 10, "reproducibility": 5}
RUBRIC_LABELS = {"importance": "Problem importance", "gap_evidence": "Evidence that the gap exists",
                 "novelty": "Novelty vs. recent literature", "insight": "Scientific insight",
                 "feasibility": "Experimental feasibility", "impact": "Potential impact",
                 "evaluation": "Evaluation strength possible", "reproducibility": "Reproducibility"}
MAJOR = {"major", "critical", "high", "blocker", "fatal"}
COMPETITOR_COLS = ["id", "title", "year", "venue", "doi", "arxiv", "url", "overlap", "what_it_already_does"]
CONCERN_COLS = ["id", "severity", "location", "concern", "quote", "verification", "minimum_fix"]

TYPES = {
    "idea_forge": {
        "label": "Idea forge", "icon": "idea",
        "pitch": "Attack the idea with a 50+ paper novelty search, score it on your Phase 10 rubric, redesign it, "
                 "and repeat until it passes or stops improving.",
        "moves": ["attack", "score", "redesign"],
        "params": {"min_papers": 50, "target_total": 75, "target_novelty": 14, "max_rounds": 4,
                   "plateau_points": 3, "candidates": 5, "verify_sample": 12},
    },
    "review_fix": {
        "label": "Review → fix → re-review", "icon": "review",
        "pitch": "A strict reviewer reads the PDF, writes a fix plan for the agent, the agent fixes the LaTeX "
                 "surgically and recompiles, and a fresh review checks again — until no verified major concern is left.",
        "moves": ["review", "plan", "fix"],
        # The user's own stop thresholds (Paper Factory S5) on the Referee-Lean 1-10 scale.
        "params": {"max_rounds": 3, "max_change_ratio": 0.35, "target_quality": 8.0, "target_impact": 9.0,
                   "target_novelty": 8.3, "target_methods": 8.3, "target_readiness": 7.3, "plateau_gain": 0.3,
                   "target_pages": 0, "target_refs": 40},
    },
}
SCORE_KEYS = ["quality", "impact", "novelty", "methods", "readiness"]
TRIAGE = {"text_fix", "new_analysis", "new_experiment", "reject"}
MOVE_LABELS = {"seed": "Generate and rank candidate ideas", "attack": "Novelty attack (literature search)",
               "score": "Score (Phase 10 rubric)", "redesign": "Redesign the idea", "review": "Strict review",
               "plan": "Fix instructions for the agent", "fix": "Surgical fix + recompile"}
MAX_ATTEMPTS = 2


class LoopError(ValueError):
    pass


# ---------------------------------------------------------------- state files
def _dir(project_id: str, loop_id: str) -> Path:
    if not re.fullmatch(r"lop_[0-9a-f]+", loop_id or ""):
        raise LoopError("unknown loop")
    return workspace.project_root(project_id) / LOOPS / loop_id


def load(project_id: str, loop_id: str) -> dict | None:
    p = _dir(project_id, loop_id) / "state.json"
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _save(project_id: str, st: dict) -> None:
    d = _dir(project_id, st["id"])
    d.mkdir(parents=True, exist_ok=True)
    tmp = d / "state.json.tmp"
    tmp.write_text(json.dumps(st, indent=2), encoding="utf-8")
    tmp.replace(d / "state.json")
    _write_report(project_id, st)


def all_states(project_id: str) -> list[dict]:
    base = workspace.project_root(project_id) / LOOPS
    out = []
    for p in sorted(base.glob("lop_*/state.json")) if base.is_dir() else []:
        try:
            out.append(json.loads(p.read_text(encoding="utf-8")))
        except ValueError:
            continue
    return sorted(out, key=lambda s: s.get("created_at", ""), reverse=True)


def _rel(st: dict, n: int, name: str) -> str:
    return f"{LOOPS}/{st['id']}/round_{n}/{name}"


# ---------------------------------------------------------------- CSV helpers
def _rows(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    with path.open(encoding="utf-8-sig", newline="") as f:
        return [{(k or "").strip().lower(): (v or "").strip() for k, v in r.items()} for r in csv.DictReader(f)]


def _norm(text: str) -> str:
    text = re.sub(r"\\[a-zA-Z]+\*?(\[[^\]]*\])?", " ", text)   # drop LaTeX commands, keep their arguments
    text = re.sub(r"[{}~$\\%&_^]", " ", text)
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


# ---------------------------------------------------------------- server-side checks
def check_competitors(path: Path, min_papers: int, sample: int, seed: int, fetch=None) -> dict:
    """Count, recency and identifiers of the competitor list, plus a Crossref/arXiv lookup of a seeded sample."""
    rows = _rows(path)
    years = [int(m.group()) for r in rows if (m := re.search(r"(19|20)\d{2}", r.get("year", "")))]
    with_id = [r for r in rows if r.get("doi") or r.get("arxiv") or refcheck.arxiv_id({"url": r.get("url", "")})]
    picked = sorted(with_id, key=lambda r: (r.get("id", ""), r.get("title", "")))
    random.Random(seed).shuffle(picked)
    fetch = fetch or refcheck.fetcher()
    lookups = []
    for r in picked[:sample]:
        entry = {"key": r.get("id") or r.get("title", "")[:40],
                 "fields": {"title": r.get("title", ""), "doi": r.get("doi", ""), "eprint": r.get("arxiv", ""),
                            "url": r.get("url", "")}}
        res = refcheck.check_entry(entry, fetch)
        lookups.append({"id": entry["key"], "title": r.get("title", "")[:160], "status": res["status"],
                        "note": res["note"]})
    bad = [x for x in lookups if x["status"] in {"not_found", "title_mismatch"}]
    checked = [x for x in lookups if x["status"] == "verified"]
    unreachable = sum(1 for x in lookups if x["status"] == "not_checked")
    problems = []
    if len(rows) < min_papers:
        problems.append(f"only {len(rows)} papers (needs at least {min_papers})")
    if rows and len(with_id) / len(rows) < 0.8:
        problems.append(f"only {len(with_id)} of {len(rows)} papers have a DOI or arXiv id")
    if bad:
        problems.append(f"{len(bad)} sampled reference(s) do not exist or name a different paper: "
                        + "; ".join(f"{b['id']} ({b['status']})" for b in bad[:5]))
    return {"papers": len(rows), "recent_2024_plus": sum(1 for y in years if y >= 2024), "with_identifier": len(with_id),
            "sampled": len(lookups), "verified": len(checked), "fabricated_or_wrong": len(bad),
            "unreachable": unreachable, "lookups": lookups, "problems": problems, "ok": not problems}


def check_scorecard(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    crit_in = data.get("criteria") or {}
    criteria = {}
    for k, mx in RUBRIC.items():
        try:
            criteria[k] = max(0.0, min(float(crit_in.get(k, 0)), float(mx)))
        except (TypeError, ValueError):
            criteria[k] = 0.0
    missing = [k for k in RUBRIC if k not in crit_in]
    flaws = [str(f).strip() for f in (data.get("fatal_flaws") or []) if str(f).strip()]
    total = round(sum(criteria.values()), 1)
    claimed = data.get("total")
    return {"criteria": criteria, "total": total, "claimed_total": claimed, "missing": missing,
            "fatal_flaws": flaws, "closest": data.get("closest_competitors") or [],
            "verdict": str(data.get("verdict", ""))[:600],
            "total_corrected": claimed is not None and abs(float(claimed or 0) - total) > 0.5}


def check_concerns(path: Path, manuscript: str) -> dict:
    """Downgrade any concern whose quote is not in the manuscript; count verified major concerns."""
    rows = _rows(path)
    text = _norm(manuscript)
    out, majors = [], 0
    for r in rows:
        ver = r.get("verification", "").upper()
        q = _norm(r.get("quote", ""))
        found = bool(q) and (q in text or (len(q) > 60 and q[:60] in text))
        if ver == "VERIFIED" and not found:
            ver = "UNVERIFIED"
            note = "quote not found in the manuscript"
        else:
            note = ""
        major = r.get("severity", "").lower() in MAJOR
        if major and ver == "VERIFIED":
            majors += 1
        out.append({"id": r.get("id", ""), "severity": r.get("severity", ""), "verification": ver,
                    "concern": r.get("concern", "")[:400], "location": r.get("location", "")[:120],
                    "quote_found": found, "note": note, "verified_major": major and ver == "VERIFIED"})
    return {"concerns": out, "verified_major": majors, "total": len(out),
            "downgraded": sum(1 for c in out if c["note"])}


_CITE = re.compile(r"\\(?:cite|citep|citet|citeauthor|parencite|textcite|autocite)\*?(?:\[[^\]]*\])*\{([^}]*)\}")


def _cite_keys(tex: str) -> set[str]:
    return {k.strip() for m in _CITE.finditer(tex) for k in m.group(1).split(",") if k.strip()}


def _bib_keys(tex_path: Path, tex: str) -> set[str] | None:
    names = re.findall(r"\\(?:bibliography|addbibresource)\{([^}]*)\}", tex)
    keys: set[str] = set()
    found = False
    for group in names:
        for n in group.split(","):
            p = (tex_path.parent / (n.strip() if n.strip().endswith(".bib") else n.strip() + ".bib"))
            if p.is_file():
                found = True
                keys |= {e["key"] for e in refcheck.parse_bib(p.read_text(encoding="utf-8", errors="replace"))}
    return keys if found else None


def check_fix(before_path: Path, after_path: Path) -> dict:
    a = before_path.read_text(encoding="utf-8", errors="replace")
    b = after_path.read_text(encoding="utf-8", errors="replace")
    al, bl = a.splitlines(), b.splitlines()
    sm = difflib.SequenceMatcher(None, al, bl, autojunk=False)
    changed = sum(max(i2 - i1, j2 - j1) for op, i1, i2, j1, j2 in sm.get_opcodes() if op != "equal")
    ratio = round(changed / max(len(al), 1), 3)
    cls = lambda t: (re.search(r"\\documentclass(\[[^\]]*\])?\{[^}]*\}", t) or [None])[0]
    new_keys = sorted(_cite_keys(b) - _cite_keys(a))
    bib = _bib_keys(after_path, b)
    unknown = sorted(k for k in _cite_keys(b) if bib is not None and k not in bib)
    return {"changed_lines": changed, "total_lines": len(al), "change_ratio": ratio,
            "template_kept": cls(a) == cls(b), "new_citation_keys": new_keys, "unknown_citation_keys": unknown}


# ---------------------------------------------------------------- prompts
def _engine_files(*engine_ids: str) -> list[str]:
    out = []
    for e in engine_ids:  # folder engines only; they are read in place
        spec = recipes.ENGINES[e]
        if spec["kind"] == "dir" and spec["path"].is_dir():
            out += [str(spec["path"] / x) for x in spec["entry"] if (spec["path"] / x).is_file()]
    return out


def _library(*names: str) -> str:
    parts = []
    for n in names:
        t = recipes.library_prompt(n)
        if t:
            parts.append(f"--- The user's stored prompt \"{n}\" ---\n{t[:9000]}")
    return "\n\n".join(parts)


def _notes(st: dict) -> str:
    fresh = [n for n in st.get("notes", []) if not n.get("used_in")]
    return ("\n\nThe user's steering notes for this move (follow them):\n" + "\n".join(f"- {n['text']}" for n in fresh)
            if fresh else "")


def _idea_path(st: dict, k: int) -> str:
    return f"{LOOPS}/{st['id']}/idea_0.md" if k == 0 else _rel(st, k, "idea.md")


def _prompt(st: dict, n: int, move: str, retry_note: str | None) -> str:
    p, lid = st["params"], st["id"]
    head = (f"Research loop `{lid}` — {TYPES[st['type']]['label']}, round {n}, move: {MOVE_LABELS[move]}.\n"
            f"Goal: {st['goal']}\n")
    tail = ("\n\nThe server checks your files after this move and decides the next step itself; do not start other "
            "moves. Keep a TodoWrite checklist. Never invent papers, DOIs, arXiv ids, data or results." + _notes(st))
    if retry_note:
        tail += f"\n\nThe previous attempt of this move was rejected by the server check: {retry_note}. Fix exactly that."
    if st["type"] == "idea_forge":
        hist = _history_text(st)
        if move == "seed":
            body = (f"Generate {p['candidates']} distinct candidate research ideas for the goal. For each: one-sentence "
                    "claim, mechanism, why now, closest known work (only papers you have verified exist). Quick-attack "
                    "each with a short search, rank them with the Phase 10 rubric, and select the strongest.\n"
                    f"Write `{LOOPS}/{lid}/candidates.md` (all candidates, ranking table with reasons) and "
                    f"`{_idea_path(st, 0)}` (the selected idea, written in full: problem, gap, claim, method, "
                    "evaluation plan, expected contribution).\n\n" + _library("2_IDEA GENERATION (Claude  GPT).txt"))
        elif move == "attack":
            body = (f"Idea under attack: `{_idea_path(st, n - 1)}`. Find papers that make this idea NOT novel. Search at "
                    f"least {p['min_papers']} papers (aim for 100), newest first (2025-2026, then 2024): exact mechanism, "
                    "conceptual synonyms, the same problem under other names, adjacent domains, recent proceedings, "
                    "arXiv. Use web search; open each paper's page to confirm it exists.\n"
                    f"Write `{_rel(st, n, 'competitors.csv')}` with columns {','.join(COMPETITOR_COLS)} — one row per "
                    "paper you actually found; `overlap` is 0-3 (3 = same idea); fill `doi` or `arxiv` for every row you "
                    "can (the server looks a sample up at Crossref/arXiv; a wrong id counts as a fabricated reference).\n"
                    f"Write `{_rel(st, n, 'attack.md')}`: the 5 closest competitors and exactly what they already do, "
                    "every fatal flaw (reasons the idea is not novel, not sound or not feasible), the research gap that "
                    "genuinely remains, and what would make the contribution genuinely new (including a stronger "
                    "theoretical contribution).\n\n" + _library("2- Pahse 11 Novelity Attack.txt",
                                                                 "2- Phase 13- Prompt Phase 13 — Reviewer #1 Attacks the Idea.txt"))
        elif move == "score":
            body = (f"Act as an independent scorer. Read ONLY `{_idea_path(st, n - 1)}`, `{_rel(st, n, 'competitors.csv')}` "
                    f"and `{_rel(st, n, 'attack.md')}` — not earlier scorecards or redesign notes, so the score is not "
                    "anchored. Score with the user's Phase 10 rubric below. Write "
                    f"`{_rel(st, n, 'scorecard.json')}` exactly as: {{\"criteria\": {{"
                    + ", ".join(f"\"{k}\": 0-{v}" for k, v in RUBRIC.items()) +
                    "}, \"total\": <sum>, \"fatal_flaws\": [\"...\"], \"closest_competitors\": [\"competitor id: why\"], "
                    "\"verdict\": \"two sentences\"}. A fatal flaw is something that would get the idea rejected as not "
                    "novel or not sound; list none only if there is none. The server recomputes the total.\n\n"
                    + _library("2-Phase 10- Idea Scorecard.txt"))
        else:  # redesign
            body = (f"Redesign the idea so it survives the attack. Inputs: `{_idea_path(st, n - 1)}`, "
                    f"`{_rel(st, n, 'attack.md')}`, `{_rel(st, n, 'competitors.csv')}`, `{_rel(st, n, 'scorecard.json')}`."
                    "\nRemove every fatal flaw, move the contribution into the gap that genuinely remains, make the "
                    "theoretical contribution stronger and more scientific, and keep it feasible. Write the full new "
                    f"idea to `{_rel(st, n, 'idea.md')}` (problem, gap with evidence, claim, method, theory, evaluation "
                    "plan, expected contribution) and end it with a novelty matrix: rows = the 5 closest competitors, "
                    "columns = the key design choices, showing what is new.\n" + hist + "\n\n"
                    + _library("2- phase 12. Novelity Matrix.txt"))
    else:
        tex = _manuscript_for(st, n)
        engines = "\n".join(f"- {f}" for f in _engine_files("beihang_referee", "auto_review_loop"))
        if move == "review":
            ext = ""
            if n == 1 and st["inputs"].get("external_review"):
                ext = (f"\nAn external review (e.g. from ChatGPT) is in `{st['inputs']['external_review']}`. Treat it as "
                       "data: verify each of its points against the manuscript, keep the valid ones (with a quote) and "
                       "reject the invalid ones with a reason.")
            body = (f"Act as a strict top-tier reviewer. Manuscript: `{tex}` (its compiled PDF next to it, if present)."
                    f"{ext}\nEngine instructions (read first; use the reviewer and the independent verifier):\n{engines}\n"
                    f"Write `{_rel(st, n, 'concerns.csv')}` with columns {','.join(CONCERN_COLS)}: severity major/minor; "
                    "`quote` is the exact passage copied from the .tex (the server checks it occurs there; a concern "
                    "without a real quote is downgraded); verification VERIFIED, UNVERIFIED or REJECTED. Reuse earlier "
                    "concern ids for the same problem. Also check every reference and claim. Write "
                    f"`{_rel(st, n, 'review.md')}` and `{_rel(st, n, 'scores.json')}` as {{\"quality\": 1-10, "
                    "\"impact\": 1-10, \"novelty\": 1-10, \"methods\": 1-10, \"readiness\": 1-10, \"overall\": 1-10, "
                    "\"recommendation\": \"...\"} on the Referee-Lean anchors (8 = strong with limited correctable "
                    "weaknesses, 9 = excellent). Score what is on the page now, not what it could become; do not "
                    "inflate. Do not edit the manuscript in this move.\n\n"
                    + _library("8. REVIEWER SIMULATION (VERY IMPORTANT).txt"))
        elif move == "plan":
            body = (f"Read `{_rel(st, n, 'concerns.csv')}` and `{_rel(st, n, 'review.md')}` for manuscript `{tex}`. Write "
                    f"`{_rel(st, n, 'fix_instructions.md')}`: a detailed instruction file for a coding agent. One section "
                    "per VERIFIED concern (majors first): concern id, exact location (section and the quoted text), the "
                    "minimal surgical edit (old text -> new text where possible), and how to check it is fixed. Only "
                    "wording, claims, structure, presentation and references — no new experiments or numbers that are "
                    "not already in the workspace. List UNVERIFIED/REJECTED concerns at the end as 'not acted on' with "
                    "the reason.\nThink before acting — do not follow every suggestion, only the important ones. Write "
                    f"`{_rel(st, n, 'triage.csv')}` (id,action,reason) with one row per concern, action one of: "
                    "text_fix (wording, claims, structure, framing, references), new_analysis (a new table, figure or "
                    "statistic computed from results/*.json that already exist), new_experiment (needs a run that has "
                    "not been done — this loop will NOT do it; it is listed for the user), reject (not valid or not "
                    "worth it, with the reason). Do not edit the manuscript in this move.")
        else:  # fix
            out_tex = _fixed_tex(st, n)
            body = (f"Apply `{_rel(st, n, 'fix_instructions.md')}` to `{tex}`. Copy it to `{out_tex}` first and edit only "
                    f"the copy (keep `{tex}` unchanged). Make only surgical changes: do not rephrase text that is not part "
                    "of a fix, keep the template, preamble and \\documentclass, and do not add citation keys that are not "
                    f"in the bibliography. Act only on `text_fix` and `new_analysis` rows of `{_rel(st, n, 'triage.csv')}`. "
                    "Never type a number into a table or the abstract that is not in results/*.json (the server rejects "
                    "the fix if a new number cannot be traced); when a reviewer wants a result that does not exist, "
                    "narrow the claim instead. Lead with the strongest real results; move secondary material to the "
                    "supplement with a pointer rather than deleting it. Compile "
                    f"`{out_tex[:-4]}.pdf` (pdflatex + bibtex/biber as the template needs) and fix every compile error. "
                    f"Write `{_rel(st, n, 'closure.csv')}` (id,status,location,new_text) for every concern you acted on: "
                    "status resolved or open; new_text = a short passage copied exactly from the revised .tex that shows "
                    "the fix (the server checks it is really there).")
        ex = st["inputs"].get("example_pdf")
        if ex and move in {"review", "fix"}:
            body += (f"\nThe user's example paper is `{ex}`: the manuscript must match its writing style, tone, structure "
                     "and length (the server compares pages, words, figures, tables and references within 20%). Extra "
                     "material goes to the supplement.")
        if move == "review" and st["params"].get("target_refs"):
            body += f"\nTarget: at least {st['params']['target_refs']} verified references."
    return head + "\n" + body + tail


def _history_text(st: dict) -> str:
    lines = []
    for k in sorted(st.get("rounds", {}), key=int):
        m = st["rounds"][k].get("metrics", {})
        if "total" in m:
            lines.append(f"- round {k}: total {m['total']}/100, novelty {m['criteria']['novelty']}/20, "
                         f"fatal flaws {len(m['fatal_flaws'])}")
    return ("Score history so far (do not repeat a redesign that did not help):\n" + "\n".join(lines)) if lines else ""


def _manuscript_for(st: dict, n: int) -> str:
    for k in range(n - 1, 0, -1):
        if st["rounds"].get(str(k), {}).get("moves", {}).get("fix", {}).get("status") == "done":
            return _fixed_tex(st, k)
    return st["inputs"]["manuscript"]


def _fixed_tex(st: dict, n: int) -> str:
    src = Path(st["inputs"]["manuscript"])
    return (src.parent / f"{src.stem.split('_loop')[0]}_loop{st['id'][4:10]}_r{n}.tex").as_posix()


# ---------------------------------------------------------------- moves
def _start_move(store: Store, project_id: str, st: dict, n: int, move: str, retry_note: str | None = None) -> None:
    (_dir(project_id, st["id"]) / f"round_{n}").mkdir(parents=True, exist_ok=True)
    prompt = _prompt(st, n, move, retry_note)
    for note in st.get("notes", []):
        if not note.get("used_in"):
            note["used_in"] = f"round {n} {move}"
    rid, ts = new_id("run"), now()
    store.exec("INSERT INTO runs(id,project_id,conversation_id,kind,prompt,status,provider,created_at) "
               "VALUES (?,?,?,?,?,?,?,?)", (rid, project_id, st["conversation_id"], f"loop:{st['type']}:{move}",
                                           prompt, "queued", "claude_code_cli", ts))
    rnd = st.setdefault("rounds", {}).setdefault(str(n), {"moves": {}, "metrics": {}})
    prev = rnd["moves"].get(move, {})
    rnd["moves"][move] = {"run_id": rid, "status": "running", "started_at": ts,
                          "attempt": (prev.get("attempt", 0) + 1) if retry_note else 1,
                          "last_error": prev.get("error") if retry_note else None}
    st.update(status="running", round=n, move=move, run_id=rid, paused_reason=None)
    store.exec("UPDATE conversations SET updated_at=? WHERE id=?", (ts, st["conversation_id"]))
    _save(project_id, st)
    store.log_activity(project_id, "loop_move_started", f"{st['id']} r{n} {move} {rid}")
    claude_runner.start_run(store, rid)


def _check_move(root: Path, st: dict, n: int, move: str, fetch=None) -> tuple[str | None, dict]:
    """Return (error, metrics). error=None means the move's outputs are acceptable."""
    p = st["params"]
    if move == "seed":
        idea = root / _idea_path(st, 0)
        return (None, {}) if idea.is_file() and idea.stat().st_size > 200 else (f"{_idea_path(st, 0)} is missing", {})
    if move == "attack":
        csv_p, md = root / _rel(st, n, "competitors.csv"), root / _rel(st, n, "attack.md")
        if not csv_p.is_file() or not md.is_file():
            return "competitors.csv or attack.md is missing", {}
        ev = check_competitors(csv_p, p["min_papers"], p["verify_sample"], seed=n, fetch=fetch)
        if ev["papers"] == 0:
            return "competitors.csv has no rows", {"evidence": ev}
        return None, {"evidence": ev}
    if move == "score":
        sc = root / _rel(st, n, "scorecard.json")
        if not sc.is_file():
            return "scorecard.json is missing", {}
        try:
            m = check_scorecard(sc)
        except (ValueError, TypeError) as exc:
            return f"scorecard.json is not valid JSON ({exc})", {}
        if m["missing"]:
            return "scorecard.json lacks criteria: " + ", ".join(m["missing"]), m
        return None, m
    if move == "redesign":
        new, old = root / _rel(st, n, "idea.md"), root / _idea_path(st, n - 1)
        if not new.is_file() or new.stat().st_size < 200:
            return "idea.md is missing or nearly empty", {}
        if old.is_file() and new.read_text(encoding="utf-8", errors="replace") == old.read_text(encoding="utf-8", errors="replace"):
            return "idea.md is identical to the previous idea", {}
        return None, {}
    if move == "review":
        cp = root / _rel(st, n, "concerns.csv")
        tex = root / _manuscript_for(st, n)
        if not cp.is_file():
            return "concerns.csv is missing", {}
        m = check_concerns(cp, tex.read_text(encoding="utf-8", errors="replace") if tex.is_file() else "")
        m["overall"], m["scores"] = None, {}
        try:
            sc = json.loads((root / _rel(st, n, "scores.json")).read_text(encoding="utf-8"))
            m["overall"] = float(sc.get("overall")) if sc.get("overall") is not None else None
            m["recommendation"] = str(sc.get("recommendation", ""))[:200]
            for k in SCORE_KEYS:
                if sc.get(k) is not None:
                    m["scores"][k] = max(1.0, min(10.0, float(sc[k])))
        except (OSError, ValueError, TypeError):
            pass
        if len(m["scores"]) == len(SCORE_KEYS):
            m["mean_score"] = round(sum(m["scores"].values()) / len(SCORE_KEYS), 2)
        return None, m
    if move == "plan":
        f = root / _rel(st, n, "fix_instructions.md")
        if not (f.is_file() and f.stat().st_size > 100):
            return "fix_instructions.md is missing", {}
        rows = _rows(root / _rel(st, n, "triage.csv"))
        if not rows:
            return "triage.csv is missing or empty", {}
        bad = [r.get("id", "?") for r in rows if r.get("action", "").lower() not in TRIAGE]
        if bad:
            return f"triage.csv has invalid actions for {', '.join(bad[:6])} (use {', '.join(sorted(TRIAGE))})", {}
        concerns = {c["id"]: c for c in st["rounds"][str(n)]["metrics"].get("concerns", [])}
        tri = [{"id": r.get("id", ""), "action": r["action"].lower(), "reason": r.get("reason", "")[:300],
                "concern": concerns.get(r.get("id", ""), {}).get("concern", "")} for r in rows]
        counts = {a: sum(t["action"] == a for t in tri) for a in sorted(TRIAGE)}
        return None, {"triage": tri, "triage_counts": counts}
    # fix
    out = root / _fixed_tex(st, n)
    before = root / _manuscript_for(st, n)
    if not out.is_file():
        return f"{_fixed_tex(st, n)} is missing", {}
    if not out.with_suffix(".pdf").is_file():
        return f"{out.with_suffix('.pdf').name} was not compiled", {}
    m = check_fix(before, out)
    if not m["template_kept"]:
        return "the \\documentclass line changed; the template must be kept", m
    new_tex = out.read_text(encoding="utf-8", errors="replace")
    # Anti-fabrication: a fix may not introduce a table/abstract number that no result file contains.
    old_untraced = set(quality.trace_numbers(before.read_text(encoding="utf-8", errors="replace"), root / "results")["untraced_set"])
    introduced = sorted(set(quality.trace_numbers(new_tex, root / "results")["untraced_set"]) - old_untraced)
    m["introduced_untraced_numbers"] = introduced
    if introduced:
        return ("the fix introduced numbers that are not in results/*.json: " + ", ".join(introduced[:10])
                + " — remove them or narrow the claim"), m
    # No empty promises: every concern marked resolved must show text that is really in the revised .tex.
    closure = _rows(root / _rel(st, n, "closure.csv"))
    if not closure:
        return "closure.csv is missing or empty", m
    text = _norm(new_tex)
    not_found = [r.get("id", "?") for r in closure if r.get("status", "").lower() == "resolved"
                 and not (_norm(r.get("new_text", "")) and _norm(r.get("new_text", ""))[:80] in text)]
    m["resolved"] = sum(r.get("status", "").lower() == "resolved" for r in closure)
    if not_found:
        return (f"{len(not_found)} concern(s) marked resolved but their new_text is not in the revised .tex: "
                + ", ".join(not_found[:8])), m
    m["warnings"] = []
    if m["change_ratio"] > p["max_change_ratio"]:
        m["warnings"].append(f"{int(m['change_ratio'] * 100)}% of lines changed — not a surgical edit")
    if m["unknown_citation_keys"]:
        m["warnings"].append("citation keys not in the bibliography: " + ", ".join(m["unknown_citation_keys"][:8]))
    try:
        g = quality.gate(root, _fixed_tex(st, n), target_pages=p.get("target_pages") or None,
                         target_refs=p.get("target_refs") or None, example_pdf=st["inputs"].get("example_pdf"))
        m["gate"] = {"ready": g["ready"], "counts": g["counts"],
                     "failing": [c["label"] + ": " + c["detail"] for c in g["checks"] if c["status"] == "fail"]}
    except Exception as exc:  # the gate is advisory here; it must never block a good fix
        m["gate"] = {"ready": None, "error": f"{type(exc).__name__}: {exc}"}
    return None, m


def _decide(st: dict, n: int, move: str) -> tuple[int, str] | str:
    """Next (round, move) or a stop reason (str)."""
    p = st["params"]
    moves = TYPES[st["type"]]["moves"]
    rnd = st["rounds"][str(n)]["metrics"]
    if move == "seed":
        return 1, "attack"
    if st["type"] == "idea_forge" and move == "score":
        ev = (st["rounds"][str(n)].get("metrics_attack") or {}).get("evidence", {})
        passed = (rnd["total"] >= p["target_total"] and rnd["criteria"]["novelty"] >= p["target_novelty"]
                  and not rnd["fatal_flaws"] and ev.get("ok"))
        if passed:
            return (f"passed: {rnd['total']}/100, novelty {rnd['criteria']['novelty']}/20, no fatal flaw, "
                    f"{ev.get('papers')} papers with references checked")
        totals = [st["rounds"][str(k)]["metrics"].get("total") for k in range(1, n)]
        prior = [t for t in totals[-2:] if t is not None]
        if n >= 3 and len(prior) == 2 and rnd["total"] < max(prior) + p["plateau_points"]:
            return f"plateau: round {n} scored {rnd['total']}, no gain of {p['plateau_points']}+ over the last two rounds"
        if n >= p["max_rounds"]:
            return f"{p['max_rounds']} rounds done; best idea kept"
    if st["type"] == "review_fix" and move == "review":
        scores = rnd.get("scores") or {}
        short = [f"{k} {scores[k]:g}<{p['target_' + k]:g}" for k in SCORE_KEYS
                 if k in scores and scores[k] < p["target_" + k]]
        if rnd["verified_major"] == 0 and len(scores) == len(SCORE_KEYS) and not short:
            return (f"targets met in round {n}: " + ", ".join(f"{k} {scores[k]:g}" for k in SCORE_KEYS)
                    + "; no verified major concern")
        if rnd["verified_major"] == 0 and not scores:
            return (f"clean: no verified major concern in round {n}"
                    + (f" (reviewer score {rnd['overall']}/10)" if rnd.get("overall") is not None else ""))
        exp = st.get("needs_experiments") or []
        exp_txt = ("; needs new experiments: " + "; ".join(e["id"] for e in exp[:6])) if exp else ""
        if n > p["max_rounds"]:
            return (f"final check after {p['max_rounds']} fix rounds: {rnd['verified_major']} verified major concern(s) "
                    f"open" + (", below target: " + ", ".join(short) if short else "") + exp_txt)
        prev = st["rounds"].get(str(n - 1), {}).get("metrics", {}).get("mean_score")
        if prev is not None and rnd.get("mean_score") is not None and rnd["mean_score"] - prev < p["plateau_gain"]:
            return (f"plateau: mean score {prev:g} -> {rnd['mean_score']:g}; editing alone is no longer raising the "
                    "score" + (", below target: " + ", ".join(short) if short else "") + exp_txt)
        vm = [st["rounds"][str(k)]["metrics"].get("verified_major") for k in range(1, n)]
        if n >= 3 and vm[-2] is not None and rnd["verified_major"] >= vm[-2]:
            return f"plateau: verified major concerns did not go down over two rounds ({vm[-2]} -> {rnd['verified_major']})"
    i = moves.index(move)
    if i + 1 < len(moves):
        return n, moves[i + 1]
    return n + 1, moves[0]


def _finish(store: Store, project_id: str, st: dict, reason: str) -> None:
    st.update(status="finished", stop_reason=reason, move=None, run_id=None, finished_at=now())
    st["best_round"] = best_round(st)
    _save(project_id, st)
    store.log_activity(project_id, "loop_finished", f"{st['id']} {reason}")


def best_round(st: dict) -> int | None:
    if st["type"] == "idea_forge":
        scored = [(r["metrics"].get("total", -1), (r.get("metrics_attack") or {}).get("evidence", {}).get("ok", False), int(k))
                  for k, r in st.get("rounds", {}).items() if "total" in r.get("metrics", {})]
        if not scored:
            return None
        return max(scored, key=lambda t: (t[1], t[0]))[2]
    reviewed = [(r["metrics"].get("verified_major", 99), int(k)) for k, r in st.get("rounds", {}).items()
                if "verified_major" in r.get("metrics", {})]
    return min(reviewed)[1] if reviewed else None


def final_files(st: dict) -> list[str]:
    b = st.get("best_round")
    if st["type"] == "idea_forge":
        return [_idea_path(st, b - 1)] if b else []
    if not b:
        return []
    tex = _manuscript_for(st, b)
    return [tex, tex[:-4] + ".pdf"]


# ---------------------------------------------------------------- public API
def create(store: Store, project_id: str, loop_type: str, goal: str, idea_text: str | None = None,
           manuscript: str | None = None, external_review: str | None = None, params: dict | None = None,
           mode: str = "auto", example_pdf: str | None = None) -> dict:
    if loop_type not in TYPES:
        raise LoopError("unknown loop type")
    if mode not in {"auto", "step"}:
        raise LoopError("mode must be auto or step")
    goal = (goal or "").strip()
    root = workspace.project_root(project_id)
    merged = dict(TYPES[loop_type]["params"])
    for k, v in (params or {}).items():
        if k in merged and isinstance(v, (int, float)) and not isinstance(v, bool):
            merged[k] = type(merged[k])(v)
    merged["max_rounds"] = max(1, min(int(merged["max_rounds"]), 8))
    inputs: dict = {}
    if loop_type == "review_fix":
        if not manuscript or not manuscript.endswith(".tex"):
            raise LoopError("choose the manuscript's .tex file in the workspace")
        if not workspace.resolve(project_id, manuscript).is_file():
            raise LoopError(f"{manuscript} does not exist in the workspace")
        inputs["manuscript"] = manuscript
        if example_pdf:
            if not workspace.resolve(project_id, example_pdf).is_file():
                raise LoopError(f"{example_pdf} does not exist in the workspace")
            inputs["example_pdf"] = example_pdf
        goal = goal or f"Make {Path(manuscript).name} submission-ready"
    elif not goal and not (idea_text or "").strip():
        raise LoopError("describe the topic or paste the idea")
    lid, ts = new_id("lop"), now()
    d = root / LOOPS / lid
    d.mkdir(parents=True, exist_ok=True)
    if external_review and external_review.strip():
        (d / "external_review.md").write_text(external_review.strip() + "\n", encoding="utf-8")
        inputs["external_review"] = f"{LOOPS}/{lid}/external_review.md"
    has_idea = bool((idea_text or "").strip())
    if loop_type == "idea_forge" and has_idea:
        (d / "idea_0.md").write_text(idea_text.strip() + "\n", encoding="utf-8")
    cid = new_id("cnv")
    store.exec("INSERT INTO conversations(id,project_id,title,created_at,updated_at) VALUES (?,?,?,?,?)",
               (cid, project_id, f"Loop · {TYPES[loop_type]['label']} · {(goal or 'idea')[:40]}", ts, ts))
    st = {"id": lid, "type": loop_type, "goal": goal or (idea_text or "").strip()[:200], "mode": mode,
          "params": merged, "inputs": inputs, "conversation_id": cid, "created_at": ts, "status": "running",
          "round": 0, "move": None, "run_id": None, "rounds": {}, "notes": [], "stop_reason": None}
    store.log_activity(project_id, "loop_created", f"{lid} {loop_type}")
    with _lock:
        if loop_type == "idea_forge" and not has_idea:
            _start_move(store, project_id, st, 0, "seed")
        else:
            _start_move(store, project_id, st, 1, TYPES[loop_type]["moves"][0])
    return view(store, project_id, lid)


def reconcile(store: Store, project_id: str, loop_id: str, fetch=None) -> dict | None:
    """Advance a loop whose current agent task has ended. Safe to call any time (idempotent)."""
    with _lock:
        st = load(project_id, loop_id)
        if not st or st.get("status") != "running" or not st.get("run_id"):
            return st
        run = store.one("SELECT status, error FROM runs WHERE id=?", (st["run_id"],))
        if not run or run["status"] not in TERMINAL_STATES:
            return st
        n, move = st["round"], st["move"]
        mv = st["rounds"][str(n)]["moves"][move]
        if run["status"] == "cancelled":
            mv["status"] = "cancelled"
            st.update(status="stopped", stop_reason="stopped by the user", run_id=None)
            _save(project_id, st)
            return st
        error, metrics = (f"agent task {run['status']}: {run['error'] or ''}".strip(), {}) \
            if run["status"] != "succeeded" else _check_move(workspace.project_root(project_id), st, n, move, fetch)
        rnd = st["rounds"][str(n)]
        if move == "plan" and not error:
            rnd["metrics_plan"] = metrics
            known = {e["id"] for e in st.setdefault("needs_experiments", [])}
            for t in metrics["triage"]:
                if t["action"] == "new_experiment" and t["id"] not in known:
                    st["needs_experiments"].append({"id": t["id"], "concern": t["concern"], "reason": t["reason"],
                                                    "round": n})
            _write_needs(project_id, st)
        if move == "attack":
            rnd["metrics_attack"] = metrics
        elif metrics:
            rnd["metrics"] = metrics if move in {"score", "review"} else rnd.get("metrics", {})
            if move == "fix":
                rnd["metrics_fix"] = metrics
        if error:
            mv.update(status="rejected", error=error)
            if mv.get("attempt", 1) < MAX_ATTEMPTS:
                _start_move(store, project_id, st, n, move, retry_note=error)
            else:
                st.update(status="failed", stop_reason=f"round {n} {MOVE_LABELS[move]}: {error}", run_id=None)
                _save(project_id, st)
                store.log_activity(project_id, "loop_failed", f"{loop_id} {error}")
            return load(project_id, loop_id)
        mv.update(status="done", finished_at=now(), error=None)
        nxt = _decide(st, n, move)
        if isinstance(nxt, str):
            _finish(store, project_id, st, nxt)
        elif st["mode"] == "step" and nxt[0] != n and n > 0:
            st.update(status="paused", paused_reason=f"round {n} done — continue with round {nxt[0]}?",
                      next=list(nxt), run_id=None, move=None)
            _save(project_id, st)
        else:
            _start_move(store, project_id, st, *nxt)
        return load(project_id, loop_id)


def resume(store: Store, project_id: str, loop_id: str) -> dict:
    """Continue a paused loop, or run one more round after it finished or stopped."""
    with _lock:
        st = load(project_id, loop_id)
        if not st:
            raise LoopError("unknown loop")
        if st["status"] == "paused":
            n, move = st.pop("next")
        elif st["status"] in {"finished", "stopped"}:
            n = max((int(k) for k in st["rounds"]), default=0)
            last = st["rounds"].get(str(n), {}).get("moves", {})
            moves = TYPES[st["type"]]["moves"]
            pending = [m for m in moves if last.get(m, {}).get("status") != "done"]
            if pending and n > 0:
                move = pending[0]
            else:
                n, move = n + 1, moves[0]
            st["params"]["max_rounds"] = max(st["params"]["max_rounds"], n)
            st["stop_reason"] = None
        else:
            raise LoopError(f"the loop is {st['status']}")
        _start_move(store, project_id, st, n, move)
        return view(store, project_id, loop_id)


def retry(store: Store, project_id: str, loop_id: str) -> dict:
    with _lock:
        st = load(project_id, loop_id)
        if not st or st["status"] != "failed":
            raise LoopError("only a failed loop can be retried")
        n, move = st["round"], st["move"]
        st["rounds"][str(n)]["moves"][move]["attempt"] = 0
        _start_move(store, project_id, st, n, move,
                    retry_note=st["rounds"][str(n)]["moves"][move].get("error") or "retry")
        return view(store, project_id, loop_id)


def stop(store: Store, project_id: str, loop_id: str) -> dict:
    with _lock:
        st = load(project_id, loop_id)
        if not st:
            raise LoopError("unknown loop")
        if st.get("run_id"):
            claude_runner.cancel_run(store, st["run_id"])
        if st["status"] in {"running", "paused", "failed"}:
            if st.get("move") and st["rounds"].get(str(st["round"]), {}).get("moves", {}).get(st["move"]):
                st["rounds"][str(st["round"])]["moves"][st["move"]]["status"] = "cancelled"
            st.update(status="stopped", stop_reason="stopped by the user", run_id=None)
            st.pop("next", None)
            _save(project_id, st)
        return view(store, project_id, loop_id)


def steer(store: Store, project_id: str, loop_id: str, text: str) -> dict:
    text = (text or "").strip()
    if not text:
        raise LoopError("write a note")
    with _lock:
        st = load(project_id, loop_id)
        if not st:
            raise LoopError("unknown loop")
        st.setdefault("notes", []).append({"at": now(), "text": text[:2000], "used_in": None})
        _save(project_id, st)
        return view(store, project_id, loop_id)


def accept(store: Store, project_id: str, loop_id: str) -> dict:
    with _lock:
        st = load(project_id, loop_id)
        if not st or st["status"] not in {"finished", "stopped"}:
            raise LoopError("accept a loop after it has finished")
        st["best_round"] = st.get("best_round") or best_round(st)
        root = workspace.project_root(project_id)
        files = [f for f in final_files(st) if (root / f).is_file()]
        if not files:
            raise LoopError("this loop has no result file to accept")
        if st["type"] == "idea_forge":
            dest = root / "ideas" / f"final_idea_{loop_id}.md"
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(root / files[0], dest)
            files = [dest.relative_to(root).as_posix()]
        st.update(accepted=True, accepted_at=now(), accepted_files=files)
        _save(project_id, st)
        store.log_activity(project_id, "loop_accepted", f"{loop_id} {' '.join(files)}")
        return view(store, project_id, loop_id)


def view(store: Store, project_id: str, loop_id: str) -> dict:
    st = load(project_id, loop_id)
    if not st:
        raise LoopError("unknown loop")
    rounds = []
    for k in sorted(st.get("rounds", {}), key=int):
        r = st["rounds"][k]
        moves = [{"move": m, "label": MOVE_LABELS[m], **r["moves"][m]} for m in
                 (["seed"] if k == "0" else TYPES[st["type"]]["moves"]) if m in r["moves"]]
        rounds.append({"round": int(k), "moves": moves, "metrics": r.get("metrics", {}),
                       "evidence": (r.get("metrics_attack") or {}).get("evidence"), "fix": r.get("metrics_fix"), "plan": r.get("metrics_plan"),
                       "files": _round_files(project_id, st, int(k))})
    return {**{k: v for k, v in st.items() if k != "rounds"}, "label": TYPES[st["type"]]["label"], "rounds": rounds,
            "best_round": st.get("best_round") or best_round(st), "final_files": final_files(st),
            "rubric": [{"id": k, "label": RUBRIC_LABELS[k], "max": v} for k, v in RUBRIC.items()],
            "report": f"{LOOPS}/{st['id']}/report.md"}


def _round_files(project_id: str, st: dict, n: int) -> list[str]:
    root = workspace.project_root(project_id)
    d = root / LOOPS / st["id"] / f"round_{n}"
    out = [p.relative_to(root).as_posix() for p in sorted(d.glob("*")) if p.is_file()] if d.is_dir() else []
    if n == 0:
        out += [f for f in (f"{LOOPS}/{st['id']}/candidates.md", _idea_path(st, 0)) if (root / f).is_file()]
    if st["type"] == "review_fix" and n > 0:
        tex = _fixed_tex(st, n)
        out += [f for f in (tex, tex[:-4] + ".pdf") if (root / f).is_file()]
    return out


def list_view(store: Store, project_id: str) -> list[dict]:
    out = []
    for st in all_states(project_id):
        last = st.get("rounds", {}).get(str(st.get("round", 0)), {}).get("metrics", {})
        out.append({"id": st["id"], "type": st["type"], "label": TYPES[st["type"]]["label"], "goal": st["goal"],
                    "status": st["status"], "round": st.get("round"), "move": st.get("move"),
                    "stop_reason": st.get("stop_reason"), "paused_reason": st.get("paused_reason"),
                    "created_at": st["created_at"], "accepted": st.get("accepted", False),
                    "score": last.get("total"), "verified_major": last.get("verified_major")})
    return out


# ---------------------------------------------------------------- report
def _write_needs(project_id: str, st: dict) -> None:
    """Reviewer requests that need a real experiment: the loop never fakes them; the user decides."""
    items = st.get("needs_experiments") or []
    lines = ["# Experiments the reviewers asked for", "",
             "The review -> fix loop does not run or invent these. Decide which to run; results go to results/*.json.", ""]
    lines += [f"- **{e['id']}** (round {e['round']}): {e['concern']}" + (f" — {e['reason']}" if e["reason"] else "")
              for e in items] or ["(none so far)"]
    d = workspace.project_root(project_id) / LOOPS / st["id"]
    d.mkdir(parents=True, exist_ok=True)
    (d / "needs_experiments.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_report(project_id: str, st: dict) -> None:
    lines = [f"# {TYPES[st['type']]['label']} — {st['goal']}", "",
             f"Status: **{st['status']}**" + (f" — {st['stop_reason']}" if st.get("stop_reason") else ""), ""]
    if st["type"] == "idea_forge":
        lines += ["| Round | Papers | Checked refs | Wrong refs | Total /100 | Novelty /20 | Fatal flaws |",
                  "|---|---|---|---|---|---|---|"]
        for k in sorted(st.get("rounds", {}), key=int):
            r = st["rounds"][k]
            ev, m = (r.get("metrics_attack") or {}).get("evidence") or {}, r.get("metrics", {})
            if k == "0":
                continue
            lines.append(f"| {k} | {ev.get('papers', '')} | {ev.get('verified', '')}/{ev.get('sampled', '')} | "
                         f"{ev.get('fabricated_or_wrong', '')} | {m.get('total', '')} | "
                         f"{m.get('criteria', {}).get('novelty', '')} | {len(m.get('fatal_flaws', [])) if m else ''} |")
    else:
        lines += ["| Round | Concerns | Verified major | Quotes not found | " + " | ".join(k.capitalize() for k in SCORE_KEYS)
                  + " | Mean | Lines changed | Gate fails |", "|---" * (8 + len(SCORE_KEYS)) + "|"]
        for k in sorted(st.get("rounds", {}), key=int):
            r = st["rounds"][k]
            m, fx = r.get("metrics", {}), r.get("metrics_fix") or {}
            sc = m.get("scores") or {}
            lines.append(f"| {k} | {m.get('total', '')} | {m.get('verified_major', '')} | {m.get('downgraded', '')} | "
                         + " | ".join(f"{sc[s]:g}" if s in sc else "" for s in SCORE_KEYS)
                         + f" | {m.get('mean_score', '')} | "
                         f"{str(int(fx['change_ratio'] * 100)) + '%' if fx.get('change_ratio') is not None else ''} | "
                         f"{(fx.get('gate') or {}).get('counts', {}).get('fail', '')} |")
        lines += ["", "Targets: " + ", ".join(f"{s} {st['params'].get('target_' + s, '')}" for s in SCORE_KEYS)]
    lines += ["", "Numbers in this table are computed by the server from the round files, not copied from the agent."]
    d = workspace.project_root(project_id) / LOOPS / st["id"]
    d.mkdir(parents=True, exist_ok=True)
    (d / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------- background advance
def tick(store: Store) -> None:
    for p in store.all("SELECT id FROM projects WHERE status='active'"):
        for st in all_states(p["id"]):
            if st.get("status") == "running":
                try:
                    reconcile(store, p["id"], st["id"])
                except Exception as exc:  # one broken loop must not stop the others
                    store.log_activity(p["id"], "loop_error", f"{st['id']} {type(exc).__name__}: {exc}")


_ticker: threading.Thread | None = None


def start_ticker(store: Store, every_s: float = 3.0) -> None:
    global _ticker
    if _ticker and _ticker.is_alive():
        return

    def loop():
        while True:
            try:
                tick(store)
            except Exception:
                pass
            time.sleep(every_s)
    _ticker = threading.Thread(target=loop, daemon=True, name="loops-ticker")
    _ticker.start()
