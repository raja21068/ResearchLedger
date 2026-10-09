# Referee validation contract

This directory freezes Referee's evaluation protocol before official model-backed benchmark results are interpreted. `SUCCESS_CRITERIA.json` is predeclared. `VALIDATION_RELEASE.json` hashes the review/verifier/evaluator prompts, schemas, hidden gold, benchmark corpus, scientific runtime, success criteria and configuration.

Validation deliberately distinguishes three adversarial layers:

1. **Static contract tests** — required instructions, schemas and security boundaries exist.
2. **Deterministic integrity tests** — IDs, hashes, provenance, anchors and state invariants behave correctly.
3. **Model-backed behavioral attacks** — actual review/rebuttal workflows are executed against missing-reporting, optional-experiment, noncausal, prompt-injection and promise-without-change attacks.

The first two can run offline with `referee validate --suite integrity`. The third is executed before the expensive benchmark in `referee validate --suite full` and is reported separately; static prompt checks never count as behavioral evidence.

Every full campaign records an evaluator-independence classification. Same-model fresh-context judging is labeled **internal validation**, never independent external validation. Use `--require-independent-evaluation` when an external validation claim requires at least cross-model judging.

Changing any frozen component requires regenerating the frozen manifest **before** official results are inspected. Prior result manifests are not overwritten.

## Lean v2 status

Referee Lean v2 is a new experimental scientific-review configuration. The frozen validation release records the exact package state, but **does not claim that Lean v2 has already matched or exceeded the legacy system on real-paper expert benchmarks**. Use `--pipeline legacy` for historical legacy comparisons and benchmark `lean` versus `legacy` before making performance claims. The original v1 manifest is retained as `VALIDATION_RELEASE_LEGACY_V1.json`.
