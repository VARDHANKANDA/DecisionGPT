# Item-Day WAPE, Aggregation Level and Baseline Strength: A Multi-Block Evaluation of Gradient-Boosting Forecasters on Public Retail Data

*Draft v2 — revised after the independent audit of 22 October 2026 (`audit_v1/AUDIT_SUMMARY.md`). **Not ready for submission.** Not submitted, posted or registered anywhere. Author names, affiliations, funding, competing interests and the generative-AI declaration are left for the authors (Section 19). The v1 draft (`MANUSCRIPT.md`) is preserved unchanged; every change is listed in `audit_v1/MANUSCRIPT_v2_CHANGE_REPORT.md`.*

**Keywords:** demand forecasting; intermittent demand; forecast evaluation; scoring functions; gradient boosting; WAPE; baselines; conformal prediction; reproducibility.

## Abstract

**Background.** Gradient-boosted trees are strong on retail demand data, but whether they "beat" a simple baseline depends on the error measure, as the theory of point-forecast scoring implies. This paper quantifies that dependence on public data. **Method.** An internally frozen, pre-specified evaluation (not registered externally) compared validation-selected boosted direct forecasters with 16 simple baselines (8 estimators, two information sets) on two M5 stores (350 series each) and the 100 top-revenue SKUs of Online Retail II, at minimum forecast lags of 7 and 28 days, with six 28-day test blocks per cell, a paired crossed series × week-block bootstrap and Holm correction. No candidate model used a median-type objective. **Results.** The hypothesis that the model beats the best matched baseline in pooled item-day WAPE was not supported in any of six cells (contradicted in three, −3.7 % to −11.4 %; inconclusive in three, −2.6 % to −3.7 %); the best baseline was always a trailing 28-day median. Summing demand before scoring reversed the ranking in every cell, already at item-week level. The median's aggregate error was close to its level bias (−0.28 to −0.58), which on M5 came mostly from zero forecasts and on Online Retail II mostly from right-skewed demand. In a post-hoc follow-up an L1-objective refit matched or beat the median baseline in pooled WAPE on two datasets, but not in aggregate on M5. Exploratory ablations found calendar and history features helpful. Conformal 80 % intervals covered 79–81 % overall, carried by zero-demand rows (positive-demand rows: 60–79 %). **Conclusion.** On these data item-day WAPE favours median-type forecasts. The result illustrates established theory; it does not show that machine-learning forecasts generally fail to beat simple baselines.

## 1. Introduction

Gradient-boosted trees earned their reputation in retail demand forecasting: in the M5 accuracy competition LightGBM was used by all of the top 50 teams [Makridakis et al., 2022a], and tree-based methods outperformed other approaches there [Januschowski et al., 2022]. Reviews of Kaggle forecasting competitions, whose data are typically intermittent, likewise find gradient-boosted trees to be strong forecasters [Bojer & Meldgaard, 2021]. Evaluation practice has its own literature on out-of-sample design, scaled errors and statistical testing [Tashman, 2000; Hyndman & Koehler, 2006; Hewamalage et al., 2023]. That literature also makes a theoretical point that matters here: the point forecast that is optimal depends on the scoring function, and the median, not the mean, is optimal for absolute error [Gneiting, 2011; Kolassa, 2020]. For sparse daily demand, absolute-error-type measures can therefore reward forecasts near zero and rank methods in ways that do not match the decision at hand [Hyndman & Koehler, 2006; Kolassa, 2016; Prestwich et al., 2014; Kourentzes, 2014].

This paper provides an empirical illustration of that dependence on three public series collections, with an evaluation designed to be reproducible and with dependence-aware uncertainty. It asks:

1. Against the strongest simple baseline chosen on validation data, how does a validation-selected boosted forecaster compare in pooled item-day WAPE, and is the difference distinguishable from sampling noise when dependence between series and across weeks is respected?
2. How does the comparison change when the same forecasts are scored after summing demand over days, weeks or items, and what drives the change?
3. Which input groups carry the learned model's gain, and where in the demand-pattern space does it hold? (exploratory)

**What is and is not new.** The dependence of rankings on the scoring function is established theory (Section 2); this paper does not claim to have discovered it. Its contributions are modest and empirical: (i) magnitudes for three public datasets under a paired, dependence-aware design with matched- and fresh-information baselines scored on identical rows; (ii) the same forecasts scored at four aggregation levels, with a decomposition of the baseline's bias by mechanism and dataset; (iii) conformal interval coverage separated by zero and positive demand; and (iv) a package from which every table can be recomputed. **What the study does not show:** that machine-learning forecasting generally fails to beat simple baselines; anything about Indian SMEs or any other business population; a causal account of why a feature helps; or anything about customer churn. Its conclusions are bounded to the three datasets, the model families and objectives that were evaluated, and the metrics used.

## 2. Prior work and positioning

*Scoring functions and point forecasts.* Gneiting [2011] shows that comparing point forecasts by an average score can be "grossly misguided" unless the scoring function and the forecasting task are matched; a score is consistent for the mean when it is a Bregman function and for a quantile when it is generalised piecewise linear, with absolute error as the standard example. Kolassa [2020] makes the practical point that the "best" point forecast depends on the error measure (the expected value minimises squared error; other measures call for other functionals).

*Error measures for intermittent and low-count demand.* Hyndman & Koehler [2006] found many popular measures degenerate in common situations and proposed the mean absolute scaled error. Prestwich et al. [2014] argue that almost all known measures rank forecasters incorrectly on intermittent demand and propose measures based on the underlying process mean. Kolassa [2016] argues that point-accuracy measures such as MAD, MASE and wMAPE are poorly suited to low-count retail data and recommends evaluating full predictive distributions with proper scoring rules. Kourentzes [2014] reports that two proposed metrics performed better than conventional error metrics for optimising intermittent-demand methods. WAPE, the measure used here, is an absolute-error measure scaled by total demand and falls in this family.

*Machine learning for retail demand.* In the M5 accuracy challenge, forecasts were requested at the lowest level of the sales hierarchy and then summed to upper levels [Makridakis et al., 2022a]; Januschowski et al. [2022] discuss why tree-based methods were so widely adopted. Bojer & Meldgaard [2021] review six Kaggle competitions with intermittent data and report that gradient-boosted trees and neural networks are strong, with cross-learning ensembles tending to beat local models. Spiliotis et al. [2022] compare statistical and machine-learning methods for daily SKU demand and report lower error and bias for some ML methods, with cross-learning helping some of them; Fildes et al. [2022] review retail forecasting; Damato et al. [2026, preprint] compare local and global models for intermittent series.

*Evaluation methodology.* Hewamalage et al. [2023] catalogue pitfalls in data partitioning, error calculation and statistical testing; Tashman [2000] and Bergmeir & Benítez [2012] discuss out-of-sample and cross-validation designs. We use forward-chaining retraining blocks.

*Baselines, uncertainty, statistics.* Croston [1972], Syntetos & Boylan [2005] and Teunter et al. [2011] define the intermittent-demand estimators included. Split-conformal prediction gives finite-sample marginal coverage under exchangeability [Angelopoulos & Bates, 2023], which can fail under distribution shift [Gibbs & Candès, 2021]. Block resampling [Künsch, 1989; Politis & Romano, 1994], Holm's procedure [Holm, 1979] and the Diebold–Mariano test [Diebold & Mariano, 1995] are used for inference.

*Positioning.* Against this background the finding that a mean-targeting model can lose an absolute-error comparison to a median baseline on sparse daily demand is expected. What the present data add is the size of the effect on public datasets, its dependence on aggregation level, a decomposition of the baseline's bias, and how the effect looks under paired two-way resampling. This is a bounded literature check with verified bibliographic records and abstract-level reading of the sources cited for specific claims (see the change report), not a systematic review.

## 3. Research questions and pre-specified hypotheses

Written in `EXPERIMENT_PLAN.md` before the confirmatory runs (hash in `FREEZE.json`); see Section 4 for the status of that freeze.

* **H1 (primary, confirmatory, six tests).** The validation-selected learned model has lower pooled item-day WAPE than the best-validation *matched-information* baseline. *Supported* only if the Holm-adjusted p < 0.05, the 95 % interval excludes 0, the relative improvement is ≥ 2 % and the model wins ≥ 4 of 6 test blocks; *contradicted* if the interval lies entirely below 0; otherwise *inconclusive*.
* **H2 (secondary, six tests).** The same against the best-validation baseline of any information set.
* **H3 (descriptive).** Rankings by pooled and by day-aggregated WAPE differ.
* **H4 (descriptive).** Series-only bootstrap intervals are narrower than crossed series × week intervals.
* **H5 (exploratory).** Removing a feature group changes WAPE.
* **H6 (descriptive).** Conformal 80 % intervals reach marginal coverage within ±0.05 of 0.80.
* **H7 (exploratory).** The improvement differs between demand-frequency segments.
* **C (classification).** Pre-specified in the plan; reported in Appendix A (exploratory in this manuscript; see the reasons there).

The plan did not state an expectation about the direction of H1. No candidate model family used an L1 or quantile objective (ridge, squared-error boosting, LightGBM with squared-error or Tweedie objective, CatBoost with RMSE); this is a design property of the study that shapes the result and is discussed in Sections 10, 13 and 16.

## 4. Status of the pre-specification, and disclosures

* **What was done.** The plan text and the hashes of 14 code and test files were recorded in `FREEZE.json` at 2026-10-22T03:29:27Z, before the first confirmatory run; the plan text above its deviations log and the hashed files are unchanged. Within every cell the model selection was written to disk before any test block was fitted (0–2 seconds before the first test fit, after all 27 validation fits).
* **What this is not.** The freeze is an **internal** record in an untracked project directory. It is **not** a public pre-registration: there is no external registry entry or independent time-stamp, and file times and hashes are held by the authors. The study should be described as *pre-specified and internally frozen*, not as *pre-registered*.
* **Disclosures that limit the weight of the freeze.** (1) Before the freeze two quick smoke runs scored real test data: one ridge model on the first M5 CA_1 test block, and the classification study at both origins; the outputs were discarded but seen, and no hypothesis, decision rule or metric was changed afterwards. (2) The authors already knew the stored results of the repository's earlier single-window benchmark on the same final M5 CA_1 days. (3) The six cells were run one after another; the selection in each was automated by frozen code, but the results of earlier cells were visible before later cells ran. (4) The L1-objective follow-up (Section 13) was conceived after the first cell's results and run after all cells were analysed; it is post hoc. (5) The ablations and segment analyses (H5, H7) were pre-specified in the plan as exploratory. (6) Deviations are logged in the plan: orchestration scripts added after the freeze, the post-hoc follow-up, and the replacement of an unworkable customer-disjoint sensitivity design.
* **Authorship of the work.** The study code, analysis scripts and the first draft were produced with an AI coding assistant; the authors must review everything (Section 19).

## 5. Data

Three public retail collections are used. None is synthetic; none comes from an Indian SME.

* **M5 CA_1 and M5 TX_1.** Daily unit sales of 350 item-store series per store from the Walmart data of the M5 accuracy competition [Makridakis et al., 2022a; Kaggle data page, "M5 Forecasting – Accuracy"]. Series are a department-stratified random sample (seed 20261015) drawn among series whose first sale falls on or before day d_1100 (CA_1: 2,673 of 3,049 series eligible; TX_1: 2,661 of 3,049); products launched later are therefore excluded and the subset is not a random sample of each store. **The last test block covers d_1914–d_1941. These are the days whose labels the competition released for its public leaderboard (`sales_train_evaluation.csv` ends at d_1941); they are not the competition's final evaluation window. In addition, every target day here is forecast from information at least *H* days old (Section 6), unlike the competition setting. Results are therefore not comparable with M5 competition scores.** Zero demand: 60 % (CA_1) and 67 % (TX_1) of series-days in the full history.
* **Online Retail II (top-100 SKUs).** Transactions of a UK online wholesaler, 2009-12-01 to 2011-12-09 [Chen, 2012; CC BY 4.0]. Cleaning: cancellation invoices (19,494 rows), non-positive quantity (3,457) or price (2,750), non-product stock codes (4,581) and exact duplicate lines (33,666; 3 %) are dropped, leaving 1,003,423 of 1,067,371 rows; returns are therefore excluded from demand (it is gross sales units); calendar days without trading are zeros; rows without a customer ID are kept for demand. Daily units of the 100 SKUs with the largest revenue before the first validation block are used; price and department features are unavailable and are dropped. These are high-volume items (the top 10 % of series hold 35 % of demand; 32 % of series-days are zero) and are less sparse than M5.

## 6. Protocol

**Terms.** A *cell* is a (dataset, minimum lag *H*) combination (six cells). A *retraining block* is a 28-day span of target days; each cell has **six test blocks** covering the last 168 days (24 weekly sub-blocks) and three validation blocks immediately before them (no overlap; asserted in code). The *minimum lag H* ∈ {7, 28} is the staleness of the freshest history input: target day *t* is predicted from history up to *t*−*H*. Every target day is thus an *H*-day-ahead forecast; for *H* = 7 the information date moves daily, for *H* = 28 the first day of a block is forecast from data ending 28 days earlier. We call the six blocks *retraining blocks* (a learned model for the block starting at day *o* is refitted on rows whose target day lies in [*o*−730, *o*−1]); they are not forecast origins in the M5 sense.

**Leakage control.** The feature builder is the repository's historical, unchanged builder; at four cutoffs per run the features are recomputed after overwriting all later observations and must be identical; the baselines are constructed so that each forecast reads only history up to its cutoff, and an independent re-implementation from raw data that cannot read beyond the cutoff reproduces all stored baselines row by row.

**Selection before test.** For each family the variant with the lowest mean validation WAPE is chosen; the primary learned model is the best family; the reference baselines are the best validation baselines (any information set; matched-information only). The selection is written to disk before any test block is fitted.

**Models.** Ridge, HistGradientBoosting, XGBoost [Chen & Guestrin, 2016], LightGBM [Ke et al., 2017] and CatBoost [Prokhorenkova et al., 2018], two small variants each (one for CatBoost), seed 42; LightGBM with the Tweedie objective was selected in all six cells. **No candidate used an L1 or quantile objective.** **Baselines.** Eight estimators (naive, seasonal naive, same-weekday mean over 4 and 8 weeks, trailing mean and median over 28 days, Croston-SBA [Croston, 1972; Syntetos & Boylan, 2005], TSB [Teunter et al., 2011]) under two information sets: *matched* (history up to *t*−*H*, exactly like the models) and *fresh* (re-estimated at the start of each block, weekly for *H* = 7, i.e. 1 to *H* days old). All methods are scored on identical (series, day) rows (58,800 per M5 cell and 16,800 per Online Retail II cell).

## 7. Metrics

* **Primary:** pooled item-day **WAPE** = Σ|ŷ−y| / Σy over all (series, day) rows. Positive relative bias = over-forecast. MAE and RMSE are also reported. MAPE is not used (actuals are zero on a large share of days); undefined values are never replaced by 0; error metrics are not called accuracy.
* **Aggregation ladder** (applied to the same forecasts): *item-week* (sum each series over its 7-day target block, then score), *subset-week* and *subset-day* (sum all series of the 350-series M5 or 100-SKU Online Retail II subset over each 7-day block or each day, then score the totals). These aggregate over the selected series, not over a whole store. For every method the subset-day WAPE is at least |relative bias| (Σ over days of |daily total error| ≥ |Σ error|).
* RMSSE and per-series summaries were computed in the stored results but are not used in this manuscript.

## 8. Statistical analysis

The estimand is the relative improvement (WAPE_ref − WAPE_model)/WAPE_ref pooled over the six test blocks. Series in one store share calendar days and shocks and each series is autocorrelated, so the 95 % interval comes from a **crossed bootstrap** resampling series with replacement and, independently, the 24 seven-day blocks with replacement (B = 2000; ratio of resampled sums); the p-value is the two-sided bootstrap tail probability, so its resolution is 0.0005 and Holm-adjusted values below the resolution are reported as bounds. The six H1 tests (3 datasets × 2 horizons) are one Holm family; H2 is a second family of six (on Online Retail II H = 28 the best baseline overall is the matched one, so H1 and H2 coincide there). *Supported* needs the Holm-adjusted p < 0.05, an interval excluding 0, a gain of at least 2 % (a declared, arbitrary minimum relevant difference) and at least 4 of 6 block wins; *contradicted* is declared when the interval lies below 0, without multiplicity adjustment (no label here depends on this). Segment, ablation and Diebold–Mariano analyses are exploratory.

*Checks.* An independent implementation of the crossed bootstrap and a different method (a delta-method variance with two-way series/week cluster-robust covariance) reproduce all twelve H1/H2 intervals and verdicts. In a simulation with known two-way dependence (300 series, 24 weekly blocks, true improvement 0) the 95 % crossed interval covered the truth in 90–93 % of replications and the series-only interval in 25–58 %; the crossed design is necessary but mildly anti-conservative. The effective number of independent cells is roughly one fifth to one sixth (M5) and one seventh to one eighth (Online Retail II) of the nominal number. One seed per model was run; seed variance is not in the intervals.

*Intervals for forecasts.* Split-conformal 80 % intervals use three prediction-size bins (group-conditional calibration), calibrated on the validation predictions of the same method and evaluated on the test blocks; clipped at zero below. Calibration residuals come from earlier blocks, so exchangeability with the test blocks is assumed, not shown; only marginal empirical coverage is claimed.

## 9. Results: confirmatory tests (H1, H2)

All six cells completed. On validation data LightGBM with the Tweedie objective was the best learned configuration in every cell and a trailing 28-day median the best baseline (with fresh information in five cells).

**Table 1. H1 — primary model vs best matched-information baseline (pooled item-day WAPE; relative improvement, positive = model better; Holm over six tests).**

| Cell | WAPE baseline | WAPE model | Improvement [95 % crossed CI] | Blocks won | Holm p | Verdict |
|---|---|---|---|---|---|---|
| M5 CA_1, H=28 | 0.724 | 0.743 | −2.6 % [−5.8, +0.3] | 1/6 | 0.207 | inconclusive |
| M5 CA_1, H=7 | 0.682 | 0.707 | −3.7 % [−6.4, −1.1] | 0/6 | 0.016 | contradicted |
| M5 TX_1, H=28 | 0.749 | 0.835 | −11.4 % [−14.8, −8.2] | 0/6 | < 0.003 | contradicted |
| M5 TX_1, H=7 | 0.710 | 0.789 | −11.1 % [−14.3, −8.1] | 0/6 | < 0.003 | contradicted |
| Online Retail II, H=28 | 0.874 | 0.906 | −3.7 % [−10.4, +1.8] | 3/6 | 0.366 | inconclusive |
| Online Retail II, H=7 | 0.853 | 0.879 | −3.0 % [−8.4, +1.7] | 1/6 | 0.366 | inconclusive |

H1 was **not supported in any of the six cells**. Against the best baseline of any information set (H2) the model was worse with intervals below zero in the four M5 cells (−4.6 % to −15.0 %, Holm p < 0.003) and inconclusive on Online Retail II (−2.9 %, −3.7 %). Dropping any one test block never changed the sign of the headline estimate (all 36 leave-one-block-out estimates are negative). The M5 CA_1 H = 28 cell is borderline: the two-way cluster-robust check gives p = 0.052 and one-way intervals (series-only or week-only) exclude zero, so "inconclusive" there means "negative and close to the boundary", not "no difference". An inconclusive cell is not evidence of equivalence.

## 10. Pooled item-day versus aggregated scoring (H3; descriptive)

**Table 2. Primary model vs best matched baseline at two scoring levels.**

| Cell | Pooled item-day WAPE (model / baseline) | Subset-day aggregate WAPE | Relative bias | RMSE | MAE |
|---|---|---|---|---|---|
| M5 CA_1, H=28 | 0.743 / 0.724 | 0.105 / 0.306 | −0.083 / −0.299 | 2.26 / 2.45 | 1.11 / 1.08 |
| M5 CA_1, H=7 | 0.707 / 0.682 | 0.082 / 0.288 | −0.039 / −0.280 | 2.13 / 2.33 | 1.06 / 1.02 |
| M5 TX_1, H=28 | 0.835 / 0.749 | 0.114 / 0.347 | −0.065 / −0.339 | 2.07 / 2.13 | 0.93 / 0.83 |
| M5 TX_1, H=7 | 0.789 / 0.710 | 0.099 / 0.329 | −0.036 / −0.321 | 1.91 / 2.02 | 0.88 / 0.79 |
| Online Retail II, H=28 | 0.906 / 0.874 | 0.360 / 0.730 | −0.050 / −0.583 | 80.95 / 86.58 | 27.42 / 26.45 |
| Online Retail II, H=7 | 0.879 / 0.853 | 0.357 / 0.714 | −0.071 / −0.546 | 80.20 / 85.24 | 26.60 / 25.82 |

The baseline has the lower item-day pooled WAPE and MAE and the model the lower subset-day WAPE and RMSE in all six cells. Rankings over the 21 methods at the two levels agree weakly (Kendall τ −0.06 to 0.38; nominally significant only on Online Retail II). The best method by pooled WAPE was a trailing median in all six cells; the best method by subset-day WAPE was a boosted model in all six.

**Table 3. The same forecasts scored at four aggregation levels (WAPE; sums taken before scoring). Model / matched trailing median.**

| Cell | item-day (pooled) | item-week | subset-week | subset-day |
|---|---|---|---|---|
| M5 CA_1, H=28 | 0.743 / 0.724 | 0.402 / 0.498 | 0.088 / 0.299 | 0.105 / 0.306 |
| M5 CA_1, H=7 | 0.707 / 0.682 | 0.339 / 0.433 | 0.054 / 0.280 | 0.082 / 0.288 |
| M5 TX_1, H=28 | 0.835 / 0.749 | 0.469 / 0.546 | 0.082 / 0.339 | 0.114 / 0.347 |
| M5 TX_1, H=7 | 0.789 / 0.710 | 0.403 / 0.494 | 0.063 / 0.321 | 0.099 / 0.329 |
| Online Retail II, H=28 | 0.906 / 0.874 | 0.562 / 0.651 | 0.188 / 0.583 | 0.360 / 0.730 |
| Online Retail II, H=7 | 0.879 / 0.853 | 0.524 / 0.605 | 0.179 / 0.546 | 0.357 / 0.714 |

The ranking already reverses at **item-week** level in all six cells: summing seven days of a series before scoring is enough for the model to have the lower error. Item-day pooled WAPE is the only level in the ladder at which the median baseline wins.

**Why: the baseline's level bias.** Subset-day WAPE is at least the absolute relative bias; for the matched median on M5 it exceeds |bias| by only 0.008 (e.g. 0.306 vs 0.299 on CA_1, H = 28), i.e. its error in daily totals is almost entirely its level bias. A trailing mean over the same 28-day window (same information, a different functional) is far less biased.

**Table 4. Where the matched median's bias comes from (share of total demand; negative = under-forecast).**

| Cell | Matched median: relative bias | …of which in rows with a zero forecast | …of which in rows with a positive forecast | Matched trailing mean (same window): relative bias | Share of rows with a zero median forecast | Mean / median of positive-demand days (demand-weighted) |
|---|---|---|---|---|---|---|
| M5 CA_1, H=28 | −0.299 | −0.210 | −0.088 | −0.053 | 0.557 | 1.24 |
| M5 CA_1, H=7 | −0.280 | −0.173 | −0.107 | −0.034 | 0.544 | 1.24 |
| M5 TX_1, H=28 | −0.339 | −0.238 | −0.101 | −0.046 | 0.687 | 1.26 |
| M5 TX_1, H=7 | −0.321 | −0.215 | −0.106 | −0.026 | 0.683 | 1.26 |
| Online Retail II, H=28 | −0.583 | −0.060 | −0.523 | −0.131 | 0.177 | 2.00 |
| Online Retail II, H=7 | −0.546 | −0.041 | −0.505 | −0.077 | 0.151 | 2.00 |

*M5.* The median forecasts exactly zero on 54–69 % of rows, including 30–42 % of rows with positive demand (17–24 % of all demand); these rows account for roughly 60–70 % of its bias. This follows from sparse daily series combined with a 28-day median (more than 14 zero days are needed); it is a property of these data and this estimator, not of median forecasting in general. *Online Retail II.* The matched median forecasts zero on only 15–18 % of rows; about 90 % of its bias arises in rows where it forecasts a positive value, and a trailing mean over the same window has bias of only −0.08 to −0.13. The under-forecast there reflects right-skewed demand (the demand-weighted mean-to-median ratio of positive days is about 2.0, against 1.2–1.3 on M5): a 28-day median of skewed order sizes lies well below the mean. The explanation "the median forecasts zero on most days" does not apply to Online Retail II.

**What each level answers.** Item-day pooled absolute error asks how far each forecast is from each day's demand, in units, summed over products; it suits per-item, per-day decisions where a missed unit and an excess unit cost the same, and it hides level bias and is dominated by high-volume series (the top 10 % of series hold 47–52 % of M5 demand). Aggregated WAPE asks whether totals over days, weeks or items match; it suits staffing, budgeting or capacity, and for a biased method it is essentially the bias. Neither shows that one model is better in general. The defensible statement is descriptive: **on these datasets, item-day absolute error favours a zero-leaning (M5) or skew-blind (Online Retail II) median forecast, while any aggregation over days or items favours the learned model, and the difference is mostly level bias.** This is what scoring-function theory predicts [Gneiting, 2011; Kolassa, 2020]; the point forecast that suits an absolute-error metric is a median, and none of the candidate models targeted one (Section 13).

## 11. Uncertainty design (H4)

The crossed series × week-block interval was 21–47 % wider than the series-only interval used by the repository's earlier benchmark (ratio 1.21–1.29 on M5, 1.46–1.47 on Online Retail II) and agreed closely with the stationary-bootstrap alternative. Under the series-only design the M5 CA_1 H = 28 estimate (−2.6 %) would have been "significant" (interval −5.1 to −0.2) while the crossed interval includes zero; on Online Retail II H = 28 the series-only upper limit is 0.0. The direction of every estimate is against the model, so the design changes the strength of the statement, not its sign. The simulation in Section 8 shows why the series-only design is inadequate.

## 12. Exploratory analyses: segments and feature groups (H7, H5)

Both analyses were specified as exploratory in the plan; intervals are unadjusted for the many segment comparisons.

*Segments.* On M5 CA_1 the model improved on the matched baseline for frequent (+6.3 % [3.3, 9.5], 50 series), smooth (+7.9 % at H = 28) and high-volume series (+4.8 % [0.8, 7.8]) and was worse for intermittent (−8.0 % [−12.0, −3.8]; 300 series) and low-volume series (−35.0 % [−44.9, −25.8]). The pattern was **not replicated** on M5 TX_1 (frequent +2.1 % [−1.7, 6.0]; high volume −2.4 % [−5.7, 0.7]) nor on Online Retail II; it should be read as store-specific.

*Feature groups (M5 CA_1, H = 28, same selected variant, no re-tuning).* Removing the calendar group (5 features) worsened pooled WAPE by 2.6 % [1.1, 4.3] and the history-statistics group (7 features) by 3.5 % [2.3, 4.5] (Holm p < 0.002 for both); removing price features (4) changed WAPE by 0.8 % [−0.1, 1.8] (Holm p = 0.19) and static identifiers (3) by 0.3 % [−0.4, 0.8] (Holm p = 0.38). These ablations measure association with forecast error in one store at one horizon; they say nothing about price *effects* on demand, and the price result does not show that price features are useless in general.

## 13. Post-hoc follow-up: a median-objective refit (exploratory; designed after seeing Sections 9–10)

**This analysis is post hoc.** It was conceived after the first cell's results suggested an objective–metric mismatch and was run after all six cells had been analysed. It is not part of the confirmatory families, uses one fixed configuration with no validation selection, and covers H = 28 only.

The same LightGBM configuration was refitted with an L1 objective at every test block, with identical features, windows and seed, and scored on the same rows.

| Cell | L1 pooled WAPE | L1 subset-day WAPE | L1 bias | L1 vs matched baseline [95 % CI] | L1 vs best any-information baseline | L1 vs Tweedie model |
|---|---|---|---|---|---|---|
| M5 CA_1 | 0.699 | 0.370 | −0.366 | +3.4 % [+2.0, +4.8] | −0.5 % [−2.6, +1.3] | +5.9 % [+3.7, +8.2] |
| M5 TX_1 | 0.743 | 0.450 | −0.445 | +0.8 % [−1.9, +2.9] | −2.4 % [−5.5, +0.1] | +10.9 % [+8.2, +13.8] |
| Online Retail II | 0.787 | 0.523 | −0.491 | +9.9 % [+8.0, +11.8] | +9.9 % [+8.0, +11.8] | +13.1 % [+8.8, +18.1] |

With a median objective the model beats the matched median baseline in pooled WAPE on two of three datasets (M5 TX_1: no distinguishable difference) and is indistinguishable from the best (fresh) baseline on M5. Its subset-day WAPE rises above the Tweedie model's on all three datasets (0.105–0.360 → 0.370–0.523) and on M5 above the median baseline's (0.370 vs 0.306; 0.450 vs 0.347), while on Online Retail II it stays below it (0.523 vs 0.730). Its bias becomes −0.37 to −0.49. This is consistent with an objective–metric mismatch explaining much of the original item-day result, but it is hypothesis-generating: it cannot show that a validation-selected median-type model would behave the same. A separate, properly frozen experiment would be required to test that; one has been proposed in writing and has **not** been run.

## 14. Prediction intervals (H6)

The interval procedure is described in Section 8. Overall test coverage of the model's nominal 80 % intervals was 0.802 and 0.802 (M5 CA_1), 0.794 and 0.793 (TX_1) and 0.807 and 0.810 (Online Retail II), within the pre-specified ±0.05, with per-block coverage between 0.775 and 0.824. **The marginal figure is carried by zero-demand rows**:

**Table 5. Empirical coverage of the model's nominal 80 % intervals.**

| Cell | All rows | Zero-demand rows (share of rows) | Positive-demand rows | Frequent series | Intermittent/sparse series |
|---|---|---|---|---|---|
| M5 CA_1, H=28 | 0.802 | 0.938 (0.538) | 0.644 | 0.725 | 0.815 |
| M5 CA_1, H=7 | 0.802 | 0.915 (0.538) | 0.671 | 0.713 | 0.817 |
| M5 TX_1, H=28 | 0.794 | 0.906 (0.628) | 0.604 | 0.660 | 0.811 |
| M5 TX_1, H=7 | 0.793 | 0.893 (0.628) | 0.623 | 0.677 | 0.807 |
| Online Retail II, H=28 | 0.807 | 0.850 (0.317) | 0.787 | 0.762 | 0.822 |
| Online Retail II, H=7 | 0.810 | 0.855 (0.317) | 0.789 | 0.777 | 0.821 |

Zero-demand rows (54–63 % of M5 rows) are covered at 89–94 % because the lower bound is clipped at zero; rows with positive demand are covered at only 60–67 % on M5 and 79 % on Online Retail II. Coverage was also uneven across demand segments: frequent series were under-covered (0.66–0.78) and intermittent series covered at 0.81–0.82. Baseline intervals built the same way over-covered on M5 (0.83–0.87) and under-covered on Online Retail II (0.77–0.79). The result supports only the statement that marginal empirical coverage was close to 80 %; it should not be read as calibrated uncertainty for each SKU or demand regime, and the conformal guarantee does not apply here because calibration and test blocks are not exchangeable under drift.

## 15. Summary of confirmatory status

| Hypothesis | Status |
|---|---|
| H1 model beats matched baseline (6 tests) | **Not supported** (3 contradicted, 3 inconclusive) |
| H2 model beats best baseline of any information set (6 tests) | **Not supported** (4 contradicted, 2 inconclusive) |
| H3 rankings differ by scoring level | Observed in all six cells (item-day vs aggregated levels) |
| H4 crossed intervals wider than series-only | Observed: 1.21–1.47× |
| H5 feature groups (exploratory) | Calendar and history statistics helped (one store, one horizon); price and static identifiers not distinguishable from zero |
| H6 marginal conformal coverage within ±0.05 | Met overall (0.793–0.810); not met for positive-demand rows or frequent series |
| H7 segment differences (exploratory) | Present on M5 CA_1; not replicated on M5 TX_1 or Online Retail II |
| C classification | Appendix A (exploratory in this manuscript) |

## 16. Discussion

**What the evidence supports.** On three public retail collections, a validation-selected mean-targeting gradient-boosting forecaster did not beat the best simple baseline in pooled item-day WAPE, the loss being small on M5 CA_1 and Online Retail II (−2.6 % to −3.7 %, inconclusive or small) and large on M5 TX_1 (−11 %). The same forecasts were better after any aggregation and on RMSE. This is what scoring-function theory predicts for a mean-targeting model scored by absolute error on sparse demand; the study measures how large the effect is in these data and where it comes from.

**What it does not show.** It does not show that machine-learning forecasts fail to beat simple baselines in general: the model families, the objective (no median or quantile candidate in the confirmatory set), the three datasets, the metric and the time windows are specific. The matched-objective model appears only in a post-hoc exploratory run.

**Practical reading.** The scoring level and the objective should match the decision. If the decision is per-item and per-day with symmetric costs, a median-type forecast is appropriate and a mean-targeting model should not be expected to win item-day absolute error. If the decision concerns totals, an unbiased forecast matters more and the aggregated measures are informative. Reporting the aggregation ladder and the bias alongside any single WAPE would make such comparisons interpretable; a single pooled WAPE against a seasonal-naive baseline (0.894 vs 0.743 for the model on M5 CA_1 at H = 28) would have shown the model winning while the strongest simple baseline reverses the sign.

**Relation to prior work.** The strength of boosted trees on M5-type data [Makridakis et al., 2022a; Januschowski et al., 2022; Bojer & Meldgaard, 2021] is not contradicted: the model beat most baselines, won after aggregation and on RMSE. Spiliotis et al. [2022] report lower error and bias for some ML methods on SKU data; the present result is a boundary condition for the pooled item-day metric on these data, not a refutation, since data, metric and baseline sets differ. The scoring-function and intermittent-demand-measure literature in Section 2 explains the direction of the effect.

**Interpretation limits.** (a) Conformal coverage is marginal only and driven by zero demand. (b) The ablations are associations in one store at one horizon. (c) The segment pattern replicated in one of two M5 stores. (d) The matched median's bias has different mechanisms in the two datasets. (e) Subset aggregates are not store totals.

**What would change the conclusion.** A median-type or quantile model selected on validation WAPE from the start; probabilistic or distributional baselines evaluated with proper scoring rules [Kolassa, 2016]; scaled-error metrics such as those used by the M5 competition; larger or different datasets; tuned neural or foundation models [Ansari et al., 2024] (not evaluated); or a decision-relevant loss (inventory cost) instead of WAPE.

## 17. Verification and reproducibility

*Independent audit.* A separate audit, using code that imports nothing from the study (and written by the same AI assistant, so independent in procedure but not in authorship), recomputed from stored predictions or raw data: every evaluation target, all 16 baselines in all six cells (row-exact), 460 numeric values in the v1 manuscript (458 exact; two interval endpoints within bootstrap noise), all twelve H1/H2 verdicts, the conformal coverage values, the exploratory results and the inactivity-study labels. It is documented in `audit_v1/`. The study's own checker passed 24/24 checks per cell and 19/19 per ablation run. Fits equal the stored predictions, tables and figures regenerate byte-identically, and the frozen historical artifacts were unchanged.
*Limits.* Model fits were not re-executed by the audit; the repository's earlier benchmark was re-run (three runs identical, one differing in two numbers by ≤ 1.5×10⁻⁵); no clean-environment reproduction has been done; gradient-boosting libraries can differ in the last digits across platforms and thread counts. Twenty-three unit tests check the baselines, metrics, bootstrap and conformal code; software tests establish that code behaves as written, not that the design answers the research question.

## 18. Limitations and threats to validity

*Construct.* WAPE favours median-type forecasts on sparse demand; the 2 % minimum gain is arbitrary; aggregates are over series subsets, not stores; forecasts are made from information at least *H* days old (not the M5 setting); the horizons are minimum lags.
*Internal.* One seed per model; a small grid; no L1 or quantile candidate in the confirmatory set; no statistical-model families beyond naive, seasonal, moving-average and Croston-type baselines; the primary reference baseline is itself chosen on validation WAPE; training windows overlap across blocks, so errors of the fitted model are correlated across blocks.
*Statistical.* The crossed bootstrap is an approximation and mildly anti-conservative in simulation; the effective sample is roughly one fifth to one eighth of the nominal cells; p-values from 2000 bootstrap draws have resolution 0.0005; segment and Diebold–Mariano analyses are unadjusted and exploratory.
*Pre-specification.* Internal freeze only; exposures disclosed in Section 4.
*External.* Two Walmart stores (350-series subsets selected with an eligibility filter) and the top 100 SKUs of one UK wholesaler; retail only; no Indian SME or other business data; M5 CA_1 and TX_1 are not independent samples of retail practice.
*Post hoc and exploratory.* Section 13 is post hoc; Sections 12 and Appendix A are exploratory.
*Not evaluated.* Deep or foundation models, probabilistic forecasters evaluated with proper scoring rules, hierarchical reconciliation, promotion data, inventory-cost metrics, the M5 scaled-error metric, other horizons, seed variance.

## 19. Declarations (to be completed by the authors)

* **Authors, affiliations, corresponding author, CRediT roles:** not provided.
* **Funding and competing interests:** none are stated in the project materials; the authors must declare them.
* **Ethics:** public secondary data; Online Retail II contains pseudonymous customer IDs (used only in Appendix A); the authors and institution decide whether any review or statement is needed.
* **Data availability.** *Online Retail II* is licensed CC BY 4.0 (Chen, 2012, doi:10.24432/C5CG6D); derived arrays for this dataset may be shared with attribution. *M5* data are available to participants who accept the competition rules on Kaggle; the rules limit use to non-commercial and academic purposes and prohibit publishing or redistributing the data. The study's stored predictions contain actual M5 sales, so they are **not** released with this manuscript; code, aggregate results and instructions for obtaining the data are, subject to the authors' approval. Whether derived M5 arrays may be shared has not been cleared with the rights holder.
* **Code availability:** the study code is in `research/forecast_study_v1/` with hashes in `FREEZE.json`; no public archive or DOI has been created.
* **Use of generative AI:** the study code, analysis scripts and this draft were prepared with an AI coding assistant (Claude) under the project owner's direction, and the independent audit was run by the same assistant. Venues require a truthful declaration; the authors must review all content and take responsibility for it.

## 20. Conclusion

On the three public datasets examined, a validation-selected, mean-targeting gradient-boosting forecaster did not beat the best simple baseline in pooled item-day WAPE in any of six cells (contradicted in three, inconclusive in three), while it was better after summing demand over days, weeks or items and on RMSE. The reversal is largely the baseline's level bias, which arises from zero forecasts on sparse M5 series and from skewed demand on Online Retail II. This is the behaviour that scoring-function theory predicts, and a post-hoc refit with a median objective points the same way. The study therefore illustrates why a forecasting comparison should state the scoring function and aggregation level and report bias; it does not show that machine learning generally fails to outperform simple forecasting baselines. The 80 % conformal intervals reached close to nominal marginal coverage only because zero-demand days are easy to cover. This draft is not ready for submission: the declarations, the data-rights position, a human review, and (if the authors wish to make a methodological claim) a separately frozen metric-matched experiment remain open.

## 21. References

* Angelopoulos, A. N., & Bates, S. (2023). Conformal prediction: A gentle introduction. *Foundations and Trends in Machine Learning*, 16(4), 494–591. doi:10.1561/2200000101
* Ansari, A. F., et al. (2024). Chronos: Learning the language of time series. *Transactions on Machine Learning Research*; arXiv:2403.07815.
* Bergmeir, C., & Benítez, J. M. (2012). On the use of cross-validation for time series predictor evaluation. *Information Sciences*, 191, 192–213. doi:10.1016/j.ins.2011.12.028
* Bojer, C. S., & Meldgaard, J. P. (2021). Kaggle forecasting competitions: An overlooked learning opportunity. *International Journal of Forecasting*, 37(2), 587–603. doi:10.1016/j.ijforecast.2020.07.007
* Chen, D. (2012). Online Retail II [Dataset]. UCI Machine Learning Repository. https://doi.org/10.24432/C5CG6D
* Chen, T., & Guestrin, C. (2016). XGBoost: A scalable tree boosting system. *Proc. KDD '16*. doi:10.1145/2939672.2939785
* Croston, J. D. (1972). Forecasting and stock control for intermittent demands. *Journal of the Operational Research Society*, 23(3), 289–303. doi:10.1057/jors.1972.50
* Damato, S., Rubattu, N., Azzimonti, D., & Corani, G. (2026). Intermittent time series forecasting: local vs global models. arXiv:2601.14031 (preprint, not peer reviewed when read).
* Diebold, F. X., & Mariano, R. S. (1995). Comparing predictive accuracy. *Journal of Business & Economic Statistics*, 13(3), 253–263. doi:10.1080/07350015.1995.10524599
* Fildes, R., Ma, S., & Kolassa, S. (2022). Retail forecasting: Research and practice. *International Journal of Forecasting*, 38(4), 1283–1318. doi:10.1016/j.ijforecast.2019.06.004
* Gibbs, I., & Candès, E. (2021). Adaptive conformal inference under distribution shift. *Advances in Neural Information Processing Systems*, 34. arXiv:2106.00170
* Gneiting, T. (2011). Making and evaluating point forecasts. *Journal of the American Statistical Association*, 106(494), 746–762. doi:10.1198/jasa.2011.r10138
* Guo, C., Pleiss, G., Sun, Y., & Weinberger, K. Q. (2017). On calibration of modern neural networks. *Proc. 34th ICML*, PMLR 70, 1321–1330.
* Hewamalage, H., Ackermann, K., & Bergmeir, C. (2023). Forecast evaluation for data scientists: common pitfalls and best practices. *Data Mining and Knowledge Discovery*, 37(2), 788–832. doi:10.1007/s10618-022-00894-5
* Holm, S. (1979). A simple sequentially rejective multiple test procedure. *Scandinavian Journal of Statistics*, 6(2), 65–70.
* Hyndman, R. J., & Koehler, A. B. (2006). Another look at measures of forecast accuracy. *International Journal of Forecasting*, 22(4), 679–688. doi:10.1016/j.ijforecast.2006.03.001
* Januschowski, T., Wang, Y., Torkkola, K., Erkkilä, T., Hasson, H., & Gasthaus, J. (2022). Forecasting with trees. *International Journal of Forecasting*, 38(4), 1473–1481. doi:10.1016/j.ijforecast.2021.10.004
* Ke, G., et al. (2017). LightGBM: A highly efficient gradient boosting decision tree. *Advances in Neural Information Processing Systems*, 30.
* Kolassa, S. (2016). Evaluating predictive count data distributions in retail sales forecasting. *International Journal of Forecasting*, 32(3), 788–803. doi:10.1016/j.ijforecast.2015.12.004
* Kolassa, S. (2020). Why the "best" point forecast depends on the error or accuracy measure. *International Journal of Forecasting*, 36(1), 208–211. doi:10.1016/j.ijforecast.2019.02.017
* Kourentzes, N. (2014). On intermittent demand model optimisation and selection. *International Journal of Production Economics*, 156, 180–190. doi:10.1016/j.ijpe.2014.06.007
* Künsch, H. R. (1989). The jackknife and the bootstrap for general stationary observations. *The Annals of Statistics*, 17(3), 1217–1241. doi:10.1214/aos/1176347265
* M5 Forecasting – Accuracy [Competition data and rules]. Kaggle. https://www.kaggle.com/competitions/m5-forecasting-accuracy (accessed 22 October 2026; data use subject to the competition rules).
* Makridakis, S., Spiliotis, E., & Assimakopoulos, V. (2022a). M5 accuracy competition: Results, findings, and conclusions. *International Journal of Forecasting*, 38(4), 1346–1364. doi:10.1016/j.ijforecast.2021.11.013
* Politis, D. N., & Romano, J. P. (1994). The stationary bootstrap. *Journal of the American Statistical Association*, 89(428), 1303–1313. doi:10.1080/01621459.1994.10476870
* Prestwich, S., Rossi, R., Armagan Tarim, S., & Hnich, B. (2014). Mean-based error measures for intermittent demand forecasting. *International Journal of Production Research*, 52(22), 6782–6791. doi:10.1080/00207543.2014.917771
* Prokhorenkova, L., Gusev, G., Vorobev, A., Dorogush, A. V., & Gulin, A. (2018). CatBoost: unbiased boosting with categorical features. *Advances in Neural Information Processing Systems*, 31.
* Saito, T., & Rehmsmeier, M. (2015). The precision-recall plot is more informative than the ROC plot when evaluating binary classifiers on imbalanced datasets. *PLOS ONE*, 10(3), e0118432. doi:10.1371/journal.pone.0118432
* Spiliotis, E., Makridakis, S., Semenoglou, A.-A., & Assimakopoulos, V. (2022). Comparison of statistical and machine learning methods for daily SKU demand forecasting. *Operational Research*, 22(3), 3037–3061. doi:10.1007/s12351-020-00605-2
* Syntetos, A. A., & Boylan, J. E. (2005). The accuracy of intermittent demand estimates. *International Journal of Forecasting*, 21(2), 303–314. doi:10.1016/j.ijforecast.2004.10.001
* Tashman, L. J. (2000). Out-of-sample tests of forecasting accuracy: an analysis and review. *International Journal of Forecasting*, 16(4), 437–450. doi:10.1016/S0169-2070(00)00065-0
* Teunter, R. H., Syntetos, A. A., & Babai, M. Z. (2011). Intermittent demand: Linking forecasting to inventory obsolescence. *European Journal of Operational Research*, 214(3), 606–615. doi:10.1016/j.ejor.2011.05.018

## Figures (source SVG files in `figures_v2/`)

* **Figure 1** (`fig1_forest.svg`). Relative improvement in pooled item-day WAPE of the primary model against the best matched-information baseline (H1) and the best baseline of any information set (H2), with 95 % crossed-bootstrap intervals. Negative values mean the baseline is better; the dotted line marks the 2 % minimum relevant gain.
* **Figure 2** (`fig2_aggregation_ladder.svg`). WAPE of the primary model and the best matched baseline (trailing 28-day median) for the same forecasts scored at four aggregation levels, per cell.
* **Figure 3** (`fig3_segments.svg`). Exploratory: relative improvement over the matched baseline by demand-frequency and volume segment, M5 CA_1 and TX_1, H = 28.
* **Figure 4** (`fig4_coverage_zero_positive.svg`). Empirical coverage of the nominal 80 % conformal intervals for all rows, zero-demand rows and positive-demand rows, per cell.

## Appendix A. Exploratory: customer-inactivity study (Online Retail II; proxy label)

**Status.** This study was pre-specified in the plan (hypothesis C), but the audit found its evidence weak and partly redundant, and it is placed here as an exploratory appendix. Its target is **inactivity of customers of one UK wholesaler** — no purchase in the 90 days after a cutoff — not churn; nothing here concerns retention, revenue or business impact.

*Design.* Two origins (test cutoffs 2011-06-12, A, and 2011-09-10, B) with chronologically earlier training and validation snapshots. Four classifiers (logistic regression, random forest, XGBoost, CatBoost; historical hyper-parameters), a prevalence baseline and two recency-rank baselines; calibrators (Platt, isotonic) and the single maximum-F1 threshold fitted on the validation snapshot only; customer bootstrap paired against the best validation baseline; Holm over 2 origins × 2 metrics. Labels, recency scores and customer sets were re-derived from the raw transactions by independent code and equal the stored ones at both origins.

*Results.* The primary classifier (chosen on validation PR-AUC) beat the best recency baseline in ROC-AUC (+0.028 [0.017, 0.039] at A; +0.037 [0.029, 0.044] at B; Holm p < 0.002) and in PR-AUC (+0.010 [0.002, 0.018], Holm p = 0.021–0.024 at A; +0.020 [0.011, 0.029], Holm p < 0.002 at B). Test ROC-AUC / PR-AUC: A 0.804 / 0.881 (recency 0.776 / 0.871); B 0.799 / 0.818 (recency 0.762 / 0.798); the four classifiers' ROC-AUCs differ by at most 0.009.

*Limits that qualify the result.*
1. **The two origins are not independent evidence.** 4,951 customers (94 % of origin B's 5,256 test customers) are in both test snapshots, and their inactivity labels correlate at 0.40. About half of each test cohort (54 % at A, 51 % at B) already appears in the earliest training snapshot (repeated measures on the same customers with different features and labels). "Supported at both origins" is closer to one study with overlapping customers than to two replications.
2. **A half-customer check weakens the origin-A result.** With a random 50/50 customer split (chronology preserved; model and baseline fixed from the main run) the origin-B advantage held (ROC-AUC +0.041 [0.030, 0.053]; PR-AUC +0.028 [0.016, 0.040]) but origin A was not distinguishable from zero (ROC-AUC +0.011 [−0.006, 0.028]; PR-AUC −0.002 [−0.016, 0.012]), with half the customers in each role. This run was not independently re-executed. (An earlier design that removed all test customers from training was vacuous, because every earlier customer is in the test snapshot, and was replaced; see the plan's deviations log.)
3. **Practical value is small.** Precision among the customers flagged at fixed contact budgets (model / recency / prevalence):

| Origin | Top 10 % flagged | Top 20 % | Top 30 % | Top 50 % |
|---|---|---|---|---|
| A | 0.950 / 0.958 / 0.677 | 0.929 / 0.914 / 0.677 | 0.915 / 0.904 / 0.677 | 0.857 / 0.863 / 0.677 |
| B | 0.920 / 0.905 / 0.565 | 0.865 / 0.864 / 0.565 | 0.836 / 0.824 / 0.565 | 0.779 / 0.761 / 0.565 |

The F1-optimal threshold chosen on validation flags 85.5 % (A) and 83.5 % (B) of customers (recall 0.955 and 0.966), i.e. close to "flag everyone"; test accuracy (0.762, 0.691) exceeds the majority-class accuracy (0.677, 0.565) but is dominated by prevalence, and top-decile lift is capped by it (1.40 at A against a maximum of 1.48).
4. **Calibration is separate from discrimination.** Platt scaling fitted on validation improved calibration at origin A (ECE 0.083 → 0.038) but worsened it at origin B (ECE 0.092 → 0.126; log-loss 0.556 → 0.584), where validation prevalence (0.677) differed from test prevalence (0.565). A diagnostic intercept shift of −0.80 logits, computed with the test labels and therefore not a method, lowers the Platt ECE at B from 0.126 to 0.019, consistent with prevalence shift being the cause; at A the shift is −0.03 and ECE is unchanged. Discrimination is unaffected by calibration.
5. **Data handling.** The customer IDs are pseudonymous; customer-level scores should not be published without a licence and institutional check.

**Recommendation recorded by the audit:** treat this appendix as a small, partly fragile secondary result, and evaluate inactivity or churn prediction in a separate study with an independent cohort and labels that establish churn.

## Appendix B. Source files

Plan and freeze: `EXPERIMENT_PLAN.md`, `FREEZE.json`. Results and tables: `results/` (`TABLES.md`, `CONFIRMATORY_SUMMARY.md`, per-cell directories). Independent audit and the numbers added in this version (aggregation ladder, bias decomposition, coverage by zero/positive demand, simulation, overlap statistics): `audit_v1/work/step3.json`, `step4.json`, `step5.json`, `step6.json`, `step16.json` and the corresponding scripts. Figures: `figures_v2/`.
