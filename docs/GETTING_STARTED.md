# Getting started — ResearchLedger on your own computer

For a new user on Windows 10/11. About 20 minutes the first time, one double-click after that.

---

## 1. What you need

| Install | Why | Where |
|---|---|---|
| **Claude desktop app** (Pro or Max plan), signed in | does the AI work | claude.ai/download |
| **Python 3.10 or newer** — tick *Add python.exe to PATH* | runs the server | python.org/downloads |
| **Node.js 20 LTS or newer** | runs the website | nodejs.org |
| **Git** (or just download the ZIP, step 2) | gets the code | git-scm.com |
| **MiKTeX** (optional) | compiles LaTeX papers to PDF | miktex.org |

Check in PowerShell: `python --version`, `node --version`.

---

## 2. Get the code

**Option A — Git**

```powershell
cd D:\
git clone https://github.com/raja21068/ResearchLedger.git
cd ResearchLedger
git checkout feature/web-app-paper-studio
```

(The website lives on the `feature/web-app-paper-studio` branch until it is merged into `main`.)

**Option B — ZIP**

1. On the GitHub page choose **Code → Download ZIP**.
2. Right-click the ZIP → **Extract All…** → choose a short folder, e.g. `D:\ResearchLedger`.
3. Open the extracted folder (the one that contains `start_web.ps1`).

Already inside the repository (`vendor\` and `skills\`): Idea Discovery v5, PaperOrchestra, the Beihang referee,
PaperCompiler and the literature, revision and research skills. That is enough for every step.

A few extra engines come from a separate **offline skills pack** (paper-writing agent V2, research-code agent V4, the
auto-review loop, the slides skill). If you have that folder, point to it in step 8; its zipped engines are unpacked
automatically the first time they are used. Without it, those steps still run, with the built-in engines only.

---

## 3. Start the website

Open PowerShell **in the ResearchLedger folder** (in Explorer: click the address bar, type `powershell`, Enter) and run:

```powershell
powershell -ExecutionPolicy Bypass -File .\start_web.ps1
```

The first time it installs the Python and website packages (a few minutes). Two windows open (the server and the
website) and your browser opens **http://localhost:3000**. Keep the two windows open while you work.

Next time: run the same line again.

---

## 4. Connect Claude

The website gives the AI work to your Claude desktop app. Connect it once per working session:

1. Open the **Claude desktop app** → **Code** tab.
2. Start a session in your ResearchLedger folder (e.g. `D:\ResearchLedger`).
3. Type **`/rl-worker`** and press Enter. Leave that session open.

The website's sidebar now says **Claude app ready**. Until then a yellow bar says *Claude isn't connected* and shows
these steps.

---

## 5. (Optional) Use it from the Claude console in any folder

```powershell
powershell -ExecutionPolicy Bypass -File .\install_console.ps1
```

Then, in a new Claude Code session in any folder, type **`/rl`** for the menu. The console does the AI work itself,
so you do not need `/rl-worker` when you work this way.

---

## 6. Your first task

### On the website

The home page has one box and the seven steps:

```
 1. Literature        PDFs, a zip, or a topic        → summary and research-gap table
 2. Idea              a topic or your idea           → an idea scored /100 after a 50+ paper search
 3. Method and code   your idea or method            → experiment plan and runnable code
 4. Run experiments   what to test                   → measured results (runs only after your click)
 5. Write paper       idea and results               → LaTeX paper and PDF
 6. Review and revise your .tex (+ any review)       → fixed paper, re-reviewed until clean
 7. Final check       your .tex                      → ready / not ready
 8. Guided paper      an idea or topic               → steps 1 → 7 in order, you approve each one
```

1. Click a step, e.g. **2. Idea**.
2. Drop files (a **.zip** of your paper folder is fine — it is unpacked for you) or paste text (a topic, your idea, a
   ChatGPT review…).
3. *Keep it in*: **Just this once** for a one-off job, or one of your papers.
4. Press **Start**.
5. When it finishes you see **Your result** (Open / Download) and **Next step →**.

Anything that needs you — approve, continue, try again — appears under **Decisions** in the sidebar. Each paper has an
overview page (click it in the sidebar): where it stands, what needs you, its loops and documents.

### In the console

```
/rl                                   the menu
/rl 2 graph neural networks for drug–target interaction on a laptop
/rl 6 D:\papers\my_draft.zip          review and fix a paper
/rl-status                            what is running and what waits for you
```

---

## 7. Where your files are

Every job has its own folder: `webapi_data\projects\<id>\workspace\` inside ResearchLedger. Uploads go to
`uploads\`, results to `results\`, loops to `loops\`. The website's **Open / Download** buttons point there.

**Nothing gets overwritten for good.** Every time you upload a file, or an agent or an experiment changes it, the old
content is kept. Open the file and click **History** to see each version (who changed it, and when), view an old one,
or **Restore** it. Restoring adds a new version, so you can always undo it. The saved copies are in
`webapi_data\objects\`; don't edit that folder by hand.

- **Compare:** in History, see what changed between an old version and the file now.
- **Rename:** move or rename a file; its history goes with it.
- **Trash:** deleted files are listed on the project's **Trash** page, ready to bring back.
- **Backups:** the database is copied and checked every day, and the last 14 copies are kept in
  `webapi_dataackups\`. **Settings → Backups and safety check** has *Back up now* and *Check everything*.
  To restore a backup, stop the server and copy the backup over `webapi_data
esearchledger_web.sqlite3`.

---

**Experiments.** A project's **Experiment records** page (button on the project page, or *Experiments* under the
project in the sidebar) lists every run, and what it started from:
- fingerprints of `code/` and `data/`;
- the Python version and package versions;
- the commands, their exit codes, logs and measured values.

Experiments are shown as a tree under the idea or loop they came from. While a run is going, you see each job's
progress and a live log. Tick two runs and click **Compare** to see which values, files or package versions changed.
**Repeat** runs the same commands again as a new, separate record and leaves your project's results as they were,
so you can check that a result reproduces. Each run's receipt is kept in `results/receipts/`.

**Evidence.** A project's **Evidence** page is its ResearchLedger:
- **Sealed runs (R####):** every experiment run with measured values, recorded tamper-evidently and marked "not
  independently reproduced".
- **Evidence (E###):** each one starts as *observed* (recorded by a run, not reviewed). Only you change that: mark
  it *checked* (you reviewed it), *verified* (confirmed, e.g. a repeat gave the same values) or *invalid*, and give
  a short reason that is kept with it.
- **Claims (C###):** pre-registered experiments become claims automatically; you can add your own. A claim's status
  (hypothesis, provisional, supported, contradicted, withdrawn) is worked out by the ledger from its evidence and is
  never set by hand.

**Trace** shows the full chain from claim to evidence to run. These checks support your judgment; they are not
proof of correctness or publication readiness.

**Independent review by another model.** On the paper page, **Independent review by another model** builds a
packet (a zip with the manuscript, an evidence summary and the Referee-Lean reviewer prompt, plus the exact answer
format). Take it to a different tool, such as a ChatGPT temporary chat, and paste its table back. ResearchLedger keeps
a concern as **verified** only if its quote is really in the manuscript; the rest are shown but never acted on. One
click sends the verified concerns to the Revise stage. Nothing is sent anywhere from the website.

**Plan lock and the draft before coding.** For a research article:
- When you approve the *Method & experiment plan*, the protocol and the declared result slots are **frozen**. If
  either changes later, nothing after the Method stage can continue until you record an **amendment** (a reason, and
  which results it affects) and approve it, or restore the locked protocol. The locked copies are kept in
  `paper/locked/` and never overwritten. Papers approved before this existed show a **Lock the approved plan now**
  button.
- A new stage, **Draft before coding**, comes right after the plan. It writes the introduction, related work,
  methods, planned figure specifications and a discussion framework, with **no results, no conclusion and no
  findings in the abstract**. The empty result tables come from the declared slots and every cell says *Pending*.
  The paper is then built from this draft once real results exist.

**Evidence panel for manuscripts.** Open any `.tex` file and an **Evidence** panel appears beside it. It lists the
numbers in the tables and abstract and says where each comes from:
- **backed:** matches a measured result whose evidence you checked or verified;
- **recorded:** matches a recorded run, still unreviewed;
- **measured:** matches a results file with no recorded run;
- **untraced:** matches no measured result. Planned values such as thresholds appear here and are fine; a number
  that claims a finding is worth checking.

It also lists placeholders (TBD, `[RESULT: …]`), results that were measured but never used, and how many sources and
sections the paper has. It shows where numbers come from; it does not prove they are correct.

**Memory.** The **Memory** page (left sidebar) lists what earlier work found, by kind:
- **Failures:** ideas that did not pass scoring, and pre-registered experiments that were not supported.
- **Decisions, experiment results, strategies and literature notes.**

Finished idea rounds and experiments are recorded automatically, with links to their files. **Reviewer findings** are too: a concern from a review round becomes a
memory only if it is marked VERIFIED and its quote is really in the manuscript that was reviewed. Unverified comments
stay out. Once the concern is resolved, the memory is replaced by a *lesson* that records how it was fixed, and says
whether the fix text was found in the revised manuscript or only reported by the agent. Agents read the
active memories before every task (`memory/remembered.md`), so they do not repeat a failed direction. When an agent
suggests something worth remembering, it appears in **Decisions** as *Remember this / Reject*. To fix a memory,
click **Correct**: the old version is kept and marked as replaced. Your own free-form notes are under
**Memory → Project notes**.

## 8. Your own prompts and the offline skills pack (optional)

If you have a personal prompt library (e.g. *2-Phase 10 Idea Scorecard.txt*, *8. Reviewer Simulation.txt*) or the
offline skills pack, tell ResearchLedger where they are, then close and restart the website:

```powershell
setx RL_PROMPT_LIBRARY "D:\path\to\your\prompt folder"
setx RL_OFFLINE_SKILLS "D:\path\to\academic-research-skills-offline"
```

Without them everything still works with the built-in engines.

---

## 9. Stop

Close the two PowerShell windows (server and website). Your projects stay in `webapi_data\`.

---

## Troubleshooting

| You see | Do this |
|---|---|
| *Claude isn't connected* bar | Step 4: `/rl-worker` in a Claude Code session, or use `/rl` in the console |
| *The ResearchLedger server isn't running* | Run step 3 again |
| `running scripts is disabled on this system` | Use the `powershell -ExecutionPolicy Bypass -File …` line exactly as shown |
| `python` / `npm` not found | Reinstall Python with *Add to PATH* ticked / install Node.js, then open a new PowerShell |
| Port 3000 or 8000 already in use | Close the old server/website windows, then start again |
| PDF not produced | Install MiKTeX (step 1) and let it install missing packages when asked |
| `/rl` not offered in Claude | Run step 5, then open a **new** Claude Code session |
