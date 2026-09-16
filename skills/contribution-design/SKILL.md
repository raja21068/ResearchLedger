---
name: contribution-design
description: "State what the field gains if the work succeeds, and design the evidence package that demonstrates each claim instead of merely asserting it. Use when An idea and its hypothesis are fixed and the claims must be made defensible; or when A proposal claims a contribution that no planned experiment would actually demonstrate; or when You need to choose baselines and controls that make the result interpretable."
---

# Contribution Design

> Ported from the ConvFusion research-skill library (category: `innovation`; origin: conception/structuring, decision/impact-evaluation). Ask/answer using this method whenever it applies to the current research workspace.

## Purpose

State what the field gains if the work succeeds, and design the evidence package that demonstrates each claim instead of merely asserting it.

## When to Use

Use this skill when:

- An idea and its hypothesis are fixed and the claims must be made defensible.
- A proposal claims a contribution that no planned experiment would actually demonstrate.
- You need to choose baselines and controls that make the result interpretable.

## Research Method

1. **Name the contribution type explicitly.** New mechanism, new evidence or understanding, new benchmark or dataset, new capability, or a negative result that changes practice. Each type demands a different demonstration.
2. **Write each contribution as a claim the field can reuse**, not as "we propose X". If a reader cannot take the result and apply it, it is a description of activity rather than a contribution.
3. **Attach a demonstration to every claim.** A mechanism claim needs an ablation that isolates the mechanism; a capability claim needs a comparison at matched budget; a benchmark needs adoption criteria. A claim without its demonstration is a promise.
4. **Choose the strongest available baselines before designing the method.** If the method is only compared with weak baselines the contribution cannot be assessed. Prefer the current state of the art plus the simplest strong alternative.
5. **Plan the negative controls.** For any performance claim, include extra-compute and extra-tuning controls so that gains can be attributed to the mechanism rather than to resources.
6. **State the scope of each claim** — the setting in which the collected evidence supports it — and refuse to generalise beyond it in the write-up.
7. **Write the fallback contribution into the plan.** State which result would force the main claim to be restated, and what would still count as a valid contribution in that case.

## Reasoning Guidance

<!-- 迁移自旧模块提示词；具体推理要点见下方逐字来源。 -->

## Evidence Requirements

Each contribution must be paired with the experiment or analysis that would demonstrate it. Baseline choices must be justified from the literature. The compute and tuning budget of every comparison must be stated so that gains are attributable.

## Expected Output

Produce:

- contribution statements with their type
- a per-claim demonstration plan
- the baseline set with its literature justification
- control conditions that isolate the mechanism
- the scope and limits of each claim, plus a fallback contribution

## Workspace Conventions

If this method reads or writes structured workspace files (evidence/claims/decisions, plans, papers, outputs, LaTeX, literature search/download), follow the exact schemas in this plugin's `reference/` directory rather than improvising a format — see [research-assets.md](../../reference/research-assets.md), [plans.md](../../reference/plans.md), [papers.md](../../reference/papers.md), [outputs.md](../../reference/outputs.md), [latex.md](../../reference/latex.md), [literature-search.md](../../reference/literature-search.md), and [paper-fulltext-download.md](../../reference/paper-fulltext-download.md), whichever applies. The `research` skill's [SKILL.md](../research/SKILL.md) is the usual entry point that pulls the right context together first; if this skill was invoked on its own, check whether a `project.md` or `research-state.md` already exists in the workspace before assuming there is none.

## Reference Prompts

The original, more verbose source prompts this method was distilled from are kept in [reference.md](reference.md) for extra detail when the summary above isn't enough (exact length/format constraints, worked examples, etc).
