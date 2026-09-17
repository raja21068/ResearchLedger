---
name: evidence-assessment
description: "Judge whether the experiment as executed actually produced the evidence its claims need, and locate the weakest link when it did not — the checkpoint before results become paper text. Use when The experiment pipeline has finished and claims are about to be written; or when A measured result departs from the pre-run prediction and needs scrutiny before it is trusted; or when A non-programmable or offline study has returned human-collected data that must be checked against the design."
---

# Evidence Assessment & Claim Traceability

> Ported from the ConvFusion research-skill library (category: `analysis`; origin: experiment/prompts (full-chain evaluator), experiment/summary, experiment/lab_offline). Ask/answer using this method whenever it applies to the current research workspace.

## Purpose

Judge whether the experiment as executed actually produced the evidence its claims need, and locate the weakest link when it did not — the checkpoint before results become paper text.

## When to Use

Use this skill when:

- The experiment pipeline has finished and claims are about to be written.
- A measured result departs from the pre-run prediction and needs scrutiny before it is trusted.
- A non-programmable or offline study has returned human-collected data that must be checked against the design.

## Research Method

1. **Restate each intended claim and the evidence it requires** — which run, which comparison, which threshold. A claim whose required evidence was never produced is marked unsupported regardless of how plausible it sounds. If the claim already exists as `research/claims/C<NNN>.md`, run `Bash researchledger trace C<NNN>` first — it prints the claim's statement, every supporting evidence record with its status, the run(s) each cites (seed, metrics, artifact-hash verification), and where the manuscript uses it, in one shot, instead of reconstructing that chain by hand.
2. **Audit the chain for consistency.** Data, method and evaluation must line up: evaluation used the intended data version and splits and the intended metric, the model evaluated is the one the config describes, and every figure traces to a run. Locate the broken link instead of averaging over it. Run `Bash researchledger validate` before doing this by hand — it already checks broken cross-references (`RL101`), a claim past `hypothesis` with no evidence (`RL110`), experimental evidence with no run (`RL111`), a cited run that didn't exit 0 (`RL211`), and artifact hashes (`RL201`/`RL202`) mechanically. Start from its findings; don't re-derive checks the tool already ran.
3. **Compare achieved against expected and investigate the gap.** Where measured results depart from the pre-run simulation or the literature, determine whether the cause is a real effect, a protocol deviation, a bug or a fallback to simulated data, and record which. A gap that cannot be explained blocks the claim.
4. **Grade the evidence per claim** as strong, indicative, insufficient or contradictory, give the reason, and state the additional run that would move it up a grade. Translate the grade into the evidence record's actual `status` field, since that's what the rest of the system reads: strong/reproduced → `verified` (only after independent corroboration — a second run, a second reviewer, a cross-check — never from the first run completing on its own); indicative/one clean run → `checked`; insufficient → `observed`/`proposed`; contradictory → `contradicted`/`invalidated`. When the evidence comes straight from a run you just captured, create it with `Bash researchledger evidence create --from-run <run_id> --supports C<NNN> [--status checked|observed]` rather than hand-writing the frontmatter — it allocates the id, sets the bidirectional claim cross-reference, and recomputes the claim's own status in the same step (and it refuses `--status verified` from a run on its own, on purpose).
5. **Check offline and human-collected evidence against its protocol.** For non-programmable studies verify that the sample and population match the design, that instruments and procedure were followed, that ethical and data-handling requirements were met, and that raw data exists. Human-collected evidence with no raw record is not evidence.
6. **Issue a verdict and a gate.** Recommend proceed, revise and rerun, or stop, naming the failed elements and the minimum change that would fix them. Never pass a claim on the strength of the surrounding narrative.

## Reasoning Guidance

<!-- 迁移自旧模块提示词；具体推理要点见下方逐字来源。 -->

## Evidence Requirements

A traceable link from each claim to run artefacts and the metric computation, the code and data versions used, and an explicit record of deviations, fallbacks and excluded runs. Assessments must quote the artefact examined rather than a summary of it, and offline evidence must include the raw records and protocol compliance notes.

## Expected Output

Produce:

- claim-by-claim evidence audit against required evidence
- chain-consistency report identifying the broken link when present
- achieved-versus-expected gap analysis with causes
- evidence grade per claim and what would raise it
- offline protocol compliance check plus a proceed, revise or stop verdict with required fixes

## Workspace Conventions

If this method reads or writes structured workspace files (evidence/claims/decisions, plans, papers, outputs, LaTeX, literature search/download), follow the exact schemas in this plugin's `reference/` directory rather than improvising a format — see [research-assets.md](../../reference/research-assets.md), [plans.md](../../reference/plans.md), [papers.md](../../reference/papers.md), [outputs.md](../../reference/outputs.md), [latex.md](../../reference/latex.md), [literature-search.md](../../reference/literature-search.md), and [paper-fulltext-download.md](../../reference/paper-fulltext-download.md), whichever applies. The `research` skill's [SKILL.md](../research/SKILL.md) is the usual entry point that pulls the right context together first; if this skill was invoked on its own, check whether a `project.md` or `research-state.md` already exists in the workspace before assuming there is none.

See [run-ledger.md](../../reference/run-ledger.md) for the evidence status vocabulary
(`proposed`/`observed`/`checked`/`verified`/`contradicted`/`invalidated`/`superseded`), the
`researchledger validate`/`trace` command reference, and the RL-code catalog referenced above.

## Reference Prompts

The original, more verbose source prompts this method was distilled from are kept in [reference.md](reference.md) for extra detail when the summary above isn't enough (exact length/format constraints, worked examples, etc).
