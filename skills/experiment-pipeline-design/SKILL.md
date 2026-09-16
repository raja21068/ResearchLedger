---
name: experiment-pipeline-design
description: "Decompose a designed method into an executable, dependency-ordered plan: stages, steps, inputs, outputs, tools, time and the artifact each step must produce, so the work can be scheduled, parallelised and reviewed step by step. Use when A method is designed but not yet broken into work that someone could start this week; or when Steps are described as prose phases with no inputs, outputs or dependencies; or when The work must be parallelised across people or machines."
---

# Experiment Pipeline Design

> Ported from the ConvFusion research-skill library (category: `research-management`; origin: planning/route_expansion, planning/plan_enricher, planning/plan_structurer, planning/plan_canonicalizer). Ask/answer using this method whenever it applies to the current research workspace.

## Purpose

Decompose a designed method into an executable, dependency-ordered plan: stages, steps, inputs, outputs, tools, time and the artifact each step must produce, so the work can be scheduled, parallelised and reviewed step by step.

## When to Use

Use this skill when:

- A method is designed but not yet broken into work that someone could start this week.
- Steps are described as prose phases with no inputs, outputs or dependencies.
- The work must be parallelised across people or machines.
- You need to know the critical path before estimating cost or negotiating a deadline.

## Research Method

1. **Decompose by artifact, not by activity.** Every step must produce a named artifact (a split dataset, a trained checkpoint, a metrics table) that some later step consumes. A step whose output nobody consumes is a checkpoint or should be removed.
2. **Canonicalise the stages.** Collapse each step into exactly one of: data, model build, training, evaluation. Free-text stages such as "do the experiments" hide several distinct steps and destroy schedulability.
3. **Make dependencies explicit and acyclic.** Reference steps by id and require that every input is either the output of an earlier step or a declared external resource. Cycles and dangling inputs are errors to fix, not ambiguities to tolerate.
4. **Attach tools and a time estimate to every step**, with the basis for the estimate (dataset size, model size, number of runs). An estimate without a basis cannot be revised when it turns out to be wrong, which is the only thing that ever happens to estimates.
5. **Mark the critical path and the parallelisable branches.** State which steps the schedule depends on and which can run concurrently; this is what shows where extra compute or extra people actually shorten the project.
6. **Plan evaluation, ablation and sweep runs as first-class steps.** Evaluation consumes the trained artifact and produces the metrics the claims rest on. Enumerate seeds, hyperparameter sweeps and ablations here rather than discovering them after the first results look wrong.
7. **Verify the route against the method.** Walk the pipeline and confirm that every element of the intervention is built by some step and measured by some evaluation step. A method component with no build step or no measurement step is a hole in the plan, not a detail.

## Reasoning Guidance

<!-- 迁移自旧模块提示词；具体推理要点见下方逐字来源。 -->

## Evidence Requirements

Every step must name its inputs, outputs, dependencies, tools and time basis. Artifact names must be consistent across steps so dependencies are mechanically checkable. Time and cost estimates must derive from run count, model size and data volume rather than assertion.

## Expected Output

Produce:

- a step table with id, stage, technique, inputs, outputs, dependencies, tools and time estimate
- the serialised pipeline with the critical path and parallelisable branches marked
- the enumerated training, evaluation, ablation and sweep runs
- a technical-route narrative explaining why this ordering is necessary and what forces it

## Workspace Conventions

If this method reads or writes structured workspace files (evidence/claims/decisions, plans, papers, outputs, LaTeX, literature search/download), follow the exact schemas in this plugin's `reference/` directory rather than improvising a format — see [research-assets.md](../../reference/research-assets.md), [plans.md](../../reference/plans.md), [papers.md](../../reference/papers.md), [outputs.md](../../reference/outputs.md), [latex.md](../../reference/latex.md), [literature-search.md](../../reference/literature-search.md), and [paper-fulltext-download.md](../../reference/paper-fulltext-download.md), whichever applies. The `research` skill's [SKILL.md](../research/SKILL.md) is the usual entry point that pulls the right context together first; if this skill was invoked on its own, check whether a `project.md` or `research-state.md` already exists in the workspace before assuming there is none.

## Reference Prompts

The original, more verbose source prompts this method was distilled from are kept in [reference.md](reference.md) for extra detail when the summary above isn't enough (exact length/format constraints, worked examples, etc).
