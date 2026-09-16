---
name: research-strategy-portfolio
description: "Decide which research strategies the project should actually pursue, as a deliberate risk-diversified portfolio rather than one bet, and then consolidate the surviving plans into a single committed strategy with a validation protocol and a reproducibility contract. Use when A research direction has been chosen but not yet translated into committable strategies; or when You cannot tell whether the plan is a safe incremental study or a high-risk, high-reward bet; or when Several candidate plans exist and must be reduced to the ones worth executing."
---

# Research Strategy Portfolio

> Ported from the ConvFusion research-skill library (category: `research-management`; origin: planning/plan_initializer, planning/research_strategy_synthesis). Ask/answer using this method whenever it applies to the current research workspace.

## Purpose

Decide which research strategies the project should actually pursue, as a deliberate risk-diversified portfolio rather than one bet, and then consolidate the surviving plans into a single committed strategy with a validation protocol and a reproducibility contract.

## When to Use

Use this skill when:

- A research direction has been chosen but not yet translated into committable strategies.
- You cannot tell whether the plan is a safe incremental study or a high-risk, high-reward bet.
- Several candidate plans exist and must be reduced to the ones worth executing.
- The experiment graph, validation protocol or target venue is still undefined.

## Research Method

1. **Anchor every plan to a named gap.** Each strategy must cite the gap or opportunity it addresses, drawn from the knowledge state or innovation state. A plan whose motivation is "this would be interesting" cannot be compared against the others.
2. **Make risk posture explicit and non-redundant.** Assign each plan a posture: conservative (established components, fast falsification), balanced (one unproven component), innovative (a new mechanism with a real chance of not working). If two plans share a posture, they are one plan with variants.
3. **Hold the comparison fixed across the portfolio.** Datasets, metrics and baselines must be identical across plans, otherwise the comparison measures the evaluation protocol rather than the strategy.
4. **Write the experiment graph before spending anything.** Express each plan as a dependency graph of stages (data, model build, training, evaluation) with inputs, outputs and edges. A plan whose evaluation step does not consume its own training output is not yet a plan.
5. **Design the ablation plan up front.** For every unproven component, state the ablation or control that would show it matters and the observable difference expected. A component with no possible ablation is either not novel or not testable.
6. **Commit to one strategy and keep the others on record.** Select the plan to execute now and say why; record each rejected plan with the condition under which it would be revived. Rejected plans with no revival condition should be deleted rather than archived.
7. **Fix the reproducibility and publication contract at commitment time**, not after results arrive: seeds, hyperparameter tables, hardware and software environment, code-release scope, target venue, and the timeline phases the venue imposes.

## Reasoning Guidance

<!-- 迁移自旧模块提示词；具体推理要点见下方逐字来源。 -->

## Evidence Requirements

Every plan must trace to a documented gap or knowledge-state claim. Baselines and metrics must be justified against the literature rather than assumed. The ablation plan must name the component and the expected observable difference. Rejected plans must record the reason for rejection and the condition for revival.

## Expected Output

Produce:

- two to four strategies, each with its posture, the gap it targets and its falsification condition
- the selected strategy, the reason for selection, and the rejected alternatives on record
- a validation protocol (datasets, metrics, baselines) shared across the portfolio
- an experiment graph and an ablation plan for the unproven components
- a reproducibility and publication contract (seeds, hyperparameters, hardware, environment, venue, timeline)

## Workspace Conventions

If this method reads or writes structured workspace files (evidence/claims/decisions, plans, papers, outputs, LaTeX, literature search/download), follow the exact schemas in this plugin's `reference/` directory rather than improvising a format — see [research-assets.md](../../reference/research-assets.md), [plans.md](../../reference/plans.md), [papers.md](../../reference/papers.md), [outputs.md](../../reference/outputs.md), [latex.md](../../reference/latex.md), [literature-search.md](../../reference/literature-search.md), and [paper-fulltext-download.md](../../reference/paper-fulltext-download.md), whichever applies. The `research` skill's [SKILL.md](../research/SKILL.md) is the usual entry point that pulls the right context together first; if this skill was invoked on its own, check whether a `project.md` or `research-state.md` already exists in the workspace before assuming there is none.

## Reference Prompts

The original, more verbose source prompts this method was distilled from are kept in [reference.md](reference.md) for extra detail when the summary above isn't enough (exact length/format constraints, worked examples, etc).
