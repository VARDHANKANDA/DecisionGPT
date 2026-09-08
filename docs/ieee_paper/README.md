# IEEE conference-format build of the DecisionGPT paper

This folder is a **publication-format conversion** of the finalized, audited
manuscript `docs/PAPER_DRAFT.md` into IEEE two-column conference format
(`IEEEtran`). It is a formatting artefact only.

**No experiment was run, re-run, re-seeded, tuned, or modified during this
conversion.** Every numerical value, confidence interval, Wilcoxon result,
effect size, wins/ties/losses count, predictive metric and causal-recovery
metric is carried over verbatim from `docs/PAPER_DRAFT.md`, which reads them from
the frozen experiment manifest.

## Contents

| File | Purpose |
|---|---|
| `main.tex` | The manuscript. `\documentclass[conference]{IEEEtran}`, two-column. Pure ASCII. |
| `references.bib` | 39 references, verbatim from `docs/PAPER_DRAFT.md` Sec. 20 and verified in `docs/PAPER_REFERENCES.md`. `\bibliographystyle{IEEEtran}`. |
| `figures/figure1_architecture.pdf` | Pipeline / evaluation decomposition (schematic; no data). |
| `figures/figure2_primary_comparison.pdf` | Architecture comparison + paired D-B distribution (experiment `0e1bd8dc`). |
| `figures/figure3_ablation_mechanism.pdf` | Component ablation + risk-penalty mechanism (`db58455b`, `ba56e42b`). |
| `figures/figure4_risk_calibration.pdf` | Pre-registered recalibration variants + S04/S07 robustness (`b8516eef`, `0e1bd8dc`). |
| `README.md` | This file. |

`main.pdf` is **not** included: no LaTeX toolchain (`pdflatex` / `latexmk` /
`IEEEtran.cls`) is available in the environment used to prepare this folder, so
the PDF could not be generated locally. The source compiles with a standard IEEE
LaTeX setup (see below).

## Figure sources

The four PDF figures were produced by `docs/figures/make_figures.py`, which reads
**only** `docs/figures/figure_data.json` --- values extracted read-only from the
frozen DecisionGPT experiment runs (the source experiment IDs are recorded in
that JSON file). The script runs no experiment. The only stochastic element is
the paired bootstrap in Figure 2, seeded `numpy.default_rng(42)`; it re-analyses
the frozen paired differences and is not a new experiment.

To regenerate the PDFs (optional; requires `matplotlib` + `numpy`):

```
python - <<'PY'
import importlib.util, os, matplotlib
matplotlib.use("pdf")
import matplotlib.pyplot as plt
spec = importlib.util.spec_from_file_location("mf", "docs/figures/make_figures.py")
mf = importlib.util.module_from_spec(spec); spec.loader.exec_module(mf)
OUT = "docs/ieee_paper/figures"
def _save_pdf(fig, name):
    fig.savefig(os.path.join(OUT, name.replace(".svg", ".pdf")), format="pdf", bbox_inches="tight")
    plt.close(fig)
mf._save = _save_pdf
mf.figure1(); mf.figure2(); mf.figure3(); mf.figure4()
PY
```

## Compiling

Requires a standard TeX distribution (TeX Live, MiKTeX, or Overleaf) providing
`IEEEtran.cls` and `IEEEtran.bst` (both are part of every mainstream
distribution and the Overleaf "IEEE Conference" template), plus the packages
`fontenc`, `graphicx`, `amsmath`, `amssymb`, `array`, `booktabs`, `url`,
`hyperref`.

```
cd docs/ieee_paper
latexmk -pdf main.tex
```

or, without `latexmk`:

```
cd docs/ieee_paper
pdflatex main
bibtex   main
pdflatex main
pdflatex main
```

On Overleaf: create a project, upload `main.tex`, `references.bib`, and the
`figures/` folder, set the compiler to pdfLaTeX, and compile.

## Source of truth

- Scientific content: `docs/PAPER_DRAFT.md` (finalized, audited).
- Reference verification: `docs/PAPER_REFERENCES.md`.
- Numerical-consistency and forbidden-claim audits: `docs/PAPER_FINAL_READINESS.md`.
- Frozen research state: `experiments/experiment_manifest.json`
  (SHA-256 `94aa419c703b1babb465975463b26e55255755a7687ecbecadb6db4c4c15cbff`),
  `experiments/paper_results_snapshot.json`.

## Frozen research state (unchanged by this conversion)

- 16 frozen experiments; manifest SHA-256 unchanged.
- Production decision configuration **R0/D0** (`risk_model = None`,
  `risk_penalty_lambda = 1`).
- R3 remains **PROMISING --- NOT PROMOTED**.
- Real SME decision outcomes = **0**; `PredictionEvaluation` = **0**.
- Real-world decision-outcome validation table = **NOT READY**.
- Real-LLM evaluation = **BLOCKED** (`llm_enabled = false`).
- `CAUSALLY_VALIDATED = 0`.
- 6 active / 3 archived models --- unchanged.

## Author block (resolved)

`main.tex` lists the four student authors in the supplied order --- K. S. Sri
Vardhan, R Rohit, K. Rahul, Felix --- all affiliated with **SCOPE, VIT-AP
University, Vijayawada, Andhra Pradesh, India**.

- **Corresponding author:** K. S. Sri Vardhan
  (`vardhan.23bce8389@vitapstudent.ac.in`) --- noted in a `\thanks{}` footnote.
- **Prof. Yelepi Usha Rani** (Professor, SCOPE, VIT-AP University, Vijayawada,
  Andhra Pradesh, India; `usharani.y@vitap.ac.in`): **supervisor / guide
  information only.** She is **not** a co-author and is **not** in the author
  list; her exact name, affiliation and email appear only in a supervisor
  `\thanks{}` footnote.
- Student registration numbers: **not** included, per instruction.
- ORCID / funding / additional acknowledgements: **none**.
- Conference: none selected; the generic `\documentclass[conference]{IEEEtran}`
  is retained.
