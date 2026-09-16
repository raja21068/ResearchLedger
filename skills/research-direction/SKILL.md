---
name: research-direction
description: "Move from a set of candidate directions to one committed direction, with the reasoning recorded so later decisions can be understood in their original context. Use when Several candidate directions exist and one must be chosen; or when A direction is being questioned and you must decide whether to continue or change; or when The user has given preferences (risk appetite, time budget, venue target) that should shape the choice."
---

# Research Direction

> Ported from the ConvFusion research-skill library (category: `research-decision`; origin: initiation/incubation, decision). Ask/answer using this method whenever it applies to the current research workspace.

## Purpose

Move from a set of candidate directions to one committed direction, with the reasoning recorded so later decisions can be understood in their original context.

## When to Use

Use this skill when:

- Several candidate directions exist and one must be chosen.
- A direction is being questioned and you must decide whether to continue or change.
- The user has given preferences (risk appetite, time budget, venue target) that should shape the choice.

## Research Method

1. **Enumerate the candidates explicitly** before evaluating any of them. Candidates never written down cannot be compared.
2. **Evaluate on separated dimensions**: novelty, feasibility, expected impact, cost, risk. Score independently — a single overall score hides exactly the trade-off the decision turns on.
3. **Apply the user's stated preferences as constraints, not tie-breakers.** If the user prioritises low risk, a high-ceiling high-variance direction fails regardless of its ceiling. Say so rather than letting the score quietly decide.
4. **Identify the critical path** for each candidate: which single dependency, if unavailable, kills it. Prefer a direction whose critical path you can actually walk.
5. **Look for the option that survives its own failure.** A direction whose negative result is still informative is usually better than one whose failure yields nothing.
6. **Record the decision** with alternatives considered and the reason, naming the evidence and preferences that drove it.

## Reasoning Guidance

Focus on:

- Whether the candidate is falsifiable within the available resources.
- What happens if the central hypothesis is wrong — is there a fallback result?
- Whether the direction depends on an external capability you do not control.
- Honest cost: not just compute, but time to obtain the data and baselines.

Avoid:

- Letting a single aggregate score decide; report the per-dimension picture.
- Selecting the theoretically most elegant direction when its critical path is unavailable.
- Treating the user's preferences as soft suggestions to be overridden by a higher score.
- Leaving the rejected candidates unrecorded — they are the context for the decision.

## Evidence Requirements

Feasibility claims should reference what makes them feasible (existing code, available data, prior results). Risk claims should name the specific thing that could fail. Novelty claims should cite the gap analysis or literature that establishes them.

## Expected Output

Produce:

- the candidate directions
- per-dimension evaluation for each, not a single score
- the critical path and fallback for the leading candidates
- the decision, alternatives considered, and the reason
- explicit note of which user preference drove the outcome

## Workspace Conventions

If this method reads or writes structured workspace files (evidence/claims/decisions, plans, papers, outputs, LaTeX, literature search/download), follow the exact schemas in this plugin's `reference/` directory rather than improvising a format — see [research-assets.md](../../reference/research-assets.md), [plans.md](../../reference/plans.md), [papers.md](../../reference/papers.md), [outputs.md](../../reference/outputs.md), [latex.md](../../reference/latex.md), [literature-search.md](../../reference/literature-search.md), and [paper-fulltext-download.md](../../reference/paper-fulltext-download.md), whichever applies. The `research` skill's [SKILL.md](../research/SKILL.md) is the usual entry point that pulls the right context together first; if this skill was invoked on its own, check whether a `project.md` or `research-state.md` already exists in the workspace before assuming there is none.

## Reference Prompts

The original, more verbose source prompts this method was distilled from are kept in [reference.md](reference.md) for extra detail when the summary above isn't enough (exact length/format constraints, worked examples, etc).
