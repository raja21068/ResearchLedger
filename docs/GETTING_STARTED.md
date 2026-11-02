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

---

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
