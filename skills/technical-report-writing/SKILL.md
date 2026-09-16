---
name: technical-report-writing
description: "Document a research result so a colleague can reproduce or build on it: what was done, how, what was found, what it does not cover, and how to rerun it. Use when An engineering or internal audience must act on the result rather than cite it; or when A result needs to be recorded before or instead of a paper (industry setting, project deliverable); or when Reproduction details exist but are scattered across logs, configs and plans."
---

# Technical Report Writing

> Ported from the ConvFusion research-skill library (category: `academic-writing`; origin: stage5.1/output-transformation). Ask/answer using this method whenever it applies to the current research workspace.

## Purpose

Document a research result so a colleague can reproduce or build on it: what was done, how, what was found, what it does not cover, and how to rerun it.

## When to Use

Use this skill when:

- An engineering or internal audience must act on the result rather than cite it.
- A result needs to be recorded before or instead of a paper (industry setting, project deliverable).
- Reproduction details exist but are scattered across logs, configs and plans.

## Research Method

1. **Lead with what the reader must do with it.** State scope first: what question this report answers and what is deliberately out of scope.
2. **Record operational detail, not argument.** Exact versions, configurations, commands, paths and hardware. A report is judged by whether someone else can rerun it.
3. **Report results with their setting attached.** Every number carries dataset, baseline, metric and seed policy; an unattached number is unusable.
4. **State limitations explicitly.** What was not tested, which conditions were assumed, where the result is known to break.
5. **Write reproduction instructions as steps someone else can follow**, referencing the actual artefacts (result files, logs) rather than describing them.
6. **Do not claim novelty or priority.** A technical report documents work; establishing priority belongs to a paper. Remove "first to" / "state of the art" phrasing.

## Reasoning Guidance

Focus on:

- What the reader will try to do next, and what they would need to know.
- The gap between what the logs contain and what a reader needs.
- Where the result is sensitive to a choice that is easy to get wrong.
- Which artefacts must be preserved for the report to stay verifiable.

Avoid:

- Turning the report into a paper: no related-work argument, no contribution claims.
- Reporting only the runs that worked.
- Describing the pipeline in prose when a command or config listing would be reproducible.
- Summarising away the exact numbers the reader needs.

## Evidence Requirements

Each reported result should reference the evidence item and the raw artefact it came from. Reproduction instructions must name real files and versions, not describe them abstractly.

## Expected Output

Produce:

- summary and scope (including what is out of scope)
- approach and implementation details (versions, configs, environment)
- results with setting attached and artefacts referenced
- explicit limitations and assumptions
- reproduction instructions a colleague can follow

## Workspace Conventions

If this method reads or writes structured workspace files (evidence/claims/decisions, plans, papers, outputs, LaTeX, literature search/download), follow the exact schemas in this plugin's `reference/` directory rather than improvising a format — see [research-assets.md](../../reference/research-assets.md), [plans.md](../../reference/plans.md), [papers.md](../../reference/papers.md), [outputs.md](../../reference/outputs.md), [latex.md](../../reference/latex.md), [literature-search.md](../../reference/literature-search.md), and [paper-fulltext-download.md](../../reference/paper-fulltext-download.md), whichever applies. The `research` skill's [SKILL.md](../research/SKILL.md) is the usual entry point that pulls the right context together first; if this skill was invoked on its own, check whether a `project.md` or `research-state.md` already exists in the workspace before assuming there is none.
