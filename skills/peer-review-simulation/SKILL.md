---
name: peer-review-simulation
description: "Produce a rigorous, construct-level peer-review critique of a manuscript in the voice of a senior, non-emotional academic reviewer for a high-level journal — auditing journal/genre fit, construct clarity, novelty against existing literature, evidence and citation depth, mechanistic specificity, and predictive/empirical viability, with every critique anchored to an exact manuscript location. Use when A manuscript draft (or a section of one) is ready and the author wants a critical, reviewer-style; or when The user explicitly asks for a \"reviewer simulation,\" \"peer review,\" \"review this paper,\" or a; or when A theoretical or conceptual contribution needs to be checked for whether it is rigorous and."
---

# Peer Review Simulation

> Ported from the ConvFusion research-skill library (category: `academic-writing`; origin: user-provided prompt library (PAPER AGENT/8-1. REVIEWER SIMULATION.txt)). Ask/answer using this method whenever it applies to the current research workspace.

## Purpose

Produce a rigorous, construct-level peer-review critique of a manuscript in the voice of a
senior, non-emotional academic reviewer for a high-level journal — auditing journal/genre fit,
construct clarity, novelty against existing literature, evidence and citation depth, mechanistic
specificity, and predictive/empirical viability, with every critique anchored to an exact
manuscript location.

## When to Use

Use this skill when:

- A manuscript draft (or a section of one) is ready and the author wants a critical, reviewer-style
  read before or instead of submitting it.
- The user explicitly asks for a "reviewer simulation," "peer review," "review this paper," or a
  numeric rating of a paper.
- A theoretical or conceptual contribution needs to be checked for whether it is rigorous and
  operationalizable, not just plausible-sounding.
- `manuscript-revision` or `venue-fit-decision` have already run and the next step is an adversarial
  outside read rather than another self-revision pass.

## Research Method

1. **Journal fit & genre compliance.** Check whether the manuscript actually fits the stated
   mission of its target venue. If it claims to be a review, verify it genuinely surveys the
   literature rather than argues a single position. If it claims novelty, judge whether its level
   of development justifies publication now. State plainly if the work is premature, mispositioned,
   or miscategorized.
2. **Construct clarity & definition audit.** For every major construct introduced: is it clearly
   defined, or circular (defined only via other internal terms), or defined by metaphor instead of
   operational specification? Could it be operationalized in an empirical study from this
   manuscript alone? Name every under-defined construct with its page/line location.
3. **Novelty vs. existing literature.** Identify every claim that existing theories are
   insufficient, and check whether that claim accurately represents the field — flag any straw-man
   characterization of dominant theories, name the established theories that already cover similar
   ground, and ask directly what this framework adds beyond what already exists.
4. **Evidence & citation depth.** Check whether claims carry adequate references, flag broad
   generalizations and "increasingly demonstrated" claims made without citation, and assess overall
   engagement with the literature.
5. **Mechanistic specificity.** For every claim about explanatory power, ask what the mechanism
   actually is, what governs the internal variables proposed, and where words like "alignment,"
   "resonance," or "architecture" are standing in for a concrete causal account — cite page/line for
   each instance.
6. **Predictive & empirical viability.** Judge whether the theory makes distinct, testable
   predictions that are unique relative to existing frameworks, whether its operational definitions
   are sufficient for empirical testing, and whether the model is currently conceptual, metaphorical,
   or formalizable.
7. **Page & line anchoring.** Throughout, quote or paraphrase specific passages and cite their
   page/line location — never write "earlier in the paper" or similarly vague references.
8. **Overall evaluation.** Close with the manuscript's developmental stage, whether it is ready for
   its current venue, and exactly what would need to change for it to become publishable.

## Reasoning Guidance

Write in full academic prose: precise, serious, analytically rigorous, non-emotional. Avoid praise
inflation and vague comments — every critique must be grounded in stated reasoning. Critique
arguments, not authors: no sarcasm, no personal remarks, no casual language. Do not summarize the
manuscript beyond what is needed to ground a specific critique.

## Evidence Requirements

Every major critique must cite a specific page/line (or section/paragraph if the manuscript has no
page numbers) — a claim without a location is not admissible in the review. Do not fabricate
content the manuscript does not contain; if a construct, citation, or result cannot be located,
say so explicitly rather than guessing.

## Expected Output

Produce a full review organized under the eight headings above (Journal Fit, Construct Clarity,
Novelty vs. Literature, Evidence & Citation Depth, Mechanistic Specificity, Predictive & Empirical
Viability, Page & Line Anchoring is woven throughout rather than a separate section, Overall
Evaluation). If the user asked for a numeric rating, close with a single "Rating: X/10" line
justified by the review above — never issue a bare number with no supporting critique.

## Workspace Conventions

If this method reads or writes structured workspace files (evidence/claims/decisions, plans, papers, outputs, LaTeX, literature search/download), follow the exact schemas in this plugin's `reference/` directory rather than improvising a format — see [research-assets.md](../../reference/research-assets.md), [plans.md](../../reference/plans.md), [papers.md](../../reference/papers.md), [outputs.md](../../reference/outputs.md), [latex.md](../../reference/latex.md), [literature-search.md](../../reference/literature-search.md), and [paper-fulltext-download.md](../../reference/paper-fulltext-download.md), whichever applies. The `research` skill's [SKILL.md](../research/SKILL.md) is the usual entry point that pulls the right context together first; if this skill was invoked on its own, check whether a `project.md` or `research-state.md` already exists in the workspace before assuming there is none.

## Reference Prompts

The original, more verbose source prompts this method was distilled from are kept in [reference.md](reference.md) for extra detail when the summary above isn't enough (exact length/format constraints, worked examples, etc).
