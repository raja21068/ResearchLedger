---
name: submission-compile-and-format
description: "Turn the revised text into a venue-conformant manuscript that compiles: correct LaTeX, escaped special characters, a reference list built from real metadata, and no leftover markup artefacts. Use when The manuscript must leave Markdown and become a compilable LaTeX document (every paper does, eventually); or when The manuscript fails to compile, or the compile log reports errors that must be addressed; or when The text still contains Markdown artefacts such as heading hashes, emphasis markers or raw underscores."
---

# Submission Formatting and Compile Repair

> Ported from the ConvFusion research-skill library (category: `academic-writing`; origin: paper/latex (latex_validator, latex_llm_fixer), paper/narrative (reference)). Ask/answer using this method whenever it applies to the current research workspace.

## Purpose

Turn the revised text into a venue-conformant manuscript that compiles: correct LaTeX, escaped special characters, a reference list built from real metadata, and no leftover markup artefacts.

## When to Use

Use this skill when:

- The manuscript must leave Markdown and become a compilable LaTeX document (every paper does, eventually).
- The manuscript fails to compile, or the compile log reports errors that must be addressed.
- The text still contains Markdown artefacts such as heading hashes, emphasis markers or raw underscores.
- References are missing, are placeholders, or use "Anonymous" as an author.

## Research Method

0. **Drive the `research_paper_latex` tool — do not hand-write LaTeX.** The manuscript stays Markdown (`papers/<paperId>/paper.md`) and is converted, never re-typed:
   - `action: "compose"` — turns `paper.md` into `papers/<paperId>/latex/main.tex` (+ `main_intermediate.tex`, which keeps raw `[cite_key]` placeholders so you can read what the converter saw). Markdown headings, inline emphasis and stray `%` are handled here; an existing `main.tex` is backed up first. Pick the template at this step: `conference` (IEEEtran, default) or `journal` (IEEEtran journal option).
   - `action: "compile"` — runs Tectonic and produces `main.pdf`; returns `{ success, errors }`.
   - `action: "repair"` — deterministic, LLM-free repair of `main.tex` from the last compile log (escapes stray `%`, fixes double-subscript and math-mode errors). Run it before spending your own effort.
   - `action: "errors"` — structured errors with line numbers **and the surrounding code**, which is what you need to fix what `repair` could not. Then `compile` again.
   - `action: "validate"` — advisory list of unrecognised commands/environments; it is not a gate and a nonzero list is not a failure.
   - `action: "status"` — what is currently in `latex/`.
   The loop is: `compose` → `compile` → if it fails, `repair` → `compile` → if it still fails, read `errors` and **edit `main.tex` yourself** → `compile`. Stop when `compile` returns `success: true`; do not loop indefinitely.
1. **Separate syntax repair from content.** Every fix in this skill is syntactic; if a correction would change a claim, a number or a citation, stop and route it back to the writing skill.
2. **Fix encoding and escaping first**, because they cascade: escape reserved characters, convert Markdown emphasis and headings into the corresponding LaTeX environments and commands, and replace Unicode math symbols with their commands.
3. **Balance environments and structure** so every begin has an end, required packages are declared, and no empty environment remains.
4. **Repair errors in bounded batches grouped by cause, not by symptom.** When many errors share one cause, fix a representative, recompile and re-read the log rather than patching every occurrence blindly; if the log cannot be parsed, treat the raw log as the error context instead of guessing.
5. **Build the reference list from real metadata.** Format entries in the venue style, order them by citation number, and omit a missing field rather than filling it with a placeholder — never emit "Anonymous" or fabricated page ranges. Note what the converter does and does not do: it rewrites `[key]`, `[key1, key2]` and `[12]`-style citations into `\cite{...}` from the `## References` section, but **author–year prose citations like `(Smith et al., 2024)` are left as plain text** — they need a real `.bib`/`\citep` pass or a rewrite in the manuscript.
6. **Re-verify after each pass**: the document compiles, the reference list contains exactly the cited keys, and the diff contains no change to scientific content.

## Known Limits of the Converter

- **Markdown tables are passed through as plain text** (pipes and all); they must be turned into `table`/`tabular` LaTeX separately. This matches the legacy pipeline, where tables arrived pre-rendered as artifacts.
- **Inline emphasis is converted** (`**x**` → `\textbf{x}`, `*x*` → `\textit{x}`) while math regions are protected, but an *unpaired* `*` (e.g. a footnote dagger like `f*`) is intentionally left alone.
- Abstract comes from `## Abstract`; the title from the `#` heading; `## References` feeds `\bibitem`. Everything else becomes a `\section`.
- Tectonic needs a writable cache; the tool points it inside the paper's `latex/` directory, so the first compile may download packages.

## Reasoning Guidance

<!-- 迁移自旧模块提示词；具体推理要点见下方逐字来源。 -->

## Evidence Requirements

Every reference entry must be constructed from actual captured metadata (authors, title, venue, year, pages); missing fields are omitted, never invented. Compile fixes stay syntactic — the change set must not alter a claim, number, citation key or placeholder. The end state must be a document that compiles.

## Expected Output

Produce:

- a corrected, compiling LaTeX document or a bounded set of patches
- a venue-style reference list built from real metadata
- the compile errors grouped by category, with anything unresolved listed
- confirmation that no scientific content changed during formatting

## Workspace Conventions

If this method reads or writes structured workspace files (evidence/claims/decisions, plans, papers, outputs, LaTeX, literature search/download), follow the exact schemas in this plugin's `reference/` directory rather than improvising a format — see [research-assets.md](../../reference/research-assets.md), [plans.md](../../reference/plans.md), [papers.md](../../reference/papers.md), [outputs.md](../../reference/outputs.md), [latex.md](../../reference/latex.md), [literature-search.md](../../reference/literature-search.md), and [paper-fulltext-download.md](../../reference/paper-fulltext-download.md), whichever applies. The `research` skill's [SKILL.md](../research/SKILL.md) is the usual entry point that pulls the right context together first; if this skill was invoked on its own, check whether a `project.md` or `research-state.md` already exists in the workspace before assuming there is none.

## Reference Prompts

The original, more verbose source prompts this method was distilled from are kept in [reference.md](reference.md) for extra detail when the summary above isn't enough (exact length/format constraints, worked examples, etc).
