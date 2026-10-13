# ResearchLedger source engineering review — 12 October 2026

> This report concerns the **uploaded ResearchLedger-main.zip** source snapshot. It is not a scientific peer review, formal security penetration test, live GitHub CI report, or claim that the code will work across every deployment.

## Engineering approach

1. Safely unpacked and inspected the source archive, first-party Factory, ResearchLedger, CI, documentation, and vendor boundaries.
2. Ran the existing unit tests to locate reproducible failures; added targeted tests for newly fixed boundary cases.
3. Inspected the bundled Idea Discovery v5 source *inside the ZIP*; documented its independent invocation and distinguished it from S1.
4. Maintained the original evidence records without generating substitute historical experiments or altering the published empirical result summaries.
5. Consolidated CI and prepared a source release without machine-specific Claude permissions or Python build/cache files.

## Changes and motivation

| Area | Change | Impact |
| --- | --- | --- |
| Idea selection | Reject non-finite (`NaN`, infinite), boolean and malformed reviewer scores | Prevents nonnumeric reviews from silently affecting idea ranking |
| Candidate validation | Require structured candidate objects and bounded, unique, string IDs | Reduces malformed or adversarial model output failure modes |
| Generated reviews | Reject unknown, duplicate and missing idea review IDs | Prevents a single model-generated review from overwriting another candidate's assessment |
| Idea files | Write generated outputs and final reports atomically | Reduces partial JSON/Markdown state after interrupted writes |
| Scientific writing | Check BibTeX failure and intermediate LaTeX rebuild failure; require BibTeX when bibliography is detected | Refuses falsely successful compilation |
| Process execution | Kill the POSIX process group on timeout | Avoids orphan child processes holding log pipes open and hanging the ledger runner |
| Run log management | Drain stdout/stderr in bounded chunks, with visible truncation after 8 million characters per stream | Avoids unbounded logfile growth and memory allocation from missing newlines |
| Vendored idea discovery | Inspected V5 architecture and added `researchctl idea-discovery inspect/prepare PROJECT` | Exposes a safe, **opt-in, non-executing** per-project setup path; full V5 remains separate |
| Vendor unpacking | Enforce a single expected archive root, reject traversal/symlinks/special files, bound archive expansion, and refuse overwriting existing setup | Prevents unsafe extraction and accidental loss of operator edits |
| Tests | Namespaced duplicate `tests_researchledger` modules | Allows both existing test directories to be collected together without `import file mismatch` |
| Validation-study fixtures | Dedicated per-run trajectory-manifest checks **skip explicitly** when the historical workspaces are absent from this source archive | Does not fabricate or silently substitute missing primary provenance |
| CI | Replaced contradictory Python 3.9 testing (package requires 3.10+); corrected unavailable mypy step; standardized cross-platform tests, smoke check, basic Ruff checks and dependency audit | Moves CI toward reproducible checks with relevant interpreter versions |
| Distribution hygiene | Excluded machine-local `.claude/settings.local.json`; remove temporary `__pycache__` and egg-info from distributed ZIP | Prevents redistribution of user-specific allowlists and generated caches |
| Documentation | Updated README and comparative manuscript matrix to describe the actual Idea Discovery v5 architecture and its non-integrated status | More accurate product positioning, less inflated capability claims |

## Tests and constraints

**Final local regression result:** `python -m pytest -q tests tests_researchledger --disable-warnings` completed with **566 passed, 2 skipped, 37 unittest subtests passed, 0 failures** in 128.80 s on the available Python 3.13 runtime. Some assertions were executed twice because `tests_researchledger/` mirrors 22 files from `tests/`; counts should not be misinterpreted as 566 unique tests. In addition, targeted engineering-hardening tests passed independently. The CLI Idea Discovery inspect/prepare smoke test completed successfully. The live cloud CI matrix was not executed.

- Added `tests/test_engineering_hardening_2026.py` with automated checks for idea-scoring, malformed inputs, bibliography error propagation, runaway child process handling, bounded logs, safe vendor extraction, and explicit no-override behavior.
- **The two tracked-trajectory tests require omitted generated workspace data.** When those workspaces are absent, tests are skipped with a named reason. The existing JSON study report remains available, but its original run-manifest claims cannot be independently revalidated from this ZIP alone.
- The entire `tests_researchledger/` suite is a **byte-identical mirror** of files already under `tests/` (22 files). Running both collections together is supported for compatibility but **double-counts those same tests**. It is not 22 independent test modules of additional coverage.
- Full Claude Code model interaction, DOI network lookup, LaTeX compilation against an installed TeX distribution, Docker model-generated experiments, and reviewer/ideation agent workflows **were not executed in this environment**. Such tests require authorized accounts, real research inputs, a properly prepared runtime, and human inspection.
- Vendor tests for bundled Referee Lean v2 and Idea Discovery v5 were not treated as certified by the first-party Factory test suite. Their own source tests and external evaluation should be run independently before claiming accuracy or reliability.

## Unresolved work (ordered)

1. **Agent orchestration:** Wire the full Referee execution engine into optional, isolated orchestrator mode, with independent model call logging, explicit file permissions and systematic reviewer benchmarks. Current S3/S5 prompts do not automatically execute every Referee specialist.
2. **Idea bridge:** Implement and benchmark a schema-validated adapter from V5's finalist reports into Factory S1, while retaining `READY_FOR_MVE` and never promoting its literature verdicts to empirical verification.
3. **End-to-end workflow:** Run a provisioned Docker/Claude Code/LaTeX test matrix with real and synthetic data explicitly distinguished; confirm all five stages and the validation gate in the actual external toolchain.
4. **Research validation:** Require blinded external expert review, independently reproduced experiments, literature full-text checks and source-bound statistical inference for scientific publication claims.
5. **Evidence fixtures:** Publish audited SHA-256 manifests and corresponding historical trajectory workspace archives, or provide a reproducible generation process with a separately audited output digest.
6. **Dependencies:** Pin/review transitive dependencies in a supported lock workflow and execute the security audit in a CI environment with current vulnerability data. Cross-platform smoke and real GitHub Actions outcomes remain to be established.

**No new benchmark or peer-review accuracy claims are made by this engineering pass.** The documentation and tests support only the specific code-level improvements described above.
