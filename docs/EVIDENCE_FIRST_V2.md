# Evidence-first v2.0 — implementation and operator guide

## What this release actually implements

v2.0 adds **opt-in validation mode** to the existing five-stage Paper Factory pipeline. It does **not** claim a full experiment-before-draft architectural rewrite; Paper Factory still drafts result-slot placeholders in S2 so PaperCompiler can build the experiment in S4. The important improvement is that **an operator-authored, locked research protocol exists before S2**, and the S5 manuscript stage is blocked until independent *integrity checks* are satisfied.

| Gate | What is checked automatically | What is NOT established |
|---|---|---|
| Protocol | Frozen protocol and selected idea; dataset hash; registered baselines, splits, seeds and data usage acknowledgement | Ethics approval, split correctness, experiment preregistration with an independent repository |
| Literature | Crossref DOI resolution and cross-checked metadata receipts; manually populated nearest-prior-art matrix | Full-text correctness, verified novelty, exhaustive literature search |
| Experiment | Docker return code, code/data hashes, supplied-data attestation, primary metric and seed-level arithmetic | Scientifically valid method, actual source usage, fair baselines, statistical inference |
| Claim mapping | Every required results slot is explicitly mapped to a claim and the exact imported run | Coverage of untagged prose, causality, validity of scientific interpretations |
| Repeat | A new restricted Docker run, matching numeric results/series/seed metadata within declared tolerances | Independent replication by a different implementation, machine, or researcher |
| ResearchLedger | Hash-linked run/evidence/claim integrity, tamper detection | Independently authenticated scientific evidence or journal readiness |

`researchctl science-audit` can return `PASS_AUTOMATED_INTEGRITY_ONLY`; **it never returns "publication ready"**. Exploration mode has no confirmatory certification.

## Step-by-step: exploration

```bash
python -m pip install -e .
researchctl doctor
researchctl init "test idea"
# Edit <path printed by researchctl init>/_inputs/topic.md
researchctl run --project test-idea
researchctl science-audit test-idea
```

In exploration mode, synthetic data is permitted only with disclosure; outputs remain pilots. It is not a retrospective validation path.

## Step-by-step: prospective validation-data attempt

1. `researchctl init "prospective study"` (creates a blank protocol and prior-art template).
2. **Before running S1**, edit `<path printed by researchctl init>/_inputs/context.json` to include `"science_mode": "validation"` and retain `"ledger_enabled": true`. Do not change it after the run begins.
3. Edit `_inputs/topic.md`, supply the legitimate dataset under `_inputs/data/`, and run `researchctl run --project prospective-study --to S1`.
4. Fill `_inputs/research_protocol.json` with a concrete question, falsifier, dataset/version/license/split/unit of independence, baseline, primary metric, ablations, analysis, limitations and **two or more registered random seeds**. Mark `analysis_type="confirmatory"`, `dataset.license_reviewed=true`, `operator_acknowledgement=true` only after review.
5. `researchctl protocol lock prospective-study`. The lock binds the protocol, chosen idea and dataset. **Changing any of them requires a new prospectively disclosed project/version.** This local checksum does not prove an independent preregistration timestamp.
6. Before publication-oriented writing, verify relevant DOIs with `researchctl literature verify prospective-study --doi 10.XXXX/...` (calls Crossref with an explicit network request). Then complete `_inputs/prior_art.json` with each `doi`, `overlap`, `difference`, `limitation`, a concrete `novelty_claim`, and acknowledgement. `researchctl literature audit prospective-study` checks the metadata and completeness. It does not judge novelty.
7. `researchctl run --project prospective-study --from S2 --to S4`. S2 drafts *empty* result slots; S4 must report `data_source="provided"`, the registered `seeds`, positive `n_samples`, and `seed_metrics` including per-seed primary results consistent with the aggregate. Synthetic fallback is forbidden in validation mode. The code still requires independent inspection.
8. `researchctl claims scaffold prospective-study` creates one row per required results slot. Fill each statement, intended population and analysis type in `_inputs/metric_claims.json`. `researchctl claims bind prospective-study` verifies arithmetic and import provenance. A claim binding is **measured**, not independently verified.
9. `researchctl reproduce-isolated prospective-study` re-runs S4 code in a fresh restricted Docker container without network access, compares metrics, curves, and per-seed records, and saves an auditable repeat receipt. It uses **the same implementation**, so it is not independent reproduction. You can specify conservative tolerances with `--abs-tol` and `--rel-tol`; choose and document them before examining the repeat.
10. `researchctl science-audit prospective-study` shows outstanding integrity gates; `researchctl run --project prospective-study --from S5 --to S5` is allowed only after all machine integrity gates pass. Always run `researchctl audit prospective-study` and review the manuscript and code independently.

Suggested sequencing: verify literature and complete the prior-art matrix **before S2**, even though the operational S5 gate permits later completion. That prevents post-hoc novelty justifications. A separate reviewer should evaluate the manuscript, references, statistics, dataset consent and experiment correctness.

## CLI summary

```text
researchctl protocol scaffold PROJECT    # create blank template if one does not exist
researchctl protocol lock PROJECT        # immutable local protocol/data/idea checksum
researchctl protocol check PROJECT
researchctl literature verify PROJECT --doi DOI
researchctl literature scaffold PROJECT  # create blank nearest-prior-art matrix
researchctl literature audit PROJECT
researchctl claims scaffold PROJECT      # requires 2_paper/results_spec.json
researchctl claims bind PROJECT          # requires valid imported S4 ledger run
researchctl claims check PROJECT
researchctl reproduce-isolated PROJECT [--abs-tol X] [--rel-tol Y]
researchctl science-audit PROJECT
```

## Input format notes

`_inputs/research_protocol.json` is generated blank: don't interpret its sample fields as experimental results. `metric_claims.json` does not contain asserted numeric values; they are computed from actual validated `results.json`. Only a declared result-slot coverage guarantee is possible; assertions in free-form prose, figures containing rasterized text, and causal interpretations still need independent examination.

## Safety / current engineering limits

- Crossref is accessed only by explicit `literature verify`; network connection requires permission and an available service. `verify_doi` checks Crossref metadata **not the paper body**.
- No host execution of S4 code is added. `researchledger reproduce` on imported runs remains forbidden; use `researchctl reproduce-isolated` instead.
- Dependency installation remains offline by default; Docker requires a digest-pinned image. A working LaTeX, Claude Code, PaperOrchestra, and vendor setup is still required.
- The automated repeated run checks *repeatability*, not transfer to an independent execution environment. Claims cannot be promoted to verified by this command.
- A true experiment-before-draft production pipeline, live systematic searches, independent statistical inference, data leakage classifiers, GPU scheduler, review-dashboard, and plugin framework remain future work; see roadmap below.

## Proposed v2.1 roadmap

1. First-class **S1 idea → S2 protocol → S3 experiments → S4 independent replication → S5 manuscript → S6 review** orchestrator, with no experiment-driven paper skeleton.
2. Signed external protocol registration (e.g., OSF integration) and a transparent amendment mechanism with append-only history.
3. Domain-specific dataset validation and leakage tests, including patient/subject-level split audits.
4. True independent reimplementation reproduction and statistical analysis of pre-defined units of independence.
5. Formal manuscript claim markup for prose-level numerical assertions, with one-to-one artifact and review traceability.
6. Specialist adversarial reviewer panels, adaptive task graph, resource scheduling, metrics dashboard and configurable model/provider interfaces.
