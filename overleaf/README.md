# Overleaf project — DecisionGPT R1 paper (two-column preprint, publication-polished)

Self-contained, upload-ready Overleaf project for the frozen R1 manuscript:

> **Does a Multi-Agent Layer Help? A Controlled Component-Level Evaluation of an
> Integrated Decision-Support Architecture for Data-Constrained SMEs**

`main.tex` is a **formatting restyle + typographic clean-up** of the canonical
IEEE version (`docs/ieee_paper_r1/main.tex`, kept unchanged as the manuscript of
record). Every word of the manuscript, every number, every table cell, every
figure, the equation, the appendices and the citations are **identical** to the
verified R1 manuscript. The **only added content** is a *System Architecture*
section and its figure (`architecture.png`), whose text and caption are verified
system description with **no results**.

## Files

| File | Purpose |
|---|---|
| `main.tex` | `article`, `10pt`, `twocolumn`, `a4paper`. 25 numbered sections + 2 lettered appendices, **10 tables, 6 figures, 1 equation**. |
| `references.bib` | 39 verified entries (29 cited); real DOIs only, none invented. |
| `figures/r1_figure{1..5}.pdf` | the R1 result figures. |
| `architecture.png` | **you add this** — see below. |

## Add `architecture.png`

Upload `architecture.png` to the **Overleaf project root** (or to `figures/`).
Until you do, `main.tex` shows a framed placeholder box in its place and still
compiles — no error. `\graphicspath` and a nested `\IfFileExists` handle either
location. The figure is `\begin{figure*}` (spans both columns) and is referenced
in the text as `Fig.~\ref{fig:architecture}`.

## What was fixed / hardened

### Latest pass — content disappearing after the figures (root cause + fix)

**Cause:** three both-column floats (`figure*` for `architecture.png` + two
`table*`) in a two-column `article` overflow LaTeX's 18-entry unprocessed-float
buffer. When that happens `pdflatex` **stops** with *"Too many unprocessed
floats"*, and every page after that point is missing from the PDF. Adding the
architecture `figure*` tipped the count over.

**Fix (no manuscript content, number, table cell, figure, caption, equation,
citation or conclusion changed):**

| Change | Effect |
|---|---|
| `stfloats` → `dblfloatfix` | repairs lost / mis-ordered `figure*` & `table*` in a two-column `article`; makes `\FloatBarrier` actually flush wide floats |
| `\usepackage[section]{placeins}` | inserts `\FloatBarrier` at **every `\section`** — single-column floats can never accumulate more than one section's worth (~2–3), so the buffer cannot overflow |
| generous float parameters | `\topfraction`/`\dbltopfraction` 0.92, `\textfraction` 0.06, `\floatpagefraction` 0.72, bigger `topnumber`/`totalnumber`/`dbltopnumber` — LaTeX places floats instead of deferring them |
| all float specifiers `[!t]`/`[!tb]` → **`[tbp]`** | drops the `!` that forbids a float page and forces deferral; `p` lets LaTeX make a float page as a last resort instead of losing content |
| explicit `\FloatBarrier` before `\appendix` and before `\bibliography` | guarantees every float is emitted **before** the appendices and reference list, so those can never be pushed off the end |
| `architecture.png`: `\includegraphics[width=0.95\textwidth,height=0.42\textheight,keepaspectratio]` | scales to fit width **or** height, whichever binds — never cropped, never distorted, and the height cap prevents it occupying a wasteful full page. `figure*[tbp]`, placed in §6 "System Architecture", referenced as `Fig.~\ref{fig:architecture}`; a framed placeholder shows (and the paper still compiles) until you upload the file to the project root or `figures/` |
| title block: removed a `\\` inside a `{\small …}` group in the `\twocolumn[…]` argument | eliminates a fragile line break in the one-column title material; corresponding-author and supervisor lines are now two separate `\par` blocks (same text, same emails) |

Result: **28 section headings** present in the exact expected order (Abstract →
25 numbered sections → Appendix A/B), all **6 figures**, all **10 tables**, the
equation, the appendices and the full reference list — nothing can be dropped by
a float now.

### Earlier passes

| Problem class | Fix |
|---|---|
| Wide display equation overflowing the column | broken over two lines with `aligned` (content identical) |
| Description-heavy tables crossing the column (`tab:families`, `tab:mech`) | converted to `tabularx` with a wrapping `X` column |
| 6-column optimal-action table too wide for one column (`tab:optaction`) | promoted to full-width `table*` |
| 8-column confirmatory-contrast table | already full-width `table*`; kept |
| Dense numeric tables near column width | every table body set `\small`; `\tabcolsep` 6pt→4pt (matches the reference's table size) |
| 64-char SHA-256 strings unbreakable in `\ttfamily` | `seqsplit` available; hashes render breakable |
| Long `\url` / DOI strings crossing the column | `xurl` (breaks anywhere) + `breaklinks=true` |
| Words protruding past the margin | `microtype` (protrusion + expansion) + `\emergencystretch=3em` |
| Orphan lines / widowed headings | `\clubpenalty=\widowpenalty=\displaywidowpenalty=10000`; `titlesec` keeps headings with following text |
| Excessive inter-column whitespace from vertical stretch | `\raggedbottom` |
| Misplaced floats / float pile-up | see the *latest pass* section above (`dblfloatfix` + `[section]placeins` + `[tbp]` + `\FloatBarrier`) |
| `??` citations / cross-refs | `natbib` + `hyperref` (numeric `[n]` link to the bib entry); every `\ref` target has a `\label`; 0 duplicate labels; 29/29 `\cite` keys resolve; run `bibtex` + 2× `pdflatex` |
| Clickable references | `hyperref` (`hidelinks` = clickable, undecorated) makes every `[n]`, `\ref` to a figure / table / equation / section / appendix a live link; DOIs are `\href` to `https://doi.org/…`; `cleveref` loaded for `\cref` |
| Package-order conflicts | `natbib` → … → `hyperref` → `xurl` → `cleveref` (cleveref last, after hyperref; natbib before hyperref) |

**Not reproduced from the reference PDF:** the vertical `arXiv:…` stamp down the
left margin — that is added by arXiv on submission, not by the author's LaTeX.

## Section order (25 numbered + Abstract + 2 appendices — complete manuscript)

Abstract · Introduction · Related Work · Scope and Non-Goals · Research Questions
· **System Architecture** · System Under Test · The Decision-Simulation
Bottleneck: Diagnosis · Research-Only Correction (R1) · Information Boundary ·
Synthetic Environment and Scenario Families · Ground-Truth Objective and Regret ·
Baselines · Experimental Design and Pre-Registration · Statistical Analysis Plan
· Power · Results: Component Ladder · Results: Confirmatory Contrasts · Results:
Per-Family and Leave-One-Family-Out · Results: Robustness · Mechanism Analysis ·
Reproducibility and Independent Recomputation · Contributions · Threats to
Validity and Limitations · Discussion · Conclusion · **Appendix A**
Reproducibility Statement · **Appendix B** Ethics and Data · References.

Tables I–X: scenario families; component ladder; confirmatory contrasts;
secondary contrasts; per-family D$-$B; leave-one-family-out; robustness;
mechanism counts; optimal-action rates; (+ the confirmatory-contrast wide table).
Figures 1–6: system architecture; R1 evaluation schematic; sorted paired D$-$B;
regret ladder; per-family D$-$B; mechanism overrides.

## Compiling

### Overleaf (recommended)

1. **New Project → Upload Project**; upload this whole `overleaf/` folder.
2. Add `architecture.png` to the project root.
3. Menu → **Compiler: pdfLaTeX**, **Main document: `main.tex`**, **TeX Live**
   latest.
4. **Recompile.** Overleaf runs `pdflatex → bibtex → pdflatex → pdflatex`, so the
   `[n]` citations, the reference list and every cross-reference resolve on the
   first full build. If a citation still shows `[?]`, hit Recompile once more.

Every package used is in Overleaf's TeX Live: `lmodern`, `microtype`, `geometry`,
`amsmath/amssymb/amsfonts`, `graphicx`, `textcomp`, `array`, `booktabs`,
`tabularx`, `adjustbox`, `seqsplit`, `stfloats`, `etoolbox`, `caption`,
`natbib` (provides `unsrtnat`), `titlesec`, `url`, `hyperref`, `xurl`, `cleveref`.

### Locally

```bash
cd overleaf
latexmk -pdf main.tex        # runs pdflatex/bibtex the right number of times
# or:
pdflatex main ; bibtex main ; pdflatex main ; pdflatex main
```

> **`LOCAL_LATEX_COMPILE = NOT_AVAILABLE`** in the environment that produced this
> project — there is **no** `pdflatex` / `xelatex` / `lualatex` / `tectonic` /
> `latexmk` installed, so the PDF was **not compiled or visually inspected here**.
> I cannot claim a clean `.log`, a zero-`Overfull \hbox` build, or a verified
> page count, and I did not run the page-by-page inspection myself — that step
> is yours to do once, on Overleaf (instructions below). What was verified
> **statically** instead:
> * all environments balanced *and correctly nested*; 676/676 braces; even
>   math-mode `$` count; one `\begin{document}` / one `\end{document}` with
>   nothing after it; no `\input`/`\include`; no `\maketitle`; no `[!t…]`
>   float specifiers left;
> * **28 section headings in the exact expected order** (Abstract → 25 numbered
>   sections → Appendix A Reproducibility Statement → Appendix B Ethics and
>   Data), then the bibliography; **10 tables, 6 figures, 1 equation**;
> * `dblfloatfix` + `[section]placeins` + `[tbp]` + explicit `\FloatBarrier`
>   before the appendix and the bibliography → the "too many unprocessed
>   floats" error that was dropping later pages is structurally prevented;
> * every `\ref`/`\cref` target has a `\label`; **0 duplicate labels**; all 29
>   `\cite` keys resolve in `references.bib`; no duplicate BibTeX keys;
> * every frozen R1 number still present verbatim (D$-$B `+0.0852`,
>   CI `[+0.0479,+0.1231]`, Wilcoxon `5.4\times10^{-10}`, `-0.469`,
>   `99/35/274`, LOFO `+0.050…+0.159`, `18/18`, ladder
>   `0.259/0.216/0.162/0.301/0.367/0.197/0.089`, `2336 of 4080`, `763`/`1573`,
>   `62.5\%`→`34.6\%`, `94.1\%→4.4\%` / `73.5\%→1.2\%`, hashes `94aa419c…`,
>   `9e302f1d…`, `NEGATIVE`, `75 of 75`, `26/26`);
> * no prohibited real-world / SME / ROI / fabrication phrasing.

### Final page-by-page check — you must run this once on Overleaf

1. Upload the folder, add `architecture.png` to the **project root**, set
   Compiler = **pdfLaTeX**, Main = **main.tex**, TeX Live = latest, **Recompile**
   (twice if a `[?]` citation appears on the first pass).
2. Open the PDF and scroll **every page**, confirming:
   - every section from **Abstract** through **Appendix B** and the **full
     reference list** is present — *nothing stops after a figure*;
   - `architecture.png` (Fig. 1) is fully visible, not cropped at any edge, not
     on a page of its own;
   - no overlapping / merged text, nothing past the margin, no broken table or
     equation, no accidental blank page;
   - clicking `[1]`, `[2]`, … jumps to the reference; clicking `Table X`,
     `Fig. X`, `Eq. (1)`, `Section X`, `Appendix X` jumps to the target; DOI
     links in the reference list open `https://doi.org/…`.
3. Open the `.log` (menu → Logs and output files → Raw logs) and search for
   `Too many unprocessed floats` (must be **absent**) and for `Overfull \hbox`
   entries larger than ~20 pt. If one large overfull remains in a specific
   table, drop that one table from `\small` to `\footnotesize` — do **not**
   shrink the whole paper.

## Frozen result (verbatim in `main.tex`)

408 locked scenarios × 10 seeds = 4080 evaluations, 0 errors, 0 exclusions, run
once. `D_vs_B` mean **+0.0852**, 95% cluster-bootstrap CI **[+0.0479, +0.1231]**,
Wilcoxon p **5.4×10⁻¹⁰**, Holm p ≈ 0, matched-pairs rank-biserial **−0.469**,
D‑better/tie/D‑worse **99 / 35 / 274**. Classification: **NEGATIVE**. The paper
makes no real-world, SME, ROI, causal, deployment or LLM claim.

## Provenance

| Item | Value |
|---|---|
| Pre-registration frozen at git commit | `22ce18c965b61641f3dd28cc35e0cfac22f61dca` |
| Raw locked results `experiments/r1/results.json` | SHA-256 `9e302f1d1cf575940e62e9abdb66393c0e7d9e9d2f2ec940abe2bd161c853065` |
| Frozen experiment manifest (unchanged) | SHA-256 `94aa419c703b1babb465975463b26e55255755a7687ecbecadb6db4c4c15cbff` |
| IEEE version of record | `docs/ieee_paper_r1/main.tex` (unchanged this pass) |

Reproducing the paper's statistics requires only the frozen raw results;
re-running the locked experiment is neither necessary nor permitted.
