# Referee Lean v2

Lean v2 keeps Referee's evidence locks while reducing the default scientific reasoning pipeline to three roles:

1. **Core Reviewer** — maps central claims, proposes evidence-grounded candidate concerns, and requests targeted evidence/specialist work.
2. **Specialist Executor** — one reusable role that dynamically loads only the skill family needed for a bounded proof burden.
3. **Independent Verifier** — adversarially attempts to falsify each candidate and supplies the steelman before admission.

The default Lean pipeline is seven stages:

`INGEST -> CORE_REVIEW -> TARGETED_EVIDENCE -> TARGETED_SPECIALISTS -> HARD_GATE -> INDEPENDENT_VERIFY -> FINALIZE`

Deterministic code owns document security, package inspection, anchor validation, provenance, closure checks, ID allocation, frozen hashes, admission, ranking and final export.

## Usage

Lean is the default pipeline for the CLI in this package. Programmatic `ReviewConfig()` keeps `legacy` as its compatibility default; set `pipeline="lean"` explicitly when embedding:

```bash
referee review paper.pdf --pipeline lean --mode deep --model <model>
```

The original architecture remains available for A/B evaluation:

```bash
referee review paper.pdf --pipeline legacy --mode deep --model <model>
```

Recommended modes:
- `standard`: up to 1 targeted specialist; small search budget.
- `deep`: up to 3 targeted specialists; recommended default.
- `exhaustive`: audit-oriented ceiling with more specialists/evidence work.

The scientific admission rule remains fail-closed: no major concern is exported unless its claims and anchors resolve, manuscript anchors pass deterministic integrity checks, external decisive evidence is opened and citation-verified, the closure criterion is actionable, an independent verifier confirms the concern, and frozen evidence hashes remain intact.
