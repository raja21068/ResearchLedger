# Session handoff — ResearchLedger web app

Last updated: 2026-11-02 (night). Read this first in a new session.

## Where things are
- Web app: `webapi/` (FastAPI) + `frontend/` (Next.js). Start with `& .\start_web.ps1`.
  API on http://127.0.0.1:8000, GUI on http://localhost:3000. Full guide: `docs/WEB_APP.md`.
- Data (projects, chats, runs, files): `webapi_data/` (git-ignored). Each project's files are in
  `webapi_data/projects/<project id>/workspace/`.
- Python for the API: `C:\Users\SAM\AppData\Local\Programs\Python\Python310\python.exe` (conda `python` lacks packages).
- Tests: `python -m pytest -q webapi/tests` (30 passing), `cd frontend; npx tsc --noEmit`.
- Nothing has been committed to git yet.

## How agents run (important)
- Default executor is the **Claude app bridge**: open the Claude app → Code tab → folder
  `D:\AutoResearch\ResearchLedger` → type `/rl-worker`. That session takes website tasks and sends replies back.
- Standalone `claude.exe` is not logged in. A dead proxy (`127.0.0.1:15721`) was removed from
  `C:\Users\SAM\.claude\settings.json`; backup `settings.json.bak-proxy-20261102`.
  Paper Factory engine tools (researchctl S1–S5, Beihang Referee) still call claude.exe themselves.

## Built so far
Claude-style UI (sidebar with history, chat with `/` commands, collapsible Activity panel), Research Director
(plan → approve → run), Brainstorm with idea cards (verified live: project "Brainstorm: Blockchain + LLM + VLM"),
21 research tools, 84 skills, Research Memory, Results, Library, Settings (bridge status).

## Next (agreed with the user)
Paper Studio: guided stage path per paper (Idea → Literature → Method → Code & results → Write → Review),
using engines in `vendor/` and `skills/`. Progress on this is recorded below.

## Progress log
- 2026-11-02 night: memory saved; started Paper Studio.
- 2026-11-02 night: **Paper Studio built** (`webapi/app/paper_studio.py`, `frontend/app/paper/`,
  `frontend/app/projects/[id]/paper/`). Research-article and review-paper paths on vendor engines; approval
  gates; "Use this idea for a paper" on idea cards; warm palette from the GUI spec. 34 backend tests pass.
- Live run (via the Claude app bridge): project **"Brainstorm: Blockchain + LLM + VLM"** (`prj_6d0b1addd06f`) →
  paper from idea I2 *Checking DeFi contracts against the figures in their whitepapers*. Idea approved; Literature
  stage done (`paper/refs.bib` 10 verified refs, `paper/literature.md`) and **waiting for the user's approval**.

## Next steps
1. User reviews and approves Literature, then runs Method → Code → Write (each via `/rl-worker` in the Claude app).
2. Thesis-to-paper and revision/rebuttal paper types (planned, not built).
3. Commit the work to a branch when the user asks (nothing committed yet).
