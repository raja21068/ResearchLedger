> **Referee Lean v2:** The CLI now defaults to the 7-stage Lean v2 initial-review pipeline (`--pipeline lean`). The original full pipeline remains available with `--pipeline legacy`. Programmatic `ReviewConfig()` retains `legacy` by default for backward compatibility; set `pipeline="lean"` explicitly when embedding. See `docs/LEAN_V2.md`.

# Referee

Referee is an **evidence-grounded scientific peer-review platform** for manuscript diagnosis, formal review support where policy permits, revision/rebuttal auditing, reproducibility checks, and review-quality control. Its evidence-locking layer prevents unsupported major criticisms from reaching the final report.

Its governing principle is simple:

> No decisive judgment without a traceable evidence path. No major criticism without a closure path. No major criticism reaches the final review without deterministic admission and independent verification.

The platform combines a multi-agent scientific review kernel with native manuscript-package inspection, scholarly-evidence adapters, claim-centered reviewer routing, provenance validation, reporting-guideline routing, reproducibility auditing, revision/rebuttal comparison, benchmarking, a local review workbench, and checksum-verifiable review handoff bundles.

## Scientific review pipeline

1. safe manuscript and package intake;
2. policy/security/confidentiality gate;
3. study and domain classification;
4. strict core peer-review pass producing the canonical claim registry, evidence anchors, strengths, major/minor concerns, observations, and confidence fields;
5. dynamic claim-centered review plan;
6. equation, unit, denominator, and numerical-consistency audit;
7. literature/novelty evidence acquisition;
8. parallel specialist review;
9. reviewer consensus/disagreement mapping and, in exhaustive mode, independent review trajectories;
10. red-team and steelman passes;
11. hard claim/anchor/provenance + evidence-entailment gate;
12. fresh-context independent judge that sees only manuscript content, one canonical proposed concern, and its frozen hash-bound claim/evidence bundle;
13. final deterministic admission followed by post-validity pairwise priority;
14. anchor/provenance and closure-quality audit;
15. repeatability/reliability and purpose-specific revision/rebuttal/meta-review workflows;
16. critical scientific gates and progressive synthesis;
17. journal calibration after scientific judgments are fixed.

A persuasive model response cannot bypass the evidence lock. Major comments require real claim IDs, source-resolving evidence anchors, verified anchor text/content, an evidence-entailment pass, a specific failure mechanism, proportionate scientific consequence, minimum resolution, testable closure criterion, numeric reviewer confidence, an explicit steelman and survival reason, a fresh independent verifier context, and an unchanged frozen evidence bundle. Model-written verification fields are never accepted as proof: Referee recomputes identifiers, anchor integrity, closure properties, verifier independence, and frozen hashes before admission.


## Core reviewer and independent judge

`core/PEER_REVIEW_PROMPT.md` is the authoritative model-facing review contract. Its exact top-level JSON is validated with `schemas/core_peer_review.schema.json`, then cross-checked deterministically for ID integrity, anchor resolution, external-evidence provenance, confidence bounds, duplicate concerns, closure properties, and internal consistency. The model-written `verification_status` on evidence anchors is deliberately ignored as proof.

`core/INDEPENDENT_VERIFIER_PROMPT.md` is a separate judge contract. The judge never receives generator identity, red-team notes, consensus traces, provenance-gate internals, or hidden reviewer reasoning. It receives manuscript content, a frozen claim/anchor bundle, and one proposed concern and returns only `verified`, `rejected`, or `uncertain` plus bounded entailment judgments. `schemas/independent_verifier.schema.json` constrains that output. Referee then independently recomputes all mechanically verifiable conditions before assigning its own `verification_status`.

## Platform capabilities

Referee includes:

- 56 scientific review skills and 24 specialist reviewer roles;
- domain packs for electrochemistry/fuel cells, materials, environmental/process engineering, microbiology/omics, energy/LCA/TEA, computational science, ML-for-science, and experimental metrology;
- DOCX/OOXML/OMML inspection, including tracked changes, comments, plaintext-math remnants, tables, media, and external relationships;
- LaTeX, JATS/XML, notebook, spreadsheet, CSV, Markdown, PDF, and text ingestion;
- Crossref, OpenAlex, Semantic Scholar, PubMed, arXiv, and Europe PMC scholarly adapters with normalization, deduplication, ranking, caching, and citation-graph support;
- genuinely distinct DAGs for initial, revision, rebuttal, meta-review, editorial-screen, and reproducibility review modes;
- reviewer consensus/disagreement, exhaustive-mode N-way independent trajectories, and post-validity pairwise priority tools;
- deterministic provenance, entailment, contradiction, proof-burden, and closure checks;
- reproducibility inspection for data/code/environment/notebook packages without executing untrusted manuscript code by default;
- persistent checkpoints, resumable runs, event logs, budgets, retries, and run manifests;
- a local run registry and human review workspace kept separate from model-generated scientific state;
- a browser workbench for concerns, evidence, artifacts, and human closure status;
- frozen handoff bundles with a closure matrix, quality snapshot, manifest, and SHA-256 file hashes;
- Markdown, JSON, HTML, CSV, JSONL, and evidence-graph outputs;
- a CLI, optional FastAPI server/dashboard, and optional MCP interface;
- synthetic benchmark corpora plus binary Office/PDF/notebook/LaTeX regression fixtures.

## Architecture

The executable runtime is under `referee/`.

- `stages/` — review graph and stage execution;
- `ingestion/` — manuscript/package structural inspection;
- `scholarly/` — scholarly providers and federated search;
- `reviewers/` — reviewer roster, routing, consensus, disagreement, calibration;
- `verification/` — anchor, entailment, contradiction, burden, provenance, and closure checks;
- `reproducibility/` — data/code/environment/package inspection;
- `comparison/` — revision and rebuttal analysis;
- `reporting/` — reporting-family routing;
- `domain_packs/` — field-specific reviewer routing;
- `lifecycle/` — run registry and human editorial workspace;
- `finalization/` — quality snapshots and frozen review handoffs;
- `profiles/` — named configuration profiles;
- `providers/` and `plugins/` — replaceable model/search/plugin integrations;
- `cache/`, `security/`, `observability/`, and `exports/` — infrastructure;
- `server/` and `mcp/` — optional interactive/service surfaces;
- `evals/` and `benchmarks/` — deterministic evaluation support.

The scientific control plane remains in `core/`, `agents/`, `skills/`, `schemas/`, `guidelines/`, and `templates/`.

## Review depth and review purpose

Depth and purpose are independent.

Depth:

- `standard` — lower call/search budgets and a compact specialist panel;
- `deep` — broad specialist coverage and repeatability checks;
- `exhaustive` — highest configured budgets, more specialists, independent trajectories, and repeated decisive judgments.

Purpose:

- `initial` — first-pass manuscript review;
- `revision` — test whether a revised manuscript closes prior scientific concerns;
- `rebuttal` — audit reviewer comment → response → changed-manuscript evidence;
- `meta_review` — preserve and synthesize reviewer agreement/disagreement;
- `editorial_screen` — identify fatal incompleteness before a full review;
- `reproducibility` — focus on data, code, environment, and package evidence.

Built-in configuration profiles are available for balanced review, editorial screening, full audit, reproducibility, and revision closure.

## Install

Core runtime:

```bash
pip install -e .
```

Useful extras:

```bash
pip install -e '.[office,pdf,scholarly,validation,server]'
```

Or all optional runtime features:

```bash
pip install -e '.[all]'
```


## Model/provider configuration

The default CLI provider is OpenAI-compatible. Set credentials and a model explicitly rather than relying on a hard-coded model name:

```bash
export OPENAI_API_KEY="..."
export REFEREE_MODEL="<model-id>"
# Optional for another compatible endpoint:
export OPENAI_BASE_URL="https://api.openai.com/v1"
```

For deterministic offline development and regression tests, use the scripted provider with `--provider scripted`. Provider implementations are replaceable; the scientific admission, provenance, and closure rules remain inside Referee.

## CLI examples

Run a balanced review:

```bash
referee review manuscript.docx supplement.docx --profile balanced
```

Run a full audit:

```bash
referee review manuscript.docx supplement.docx data.xlsx analysis.ipynb --profile full-audit
```

Inspect a package without model calls:

```bash
referee inspect-package manuscript.docx supplement.docx data.xlsx analysis.ipynb
```

Compare manuscript revisions:

```bash
referee compare-revision original.docx revised.docx
```

Audit a response letter:

```bash
referee audit-rebuttal response_to_reviewers.docx
```

List indexed runs and configuration profiles:

```bash
referee list-runs
referee list-profiles
```

Freeze a completed review into a handoff bundle:

```bash
referee finalize-run runs/<run-id>
referee verify-handoff runs/<run-id>/artifacts/referee-handoff.zip
```

Attach human notes without modifying model-generated scientific state:

```bash
referee add-note runs/<run-id> "Check the revised normalization against Table S4."
referee set-concern-status runs/<run-id> MC003 resolved --note "Verified in revised Fig. 5 and Methods."
```

Start the local workbench:

```bash
referee serve --run-root runs --port 8765
```

## Run outputs

A completed run can contain:

- `core_peer_review.json`, `core_peer_review_validation.json`, `review.md`, `review.json`, and `review.html`;
- `major_concerns.csv`;
- document/package/reporting/reproducibility audits;
- review plan and reviewer-disagreement artifacts;
- concern-admission and independent-verification records;
- provenance report and evidence graph;
- `events.jsonl` plus stage checkpoints;
- `run_manifest.json` containing final state and input hashes;
- optional `workspace.json` containing human notes/statuses;
- `quality_snapshot.json` and `closure_matrix.csv` after finalization;
- `handoff_manifest.json` and `referee-handoff.zip` for frozen handoff.

## Benchmarks and regression fixtures

`benchmark_corpus/` contains 1,057 automated validation cases: the original scientific/domain/revision/rebuttal corpora plus dedicated major/minor/observation severity-calibration cases. The 624 positive scientific/domain cases retain structured mechanism gold, while severity calibration has its own class-balanced structured gold. Gold labels are kept outside model prompts by the end-to-end benchmark runner. Synthetic benchmark content must never be used as scientific evidence.

Run a hidden-gold model benchmark (limited by default to control cost):

```bash
python scripts/run_benchmark_suite.py --model "$REFEREE_MODEL" --limit-per-corpus 10 --repeats 3
# complete validation corpus:
python scripts/run_benchmark_suite.py --model "$REFEREE_MODEL" --full
```

Counterfactual defect→fixed sensitivity and component ablations are separate:

```bash
python scripts/run_mutation_benchmark.py --model "$REFEREE_MODEL"
python scripts/run_ablation_benchmark.py --model "$REFEREE_MODEL"
```

`benchmark_corpus/REAL_WORLD_BENCHMARK.md` defines the adjudicated atomic-concern format for a 100–300+ public-paper expert benchmark. `benchmark_corpus/BLINDED_EXPERT_STUDY.md` and `scripts/prepare_expert_study.py` prepare source-blinded human evaluation without fabricating human judgments inside the repository. See `docs/evaluation/VALIDATION.md` for the validation boundary and benchmark protocols.

`fixtures/` contains binary regression artifacts, including DOCX files with genuine OMML equations, deliberately broken plaintext `R^2`, wide tables, comments, tracked changes, spreadsheets, notebooks, LaTeX, and PDFs.

## Validation campaign

Referee freezes its validation protocol before official model-backed results are interpreted. The frozen contract hashes the core review/verifier/evaluator prompts, JSON schemas, hidden structured gold, benchmark corpus, runtime code, success criteria, and configuration. Each full campaign then writes a separate immutable experimental configuration manifest containing the exact reviewer, verifier, judge A, judge B, adjudicator, search, temperature, randomness, repeatability, and ablation settings. Evaluator independence is explicitly classified; same-model judging is labeled internal validation rather than independent validation. Use `--require-independent-evaluation` to require cross-model judging for an external validation claim.

Citation verification separates bibliographic provenance from scientific proposition entailment. Exact non-negated quotations may resolve deterministically; paraphrased propositions require an independent entailment check, and token overlap alone cannot establish support. Before the main benchmark, the full command also executes model-backed behavioral adversarial workflows separately from static-contract and deterministic-integrity checks.

Run the deterministic integrity campaign first:

```bash
referee validate --suite integrity --output validation-results
```

Run the complete hidden-gold campaign from one command:

```bash
referee validate --suite full \
  --model "$REFEREE_MODEL" \
  --verifier-model "$REFEREE_VERIFIER_MODEL" \
  --judge-model-a "$REFEREE_JUDGE_MODEL_A" \
  --judge-model-b "$REFEREE_JUDGE_MODEL_B" \
  --adjudicator-model "$REFEREE_ADJUDICATOR_MODEL" \
  --repeats 3 \
  --output validation-results
```

Omit the optional judge-model variables to reuse the configured reviewer/verifier models with fully fresh judge contexts. Using a different capable model family for benchmark judging is preferred when available. `--limit-per-corpus` exists only for development smoke tests; omit it for an official campaign.

The campaign writes `validation_summary.json`, `per_case_results.jsonl`, `metrics.csv`, `domain_metrics.csv`, `ablation_metrics.csv`, `repeatability_metrics.csv`, `citation_metrics.csv`, `failed_cases.jsonl`, immutable `run_manifest.json`, `results_manifest.json`, and `validation_report.html`. Primary metrics remain separate rather than being collapsed into an opaque overall score.

The deterministic adversarial suite contains 43 provenance, identifier, hash-mutation, benchmark-gaming, review-behaviour, citation/literature, prompt-injection, and revision/rebuttal attacks. Critical deterministic integrity properties must pass at 100% before a full model-backed campaign can start.

Repository/package self-validation remains available with:

```bash
python scripts/rebuild_package_metadata.py
python scripts/validate_package.py
```

Offline release validation checks code/schema integrity and validation readiness; it does **not** fabricate scientific benchmark performance. Official performance claims require a completed model-backed campaign tied to its frozen manifests.

## Portable prompt

`dist/REFEREE_SINGLE_PROMPT.md` is available for environments that cannot execute Python. It contains the authoritative core peer-review prompt, the separate independent-verifier prompt, and the complete scientific skill layer. The strongest guarantees require the runtime because concern admission, independent verification, state, budgets, retries, provenance checks, package inspection, and final handoff integrity are enforced outside the model.

## Security and confidentiality

Manuscripts are always treated as untrusted data. Prompt-like text inside a manuscript cannot become runtime instruction. Untrusted research code is inspected but not executed by default. Formal confidential peer review remains subject to the target journal or publisher's current AI and confidentiality rules; the package never assumes AI assistance is permitted.

## Scope and responsibility

Referee is decision support for scientific review, not an autonomous publication decision-maker. Human reviewers and editors remain responsible for scientific judgment, confidentiality, conflicts of interest, and compliance with journal policy. Formal confidential peer review should only use Referee where the relevant journal or publisher permits the intended AI-assisted workflow.

## License

Referee is distributed under the MIT License. See `LICENSE` and `THIRD_PARTY_NOTICES.md`.
