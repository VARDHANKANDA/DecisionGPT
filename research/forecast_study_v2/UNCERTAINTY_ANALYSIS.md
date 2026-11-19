# UNCERTAINTY_ANALYSIS — inference design and the status of predictive intervals

## 1. Inference for forecast comparisons (confirmatory)

**Estimand and sampling unit.** The estimand is the relative improvement θ = 1 − Σ|e_model| / Σ|e_ref| of an endpoint error pooled over the six test blocks of a window. The comparison is *paired*: both methods are scored on the same (series, day) rows, and the resampled unit is the (series, 7-day block) **cell total** of both methods' absolute errors together. The target of inference is the performance of the prespecified procedure on this *subset of series and these time blocks*, with the series and the weeks treated as samples from larger populations that have crossed dependence (series share calendar days and shocks; weeks share series effects).

**Candidate methods and the pre-freeze simulation** (`simulation.py`, synthetic cell totals with known truth; 24 designs of dependence × 400 replications; `results/simulation_inference.json`):

| method | worst-case \|coverage − 0.95\| over the grid | mean coverage | note |
|---|---|---|---|
| crossed (pigeonhole) percentile bootstrap — **primary** (item-day) | 0.050 | 0.937 | worst case 0.90; Type-I error up to 0.10 at nominal 0.05 |
| two-way cluster-robust delta method, t(G−1) — **secondary** | 0.052 | 0.933 | worst case 0.897 |
| same variance with a normal reference | 0.073 | 0.920 | |
| series-only bootstrap (the v1 benchmark's design) | 0.757 | 0.641 | collapses when week-level shocks are large (coverage 0.19–0.61 at the largest week shock) |

For the **aggregate endpoint** (ratio of sums of absolute daily total errors over 24 weekly blocks, AR(1) daily dependence ρ ∈ {0, 0.3, 0.6}): iid week bootstrap worst-case error 0.057 (coverage 0.89–0.94) — **primary**; circular block 0.083; stationary block (mean 3 weeks) 0.090 — **secondary**.

**Findings that shape the plan.** (i) The crossed bootstrap is *not* conservative in these dense, balanced arrays (coverage 0.90–0.98; it under-covers when week-level shocks are large and series heterogeneity is high), although the pigeonhole bootstrap has been described as mildly conservative for sparse unbalanced designs (Owen, 2007; secondary description); this is not a contradiction because the designs differ. (ii) Both candidate methods are mildly liberal. (iii) Series-only resampling is unacceptable. The plan therefore adds the **dual-method rule**: a verdict stands only if the secondary method gives the same verdict under the same decision rule with its own Holm adjustment.

**Effective sample size.** The report gives, per cell, the number of series, weekly blocks and an approximate number of effective independent cells from the variance-component design effect (v1 audit: about one fifth to one eighth of the nominal cell count; design effect on the standard error about 2.2–2.7).

**Remaining assumptions.** Cell totals are exchangeable across series and across weeks after removing series and week effects; model errors in different blocks are correlated through overlapping training windows (not modelled; it affects only the learned model's side); only 24 weekly blocks per window (the aggregate endpoint has no cross-sectional dimension left); one seed per model (seed variation is reported separately for the item-day model on W2).

## 2. Multiplicity and decision rules

Holm within each family across the eight confirmatory W2 cells (families H1, H1b, H2, H3); replication sets are separate. Verdicts: SUPPORTED / CONTRADICTED / INCONCLUSIVE with a 2 % minimum improvement and at least four of six blocks won; CONTRADICTED is not multiplicity-adjusted. The rules were fixed before any confirmatory outcome and are never changed after seeing results.

## 3. Predictive intervals — status

Predictive intervals are **not part of the confirmatory plan** of this study; they are peripheral to the research question and were not re-evaluated here. What is known (from `forecast_study_v1` and the independent audit): split-conformal 80 % intervals calibrated on earlier validation predictions reached marginal coverage of 0.79–0.81 on M5 CA_1/TX_1 and Online Retail II, but the marginal figure was carried by zero-demand rows (coverage 0.89–0.94) while positive-demand rows were covered at only 0.60–0.67 on M5 (0.79 on Online Retail II); frequent series were under-covered (0.66–0.78). The conformal guarantee does not apply because calibration (earlier origins) and test blocks are not exchangeable under drift. If intervals are included in the manuscript at all, they appear only as a clearly labelled appendix summarising those v1 results, with the zero/positive split, and with no claim of calibrated uncertainty.
