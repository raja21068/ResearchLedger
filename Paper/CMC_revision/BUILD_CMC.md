# CMC format build and submission checks

This is an adapted CMC Research Article submission draft derived from the manuscript source, not the unrelated example text in the uploaded CMC template.

The provided `Definitions/tsp.cls` was modified in its submit-mode `\@maketitle` branch to suppress an unassigned DOI. A local `\sixdigits` helper override in `main.tex` closes a conditional left unbalanced in the supplied version of the class. The manuscript is in `main.tex` with CMC numbered citations, the BibTeX database is `ref.bib`, and figures are in `figs/`.

Compile the CMC paper in this folder:

```sh
pdflatex -interaction=nonstopmode main.tex
bibtex main         # or bibtex8 main
pdflatex -interaction=nonstopmode main.tex
pdflatex -interaction=nonstopmode main.tex
```

The BibTeX file contains preprint entries that trigger some `vancouver.bst` bibliographic warnings under bibtex8; the compiled PDF nevertheless has resolved in-text citations and the bibliography. The `supplement.tex` is an IEEE-formatted standalone supplement (uses biber and the same `ref.bib`), provided with its compiled PDF.

## Required confirmations before journal submission

- All six authors must consent to the new author order and confirm genuine qualifying contributions; update the mandatory Author Contributions statement based on their approved roles.
- Waqar Ali is designated corresponding author using the prior manuscript email `waqar.uestc@yahoo.com`; verify his preferred email and obtain his approval before submission.
- Obtain the authors' actual funding, conflict-of-interest, ethics, use-of-AI and other disclosure statements. No responses have been invented.
- Confirm the supplied code URL resolves to the appropriate version and that described validation artifacts are actually available.
- Submit author identifiers using `AUTHOR_INFORMATION.md` as needed. ORCID appears in the CMC PDF; Scopus/LinkedIn/WeChat remain in metadata only.
