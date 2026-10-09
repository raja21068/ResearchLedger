# Paper Factory × ResearchLedger — Evidence-first v2.0.1 (audited)


> **v2.0 engineering update:** The new opt-in `science_mode="validation"` requires a locked prospective research protocol, verified bibliographic *metadata* and a manually evaluated prior-art matrix, explicit measured metric/claim bindings, registered-seed arithmetic, and an isolated Docker repeat before S5 can finalize a manuscript. These are machine-checkable integrity gates, **not** independent proof of scientific validity. The legacy S1→S2→S3→S4→S5 workflow is retained for compatibility. For the code and release audit see [docs/DEEP_CODE_AUDIT_2026-10-08.md](docs/DEEP_CODE_AUDIT_2026-10-08.md). See [the full operator guide](docs/EVIDENCE_FIRST_V2.md) and [START_HERE.md](START_HERE.md).

**One project workspace, two complementary responsibilities:** Paper Factory runs the five-stage idea → draft → review → Docker experiment → measured revision pipeline, while ResearchLedger records scientific hypotheses, immutable experiment manifests, evidence status, and claim relationships. **A successful experiment is only checked pilot evidence, not independent scientific verification or reproduction.**

This is a working software integration for research prototyping, **not an automatic Q1-paper or scientific correctness certifier**. Full Claude Code, Docker, LaTeX, and research-domain validation must run on the user's own machine.

## Install and start

Requirements: **Python 3.10+**, `pip`, Claude Code CLI authenticated, `pdflatex`/`bibtex`, Docker Desktop (for generated experiments), the PaperOrchestra Claude Code skill and the bundled PaperCompiler/Referee vendor components. Windows: use PowerShell; Docker Desktop must be running. **No API key is needed for the factory when using the Claude Code login.**

```bash
python -m pip install -e .
researchctl doctor
researchctl init "brain tumor robustness"
# Edit <path printed by researchctl init>/_inputs/topic.md
researchctl run --project brain-tumor-robustness
researchctl status brain-tumor-robustness
researchctl ledger brain-tumor-robustness
researchctl audit brain-tumor-robustness
```

`researchctl init` writes new projects to `~/.local/share/paperfactory/workspaces/` by default (or `PAPERFACTORY_WORKSPACES` if set). An existing source-checkout `workspaces/` directory is used for backward compatibility. Follow the absolute workspace path printed by the command. **The source archive uses editable installation (`pip install -e .`); a standalone non-editable wheel is not yet supported because external vendor and template resources are not packaged into it.**

`researchctl init` defaults to exploration mode and enables the integrated ledger by writing `_inputs/context.json` with `"ledger_enabled": true` and creates a per-project ResearchLedger directory. If migrating an existing Paper Factory project, back it up, add `"ledger_enabled": true` to `_inputs/context.json`, and use `researchctl resume PROJECT` **starting from stale stages**; ledger-enabled S1 and S4 must be rerun if their receipts are missing. A run with `ledger_enabled` explicitly false retains older pipeline behavior.

Run tests separately or together:

```bash
python -m unittest discover -s tests -p 'test_*.py'
python -m pytest -q tests_researchledger
researchctl test
```

## Integration boundaries

| Stage | Paper Factory operation | ResearchLedger integration |
|---|---|---|
| S1 | Candidate idea generation/selection with falsifiability gate | Injects relevant ResearchLedger research methodology when ideas are generated; creates a **hypothesis** claim C### |
| S2 | Draft a paper containing EMPTY empirical slots | Result IDs form explicit future measurement contracts; no guessed outcomes |
| S3 | First-pass Referee assessment | Injects peer-review methodology as a checklist; model feedback remains a heuristic, not a scientific acceptance verdict |
| S4 | Generate code and run it inside network-isolated Docker | Records the ALREADY executed result as external R####, snapshots metrics and artifacts, creates linked E### with **checked** status |
| S5 | Insert actual results and run manuscript refinement | Blocks if the corresponding ledger receipt, metrics digest, code digest, spec or dataset have changed, or if ledger graph integrity fails |

`researchctl ledger PROJECT` reports the claim/evidence/run graph; `researchctl methodology idea|experiment|review` shows stage-specific ResearchLedger method guidance injected into the corresponding agent prompts. The standalone `researchledger` CLI remains included: enter a project workspace and use `researchledger validate --strict`, `researchledger report`, `researchledger trace C001`, etc.

**External-run safety:** Paper Factory's Docker sandbox remains the only execution path for S4-generated code. Importing a result does **not** execute it through `researchledger run` on the host. `researchledger reproduce R####` refuses to replay imported runs as host commands. To independently reproduce, use a separate isolated experimental procedure, compare predictions, metrics and artifacts, and document the comparison under ResearchLedger without falsifying the imported run's provenance.

## Typical project tree

```text
<workspace directory>/<project>/
  _inputs/                 # user inputs; context.json enables ledger
  1_idea/                  # S1 idea selection
  2_paper/                 # draft and results_spec.json
  3_review/                # review report
  4_code/                  # Docker-generated repo + measured results.json
  5_refine/                # filled paper and iterative review
  control/
    checkpoint.json        # signatures of stage inputs and outputs
    ledger_idea.json       # selected hypothesis mapping to C###
    ledger_s4_receipt.json # tamper-evident link to R#### and E###
    quality_report.json    # automated, not an external scientific review
  .researchledger/         # ledger marker/index
  research/
    claims/C001.md         # hypothesis -> provisional with checked evidence
    evidence/E001.md      # checked, NOT verified evidence
    runs/R0001/
      manifest.json        # hashed, sealed external Docker execution record
      metrics.json         # exact copied results.json, with SHA-256
      environment.json     # importing host environment, NOT container env
      artifacts/           # snapshots of input spec, results and logs
```

The imported manifest includes Docker image, generated repo digest, dataset digest (if present), source experiment digest, and `external_execution=true`, `replay_supported=false`, `reproducibility_status=NOT_INDEPENDENTLY_REPRODUCED`. Its `environment.json` describes the *importing host*, not the run container; container metadata is in the external provenance field. Every run is connected into ResearchLedger's hash-linked run history. Modifying previously sealed manifests, metrics or artifacts is detected by validation.

## Scientific restrictions

- ResearchLedger methodology skills are **instructions, not proof of literature searches or verified novelty**. They are injected as bounded checklists; they do not autonomously search the literature or conduct independent peer review.
- S4 records `checked` evidence only when the result-slot contract, successful sandbox attempt and source hashes agree. A successful process exit cannot establish scientific validity, fair baselines or meaningful statistics.
- Supporting evidence automatically makes a hypothesis **provisional**, never **supported**. ResearchLedger promotes it only with verified evidence and consistent graph status. This integration does not automatically promote evidence to `verified`.
- The generated code and datasets must be independently examined. A result produced on synthetic data must remain labeled *pilot/synthetic*. The manuscript may not assert external validity on that basis.
- The standalone ResearchLedger CLI can execute arbitrary commands when explicitly invoked by an operator. **Do not use it to re-run untrusted generated code outside Docker.**
- Automated Referee score thresholds do not certify Q1 quality, acceptance or even correctness.

## Compatibility, licenses and source provenance

Integrated from **Paper Factory v0.2** and **ResearchLedger v2.2** as supplied by the user. `factory/` and the five-stage controller are preserved; `researchledger/`, its `schemas/`, the complete `skills/` library and `reference/` documentation are preserved. The ResearchLedger upstream Apache 2.0 license text is retained in `licenses/RESEARCHLEDGER_APACHE-2.0.txt`; additional vendored code carries its own notices. Avoid implying ResearchLedger itself is MIT-licensed because the actual source archive contains Apache 2.0 text.

Old generated workspaces and `.git` history are deliberately excluded. Keep backups of research outputs separately. See [docs/INTEGRATION.md](docs/INTEGRATION.md) and [docs/SCIENTIFIC_READINESS.md](docs/SCIENTIFIC_READINESS.md), plus the original Paper Factory [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).
