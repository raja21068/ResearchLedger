"""Skill tools: every unpacked SKILL.md in the configured skill folders becomes a tool.

A skill run copies the skill's folder into the project workspace (`.skills/<id>/`,
hidden from file listings) so the Claude Code agent can read it without write
access to the original, then asks the agent to follow it for the user's task.
Zipped skills are counted but not used until unpacked.
"""
from __future__ import annotations

import os
import re
import shutil
import threading
from pathlib import Path

from .config import REPO_ROOT

DEFAULT_ROOTS = [Path(r"D:\AutoResearch\academic-research-skills-offline"), REPO_ROOT / "skills"]
SKIP_PARTS = {".claude", ".git", "node_modules", "__pycache__", "$out", "pervious version", "previous version"}
COPY_LIMIT_BYTES = 25 * 1024 * 1024
_cache: dict | None = None
_lock = threading.Lock()


def roots() -> list[Path]:
    raw = os.environ.get("RL_SKILL_ROOTS")
    return [Path(p) for p in raw.split(os.pathsep)] if raw else DEFAULT_ROOTS


def _frontmatter(text: str) -> dict:
    m = re.match(r"^---\s*\n(.*?)\n---", text, re.S)
    if not m:
        return {}
    out, key = {}, None
    for line in m.group(1).splitlines():
        kv = re.match(r"^([A-Za-z_-]+):\s*(.*)$", line)
        if kv:
            key, val = kv.group(1), kv.group(2).strip()
            out[key] = "" if val in {">", "|", ">-", "|-"} else val.strip('"\'')
        elif key and line.startswith((" ", "\t")):
            out[key] = (out[key] + " " + line.strip()).strip()
    return out


def _category(root: Path, skill_dir: Path) -> str:
    if root == REPO_ROOT / "skills":
        return "Research method skills"
    top = skill_dir.relative_to(root).parts[0] if skill_dir != root else root.name
    top = re.sub(r"\(.*?\)", "", top)
    top = re.sub(r"^[\d.\s-]+", "", top).replace("-", " ").replace("_", " ")
    top = " ".join(top.split()).title() or "Skills"
    return {"Phd Apply Agnet Localy": "PhD Application", "Paper Finder Search": "Paper Finder"}.get(top, top)


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60] or "skill"


def scan() -> dict:
    skills: dict[str, dict] = {}
    zipped = 0
    for root in roots():
        if not root.is_dir():
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in SKIP_PARTS]
            zipped += sum(1 for f in filenames if f.endswith((".zip", ".skill")))
            if "SKILL.md" not in filenames:
                continue
            md = Path(dirpath) / "SKILL.md"
            try:
                meta = _frontmatter(md.read_text(encoding="utf-8", errors="replace")[:20000])
            except OSError:
                continue
            name = meta.get("name") or Path(dirpath).name
            sid = "skill-" + _slug(name)
            depth = len(md.relative_to(root).parts)
            if sid in skills and skills[sid]["_depth"] <= depth:
                continue  # keep the shallowest copy of a duplicated skill
            desc = re.sub(r"\s+", " ", meta.get("description", "")).strip()
            desc = re.split(r"(?<=[.!?])\s+(?:Use when|TRIGGER|Trigger)", desc)[0]
            skills[sid] = {"id": sid, "name": name.replace("-", " ").strip().capitalize(), "slug": name,
                           "description": desc[:280], "category": _category(root, Path(dirpath)),
                           "path": str(md), "dir": str(Path(dirpath)), "_depth": depth}
    items = sorted(skills.values(), key=lambda s: (s["category"], s["name"]))
    for s in items:
        s.pop("_depth", None)
    return {"skills": items, "zipped_packages": zipped, "roots": [str(r) for r in roots()]}


def catalog(refresh: bool = False) -> dict:
    global _cache
    with _lock:
        if _cache is None or refresh:
            _cache = scan()
        return _cache


def get(skill_id: str) -> dict | None:
    return next((s for s in catalog()["skills"] if s["id"] == skill_id), None)


def stage(skill: dict, workspace: Path) -> str:
    """Copy the skill folder into the workspace; return its relative SKILL.md path."""
    src = Path(skill["dir"])
    dest = workspace / ".skills" / skill["id"]
    if dest.exists():
        shutil.rmtree(dest)
    total = 0

    def ignore(folder, names):
        nonlocal total
        skipped = {n for n in names if n in SKIP_PARTS or n.endswith((".zip", ".skill", ".pdf", ".mp4"))}
        for n in names:
            p = Path(folder) / n
            if n not in skipped and p.is_file():
                total += p.stat().st_size
                if total > COPY_LIMIT_BYTES:
                    skipped.add(n)
        return skipped

    shutil.copytree(src, dest, ignore=ignore)
    return (dest / "SKILL.md").relative_to(workspace).as_posix()


def prompt(skill: dict, skill_md: str, task: str, files: list[str]) -> str:
    attached = "\n".join(f"- `{f}`" for f in files) or "- (none)"
    out_dir = f"outputs/{skill['slug']}/"
    return (f"Use the skill **{skill['name']}**. Its instructions are in `{skill_md}`: read that file completely "
            f"before doing anything, and read the other files in its folder that it refers to. Follow its procedure.\n\n"
            f"Task from the user:\n{task}\n\nAttached files in the workspace:\n{attached}\n\n"
            f"Write the outputs under `{out_dir}` unless the skill names other locations. Do not modify files under "
            "`.skills/`. If a step needs a tool you do not have here (running Python or other programs, external "
            "APIs such as Gemini or Codex), complete every step you can, then list the skipped steps and the exact "
            "commands the user can run themselves. Do not invent data, results or references.")
