"""Run an authenticated Claude Code or Codex *writing* session without API keys.

This module is intentionally different from the review/idea JSON-only transport:
writing is permitted in the specified project working directory. Vendor source
and skills are read as guidance; API-backed PaperOrchestra Python code is never
started by this adapter. A running CLI must already be authenticated locally.
"""
from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import tempfile


def run_session(prompt, cwd, tools, add_dirs=(), permission_mode="acceptEdits", model=None,
                timeout=3600, provider="claude"):
    if provider not in ("claude", "codex"):
        raise ValueError("writing session provider must be claude or codex")
    executable = shutil.which(provider)
    if not executable:
        raise ValueError(f"{provider} CLI is not installed or not on PATH")
    cwd = Path(cwd).resolve()
    if not cwd.is_dir():
        raise ValueError(f"writing workspace does not exist: {cwd}")
    if provider == "claude":
        command = [executable, "-p", "--output-format", "text", "--no-session-persistence",
                   "--permission-mode", permission_mode, "--allowedTools", *tools]
        for directory in add_dirs:
            command += ["--add-dir", str(directory)]
        if model:
            command += ["--model", model]
    else:
        # Codex is allowed to edit files in cwd only (workspace-write sandbox).
        # --add-dir isn't passed: writable permission must not extend to the
        # bundled skills or upstream vendor source trees.
        command = [executable, "exec", "--sandbox", "workspace-write", "--ephemeral",
                   "--skip-git-repo-check"]
        if model:
            command += ["--model", model]
    # Always stream the prompt over stdin so manuscript-sized prompts do not
    # exceed argv length limits or expose the text in process listings.
    with tempfile.TemporaryDirectory(prefix="researchledger-writer-") as output_dir:
        output_file = Path(output_dir) / "last_message.txt"
        if provider == "codex":
            command += ["--output-last-message", str(output_file), "-"]
        try:
            done = subprocess.run(command, input=prompt, cwd=str(cwd), capture_output=True,
                                  text=True, encoding="utf-8", errors="replace", shell=False,
                                  timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            raise ValueError(f"{provider} writing session exceeded {timeout}s") from exc
        if done.returncode != 0:
            raise ValueError(f"{provider} writing session exited {done.returncode}: "
                             f"{(done.stderr or done.stdout)[-400:]}")
        if provider == "codex":
            if not output_file.is_file():
                raise ValueError("codex writing session omitted its expected output file")
            stdout = output_file.read_text(encoding="utf-8")
        else:
            stdout = done.stdout
        return {"stdout": stdout, "returncode": done.returncode,
                "command": command, "provider": provider}
