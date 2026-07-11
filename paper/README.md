# ShallowSWE white paper

This directory contains the arXiv-ready LaTeX source for the ShallowSWE v0.4.2
freeze candidate.

## Build

The verified local build uses Tectonic:

```sh
tectonic -X compile main.tex
```

With a conventional TeX Live installation, the equivalent command is:

```sh
latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex
```

The source uses only conventional TeX Live packages accepted by arXiv. Upload
`main.tex`, `references.bib`, and the `figures/` directory together. Do not upload
generated auxiliary files.

## Regenerate from the Markdown freeze candidate

The converter requires Ruby and the `kramdown` gem:

```sh
ruby build_latex.rb ../docs/white-paper-v0.4.2.md main.tex
```

Before publication, replace the dated implementation-audit language and its
placeholder commit requirement with the exact repository commit SHA.
