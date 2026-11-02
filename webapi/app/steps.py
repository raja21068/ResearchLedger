"""The research pipeline the user sees, in one place: the same seven numbered steps in the console (/rl) and the GUI.

Each step names what the user gives, what they get, the user's own (tested) engines behind it, and how it starts:
a ready-made recipe, a loop, a page, or the server's check. "Whole pipeline" is the guided Paper Studio, which runs
the steps in order with an approval after each one. Add or rename a step here, not in the console or the GUI.
"""
from __future__ import annotations

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
     "href": "/do/understand_papers",
     "console": 'RL start <p> "Understand and compare these papers: method, data, results, limitations, research gap" --files <PDFs>'},
    {"n": 2, "id": "idea", "group": "Idea", "name": "Idea",
     "give": "a topic, or your own idea", "get": "a scored idea (/100) that survived a 50+ paper novelty search",
     "engines": ["Idea Discovery V5", "your prompts Phase 10–13 (scorecard, novelty attack, matrix, reviewer #1)"],
     "href": "/loops?type=idea_forge",
     "console": 'RL start <p> "<topic or idea>" --repeat idea'},
    {"n": 3, "id": "code", "group": "Build", "name": "Method and code",
     "give": "your idea or method", "get": "experiment plan (baselines, ablations) and runnable code",
     "engines": ["PaperCompiler", "Research code agent V4", "experiment-design skills"],
     "href": "/do/generate_code",
     "console": 'RL start <p> "Generate research code (<framework>) for: <description>" --files <idea or paper>'},
    {"n": 4, "id": "experiments", "group": "Build", "name": "Run experiments",
     "give": "what to test (or the reviewers' requests)", "get": "measured results, each traced to its script and run",
     "engines": ["Experiment loop: plan locked first, runs only after your click"],
     "href": "/loops?type=experiment",
     "console": 'RL experiment <p> "<what to test>" [--tex <paper.tex>]'},
    {"n": 5, "id": "write", "group": "Write", "name": "Write paper",
     "give": "idea and results", "get": "LaTeX paper with figures and a compiled PDF",
     "engines": ["PaperOrchestra (outline, literature, figures, sections, refine)", "your prompt 6 Paper Writing"],
     "href": "/do/write_paper",
     "console": 'RL start <p> "Write my paper from the idea and results in this project" --files <idea, results>'},
    {"n": 6, "id": "review", "group": "Review", "name": "Review and revise",
     "give": "your .tex (and a ChatGPT or journal review, if you have one)",
     "get": "fixed paper and new PDF, re-reviewed until clean or your score targets are met",
     "engines": ["Beihang referee", "Master auto-review loop", "your prompt 8 Reviewer Simulation"],
     "href": "/loops?type=review_fix",
     "console": 'RL start <p> "Review and fix my paper" --files <tex> [review] --repeat review   '
                '(journal comments: "Revise the paper and write a response to the reviewers")'},
    {"n": 7, "id": "check", "group": "Submit", "name": "Final check",
     "give": "your .tex", "get": "ready / not ready: references, numbers, figures, placeholders, pages",
     "engines": ["Submission gate (server)", "your prompt 99 Journal-ready paper"],
     "href": "/quality",
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
