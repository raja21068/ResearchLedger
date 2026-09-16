# Plans

Path: `plans/<id>.md`, one file per plan. `<id>` is a kebab-case slug derived from the plan's name
(e.g. "Baseline robustness evaluation" -> `baseline-robustness-eval`). **Never name a plan by
sequence** — ids like `step1`, `plan-1`, `module3`, or anything matching `*-step-*` are rejected: a
plan is named by the capability/task it covers, not by its position in a pipeline.

Plans are the one asset type with **no dedicated schema-enforcing tool** in the original system —
they're just files, created and edited the same way you'd write any other file. Follow this shape by
convention; nothing else validates it.

```yaml
---
name: Baseline robustness evaluation
type: research-plan
status: ready
version: '1.1'                      # semantic label: 1.0 -> 1.1 (minor) -> 2.0 (major); bumped explicitly on a "revise"
source_skill: experiment-design      # which skill this plan was produced from, if any
paper: paper-2026-01
review_policy: review-required       # or: auto-execute
created_at: <ISO8601>
updated_at: <ISO8601>
---

# Plan: Baseline robustness evaluation

## Objective
<one-sentence goal>

## Context
### Research Problem
...
### Current Research State
...

## Research Questions
<optional>

## Execution Strategy
<how, this time through — describe the approach, not a rigid numbered pipeline>

## Expected Evidence
<what evidence this run must produce, and which claim(s) it targets>

## Expected Outputs
<optional>

## Constraints
<optional>

## Completion Criteria
<must correspond 1:1 with Expected Evidence — this is how you know the plan is done>

## User Notes
<space for the user's own additions — never overwrite this section>
```

## Lifecycle

Seven states; only these transitions are valid (anything else is a mistake, not a matter of style):

```text
draft     -> reviewed | ready | archived
reviewed  -> ready | draft | archived
ready     -> executing | draft | archived
executing -> completed | refined | ready | archived
completed -> refined | archived
refined   -> ready | executing | archived
archived  -> (terminal — no transitions out)
```

`review_policy: auto-execute` is the only way a `draft` plan may move straight to execution without
passing through `reviewed`/`ready` first. Track status via the frontmatter `status:` field.

## Versioning — two independent counters

Don't conflate these:

1. **`version`** (frontmatter) — a semantic label (`1.0 -> 1.1` minor, `-> 2.0` major), bumped
   explicitly whenever the plan is substantively revised.
2. **Snapshot history** — a separate sequential counter, one snapshot per meaningful edit, at
   `plans/history/<id>/v<NNN>.md` (`001`, `002`, … — *not* the semver value), each prefixed with a
   header `<!-- archived: <ISO> -- plan_version: <version> -->`. Skip writing a new snapshot if the
   content (header stripped) is identical to the last one.

Since there's no automatic interception of plan edits, **snapshot explicitly** at the two moments
that matter: right after a plan is finalized for review/execution, and right before a significant
revision overwrites its body. When in doubt, snapshot before you edit.

## Handing a plan off for execution

When a `ready`/`refined` plan (or a `draft` with `auto-execute`) is picked up to actually work on,
restate it as the frame for the work about to happen: the Objective, the full plan body, and a
closing reminder of the Completion Criteria / Expected Evidence — then do the work in the current
turn. There is no mechanism to "hand off" work to a separate future turn automatically; treat the
plan as the brief for what you're about to do right now, in this response.
