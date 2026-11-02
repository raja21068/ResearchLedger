"""Standing preferences: the instructions the user repeats in almost every session, applied to every agent task.

The defaults come from the user's own recurring prompts ("independently verify every reference", "don't invent
citations or DOIs", "surgical changes only", "stick to the template", "complete, finished version", "check everything
again"). They are added to the agent's system instructions (CLI and Claude app worker alike), so the user no longer
types them. Stored in `<data_dir>/preferences.json`; editable in Settings.
"""
from __future__ import annotations

import json

from .config import settings

DEFAULT_RULES = [
    "Independently verify every reference, DOI and factual claim before you use it (Crossref, arXiv, the publisher "
    "page). Never invent citations, references, DOI numbers, data or results; mark anything you could not verify.",
    "When novelty or related work is in question, search widely: at least 50 recent papers (2024-2026 first), "
    "including arXiv and the main venues, and name the closest competitors explicitly.",
    "Edit surgically: change only what the task needs, do not rephrase text that is not part of the fix, and keep "
    "the original template, structure and style.",
    "Deliver complete, finished files (compiled PDF when there is LaTeX), not outlines, scaffolds or partial drafts.",
    "Score and rank objectively against the stated rubric; do not inflate scores or hide weaknesses.",
    "Before you finish, check everything again: re-read your outputs, recompile, re-check references and numbers.",
    "Explain what you changed and why in plain, simple language.",
]


def _path():
    return settings.data_dir / "preferences.json"


def load() -> dict:
    try:
        data = json.loads(_path().read_text(encoding="utf-8"))
        rules = [str(r).strip() for r in data.get("rules", []) if str(r).strip()]
        return {"enabled": bool(data.get("enabled", True)), "rules": rules, "custom": True}
    except (OSError, ValueError):
        return {"enabled": True, "rules": list(DEFAULT_RULES), "custom": False}


def save(enabled: bool, rules: list[str]) -> dict:
    clean = [r.strip() for r in rules if r and r.strip()][:30]
    _path().parent.mkdir(parents=True, exist_ok=True)
    _path().write_text(json.dumps({"enabled": enabled, "rules": clean}, indent=2), encoding="utf-8")
    return load()


def reset() -> dict:
    try:
        _path().unlink()
    except FileNotFoundError:
        pass
    return load()


def system_block() -> str:
    """Text appended to the agent's system instructions ('' when switched off)."""
    p = load()
    if not p["enabled"] or not p["rules"]:
        return ""
    return "\n\nThe user's standing instructions (apply to every task):\n" + "\n".join(f"- {r}" for r in p["rules"])
