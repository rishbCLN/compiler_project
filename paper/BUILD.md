# Building the manuscript

The manuscript uses the official IEEE Access LaTeX template of 13 May 2026
(`ACCESS_latex_template_20260513-1-1.zip`, from
https://ieeeaccess.ieee.org/authors/submission-guidelines/). `ieeeaccess.cls`,
`spotcolor.sty`, `IEEEtran.cls` and the logos in this directory are the
template's files, unchanged.

1. Copy the template's font files (`t1*.pfb`, `t1*.tfm`, `t1*.fd`, `t1*.map`)
   into this directory. They are not in the repository (see `.gitignore`).
2. Build the five TikZ diagrams once (the class redefines `\year`, which breaks
   TikZ inside the main document):

       cd figures
       for f in fig_architecture fig_flow fig_modules fig_layout fig_ssa_example; do pdflatex $f.tex; done

3. Build the article with pdfLaTeX, twice: `pdflatex ir_compaction_access.tex`.
   On Overleaf, upload this directory together with the font files and set
   the compiler to pdfLaTeX.

The class needs pdfLaTeX: `spotcolor.sty` uses `\pdfobj`, so XeTeX-based
engines (including tectonic) stop at the spot-colour definition.

## Generated files

Do not edit these by hand; rerun `python3 paper_eval/run_all.py`:

* `tables/*.tex`: table rows and `numbers.tex`, the macros (`\n...`) for every
  number quoted in the text;
* `figures/fig_{reduction,ablation,benchmark_sizes,compare,density,scaling,throughput}.pdf`;
* `figures/fig_layout.tex`.

`python3 paper_eval/check_paper.py` checks macros, table files, figures,
references and citations without a LaTeX installation.

## Still to be supplied by the authors

* Confirm that the AI-use statement in the Acknowledgements is accurate and
  permitted under the course and institutional policy.
