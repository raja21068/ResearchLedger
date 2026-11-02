# Claude Code instructions

Follow the contributor rules in [CODEX.md](CODEX.md).

## Running the web app

When the user asks to "run", "start" or "open" ResearchLedger (the website / GUI), run:

```powershell
& .\start_web.ps1
```

It starts the API (http://127.0.0.1:8000, `webapi/`) and the GUI (http://localhost:3000, `frontend/`)
in their own windows and opens the browser. The API launches the user's own Claude Code CLI for
model work, so it must be started from a normal terminal, not inherited from a parent Claude session
(the API strips inherited session variables anyway). Details: [docs/WEB_APP.md](docs/WEB_APP.md).

## Using ResearchLedger from this console

When the user asks how to use ResearchLedger, says they want to do research work (ideas, a paper, code, a
revision) without a specific instruction, or greets you in a new session here, offer the `/rl` menu — the
same seven numbered steps as the website (defined once in `webapi/app/steps.py`): 1 Literature · 2 Idea ·
3 Method and code · 4 Run experiments · 5 Write paper · 6 Review and revise · 7 Final check · 8 Guided paper (all
steps) · 0 Status. Run `/rl` and let them pick a number.
`/rl-status` shows what is running and waiting.

To let this Claude Code session do the website's agent work (no separate CLI login needed), the
user types `/rl-worker` (see `.claude/commands/rl-worker.md` and the bridge section of docs/WEB_APP.md).

Web app tests: `python -m pytest -q webapi/tests` (the workflow tests run real researchctl commands
without model calls).
