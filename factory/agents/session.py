"""One agentic Claude Code session, run headless under your login.

`loop.AgentLoop` is for single JSON answers. Some steps need Claude Code to work like
it does in your terminal: read a directory of instructions, write files, fix them.
This runs `claude -p` in a working directory with an explicit tool allow-list and
returns when the session ends. Nothing here needs an API key.

The prompt goes on stdin (it can be long). `permission_mode="acceptEdits"` lets the
allowed file tools write without prompting; anything not in `tools` is refused.
"""
import shutil
import subprocess


def run_session(prompt, cwd, tools, add_dirs=(), permission_mode="acceptEdits", model=None,
                timeout=3600):
    executable = shutil.which("claude")
    if not executable:
        raise ValueError("claude CLI is not installed or not on PATH")
    command = [executable, "-p", "--output-format", "text", "--no-session-persistence",
               "--permission-mode", permission_mode, "--allowedTools", *tools]
    for directory in add_dirs:
        command += ["--add-dir", str(directory)]
    if model:
        command += ["--model", model]
    try:
        done = subprocess.run(command, input=prompt, cwd=str(cwd), capture_output=True,
                              text=True, encoding="utf-8", errors="replace", shell=False,
                              timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise ValueError(f"claude session exceeded {timeout}s") from exc
    if done.returncode != 0:
        raise ValueError(f"claude session exited {done.returncode}: "
                         f"{(done.stderr or done.stdout)[:400]}")
    return {"stdout": done.stdout, "returncode": done.returncode, "command": command}
