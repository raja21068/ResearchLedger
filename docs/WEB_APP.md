# ResearchLedger web app (local)

A browser GUI for the research engines in this repository. You type prompts in a chat; your
locally installed **Claude Code CLI** does the work inside the project's workspace folder; the
PDF and Word files it produces open in a tabbed panel beside the chat, and any file can be
opened in its own browser tab.

```
frontend/  Next.js + TypeScript + Tailwind   http://localhost:3000
webapi/    FastAPI (Python)                  http://127.0.0.1:8000/api/v1
webapi_data/  SQLite database + one workspace folder per project (git-ignored)
```

## Run it

Requirements: Python 3.10+, Node 20+, Claude Code installed **and logged in** (run `claude`
once in a normal terminal). Optional: MiKTeX or TeX Live for PDF compilation.

```bash
python -m pip install -r webapi/requirements.txt
```

```bash
python -m uvicorn webapi.app.main:app --host 127.0.0.1 --port 8000
```

In a second terminal:

```bash
cd frontend && npm install && npm run dev
```

Open http://localhost:3000 → **Projects → New project** → type a prompt.

Run the backend from a normal terminal. If it is started from inside a Claude Code session,
the server strips that session's routing/auth variables before launching the CLI, so the child
uses your own login.

## Quick start

```powershell
& .\start_web.ps1
```

Or ask Claude Code in this repository to "run ResearchLedger" ([CLAUDE.md](../CLAUDE.md) tells it how).

## One-click use: Autopilot and Approvals

- **New task box (home):** type a goal and/or attach files and press Enter. `webapi/app/autopilot.py` decides:
  a whole paper ("write a paper on…", "survey paper…", "thesis…", "reviewer comments…") → Paper Studio with
  Autopilot; a single job (one manuscript → review, slides, code, …) → the matching ready-made agent (or its
  upload page if a required file is missing); anything else → Research Director plan.
- **Autopilot (Paper Studio):** on by default (`RL_PAPER_AUTOPILOT=0` turns the default off). Creating a paper starts
  stage 1; approving a stage starts the next one. *Run experiments* never starts by itself. Switch per paper on
  the paper page.
- **Approvals (sidebar, with a badge):** `/inbox` lists every decision across projects — stages to approve
  (with the agent's summary and files), Director plans, experiments waiting for a click, steps that did not finish
  (Try again), and what is running now. `GET /api/v1/inbox`.

## Research Loops: the prompt rounds you used to type by hand

Built from how the user actually works (memory export + recurring prompts): review a paper in ChatGPT, paste
instructions into Claude Code, fix, recompile, review the PDF again; for ideas, "why is this not novel? search
50–100 papers" → "score it again" → "design it again" → repeat. `webapi/app/loops.py` runs those rounds until a
stop rule; the user only steers, approves the result, or asks for one more round. Page: **Research Loops**
(`/loops`, detail at `/projects/<id>/loops/<loop>`); finished, paused and failed loops also appear in Approvals.

| Loop | One round | Stops when |
| --- | --- | --- |
| **Idea forge** (`idea_forge`) | *attack* (≥50 recent papers → `competitors.csv`, `attack.md`, the user's Phase 11/13 prompts) → *score* (Phase 10 rubric /100 → `scorecard.json`, scorer reads only idea + attack) → *redesign* (`idea.md` + novelty matrix, Phase 12). Optional round 0 generates and ranks candidates when only a topic is given. | **pass**: total ≥ 75, novelty ≥ 14/20, no fatal flaw, evidence gate passed · **plateau**: < 3 points gained over two rounds · **max rounds** (4) |
| **Review → fix → re-review** (`review_fix`) | *review* (Beihang/Lean reviewer + verifier, the user's "Reviewer simulation" prompt → `concerns.csv`, `scores.json`; an optional pasted ChatGPT review is verified point by point) → *plan* (`fix_instructions.md`: the detailed MD for the coding agent) → *fix* (`<stem>_loop<id>_rN.tex` + compiled PDF, original untouched) | **clean**: a fresh review finds no verified major concern · final check after 3 fix rounds · **plateau**: majors do not go down over two rounds |

The server checks every move itself and never takes the agent's word for it:
- **References:** competitor rows must reach the paper count, ≥80% with DOI/arXiv; a seeded sample is looked up at
  Crossref/arXiv (`refcheck.check_entry`). One id that does not exist or names a different paper blocks a pass.
- **Scores:** criteria are clamped to the rubric maximums and the total is recomputed (a wrong claimed total is shown).
- **Review quotes:** a VERIFIED concern whose quoted passage is not in the .tex is downgraded to UNVERIFIED.
- **Surgical fixes:** a changed `\documentclass` rejects the move; the share of changed lines, new citation keys and
  keys missing from the .bib are recorded and shown as warnings.
- A rejected move is retried once with the reason; then the loop waits in Approvals (*Try again*).
- `report.md` in the loop folder holds the round table (numbers computed by the server).

Modes: *auto* (default; run to the stop rule, then the user accepts) or *step* (pause after every round). Notes added
with *Steer* go into the next move's prompt. Accepting an idea copies it to `ideas/final_idea_<loop>.md`.
The New task box routes "why is this idea not novel / attack / redesign / generate ideas" to Idea forge and
"review … fix" with a .tex attached to Review → fix. A background thread (`RL_LOOP_TICKER=0` turns it off)
advances loops every 3 s; opening a loop page also advances it.

API: `GET /api/v1/loop-types`, `GET|POST /api/v1/projects/{id}/loops`, `GET /api/v1/projects/{id}/loops/{loop}`,
`POST …/loops/{loop}/steer|continue|stop|retry|accept`.

**Standing instructions** (`webapi/app/prefs.py`, Settings → *Your standing instructions*): the instructions the
user repeats in every session (verify every reference, never invent citations/DOIs, search 50+ recent papers,
surgical edits, keep the template, finished deliverables, objective scoring, check everything again, plain
explanation) are appended to the agent's system instructions for every task (CLI and Claude app worker).
Stored in `webapi_data/preferences.json`; `GET|PUT /api/v1/preferences`, `POST /api/v1/preferences/reset`.

## Paper Studio (guided paper writing)

Sidebar → **Paper Studio**, or *Use this idea for a paper* on a Brainstorm idea card. One stage path per paper
(`webapi/app/paper_studio.py`); state in the project's `paper/studio.json`.

| Paper type | Stages |
| --- | --- |
| Research article | Idea → Literature → Method & experiment plan → Code → Run experiments → Write paper → Review → Revise |
| Review (survey) paper | Scope & protocol → Search & screening → Taxonomy & synthesis → Write survey → Review → Revise |
| Thesis to paper | Read the thesis → Paper plan → References → Write paper → Review → Revise |
| Revision & rebuttal | Comments & triage → Response plan → Revise manuscript → Response letter |

Venues: generic journal, ICLR 2025, CVPR 2025, plus IEEE (`IEEEtran`), Elsevier (`elsarticle`), Springer (`llncs`) and MDPI. IEEEtran, elsarticle and llncs are installed with MiKTeX; the Springer Nature journal class and `mdpi.cls` are not, so MDPI uses a generic layout, and the agent is told to prefer an official class the user places in `paper/`.

*Thesis to paper* and *Revision & rebuttal* start from files you upload on the paper page (saved in `uploads/`; the first stage will not run without them). Thesis results enter as `results/<slot>.json` with `source: thesis` and the table/page, copied exactly from the thesis; the server collects them into the experimental log on approval, like measured results. The revision path shows how many reviewer points `review/closure.csv` marks resolved (computed from `review/comments.csv`).

Each stage tells the agent to read the user's own engines first, then the earlier stages' files, and must write
named outputs:
- Idea: `vendor/idea-generation/idea-discovery-v5` (SKILL.md, LOOP_PROTOCOL.md) + idea skills → `paper/idea.md`
- Literature: `skills/paper-orchestra-literature`, PaperOrchestra `literature_review_agent.py` → `paper/refs.bib`, `paper/literature.md`
- Method: research-method/experiment/evaluation/baseline/ablation skills → `paper/protocol.md`, `paper/experimental_log.md` (declared slots, values `TBD`)
- Code: PaperCompiler `3_architecting.py`, `4_contracting.py`, `5_engineering.py` as the recipe → `code/` (scripts write `results/<slot>.json`)
- Reference check (button on Literature / Search stages, `webapi/app/refcheck.py`): each `paper/refs.bib` entry with a DOI or arXiv id is looked up at Crossref / arXiv. Status per entry: verified, title mismatch, not found, no identifier, or not checked (network down). Only missing author/year/venue fields are filled, and only from a record whose title matches; the original is kept as `refs.bib.orig`; report in `paper/refcheck.json`. `POST /projects/{id}/paper/check-references`, `GET .../paper/references`.
- Run experiments: the agent runs `code/` (CLI executor gets `python`/`pip install` for this stage only), writes `results/<slot>.json` and `results/run_log.md`. On approval the server (`webapi/app/experiments.py`) copies each valid result into the `value` column of `paper/experimental_log.md` and records file, SHA-256 and run id in `results/provenance.json`; invalid, mismatched or undeclared files are reported and ignored; unmeasured slots stay `TBD`. `POST /projects/{id}/paper/collect-results` does the same on demand.
- Write: `skills/paper-orchestra*` + PaperOrchestra prompts + venue template (`vendor/paperorchestra/templates/iclr2025|cvpr2025`) → `paper/main.tex`, `paper/main.pdf`
- Review: Referee-Lean v2 core reviewer + independent verifier prompts → `review/review_report.md`, `review/concern_matrix.csv`
- Review ↔ revise loop (`webapi/app/review_loop.py`): Revise also writes `review/closure.csv` (id,status,evidence). After Revise is approved, *Run another review round* (max rounds 2 and 3, per Master Auto Review Loop skill) re-reviews the latest revision and writes `review/round_N/{concern_matrix,closure}.csv`, `paper/main_revised_rN.tex/.pdf`, `review/round_N/response_letter.md`. The loop stops when no VERIFIED major concern is open (computed from the CSVs) or after round 3; the Revise stage lists each concern as resolved/open. `POST /projects/{id}/paper/review-rounds`.
- Document tools (below the stage path, `webapi/app/document_tools.py`): *Compare* any two paper files (unified diff); *Revise one passage* (paste the exact passage + request → the agent writes a proposal `paper/edits/<id>.json`; you see before/after, warnings for new numbers, and click *Apply*, which replaces exactly that passage after saving a backup in `paper/edits/backups/`); *Build submission package* (`paper/package/submission_<time>.zip`: latest PDF + LaTeX, refs.bib, style files, figures, response letter, provenance, MANIFEST.json with SHA-256 and warnings about placeholders). Endpoints: `GET .../paper/compare`, `GET/POST .../paper/edits`, `POST .../paper/edits/{id}/apply`, `POST .../paper/package`.
- Revise: manuscript-revision + refine → `paper/main_revised.tex/.pdf`, `review/response_letter.md`

A stage is *Waiting for your approval* only when its run succeeded and all outputs exist; approving unlocks the next
stage. *Ask for changes* re-runs it with your feedback and re-locks later stages. Measured numbers enter the paper only
from `results/*.json`; otherwise `\PFVAL{slot}` placeholders stay visible.

## Where agents run: the Claude app bridge (default)

The website does not need its own Claude login. Agent tasks wait in a queue until a Claude Code
session in the **Claude app** picks them up:

1. Start the website (`& .\start_web.ps1`).
2. Claude app → **Code** tab → session in `D:\AutoResearch\ResearchLedger` → type **`/rl-worker`**.
   Leave that session open; it loops on `python webapi/bridge_cli.py next`.
3. Use the website. Each task appears in the Claude app session, runs there with the app's login and
   tools, writes files into the project folder, and the reply, checklist, steps and files come back
   to the website chat.

Robustness: each claimed task gets a claim token (`bridge_cli.py` stores and sends it automatically). A task whose
worker has been silent for 15 minutes (no step, todo, say or `ping`) goes back to the queue with a visible note; after two
re-queues it is marked failed. A late `done` from the old worker is refused (409, "STOP: ... went back to the queue").
`GET /bridge/status` reports `worker_state`: *busy* (a task is being worked on; the worker is not polling then),
*free* (polling) or *offline*; the sidebar shows Working / Ready / Not connected. For commands longer than 10 minutes the
worker runs `python webapi/bridge_cli.py ping RUN_ID`.

Settings → *Where agents run* switches between the Claude app bridge and `claude.exe` in the
background (which needs `claude auth login`). The Settings page and the chat show whether a worker is
connected. Paper Factory engine tools that call `claude.exe` themselves (S1–S5, Beihang Referee)
still need `claude.exe` to be logged in.

## Research Director (default chat mode)

A new chat starts with the **Research Director** (switch to *Direct chat* under the box). It answers
small questions itself; for goals that need tools it writes `director/plan_<chat>.json` and explains the
plan. Nothing runs until you press **Approve and run**. The executor then runs each step, one research
tool at a time, in the same chat (`webapi/app/director.py`), stopping at the first failure or when you
press Stop. Human-only gates (protocol lock) can never be planned.

The right-hand **Activity** panel (collapsible) shows the plan and each step's status, the agents
working now and their latest step, the current agent's checklist, and files produced in this chat.
The left panel lists the current project's documents.

## Claude-style layout and slash commands

- **Sidebar:** New chat, Search (filters chats), Brainstorm ideas, Projects, Tools & skills, Library,
  Research memory, Results; chat history grouped Today / Yesterday / Previous 7 days; settings at the bottom.
- **Chat box** (home page and every chat): Enter sends, Shift+Enter adds a line, `+` attaches files,
  `/` opens the command list. `/brainstorm Blockchain, LLM, VLM`, `/literature <topic>`, `/draft`, `/code`,
  `/analyze`, `/review`, `/thesis`, `/referee`, `/cite`, plus every skill by its name (`/grant-proposal …`).
  A command whose form needs more (e.g. a file) opens that form prefilled.
- **In a chat:** the agent's checklist (its TodoWrite plan) shows as a card, tool calls fold into one
  "Worked through N steps" line, and a Brainstorm run shows its idea cards inline.

## Home: one box for any task

The home page is a single prompt box. **Tools ▾** lists every research tool (opens its form) and
every **skill** found in the skill folders; picking a skill runs your task through it. `+` attaches
files, the project and model selectors sit in the box, and the chips below are shortcuts.

Skills are discovered from every unpacked `SKILL.md` under `D:\AutoResearch\academic-research-skills-offline`
and `skills/` (override with `RL_SKILL_ROOTS`, paths separated by `;`). `.claude/` worktrees and
"previous version" folders are skipped; `.zip`/`.skill` packages are counted but not used until unpacked.
A skill run copies the skill folder to the project's hidden `.skills/<id>/` and asks Claude Code to
follow it; steps that need Python, Gemini or Codex are listed for you to run yourself.

## Research tools

Each research tool is a form

Each tool is a form (options, *Upload file* / *From library*, **Generate**) defined in
`webapi/app/workflows.py`. Generate creates a run and opens the project, where you watch
progress live and the results open in the document panel.

| Section | Tool | Engine |
| --- | --- | --- |
| Discover | Idea generation | Paper Factory S1 (`researchctl run --to S1`) |
| Discover | Literature review, Research proposal, Research design & protocol | Claude Code task prompt |
| Analyze | Code generation, Data analysis (code is written, not executed) | Claude Code task prompt |
| Analyze | Run experiments (S4) | Paper Factory; needs Docker running |
| Manuscripts | Write manuscript, Thesis to manuscript, Academic language editing | Claude Code task prompt |
| Manuscripts | Paper Factory draft (S2), Idea → draft → review (S1–S3) | Paper Factory |
| Manuscripts | Run experiments (S4), Evidence-bound revision (S5) | Paper Factory; needs Docker running |
| Peer Review | Specialist review | Beihang Referee (`researchctl referee cycle --provider claude`) |
| Peer Review | Paper Factory review (S3) | Paper Factory |
| Peer Review | Quick four-reviewer review | Claude Code task prompt |
| Evidence | Citation verification | Claude Code task prompt |
| Evidence | Ledger report, Readiness audit, Integrity gates, Pipeline status | researchctl, no model calls |
| Evidence | Lock research protocol | researchctl, requires an approval checkbox |

Paper Factory tools use the project's workspace folder as the Factory project (`PAPERFACTORY_WORKSPACES`
points at the project's folder; the project id is `workspace`). The home page's 01–05 progress shows a
stage as Done only when its output file exists.

## Research Memory and Results

- **Research Memory** (`memory/research_memory.md` in each project): the research question and
  decisions you write, plus a run log the server appends after every run (tool, status, summary,
  files). Every Claude run is told to read it first and never edit it. Edit it on the Research Memory page.
- **Results**: lists files under `results/`, `4_code/`, `analysis/`, `5_refine/` and `code/outputs/`, and
  shows the measured `4_code/results.json` from S4 when it exists.

## Troubleshooting

`API Error: Unable to connect to API (ConnectionRefused)`: the Claude CLI itself cannot reach its API.
Check `~/.claude/settings.json`: an `env.ANTHROPIC_BASE_URL` pointing at a local proxy (for example
`http://127.0.0.1:15721`) requires that proxy to be running. Test with `claude -p "say OK"` in a terminal.

## How a prompt runs

1. `POST /api/v1/conversations/{id}/runs` stores the run (`queued`) and starts a worker thread.
2. The worker launches `claude -p --output-format stream-json --verbose` with the project
   workspace as its working directory, `--permission-mode acceptEdits`, an explicit tool
   allowlist and an appended system prompt (no invented results or citations; placeholders
   instead). The prompt goes over stdin. Follow-up prompts in the same chat pass `--resume`.
3. Every stream-json line becomes a stored event; the browser follows them over SSE
   (`GET /runs/{id}/events`, resumable with `Last-Event-ID`). Refreshing the page loses nothing.
4. When the CLI exits, files created or modified during the run are recorded with SHA-256
   hashes. A new `.pdf` or `.docx` opens automatically in the document panel.
5. The run ends `succeeded` only if the CLI exited 0 **and** reported a non-error result.
   Anything else is `failed`, with the CLI's message.

## Documents

| File | Panel view | Actions |
| --- | --- | --- |
| `.pdf` | Browser PDF viewer | Open in new tab, download |
| `.docx` | Server-side mammoth → HTML in a script-less sandboxed frame | Conversion notes shown |
| `.tex` | Source | **Compile PDF** (pdflatex + bibtex/biber, shell escape off) |
| `.md` | Rendered / source | **Export Word** (python-docx; tables and equations copied as text, with a warning) |

## Configuration (environment variables)

| Variable | Default | Purpose |
| --- | --- | --- |
| `RL_WEB_DATA` | `./webapi_data` | Database and project workspaces |
| `RL_CLAUDE_CMD` | `claude` on PATH | CLI command, JSON list form recommended |
| `RL_CLAUDE_MODEL` | CLI default | Default model alias |
| `RL_CLAUDE_ALLOWED_TOOLS` | see `webapi/app/config.py` | JSON list replacing the tool allowlist |
| `RL_RUN_TIMEOUT_S` | `3600` | Kill a run after this long |
| `RL_MAX_UPLOAD_MB` | `50` | Upload size limit |
| `RL_LOOP_TICKER` | `1` | `0` stops the background thread that advances research loops |
| `RL_PAPER_AUTOPILOT` | `1` | `0` makes new papers start with Autopilot off |
| `RL_FRONTEND_ORIGINS` | `http://localhost:3000,http://127.0.0.1:3000` | CORS origins |
| `NEXT_PUBLIC_API_URL` (frontend) | `http://127.0.0.1:8000` | Where the browser reaches the API |

## Security model and known limits

This is a **local, single-user** build (blueprint Phase 1–3). It is not ready to expose on a network.

- No login. The API accepts only loopback `Host` headers (DNS-rebinding guard), allows CORS only
  from the frontend origin, and rejects state-changing requests without the `x-rl-client`
  header, so other websites in your browser cannot drive it.
- The agent may Read/Write/Edit, search the web and run only `pdflatex`, `bibtex`, `biber` and
  `latexmk`. It cannot run other shell commands. `Read` is not path-restricted by the CLI, so the
  agent *could* read files outside the workspace if asked to; it is not given other projects'
  files automatically.
- Workspace paths are resolved server-side; `..`, absolute and drive paths are refused.
  Uploads are type- and size-checked and never overwrite: an earlier version is kept as `name.vN.ext`.
- Non-PDF files are served with `Content-Security-Policy: sandbox`; workspace HTML/SVG is served as text.
- Prompts and manuscripts are sent to Anthropic by the Claude Code CLI under your account. Do not
  use confidential manuscripts unless that is permitted.

Not implemented yet (shown as **Planned** in the sidebar): Research Studio workflows, Peer Review
Center (Referee Lean v2 / Beihang Referee adapters), Evidence Center views of the ledger,
authentication, Codex provider, Docker-isolated execution from the web.

## Tests

```bash
python -m pytest -q webapi/tests
```

The tests use `webapi/tests/fake_claude.py`, a scripted stand-in that emits the CLI's
stream-json shapes; they make no model calls.
