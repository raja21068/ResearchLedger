# Research Idea Discovery Agent — V5

> **V5 rule:** generation, literature validity, falsifiability, empirical support, and relative ranking are different judgments. Never substitute one for another.

This file accompanies `output/SESSION.md` or `output/SESSION.json` from the executable V5 pipeline.

## Evidence hierarchy inside V5

Read the research state in this order:

1. `discovery_grounding` — whether the problem is genuinely open.
2. `evolution_trace` — how candidate directions were generated and refined.
3. `attack_loop` — destructive prior-work search and hostile reviewer survival.
4. `falsification` — falsifiable contract, Occam/counterexample attack, blind verification, MVE protocol, and real-evidence audit.
5. `survivor_elo` — preference ordering among final-valid survivors only.
6. `blueprints` — full-study design after final GREENLIGHT.

If layers disagree, the stricter downstream scientific gate wins.

## Discovery rules

- Ground ideation in a broad relevant paper pool rather than model memory alone.
- Use novelty Type 1–4 and challenge→insight mapping.
- Block Level 1/2 well-established solutions by default.
- Use quote-or-zero evidence for claims that a problem is solved/open.
- Never manufacture a research gap from incomplete search.

## Multi-persona evolution

Each round produces complete Innovator, Pragmatist, and Critic variants. Select one seed only after all three exist. A dead-end mechanism may pivot; cosmetic wording changes are not a scientific revision.

## Phase 10–14 literature/reviewer survival

- **10 Scorecard:** 100-point weighted scientific quality assessment.
- **11 Novelty Attack:** search specifically for papers that make the idea not novel.
- **12 Novelty Matrix:** compare with strongest competitors and state the intellectual contribution.
- **13 Reviewer #1:** top 10 likely rejection reasons with Fatal/Major/Minor severity.
- **14 Revise/Pivot/Kill:** any material revision returns to Phase 10 with fresh search.

A direct prior-work collision or unresolved fatal flaw blocks literature GREENLIGHT.

## Phase 15–19 falsification zone

### Phase 15 — Hypothesis Contract

Require:
- central hypothesis;
- null hypothesis;
- mechanism claim;
- observable predictions;
- evidence that would support, weaken, and falsify the claim;
- competing explanations and confounders;
- boundary conditions;
- a minimum decisive experiment.

Reject hypotheses that cannot be disproven by observable evidence.

### Phase 16 — Occam + Counterexample Attack

Ask what can be removed, simplified, or replaced by a simpler explanation. Design counterexamples, positive/negative controls, leakage/shortcut tests, and competing-explanation tests. Complexity is not a contribution unless it is necessary for the claimed effect.

### Phase 17 — Independent Blind Verifier

The verifier must not be shown the generator's private reasoning, prior scores, desired acceptance outcome, or persuasive framing. It judges only the falsifiable contract, attack plan, and MVE protocol.

### Phase 18 — Minimum Viable Experiment

Prefer the cheapest credible experiment most capable of proving the hypothesis wrong. Specify strong baselines/controls, a critical ablation, primary metric, repeats/seeds, success/falsification/inconclusive rules, leakage checks, and required reproducibility artifacts.

Do not auto-execute generated commands unless a human separately approves and supplies a concrete execution context.

### Phase 19 — Evidence Audit + Ledger

No evidence, no GREENLIGHT.

Real MVE results are assessed as:
- `SUPPORTED`;
- `INCONCLUSIVE`;
- `CONTRADICTED`;
- `INVALID`.

The ledger must separately record supporting, contradicting, and missing evidence for each claim. Use `SUPPORTED / UNCERTAIN / CONTRADICTED`; do not claim scientific truth.

## State discipline

- `READY_FOR_MVE`: literature/reviewer + falsification design survived, but no executed pilot evidence exists.
- `REVISE_EVIDENCE`: evidence exists but is inconclusive, weak, protocol-incomplete, or fails controls/leakage checks.
- `KILL`: core claim or design is contradicted/fatal and not defensibly rescuable.
- `GREENLIGHT`: executed MVE evidence is adequate and the evidence ledger supports proceeding to a full study.

Any scientific revision caused by the falsification zone must restart Phase 10 before returning to Phase 15.

## Final-survivor ELO

ELO ranks only final GREENLIGHT ideas on novelty, feasibility, relevance, and clarity. It is a preference layer, not evidence of validity.

## Full-study architecture

Only after final GREENLIGHT should the system generate the complete research blueprint: datasets/materials, baselines, ablations, statistics, robustness, external validation, compute/resources, reproducibility artifacts, ethics/governance, success/failure criteria, and release plan.

## Hard prohibitions

- Never treat literature survival as empirical support.
- Never mark an unexecuted MVE as passed.
- Never invent pilot results, confidence intervals, artifacts, or control outcomes.
- Never convert `INCONCLUSIVE` into `SUPPORTED` because the idea is attractive.
- Never hide negative evidence from the ledger.
- Never let ELO rescue a failed scientific gate.
