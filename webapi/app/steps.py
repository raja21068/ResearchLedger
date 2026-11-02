"""The research pipeline the user sees, in one place: the same seven numbered steps in the console (/rl) and the GUI.

Each step names what the user gives, what they get, the user's own (tested) engines behind it, and how it starts:
a ready-made recipe, a loop, a page, or the server's check. "Whole pipeline" is the guided Paper Studio, which runs
the steps in order with an approval after each one. Add or rename a step here, not in the console or the GUI.
"""
from __future__ import annotations

import re
from pathlib import Path

from . import autopilot, loops, quality, recipes, workspace
from .db import Store, new_id

PIPELINE = {
    "name": "Guided paper (all steps)", "href": "/paper",
    "does": "Runs steps 1 → 7 for you in order: literature, idea, method, code, experiments, writing, review, revision. "
            "You approve each step before the next starts.",
    "console": 'RL new "<title>" --paper, then RL start <p> "Write a full research paper about: <idea>. Target: <venue>."',
}

STEPS = [
    {"n": 1, "id": "literature", "group": "Idea", "name": "Literature",
     "give": "PDFs, a zip of papers, or a topic", "get": "summary, methods, results and research-gap table",
     "engines": ["Literature skills", "your prompt 1 Literature Understanding"],
     "href": "/step/literature",
     "console": 'RL start <p> "Understand and compare these papers: method, data, results, limitations, research gap" --files <PDFs>'},
    {"n": 2, "id": "idea", "group": "Idea", "name": "Idea",
     "give": "a topic, or your own idea", "get": "a scored idea (/100) that survived a 50+ paper novelty search",
     "engines": ["Idea Discovery V5", "your prompts Phase 10–13 (scorecard, novelty attack, matrix, reviewer #1)"],
     "href": "/step/idea",
     "console": 'RL start <p> "<topic or idea>" --repeat idea'},
    {"n": 3, "id": "code", "group": "Build", "name": "Method and code",
     "give": "your idea or method", "get": "experiment plan (baselines, ablations) and runnable code",
     "engines": ["PaperCompiler", "Research code agent V4", "experiment-design skills"],
     "href": "/step/code",
     "options": [{"name": "framework", "label": "Framework", "choices": ["PyTorch", "TensorFlow", "scikit-learn", "any"]}],
     "console": 'RL start <p> "Generate research code (<framework>) for: <description>" --files <idea or paper>'},
    {"n": 4, "id": "experiments", "group": "Build", "name": "Run experiments",
     "give": "what to test (or the reviewers' requests)", "get": "measured results, each traced to its script and run",
     "engines": ["Experiment loop: plan locked first, runs only after your click"],
     "href": "/step/experiments",
     "console": 'RL experiment <p> "<what to test>" [--tex <paper.tex>]'},
    {"n": 5, "id": "write", "group": "Write", "name": "Write paper",
     "give": "idea and results", "get": "LaTeX paper with figures and a compiled PDF",
     "engines": ["PaperOrchestra (outline, literature, figures, sections, refine)", "your prompt 6 Paper Writing"],
     "href": "/step/write",
     "options": [{"name": "journal", "label": "Target journal (optional)"}],
     "console": 'RL start <p> "Write my paper from the idea and results in this project" --files <idea, results>'},
    {"n": 6, "id": "review", "group": "Review", "name": "Review and revise",
     "give": "your .tex (and a ChatGPT or journal review, if you have one)",
     "get": "fixed paper and new PDF, re-reviewed until clean or your score targets are met",
     "engines": ["Beihang referee", "Master auto-review loop", "your prompt 8 Reviewer Simulation"],
     "href": "/step/review",
     "console": 'RL start <p> "Review and fix my paper" --files <tex> [review] --repeat review   '
                '(journal comments: "Revise the paper and write a response to the reviewers")'},
    {"n": 7, "id": "check", "group": "Submit", "name": "Final check",
     "give": "your .tex", "get": "ready / not ready: references, numbers, figures, placeholders, pages",
     "engines": ["Submission gate (server)", "your prompt 99 Journal-ready paper"],
     "href": "/step/check",
     "console": "RL check <p> <tex>"},
]

EXTRAS = [
    {"id": "slides", "name": "Slides", "href": "/do/make_slides"},
    {"id": "style", "name": "Match a journal's style", "href": "/do/match_reference_style"},
    {"id": "rebuttal", "name": "Respond to reviewers", "href": "/do/respond_to_reviewers"},
    {"id": "chat", "name": "Ask the Research Director", "href": "/"},
]


def menu_text() -> str:
    """The console menu (printed by `rl_cli.py menu`)."""
    lines = ["ResearchLedger — choose a number", ""]
    group = None
    for s in STEPS:
        if s["group"] != group:
            group = s["group"]
            lines.append(f" {group.upper()}")
        lines.append(f"  {s['n']}. {s['name']:<18} {s['give']}  →  {s['get']}")
    lines += ["", f"  8. {PIPELINE['name']:<18} runs 1 → 7 in order; you approve each step",
              "  0. Status             what is running and what waits for you", "",
              "  Also: " + " · ".join(e["name"] for e in EXTRAS), "",
              " Type a number with your topic, files or pasted text, e.g.  2 zero-knowledge proofs for AI oracles"]
    return "\n".join(lines)


class StepError(ValueError):
    """A plain sentence telling the user what to add."""


TEXT_EXT = {".md", ".txt"}
# Which step a finished job belongs to, so its page can suggest the next step.
RECIPE_STEP = {"understand_papers": "literature", "generate_ideas": "idea", "generate_code": "code",
               "write_paper": "write", "review_paper": "review", "respond_to_reviewers": "review",
               "presubmission_check": "check"}
LOOP_STEP = {"idea_forge": "idea", "experiment": "experiments", "review_fix": "review"}


def step(step_id: str) -> dict:
    for s in STEPS:
        if s["id"] == step_id:
            return s
    raise StepError("Unknown step.")


def _save_text(project_id: str, step_id: str, text: str, name: str = "input") -> str:
    rel = f"uploads/{step_id}_{name}_{new_id('t')[2:8]}.md"
    p = workspace.resolve(project_id, rel)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text.strip() + "\n", encoding="utf-8")
    return rel


def _read(project_id: str, rel: str) -> str:
    return workspace.resolve(project_id, rel).read_text(encoding="utf-8", errors="replace")


def start(store: Store, project_id: str, step_id: str, text: str = "", files: list[str] | None = None,
          options: dict | None = None) -> dict:
    """Start one step from whatever the user gave (files and/or pasted text). Returns {url, label}."""
    s, files, text, options = step(step_id), list(files or []), (text or "").strip(), options or {}
    for f in files:
        if not workspace.resolve(project_id, f).is_file():
            raise StepError(f"A file is missing from the project: {f}")
    ext = lambda f: Path(f).suffix.lower()
    tex = [f for f in files if ext(f) == ".tex"]
    docs = [f for f in files if ext(f) in recipes.DOC_EXT]
    texts = [f for f in files if ext(f) in TEXT_EXT]
    is_review = lambda f: bool(re.search(r"review|comment|feedback|report|decision", Path(f).name.lower()))
    chat = lambda r: f"/projects/{project_id}?conv={r['conversation_id']}"
    loop_url = lambda v: f"/projects/{project_id}/loops/{v['id']}"

    if step_id == "literature":
        if docs:
            return {"url": chat(recipes.run(store, project_id, "understand_papers", {"papers": docs}, {})), "label": s["name"]}
        if not text:
            raise StepError("Add the papers (PDFs or a zip), or type a topic to search.")
        r = autopilot.start(store, project_id, f"Find and summarise the key recent papers on: {text}. For each: method, "
                                               "data, results, limitations; then the research gap.", [])
        return {"url": r["url"], "label": s["name"]}
    if step_id == "idea":
        idea = "\n\n".join([_read(project_id, f) for f in texts] + ([text] if len(text) > 300 else []))
        if not idea and not text:
            raise StepError("Type a topic, or paste your idea.")
        goal = text if text and len(text) <= 300 else "Improve my idea"
        return {"url": loop_url(loops.create(store, project_id, "idea_forge", goal, idea_text=idea or None)), "label": s["name"]}
    if step_id == "code":
        src = next((f for f in docs if not is_review(f)), None) or (_save_text(project_id, "code", text, "idea") if text else None)
        if not src:
            raise StepError("Add your idea or method (a file, or paste it as text).")
        r = recipes.run(store, project_id, "generate_code", {"source": [src]},
                        {"framework": options.get("framework") or "PyTorch"})
        return {"url": chat(r), "label": s["name"]}
    if step_id == "experiments":
        req = "\n\n".join([_read(project_id, f) for f in texts] + ([text] if text else []))
        if not req:
            raise StepError("Describe what to test (or paste the reviewer's request).")
        v = loops.create(store, project_id, "experiment", "", experiments_text=req, manuscript=tex[0] if tex else None)
        return {"url": loop_url(v), "label": s["name"]}
    if step_id == "write":
        materials = [f for f in files if ext(f) in recipes.DOC_EXT + [".csv", ".json"] and "template" not in f.lower()]
        if text:
            materials.append(_save_text(project_id, "write", text, "idea"))
        if not materials:
            raise StepError("Add your idea and results (files), or paste the idea as text.")
        template = [f for f in files if "template" in f.lower() and ext(f) in {".tex", ".zip", ".cls", ".sty"}][:1]
        r = recipes.run(store, project_id, "write_paper", {"materials": materials, "template": template},
                        {"journal": options.get("journal", "")})
        return {"url": chat(r), "label": s["name"]}
    if step_id == "review":
        reviews = [f for f in texts if is_review(f)]
        review_text = "\n\n".join([_read(project_id, f) for f in reviews] + ([text] if text else []))
        if tex:
            v = loops.create(store, project_id, "review_fix", "", manuscript=tex[0], external_review=review_text or None)
            return {"url": loop_url(v), "label": s["name"]}
        paper = next((f for f in docs if not is_review(f) and f not in texts), None)
        if not paper:
            raise StepError("Add your paper: the .tex to review and fix it, or the PDF to answer journal reviewers.")
        if not review_text:
            r = recipes.run(store, project_id, "review_paper", {"paper": [paper]}, {})
            return {"url": chat(r), "label": "Review (add the .tex to also fix it)"}
        comments = reviews[0] if reviews else _save_text(project_id, "review", review_text, "reviewer_comments")
        r = recipes.run(store, project_id, "respond_to_reviewers", {"paper": [paper], "comments": [comments]}, {})
        return {"url": chat(r), "label": "Respond to reviewers"}
    if step_id == "check":
        if not tex:
            raise StepError("Add your paper's .tex file (with its .bib and figures next to it).")
        quality.gate(workspace.project_root(project_id), tex[0], target_refs=40)
        return {"url": f"/quality?project={project_id}&tex={tex[0]}", "label": s["name"]}
    raise StepError("Unknown step.")
