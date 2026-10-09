# Referee Lean v2 quick note

The CLI defaults to the Lean v2 initial-review pipeline. Explicit usage:

```bash
referee review manuscript.pdf --pipeline lean --mode deep --model <model>
```

Use `--pipeline legacy` to reproduce the original full review DAG.

# Quickstart — Referee

Install editable with common extras:

```bash
pip install -e '.[office,pdf,scholarly,validation]'
```

Configure the default OpenAI-compatible provider:

```bash
export OPENAI_API_KEY="..."
export REFEREE_MODEL="<model-id>"
```

Run a balanced review:

```bash
referee review paper.docx supplement.docx --profile balanced
```

Run the most intensive built-in profile:

```bash
referee review paper.docx supplement.docx data.xlsx analysis.ipynb --profile full-audit
```

Audit the submission package before model calls:

```bash
referee inspect-package paper.docx supplement.docx data.xlsx analysis.ipynb
```

Compare a revision and audit a response letter:

```bash
referee compare-revision original.docx revision.docx --json-out revision_diff.json
referee audit-rebuttal response.docx
```

Inspect local runs and freeze a completed review:

```bash
referee list-runs
referee finalize-run runs/<run-id>
```

Start the optional browser workbench:

```bash
pip install -e '.[server]'
referee serve
```

Run deterministic structural tests:

```bash
referee benchmark evals/cases/major_comment_cases.json
pytest -q
```

Run a bounded hidden-gold end-to-end benchmark:

```bash
python scripts/run_benchmark_suite.py --model "$REFEREE_MODEL" --limit-per-corpus 10 --repeats 3
```

Run counterfactual mutation and architecture-ablation benchmarks:

```bash
python scripts/run_mutation_benchmark.py --model "$REFEREE_MODEL"
python scripts/run_ablation_benchmark.py --model "$REFEREE_MODEL"
```


Run the deterministic 43-case integrity campaign:

```bash
referee validate --suite integrity --output validation-results
```

Run the complete frozen validation campaign (all benchmark corpora, counterfactuals, repeatability, ablations, citation metrics, and reports):

```bash
referee validate --suite full --model "$REFEREE_MODEL" --repeats 3 --output validation-results
```

For independent benchmark adjudication, optionally pass `--judge-model-a`, `--judge-model-b`, and `--adjudicator-model`.

For evaluation semantics and the real-paper/blinded-expert protocols, read `docs/evaluation/VALIDATION.md`.

For architecture and development details, read `docs/architecture/`, `docs/guides/`, and `CONTRIBUTING.md`.
