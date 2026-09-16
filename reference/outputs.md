# Non-paper outputs: patents, technical reports, slides

Every non-paper output type has a fixed **profile**: an audience, a purpose, a recommended section
structure, and a set of quality checks. Profiles are reference data, not a workflow to execute step
by step.

| type | dir | id prefix | main file | format | claim-traceable? | matching skill |
|---|---|---|---|---|---|---|
| patent | `outputs/patents/` | `patent` | `patent.md` | markdown | no | `patent-drafting` |
| technical report | `outputs/reports/` | `report` | `report.md` | markdown | no | `technical-report-writing` |
| slides | `outputs/slides/` | `presentation` | `slides.md` | markdown | no | `presentation-design` |

Ids: kebab-case + zero-padded sequential number, e.g. `patent-001`, `report-002`,
`presentation-001` — next unused number for that type.

## Recommended structure per type

- **Patent**: Technical Field, Background/Technical Problem, Technical Solution, Technical Effects,
  Detailed Implementation, Embodiments, Claims, Abstract.
- **Technical report**: Summary, Context and Scope, Approach, Implementation Details, Results,
  Limitations, Reproduction Instructions, References.
- **Slides**: Title, Motivation/Problem, Limitations of Prior Work, Key Insight, Approach,
  Experiment Setup, Results, Analysis/Ablation, Limitations, Conclusion, Backup.

These are recommendations, weakly enforced: note a missing section as a gap, don't block on it.

> **A patent claim is not a research claim.** A research claim (`research/claims/C00N.md`) states a
> fact and needs evidence. A patent claim defines the boundaries of an exclusive right via technical
> features, phrased as one enumerated sentence: `1. A ... method, comprising: receiving ...;
> determining ...; calibrating ...`. Never copy research-claim text into a patent's `claims.md`.

## Directory layout per output

```text
outputs/<kind>/<id>/
├── <mainfile>       # patent.md | report.md | slides.md
├── metadata.md       # human-readable recap of the frontmatter
├── claims.md          # patent only — patent claims, see warning above
├── provenance.md       # what this output was derived from (references only, nothing copied)
├── history/v<version>.md
├── history/reviews.json
└── assets/             # slides only
```

## Main-file frontmatter

```yaml
---
id: patent-001
title: <string>
type: patent|technical-report|slides
status: draft|reviewed|approved|archived
version: "0.1"
goal: <what this transformation is meant to achieve>
source_research_state: "3"
source_paper: paper-d2-method
source_claims: C001, C003
source_evidence: E001, E008
skill: patent-drafting
created_at: <ISO8601>
updated_at: <ISO8601>
---

# Patent: <title>

## Technical Field
...
## Claims
<!-- these are patent claims, not research claims — see the warning above -->
...
```

## Creating an output

1. Allocate the next unused id for that type.
2. Create the output directory (+ `assets/` if it's a slide deck).
3. Write the main file: frontmatter above + one `##` section per entry in that type's structure
   list, seeded with an HTML-comment placeholder (`<!-- Technical Field -->`) — except a patent's
   `## Claims` section, which gets the "not a research claim" warning comment instead of a bare
   placeholder.
4. Write `metadata.md` (a human-readable recap of the frontmatter — no new information).
5. If the type is `patent`, also write `claims.md`: the warning comment + a numbered
   `1. <!-- ... -->` stub to fill in.
6. Write `provenance.md` (below).

**Never touch `research/` when creating or editing an output** — outputs only *reference* research
assets, they never modify them.

## Reviewing an output

Actions: `reviewed | approved | rejected | edited | archived`.

- An `archived` output can never be reviewed again — create a new output instead of reviving one.
- `rejected` only appends a record to `history/reviews.json`; no version bump, no content change.
- Otherwise: archive the current main-file content to `history/v<version>.md` (same
  `<!-- snapshot: ... -->` convention as papers) -> if `edited`, replace the body with the supplied
  final text -> bump `status` (and `version`, except for `archived`, which keeps its version number)
  -> rewrite the main file, refresh `metadata.md`/`provenance.md` -> append a record to
  `history/reviews.json`:
  ```json
  [{ "action": "approved", "at": "<ISO8601>", "by": "user", "fromVersion": "0.1", "toVersion": "0.2", "note": "..." }]
  ```

## `provenance.md` — references only, never copied content

Refresh this on every create/edit:

```markdown
# Provenance

This patent was transformed from the research below. Nothing here is copied —
these are references, so the source of every statement stays answerable.

## Chain

```text
output: patent-001  (patent v0.2)
  ↓ skill: patent-drafting
  ↓ source: paper-d2-method
  ↓ claim: C003
  ↓ evidence: E008
```

## Source references

- output type: patent
- output version: v0.2
- skill: patent-drafting
- paper: paper-d2-method
- claims: C003
- evidence: E008

> If any referenced claim or evidence changes, this output must be re-checked.
```

## Impact analysis (read-only)

When a claim/evidence changes, check every output's `source_claims`/`source_evidence`/`source_paper`
for a match, and surface which outputs may now be stale with a one-line recommendation ("Claim C003
changed. Re-check whether patent-001 still states it correctly."). This is **advisory only** — never
rewrite an output automatically just because its source changed.
