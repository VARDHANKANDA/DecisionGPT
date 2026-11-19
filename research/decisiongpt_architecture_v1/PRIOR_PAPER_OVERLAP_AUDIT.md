# PRIOR_PAPER_OVERLAP_AUDIT (private; 2026-10-23)

Read-only audit. Nothing was submitted, uploaded, or sent anywhere; no similarity service was used (the scan below is a local script, `analysis/overlap_scan.py`). Evidence labels: **[F]** verified in a file, **[I]** inference, **[?]** needs the authors.

## 0. What was compared (the project contains FIVE related manuscripts, not one)

| # | Manuscript | Location | Date of files | Title | Contents |
|---|---|---|---|---|---|
| P0 | Original 60-pair paper | `docs/ieee_paper/main.tex` | 2026-09-03 | *Does a Multi-Agent Layer Help? A Controlled Component-Level Evaluation of an Integrated Decision-Support Architecture for Data-Constrained SMEs* | 12 scenarios × 5 seeds architecture comparison + ablation |
| P1 | R1 paper | `docs/ieee_paper_r1/main.tex` | 2026-09-07/08 | **identical title to P0 and to the current paper** | the 408-scenario locked R1 study in full (7 tables, 5 figures per the project record) |
| P2 | Component-composition paper | `docs/ieee_paper_r2/main.tex` (+ compiled `main.pdf`) | 2026-09-24 | *Component Composition in an Integrated Decision-Support Architecture: A Controlled Evaluation With a Pre-Registered Confirmatory Replication* | R1 as confirmatory replication of the 12×5 discovery study; mentions the 80-scenario study in one sentence |
| P3 | Broad system paper ("previous paper") | `overleaf/main.tex` = `C:\Users\VARDHAN\Downloads\DecisionGPT (1).pdf` (compiled 2026-09-17, 10 pages) | 2026-09-17/23 | *DecisionGPT: A Multi-Agent Decision-Support Architecture Combining Predictive Analytics, Digital Twin Simulation, and Causal Context …* | whole system: predictive models on 5 datasets, causal graph, 12×5 ladder + 6-way ablation + risk diagnostic, R1 as §VII-G |
| C | **Current paper** | `overleaf/architecture_paper_v1/` | 2026-10-22/23 | same title as P0/P1 | component ladder re-analysis of R1 + 80-scenario study + sensitivity + new cost run + RQ1 summary |

[F] The user-supplied PDF is P3. The R1 study is also reported in P1 and P2, and as a subsection of P3.
[F] The repository's remote tracking branch (`origin/main`, remote `https://github.com/VARDHANKANDA/DecisionGPT.git`) contains P0 (`docs/ieee_paper`, 7 files), P1 (`docs/ieee_paper_r1`, 13 files), `experiments/r1` (17 files), `experiments/upgraded_controlled_v1` (16 files), `docs/R1_FINAL_REPORT.md` and `docs/UPGRADED_EVALUATION_REPORT.md`; an earlier `overleaf/main.tex` (R1 manuscript) exists in its history and was deleted at the tip (commit `e811e02`, 2026-09-08). P2, the current `overleaf/main.tex` (P3), `docs/ML_BENCHMARK_REPORT.md`, `experiments/ml_benchmark_v1` and everything in the current paper/research folders are **not** in `origin/main`. [?] Whether that GitHub repository is public was not checked (no external access was made).

## 1. Textual overlap (local scan; `results/prior_overlap_scan.json`)

| Prior | share of the current paper's 6-word shingles found in the prior | 10-word | longest verbatim run | share of numeric tokens of the current PDF also present in the prior's text |
|---|---|---|---|---|
| P0 | 0.2 % | 0.04 % | 11 words | 1.8 % |
| P1 | 0.2 % | 0.02 % | 10 words | **19.5 %** |
| P2 | 0.0 % | 0.0 % | 0 | 9.8 % |
| P3 (LaTeX) | 0.07 % | 0 % | 7 words | 3.9 % |
| P3 (compiled PDF) | 0.07 % | 0 % | – | 16.0 % |

[F] The prose is newly written; verbatim textual overlap is negligible. The scan measures only text. It does **not** reduce scientific overlap (§2): the numbers, designs and conclusions are what is shared, and the numeric-token measure (up to ~20 %, higher for the R1-derived tables) is a lower bound because the current paper reports many values rounded or recomputed.

## 2. Contribution-level comparison (every claim checked against files)

Classes: **DR** directly reused (same result, same data); **RA** re-analysed from the previously reported results; **NM** newly measured; **NA** newly analysed (stored data, analysis not in the earlier manuscripts); **NI** new interpretation; **RW** rewritten/reformatted only.

| # | Dimension | Current paper | Earlier manuscripts | Class | Evidence |
|---|---|---|---|---|---|
| 1 | Research question | "Does a multi-agent layer help?" with RQ1–RQ4 (prediction, architecture, components, quality–cost) | P0/P1 ask exactly RQ2/RQ3; P3 O2 asks the same; P2 asks component composition | RW (RQ2/RQ3), NI (RQ4 is new) | titles/abstracts [F] |
| 2 | Research gap / novelty claim | scoped gap vs 2026 LLM-agent literature; "controlled component ladder with cost" | P0–P3 each claim "controlled component-level evaluation, negative result reported with equal weight" | RW; new literature positioning (Tran 2026, Fu 2026) is NI | [F] |
| 3 | Datasets / provenance (RQ1) | M5 CA_1 (350 series, 28-day direct), Online Retail II, proxy-label inactivity, synthetic churn; WAPE; registry re-scoring | P3: MAE-reduction vs naive on 5 datasets (Benroshan, platform, UCI Online Retail, M5 subset, Myanmar), churn table | NA (benchmark run dated 2026-10-15, **after** P0–P3; stored, not measured in this task); registry re-scoring is NM (2026-10-22) | `experiments/ml_benchmark_v1`; P3 §VII-A [F] |
| 4 | Benchmark cases / protocol | R1 locked protocol (12×34×10); upgraded-v1 protocol | P1 and P2 give the R1 protocol in full; P2 names upgraded-v1 | DR (R1); RA (upgraded-v1) | P1 §§ method [F] |
| 5 | Forecasting/classification models | naive/linear/XGBoost registry + benchmark families | P3 same three types | DR for the registry description | [F] |
| 6 | Architecture variants A–D | A–D definitions; **A scored as minimal-intervention action** | P0–P3 define A–D (P3: "prediction only … decision-quality floor") | DR; the A-scoring clarification is NI | [F] |
| 7 | 408-scenario locked study | D−B +0.085, B−A −0.044, C−B −0.054 (null), D−C +0.139, ladder means 0.259/0.216/0.162/0.301, greedy/classical/naive 0.197/0.089/0.367, W/T/L 99/35/274, LOFO +0.050…+0.159, 1 620 perturbed runs, mechanism 57 %/763 vs 1573/62.5→34.6 % | **all appear in P1**; most in P2; headline D−B, p = 5.4e-10, 274/408, rank-biserial also in P3 | **DR** (same `results.json`, sha `9e302f1d…`) | grep matches in P1 for every listed value [F] |
| 8 | 80-scenario locked study | full contrasts incl. D−A +0.109 (Holm 0.003), B−A mixed, family-level contrasts | P2 gives one sentence ("D vs B null, Holm 1.0"); full detail exists only in project docs (`docs/UPGRADED_EVALUATION_REPORT.md`, which is also on the remote) | RA/NA (first *paper-level* presentation of the full contrasts); not new data | [F] |
| 9 | Decision-regret outcome | normalised regret vs exogenous objective | same metric in P1/P2 | DR | [F] |
| 10 | Component ablation | ladder only; **no six-way ablation** | P0/P3 contain the six-way ablation and risk-penalty diagnostic | not repeated (the earlier papers contain more here) | [F] |
| 11 | Sensitivity analyses | (a) LOFO, robustness – stored; (b) exclusion of fallback instances; (c) first-seed only; (d) re-run on another date | P1/P2/P3 have LOFO and robustness; none has (b)–(d) | (a) DR; (b)(c)(d) NA/NM | grep: "first seed" absent in P0–P3 [F] |
| 12 | Cost and latency | measured end-to-end seconds, invocation counts, overhead, 0 model requests, quality–cost dominance | P0 only lists latency as a metric; no result in P0–P3 | **NM** — the clearest new contribution | grep "latency|wall-clock" [F] |
| 13 | Statistical methods | scenario-level paired bootstrap/Wilcoxon, Holm per study | same in P1/P2 (rank-biserial convention differs: P1 −0.469 vs recomputed +0.37) | DR (methods), NI (convention disclosure) | `replication_check.json` [F] |
| 14 | Figures/tables | 4 figures, 7 tables regenerated from JSON | P1: tables/figures of the same R1 data incl. a per-family table | RW (regret figure, family table) + NM (cost figure/table) | [F] |
| 15 | Conclusions / limitations | negative for the tested deterministic layer; synthetic only; no LLM claim | same stance in P0–P3 | RW; limitations partly new (construct validity of a risk-neutral scorer; calendar-anchored histories) | [F] |
| 16 | Citation relationships | cites an anonymised earlier manuscript for R1; shares Kritzinger, Lepenioti, Arnott, Buteau, Hyndman–Koehler, Chen, Bulling | P3/P2 cite only Kritzinger and Buteau in text | RW | `references.bib` [F] |

**New relative to every earlier manuscript (NM/NA):** the end-to-end cost measurement and quality–cost dominance result; the independent recomputation with a stored-vs-recomputed replication check; three stored-artifact discrepancies; sensitivity analyses (fallback exclusion, first seed, date re-run); the paper-level presentation of the 80-scenario study; the predictive benchmark (WAPE, 350-series M5, proxy-label caveats) and the registry re-scoring.
**Not new:** the entire R1 result set (§2 row 7), the A–D design, the direction of the conclusion, the statistical framework.

## 3. Discrepancies the audit found in the EARLIER manuscripts (correct before any submission of P1/P2/P3)

1. [F] P1 states "on the locked run the fallback rate was 0.0 %" (`docs/ieee_paper_r1/main.tex` ~line 328); the stored run records **69 of 4 080 instances (1.7 %)** with `r1_dt_method = fallback_generator` (reason `implausible_elasticity_sign_or_magnitude`), a reason not in P1's list of fallback triggers. The same 0 % appears in `docs/R1_FINAL_REPORT.md`. The conclusion is unchanged (excluding them: D−B +0.085).
2. [F] The stored upgraded-v1 `statistical_results.json` lists win/tie/loss counts in reversed orientation relative to its label.
3. [F] P1/P3 report matched-pairs rank-biserial −0.469 for D−B; the standard formula on the non-zero differences gives +0.37 with the sign convention "positive = first worse". Both reflect the same direction; the convention should be stated.
4. [I] P0, P1 and the current paper share the same title; two different manuscripts under one title will be confused by editors and CrossCheck.

## 4. Verdict on distinctness

* [I] On the **primary scientific finding** (the multi-agent layer degrades regret relative to the simulation-only workflow in R1), the current paper is **not** distinct: it re-presents the same locked data and statistics already written up in P1 (and summarised in P2, P3).
* [I] The paper's separate contribution is **incremental but real**: (i) measured cost showing the layer is cheap in compute yet dominated on (cost, regret); (ii) the independent recomputation/replication audit and the discrepancies it exposed; (iii) the 80-scenario study's full result and the sensitivity analyses; (iv) the newer predictive benchmark. None of these changes the central conclusion.
* [I] Whether (i)–(iv) justify a **separate** publication depends on the venue's rule for "substantive novel contributions" and on the status of P1–P3, which the repository does not establish. Without the risk-mechanism test or any new decision-quality data, a reviewer who has seen P1 will see the paper as P1 plus cost and an audit.
