# Research Assets: project.md, research-state.md, evidence, claims, decisions

This is the schema reference for every structured research-asset file ConvFusion skills read and
write. Follow it exactly — the id schemes and cross-references only stay useful if every skill
writes them the same way. All paths are relative to the workspace root (see `workspace-layout.md`).

## ID scheme

Evidence, claims and decisions each use a numeric id local to their own directory:
`E001`, `C001`, `D001` — zero-padded to 3 digits, **next id = (highest existing number in that
directory) + 1**. Never reuse or renumber an id, even after a file is deleted. Plans do NOT use this
scheme — see `plans.md`.

## `project.md` (workspace root)

```yaml
---
type: research-project
topic: <current adopted topic, one line>
initial_topic: <topic as first entered — set once, then frozen forever>
domain: <optional>
created_at: <ISO8601>
updated_at: <ISO8601>
---

# Research Project

## Research Statement
<topic, restated as prose>

## Motivation
<optional — include only if a goal/motivation was actually given>

## Research Questions
- <question 1>
<!-- or, if none yet defined: 尚未凝练出可检验的研究问题 -->

## Scope
<!-- what is / isn't in scope, or a placeholder note if not yet defined -->

## Domain
<domain, or a placeholder note>
```

- **Create once**, on the first `/research <topic>` in a fresh directory. Regenerating the whole
  file is fine at creation time; after that, prefer the surgical topic update below.
- **Topic changes are a frontmatter-only edit, never a full rewrite** — the hand-written body
  (Research Statement/Scope/Domain) must survive a topic change untouched. On a real change (not a
  no-op — compare whitespace/quote-normalized): if this is the *first* change, freeze the current
  `topic` value into `initial_topic` before overwriting it. Then append a record to
  `research/topic-history.json` (create the array if absent, never truncate it):
  ```json
  { "from": "...", "to": "...", "at": "<ISO8601>", "reason": "...", "evidence": ["D001"], "by": "agent" }
  ```
  Always give a `reason` when the agent (not the user directly) changes the topic.

## `research-state.md` (workspace root, sibling of `project.md`)

```yaml
---
name: Research State
type: research-state
version: '2'                     # plain increasing integer-as-string: '1' -> '2' -> '3'
maturity_problem: Emerging
maturity_knowledge: Weak
maturity_innovation: Unknown
maturity_method: Emerging
maturity_experiment: Unknown
maturity_evidence: Weak
created_at: <ISO8601>
updated_at: <ISO8601>
---

# Research State

## Problem
<free text>

## Literature
<free text>
```

- **13 dimensions**, in this fixed order, each rendered as its own `## <Dimension>` section —
  **only when it has real content**. Never write an empty/placeholder header for a dimension with
  nothing to say — a missing section IS the correct way to represent "not established yet":
  `Problem, Research Questions, Current Knowledge, Literature, Innovation, Hypotheses, Method,
  Experiments, Claims, Evidence, Decisions, Risks, Open Questions`.
- **6 maturity levels** (a *different*, smaller list — do not confuse with the 13 dimensions above):
  `Problem, Knowledge, Innovation, Method, Experiment, Evidence`. Each takes one of, in increasing
  order: `Unknown, Weak, Emerging, Strong, Established`. Stored as flat frontmatter keys
  `maturity_<lowercase name>` (e.g. `maturity_method: Strong`).
- The `## Decisions` dimension here is a short free-text human summary only — the actual structured
  decision records live one level down, in `research/decisions/D<NNN>.md` (schema below). Keep both
  in sync when a decision is added.
- **The agent never overwrites `research-state.md` directly.** Instead:
  1. Archive the current on-disk file byte-for-byte to `research/state-history/v<N>.md` where `N` is
     the version number *being replaced* (skip if that exact content, header stripped, is already
     archived there).
  2. Write a proposal instead of the real file, at `research/state-proposals/S<NNN>.json`
     (next sequential number in that directory):
     ```json
     {
       "id": "S003",
       "origin": { "actor": "agent", "evidence": ["E004", "E007"], "plan": "baseline-eval" },
       "changes": { "Method": "new section text", "Risks": null },
       "maturityChanges": { "Method": "Strong" },
       "rationale": "one sentence",
       "confidence": "Emerging",
       "at": "<ISO8601>"
     }
     ```
     `changes` maps a dimension name to new Markdown text, or `null` to delete that dimension.
  3. On the user accepting (or the agent applying with clear authorization) a proposal: merge
     `changes` into the dimensions and `maturityChanges` into maturity, bump `version` by 1, write
     the new `research-state.md`, append a record to `research/state-proposals/applied.json`
     (append-only, never overwritten):
     ```json
     { "proposalId": "S003", "action": "accepted", "at": "...", "fromVersion": "2", "toVersion": "3", "by": "user", "appliedChanges": { "...": "..." } }
     ```
     then delete the `S<NNN>.json` proposal file. On rejection, append an `applied.json` record with
     `"action": "rejected"` and leave the state file untouched.

## Evidence — `research/evidence/E<NNN>.md`

```yaml
---
name: Baseline accuracy drop on ImageNet-C
type: experiment-evidence          # convention: `${source_kind}-evidence`
status: supported                  # unverified | supported | verified | rejected | superseded
source_kind: experiment             # literature | experiment | computation | observation | dataset | implementation | analysis | user-judgment | external
supports: C001, C003                # CLAIM ids this evidence supports
contradicts: C007                   # CLAIM ids this evidence contradicts (omit if none)
supersedes: E002                    # omit unless set
superseded_by: E011                 # omit unless set (filled in on the OLD record automatically)
plan: baseline-robustness-eval      # plan id (no `plans/` prefix, no `.md` suffix)
paper: paper-2026-01
raw_artifacts: experiments/baseline-eval/results/imagenet-c.json | experiments/baseline-eval/results/summary.md
created_at: <ISO8601>
updated_at: <ISO8601>
---

# Evidence: Baseline accuracy drop on ImageNet-C

## Claim
<the one-line factual claim this evidence establishes>

## Experimental Context
<dataset, baseline, setup>

## Result
<the actual numbers>

## Observation
<what pattern the numbers show>

## Supporting Data
- experiments/baseline-eval/results/imagenet-c.json

## Reproducibility
<exact command to reproduce>

## Validation
Status: supported
```

- All 7 body sections are a **recommended template, not a requirement** — write the ones that apply,
  skip the rest. `## Validation` must always end with a `Status: <status>` line, rewritten whenever
  status changes; add `Superseded by: <id>` (and optionally `Reason:`) when superseding.
- `raw_artifacts` in frontmatter is `|`-delimited. Prefer setting it explicitly in frontmatter over
  relying on parsing the `## Supporting Data` list.
- **Supersede, don't overwrite**: when evidence is corrected/replaced, set the old file's
  `status: superseded` + `superseded_by: <new id>`, and the new file's `supersedes: <old id>` — never
  delete the old file.
- **Delete is only for evidence with zero references** (empty `supports`/`contradicts` everywhere it
  might be cited) — a cited fact is never deleted outright; supersede it or set `status: rejected`
  instead.
- Before any mutating edit, snapshot the pre-edit file to
  `research/evidence/.history/E<NNN>.<ISO-timestamp-with-dashes>.md` (e.g.
  `E003.2026-09-16T10-22-01-123Z.md`) with a `<!-- snapshot: <note> -->` header. This is a per-file
  mutation history, independent of `research-state.md`'s own version history.
- When creating evidence with `supports`/`contradicts` set, immediately establish the matching
  cross-reference on every claim listed (see below) in the same step.

## Claims — `research/claims/C<NNN>.md`

```yaml
---
name: ResNet-50 baseline is not robust to common corruptions
type: research-claim
status: supported                  # unverified | supported | verified | rejected | superseded
evidence: E001                     # EVIDENCE ids supporting this claim
contradicts: E009                   # EVIDENCE ids contradicting this claim
required_evidence: <what would still be needed to establish this, if incomplete>
paper: paper-2026-01
created_at: <ISO8601>
updated_at: <ISO8601>
---

# Claim: C001

## Statement
<the claim, as one falsifiable sentence>

## Required Evidence
<optional, only if `required_evidence` is set>

## Evidence
- E001

## Contradicting Evidence
<optional — only if there are any>
- E009
```

> **Naming trap — read carefully.** The YAML key `contradicts` is used on **both** file types, but
> holds a different *kind* of id on each: on an **Evidence** file it lists **claim ids**
> (`contradicts: C007`); on a **Claim** file it lists **evidence ids** (`contradicts: E009`). Do not
> transpose these.

- **Cross-reference invariant** (keep both sides consistent on every write):
  `Evidence.supports` <-> appears in `Claim.evidence`; `Evidence.contradicts` <-> appears in
  `Claim.contradicts`.
- **Reconciling a claim's status from its evidence** (deterministic, never a subjective judgment
  call): recompute from the evidence side, ignoring superseded evidence.
  - All supporting evidence `rejected` -> claim `rejected`.
  - >=1 evidence `supported`/`verified` and none contradicting -> claim `supported` (or `verified`
    if any evidence is `verified`).
  - >=1 supporting AND >=1 contradicting -> claim `unverified` (contested — flag for a human, do not
    auto-resolve).
  - No qualifying evidence either way -> leave status unchanged.

## Decisions — `research/decisions/D<NNN>.md`

```yaml
---
name: <short title>
type: research-decision
status: decided                    # free string; conventionally: decided | revisiting | reversed
evidence: E001, E004                # evidence ids relied on (comma-joined)
created_at: <ISO8601>
updated_at: <ISO8601>
---

# Decision: D001

## Decision
<what was decided>

## Reason
<why — required if `evidence` is empty>

## Evidence
- E001
- E004

## Alternatives Considered
<what else was considered, if anything>

## Status
decided
```

- **Require either a `Reason` or at least one `evidence` id.** A decision record with neither is not
  a valid research decision — do not create it.
- Decisions are appended or status-updated, never silently rewritten. There is no "supersede"
  concept for decisions (unlike evidence) — if a decision is reversed, update its `status` in place
  and say why in the body; deleting a decision file is a hard removal, not a soft one, and should be
  rare.
