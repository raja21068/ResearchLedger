---
name: research-method-design
description: "Convert a committed research strategy into a concrete, testable method: the paradigm, the learning setting, the intervention, the training protocol and the data it requires, stated so that a third party could implement it and know what would falsify it. Use when A strategy exists at the level of an idea but has no implementable method behind it; or when The method is named but its intervention is not stated (for example \"a diffusion model\" with no stated change); or when You need to check that the planned evaluation could actually falsify the mechanism."
---

# Research Method Design

> Ported from the ConvFusion research-skill library (category: `methodology`; origin: planning/method_expansion). Ask/answer using this method whenever it applies to the current research workspace.

## Purpose

Convert a committed research strategy into a concrete, testable method: the paradigm, the learning setting, the intervention, the training protocol and the data it requires, stated so that a third party could implement it and know what would falsify it.

## When to Use

Use this skill when:

- A strategy exists at the level of an idea but has no implementable method behind it.
- The method is named but its intervention is not stated (for example "a diffusion model" with no stated change).
- You need to check that the planned evaluation could actually falsify the mechanism.
- Data requirements must be settled before resources are estimated.

## Research Method

1. **State the paradigm and learning setting first.** Supervised, self-supervised, unsupervised, reinforcement, or a non-learning analytical method. The setting determines which data may legitimately be used and which comparisons are fair; everything downstream is conditional on it.
2. **Name the intervention precisely.** State what changes relative to the closest existing method. "Add conditioning" is a direction, not an intervention; "condition the denoiser on per-pixel transmission estimated by a physics model" is one.
3. **Fix what is held constant.** Backbone, data split, optimiser, schedule and compute budget. A design in which every component moves at once cannot attribute any result to any component.
4. **Specify the training protocol to the level of reproducibility**: objective, schedule, augmentation, regularisation, stopping rule, and the number of seeds. State the cost of a single run, since this becomes the input to resource estimation.
5. **State the data requirement as properties, not dataset names.** Modality, resolution, label type, volume, licensing, and whether the data exists, must be acquired, or must be synthesised. A method needing data that does not exist is a data-collection project first.
6. **Predict the observable difference and the failure signature.** Say which metric should improve, by roughly how much, and what result would show the central mechanism does not work. A method with no failure signature cannot be falsified by its own evaluation.
7. **Check the method against the strategy posture.** If the method quietly requires a component the chosen posture excludes, such as a new module inside a conservative plan, either the method or the posture must change now rather than mid-project.

## Reasoning Guidance

<!-- 迁移自旧模块提示词；具体推理要点见下方逐字来源。 -->

## Evidence Requirements

Claims about what existing methods do must cite the works. Data requirements must distinguish existing datasets from data to be acquired and must state access conditions. Training cost figures must show their basis (model size, dataset size, epochs, hardware class). The intervention must be described in enough detail that an independent researcher could implement it.

## Expected Output

Produce:

- the paradigm and learning setting, with its implications for data and comparison
- the named intervention and the components held constant
- a reproducible training protocol with a per-run cost estimate
- data requirements as properties (modality, volume, labels, licensing, acquisition path)
- the expected observable difference and the failure signature

## Workspace Conventions

If this method reads or writes structured workspace files (evidence/claims/decisions, plans, papers, outputs, LaTeX, literature search/download), follow the exact schemas in this plugin's `reference/` directory rather than improvising a format — see [research-assets.md](../../reference/research-assets.md), [plans.md](../../reference/plans.md), [papers.md](../../reference/papers.md), [outputs.md](../../reference/outputs.md), [latex.md](../../reference/latex.md), [literature-search.md](../../reference/literature-search.md), and [paper-fulltext-download.md](../../reference/paper-fulltext-download.md), whichever applies. The `research` skill's [SKILL.md](../research/SKILL.md) is the usual entry point that pulls the right context together first; if this skill was invoked on its own, check whether a `project.md` or `research-state.md` already exists in the workspace before assuming there is none.

## Reference Prompts

The original, more verbose source prompts this method was distilled from are kept in [reference.md](reference.md) for extra detail when the summary above isn't enough (exact length/format constraints, worked examples, etc).
