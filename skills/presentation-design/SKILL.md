---
name: presentation-design
description: "Turn a research result into a talk that carries one argument: what problem, why prior answers fail, what was done, what was found, and what it means. Use when A result must be presented live (conference, group meeting, review); or when An existing paper needs to become a talk for audiences with different backgrounds; or when A result is being questioned and you need to walk an audience through the evidence."
---

# Research Presentation Design

> Ported from the ConvFusion research-skill library (category: `academic-writing`; origin: stage5.1/output-transformation). Ask/answer using this method whenever it applies to the current research workspace.

## Purpose

Turn a research result into a talk that carries one argument: what problem, why prior answers fail, what was done, what was found, and what it means.

## When to Use

Use this skill when:

- A result must be presented live (conference, group meeting, review).
- An existing paper needs to become a talk for audiences with different backgrounds.
- A result is being questioned and you need to walk an audience through the evidence.

## Research Method

1. **Fix the single argument first.** A talk that tries to convey the whole paper conveys nothing. Decide the one thing the audience should remember, then cut everything that does not serve it.
2. **Order the narrative as problem → why existing answers fail → key insight → approach → evidence → what it means.** This is an argument order, not a summary of the paper's section order.
3. **One idea per slide.** Text on a slide competes with the speaker; keep the slide to the claim plus the support it needs.
4. **Attach the setting to every number shown.** Slides get remembered without their caveats, so dataset, baseline and metric must be visible on the slide itself.
5. **State limitations in the talk**, in their own slide. It makes the rest credible and prevents the audience from drawing a stronger conclusion than the evidence supports.
6. **Prepare the backup slides from the questions you expect**: the ablation, the failure cases, the alternative baseline. Anticipating the challenge is part of the design.

## Reasoning Guidance

Focus on:

- What the audience already believes, and what must be shifted.
- Which single result is most convincing, and what setup it needs to be understood.
- Where the audience is likely to disbelieve, and which slide answers it.
- What can be removed without weakening the argument.

Avoid:

- Reproducing the paper's structure slide by slide.
- Showing numbers without their setting.
- Unbounded claims in headlines — the caveat is never remembered with the claim.
- Dense slides that the speaker then reads aloud.

## Evidence Requirements

Numbers shown must be traceable to evidence items; cite the evidence id on the slide or in the notes. Any comparison shown must state its setting on the same slide.

## Expected Output

Produce:

- the single argument of the talk, stated in one sentence
- a slide outline following problem → gap → insight → approach → evidence → implications
- per-slide content: the claim, its support, and the setting for any number
- a limitations slide
- backup slides for anticipated questions

## Workspace Conventions

If this method reads or writes structured workspace files (evidence/claims/decisions, plans, papers, outputs, LaTeX, literature search/download), follow the exact schemas in this plugin's `reference/` directory rather than improvising a format — see [research-assets.md](../../reference/research-assets.md), [plans.md](../../reference/plans.md), [papers.md](../../reference/papers.md), [outputs.md](../../reference/outputs.md), [latex.md](../../reference/latex.md), [literature-search.md](../../reference/literature-search.md), and [paper-fulltext-download.md](../../reference/paper-fulltext-download.md), whichever applies. The `research` skill's [SKILL.md](../research/SKILL.md) is the usual entry point that pulls the right context together first; if this skill was invoked on its own, check whether a `project.md` or `research-state.md` already exists in the workspace before assuming there is none.
