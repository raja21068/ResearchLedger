---
name: systematic-literature-synthesis
description: "Build a large, recent literature corpus (40-100 papers, last 2-3 years) into comparable structured evidence records, synthesize the patterns across the whole corpus, and derive a gap inventory whose every entry has survived a deliberate attempt to kill it — so \"few studies have explored X\" is never mistaken for a finding. Use when The user wants a literature universe built at scale (tens of papers, not a handful) as the basis; or when Each candidate paper needs to be turned into a comparable, structured record before any; or when A \"research gap\" is about to be asserted and must survive scrutiny before it becomes the basis of."
---

# Systematic Literature Synthesis & Validated Gap Inventory

> Ported from the ConvFusion research-skill library (category: `literature`; origin: user-provided workflow (literature universe -> structured evidence -> landscape -> validated gap inventory)). Ask/answer using this method whenever it applies to the current research workspace.

## Purpose

Build a large, recent literature corpus (40-100 papers, last 2-3 years) into comparable structured
evidence records, synthesize the patterns across the whole corpus, and derive a gap inventory whose
every entry has survived a deliberate attempt to kill it — so "few studies have explored X" is
never mistaken for a finding.

## When to Use

Use this skill when:

- The user wants a literature universe built at scale (tens of papers, not a handful) as the basis
  for serious idea generation, not a quick five-paper skim.
- Each candidate paper needs to be turned into a comparable, structured record before any
  cross-paper pattern claim is trusted.
- A "research gap" is about to be asserted and must survive scrutiny before it becomes the basis of
  a research direction, a plan, or a claim.

## Research Method

Run these four phases in order. Each phase's output is the next phase's input — don't synthesize a
landscape from an unscreened pile of abstracts, and don't propose a gap that skipped validation.

### Phase 1 — Build the literature universe

1. Use `literature-search` (OpenAlex, keyless) with the year filter set to the requested window
   (default: the last 2-3 years unless the user says otherwise) and a query built from the actual
   research question, not just the topic's name.
2. Screen every hit with `literature-screening`'s stated-criteria approach, logging why each
   inclusion/exclusion decision was made. Target the requested corpus size (40-100 is typical) —
   after screening, not as a raw hit count.
3. Where the extraction in Phase 2 needs details that never appear in an abstract (dataset splits,
   baseline numbers, ablations, stated limitations), fetch the full text with
   `paper-fulltext-download` before extracting.

### Phase 2 — Convert every paper into a structured evidence record

For each included paper, extract exactly these ten fields, in this fixed order, so records stay
comparable across the whole corpus. Write each as an evidence record (see
`../../reference/research-assets.md` for the evidence file schema — `source_kind: literature`,
`citation` set to the paper), with these ten fields as the body instead of the default template:

1. **Problem** — the specific problem or question this paper addresses (not the field in general).
2. **Dataset** — dataset(s) used, scale, and split.
3. **Core Method** — the actual mechanism, one or two sentences, stripped of marketing language.
4. **Baseline(s)** — what it's compared against.
5. **Baseline Results** — the actual numbers, with the metric and its direction (higher/lower is
   better).
6. **Evaluation Settings** — protocol, metrics, hardware, hyperparameters, if the paper states them.
7. **External Validation** — was this tested outside the paper's own benchmark/domain/population? If
   not, say so explicitly rather than leaving it implicit.
8. **Robustness / Missing Tests** — what the paper does *not* test: ablations not run, conditions
   not tried, robustness or generalization checks skipped. This field is usually the richest source
   of later gaps — don't leave it thin.
9. **Author's Stated Future Work** — the authors' own words (or a close paraphrase) about what they
   flagged as open, future, or out of scope.
10. **Our Observation** — your own critical note: what's suspicious, what doesn't add up, what claim
    in this paper would itself need scrutiny before being trusted as a building block.

A paper with no extractable value in a field gets an explicit "not stated" for that field — never a
silently omitted section, and never a guessed value standing in for a real one.

### Phase 3 — Build the research landscape

Once the corpus has structured records, hand off to `research-landscape` to synthesize what's
settled, what's contested, and what's moving — grouped by each record's Problem and Core Method
fields so the landscape reflects the actual corpus, not a generic summary of the topic.

### Phase 4 — Generate a gap inventory, but kill fake gaps first

**This phase is the one most likely to be done badly, and it matters most.** A language model (or a
tired human) will readily produce a sentence like *"Few studies have explored X."* That sentence is
not automatically a research gap — it's a guess that has not yet been checked.

**Step 1: classify each candidate gap by type.** These are *corpus-level* gaps — a blind spot in
the field as a whole — not the same thing as the manuscript-level gaps in
`../../reference/papers.md` (which describe what *your own draft* is missing). Don't conflate the
two.

| Gap type | What it means |
|---|---|
| Performance gap | No method in the corpus reaches acceptable performance on a specific, named sub-case. |
| Generalization gap | Methods are validated only within one dataset/domain/population and never shown to transfer. |
| Methodological gap | A plausible technique from an adjacent area hasn't been applied here, with a stated reason it should help. |
| Evaluation gap | No accepted protocol/metric exists for a phenomenon the field claims matters, so claims about it can't be compared. |
| Dataset gap | No dataset exists (or none public/adequate) with the properties a rigorous test of the claim would need. |
| Mechanistic gap | Results are reported but there is no accepted explanation of *why* the method works — correlation without a causal account. |
| Contradiction gap | Two or more papers report genuinely conflicting findings under comparable conditions, unreconciled. |
| Robustness gap | Methods are evaluated only under clean/ideal conditions; a specific, named perturbation or failure mode is untested. |
| Efficiency gap | Methods work, but at a compute/data/latency cost nobody has tried to reduce, despite the field caring about deployability. |
| Translation gap | A method demonstrated in a lab/benchmark setting has never been tested in the applied, real-world setting. |

**Step 2: run every candidate gap through all three tests before it's allowed into the inventory.**

- **Test 1 — Is it actually missing?** Search specifically for the supposed gap — don't infer
  absence from your own reading list. For example: `"<topic>" "missing modalities" 2025 2026`. If
  recent work already addresses it, the gap is dead. Record the query you ran and what it returned,
  even when the gap dies here.
- **Test 2 — Does it matter?** Suppose nobody has combined Method A with Method B — that alone does
  not make it important. Ask: what scientific or practical problem would this actually solve? If
  there's no compelling answer, kill it. Novelty of combination is not a substitute for
  significance.
- **Test 3 — Can we investigate it?** A surviving gap must lead naturally to a concrete
  experiment, dataset, benchmark, hypothesis, or methodological test. A gap that only supports
  another sentence like itself is not investigable — kill it.

Only gaps that survive all three tests are written into the gap inventory. Gaps that die at any
test are kept too, in a visible "killed" log with the test and reason they failed — the discipline
must be auditable, not just its survivors.

## Reasoning Guidance

Treat "few studies have explored X" as a hypothesis to be tested, never as a conclusion. Prefer a
short inventory of gaps that all survived validation over a long list that sounds impressive but
would collapse under Test 1. When in doubt about whether a gap is real, run the search — don't
reason your way around doing it.

## Evidence Requirements

Every surviving gap must cite: the Test 1 search actually run and its result, the Test 2 answer to
"why does this matter," and the Test 3 concrete investigable form. A gap with no recorded Test 1
search is not eligible for the inventory, no matter how plausible it sounds. Every structured
evidence record (Phase 2) must cite the source paper and flag any of the ten fields that were not
stated in the paper, rather than silently filling them in.

## Expected Output

Produce:

- A literature universe: N screened papers (with the raw hit count and screening criteria used),
  each as a structured evidence record with all ten fields.
- A research landscape summary produced from that corpus (via `research-landscape`).
- A validated gap inventory: each surviving entry with its type (from the ten-type taxonomy above),
  the claim, and its Test 1/2/3 justification.
- A killed-gaps log: each candidate that failed a test, which test it failed, and why — kept
  alongside the inventory, not deleted, so the validation discipline stays checkable.

## Workspace Conventions

If this method reads or writes structured workspace files (evidence/claims/decisions, plans, papers, outputs, LaTeX, literature search/download), follow the exact schemas in this plugin's `reference/` directory rather than improvising a format — see [research-assets.md](../../reference/research-assets.md), [plans.md](../../reference/plans.md), [papers.md](../../reference/papers.md), [outputs.md](../../reference/outputs.md), [latex.md](../../reference/latex.md), [literature-search.md](../../reference/literature-search.md), and [paper-fulltext-download.md](../../reference/paper-fulltext-download.md), whichever applies. The `research` skill's [SKILL.md](../research/SKILL.md) is the usual entry point that pulls the right context together first; if this skill was invoked on its own, check whether a `project.md` or `research-state.md` already exists in the workspace before assuming there is none.
