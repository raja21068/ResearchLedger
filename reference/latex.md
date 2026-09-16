# LaTeX pipeline for papers

Layout per paper:

```text
papers/<id>/latex/
├── main.tex                            # compiled version — real \cite{}
├── main_intermediate.tex                 # human-proofreading version — literal [cite_key] left in place
├── main_bak_<YYYYMMDDTHHMMSS>.tex        # backup made before each recompose, never silently lost
├── main.pdf / main.log
└── .tectonic-cache/
```

## Compose: `paper.md` → `main.tex`

Read `paper.md` (title = first `# H1`; `## Abstract` and `## References`/`## Bibliography` pulled
out as front/back matter; everything else becomes body sections in reading order) plus
`metadata.md`'s `authors`/`affiliation` (the manuscript itself has no slot for these). Apply these
steps **in order** — later steps assume earlier ones already ran:

1. Strip markdown residue: remove HTML comments, unwrap bold-only lines, turn `####`/`###` into
   `\subsubsection*{}`/`\subsection*{}` (already numbered by hand, so unnumbered LaTeX commands),
   delete stray `#`/`##` lines, convert inline `**bold**`/`*italic*` to `\textbf{}`/`\textit{}`
   (skip anything already inside a math region).
2. Convert GitHub-style pipe tables to `table`/`table*` + `tabular` with `booktabs`
   (`\toprule`/`\midrule`/`\bottomrule`). A table wider than ~62 visual characters or with 6+ columns
   becomes `table*` with `p{...}` columns. Protect the result behind a placeholder so later steps
   don't try to math-escape it.
3. Replace any line referencing `\ref{fig:<label>}` with a `<<FIG:label>>` placeholder.
4. Expand `<<EQ:key>>` placeholders into `\begin{equation}...\end{equation}` blocks. If the key
   matches a well-known ML/physics equation shape (attention, softmax, cross-entropy, etc.) render
   the standard form; otherwise render the placeholder's own text as raw LaTeX.
5. Sanitize the remaining math region: protect `\includegraphics`/`\label`/`\ref`/`\cite`/`\input`/
   `\bibliography` argument text from escaping, protect existing `$...$`/`$$...$$`/math environments,
   auto-wrap bare patterns like `x_1`/`x^2` in `$...$`, then escape any remaining `& % # _ ^`.
6. Replace `<<FIG:label>>` placeholders with a real `figure` environment
   (`\includegraphics[width=0.5\textwidth]{...}`).
7. Restore the protected table blocks, then convert citations: `[key1, key2]` / `[key]` / a plain
   `[12]` → `\cite{...}` (skipping math regions) — this is the step that differs between the two
   output files: `main_intermediate.tex` skips it (keeps literal `[key]` for a human to proofread),
   `main.tex` runs it.

Title/authors/affiliation go through a separate, stricter sanitizer that also transliterates stray
Unicode (`≥ κ − → ⚠️ …`) so nothing silently disappears, and escapes `& % # _ ~ { } ^`.

`main.tex` skeleton:

```latex
\documentclass{IEEEtran}          % or \documentclass[journal]{IEEEtran}
\usepackage{graphicx}
\usepackage{amsmath}
\usepackage{amssymb}
\usepackage[numbers]{natbib}
\usepackage[T1]{fontenc}
\usepackage{lmodern}
\usepackage{booktabs}
\usepackage{url}
\usepackage{float}

\begin{document}

\title{<title>}
\author{\IEEEauthorblockN{<authors>} \\
\IEEEauthorblockA{<affiliation>}}
\maketitle

\begin{abstract}
<abstract>
\end{abstract}

\section{<Section 1 title, leading number stripped>}
<body>
...

\begin{thebibliography}{99}
\bibitem{key} <formatted citation text>
\end{thebibliography}

\end{document}
```

Before overwriting an existing `main.tex`, rename it to `main_bak_<YYYYMMDDTHHMMSS>.tex` first.

## Compile

Prefer, in this order, whatever is actually installed:

1. **`tectonic <main.tex> --keep-logs`** — run from inside the `latex/` directory, with
   `TECTONIC_CACHE_DIR` pointed at a writable cache directory (e.g.
   `<workspace>/harness/.tectonic-cache`, not a system cache dir that may be read-only in a sandbox).
   Give it up to 300s the first time (it downloads packages on first use). Success = exit code 0
   **and** `main.pdf` now exists — tectonic is lenient and can exit 0 on a recoverable-but-broken
   document, so always check for the PDF too, not just the exit code.
2. **`latexmk -pdf -interaction=nonstopmode main.tex`** if tectonic isn't installed.
3. **Manual cycle** as a last resort:
   ```bash
   pdflatex -interaction=nonstopmode main.tex
   bibtex main
   pdflatex -interaction=nonstopmode main.tex
   pdflatex -interaction=nonstopmode main.tex
   ```

Probe for a binary before assuming one exists (`which tectonic`, `which latexmk`, `which pdflatex`);
degrade to the next option rather than failing outright, and tell the user which toolchain was used.
If a missing-LaTeX-package error surfaces, report the exact error and tell the user to install it
(`tlmgr install <package>` / their TeX distribution's package manager) rather than guessing a fix.

## Reading compile errors

Scan stdout + stderr + `main.log` together, line by line, ignoring `underfull`/`overfull` box
warnings. Look for, in priority order:

1. `error: <file>:<line>: <msg>` (tectonic's own format — preferred, has a line number).
2. `error: <msg>` with no line number (skip tectonic's own progress chatter like
   `halted on` / `Running` / `downloading`).
3. Classic TeX `! <msg>` followed within ~6 lines by `l.<N>`.
4. `LaTeX (Font )?Warning: <msg>` — only worth surfacing if it mentions `undefined`,
   `Missing character`, or `Invalid UTF-8`.

Sort errors with a known line number first, ascending, then present the rest.

## Deterministic repair (try before asking for a hand-edit)

Plain regex fixes, no model call needed:

1. Globally escape any un-escaped `%` outside math regions.
2. For each error with a known line number, process lines in **descending** order (so an earlier fix
   doesn't shift a later line number) and try, by error-message text:
   - `double subscript` → fix a stray `x_(...)` / parenthesized sub/superscript.
   - `missing control sequence` / `inserted` → fix a bare `$_x` pattern.
   - `invalid in math mode` → pull a `\cite{}`/`\bfseries` that got stuck inside `$...$` back out.

Anything that doesn't match one of these three patterns, or has no usable line number, goes into a
`remaining` list for a human/agent to fix by hand — show the surrounding ±6 lines of context when
presenting it.

## Lint (advisory only — never blocks a compile)

Scan for `\command`/`\begin{env}` tokens not on a broad known-safe allow-list of IEEEtran/structure/
math commands, and just list the unknown ones. Do not fail a compile over this — a narrower allow-
list previously false-flagged nearly every real paper.
