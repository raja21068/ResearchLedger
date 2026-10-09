"""Subscription-authenticated transport for PaperOrchestra model calls.

LOCAL ADDITION -- not upstream PaperOrchestra. This file is added by Paper Factory
so the five writing agents run under the user's Codex or Claude Code login instead
of a provider API key. `utils/gemini_utils.py` and `utils/openai_utils.py` call
`configured_backend()` at module init and again per call, so when
PAPER_ORCHESTRA_BACKEND is set no provider client is ever constructed and no key
is read. Recorded in registry/tools/paperorchestra/tool_manifest.json.

The transport itself is deliberately thin: the generate-validate-repair loop lives
in `factory.agents.loop`, which is tested in our own suite. PaperOrchestra's
parsers are strict -- `parse_gemini_json_results` rejects a response that wraps
its JSON in prose, which is exactly what a chat-shaped model does on the first
attempt -- so a single call that raises on the first parser rejection wastes most
of what the loop is for. Here a rejection becomes the next turn's instruction.

If `factory` is not importable (someone ran the upstream CLI directly, without
PYTHONPATH), this falls back to a self-contained single-shot call rather than
failing, and says so in the returned record.
"""
import json
import os
import pathlib
import shutil
import subprocess
import tempfile


MAX_TURNS = int(os.environ.get("PAPER_ORCHESTRA_CLI_TURNS", "3"))


def configured_backend():
    return os.environ.get("PAPER_ORCHESTRA_BACKEND", "").strip().lower()


def _working_dir():
    return pathlib.Path(
        os.environ.get("PAPER_ORCHESTRA_WORKDIR", os.getcwd())).resolve()


def _timeout(explicit=None):
    return int(explicit or os.environ.get("PAPER_ORCHESTRA_CLI_TIMEOUT", "1800"))


def _login_state(backend, executable):
    """Distinguish 'not installed' from 'installed but not logged in'.

    Without this the first failure surfaces as an opaque non-zero exit in the
    middle of a writing run, and the remedy -- one login command -- is not
    obvious from the message.
    """
    command = ([executable, "login", "status"] if backend == "codex"
               else [executable, "auth", "status"])
    try:
        completed = subprocess.run(command, capture_output=True, text=True,
                                   encoding="utf-8", errors="replace", shell=False,
                                   timeout=60)
    except (subprocess.SubprocessError, OSError) as exc:
        return False, f"could not query {backend} login state: {exc}"
    try:
        payload = json.loads(completed.stdout)
        if payload.get("loggedIn"):
            return True, payload.get("authMethod", "subscription/oauth")
    except (json.JSONDecodeError, AttributeError):
        if "Logged in" in (completed.stdout + completed.stderr):
            return True, "subscription/oauth"
    return False, (
        f"{backend} CLI is installed but not logged in. Run "
        f"`{backend} {'login' if backend == 'codex' else '/login'}` once; "
        f"no API key is required.")


def _build_command(backend, executable, prompt, images, working_dir):
    if backend == "codex":
        handle = tempfile.NamedTemporaryFile(suffix=".txt", delete=False)
        handle.close()
        output = pathlib.Path(handle.name)
        command = [executable, "exec", "--sandbox", "read-only", "--ephemeral",
                   "--skip-git-repo-check", "--output-last-message", str(output),
                   "-C", str(working_dir)]
        for image in images or []:
            command.extend(["--image", str(pathlib.Path(image).resolve())])
        command.append(prompt)
        return command, output
    # Claude Code. `plan` is read-only: the writer must not edit the workspace,
    # and leaving edit tools enabled during a writing pass is how a manuscript
    # ends up with a number nobody put in the ledger. Read remains available so
    # the agent can open the figures it is asked to describe.
    command = [executable, "-p", "--permission-mode", "plan",
               "--no-session-persistence", "--output-format", "text",
               "--disallowedTools", "Bash", "Write", "Edit", "NotebookEdit",
               "--add-dir", str(working_dir)]
    model = os.environ.get("PAPER_ORCHESTRA_CLI_MODEL")
    if model:
        command += ["--model", model]
    command.append(prompt)
    return command, None


def _invoke(backend, executable, prompt, images, working_dir, timeout):
    command, output = _build_command(backend, executable, prompt, images, working_dir)
    completed = subprocess.run(command, cwd=str(working_dir), capture_output=True,
                               text=True, encoding="utf-8", errors="replace",
                               shell=False, timeout=timeout)
    if output is not None:
        try:
            raw = output.read_text(encoding="utf-8")
        finally:
            output.unlink(missing_ok=True)
    else:
        raw = completed.stdout
    if completed.returncode != 0:
        raise ValueError(
            f"{backend} CLI failed: {(completed.stderr or completed.stdout)[:600]}")
    return raw


def call_agent_cli(prompt, result_parsing_func, check_parsed_response_not_none=True,
                   system_prompt=None, images=None, timeout=None):
    """One model call, retried with the parser's own complaint as feedback."""
    backend = configured_backend()
    if backend not in {"codex", "claude"}:
        raise ValueError("PAPER_ORCHESTRA_BACKEND must be codex or claude")
    executable = shutil.which(backend)
    if not executable:
        raise ValueError(
            f"{backend} CLI is not installed. Install it and log in; no API key "
            f"is required for the Paper Factory writing path.")
    logged_in, detail = _login_state(backend, executable)
    if not logged_in:
        raise ValueError(detail)

    working_dir = _working_dir()
    timeout = _timeout(timeout)
    base = ((system_prompt + "\n\n") if system_prompt else "") + prompt
    base += ("\n\nReturn only the requested response format, with no preamble and no "
             "closing commentary. Do not execute generated research code, and do not "
             "invent citations, numbers, or empirical results: every value you report "
             "must already appear in the material you were given.")
    if backend == "claude" and images:
        base += ("\n\nThe following image files are available; read them if you need "
                 "their contents:\n" + "\n".join(str(pathlib.Path(i).resolve())
                                                 for i in images))

    attempts, current = [], base
    for turn in range(1, MAX_TURNS + 1):
        raw = _invoke(backend, executable, current, images, working_dir, timeout)
        parsed = result_parsing_func(raw)
        rejected = check_parsed_response_not_none and parsed is None
        attempts.append({"turn": turn, "chars": len(raw), "accepted": not rejected})
        if not rejected:
            return {"raw_response": raw, "parsed_response": parsed,
                    "transport": backend, "authentication": "subscription/oauth",
                    "turns": turn, "attempts": attempts}
        # The parser is the only thing that knows why it refused, and all it can
        # say is "not the requested shape". That is still a far more useful next
        # instruction than re-sending the identical prompt.
        current = (
            base + "\n\n---\nYour previous response could not be parsed into the "
            "requested format. Return the same content again as strictly valid "
            "output in that exact format, with no surrounding text, no markdown "
            "fences, and no explanation.")
    raise ValueError(
        f"PaperOrchestra parser rejected {backend} output on all {MAX_TURNS} attempts; "
        f"last response began: {raw[:400]}")
