"""Server-side configuration, read once from environment variables."""
from __future__ import annotations

import json
import os
import shlex
import shutil
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# Tools the Claude Code session may use inside a project workspace. Bash is
# limited to the LaTeX toolchain: the browser never gets arbitrary shell.
DEFAULT_ALLOWED_TOOLS = [
    "Read", "Write", "Edit", "MultiEdit", "Glob", "Grep", "WebSearch", "WebFetch", "TodoWrite",
    "Bash(pdflatex:*)", "Bash(bibtex:*)", "Bash(biber:*)", "Bash(latexmk:*)",
]


def _claude_command() -> list[str]:
    raw = os.environ.get("RL_CLAUDE_CMD")
    if raw:
        # JSON list (preferred, survives Windows paths) or a shell-style string.
        return json.loads(raw) if raw.lstrip().startswith("[") else shlex.split(raw)
    found = shutil.which("claude")
    return [found] if found else []


@dataclass(frozen=True)
class Settings:
    data_dir: Path = field(default_factory=lambda: Path(
        os.environ.get("RL_WEB_DATA", REPO_ROOT / "webapi_data")).resolve())
    claude_cmd: list[str] = field(default_factory=_claude_command)
    allowed_tools: list[str] = field(default_factory=lambda: (
        json.loads(os.environ["RL_CLAUDE_ALLOWED_TOOLS"])
        if os.environ.get("RL_CLAUDE_ALLOWED_TOOLS") else list(DEFAULT_ALLOWED_TOOLS)))
    default_model: str | None = os.environ.get("RL_CLAUDE_MODEL") or None
    run_timeout_s: int = int(os.environ.get("RL_RUN_TIMEOUT_S", "3600"))
    max_upload_bytes: int = int(os.environ.get("RL_MAX_UPLOAD_MB", "50")) * 1024 * 1024
    frontend_origins: list[str] = field(default_factory=lambda: os.environ.get(
        "RL_FRONTEND_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(","))

    @property
    def db_path(self) -> Path:
        return self.data_dir / "researchledger_web.sqlite3"

    @property
    def projects_dir(self) -> Path:
        return self.data_dir / "projects"


settings = Settings()
