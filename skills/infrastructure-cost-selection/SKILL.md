---
name: infrastructure-cost-selection
description: "Turn an audited resource requirement into costed, feasibility-checked infrastructure options and one recommended plan that respects budget, deadline and data-governance constraints, with the rejected options and their prices kept on record. Use when A resource estimate exists and must become something purchasable or bookable; or when Several providers, or a cloud-versus-on-prem choice, are plausible and the decision is contested; or when A budget or deadline is fixed and you must show whether the plan fits inside it."
---

# Infrastructure and Cost Selection

> Ported from the ConvFusion research-skill library (category: `research-management`; origin: resource/instance_selection, resource/infra_selection, resource/cost_estimation, resource/recommendation, resource/consistency_validation). Ask/answer using this method whenever it applies to the current research workspace.

## Purpose

Turn an audited resource requirement into costed, feasibility-checked infrastructure options and one recommended plan that respects budget, deadline and data-governance constraints, with the rejected options and their prices kept on record.

## When to Use

Use this skill when:

- A resource estimate exists and must become something purchasable or bookable.
- Several providers, or a cloud-versus-on-prem choice, are plausible and the decision is contested.
- A budget or deadline is fixed and you must show whether the plan fits inside it.
- A quoted cost looks too low and you suspect storage, checkpoints or egress were ignored.

## Research Method

1. **Gate on feasibility before ranking on price.** Check each candidate against the full requirement, namely GPU-hours, CPU, memory, storage tiers, network and the deadline, and mark it feasible, scalable (meets the need after a stated adjustment) or infeasible. Drop infeasible candidates before any score is computed; free tiers are infeasible by default unless they demonstrably satisfy the requirement.
2. **Keep near-misses as candidates.** A candidate that fits after increasing GPU count or extending the deadline is a real option and belongs in the comparison with its adaptation plan stated. Do not reject it on GPU-model mismatch alone when the performance model says the compute requirement can be met.
3. **Price the whole plan, not the GPU-hour.** Include compute, storage at each tier, checkpoints, network egress and data transfer, and the human time to operate the setup. State the pricing source and date. A total that omits storage and egress is not a total and will not survive contact with the invoice.
4. **Normalise heterogeneous options onto one basis.** Convert on-demand, reserved or spot cloud pricing and amortised on-prem hardware into a common currency and period, and state which cost model was used. Comparing a monthly reservation against an hourly rate without normalisation is a category error.
5. **Score cost, time and risk explicitly, with weights fixed in advance.** Report per-criterion scores alongside the aggregate so a reviewer can see whether the winner won on price or on risk. An aggregate score with invisible weights cannot be argued with and therefore cannot be trusted.
6. **Cross-check the chain.** Verify that providers in the infrastructure set have corresponding instances, that every priced instance traces back to a requirement, and that the recommended option appears in the feasible set. Mismatches are errors to surface, not to repair silently.
7. **Recommend with the trade-off stated, or return an explicit no-feasible-option verdict.** If nothing satisfies the constraints, say so and name the binding constraint and the relaxation that would open the option set. Do not introduce a fallback that the constraints already exclude.

## Reasoning Guidance

<!-- 迁移自旧模块提示词；具体推理要点见下方逐字来源。 -->

## Evidence Requirements

Every price must cite its source and date. Each rejected option must carry its price and the reason it lost. Feasibility verdicts must show the requirement-versus-capacity comparison. When no feasible option exists, the binding constraint and the required relaxation must be stated explicitly.

## Expected Output

Produce:

- feasibility-gated candidate instances and infrastructure options per provider
- a full cost breakdown (compute, storage, egress, human time) with pricing provenance
- a ranked shortlist with per-criterion scores, stated weights and the recommended option
- the trade-off rationale plus rejected options with their prices
- a consistency report across requirement, instances, infrastructure and cost, or an explicit no-feasible-option verdict

## Workspace Conventions

If this method reads or writes structured workspace files (evidence/claims/decisions, plans, papers, outputs, LaTeX, literature search/download), follow the exact schemas in this plugin's `reference/` directory rather than improvising a format — see [research-assets.md](../../reference/research-assets.md), [plans.md](../../reference/plans.md), [papers.md](../../reference/papers.md), [outputs.md](../../reference/outputs.md), [latex.md](../../reference/latex.md), [literature-search.md](../../reference/literature-search.md), and [paper-fulltext-download.md](../../reference/paper-fulltext-download.md), whichever applies. The `research` skill's [SKILL.md](../research/SKILL.md) is the usual entry point that pulls the right context together first; if this skill was invoked on its own, check whether a `project.md` or `research-state.md` already exists in the workspace before assuming there is none.

## Reference Prompts

The original, more verbose source prompts this method was distilled from are kept in [reference.md](reference.md) for extra detail when the summary above isn't enough (exact length/format constraints, worked examples, etc).
