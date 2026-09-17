---
name: research
description: "Open, inspect, or continue the ResearchLedger research project in the current workspace. Use when the user runs /research, asks what stage their research/paper is at, wants to start a new research project, asks to continue or advance their research, or asks to export/review the research-methods library. This is the single entry point for ResearchLedger's research-operating-system workflow (project definition, evidence/claims/decisions, plans, papers, outputs)."
argument-hint: "[research topic, question, or blank for status]"
---

# Research

ResearchLedger's single entry point: open, inspect, or continue a long-running research project that
lives as plain files in the current workspace (the directory Claude Code is running in — see
[workspace-layout.md](../../reference/workspace-layout.md)). There is no fixed pipeline and no other
command — natural language plus the 53 methodology skills in this plugin cover everything from
topic framing through paper writing and submission audit.

## Procedure

Run this every time the skill is invoked, in order:

### 1. Resolve the workspace

The research root is the current working directory. A directory counts as an existing research
project if `project.md` or `research-state.md` already exists at its root.

### 2. Branch on the request

**A. No argument / a bare status request** (e.g. "what's the status", "/research" with nothing
after it) → go to **Status view** below, then stop.

**B. "Export research methods" / "export methods library"** → go to **Export skills** below, then
stop.

**C. Anything else** → go to **Bootstrap or continue** below.

## Status view

If no `project.md` exists yet:

> This workspace isn't a research project yet. Start one with `/research <your topic>`.

Otherwise report, reading straight from disk (never from memory of earlier turns):

- Topic (and initial topic, only if it has since changed), domain, goal, open questions — from
  `project.md`.
- Plans: for each file in `plans/`, its path, status, version, title — or "no plans yet; describe
  what you want to do and one will be drafted." If any plan is `draft`/`reviewed`, note that editing
  the file (or just continuing) will move it forward.
- Skill count (53 built in, spanning topic understanding through paper writing and submission audit — plus any the user added).
- Evidence/claim/decision/run counts and integrity status — run `Bash researchledger report` (if
  `research/runs/` exists) rather than re-deriving these by reading files by hand; it's the
  mechanically checked source, not an approximation. Surface any errors/warnings it reports.
- Current research stage and what's needed next — see
  [progress-snapshot.md](../../reference/progress-snapshot.md) §A/§C, or just the `research-process`
  skill if a full snapshot isn't warranted for a plain status check.
- Close with: "Continue with natural language — e.g. 'analyze the direction', 'design the
  experiment', 're-check the baseline claim.' There's no fixed step list; you decide what's next."

## Export skills

Glob `${CLAUDE_PLUGIN_ROOT}/skills/*/SKILL.md` (every skill except this one), and for each one read
its frontmatter `description` and its `## Purpose` section. Write a consolidated
`research/methods-export.md`:

- A header with the export timestamp and totals (skill count, category count derived from each
  skill's `> Ported from the ConvFusion research-skill library (category: ...)` provenance line).
- Grouped by category, each skill listed as `### <name> — <human title>` with its Purpose paragraph.
- If the user asked for a **full** export (they said "full" / "complete"), include each skill's
  entire body instead of just Purpose.

Reply with the file path, the skill/category counts, and a one-line reminder that a skill is
customized by editing its `SKILL.md` directly (see **Customizing a skill**, below) — there's no
separate override-file mechanism to know about.

## Bootstrap or continue

**If `project.md` does not exist yet** (new project):

1. Create the core directories: `plans/`, `research/evidence/`, `research/claims/`,
   `research/decisions/`, `research/state-history/` (see
   [workspace-layout.md](../../reference/workspace-layout.md) — don't create `papers/`, `outputs/`,
   `experiments/`, or `attachments/` yet, they're created on demand). Also run
   `Bash researchledger init` so the run ledger (`research/runs/`, `.researchledger/index.json`) is
   ready before any experiment happens — see [run-ledger.md](../../reference/run-ledger.md). If the
   command isn't found, the CLI hasn't been installed yet (`pip install -e .` from the plugin root);
   note that to the user rather than silently skipping it.
2. Write `project.md` with the given text as the topic (see
   [research-assets.md](../../reference/research-assets.md) for the exact schema). Don't create
   `research-state.md` yet — wait until there's a real first dimension to write into it.
3. Frame the work to yourself as: *this is a long-running research project, not a one-shot answer.*
   Decide what's actually most useful right now — clarifying the question, a literature scan, a
   first experiment plan, whatever fits — there's no required first step and no stage order to
   follow. If real execution is involved (writing code, running experiments, processing data), draft
   it as a plan under `plans/` first (see [plans.md](../../reference/plans.md)) so the user can look
   it over before it runs.
4. Do that work now, in this same turn — don't wait for a follow-up message to "confirm" starting.
5. Tell the user the project was created, where `project.md` lives, and what you just did.

**If `project.md` already exists** (continuing):

1. Reconstruct Research Context by reading the workspace — follow
   [research-context.md](../../reference/research-context.md) — and skip anything not relevant to
   the current request rather than dumping the entire workspace into context.
2. Treat the text after `/research` as the user's actual intent for this turn (this covers
   status-flavored questions too, like "what stage are we at" — answer those from the Research
   Process section of the context you just built, not with a canned reply).
3. Decide what the request needs and do it, pulling in whichever of the 53 skills apply — read a
   skill's `SKILL.md` before following its method, don't wing it from the title alone. If the work
   needs real execution, write or update a plan under `plans/` first so the user can refine it before
   it runs; when it does run, execute it via `Bash researchledger run -- <command>`, not a bare
   shell command — see [run-ledger.md](../../reference/run-ledger.md) and the
   `reproducible-implementation-spec` / `evidence-assessment` skills for what that buys you (an
   immutable, hashed, re-verifiable record instead of a claim you'd otherwise have to take on faith).
4. If anything in `plans/*.md` looks like it changed since you last saw it and wasn't snapshotted,
   snapshot it now (see [plans.md](../../reference/plans.md)) before editing further.

### After either branch: print a progress snapshot

If this turn touched any workspace file, close with a Research Progress Snapshot — see
[progress-snapshot.md](../../reference/progress-snapshot.md). Skip it for a turn that was pure
discussion with no file changes.

## Customizing a skill

There's no separate override-file system to learn. To change how a skill behaves, edit its
`SKILL.md` (or its `reference.md`, if it has one) directly — either in this plugin's own directory,
or by forking the plugin. Your edit takes effect immediately, with no merge step and no settings UI.

## What's deliberately not here

Some parts of the original system depend on a plugin runtime with in-memory session state and a
native settings UI, neither of which exist in Claude Code. Rather than half-port these, they're
simplified to what Claude Code can actually do on its own:

- **Per-turn context injection is lightweight, not deep.** The plugin's `UserPromptSubmit` hook
  (`hooks/inject_research_context.py`) auto-prints a compact status block every turn — topic,
  evidence/claim counts by status, run count, open integrity issues — with no model call involved
  and no prescribed "current stage" (a fixed stage table would contradict this skill's own "no
  fixed pipeline" design; see [run-ledger.md](../../reference/run-ledger.md#the-cached-index)). It
  is intentionally terse. This skill is what does the *deep* read (full plan list, gaps, paper
  status, skill suggestions) — invoke it when the lightweight hook line isn't enough context to act
  on.
- **No cross-turn auto-continuation.** Self-continuing within one response (capped at ~3 steps, see
  `progress-snapshot.md`) is fine; silently injecting a whole new turn the user never asked for is
  not attempted.
- **No settings UI, no RPC.** Configuration is: edit a file. That's it.
