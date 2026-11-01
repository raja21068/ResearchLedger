"""One-click start: understand a plain goal (and uploaded files), pick the right pipeline, start it.

- Whole papers go to the Paper Studio with Autopilot on (each stage starts by itself after
  the user approves the previous one).
- Single jobs (review this paper, generate code, slides, …) go to a ready-made recipe; if a
  required file is missing the user is sent to that recipe's upload page.
- The user's repeated multi-prompt habits go to a research loop: idea novelty attack -> score -> redesign
  ("why is this idea not novel?"), and review -> fix -> re-review of a .tex manuscript.
- Anything else goes to the Research Director, which proposes a plan for approval.
Rule-based on purpose: instant, predictable and explainable ("why" is returned).
"""
from __future__ import annotations

import re
from pathlib import Path

from . import director, loops, paper_studio, recipes, workspace
from .db import Store, new_id, now

IDEA_LOOP = (r"not novel|novelty|attack (the |my |this )?idea|(refine|improve|strengthen|redesign|score) (the |my |this )?"
             r"(research )?idea|research idea|(generate|find|brainstorm|propose)\b.{0,30}\bideas?\b|idea (for|on|about)")
REVIEW_LOOP = (r"review.{0,60}\b(fix|revise|improve|correct)|\bfix\b.{0,40}\b(paper|manuscript|review)|re-?review|"
               r"submission[- ]ready|until (it is |it's )?(clean|ready)|review (and|then) (fix|revise)")

PAPER_RULES = [
    (r"\bthesis|dissertation\b", "thesis_to_paper", "you mentioned a thesis"),
    (r"rebuttal|respond(ing)? to (the )?review|reviewer comments|response letter|major revision|minor revision",
     "revision_rebuttal", "you mentioned reviewer comments"),
    (r"survey|review paper|literature review paper|systematic review|state of the art review", "review_paper",
     "you asked for a review/survey paper"),
    (r"(write|draft|create|generate|produce|make)\b.{0,40}\b(paper|manuscript|article)\b|full paper|journal paper|"
     r"conference paper|paper (on|about)", "research_article", "you asked for a full paper"),
]


def classify(goal: str, filenames: list[str]) -> dict:
    g = goal.lower()
    if any(f.lower().endswith(".tex") for f in filenames) and re.search(REVIEW_LOOP, g):
        return {"mode": "loop", "loop": "review_fix", "why": "review, fix and re-review your .tex until it is clean"}
    if re.search(IDEA_LOOP, g) and not re.search(PAPER_RULES[3][0], g):
        return {"mode": "loop", "loop": "idea_forge",
                "why": "novelty attack (50+ papers) -> score -> redesign, repeated until the idea passes"}
    for pattern, ptype, why in PAPER_RULES:
        if re.search(pattern, g):
            return {"mode": "paper", "paper_type": ptype, "why": why}
    s = recipes.suggest(filenames, goal)
    if s and s[0]["score"] >= 1.5:
        return {"mode": "recipe", "recipe": s[0]["id"], "why": s[0]["why"] or f"best match: {s[0]['name']}"}
    return {"mode": "director", "why": "general request: the Research Director will propose a plan"}


def _assign(recipe_id: str, paths: list[str]) -> dict[str, list[str]]:
    r = recipes.R[recipe_id]
    out: dict[str, list[str]] = {}
    for p in paths:
        n, ext = p.lower(), Path(p).suffix.lower()
        fits = [i for i in r["inputs"] if ext in i["accept"]]
        if not fits:
            continue
        role = next((i["role"] for i in fits if i["role"] == "comments" and re.search(r"comment|review|response|decision", n)), None) \
            or next((i["role"] for i in fits if i["role"] == "reference" and re.search(r"reference|template|sample|style", n)), None) \
            or next((i["role"] for i in fits if not out.get(i["role"]) or i.get("multiple")), fits[0]["role"])
        spec = next(i for i in r["inputs"] if i["role"] == role)
        out[role] = (out.get(role, []) + [p]) if spec.get("multiple") else [p]
    return out


def start(store: Store, project_id: str, goal: str, files: list[str], model: str | None = None) -> dict:
    """Start the right pipeline in `project_id` (files are workspace-relative uploads)."""
    root = workspace.project_root(project_id)
    for f in files:
        if not workspace.resolve(project_id, f).is_file():
            raise ValueError(f"file not found: {f}")
    decision = classify(goal, [Path(f).name for f in files])
    if decision["mode"] == "paper":
        ptype = decision["paper_type"]
        if not paper_studio.load(project_id):
            # Paper types that read uploads/ need the user's files there.
            for f in files:
                if not f.startswith("uploads/"):
                    dest = root / "uploads" / Path(f).name
                    dest.parent.mkdir(exist_ok=True)
                    dest.write_bytes((root / f).read_bytes())
            paper_studio.create(store, project_id, ptype, "journal", goal)
        return {**decision, "project_id": project_id, "url": f"/projects/{project_id}/paper"}
    if decision["mode"] == "loop":
        texts = {f: (root / f).read_text(encoding="utf-8", errors="replace") for f in files
                 if Path(f).suffix.lower() in {".md", ".txt"}}
        if decision["loop"] == "review_fix":
            tex = next(f for f in files if f.lower().endswith(".tex"))
            ext = next((t for f, t in texts.items() if re.search(r"review|comment|feedback|report", f.lower())), None)
            v = loops.create(store, project_id, "review_fix", goal, manuscript=tex, external_review=ext)
        else:
            idea = "\n\n".join(texts.values()) or (goal if len(goal) > 400 else None)
            v = loops.create(store, project_id, "idea_forge", goal, idea_text=idea)
        return {**decision, "project_id": project_id, "loop_id": v["id"], "url": f"/projects/{project_id}/loops/{v['id']}"}
    if decision["mode"] == "recipe":
        rid = decision["recipe"]
        assigned = _assign(rid, files)
        needs_text = any(o.get("required") for o in recipes.R[rid]["options"])
        options = {o["name"]: goal for o in recipes.R[rid]["options"] if o.get("required") and o["kind"] == "text"}
        missing = [i["label"] for i in recipes.R[rid]["inputs"] if i.get("required") and not assigned.get(i["role"])]
        if missing or (needs_text and not goal.strip()):
            q = "&".join(f"f={p}" for p in files)
            return {**decision, "project_id": project_id, "missing": missing,
                    "url": f"/do/{rid}?project={project_id}" + (f"&{q}" if q else "")}
        r = recipes.run(store, project_id, rid, assigned, options)
        return {**decision, "project_id": project_id, "url": f"/projects/{project_id}?conv={r['conversation_id']}"}
    cid, ts = new_id("cnv"), now()
    store.exec("INSERT INTO conversations(id,project_id,title,created_at,updated_at) VALUES (?,?,?,?,?)",
               (cid, project_id, "New chat", ts, ts))
    text = goal + ("\n\nAttached files in the workspace:\n" + "\n".join(f"- `{f}`" for f in files) if files else "")
    director.start_turn(store, cid, text, model)
    return {**decision, "project_id": project_id, "url": f"/projects/{project_id}?conv={cid}"}
