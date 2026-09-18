---
name: peer-review-panel
description: "Run a manuscript through four independently-mandated reviewer personas (Journal-Fit, Methods & Reproducibility, Impact & Related-Work, Devil's Advocate) instead of one reviewer voice, then reconcile their verdicts into a single risk-ranked action list with a journal-style recommendation. Use when A single-reviewer critique already exists and the author wants the wider spread of opinion a real; or when The manuscript is high-stakes (top-venue submission, rebuttal-defining revision) and a single; or when The author suspects a single reviewer voice is anchoring on one class of problem (e.g. always; or when Evidence and claim records exist in the workspace and a reviewer should check the manuscript's."
---

# Peer Review Panel

> Original addition to this plugin (not ported from ConvFusion). Complements `peer-review-simulation`
> rather than replacing it: that skill produces one rigorous reviewer voice; this skill runs several
> differently-mandated ones and reconciles them, the way a real journal's review round does.

## Purpose

Real peer review rarely comes back as one verdict — it comes back as two or three reviewers who
disagree, plus an editor who has to weigh their disagreement. A single simulated reviewer, however
well-calibrated, anchors on whatever that one persona is built to notice. This skill runs the
manuscript through four reviewers with genuinely different mandates, has them work independently
(no persona sees another's draft critique before finishing its own), and then produces a synthesis
that shows where they agree, where they conflict, and what that conflict itself implies about the
manuscript's readiness.

## When to Use

Use this skill when:

- A single-reviewer critique (`peer-review-simulation`) already exists and the author wants the
  wider spread of opinion a real review round would produce before deciding what to fix.
- The manuscript is high-stakes (top-venue submission, a rebuttal-defining revision) and a single
  missed class of objection is expensive.
- The author suspects a single reviewer voice is anchoring on one class of problem (e.g. always
  flagging novelty, never flagging statistical validity) and wants deliberately different mandates
  applied.
- Evidence and claim records exist in the workspace (`research/evidence/`, `research/claims/`,
  `.researchledger/index.json`) and a reviewer should check the manuscript's empirical claims
  against them mechanically, not just plausibility-check them by reading.
- The user explicitly asks for a "review panel," "multiple reviewers," "devil's advocate," or "what
  would different reviewers say."

Do not use this in place of `pre-submission-editorial-audit` — that skill screens for integrity
risks (fabrication, unsupported claims, benchmark contamination) under one editorial mandate. This
skill is about the *spread* of legitimate scholarly opinion, not integrity screening.

## Research Method

### 1. Confirm scope before dispatching personas

Identify the manuscript (or section) under review, its target venue if stated, and whether workspace
evidence/claim records exist to ground Reviewer 2's cross-check (see step 2.2). If no such records
exist, say so once and have Reviewer 2 note the limitation rather than skip the check silently.

### 2. Run four independent reviewer passes

Write each persona's critique as if the others do not exist — no persona should reference or soften
its judgment based on what another might say. Each pass follows the same grounding discipline as
`peer-review-simulation`: every critique is anchored to a specific page/line or section/paragraph,
nothing is fabricated, and anything that cannot be located in the manuscript is flagged as such
rather than guessed at.

**2.1 — Journal-Fit & Construct Reviewer.** Runs the existing `peer-review-simulation` method in
full: journal/genre fit, construct clarity, novelty vs. literature, evidence/citation depth,
mechanistic specificity, predictive/empirical viability. (Reuse that skill's output rather than
re-deriving it if it was already produced in this session.)

**2.2 — Methods & Reproducibility Reviewer.** Mandate: assume the framing and novelty claims are
fine, and interrogate whether the *evidence actually supports* them. Check experimental design
(baselines, ablations, control conditions), statistical soundness (are effect sizes, error bars,
significance tests reported and appropriate for the claim size), and dataset/protocol adequacy. If
workspace evidence/claim records exist, trace each major empirical claim in the manuscript back to
the run(s) and evidence record(s) that produced it — flag any claim that cites a stronger result
than its linked evidence record supports, any claim with no traceable evidence record at all, and
any run whose recorded status contradicts what the manuscript reports. This is the one persona
uniquely positioned to do a mechanical check rather than a plausibility read, since the workspace's
run ledger and claim records are content this reviewer can actually open and cross-reference.

**2.3 — Impact & Related-Work Reviewer.** Mandate: assume the methods are sound, and interrogate
whether the contribution is worth publishing *now, here*. Position the work against the strongest
recent related work the manuscript itself cites or should cite — is the delta genuinely novel or
incremental dressed as novel? Would a reader already familiar with the two or three closest prior
works find this paper's contribution obvious in hindsight? Flag missing comparisons to work the
manuscript's own citations imply should be compared against, and judge whether the claimed
significance matches the actual scope of the result.

**2.4 — Devil's Advocate.** Mandate: build the strongest good-faith case for rejection, using only
what is in the manuscript (or its cited sources) — never invented flaws. For each of the manuscript's
central claims, generate at least one alternative explanation for the observed result that the
manuscript does not rule out, and name the single most damaging unaddressed threat to validity. This
persona does not have to be right about every point — its job is to force the other reviewers'
optimism to be tested — but every point must still be anchored to the manuscript and reasoned, not
asserted.

### 3. Reconcile into a synthesis

After all four passes are complete, produce a synthesis that:

- Lists points where two or more reviewers independently converged on the same issue (these are the
  highest-confidence action items — independent convergence is stronger signal than any one
  reviewer's severity rating).
- Lists points where reviewers explicitly conflict (e.g. Impact reviewer calls the contribution
  sufficient, Devil's Advocate calls it incremental) and states what would resolve the conflict
  (usually: what additional evidence or framing change would satisfy both readings).
- Ranks the combined action list by (a) how many reviewers raised it, (b) whether Reviewer 2 found a
  mechanical evidence gap (treat this tier as highest priority — an untraceable claim is a
  correctness risk, not a matter of opinion), then (c) severity as judged by the individual reviews.
- Closes with a single journal-style recommendation — Accept / Minor Revision / Major Revision /
  Reject-with-resubmission-potential / Reject — justified by which tier of issues dominates, not
  asserted on its own.

## Reasoning Guidance

Keep each persona's voice genuinely distinct in mandate, not just tone — the value of this skill is
that four different lenses were actually applied, not that the same critique was restyled four ways.
Write in full academic prose for each pass: precise, serious, non-emotional, no sarcasm or personal
remarks, consistent with `peer-review-simulation`. The synthesis step is the one place a more
editorial voice is appropriate, since an editor synthesizing conflicting reviews is itself a
real academic register.

### Anti-gaming safeguards

These three rules exist because they are documented ways automated reviewers get fooled — not
hypothetical risks:

- **Presentation-invariance.** Judge every claim on whether it is supported, never on how
  confidently or fluently it is stated. A rewrite that only improves phrasing, without changing the
  underlying evidence, must not change any reviewer's severity rating. If a reviewer notices its own
  assessment softening because a passage merely *reads* more polished, that is the signal to
  re-examine the underlying evidence, not to relax the finding.
- **Hedging does not rescue an unsupported claim.** "Results suggest," "may indicate," or similar
  hedges reduce a claim's certainty; they do not supply the missing evidence for it. A hedged causal
  or comparative claim with no reported statistical test, baseline, or ablation behind it is still
  flagged as unsupported by the Methods & Reproducibility reviewer — the hedge changes how the flag
  is worded, not whether it is raised.
- **Independent-pass discipline is load-bearing, not procedural.** A panel where each persona
  quietly reads the others' drafts before finishing its own collapses into one opinion wearing four
  labels — which defeats the purpose of running a panel at all. If personas are being produced in a
  single continuous pass, keep each one's reasoning self-contained and do not let a later persona's
  critique reference or soften an earlier one's finding.

### Per-persona checklist (score, don't just narrate)

Narrative-only reviews drift in severity across runs of the same manuscript. Alongside each
persona's prose, track a short checklist so the same issue gets the same weight every time:

- **Journal-Fit & Construct** — for each major construct: defined / circular / undefined (per
  `peer-review-simulation`'s own method).
- **Methods & Reproducibility** — for each major empirical claim: evidence-traced-and-matches /
  evidence-traced-but-overstated / no-traceable-evidence. Treat the latter two as findings regardless
  of how the claim is worded.
- **Impact & Related-Work** — for the central contribution: novel / incremental-but-positioned-as-novel
  / incremental-and-acknowledged. Name the specific prior work, if any, that the manuscript's own
  citations already establish as closest.
- **Devil's Advocate** — for each central claim: at least one alternative explanation named, or
  explicitly "no plausible alternative found" (never silence — an absence of a counter-argument
  should be stated, not implied by omission).

## Evidence Requirements

Same discipline as `peer-review-simulation`: every critique across all four personas must cite a
specific manuscript location. Reviewer 2's evidence cross-check must cite the specific claim/evidence
record IDs it compared, not just "the workspace records." Never infer fraud or AI-authorship from
prose style in any persona (same rule as `pre-submission-editorial-audit`) — this skill evaluates
the strength of an argument and its evidence, not the manuscript's provenance.

## Expected Output

1. Four labeled review sections (Journal-Fit & Construct, Methods & Reproducibility, Impact &
   Related-Work, Devil's Advocate), each internally organized however that persona's method
   dictates.
2. A **Synthesis** section: convergent issues, conflicting issues (with what would resolve each),
   and the ranked combined action list.
3. A closing **Recommendation** line (one of the five categories above) with one paragraph of
   justification tied to the ranked action list — never a bare category with no justification.

## Workspace Conventions

If Reviewer 2 traces claims against workspace evidence/claim records, follow the exact schemas in
this plugin's `reference/` directory — see [research-assets.md](../../reference/research-assets.md)
for the evidence/claim/decision record format and [run-ledger.md](../../reference/run-ledger.md) for
how runs are recorded and how the `researchledger` CLI's tracer can be used to check a claim's
lineage mechanically rather than by eye, when the CLI is available in the workspace. If this skill
was invoked on its own rather than through `/research`, check whether `project.md` or
`research-state.md` already exists before assuming there is no workspace context.

## Reference Prompts

This skill has no `reference.md` — it composes `peer-review-simulation`'s existing method (see that
skill's own [reference.md](../peer-review-simulation/reference.md) for its verbose source prompts)
rather than introducing a second version of the same critique method.
