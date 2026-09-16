# Reconstructing Research Context

A lightweight version of this already runs automatically every turn: `hooks/inject_research_context.py`
(a `UserPromptSubmit` hook, plain Python, no model call) prints a compact status line — topic,
current stage, evidence/claim/decision/plan counts — before each response. That's deliberately terse.
This document is for the **deep** version: what the `research` skill (see
`../skills/research/SKILL.md`) reconstructs **by reading workspace files at the moment it's
invoked**, when the hook's one-liner isn't enough to act on. Treat it as a snapshot taken right now,
not a persistent fact — if a lot of the conversation has happened since you last read these files
(several turns, or the user mentions something that sounds newer than what you have in context),
re-read them rather than trusting a stale in-context summary.

Build these sections, in this order, **each one omitted entirely if it has nothing to show** (don't
print an empty header):

1. **Research project** — from `project.md`: topic, initial topic (only if it changed), domain,
   goal, open questions.
2. **Papers in workspace** (only if `papers/` has ≥1 paper) — active paper id (from
   `.active-paper` if present, else the only paper, else ask), then one line per paper: id, version,
   status, title.
3. **Current active paper excerpt** — the active paper's title, and either a relevant excerpt (if
   the user's request is clearly about writing/the manuscript) or just a pointer to
   `papers/<id>/paper.md` to read on demand — don't dump the whole manuscript into context by
   default.
4. **Plans** — one line per file in `plans/`: path, title, status.
5. **Research state** — from `research-state.md`: version, which of the 13 dimensions are
   established (non-empty), and the maturity table for the 6 maturity dimensions (only levels above
   `Unknown`) — point to the file for full text rather than copying its body.
6. **Evidence gaps** (only if any exist) — claims with no supporting evidence; claims with
   unaddressed contradicting evidence; evidence missing a raw-artifact reference.
7. **Open questions** — bulleted, from the state's Open Questions dimension.
8. **Active paper status** — version/status, sections with real content vs. total, claims with/
   without evidence, evidence actually cited in the manuscript vs. total, maturity summary, count of
   revision proposals awaiting review.
9. **Research outputs** (only if `outputs/` has any) — id/type/status/version/title per output, plus
   how many are still awaiting review.
10. **Current paper gaps** — top ~6 by priority from `gaps.md`, each with its suggested skill. State
    plainly that gaps only *suggest* what could be done — the user decides what to act on.
11. **Research process** — current stage (see the `research-process` skill): its label and what it
    produces, or "every stage has landed artifacts — no obvious missing step" if none. List which
    stages have landed and which haven't. Always add the disclaimer that this describes assets, not
    a required order to follow.
12. **Possibly relevant skills** — if the user's request maps clearly onto a skill category or
    contains keywords matching a specific skill's purpose, name up to ~6 candidates. This is
    navigation, not an execution order — if nothing matches clearly, it's fine to name none rather
    than force a guess.

## How to gather each piece

- `project.md`, `research-state.md`: read frontmatter + relevant sections directly.
- `plans/*.md`: read each file's frontmatter (`status`, `version`, `name`/title).
- `research/evidence/*.md`, `research/claims/*.md`: grep frontmatter fields (`supports:`,
  `contradicts:`, `raw_artifacts:`) to compute unsupported/contested claims and evidence lacking a
  raw-artifact reference — don't open every file's full body unless you need it.
- `papers/*/paper.md`, `metadata.md`, `gaps.md`: enumerate `papers/*/` and read each paper's
  `metadata.md` for the summary line; read `gaps.md` for the gap list.
- `outputs/**/metadata.md`: enumerate for the outputs list.
- Current research stage: check, in order, whether each stage's artifact exists (see the
  `research-process` skill's stage table) — the first stage whose artifact is missing is the current
  stage. This is a simple existence check per stage, not a scored/weighted computation.

## What NOT to do

- Don't try to keep this "live" — it's a point-in-time read, always cheap to redo.
- Don't copy full file bodies into your context unless the task actually needs them (e.g. don't
  paste the whole manuscript just to report its version number).
- Don't invent a dimension, stage, or gap that isn't actually backed by a file on disk.
