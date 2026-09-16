---
name: feasibility-cost-and-resource-plan
description: "Determine whether a research plan can actually be executed within the available resources, and what it will cost, expressed in units that can be checked — compute, data, storage, skills, time and money. Use when A plan is about to be committed and its resource envelope is unknown; or when Two technical routes look equally good on paper and must be compared by cost and feasibility; or when A claim depends on resources you do not control, such as a dataset, a licence or a cluster."
---

# Feasibility, Cost and Resource Plan

> Ported from the ConvFusion research-skill library (category: `research-decision`; origin: decision/feasibility-evaluation, decision/cost-evaluation, resource/estimation). Ask/answer using this method whenever it applies to the current research workspace.

## Purpose

Determine whether a research plan can actually be executed within the available resources, and what it will cost, expressed in units that can be checked — compute, data, storage, skills, time and money.

## When to Use

Use this skill when:

- A plan is about to be committed and its resource envelope is unknown.
- Two technical routes look equally good on paper and must be compared by cost and feasibility.
- A claim depends on resources you do not control, such as a dataset, a licence or a cluster.

## Research Method

1. **Estimate requirements from the plan's computation, not from hardware names.** Express compute as a work quantity — GPU-hours times relative compute units against a stated reference (A100 = 1.0) — plus storage tiers, data volume, parallelism and number of runs. Fix the requirement before naming any hardware.
2. **Enumerate cost components separately and cite their source.** Compute, storage, network egress, data acquisition and personnel time, each with the pricing source and date. A single total without a breakdown cannot be audited, and goes stale silently when prices change.
3. **Convert every requirement into a hard constraint and gate on it first.** An option that fails any single requirement — GPU-hours, storage, bandwidth, deadline — is infeasible and is removed before ranking. A strong score on one axis must never hide a failed constraint.
4. **Compare at least two viable options**, including the local or self-hosted alternative and the cheapest credible provider, and report the total for each rather than only for the winner.
5. **Report the bottleneck and the scaling regime.** State which resource binds first and how cost grows with scale — runs, parameters, data, sequence length — so the estimate can be reused at a different scale instead of recomputed.
6. **Validate consistency across the estimate chain.** Resource spec, chosen option and cost must describe the same configuration; a mismatch invalidates the number rather than merely looking untidy.
7. **Publish the uncertainty on the dominant driver** as scenarios (optimistic, expected, pessimistic) and say which assumption would move the estimate most.

## Reasoning Guidance

<!-- 迁移自旧模块提示词；具体推理要点见下方逐字来源。 -->

## Evidence Requirements

Prices, instance types and exchange rates must cite their source and date. Requirement estimates must show the derivation from plan parameters rather than appearing as given numbers. Infeasible options must be recorded with the constraint they failed, and assumptions about data availability or expertise must be flagged.

## Expected Output

Produce:

- a resource specification covering compute, storage, network, data, skills and time
- a cost breakdown per option with pricing provenance
- a feasibility gating table showing pass/fail per hard constraint
- the bottleneck and the scaling behaviour of cost
- a consistency check across spec, option and cost, plus an uncertainty range

## Workspace Conventions

If this method reads or writes structured workspace files (evidence/claims/decisions, plans, papers, outputs, LaTeX, literature search/download), follow the exact schemas in this plugin's `reference/` directory rather than improvising a format — see [research-assets.md](../../reference/research-assets.md), [plans.md](../../reference/plans.md), [papers.md](../../reference/papers.md), [outputs.md](../../reference/outputs.md), [latex.md](../../reference/latex.md), [literature-search.md](../../reference/literature-search.md), and [paper-fulltext-download.md](../../reference/paper-fulltext-download.md), whichever applies. The `research` skill's [SKILL.md](../research/SKILL.md) is the usual entry point that pulls the right context together first; if this skill was invoked on its own, check whether a `project.md` or `research-state.md` already exists in the workspace before assuming there is none.

## Reference Prompts

The original, more verbose source prompts this method was distilled from are kept in [reference.md](reference.md) for extra detail when the summary above isn't enough (exact length/format constraints, worked examples, etc).
