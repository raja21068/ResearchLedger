# Papers: entity, evolution, gaps, maturity

A paper lives at `papers/<paperId>/`, not under `outputs/` — it's the core research entity, not a
derived output (see `outputs.md` for patents/reports/slides, which *are* derived from a paper).
Paper ids: kebab-case, e.g. `paper-d2-method`, falling back to `paper-main` for a single-paper
project. The currently active paper id, if there's more than one, is tracked in a plain-text file
`.active-paper` at the workspace root.

```text
papers/<paperId>/
├── paper.md            # the manuscript — the ONLY file that's actually required
├── metadata.md          # frontmatter-carried identity (title, status, version, venue, authors...)
├── evolution.md          # human-readable revision narrative
├── evolution.json        # machine-readable event log (array)
├── claims.md              # Claim Map — derived, never hand-edited
├── evidence.md            # Evidence Map — derived, never hand-edited
├── gaps.md                 # open gaps between manuscript and research state
├── maturity.md             # qualitative per-dimension maturity judgment
├── proposals/R<NNN>.md     # one file per pending/resolved revision proposal
├── history/v<version>.md  # manuscript snapshots, one per version bump
└── figures/
```

A paper document's pieces are independent and each is **optional except `paper.md`** — a paper with
no `gaps.md` yet just means gaps haven't been analyzed, not an error.

## Manuscript skeleton (`paper.md`)

```markdown
# Title

## Abstract

## 1. Introduction

## 2. Related Work
## 3. Method
## 4. Experiments
## 5. Results
## 6. Discussion
## 7. Conclusion
```

The required sections for gap-checking purposes (never enforced on write, only used to detect a
missing one): `Abstract, Introduction, Related Work, Method, Experiments, Results, Discussion,
Conclusion` (compare titles with any leading `N.`/`N、`/`N)` stripped).

Claims are referenced in body text as `C001`; evidence as `E001`. A quantitative statement can
optionally carry an invisible provenance marker right after it, e.g. `<!-- rl:claim=C014 -->` (the
evidence is already reachable from the claim, so naming it explicitly, `evidence=E031,E034`, is
optional) — `researchledger validate`/`trace`/`validate-paper` use it to check and follow the chain
from that sentence down to the run and artifact that produced it. See
[`run-ledger.md`](run-ledger.md). Optional: a paper with no markers is unaffected.

## `metadata.md` frontmatter

```yaml
---
id: PAPER001              # UPPERCASE id, <=12 chars, [A-Z0-9]
type: research-paper
title: <string>
status: draft|evolving|frozen|archived|submitted   # default: evolving
version: "0.1"             # bump 0.1 -> 0.2 (minor) or -> 1.0 (major)
research_state_version: "3"
authors: <string>
affiliation: <string>       # multiple, separated by ";"
target_venue: <string>
research_domain: <string>
created_at: <ISO8601>
updated_at: <ISO8601>
---
```

## Claim Map / Evidence Map — always derived, never hand-authored

`claims.md` — regenerate from `research/claims/*.md` plus a scan of which sections in `paper.md`
actually cite each claim id; never invent a claim here that doesn't exist in `research/claims/`:

```markdown
# Claim Map

## C001

Statement:

<the claim statement>

Status:

supported

Evidence:
- E001

Contradicting Evidence:
- E009

Paper Sections:
- Method
- Results
```

`evidence.md` mirrors it from the evidence side:

```markdown
# Evidence Map

## E001

- supports: C001, C003
- contradicts: (none)
- referenced by: Method, Results
```

## Evolution — agents never edit `paper.md` directly

Every change to a manuscript passes through a proposal first:
`Research change -> impact analysis (read-only) -> Revision Proposal -> user review (accept/edit/reject) -> applied -> new version`.

Proposal file, `papers/<id>/proposals/R<NNN>.md`:

```yaml
---
id: R001
type: paper-revision-proposal
status: proposed|accepted|edited|rejected
proposed_by: agent|user
trigger: evidence-added|new-claim|claim-status-changed|research-state-changed|new-decision|experiment-completed|user-revision-request|literature-update|gap-detected|manual
created_at: <ISO8601>
---

# Revision Proposal R001

## Reason
<why>

## Affected Claims
- C003

## Affected Sections
- Results

## Proposed Changes
<markdown text to add/change>

## Supporting Evidence
- E008

## Risk
<free text, or "(none recorded)">

## Status
proposed
```

**Applying an accepted/edited proposal — do these 5 steps, in order, as one operation:**

1. Archive the current manuscript verbatim to `history/v<currentVersion>.md`, prefixed with
   `<!-- snapshot: <ISO8601> -- <reason> -->`. Skip if identical content is already archived there.
2. Write the new manuscript. Default behavior when the proposal doesn't supply a full rewrite is to
   **append**, not overwrite: insert
   `<!-- proposed by R001 (agent): <reason, <=120 chars> -->\n<the proposed text>` right after the
   affected section's last line (before the next `##`), or at the end of the file if no section is
   named.
3. Bump `metadata.md`'s `version` and `updated_at`.
4. Append an event to `evolution.json` **and** a matching narrative block to `evolution.md`:
   ```json
   { "id": "EV003", "fromVersion": "0.4", "toVersion": "0.5", "trigger": "user-revision-request",
     "evidence": ["E008"], "claims": ["C003"], "sections": ["Results"],
     "action": "accepted", "author": "user", "timestamp": "<ISO8601>", "summary": "R001 accepted: ..." }
   ```
   ```markdown
   ## EV003 — 0.4 → 0.5

   - Trigger: user-revision-request
   - Action: accepted (by user)
   - When: <ISO8601>
   - Evidence: E008
   - Claims: C003
   - Sections: Results
   ```
5. Rewrite the proposal file's `status:` (`accepted`/`edited`).

**Rejecting** a proposal only rewrites its own `status: rejected` and appends an evolution event with
`fromVersion == toVersion` — no manuscript change, no version bump.

**Restoring** an old version is itself an evolution: archive current -> write the historical text
back to `paper.md` (stripping its snapshot comment) -> bump the version *forward* (never reuse the
old number) -> `status: evolving`.

## Gaps (`gaps.md`)

One `##`-block per gap, plain-text field lines (not YAML):

```markdown
# Research Gaps

## G001

**Type**: unsupported-claim
**Description**: Claim C003 appears in the manuscript with no supporting evidence.
**Related Claim**: C003
**Related Section**: Results
**Suggested Skill**: evidence-assessment
**Priority**: high
**Detected By**: rule
**Created At**: <ISO8601>
```

Gap types worth checking for, in this order, each mapped to the skill that would close it:

| check | gap type | priority | suggested skill |
|---|---|---|---|
| a required section is missing | `missing-section` | high (Abstract/Method) or medium | `paper-architecture` |
| a section body is empty after stripping comments | `thin-section` | medium | `section-drafting` |
| a claim has zero supporting evidence | `unsupported-claim` | high | `evidence-assessment` |
| a claim has unaddressed contradicting evidence | `contested-claim` | high | `comparative-analysis` |
| body cites a claim id that doesn't exist in `research/claims/` | `missing-evidence` | high | `experiment-design` |
| evidence has no raw-artifact reference | `evidence-without-artifact` | medium | `reproducible-implementation-spec` |
| evidence is never referenced in the manuscript | `unreferenced-evidence` | low (medium if `verified`) | `section-drafting` |
| Experiments/Results has content but no ablation | `missing-ablation` | high | `ablation-design` |
| Method/Experiments text lacks all of dataset/seed/environment/hyperparameter/version/benchmark | `reproducibility` | medium | `reproducible-implementation-spec` |
| an Open Question from `research-state.md` isn't echoed anywhere in the manuscript | `missing-section` (Discussion) | medium | — |

When re-running gap detection, only insert a gap if an unresolved one with the same
`type + relatedClaim + relatedSection` doesn't already exist — don't duplicate.

**Hard rule: gap -> suggested skill -> (user decides to create) a plan -> user review -> execution.**
Never auto-execute a fix for a detected gap.

## Maturity (`maturity.md`)

Nine dimensions (distinct from `research-state.md`'s 6 — don't confuse them):
`Problem, Literature, Innovation, Method, Experiment, Evidence, Claims, Writing, Reproducibility`.
Same 5 qualitative levels as elsewhere (`Unknown, Weak, Emerging, Strong, Established`) — always with
a documented reason citing claim/evidence ids, never a bare percentage:

```yaml
---
name: Paper Maturity
type: paper-maturity
problem: Established
literature: Emerging
---

# Paper Maturity

## Problem

Status: Established

<reason, citing C/E ids inline>
```
