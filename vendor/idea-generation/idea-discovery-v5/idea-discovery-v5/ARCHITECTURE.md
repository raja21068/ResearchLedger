# V5 Architecture

## Core principle

V5 uses separate gates for **problem validity**, **idea quality**, **literature/reviewer survival**, **falsifiability**, and **empirical support**.

```text
GAP
 ├─ Level 1/2 → BLOCKED
 └─ Level 3/4 → EVOLUTION_TRACK

EVOLUTION_TRACK
 └─ champion → ATTACK_ROUND_1

ATTACK_ROUND_n (Phase 10–14)
 ├─ all attacks pass → PROVISIONAL_LITERATURE_GREENLIGHT
 ├─ unrecoverable collision/flaw → KILL
 └─ revision → ATTACK_ROUND_(n+1)

PROVISIONAL_LITERATURE_GREENLIGHT
 └─ FALSIFICATION_ROUND_1

FALSIFICATION_ROUND_n (Phase 15–19)
 ├─ design flaw, revisable → SCIENTIFIC_REVISION → Phase 10 restart
 ├─ fatal design/contradiction → KILL
 ├─ design passes, no MVE evidence → READY_FOR_MVE
 ├─ weak/inconclusive evidence → REVISE_EVIDENCE
 └─ controlled executed evidence supports claim → FINAL GREENLIGHT

FINAL GREENLIGHT
 └─ ELO → full-study blueprint
```

## Falsification implementation

`scripts/step7c_falsification.py` adds five stages:

- **Phase 15:** convert the idea into a falsifiable hypothesis contract.
- **Phase 16:** remove unnecessary complexity and design counterexamples/controls.
- **Phase 17:** blind independent verification of testability and identifiability.
- **Phase 18:** generate an MVE protocol with explicit decision rules.
- **Phase 19:** audit externally executed evidence and build a claim/evidence ledger.

The module does not run arbitrary generated scientific commands. It writes the protocol, then looks for real evidence in `output/mve_evidence/<IDEA-ID>.json`.

## Back-edge to literature validation

A falsification-stage scientific revision cannot retain its old literature pass. V5 re-runs Phase 10–14 with fresh literature search using `rerun_literature_survival()` before the revised idea can re-enter falsification.

## Independent verification boundary

The blind verifier receives a deliberately reduced payload:

`hypothesis_contract + falsification_plan + MVE_protocol`

It does not receive generator enthusiasm, prior scorecard totals, ELO, or desired outcome. When a second provider is configured, `AttackClient` can use it; otherwise the separation remains contextual rather than provider-independent and is recorded as such.

## Evidence states

Final decision is conservative:

- `READY_FOR_MVE` — no executed evidence artifact exists.
- `REVISE_EVIDENCE` — evidence is incomplete, inconclusive, weak, protocol-partial, or control/leakage checks fail.
- `KILL` — contradiction/fatal failure.
- `GREENLIGHT` — real MVE evidence is at least medium quality, follows protocol, passes negative controls/leakage checks, and yields a supported evidence ledger justifying the full study.

## Audit chain

`discovery_grounding.json → evolution_trace.json → attack_loop/* → falsification/* → falsification_summary.json → survivor_elo.json → research_blueprints.json`

Every transition is persisted so a later reviewer can reconstruct why an idea advanced or stopped.
