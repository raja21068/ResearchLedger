---
name: go-no-go-decision
description: "Convert the multi-dimensional evaluations into a committed go, no-go or conditional go — with gates checked first, risk weighed against reward, and next actions whose progress can be observed. Use when The novelty, feasibility, cost and risk assessments exist and a commitment must be made; or when A project is continuing by momentum and nobody has stated the grounds for continuing; or when The decision depends on a missing fact and the right answer is currently neither go nor no-go."
---

# Go / No-Go Decision

> Ported from the ConvFusion research-skill library (category: `research-decision`; origin: decision/decision-synthesis). Ask/answer using this method whenever it applies to the current research workspace.

## Purpose

Convert the multi-dimensional evaluations into a committed go, no-go or conditional go — with gates checked first, risk weighed against reward, and next actions whose progress can be observed.

## When to Use

Use this skill when:

- The novelty, feasibility, cost and risk assessments exist and a commitment must be made.
- A project is continuing by momentum and nobody has stated the grounds for continuing.
- The decision depends on a missing fact and the right answer is currently neither go nor no-go.

## Research Method

1. **Assemble the dimensions side by side before judging** — novelty, feasibility, cost, risk, impact — each with its provenance and its confidence. Do not average dimensions that carry different confidence into one number.
2. **Apply the hard gates first.** A failed gate — unfalsifiable claim, infeasible resource requirement, unresolved ethics or licence, novelty destroyed by the closest work — forces a no-go or a re-scope. A high average must never rescue a failed gate.
3. **Weigh risk against reward explicitly.** State the upside if it works, the downside if it fails, and the residual risk after mitigation. A favourable ratio with unresolvable uncertainty is a conditional go, not a go.
4. **Prefer a conditional decision to a vague one.** If the decision depends on a missing fact, name the check, its cost, and the decision rule — "go if the pilot reaches X, otherwise no-go" — instead of deciding on optimism.
5. **State what is being committed:** compute, people, time and the opportunity cost of the alternatives that are now not being pursued.
6. **Assign prioritised next actions** with an owner, a first step and the observable that marks progress. The first action should retire the largest uncertainty soonest.
7. **Record the decision as an auditable artefact** with the evidence snapshot it used, so that a later reversal can be traced to a changed fact rather than to a changed mood.

## Reasoning Guidance

<!-- 迁移自旧模块提示词；具体推理要点见下方逐字来源。 -->

## Evidence Requirements

The decision must reference the underlying assessments rather than restate them. Every condition and threshold must be checkable. The go/no-go, its date, its weights and the evidence snapshot must be recorded, and evidence that argued against the decision must be kept rather than dropped.

## Expected Output

Produce:

- gate check results with the gate that failed, if any
- a risk-versus-reward assessment with residual risk
- a go, no-go or conditional go, with the decision rule when conditional
- what is being committed and the opportunity cost
- prioritised next actions with owners and progress signals

## Workspace Conventions

If this method reads or writes structured workspace files (evidence/claims/decisions, plans, papers, outputs, LaTeX, literature search/download), follow the exact schemas in this plugin's `reference/` directory rather than improvising a format — see [research-assets.md](../../reference/research-assets.md), [plans.md](../../reference/plans.md), [papers.md](../../reference/papers.md), [outputs.md](../../reference/outputs.md), [latex.md](../../reference/latex.md), [literature-search.md](../../reference/literature-search.md), and [paper-fulltext-download.md](../../reference/paper-fulltext-download.md), whichever applies. The `research` skill's [SKILL.md](../research/SKILL.md) is the usual entry point that pulls the right context together first; if this skill was invoked on its own, check whether a `project.md` or `research-state.md` already exists in the workspace before assuming there is none.

## Reference Prompts

The original, more verbose source prompts this method was distilled from are kept in [reference.md](reference.md) for extra detail when the summary above isn't enough (exact length/format constraints, worked examples, etc).
