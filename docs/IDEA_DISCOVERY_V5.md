# Bundled Idea Discovery v5 — safe opt-in workflow

[← README](../README.md) · [Evidence-first validation](EVIDENCE_FIRST_V2.md)

ResearchLedger bundles **Idea Discovery v5** as a separate ZIP distribution at
`vendor/idea-generation/idea-discovery-v5.zip`. The bundled application contains
literature ingestion, source checks, embeddings/clusters, knowledge graph,
problem-gap analysis, idea evolution, hostile novelty/reviewer attacks, a
falsifiable-hypothesis contract, blind-verifier stages, and an externally
executed minimum viable experiment (MVE) evidence audit.

**The default Factory S1 still uses its own candidate-generation and two-persona
scoring engine.** Bundling the sophisticated v5 tool does not mean every Factory
idea passes through its full nineteen-phase pipeline.

## Prepare a project-local copy, without executing anything

```bash
researchctl idea-discovery inspect
researchctl init "my research question"
researchctl idea-discovery prepare my-research-question
```

The second command requires an existing workspace and extracts V5 to the
project's `_vendor/idea-discovery-v5/` directory. It rejects unsafe archive
paths, symlinks, special entries, unexpectedly large expansions, or an existing
destination; it does **not** call the model, fetch papers, or run generated code.

## Run V5 with the ResearchLedger CLI

The CLI now runs the **real vendored V5 engine** in an isolated project-local subdirectory. Configure its model key privately and supply real papers. Heavy embeddings are opt-in.

```bash
researchctl idea-discovery run my-research-question --topic "My research question" --paper ./papers/source.pdf --dry-run
export ANTHROPIC_API_KEY="..."
researchctl idea-discovery run my-research-question --topic "My research question" --paper ./papers/source.pdf
```

To explicitly adopt a surviving research direction into Factory S1, use `researchctl idea-discovery adopt` with your chosen numeric falsifier and `--acknowledge-manual`. See [native vendor engine guide](NATIVE_VENDOR_ENGINES.md) for an end-to-end example and important evidence-status restrictions.

Read the generated output under `output/` critically. This is **not** a verified
novelty result: paper retrieval and citation accuracy require independent
verification. In V5, an idea without executed MVE evidence should remain
`READY_FOR_MVE`, **not** `GREENLIGHT`. Generated protocols are never
executed automatically by this integration. Keep credentials and patient or
other private data out of external agent prompts unless authorized.

## Integration status

- **Implemented:** archive inspection, safe extraction, an explicit model-backed V5 `run` command, and an operator-approved SHA-bound single-survivor S1 adoption path.
- **Not yet integrated:** automatic V5 execution on every S1 run, independent validation of its literature search, unattended experiment execution, or human-blinded idea-quality benchmarks.
- **Do not assume:** V5's reports constitute independent peer review, empirical
  validation of a hypothesis, or an externally preregistered research protocol.
