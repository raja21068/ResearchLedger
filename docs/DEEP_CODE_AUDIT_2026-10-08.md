# Paper Factory × ResearchLedger — source and release audit

**Release:** 2.0.1 (post-audit patch)  
**Date:** 2026-10-08  
**Source baseline:** user-provided Evidence-First v2.0 ZIP

## What was actually checked

- Extracted the shipped v2.0 ZIP and catalogued its contents.
- Inspected the critical first-party execution and evidence paths: CLI and workspace creation, orchestrator/checkpoints, stage signatures, generated-code execution, Docker sandbox, source/result hashing, ResearchLedger import and verification, protocol/literature/claims/statistics/reproduction gates, and manuscript review.
- Parsed all source-controlled Python, JSON, YAML and TOML material, including bundled vendors and restored ResearchLedger validation-study fixtures (416 Python files, 298 JSON files, 6 YAML files, 2 TOML files; **no syntax/format parse errors**). This is *automated static coverage*, not a manual security audit of every statement in every vendored file.
- Re-ran the integrated test suites, added regression tests for the discovered failure modes, and checked the distribution archive separately.
- The vendor directory contains third-party code (754 files before bytecode/cache generation). It was included in parsing and artifact-integrity checks, but **not** independently rewritten or certified as secure.

## Confirmed findings and implemented corrections

1. **Incomplete distributable (high):** the v2.0 ZIP included tests referring to missing `validation_study/`, `hooks/` and ResearchLedger example fixtures. This caused test collection errors and six subsequent hook-test failures. Recovered the original test fixtures, runnable hook and plugin metadata from the supplied ResearchLedger archive. Did **not** copy source `.git` history, local build caches or credentials.
2. **Unsafe Docker bind-source paths (high):** validating source paths after `Path.resolve()` can conceal symlinks. Docker sandbox mount checks now reject symlinked sources, symlinked ancestor components and symlinks within untrusted repository/dataset trees. Added negative tests verifying Docker is not launched for unsafe dataset mounts.
3. **Overly permissive reproduction comparison (high):** arbitrary large, finite tolerances could make mismatched results look reproduced. The isolated-repeat interface now rejects tolerances greater than 0.01, negative/non-finite values and booleans; rechecking a stored receipt independently validates these limits and rejects symlinked evidence-path components. More stringent experiment-specific bounds should still be preregistered and used where appropriate.
4. **Memory scalability and symlinks in repository hashing (medium):** tree hashing loaded entire files with `read_bytes()`. It now streams 1 MiB chunks and rejects symlinks, while preserving the existing hash format for unchanged ordinary source trees.
5. **Unwritable default workspace on standard installs (medium):** a globally installed package could try to put projects under `site-packages`. By default new projects now go to `~/.local/share/paperfactory/workspaces`, while an existing checkout-local `workspaces/` remains compatible. `PAPERFACTORY_WORKSPACES` overrides this root.
6. **Malformed Crossref record handling (low):** unexpected non-object registry entries and malformed container-title data are now handled with explicit validation instead of unpredictable attribute/type exceptions.
7. **Potentially misleading run label (medium):** the text-only ResearchLedger paper audit now identifies its run count as **recorded runs, not replay-verified runs**. The original machine-readable field is unchanged for API compatibility and needs a future breaking-schema revision.
8. **Regression coverage:** added `tests/test_audit_hardening_v201.py` for the above conditions and corrected documentation about workspace location and installation limits.

## Unresolved risks and limits

- **No live E2E scientific trial.** Full Claude Code → model → code generation → actual Docker run → LaTeX compilation, with external literature lookup, was not exercised in this environment. Automated tests include stubs/mocks and validation fixtures.
- **Scientific evidence is not established by an execution exit code.** Claim bindings cover *declared* result slots; unmarked prose, causality, novelty, leakage, data use, ethics, references, statistics and independent scientific reproduction still require external checks.
- **Local SHA-256 receipts are change detectors, not external signatures or trustworthy timestamps.** A hostile user with filesystem write access could forge both receipt and source artifacts. Stronger guarantees require immutable external storage or signed attestations.
- **Only editable source-tree installation is supported end to end.** The source ZIP carries `vendor/`, `schemas/`, `skills/` and `templates/`, but `pyproject.toml` does not package all of them into a standalone wheel. Install with `python -m pip install -e .` from the extracted repository. A real wheel build/distribution redesign is still needed.
- **Generic host-side ResearchLedger CLI is powerful.** Its `researchledger run` command can run commands directly on the host by operator request. Never run generated Paper Factory experiments through that CLI; use the isolated `researchctl` experiment path.
- **Vendor code and AI agent behavior:** Parsing 270 vendor Python files and checking bundle structure is not equivalent to manual threat modeling or proving no vulnerabilities. Prompts and generated manuscripts are untrusted inputs. TeX compilation and optional provider tool permissions should be separately sandboxed for adversarial deployments.
- **Platform testing:** CI includes Python 3.10 and 3.12 on Ubuntu; no local macOS/Windows Docker + LaTeX end-to-end test was conducted here.

## Local verification commands

```bash
python -m pip install -e '.[dev]'
python -m pytest -q tests tests_researchledger
researchctl doctor
researchctl init 'smoke project'
researchctl protocol check smoke-project
```

The final **full-suite pass count** and archive inspection for this release are reported in `AUDIT_TEST_RESULTS.json` at the package root. No Q1 publication-quality or independently reproduced science claim is implied.
