# R1 — Publication Readiness Assessment

Scored **PASS / QUALIFIED / FAIL** against 11 categories. This is an honest
self-assessment for a **controlled component-level evaluation / negative-result /
reproducibility** submission — not a marketing sheet. Nothing here is scored a
perfect 10/10; every category lists its residual weakness.

Source of truth: `experiments/r1/{config,statistical_results,mechanism_results,
robustness_results,independent_recheck}.json`, `experiments/r1/MACHINE_AUDIT.md`
(26/26), `docs/R1_{DT_DIAGNOSTIC,INFORMATION_BOUNDARY,PREREGISTRATION,
PRELOCK_GATE,RESULTS,AUDIT,HOSTILE_REVIEW,FINAL_REPORT}.md`.

Primary result (verbatim, immutable): `D_vs_B` mean **+0.0852**, 95 %
cluster-bootstrap CI **[+0.0479, +0.1231]**, Wilcoxon p **5.4×10⁻¹⁰**, Holm
p ≈ 0, matched-pairs rank-biserial **−0.469**, D-better/tie/D-worse
**99 / 35 / 274** of 408, leave-one-family-out **+0.050 … +0.159**, robustness
**18/18** sign preserved, `primary_conclusion_changes = False`. Classification:
**NEGATIVE**.

---

## 1. Scientific integrity — **PASS**

- Pre-registration frozen at git `22ce18c` **before** the one-shot locked run;
  the run script hard-refuses on any manifest/doc SHA mismatch.
- Locked test executed **once** (4 080 instances, 0 errors); no re-run, no
  tuning, no post-hoc exclusion (`excluded.count == 0`).
- The result is **negative** and is reported as such — no salvage framing.
- The pre-lock gate explicitly recorded that a null/negative `D_vs_B` was an
  acceptable outcome, removing "we expected positive" bias.
- Frozen prior artifacts (V1, V2, R0/D0, R3, `PAPER_DRAFT.md`, `ieee_paper/`)
  verified byte-identical before and after (`experiment_manifest.json` sha256
  `94aa419c…`).

**Residual weakness.** The research-only correction (`r1_dt`) was authored by the
same team that runs the evaluation; although `ε̂` is data-estimated and the
scorer is an independent functional form, a fully independent re-implementation
of the correction would remove the last degree of freedom.

## 2. Statistical validity — **PASS**

- Unit of analysis = **scenario** (n = 408); 10 seeds aggregated to the scenario
  mean before every test (machine-verified).
- Primary interval = paired **scenario cluster bootstrap** (10 000 resamples,
  seed 12345, percentile); primary test = Wilcoxon signed-rank; primary effect
  size = matched-pairs rank-biserial (Kerby).
- Holm–Bonferroni over the pre-registered confirmatory family exactly
  `{B_vs_A, C_vs_B, D_vs_C, D_vs_B}`; raw and adjusted p both reported.
- Every headline number **independently recomputed** from raw `results.json`
  with no reuse of the summaries — **75/75 checks reproduce**
  (`experiments/r1/independent_recheck.json`).
- Effect is 1.7× the pre-registered MEI (0.05); CI clear of 0 by > 4×.

**Residual weakness.** The prospective power calculation (`estimated_power`
0.894) does not model the 35/408 exact ties, so achieved power is modestly
lower; the p-value (5.4×10⁻¹⁰) makes this immaterial to the conclusion but it is
a methods imperfection. Cluster count for the mechanism OLS = 12 families, so
factor-level coefficients are reported as family-clustered associations only.

## 3. Methodological clarity — **PASS**

- Four conditions A/B/C/D precisely defined; information boundary tabulated
  (`docs/R1_INFORMATION_BOUNDARY.md`).
- System A (log-linear history) vs System B (additive-linear exogenous scorer)
  vs the constant-elasticity correction are three distinct functional forms;
  their coupling is a noisy monotone parameter map, not shared code
  (AST-verified: `ground_truth` imports only stdlib + numpy/scipy).
- The diagnosis that motivates R1 is quantified: production forecaster SHAP for
  price + marketing = 2.2 %; projected units exactly flat over a 3× price sweep
  (`docs/R1_DT_DIAGNOSTIC.md`).

**Residual weakness.** The 27-family taxonomy and its parameter ranges are a
designed artefact; while pre-registered and structurally diverse, the mapping
from "family" to "real decision situation" is asserted by construction, not
empirically grounded.

## 4. Novelty — **QUALIFIED**

- The contribution is a *component-level* separation — value enters at B
  (B beats A, Holm p 1×10⁻⁸), the single agent is inert (C≈B, Holm p 0.61), and
  the full stack **removes** value (D worse than B and than C) — plus a
  mechanistic characterisation (action-change hit-rate, optimal-action rate
  collapse 62.5 % → 34.6 %).
- This is a negative result about an "add agents → better" assumption that the
  surrounding literature rarely tests at the component level.

**Residual weakness.** "Ablation of a decision pipeline on synthetic scenarios"
is not a methodological novelty in itself; the paper's interest rests on the
diagnosis + the minimal-correction design + the direction of the result, which a
reviewer may consider incremental. Fixable by framing, not by data.

## 5. Reproducibility — **PASS**

- Frozen: pre-registration, scenario manifest (per-scenario `content_hash`,
  `suite_checksum cd73f0d5…`), raw locked `results.json` (sha256 `9e302f1d…`),
  analysis script, robustness output, figure generator, machine audit,
  independent recheck, per-artifact checksums, git commit, exact command list.
- All analysis reproduces **from the frozen raw results** with no new locked
  run. Bootstrap / mechanism / power seeds fixed (12345 / 4242 / 777 /
  20260907).

**Residual weakness.** The repo ships a pinned `backend/requirements.txt`
(numpy 2.5.2, pandas 2.2.3, scikit-learn 1.5.2, scipy 1.18.1, xgboost 3.4,
shap 0.52), but no container/lockfile is bundled inside the R1 package itself and
the analysis has not been re-executed in a clean venv *as part of this
publication pass* (it was, in the earlier repro-validation pass). A bundled
lockfile + clean-room analysis rerun would close this; it needs no new
experiment.

## 6. IEEE formatting — **QUALIFIED**

- Manuscript in `docs/ieee_paper_r1/main.tex` uses `IEEEtran` `conference`
  class, two-column, `abstract` + `IEEEkeywords`, 24 numbered sections +
  Reproducibility Statement + Ethics, `\bibliographystyle{IEEEtran}`.
- **9 tables and 5 figures** with captions; references restricted to the
  previously verified set (`docs/ieee_paper/references.bib`) — no fabricated
  DOIs.
- Structural validation passed: all `\begin/\end` environments balanced; every
  `\ref` resolves to a `\label`; every `\cite` (29 keys) resolves in
  `references.bib`.
- Figure PDFs generated (`scripts/r1_figures_to_pdf.py`); `\includegraphics`
  uses no extension so `pdflatex` picks them up.

**Residual weakness.** **The PDF was not compiled** — no LaTeX toolchain
(`pdflatex`/`bibtex`/`latexmk`) is available in this environment; the manuscript
header and README say so explicitly. Overfull-box / page-limit / venue-template
passes therefore remain for the authors, as do the placeholder corresponding-author
contact details (no fabricated identifiers).

## 7. Figure quality — **QUALIFIED**

- 5 figures generated by one reproducible script (`scripts/r1_figures.py`)
  reading `experiments/r1/figure_data.json`, itself derived read-only from the
  frozen artifacts: architecture + information boundary (Fig 1), sorted paired
  D−B (Fig 2), A/B/C/D + baseline ladder (Fig 3), per-family D−B (Fig 4),
  action-change → improved/worsened (Fig 5). SVG **and** PDF are both shipped.

**Residual weakness.** Figures are hand-authored SVG (no `matplotlib` in the
environment); correct and legible but not typeset to IEEE column width / font.
Fig 2 (408 bars) needs a scale check at two-column width. Not verified visually
in a compiled PDF (no toolchain).

## 8. Table consistency — **PASS**

- All 9 manuscript tables trace cell-by-cell to
  `experiments/r1/statistical_results.json` / `mechanism_results.json` /
  `robustness_results.json` / raw `results.json`; the automated
  numerical-consistency pass is **66/66** (59 headline + 7 per-family
  optimal-action), on top of the 75/75 independent recheck.
- Ladder (mean regret): Oracle 0.000, classical-opt 0.089, C 0.162, greedy
  0.197, B 0.216, A 0.259, D 0.301, naive 0.367 — consistent across abstract,
  body, tables, and figure.

**Residual weakness.** Tables IV and the confirmatory table report two CI
flavours (cluster bootstrap + secondary Student-t); the caption states the
bootstrap is primary, but a reviewer skim could still misread the narrower
t-interval.

## 9. Citation quality — **QUALIFIED**

- Reference list reused verbatim from the already-verified V1 bibliography;
  anchor negatives (multi-agent failure-mode literature), digital-model
  terminology (Kritzinger 2018), effect-size (Kerby 2014 / Fritz 2012),
  pre-registration (Nosek 2018), and forecast-error-metric guidance
  (Hyndman–Koehler 2006) are cited.

**Residual weakness.** R1 introduces no new literature search; a reviewer may ask
for more recent (2024–2025) multi-agent-evaluation references. Adding them is
desk work, not a new experiment, but it is genuinely not done yet.

## 10. Claim discipline — **PASS**

- Forbidden-term scan (`scripts/scan_r1_claims.py` →
  `experiments/r1/forbidden_term_scan.json`) across all R1 docs + the manuscript:
  **0 prohibited**.
- Abstract, discussion, and a dedicated threats section state that R1 shows
  **nothing** about real-world / SME / Indian-SME / ROI / causal / deployment /
  human-decision / LLM effects, or about the shipped Digital Twin as deployed;
  and that a negative R1 result does not show multi-agent systems are useless in
  general.
- The term "accuracy" is never attached to a regret metric or error metric
  (the endpoint is normalised regret throughout).

**Residual weakness.** The scan is heuristic (regex + defuser list); it is a
safety net, not a proof. A human read of the final camera-ready is still
required.

## 11. Reviewer resistance — **QUALIFIED**

- `docs/R1_HOSTILE_REVIEW.md` works through 16 reviewer attack lines
  (novelty, synthetic legitimacy, ground-truth independence, architecture
  faithfulness, correction bias, information fairness, baseline advantage,
  clustering, power, multiplicity, seeds, external validity, mechanism,
  negative-result value, reproducibility, leakage). **No Critical issue is
  substantiated**; every Major issue is met by disclosure already in the
  manuscript and none needs a new experiment.

- The manuscript now **foregrounds** both of the previously soft spots:
  1. **Scope of the claim** — the abstract, Introduction, and
     Threats-to-Validity item 3 state that R1 evaluates the architecture *given
     a functioning decision-simulation layer* (the research-only correction),
     not the shipped layer.
  2. **The two D-favourable families** — the per-family results section, Threats
     item 9, and the Discussion all identify `nonlinear_response` and
     `demand_saturation` as censored-demand cases where D helps only because B is
     worst there, and state that the aggregate stays D-worse without them (LOFO
     with them removed: +0.114 / +0.159).
- A dedicated "Response to *this is an artifact of synthetic scenario design*"
  paragraph answers the single strongest reviewer line with the independent
  objective, 12 structural families, LOFO, pre-registration + one-shot lock, and
  18/18 robustness — without claiming equivalence to real-world validation.

**Residual weakness.** Reviewer resistance cannot be fully verified without a
compiled PDF and an actual review; the novelty framing (QUALIFIED, category 4)
is the most likely remaining point of friction for a reviewer who wants a
positive or deployment result. Nothing here is fixable by more data.

---

## Scorecard

| # | Category | Verdict |
|---|---|---|
| 1 | Scientific integrity | **PASS** |
| 2 | Statistical validity | **PASS** |
| 3 | Methodological clarity | **PASS** |
| 4 | Novelty | **QUALIFIED** |
| 5 | Reproducibility | **PASS** |
| 6 | IEEE formatting | **QUALIFIED** |
| 7 | Figure quality | **QUALIFIED** |
| 8 | Table consistency | **PASS** |
| 9 | Citation quality | **QUALIFIED** |
| 10 | Claim discipline | **PASS** |
| 11 | Reviewer resistance | **QUALIFIED** |

**6 PASS / 5 QUALIFIED / 0 FAIL.**

## Overall

**Ready to submit as a controlled component-level evaluation / negative-result /
reproducibility paper, after minor revision.** The QUALIFIED items are all
publication-desk tasks that do **not** touch the experiment and require no new
data:

- **(6, 7) Compile the PDF.** No LaTeX toolchain was available in this
  environment, so `main.tex` was validated structurally / numerically / for
  citations but not compiled. The authors run `latexmk -pdf main.tex` on any TeX
  install, then do the overfull-box / page-limit / venue-template pass and a
  visual figure check (esp. Fig. 2 at column width). Figure PDFs are already
  generated.
- **(5) Bundle a lockfile** and re-run the analysis once in a clean venv (the
  repo's `backend/requirements.txt` is already pinned).
- **(9) Add a few 2024–2025 multi-agent-evaluation references.**
- **(4, 11) Framing.** Position firmly as a component-level / negative-result
  contribution; the disclosures a reviewer will probe are already foregrounded.

The scientific core — integrity, statistics, methodological clarity,
reproducibility, table consistency, claim discipline — is **PASS**. Every
headline number is independently reproduced (75/75 from raw `results.json`) and
the manuscript's numbers cross-check 66/66 against the frozen artifacts.

**Not ready for:** any venue expecting a positive/deployment/real-SME result;
any claim that DecisionGPT is validated, superior, or effective for SMEs; any
causal or real-world interpretation. Those are out of scope by construction and
must stay out of the paper.
