"""Research Memory: one Markdown file per project, shared by every agent and tool.

The server appends a dated entry after every run (what ran, its status, its summary
and the files it produced). The user can edit the file from the Research Memory page.
Agents read it as context; they never rewrite it.
"""
from __future__ import annotations

import threading
from datetime import datetime, timezone

from . import workspace

MEMORY_PATH = "memory/research_memory.md"
HEADER = ("# Research memory\n\n"
          "Shared context for every agent in this project. Edit the sections below freely; "
          "run entries are appended automatically.\n\n"
          "## Research question\n\n[Write your research question here]\n\n"
          "## Key decisions\n\n- \n\n"
          "## Run log\n")
_lock = threading.Lock()


def path(project_id: str):
    return workspace.project_root(project_id) / MEMORY_PATH


def read(project_id: str) -> str:
    p = path(project_id)
    return p.read_text(encoding="utf-8") if p.is_file() else HEADER


def write(project_id: str, text: str) -> None:
    p = path(project_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    with _lock:
        p.write_text(text, encoding="utf-8")


def append_run(project_id: str, title: str, run_id: str, status: str, summary: str | None,
               files: list[str]) -> None:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [f"\n### {stamp} · {title} · {status}", f"- Run: `{run_id}`"]
    if summary:
        lines.append("- Summary: " + " ".join(summary.split())[:600])
    if files:
        lines.append("- Files: " + ", ".join(f"`{f}`" for f in files[:20]))
    with _lock:
        p = path(project_id)
        p.parent.mkdir(parents=True, exist_ok=True)
        text = p.read_text(encoding="utf-8") if p.is_file() else HEADER
        p.write_text(text.rstrip("\n") + "\n" + "\n".join(lines) + "\n", encoding="utf-8")
