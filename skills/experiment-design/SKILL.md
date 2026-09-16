---
name: experiment-design
description: "Decide whether a research question can be tested experimentally at all, then fix a design whose outcome would be interpretable: what is manipulated, what is held fixed, what is measured, and what result would falsify the hypothesis. Use when A hypothesis exists but no executable experiment stands behind it yet; or when You must decide whether the work is programmable, needs new data, or can only be done offline; or when Compute or lab time is about to be committed and the design should be stress-tested first."
---

# Experiment Design & Feasibility

> Ported from the ConvFusion research-skill library (category: `experiment`; origin: experiment/design, experiment/simulation). Ask/answer using this method whenever it applies to the current research workspace.

## Purpose

Decide whether a research question can be tested experimentally at all, then fix a design whose outcome would be interpretable: what is manipulated, what is held fixed, what is measured, and what result would falsify the hypothesis.

## When to Use

Use this skill when:

- A hypothesis exists but no executable experiment stands behind it yet.
- You must decide whether the work is programmable, needs new data, or can only be done offline.
- Compute or lab time is about to be committed and the design should be stress-tested first.

## Research Method

1. **Test feasibility before designing.** Classify the experiment on three axes: can the core manipulation be implemented in software, does it need data that exists or can be obtained, and does it need physical-world access (hardware, participants, wet lab). Name the specific non-simulable dependency behind any not-programmable verdict, and state which sub-parts remain programmable.
2. **State the question as a comparison with a falsification condition.** Write the research question, the hypothesis, and the observation that would show the hypothesis false. If no possible outcome would count against it, the design is not an experiment.
3. **Fix the manipulation and the controls.** Specify the independent variables and their levels, everything held constant, and the controls that rule out the obvious alternative explanations (data, capacity, tuning budget). A design with no controls cannot attribute an effect.
4. **Choose outcome measures and the split protocol before running.** Name the primary metric, the secondary metrics and the data splits, and decide when test data may be touched. Measurements picked after seeing results are not measurements.
5. **Stress-test the design by pre-run simulation.** Predict expected values and their plausible spread from published numbers and the baselines, then judge whether the predicted effect is large enough to be distinguishable from run-to-run variation. If it is not, revise the design rather than proceeding.
6. **Record the refinement as a versioned design.** When simulation or review changes the design, keep the change, the reason and the resulting version. The design handed to implementation must be the refined one, and predicted values must stay labelled as predictions.

## Reasoning Guidance

<!-- 迁移自旧模块提示词；具体推理要点见下方逐字来源。 -->

## Evidence Requirements

Feasibility verdicts must name the concrete dependency (dataset id, hardware, population). Each design choice — metric, split, control, baseline — must cite literature or a pilot rather than preference. Pre-run simulated values must be labelled as predictions and must never appear later as measured results.

## Expected Output

Produce:

- feasibility verdict per axis, with the non-programmable dependency named
- research question, hypothesis and falsification condition
- variables, levels, controls and constant factors
- primary and secondary metrics with the split protocol
- versioned design plus the recorded refinements and their reasons

## Workspace Conventions

If this method reads or writes structured workspace files (evidence/claims/decisions, plans, papers, outputs, LaTeX, literature search/download), follow the exact schemas in this plugin's `reference/` directory rather than improvising a format — see [research-assets.md](../../reference/research-assets.md), [plans.md](../../reference/plans.md), [papers.md](../../reference/papers.md), [outputs.md](../../reference/outputs.md), [latex.md](../../reference/latex.md), [literature-search.md](../../reference/literature-search.md), and [paper-fulltext-download.md](../../reference/paper-fulltext-download.md), whichever applies. The `research` skill's [SKILL.md](../research/SKILL.md) is the usual entry point that pulls the right context together first; if this skill was invoked on its own, check whether a `project.md` or `research-state.md` already exists in the workspace before assuming there is none.

## Reference Prompts

The original, more verbose source prompts this method was distilled from are kept in [reference.md](reference.md) for extra detail when the summary above isn't enough (exact length/format constraints, worked examples, etc).
