# ResearchLedger — Native Idea Discovery V5 + Referee Lean v2 integration audit

**Build date:** 2026-10-12  
**Source:** user-provided `ResearchLedger_Engineering_Hardened_2026-10-12.zip`  
**Scope:** opt-in native vendor execution, explicit V5-to-S1 adoption, real native manuscript reviewer, bounded reviewer/revision loop, offline integration testing, CI and documentation  
**Status:** **local offline engineering checks passed**; live remote provider and scientific-quality validation **not performed**.

## Executive results

| Check | Result | Explanation |
| --- | --- | --- |
| Full first-party regression | **576 passed, 2 skipped, 37 subtests passed** | `python -m pytest -q tests tests_researchledger`; 134.97 seconds, exit code 0. Counts include compatibility/mirror tests. |
| New vendor integration tests | **10 passed** | Native Referee 3-round CLI test, V5 adoption/digest tamper test, Factory guarded editor/re-review, unsafe/missing credentials fail-closed paths. |
| Bundled Idea Discovery V5 tests | **30 passed** | Executed its own `python -m unittest discover -s tests -q` from safely extracted vendor code. |
| Targeted Referee Lean tests | **5 passed** | Bundled Lean contract, evidence/invariant, and strictness regression selection. |
| Native Referee reviewer workflow | **7 stages per round × 3 rounds = 21 completed vendor stages** | Provider deliberately scripted. 1 → 1 → 0 admitted major concerns. No live model inference. |
| Factory S3/S5 native bridge | **Tested with mocked reviewer/editor seams** | Correct contract/report formats; revised TeX passes no-invented-number/citation guard; S5 audit status remains carefully qualified. |
| Research manuscript PDF package intake | **Passed** | Native Referee `inspect-package` on included `Paper/AutoResearch_Ledger_Revision_Integrity.pdf`; no scientific content review performed. |
| Scientific experiment / independent reproduction | **Not run** | Docker, external model credentials and authentic datasets unavailable in this runtime. |

## Important difference from prior release

Previously, Factory's `referee-full` mode asked its existing agent to read some bundled Referee prompts. It was **not an invocation of the Referee engine**. Idea Discovery V5 was extractable but not executable through `researchctl` and its outputs could not be adopted into S1. Both issues are addressed **opt-in** without breaking the legacy paths.

## New code paths

- `factory/integrations/referee_native.py`: strict, subprocess-based adapter to *real* Referee Lean v2 `referee.cli`; separate per-project run directories, structured status/invariant accounting, native document inspection, manuscript comparison, multi-version reevaluation, fail-closed credential requirements.
- `factory/integrations/idea_discovery.py`: safe per-project V5 extraction retained; new native `run` command with `--dry-run`, paper copying, timeout, no auto MVE execution, and explicit `adopt` mapping.
- `factory/steps/idea.py`: explicit V5 S1 adoption (one survivor, no invented peer scores), source-checksum and selected-idea consistency checks, falsifier contract, local provenance annotation.
- `factory/steps/review.py`: optional `review_agent=referee-native`; native referee concerns feed the guarded Claude Code revision contract. Every revision must rebuild before it can be reevaluated. S3 runs a single native review; S5 repeats it with new native model calls and requires a clean report-exportable state. Rejected candidates and remaining concerns cannot pass the S5 stop gate.
- `factory/pipeline/stages.py` + `factory/config.py`: preserves existing review scheme while explicitly supporting the native backend without fabricating 49-dimensional AI review scores.
- `factory/cli/main.py`: adds `idea-discovery run/adopt` and `referee inspect/review/iterate/compare`.
- `pyproject.toml`, CI, docs, and Makefile: adds optional reviewer/idea dependencies, a native-vendor smoke CI job, documented model configuration and reproducible sample outputs.

## Demonstration A — one research idea

**Topic:** detecting evaluation leakage in brain-tumor MRI segmentation.

**Selected illustrative direction:** *Multi-level leakage stress test for brain MRI segmentation*.

**Scientific hypothesis (unverified):** compared with random-slice evaluation, patient- and acquisition-site-disjoint testing may decrease mean Dice by more than **0.03** in an appropriately licensed, sufficiently heterogeneous dataset.

**Proposed falsifier:** an observed paired Dice gap of **≤0.03** under a preregistered protocol disconfirms the stated magnitude. This is a *proposed threshold*, not an observed result or a validated novelty claim.

Three mechanistically different candidate directions and two deliberately scripted review personas were fed through **Factory's real generation-response validation, falsifiability and idea-selection code**. `MRI-01` was selected with an **illustrative scripted aggregate score of 7.9/10**. V5's **real JSON schema and semantic checks** passed on the corresponding formatted idea object. V5's *generative* research/attacker loops were **not run** without model API access.

Readable example: `examples/native_vendor_demo/sample_outputs/selected_idea.md`.

## Demonstration B — three rounds of reviewer/author revision

Each round passed its manuscript through the **actual Referee Lean v2 engine** with a version-specific, authored scripted fixture. The vendor executed its seven stages including structured review, hard evidence admission, verification and final report export. The actual native `compare-revision` command calculated diffs between editions.

| Round | Manuscript | Admitted major concern | Test action |
| --- | --- | --- | --- |
| 1 | `v1_original.md` | 1 — unsupported causal inference from uncontrolled pre/post cohort | Rewrite as within-group description |
| 2 | `v2_reframed.md` | 1 — new unsupported all-population extrapolation | Narrow scope, describe uncertainty and limits |
| 3 | `v3_limited.md` | 0 admitted major concerns in programmed test | Stop; do **not** infer scientific acceptance |

**What this proves:** the native agent CLI runs, generates traceable reviewer artifacts, rejects/admits concern objects, checks invariants, tracks revisions and supports multiple passes. **What it does not prove:** live scientific critique, effective model-generated editing, source-level novelty coverage, or an independent expert's agreement. Example corrections were written explicitly rather than autonomously generated.

See `examples/native_vendor_demo/sample_outputs/review_cycle_report.json` for round counts, comparisons and status; `sample_outputs/referee_round_*.md` for review text; and `docs/NATIVE_VENDOR_ENGINES.md` for actual configuration.

## Live execution recipe

```bash
python -m pip install -e '.[dev,referee,idea-discovery]'
researchctl init "my research topic"
researchctl idea-discovery prepare my-research-topic
researchctl idea-discovery run my-research-topic --topic "..." --paper ./references/real_paper.pdf --dry-run
# Set ANTHROPIC_API_KEY privately before genuine V5 generation.
researchctl idea-discovery run my-research-topic --topic "..." --paper ./references/real_paper.pdf

# After independent review of an actual V5 survivor:
researchctl idea-discovery adopt my-research-topic --idea-id IDEA-001 --metric my_metric \
  --threshold 0.03 --falsifier-statement "Reject if the observed metric gap does not exceed 0.03." \
  --acknowledge-manual
researchctl run --project my-research-topic --from S1 --to S1

# For full native scientific review, configure OPENAI_API_KEY and REFEREE_MODEL.
researchctl referee inspect ./manuscript.pdf
researchctl referee review my-research-topic ./manuscript.pdf --model "$REFEREE_MODEL" --mode deep
researchctl referee iterate my-research-topic ./v1.md ./v2.md ./v3.md --model "$REFEREE_MODEL"
```

In Factory's `_inputs/context.json`, `"review_agent": "referee-native"` opts S3/S5 into the real native engine. The Factory revision editor continues to need authenticated Claude Code and LaTeX; the remote Referee model needs a compatible API configuration. Never save API keys in source control. Live API invocation costs depend on your providers.

## Remaining constraints / follow-up verification required

1. **Model-backed V5 end-to-end generation, literature retrieval and evidence adjudication:** requires an appropriately configured Anthropic API and legally provided paper corpus; no live model credentials were available in this environment.
2. **Model-backed Referee and autonomous manuscript refinement:** requires an OpenAI-compatible endpoint, Claude Code (Factory reviser), working LaTeX/BibTeX and independent editorial audit. Unit and scripted-stage executions do not substitute for this.
3. **Independent scientific correctness / human reviewer benchmarks:** no blinded experts, held-out annotated papers or demonstrated defect precision/recall were evaluated; evidence-first audit is not Q1 certification.
4. **Actual research computations:** Docker was unavailable in this environment; no datasets or experimental claim outputs were generated.
5. **Older study trajectories:** two history-dependent tests were skipped because the original archived project workspaces were absent; the corresponding evidence files were not invented or modified.
6. **Research data protection:** V5 and Referee model-backed execution can transmit supplied context to external APIs. Require consent, licensing and data-governance checks before submitting confidential materials.
7. **Native execution as a separate component:** V5 runs explicitly and is not forcibly invoked for every Factory S1. This avoids recasting a preliminary `READY_FOR_MVE` idea as empirical `GREENLIGHT` or silently spending significant model credits.

## Files left unchanged

Original manuscript PDFs and prior experimental-study materials were preserved. The included `Paper/AutoResearch_Ledger_Revision_Integrity.pdf` was checked byte-identical to the preceding hardening archive (SHA-256 `af206b1311202f9c2861ee6f4607b99785ef43438667edae1fcccd065c93f551`). All example candidate hypotheses, test reviewer responses and scripted scores are clearly isolated under `examples/native_vendor_demo/`.
