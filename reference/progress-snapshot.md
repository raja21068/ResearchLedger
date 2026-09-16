# Research Progress Snapshot

Print this at the end of any `/research` turn that touched the workspace (skip it for a turn that
was pure discussion with no file changes). Everything in it is **computed from disk, never from
what was said in conversation** — that's the entire point: it's a check against reality, not a
recap of the chat.

## A. Current state (always computable)

1. **Maturity bars.** For each of the 6 maturity dimensions (`Problem, Knowledge, Innovation,
   Method, Experiment, Evidence` — read from `research-state.md` frontmatter,
   `maturity_<dimension>`), render a 20-character bar: `Unknown`=0/20 filled, `Weak`=5/20,
   `Emerging`=10/20, `Strong`=15/20, `Established`=20/20 (`█` filled, `░` empty).
2. **Overall** = the mean of the 6 maturity values (as the same 0/.25/.5/.75/1 scale), shown as a
   percentage and **explicitly labeled as level-derived, not a measured precision number** — never
   present it as if it were an exact metric.
3. **Counts**, all real (never estimated): evidence total / settled (`supported`+`verified`) / with
   a raw-artifact reference; claims total / supported (>=1 evidence); decisions; plans total /
   ready-or-refined; open questions (bullet count under the state's "Open Questions" dimension);
   outputs; whether `papers/<id>/paper.md` exists for the active paper.
4. **Current stage** — see the `research-process` skill: the first stage (in its default or
   user-customized order) whose signal/artifact is missing. If every stage's artifact already
   exists, there is no "current stage" — the project is in open-ended continued research, not a
   fixed end state; say so explicitly rather than leaving this blank.

## B. What changed this turn

If you took an "A" snapshot at the *start* of this turn (recommended whenever you expect to modify
several files), diff it against the end-of-turn snapshot: per-dimension maturity changes
(`from -> to`), and per-count deltas (list only the non-zero ones). If nothing changed, say so
plainly — a quiet, no-op turn is a normal and fine outcome, not a failure to report.

## C. What's needed next

1. The current stage's "produces" description (from the `research-process` skill), or "all stages
   have landed assets" if there is no current stage.
2. Counts worth surfacing: unsupported claims (`claims total - claims supported`), evidence missing
   a raw-artifact reference (a provenance gap worth closing), and the open-question count.
3. **Advance judgment** — apply these checks in order, stop at the first that matches:
   1. **Blocked** — any research question in `project.md` literally contains `[blocking]` (or its
      Chinese equivalent `（阻塞项）`/`(阻塞项)`) -> report that question as needing a user decision.
   2. **Stalled** — you've now had 2+ consecutive turns with zero growth across
      evidence/claims/decisions/plans/outputs/paper existence -> say progress has stalled and
      suggest a concrete unstick action.
   3. **Direction unresolved** — 2+ plans sitting in `status: draft` and no decision in
      `research/decisions/` with a status starting with `decided` -> flag that a direction decision
      is overdue.
   4. **Fully mature** — no current stage from A.4 (nothing structurally missing) -> ask the user
      what they want to pursue next rather than inventing a task.
   5. **Clear** (default/else) — state the current stage's "produces" text as the obvious next step.

## Rendering

Print this as one Markdown block: a one-line summary (e.g. "Progress: 62% (evidence up, method
unchanged) — next: run baseline experiments"), then the maturity bars, a short "this turn" bullet
list (or "no changes"), a short "current gaps" bullet list, and the advance verdict from C.3. There
is no separate UI panel to fill — the Markdown text you print in the response **is** the snapshot.

## Self-continuation (bounded, in-turn only)

If the advance verdict is **clear**, it's fine to keep working within the *same* response toward the
next step rather than stopping to ask — but cap this at roughly 3 self-directed continuations before
pausing to report progress and hand control back. There is no mechanism to silently continue into a
*new* turn the user didn't ask for — never fabricate a "continuing automatically" turn; only
continue within the response you're currently producing.
