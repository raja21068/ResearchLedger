# Build

Requires a TeX distribution with `pdflatex`, `biber`, and `latexmk`.

```bash
latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex
latexmk -pdf -interaction=nonstopmode -halt-on-error supplement.tex
```

The supplied PDFs were compiled successfully in the working environment. `main.pdf` is 11 pages and `supplement.pdf` is 9 pages. The rendered outputs were visually inspected for clipping and overlap.
