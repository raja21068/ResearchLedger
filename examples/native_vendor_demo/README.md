# Reproducible offline demonstration — Idea Discovery V5 + Referee Lean v2

**Read first:** These are **software integration tests**, not research study results or independent scientific peer review. The sample papers and reviewer responses are deliberately authored scripts. Native Referee's seven-stage Lean execution and evidence gates actually run, but no model is queried in this offline mode.

## Run

From the ResearchLedger repository root:

```bash
python examples/native_vendor_demo/generate_fixtures.py
python examples/native_vendor_demo/run_offline_demo.py --workspace ./tmp/native-vendor-proof
python -m pytest -q tests/test_vendor_native_integration.py
```

### Example 1 — Ideas and falsification

- **Topic:** detecting evaluation leakage in brain-tumor MRI segmentation.
- **Three illustrative candidate research ideas** with mechanistically distinct hypotheses and numerical falsifiers.
- **Two scripted reviewer personas** score candidates; Factory's real `generate` orchestration, candidate validation, `select`, and falsifiability/ranking gate are executed.
- **Selected idea:** `MRI-01`, source leakage and multi-level split validation; see [selected_idea.md](sample_outputs/selected_idea.md).
- **Illustrative aggregate score:** 7.9/10. This is **not** a measured novelty or feasibility result.
- **V5 integration:** project-safe archive extraction plus real `schema_validator.validate_json()` and `validate_semantics('idea_report')`, both passed; the full V5 multi-agent research pipeline was not run without credentials. See [the valid sample V5 report](sample_outputs/v5_schema_validated_idea_report.json).

### Example 2 — Three manuscript review cycles

| Round | Draft | Synthetic reviewer finding | Native Referee admitted major concerns |
| --- | --- | --- | ---: |
| 1 | [v1_original.md](v1_original.md) | Uncontrolled cohort is described as causal | **1** |
| 2 | [v2_reframed.md](v2_reframed.md) | Causality corrected; unsupported generalization added | **1** |
| 3 | [v3_limited.md](v3_limited.md) | Scope limited to illustrative sample | **0** |

Review runs use native `referee.cli review` with explicitly named [scripted responses](scripted_round_1.json), [round 2](scripted_round_2.json) and [round 3](scripted_round_3.json). Native `compare-revision` runs between drafts. See [machine-readable test history](sample_outputs/review_cycle_report.json) and rendered review reports for [round 1](sample_outputs/referee_round_1.md), [round 2](sample_outputs/referee_round_2.md) and [round 3](sample_outputs/referee_round_3.md).

> **Critical caveat:** Draft changes are hand-prepared example strings. Neither autonomously generated reviewer insights nor automatically improved manuscript quality can be inferred from this demonstration. No uncertainty intervals, control group, actual human observations, or external citations were supplied: it is a synthetic example, not original research.

### Real manuscript structural intake

The same Referee CLI was separately run with `inspect-package` on `Paper/AutoResearch_Ledger_Revision_Integrity.pdf`; this verified package intake and SHA-256 tracking only. It was **not** a live scientific peer review of the paper.

## Run with actual model providers

Use the main [native integration guide](../../docs/NATIVE_VENDOR_ENGINES.md). Live V5 generation requires an Anthropic API key and legitimate source-paper corpus. Native Referee requires an OpenAI-compatible provider; the Factory LaTeX reviser additionally requires authenticated Claude Code. Never commit keys, undisclosed data, or private manuscripts to a public repository.
