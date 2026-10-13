# V5 Loop Protocol

## Loop A — Literature and Reviewer Survival (Phase 10–14)

Phase 10 scores scientific quality; Phase 11 searches for prior work that destroys novelty; Phase 12 builds the closest-work matrix and intellectual-contribution statement; Phase 13 acts as Reviewer #1; Phase 14 revises/pivots/kills. Any material revision restarts at Phase 10 with fresh search.

Default literature GREENLIGHT thresholds remain conservative: total score ≥80/100, novelty component ≥14/20, destructive novelty verdict `SURVIVES`, matrix `DISTINCT`, explicit intellectual contribution, reviewer `SURVIVES`, zero Fatal criticisms, and no unresolved high-relevance patent-search gap.

This GREENLIGHT is **provisional** in V5. It only means the idea survived literature/reviewer attacks.

## Loop B — Falsification and Evidence (Phase 15–19)

### Phase 15 — Hypothesis Contract

The idea is rewritten as a falsifiable contract with null hypothesis, mechanism, observable predictions, confounders, competing explanations, boundary conditions, and explicit falsifiers.

### Phase 16 — Occam + Counterexample Attack

The falsifier asks whether a simpler mechanism explains the same effect, removes components, designs adversarial/counterexample tests, and specifies positive/negative controls and leakage tests.

### Phase 17 — Blind Verifier

A reduced-context verifier judges whether the mechanism is identifiable and whether the proposed tests can discriminate the claim from alternatives. `REVISE` or `KILL` cannot be overridden by an earlier high score.

### Phase 18 — Minimum Viable Experiment

A small, high-information pilot is specified. Its purpose is not to maximize performance; it is to cheaply expose whether the central claim is wrong, confounded, or unnecessary.

### Phase 19 — Real Evidence Audit

If no evidence file exists, termination is `READY_FOR_MVE`. If evidence exists, V5 validates that it represents an executed run, independently audits it, and builds the claim/evidence ledger.

```text
SUPPORTED + adequate quality + full protocol + controls/leakage pass
    → GREENLIGHT
INCONCLUSIVE / weak / protocol-partial
    → REVISE_EVIDENCE
CONTRADICTED
    → KILL or scientific revision
```

A scientific revision generated from Loop B must restart **Loop A at Phase 10** before it may return to Phase 15.

## Why two loops

Loop A asks: **Is the idea novel and reviewer-defensible?**

Loop B asks: **Is the claim falsifiable, and does actual pilot evidence justify the full study?**

Passing one never implies passing the other.
