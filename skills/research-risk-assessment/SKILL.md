---
name: research-risk-assessment
description: "Identify what could make the plan fail or make its result unusable, separate risk from missing fact, and attach a mitigation and a detectable early signal to each risk that is kept. Use when A plan is being committed and its failure modes have not been written down; or when A risk list exists but contains unread papers and vague warnings instead of mechanisms; or when You need to decide at what observation the direction should be abandoned."
---

# Research Risk Assessment

> Ported from the ConvFusion research-skill library (category: `research-decision`; origin: decision/risk-evaluation, decision/feasibility-evaluation, resource/estimation). Ask/answer using this method whenever it applies to the current research workspace.

## Purpose

Identify what could make the plan fail or make its result unusable, separate risk from missing fact, and attach a mitigation and a detectable early signal to each risk that is kept.

## When to Use

Use this skill when:

- A plan is being committed and its failure modes have not been written down.
- A risk list exists but contains unread papers and vague warnings instead of mechanisms.
- You need to decide at what observation the direction should be abandoned.

## Research Method

1. **Enumerate risks by failure mode, not by category label.** For each risk name the mechanism: the method does not scale, the result is not attributable to the mechanism, the data or licence is unavailable, a dependency slips, a regulatory or ethics constraint blocks release.
2. **Separate risk from uncertainty.** A risk has a plausible mechanism and can be mitigated or monitored; an uncertainty is a missing fact that must be resolved by looking it up or by running a pilot. Do not park an unread paper as a risk.
3. **Rate each risk by impact and by how early it becomes detectable.** A high-impact risk that only surfaces at the end of the project demands a different response from one a pilot would reveal next week.
4. **Attach a mitigation and an owner to every risk you keep.** A mitigation must be an action with a trigger and a fallback — "if scaling to N fails, fall back to setting S" — not a sentiment such as "monitor carefully".
5. **Define the kill criteria now.** State the observation at which the direction is abandoned rather than patched, while the sunk cost is still near zero.
6. **Check reproducibility risks explicitly:** data licensing and availability, compute budget for re-runs, seeds and variance reporting, and whether the key comparison can be reproduced by someone else from what you intend to release.
7. **Carry the residual risk forward.** Rank the risks and hand the go/no-go decision the risk that remains after mitigation, not the risk as first stated.

## Reasoning Guidance

<!-- 迁移自旧模块提示词；具体推理要点见下方逐字来源。 -->

## Evidence Requirements

Each risk must name the mechanism that would produce the failure and the evidence or precedent for it. Mitigations must specify trigger and fallback. Resource risks must cite the resource estimate, and unresolved external constraints such as licences or ethics approval must be flagged rather than assumed away.

## Expected Output

Produce:

- a risk register with mechanism, impact and detectability
- the split between true risks and open uncertainties
- a mitigation with trigger and fallback per retained risk
- kill criteria stated in advance
- residual risk after mitigation, plus reproducibility risks

## Workspace Conventions

If this method reads or writes structured workspace files (evidence/claims/decisions, plans, papers, outputs, LaTeX, literature search/download), follow the exact schemas in this plugin's `reference/` directory rather than improvising a format — see [research-assets.md](../../reference/research-assets.md), [plans.md](../../reference/plans.md), [papers.md](../../reference/papers.md), [outputs.md](../../reference/outputs.md), [latex.md](../../reference/latex.md), [literature-search.md](../../reference/literature-search.md), and [paper-fulltext-download.md](../../reference/paper-fulltext-download.md), whichever applies. The `research` skill's [SKILL.md](../research/SKILL.md) is the usual entry point that pulls the right context together first; if this skill was invoked on its own, check whether a `project.md` or `research-state.md` already exists in the workspace before assuming there is none.

## Reference Prompts

The original, more verbose source prompts this method was distilled from are kept in [reference.md](reference.md) for extra detail when the summary above isn't enough (exact length/format constraints, worked examples, etc).
