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

- 2026-11-02 (user asleep): read the user's Claude memory export (`D:\claude-memory-2026-11-01*.zip`: terse,
  wants finished deliverables, runs multi-prompt idea and review loops by hand, ChatGPT reviews → Claude Code fixes).
  Built **Research Loops** (`webapi/app/loops.py`, `/loops`, loop detail page, Approvals cards): Idea forge
  (attack ≥50 papers → Phase 10 score → redesign, server-checked references/scores, pass/plateau/max stop rules)
  and Review → fix → re-review (quote check, surgical-diff check, template guard, clean/plateau/final-check stop).
  **Standing instructions** (`prefs.py`, Settings) appended to every agent task. Autopilot routes idea/review-fix
  goals to loops. Test env moved to `webapi/tests/__init__.py` so any single test file uses a temp data dir
  (running `test_loops.py` alone once wrote test projects into the live DB; they were removed, nothing of the
  user's was touched). 79 tests pass. Demo loop `lop_27eb2060cce8` (review_fix on `paper/main_revised.tex` of the
  DeFi paper) was created and stopped before any work; "One more round" resumes it.

## Git
Work is committed on branch `feature/web-app-paper-studio` (commit 328c4e4, not pushed). Leave the user's own
uncommitted `Paper/`, zip and `__pycache__` changes alone; never stage them.

## Accepted improvement backlog (user approved 2026-11-02 01:30; build in this order)
The user said: use the many skills in `skills/`, `vendor/` and `D:\AutoResearch\academic-research-skills-offline`
freely; newer models can verify a lot themselves, so keep deterministic checks lightweight.

1. **Run experiments → real results.** Paper Studio stage "Run experiments" after Code: the agent (Claude app
   worker or claude.exe) runs `code/` in the project folder after the user approves, writes `results/<slot>.json`,
   updates `paper/experimental_log.md` values from those files, and records which run produced each value.
   The Write stage then uses measured values; untouched slots stay `\PFVAL`.
2. **Reference checking.** Backend checks each `paper/refs.bib` entry against Crossref (DOI) and arXiv (eprint)
   APIs, fills missing authors/year/venue, flags entries not found; show results on the Literature stage.
   Network failure must degrade gracefully (mark "not checked").
3. **Review ↔ revise loop.** Up to 3 rounds (Master Auto-Review Loop skill in
   `D:\AutoResearch\academic-research-skills-offline\3- paper-writing\Master_Auto_Review_Loop_SKILL.md`), stop when no
   VERIFIED major concern remains; show each round's concerns as resolved/open.
4. **Document editing.** Side-by-side LaTeX/PDF, select a paragraph → "revise this" request, compare old vs revised,
   one-click submission package zip (PDF, LaTeX, figures, bib, response letter).
5. **Journals and paper types.** Add IEEE, Elsevier, Springer, MDPI journal templates (generic LaTeX classes if the
   official ones are not on disk); add paper types *Thesis to paper* and *Revision & rebuttal* (upload paper + reviewer
   comments → revised paper + response letter).
6. **Bridge robustness.** Re-queue runs claimed by a worker that stopped polling (stale > 15 min); show worker
   busy/free in the sidebar.

For each item: add backend tests (`python -m pytest -q webapi/tests`), `npx tsc --noEmit` in `frontend/`, update
`docs/WEB_APP.md` and the progress log above, and commit to `feature/web-app-paper-studio` (no push).
- 2026-11-02 ~02:00: **Smart recipes** added (webapi/app/recipes.py, /do/[recipe], home 'Ready-made agents' + drop zone): 9 upload-and-Start agents (review, pre-submission check, ideas with Phase 10-13 prompts, write paper, match reference style, respond to reviewers, code, understand papers, slides) using vendor engines, offline zipped agents (unpacked to webapi_data/engines) and the prompt library D:\AutoResearch\AI-LAB\07_PROMPTS\PAPER AGENT. 39 tests pass. Not yet browser-checked or live-run.
- 2026-11-02 (4am run): **Item 1 done** — stage *Run experiments* after Code; `webapi/app/experiments.py` fills the experimental log from `results/*.json` on approval with provenance. 42 tests pass, tsc clean.
- 2026-11-02 (4am run): **Item 2 done** — `webapi/app/refcheck.py` + button on Literature stage; verified live against Crossref/arXiv on the Blockchain project's refs.bib copy (7 verified, 1 not found, 2 no id; user's file not changed). 46 tests pass, tsc clean.
- 2026-11-02 (4am run): **Item 3 done** — `webapi/app/review_loop.py`, rounds 2-3 from the Revise stage, stop rule computed from CSVs, panel on Revise. Revise stage now also requires `review/closure.csv` (older papers already past Revise need that file). 48 tests pass, tsc clean.
- 2026-11-02 (4am run): **Item 4 done** — `webapi/app/document_tools.py`, `frontend/components/PaperDocument.tsx`: compare, revise-one-passage proposals with explicit Apply, submission package zip. Side-by-side PDF preview is NOT built (compare is a text diff; PDFs open in the existing viewer). 52 tests pass, tsc clean.
- 2026-11-02 (4am run): **Item 5 done** — venues IEEE/Elsevier/Springer(LNCS)/MDPI (generic layout for MDPI; no official class on disk), paper types *Thesis to paper* and *Revision & rebuttal*, upload box on the paper page, reviewer-point coverage. 55 tests pass, tsc clean. Not live-run with the Claude app worker.
- 2026-11-02 (4am run): **Item 6 done** — stale-claim re-queue (15 min, max 2), claim tokens, `ping`, worker busy/free/offline in sidebar and Settings. Needs an API restart and a fresh `/rl-worker` session to take effect (old workers still work, without tokens). Not done: a server restart still fails queued runs (db.py) — consider keeping queued bridge runs. 58 tests pass, tsc clean.
- 2026-11-02 (4am run): Note: a read-only check of the live project imported the API module, and Store() start-up marks active runs failed. This closed run_3cf6fc1a2d2e (a Director run from the previous evening, "server restarted while run was active"). Never import webapi.app.main against the live data dir; use RL_WEB_DATA=<temp> for checks.
- 2026-11-02 morning: **Autopilot + Approvals** — `webapi/app/autopilot.py` (goal → paper/recipe/Director), Paper Studio autopilot (approve = next stage starts; experiments manual), `webapi/app/inbox.py` + `/inbox` page + sidebar badge, home box uses autopilot. 68 tests pass, tsc clean, Approvals page checked in the browser.
- 2026-11-02 morning: **End-to-end Autopilot run** on prj_6d0b1addd06f (DeFi whitepaper-figures paper) through the Claude app bridge: Literature→Method→Code→(manual) Experiments→Write→Review→Revise each started automatically after approval. Experiments measured 0/14 slots honestly (no dataset/model/annotations; found and fixed a real bug in evaluate.py). Paper compiled (main.pdf, main_revised.pdf, 4 pages); review 4 major + 4 minor, 7 resolved, mc8 (missing author lists) open; loop stop rule met. Revise awaits the user's final approval. Fixed inbox label: approve button no longer says it starts a manual stage.
