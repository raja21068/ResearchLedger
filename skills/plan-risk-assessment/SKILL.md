---
name: plan-risk-assessment
description: "Stress-test a research plan before it is executed: surface the assumptions it rests on, classify the risks that would invalidate it, and decide whether it is executable under the current constraints, including the honest answer that it is not. Use when A plan is about to be committed and its assumptions have never been written down; or when A risk list exists but contains neither mitigation nor a trigger for acting; or when Budget, deadline, compute availability or data-access constraints may make the plan impossible."
---

# Plan Risk Assessment

> Ported from the ConvFusion research-skill library (category: `research-decision`; origin: planning/plan_enricher, resource/recommendation, resource/consistency_validation). Ask/answer using this method whenever it applies to the current research workspace.

## Purpose

Stress-test a research plan before it is executed: surface the assumptions it rests on, classify the risks that would invalidate it, and decide whether it is executable under the current constraints, including the honest answer that it is not.

## When to Use

Use this skill when:

- A plan is about to be committed and its assumptions have never been written down.
- A risk list exists but contains neither mitigation nor a trigger for acting.
- Budget, deadline, compute availability or data-access constraints may make the plan impossible.
- Two candidate plans must be compared on risk rather than on expected performance.

## Research Method

1. **Extract the assumptions before the risks.** List what must be true for the plan to work (the data is obtainable, the phenomenon reproduces, the baseline is reproducible) and mark each as testable or untestable. An untestable assumption is a risk that no experiment inside the plan can retire.
2. **Classify risks on a fixed taxonomy rather than ad hoc**, for example domain gap, technical complexity, data quality, compute intensity and convergence, or an equally explicit domain-specific set. A stable taxonomy is what lets two plans be compared at all.
3. **Assign severity and mitigation to each risk.** Every risk carries a level, a concrete mitigation, an owner, and a trigger stating which observation means the mitigation must be executed. A risk with no mitigation is a plan defect rather than a risk entry.
4. **Apply hard constraints as gates, not scores.** Budget, deadline, compute availability, licensing and data governance are pass or fail. A plan that fails a gate is infeasible regardless of how well it scores elsewhere, so evaluate gates before any weighted ranking.
5. **Look for correlated failure.** Several risks that share one cause (a single dataset, one person, one cluster) are one risk with a compounded effect. Name the shared dependency; independent-looking risks that fail together are the most common cause of a dead project.
6. **Check the internal consistency of the plan artefacts.** Requirement, instance choice, infrastructure and cost must describe the same plan. A costed option that does not satisfy the stated requirement is an error rather than a rounding difference, and must be reported as one.
7. **Give a verdict with the condition that would change it.** State feasible, feasible only after a named relaxation or descope, or no feasible plan under the constraints, together with the evidence that would flip the verdict.

## Reasoning Guidance

<!-- 迁移自旧模块提示词；具体推理要点见下方逐字来源。 -->

## Evidence Requirements

Assumptions must be written as checkable propositions with the artefact or experiment that would test each. Risk severities must have a stated basis. Gate failures must cite the constraint and the measured shortfall. An infeasible verdict must name the binding constraint and the relaxation that would open the option set.

## Expected Output

Produce:

- the assumptions the plan rests on, marked testable or untestable
- risks classified on a stated taxonomy with severity, mitigation, owner and trigger
- hard-constraint gate results with the measured shortfall for each failure
- shared dependencies and correlated failure modes
- a feasibility verdict with the condition that would change it

## Workspace Conventions

If this method reads or writes structured workspace files (evidence/claims/decisions, plans, papers, outputs, LaTeX, literature search/download), follow the exact schemas in this plugin's `reference/` directory rather than improvising a format — see [research-assets.md](../../reference/research-assets.md), [plans.md](../../reference/plans.md), [papers.md](../../reference/papers.md), [outputs.md](../../reference/outputs.md), [latex.md](../../reference/latex.md), [literature-search.md](../../reference/literature-search.md), and [paper-fulltext-download.md](../../reference/paper-fulltext-download.md), whichever applies. The `research` skill's [SKILL.md](../research/SKILL.md) is the usual entry point that pulls the right context together first; if this skill was invoked on its own, check whether a `project.md` or `research-state.md` already exists in the workspace before assuming there is none.

## Reference Prompts

The original, more verbose source prompts this method was distilled from are kept in [reference.md](reference.md) for extra detail when the summary above isn't enough (exact length/format constraints, worked examples, etc).
