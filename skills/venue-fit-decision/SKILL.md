---
name: venue-fit-decision
description: "Decide whether the assembled evidence supports a full-length journal submission or only a focused conference paper, and commit to the template and effort that follow from that decision. Use when Before fixing the section skeleton, because the venue choice determines it; or when A project sits between conference and journal ambition and a choice must be made; or when Experiments are complete but weaker than hoped, and the submission target must be re-decided."
---

# Venue Fit Decision

> Ported from the ConvFusion research-skill library (category: `research-decision`; origin: paper/venue (paper_decision)). Ask/answer using this method whenever it applies to the current research workspace.

## Purpose

Decide whether the assembled evidence supports a full-length journal submission or only a focused conference paper, and commit to the template and effort that follow from that decision.

## When to Use

Use this skill when:

- Before fixing the section skeleton, because the venue choice determines it.
- A project sits between conference and journal ambition and a choice must be made.
- Experiments are complete but weaker than hoped, and the submission target must be re-decided.

## Research Method

1. **Audit the evidence before judging the idea**: count datasets, baselines and ablations, and check whether improvements exceed run-to-run variation. Novelty does not compensate for thin validation.
2. **Score the criteria separately** — novelty, technical depth, experimental completeness, result significance, paper completeness — instead of collapsing them into one impression.
3. **Apply the venue bar as a rule**: a journal submission normally needs several datasets, a large baseline set, ablations, comprehensive results and a non-incremental method; a focused conference paper needs one or two datasets, a few baselines and solid validation.
4. **Default downwards when uncertain.** An over-claimed submission costs a review cycle; an under-claimed one can be upgraded later.
5. **Convert the shortfall into a plan**: if the answer is conference, list exactly which additional experiments would justify a journal version and what each would cost.
6. **Emit a typed decision** with confidence, reasoning, the template it implies, and the actions that would change it.

## Reasoning Guidance

<!-- 迁移自旧模块提示词；具体推理要点见下方逐字来源。 -->

## Evidence Requirements

The decision must cite the concrete experiment inventory — datasets, baselines, ablations, effect sizes — rather than the method description. Confidence must be reported, and must be low when ablations are missing or a single dataset was used. Suggested upgrades must name the evidence each would require.

## Expected Output

Produce:

- the decision (journal or conference) with confidence and reasoning grounded in the evidence inventory
- the template type the decision implies
- concrete upgrade actions, each with the evidence it would require
- the named evidence gaps that drove the decision

## Workspace Conventions

If this method reads or writes structured workspace files (evidence/claims/decisions, plans, papers, outputs, LaTeX, literature search/download), follow the exact schemas in this plugin's `reference/` directory rather than improvising a format — see [research-assets.md](../../reference/research-assets.md), [plans.md](../../reference/plans.md), [papers.md](../../reference/papers.md), [outputs.md](../../reference/outputs.md), [latex.md](../../reference/latex.md), [literature-search.md](../../reference/literature-search.md), and [paper-fulltext-download.md](../../reference/paper-fulltext-download.md), whichever applies. The `research` skill's [SKILL.md](../research/SKILL.md) is the usual entry point that pulls the right context together first; if this skill was invoked on its own, check whether a `project.md` or `research-state.md` already exists in the workspace before assuming there is none.

## Reference Prompts

The original, more verbose source prompts this method was distilled from are kept in [reference.md](reference.md) for extra detail when the summary above isn't enough (exact length/format constraints, worked examples, etc).
