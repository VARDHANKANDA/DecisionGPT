# EXPERIMENT_PLAN — forecast_study_v1 (pre-registration, written 2026-10-22 before any new result was inspected)

Status: **FROZEN by `FREEZE.json` (plan + code hashes) before the first confirmatory run.** Anything added after the freeze goes into the
"Deviations log" at the end, with its date and reason; nothing above that log is edited after the freeze.

## 1. Intended contribution (and what is explicitly *not* claimed)

The historical benchmark (`experiments/ml_benchmark_v1/`, frozen, never modified) reports one 28-day test window per dataset and a
series-only bootstrap. Its headline "gradient boosting beats the baselines on M5" depends on which baseline is used (RESEARCH_AUDIT.md A3),
on pooled versus aggregate scoring (A4), and on a single origin (A1). This study asks a narrower, defensible question:

> **Does a validation-selected, leakage-safe gradient-boosting direct forecaster still beat strong, information-matched baselines when it
> is evaluated over six consecutive forecast origins, two horizons, two public retail datasets, and dependence-aware uncertainty — and how
> much do the conclusions depend on the evaluation choices (baseline information set, aggregation level, bootstrap design, segment)?**

The contribution is an *empirical, protocol-focused* one: an audited multi-origin evaluation with matched baselines, crossed
series × time uncertainty, per-segment and ablation analyses, and a full reproduction path. It is **not** a new model, **not** evidence about
real Indian SMEs, **not** a claim about churn/decision quality, and **not** a causal statement about why a feature helps.

## 2. Data, windows and leakage controls (fixed)

| Key | Source | Series | Notes |
|---|---|---|---|
| `m5_ca1` | M5 Accuracy (Walmart, store CA_1) — real retail, public competition data | 350 series (historical subset rule) | last block = official evaluation window d_1914–d_1941 |
| `m5_tx1` | M5, store TX_1 | 350 series | second, independent store (same rule) |
| `or2_top100` | UCI Online Retail II — real transactions, UK wholesaler | top-100 SKUs by revenue **before the first validation block** | no price/department features |

* 6 test origins × 28 days = the last 168 days; 3 validation blocks immediately before; test and validation never overlap (`assert_windows_ordered`).
* A model for origin `o` is fitted on rows whose **target day ∈ [o−730, o−1]** only; features at day *t* use history ≤ *t−H* (`H ∈ {7, 28}` = minimum lag).
* `assert_no_future_leakage` (perturb everything after a cutoff, require identical features) is run at four cutoffs per full run; baselines are unit-tested the same way.
* Variant / family / reference-baseline selection uses the **validation blocks only** and is written to `selection.json` *before* any test block is fitted.
* Segments (ADI/CV², volume terciles) use 365 days **before** the first validation block.
* RMSSE scales use training history before the first test block. Constant-history series are excluded and counted.
* This is real transaction/competition data, not synthetic. No result here concerns a customer-churn label; inactivity ≠ churn (see §10).

## 3. Methods compared

Learned (direct strategy, historical feature builder unchanged): ridge, HistGradientBoosting, XGBoost, LightGBM, CatBoost; per family
2 variants (CatBoost 1) chosen on validation; the **primary learned model** is the family/variant with the lowest mean validation WAPE.

Baselines (8 estimators × 2 information sets):
* *matched* — same staleness as the model (uses only history ≤ t−H);
* *fresh* — re-estimated at the block start (28-day blocks; weekly for H=7), i.e. strictly **more recent information than the models**.
Estimators: naive, seasonal naive (7), same-weekday mean (4 and 8 weeks), trailing mean 28, trailing median 28, Croston-SBA (α=0.1), TSB (α=β=0.1).
Models and baselines are scored on **identical (series, day) rows**.

## 4. Metrics (definitions in `metrics.py`)

Primary: pooled **WAPE** = Σ|ŷ−y| / Σy. Secondary: MAE, RMSE, relative bias (positive = over-forecast), mean per-series RMSSE (n used / n excluded),
store-day **aggregate WAPE** and median-series WAPE. **No MAPE** (zero actuals). Undefined results are `None`, never 0. Error metrics are never called "accuracy".

## 5. Hypotheses and decision rules

Confirmatory family (6 tests = 3 datasets × 2 horizons): **model vs the best-validation *matched-information* baseline.**

* **H1 (primary).** The primary learned model has lower pooled WAPE than the reference matched baseline. Estimand: relative WAPE improvement
  (WAPE_base − WAPE_model)/WAPE_base, pooled over 6 origins; two-sided crossed bootstrap p, Holm over the 6 tests (α = 0.05).
  * **SUPPORTED** if Holm p < 0.05 **and** the 95 % CI excludes 0 **and** the estimate ≥ 2 % relative improvement (minimum practically relevant
    difference, fixed here; arbitrary but pre-set) **and** the model wins in ≥ 4 of 6 origin blocks.
  * **CONTRADICTED** if the CI lies entirely below 0. **INCONCLUSIVE** otherwise. Every outcome is reported.
* **H2 (secondary, own Holm family of 6).** Same comparison against the best-validation baseline of *any* information set (the fresh baselines).
  A model that beats matched but not fresh baselines is reported as such: the gain is then information recency, not modelling.
* **H3 (descriptive).** Ranking by pooled WAPE and by store-day aggregate WAPE can differ (Kendall τ reported per cell).
* **H4 (descriptive).** Series-only bootstrap intervals are narrower than crossed series × week intervals (ratio reported); the confirmatory p-values use the crossed design.
* **H5 (exploratory).** Removing a feature group (price, calendar, history statistics, static ids; `m5_ca1`, H=28, variants fixed from the main run, no re-tuning) changes WAPE; reported with crossed CIs, Holm within the 4 ablations, labelled exploratory.
* **H6 (descriptive).** Mondrian split-conformal 80 % intervals (3 prediction-size bins, calibrated on the **validation** predictions of the same method) reach near-nominal marginal coverage on the test blocks; coverage by segment, by origin and by horizon is reported without a pass/fail claim beyond "within ±0.05 of 0.80 overall".
* **H7 (exploratory).** Improvement over the reference baseline differs between demand-frequency segments (frequent vs intermittent/sparse) and volume terciles.

Sensitivity (all reported): stationary week bootstrap, series-only bootstrap, alternative reference baselines (each of the 16), pooled vs aggregate vs
per-series scoring, excluding the lowest-volume tercile, Diebold–Mariano on the store-day aggregate (exploratory, short series), leave-one-origin-out.

Multiplicity: Holm inside each family above. Exploratory results are labelled and not used for the headline.
Uncertainty: crossed series × 7-day-block bootstrap, B = 2000, seed 20261022 (inference.py). Stated limitation: two-way independent resampling is an approximation; the stationary bootstrap is the check.

## 6. Minimum-sample and exclusion rules

* A segment is reported only with ≥ 20 series; otherwise "too small", not an estimate.
* A (dataset, H) cell with fewer than 4 test origins covered is not a confirmatory result.
* Rows where any baseline is undefined (insufficient history) are dropped for *all* methods, and the count is reported.
* Failed fits abort the run (no silent substitution); runs resume only if the configuration hash matches.

## 7. Compute budget

4 cores / 7.7 GB. Per (dataset, H): 3×9 validation fits + 6×5 test fits = 57 fits; a measured single-fit time is recorded before scheduling the full set
(6 cells + 4 ablation cells + classification study). If the measured budget is exceeded, the order is: `m5_ca1` H=28 → `or2_top100` H=28 → `m5_tx1` H=28 → H=7 cells → ablations. A cell not completed is reported as *not run*, and its hypotheses as untested.

## 8. Reproduction

`python -m research.forecast_study_v1.run_forecast_study <dataset> <H>`; analysis and independent verification scripts are listed in `REPRODUCIBILITY.md`.
Predictions for every method are stored (`predictions.npz`), so every number in the manuscript can be recomputed without refitting.

## 9. Integrity commitments

No frozen artifact is modified (`experiments/ml_benchmark_v1/HISTORICAL_HASHES.json`, manifest `94aa419c…`, other experiments); no live AI calls; no test information used for selection, thresholds or tuning; no secrets or customer data in outputs; negative and inconclusive results are reported.

## 10. Classification / customer-scoring study (S2) — scope

Dataset: Online Retail II. The label is an **inactivity proxy** (no purchase in a following window), *not* observed churn. S2 reports discrimination (ROC-AUC, PR-AUC)
separately from calibration (Brier, log-loss, ECE with a fixed binning policy stated in its addendum), P/R/F1/accuracy at **one** threshold chosen on validation only, the confusion matrix,
top-decile lift, and majority-class and recency baselines, with customer-cluster bootstrap CIs. A customer-unseen split is a sensitivity analysis. The detailed S2 design
(window lengths, features, split dates, threshold rule) is added as a dated **addendum before S2 is run**; it is part of the frozen record once added.

### 10.1 S2 addendum (written 2026-10-22, before any new S2 result; reuses `ml/benchmark/churn.py` snapshot/feature/metric code read-only)

* **Label**: `inactive_90d` = no invoice in (cutoff, cutoff+90 d] for customers seen before the cutoff (operational proxy, *not* churn). Features use transactions strictly before the cutoff (historical `snapshot`).
* **Two rolling origins** (label windows never overlap the next stage): origin A — train cutoffs 2010-06-01, 2010-09-01, 2010-12-01; validation 2011-03-14; test 2011-06-12. Origin B (= historical c2) — train cutoffs 2010-06-01, 2010-09-01, 2010-12-01, 2011-03-14; validation 2011-06-12; test 2011-09-10.
* **Models**: logistic regression, random forest, XGBoost, CatBoost (historical hyper-parameters, no new tuning); the primary model = best validation PR-AUC. **Baselines**: prevalence (majority class; constant score), recency rank (score = recency_days), recency-ratio rank.
* **Calibration** is handled separately from discrimination: raw probabilities, Platt scaling (primary calibrated variant) and isotonic regression (sensitivity), both fitted on the validation snapshot only; no selection among them (in-sample validation log-loss would always favour isotonic). ECE uses **10 equal-width bins** (fixed policy; 10 equal-mass bins reported as sensitivity); Brier skill is measured against the prevalence forecast of the same snapshot.
* **Threshold**: ONE threshold per model chosen on validation (maximum F1); on test, precision, recall, F1, accuracy and the confusion matrix at that threshold are reported next to the majority-class accuracy; top-decile lift reported; ROC-AUC, PR-AUC, log-loss, Brier reported at score level.
* **Inference**: customer-cluster bootstrap (B = 2000, a customer appearing once per snapshot, so resampling customers), paired differences model − best baseline for ROC-AUC and PR-AUC; Holm over 2 origins × 2 metrics = 4 tests. Decision rule: SUPPORTED if Holm p < 0.05 and the CI excludes 0 at both origins; otherwise INCONCLUSIVE/CONTRADICTED with the numbers.
* **Sensitivity**: customer-disjoint refit (customers present in the test snapshot removed from train and validation); alternative inactivity window is NOT explored (documented in limitations).
* **Claim limits**: results concern inactivity of customers of one UK wholesaler; they say nothing about contractual churn or about SMEs.

## 11. Deviations log

*(empty at freeze)*

* 2026-10-22 (after the main S2 run, which did not depend on this): the S2 "customer-disjoint refit" as written in section 10.1 (remove customers present in the test snapshot from train and validation) is **vacuous** — every customer seen before a cutoff is in that cutoff's snapshot, so nothing remains; the main run's sensitivity block therefore reports "unsupported". It is replaced by `s2_customer_disjoint.py`: a random 50/50 customer split (seed 42), models/calibration/threshold from G1 customers' earlier snapshots, scoring on G2 customers at the test cutoff, model and baseline fixed from the main run. Reported as a sensitivity analysis only.
* 2026-10-22 (AFTER the six confirmatory cells were analysed — post-hoc): `exploratory_l1.py` (experiment **E1**) added. Motivation, stated honestly: the confirmatory result showed the primary model (a mean-type Tweedie LightGBM) losing pooled WAPE to a trailing-median baseline whose bias is about −0.3, while winning store-day aggregate WAPE by a wide margin; E1 asks whether that is an objective mismatch by refitting the same LightGBM with the L1 (median) objective on the same rows, with no validation selection. It is exploratory, never enters H1/H2/Holm, and every E1 number in the manuscript is labelled post-hoc.
* 2026-10-22 (after freeze, before any full run): `run_all.sh` (orchestration only: executes the cells in the order of section 7) and `make_freeze.py` were added; they are not in `FREEZE.json`'s hash list for `run_all.sh`. No analysis code, metric, split, hypothesis or decision rule changed.
