---
name: simulation-baseline
description: "Produce expected results when the real experiment cannot be run yet — hardware, data or lab access unavailable — as explicit, labelled predictions anchored on published numbers and the baselines, so that design decisions and the expected margin over baselines can be judged before execution, and so that no simulated value ever masquerades as a measurement. Use when The experiment needs hardware, a dataset or lab access that is not available yet, but the design depends on the expected magnitude of the effect; or when Baselines cannot be reimplemented yet, so expected baseline values are needed to judge whether the expected gain justifies the work; or when A pre-registered expectation is wanted before execution, so that later interpretation of real runs stays honest."
---

# Simulation-First Results & Baseline Reference

> Ported from the ConvFusion research-skill library (category: `experiment`; origin: experiment/simulation, experiment/design, experiment/lab_offline). Ask/answer using this method whenever it applies to the current research workspace.

## Purpose

Produce expected results when the real experiment cannot be run yet — hardware, data or lab access unavailable — as explicit, labelled predictions anchored on published numbers and the baselines, so that design decisions and the expected margin over baselines can be judged before execution, and so that no simulated value ever masquerades as a measurement.

## When to Use

Use this skill when:

- The experiment needs hardware, a dataset or lab access that is not available yet, but the design depends on the expected magnitude of the effect.
- Baselines cannot be reimplemented yet, so expected baseline values are needed to judge whether the expected gain justifies the work.
- A pre-registered expectation is wanted before execution, so that later interpretation of real runs stays honest.

Do **not** use it when:

- The experiment can actually be run — a simulation is never a substitute for an available measurement.
- The question is whether the method works rather than what magnitude is plausible; only real runs can answer that.
- A simulated value would enter an abstract, result table, figure or claim without a simulated label.

## Research Method

1. **Anchor every number on the frozen design and the literature.** Take the design version, the primary metric and the baseline set. For each baseline use values reported under a comparable setting (data version, split, metric definition, compute) and record the citation. Where no comparable value exists, say so instead of inventing one.
2. **Predict a band, not a point.** For every metric give expected, optimistic and pessimistic values, and name the assumption that separates them (tuning budget, data scale, compute). A single number hides exactly the uncertainty the design needs to see.
3. **State the generative assumption so each number is recomputable.** Write what is extrapolated, from which anchor, under which scaling assumption. A prediction nobody can recompute or refute is an opinion, not a simulation.
4. **Assess simulation quality explicitly and honestly.** Report confidence together with its justification and the risks: how close the anchor setting is, whether the claimed mechanism is even representable in that anchor, and what would make the extrapolation invalid. Confidence is high only when closely comparable published results exist, and must be low for a novel task, metric or domain.
5. **Compare against the baselines and pre-declare the decision.** Give the predicted margin and state whether it clears the run-to-run variation threshold fixed in the evaluation protocol. If it does not, revise the design instead of proceeding — the simulation exists to stop a weak experiment before it consumes resources.
6. **Label simulated values at creation, everywhere.** File names, frontmatter, table headers, axis labels and figure captions must say simulated or predicted. Simulated values live in their own artefacts and are never merged into a table of measured runs.
7. **Plan the replacement and the falsification.** For each simulated value state which pilot or full run will replace it and what observed result would falsify the prediction. Once real runs exist the simulation is superseded, and a superseded prediction must not remain in a claim.

## Reasoning Guidance

Focus on:

- What the simulation is for: sizing the effect, choosing the design, pre-registering expectations, and giving the paper a baseline reference before real runs exist.
- Where each anchor number came from and how comparable that setting really is to yours.
- Which parts of the design remain uncertain after the simulation, and which pilot run would reduce that uncertainty most.

Avoid:

- Presenting a predicted value as a result, or letting a simulated number survive into a results table, figure or claim once real runs exist.
- Confidence that is not justified by a comparable published benchmark.
- Using simulation to avoid an experiment that is actually feasible with the available resources.

## Evidence Requirements

The design version, primary metric and baseline set the prediction was derived from; per-metric predicted ranges with the anchor citation behind each baseline; the generative assumption that makes each number recomputable; an explicit quality assessment giving confidence, justification and risks; the simulated label present on every artefact carrying a predicted value; and the replacement plan mapping each simulated value to the run that will supersede it. A simulated value supports no claim about whether the method works.

## Expected Output

Produce:

- predicted metric ranges with the assumption behind each bound
- per-baseline expected values with sources, each marked as measured anchor or estimate
- predicted margin against the pre-declared decision threshold, with the go/no-go it implies
- simulation quality: confidence, justification and risks
- expected chart and table descriptions, marked as expected rather than observed
- label policy applied to artefacts plus the sim-to-real replacement plan

## Workspace Conventions

If this method reads or writes structured workspace files (evidence/claims/decisions, plans, papers, outputs, LaTeX, literature search/download), follow the exact schemas in this plugin's `reference/` directory rather than improvising a format — see [research-assets.md](../../reference/research-assets.md), [plans.md](../../reference/plans.md), [papers.md](../../reference/papers.md), [outputs.md](../../reference/outputs.md), [latex.md](../../reference/latex.md), [literature-search.md](../../reference/literature-search.md), and [paper-fulltext-download.md](../../reference/paper-fulltext-download.md), whichever applies. The `research` skill's [SKILL.md](../research/SKILL.md) is the usual entry point that pulls the right context together first; if this skill was invoked on its own, check whether a `project.md` or `research-state.md` already exists in the workspace before assuming there is none.

## Reference Prompts

The original, more verbose source prompts this method was distilled from are kept in [reference.md](reference.md) for extra detail when the summary above isn't enough (exact length/format constraints, worked examples, etc).
