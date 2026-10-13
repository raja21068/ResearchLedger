"""Resolve the first-party PaperOrchestra skill without installing into ~/.claude.

The vendored PaperOrchestra *source* includes API-backed Python utilities. The
ResearchLedger skill is a distinct, provider-neutral Claude/Codex CLI writing
workflow that reads the vendor's prompt recipes but does not execute its API
runtime. Keeping the two paths separate avoids accidental credential demands.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BUNDLED_SKILLS = ROOT / "skills"
EXTERNAL_SKILLS = Path.home() / ".claude" / "skills"
VENDOR_DIR = ROOT / "vendor" / "paperorchestra"
VENDOR_PROMPTS = (
    "outline_agent.py", "literature_review_agent.py",
    "section_writing_agent.py", "content_refinement_agent.py",
)


def resolve_skills_dir(explicit=None):
    """Prefer bundled; never mask a broken explicitly configured directory."""
    if explicit is not None:
        choice = Path(explicit).expanduser().resolve()
        if not (choice / "paper-orchestra" / "SKILL.md").is_file():
            raise ValueError(f"PaperOrchestra skills not found in {choice}")
        return choice
    for choice in (BUNDLED_SKILLS, EXTERNAL_SKILLS):
        if (choice / "paper-orchestra" / "SKILL.md").is_file():
            return choice.resolve()
    raise ValueError(
        "PaperOrchestra skills not found: expected bundled "
        f"{BUNDLED_SKILLS / 'paper-orchestra' / 'SKILL.md'} "
        "or ~/.claude/skills/paper-orchestra/SKILL.md"
    )


def bundled_vendor_present():
    """Verify real upstream prompt assets, not merely a vendor directory."""
    base = VENDOR_DIR / "methods" / "prompts"
    return all((base / f).is_file() for f in VENDOR_PROMPTS)


def writing_access_dirs(skills_dir):
    """Expose only source-reading roots explicitly needed by the bundled skill."""
    paths = [Path(skills_dir).resolve()]
    if Path(skills_dir).resolve() == BUNDLED_SKILLS.resolve():
        if not bundled_vendor_present():
            raise ValueError("bundled PaperOrchestra original prompts are missing")
        paths.append(VENDOR_DIR.resolve())
    return paths
