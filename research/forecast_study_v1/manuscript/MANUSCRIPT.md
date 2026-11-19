# How Much Does a Tuned Gradient-Boosting Forecaster Beat Simple Baselines? A Pre-registered, Multi-Origin Evaluation on Public Retail Data

*Draft v1 for author revision — 22 October 2026. Not submitted anywhere. Author names, affiliations, funding and competing-interest statements are intentionally left for the authors (Section 20).*

**Keywords:** demand forecasting; intermittent demand; forecast evaluation; gradient boosting; baselines; WAPE; conformal prediction; reproducibility.

## Abstract

**Background.** Gradient-boosted trees are widely reported to beat simple methods on retail demand data, but most comparisons use a single forecast origin, a weak reference, and uncertainty that ignores dependence between series and across time. **Method.** We pre-registered (plan and code hashed before any confirmatory run) a leakage-controlled, six-origin evaluation of validation-selected gradient-boosting direct forecasters (ridge, HistGradientBoosting, XGBoost, LightGBM, CatBoost) against 16 simple baselines (8 estimators × matched or fresher information) on two M5 stores (350 series each) and the 100 top SKUs of Online Retail II, at horizons of 7 and 28 days. All methods were scored on identical rows; the confirmatory estimand was the relative change in pooled WAPE against the best validation-selected baseline, with a crossed series × week-block bootstrap and Holm correction over six tests. **Results.** The pre-specified hypothesis that the learned model beats the best matched-information baseline was *not supported in any of the six cells*: it was contradicted in three (−3.7 % to −11.4 %; Holm p ≤ 0.016) and inconclusive in three (−2.6 % to −3.7 %). The best baseline was always a trailing 28-day median, which forecasts close to zero for sparse series (relative bias −0.28 to −0.58). At the store-day aggregate level the ranking reverses: the model's WAPE was 0.08–0.11 on M5 against 0.29–0.35 for the median baseline. A post-hoc refit with an L1 objective matched or beat the median baseline in pooled WAPE but lost the aggregate advantage, showing the conclusion depends on objective and metric rather than on one method. Calendar and history-statistic features helped (+2.6 %, +3.5 % WAPE when removed); price and identifier features did not measurably. Mondrian split-conformal 80 % intervals covered 79–81 % overall but under-covered frequent series. On a customer-inactivity proxy label (not churn), the best classifier beat a recency baseline in ROC-AUC at both origins (+0.028, +0.037), while a calibrator fitted on validation worsened calibration when prevalence shifted. **Conclusion.** For intermittent retail demand, whether a boosted model "beats the baseline" is decided by the choice of metric, aggregation level and baseline strength at least as much as by the model. All code, predictions and verification scripts are provided.

## 1. Introduction

Retail demand forecasting is the setting in which gradient-boosted trees earned their reputation: tree-based methods dominated the top of the M5 accuracy competition [Makridakis et al., 2022a; Januschowski et al., 2022] and Kaggle retail competitions [Bojer & Meldgaard, 2021]. Careful evaluation practice is also well documented — rolling origins, scaled errors, and attention to the choice of error measure [Tashman, 2000; Hyndman & Koehler, 2006; Hewamalage et al., 2023; Kolassa, 2020]. Yet applied comparisons often still report one forecast origin, compare against a weak reference such as seasonal naive, and bootstrap only over series. Three questions follow that matter to any practitioner deciding whether a learned model is worth its cost:

1. Against the *strongest simple baseline chosen on validation data*, rather than a convenient one, how large is the gain, and is it distinguishable from sampling noise once dependence between series and across time is respected?
2. Does the answer survive a change of metric or aggregation level?
3. Which input groups carry the gain, and where in the demand-pattern space does it hold?

This paper answers these questions with a protocol that was fixed before the confirmatory results were seen, and reports the answer even though it is largely negative for the learned model on the pre-specified metric.

**Contributions.** (i) A pre-registered, leakage-controlled multi-origin protocol with matched- and fresh-information baselines, scored on identical rows, with a crossed series × time bootstrap and Holm correction. (ii) Evidence from three public series collections that the sign of the headline comparison depends on the baseline set, the metric, and the aggregation level; the best pooled-WAPE method was a trailing median in every cell, the best aggregate-WAPE method was a boosted model in every cell. (iii) Exploratory evidence that feature groups contribute unequally and that an L1-objective refit changes the picture. (iv) A customer-inactivity study on a proxy label that reports discrimination, calibration and one-threshold metrics separately. (v) A reproducible package: stored predictions for every method, independent verification scripts, hashes, and an audit of the repository's earlier benchmark.

**What this paper does not claim.** It is not a new model, not evidence about Indian SMEs or any other business population, not a causal account of why a feature helps, and not a statement about churn. Its datasets are public retail data; its conclusions are bounded to that setting.

## 2. Related work

*Evaluation methodology.* Hewamalage et al. [2023] catalogue pitfalls in forecast evaluation (partitioning, error calculation, testing) and are the closest methodological precedent; this study applies such principles in a concrete, pre-registered protocol rather than adding a principle. Tashman [2000] and Bergmeir & Benítez [2012] discuss out-of-sample and cross-validation schemes for time series; we use forward-chaining origins. Hyndman & Koehler [2006] motivate scaled errors and the difficulty of percentage errors near zero, which is why no MAPE is reported here. Kolassa [2020] shows that the "best" point forecast depends on the error measure — the mechanism behind our central finding.

*Machine learning for retail demand.* Spiliotis et al. [2022] compare statistical and ML methods for daily SKU demand and report lower error and bias for some ML methods on their data; Januschowski et al. [2022] and Bojer & Meldgaard [2021] document the strength of boosted trees in competitions; Fildes et al. [2022] review retail forecasting. Damato et al. [2026, preprint] compare local and global models for intermittent series. Our question is narrower and differently posed: how much of the learned-model advantage survives the strongest validation-selected simple baseline under dependence-aware inference, and does it survive a change of metric.

*Intermittent demand and baselines.* Croston [1972], Syntetos & Boylan [2005] and Teunter et al. [2011] define the standard estimators, which we include. The ADI/CV² classification conventions come from the same literature.

*Uncertainty.* Split-conformal prediction gives finite-sample marginal coverage under exchangeability [Angelopoulos & Bates, 2023]; coverage can drift under distribution shift [Gibbs & Candès, 2021], which we observe and report rather than correct.

*Statistics.* Block resampling for dependent data [Künsch, 1989; Politis & Romano, 1994], Holm's step-down procedure [Holm, 1979] and the Diebold–Mariano test [Diebold & Mariano, 1995].

*Limits of the literature search.* This is a bounded search with verified bibliographic records (see `LITERATURE_REVIEW.md`), not a systematic review; items whose content was not read are cited only for facts established by their verified metadata or abstract.

## 3. Research questions and pre-specified hypotheses

Fixed in `EXPERIMENT_PLAN.md` before any confirmatory run (hash in `FREEZE.json`):

* **H1 (primary, confirmatory, six tests).** The validation-selected learned model has lower pooled WAPE than the best-validation *matched-information* baseline. *Supported* only if Holm p < 0.05, the 95 % interval excludes 0, the relative improvement is ≥ 2 %, and the model wins ≥ 4 of 6 origin blocks.
* **H2 (secondary, six tests).** The same against the best-validation baseline of *any* information set.
* **H3 (descriptive).** Rankings by pooled and store-day aggregate WAPE differ.
* **H4 (descriptive).** Series-only bootstrap intervals are narrower than crossed series × week intervals.
* **H5 (exploratory).** Removing a feature group changes WAPE.
* **H6 (descriptive).** Conformal 80 % intervals reach near-nominal marginal coverage (within ±0.05).
* **H7 (exploratory).** Improvement differs between demand-frequency segments.
* **C (classification, confirmatory).** The best validation-selected classifier beats the best recency baseline in ROC-AUC and PR-AUC at both origins (Holm over 4 tests).

## 4. Data

Three public retail series collections are used; none is synthetic and none is from an Indian SME. (1) **M5 CA_1** and (2) **M5 TX_1**: daily unit sales of 350 item-store series each, drawn by the deterministic rule of the historical benchmark from the Walmart data of the M5 Accuracy competition [Makridakis et al., 2022a]; the last of six test blocks is exactly the official evaluation window (d_1914–d_1941). (3) **Online Retail II (top-100 SKUs)**: daily units of the 100 SKUs with the largest revenue before the first validation block, from the UCI transaction table of a UK online wholesaler; price and department features are not available and are dropped. Licences and provenance are recorded in `inventory/experiment_inventory.json`.

## 5. Protocol

**Origins and splits.** For each dataset with T days, six consecutive 28-day test blocks cover the last 168 days; three 28-day validation blocks immediately precede them (no overlap; asserted in code). A learned model for the block starting at day *o* is refitted on rows whose *target* day lies in [*o*−730, *o*−1] and forecasts days *o*…*o*+27. **Horizon.** The direct strategy uses features whose freshest history input is *H* days old (*H* ∈ {7, 28}); day *t* is predicted from history up to *t*−*H*. **Leakage control.** The feature builder is the historical, unchanged one; at four cutoffs per run the features are recomputed after overwriting all later observations and must be identical (`assert_no_future_leakage`); the baselines are unit-tested the same way.

**Selection before test.** For each family the variant with the lowest mean validation WAPE is chosen; the primary learned model is the best family; the reference baselines are the best validation baselines (any information set, and matched-information only). The selection is written to disk before any test block is fitted, and the verifier checks file modification times.

**Models.** Ridge, HistGradientBoosting, XGBoost [Chen & Guestrin, 2016], LightGBM [Ke et al., 2017] and CatBoost [Prokhorenkova et al., 2018], two small variants each (one for CatBoost), seed 42. **Baselines.** Eight estimators — naive, seasonal naive, same-weekday mean over 4 and 8 weeks, trailing mean and median over 28 days, Croston-SBA [Croston, 1972; Syntetos & Boylan, 2005] and TSB [Teunter et al., 2011] — each under two information sets. *Matched* baselines use only history up to *t*−*H*, exactly like the models. *Fresh* baselines are re-estimated at the block start (weekly for *H*=7), i.e. they see strictly more recent data than the models and answer "is the model better than a simple method that is kept up to date". All methods are scored on identical (series, day) rows.

## 6. Metrics

Primary: pooled WAPE = Σ|ŷ−y|/Σy [Hyndman & Koehler, 2006 discuss the scaling issue]. Secondary: MAE, RMSE, relative bias (positive = over-forecast), mean per-series RMSSE (scale = mean squared one-step difference of the training history; constant-history series excluded and counted), store-day aggregate WAPE and per-series summaries. MAPE is not reported because actuals are zero on a large share of days and no denominator policy is defensible; undefined values are reported as undefined, never as 0. Error metrics are not called accuracy.

## 7. Statistical analysis

The estimand is the relative WAPE improvement of the model over a reference, (WAPE_ref − WAPE_model)/WAPE_ref, pooled over the six origins. Series in one store share calendar days and shocks, and each series is autocorrelated, so the 95 % interval is obtained from a **crossed bootstrap**: series are resampled with replacement and, independently, 7-day target blocks are resampled with replacement (B = 2000; ratio of resampled sums). This builds on block resampling [Künsch, 1989] and is an approximation to the two-way dependence; as sensitivity we use the stationary bootstrap over weeks [Politis & Romano, 1994] and the historical series-only bootstrap. The six confirmatory tests of H1 (3 datasets × 2 horizons) are adjusted with Holm's procedure [Holm, 1979]; H2 forms a separate family of six. A result is called *supported* only if the Holm-adjusted p < 0.05, the interval excludes 0, the estimated improvement is at least 2 % (a minimum relevant difference fixed in advance, arbitrary but declared), and the model wins in at least four of six origin blocks. Segment, ablation and Diebold–Mariano [Diebold & Mariano, 1995] analyses are exploratory and labelled as such. Prediction intervals are Mondrian split-conformal [Angelopoulos & Bates, 2023] with three prediction-size bins, calibrated on the validation predictions of the same method and evaluated on the test blocks; coverage is reported overall, by origin and by demand segment without claiming conditional validity.

## 8. Classification study (customer inactivity proxy)

On Online Retail II the label is *no purchase in the 90 days after a cutoff* for customers seen before it. It is an operational proxy for inactivity and **not** observed churn. Two rolling origins (test cutoffs 2011-06-12 and 2011-09-10) with chronologically earlier training and validation snapshots (label windows never overlap the next stage). Four classifiers (logistic regression, random forest, XGBoost, CatBoost; historical hyper-parameters) are compared with a prevalence baseline and two recency-rank baselines. Calibrators (Platt, isotonic) and the single decision threshold (maximum F1) are fitted on the validation snapshot only. Reported separately: discrimination (ROC-AUC, PR-AUC [Saito & Rehmsmeier, 2015]), calibration (Brier score and skill vs. the prevalence forecast, log-loss, ECE with ten equal-width bins [Guo et al., 2017] and ten equal-mass bins), and threshold metrics (precision, recall, F1, accuracy next to the majority-class accuracy, confusion matrix, top-decile lift). Intervals come from a customer bootstrap (one snapshot row per customer), paired differences against the best validation baseline, Holm over 2 origins × 2 metrics, and a customer-disjoint refit as a sensitivity analysis.

## 9. Results: confirmatory forecasting tests (H1, H2)

All six (dataset, horizon) cells completed; every cell passed the independent verification (24/24 checks, Section 18). Table numbers refer to `results/TABLES.md` and `results/CONFIRMATORY_SUMMARY.md`, generated from stored files.

**Selection.** On validation data LightGBM with the Tweedie objective was the best learned configuration in all six cells, and a trailing 28-day median was the best baseline (with fresh information in five cells; on Online Retail II at H = 28 the best baseline overall was a matched one, so H1 and H2 coincide there).

**Table 1. H1 — primary model vs best matched-information baseline (pooled WAPE; relative improvement, positive = model better; Holm over 6).**

| Cell | WAPE baseline | WAPE model | Improvement [95 % crossed CI] | Blocks won | Holm p | Verdict |
|---|---|---|---|---|---|---|
| M5 CA_1, H=28 | 0.724 | 0.743 | −2.6 % [−5.8, +0.3] | 1/6 | 0.207 | inconclusive |
| M5 CA_1, H=7 | 0.682 | 0.707 | −3.7 % [−6.4, −1.1] | 0/6 | 0.016 | contradicted |
| M5 TX_1, H=28 | 0.749 | 0.835 | −11.4 % [−14.8, −8.2] | 0/6 | <0.001 | contradicted |
| M5 TX_1, H=7 | 0.710 | 0.789 | −11.1 % [−14.3, −8.1] | 0/6 | <0.001 | contradicted |
| Online Retail II, H=28 | 0.874 | 0.906 | −3.7 % [−10.4, +1.8] | 3/6 | 0.366 | inconclusive |
| Online Retail II, H=7 | 0.853 | 0.879 | −3.0 % [−8.4, +1.7] | 1/6 | 0.366 | inconclusive |

H1 was **not supported in any of the six cells**. Against the best baseline of any information set (H2) the model was worse with intervals excluding zero in the four M5 cells (−4.6 % to −15.0 %, all Holm p < 0.001) and inconclusive on Online Retail II (−2.9 %, −3.7 %). Removing any one origin block never changed the sign of the headline estimate (Table T6: all 36 leave-one-origin-out estimates are negative). Because H1 was not supported, the minimum-relevant-gain and block-win criteria were never decisive.

## 10. The metric and the aggregation level change the answer (H3)

**Table 2. Primary model vs best matched baseline at two scoring levels** (Figure 2).

| Cell | Pooled WAPE model / baseline | Store-day aggregate WAPE model / baseline | Rel. bias model / baseline | RMSE model / baseline | MAE model / baseline |
|---|---|---|---|---|---|
| M5 CA_1, H=28 | 0.743 / 0.724 | 0.105 / 0.306 | −0.083 / −0.299 | 2.257 / 2.454 | 1.113 / 1.084 |
| M5 CA_1, H=7 | 0.707 / 0.682 | 0.082 / 0.288 | −0.039 / −0.280 | 2.130 / 2.325 | 1.059 / 1.021 |
| M5 TX_1, H=28 | 0.835 / 0.749 | 0.114 / 0.347 | −0.065 / −0.339 | 2.069 / 2.130 | 0.927 / 0.832 |
| M5 TX_1, H=7 | 0.789 / 0.710 | 0.099 / 0.329 | −0.036 / −0.321 | 1.912 / 2.020 | 0.876 / 0.788 |
| OR II, H=28 | 0.906 / 0.874 | 0.360 / 0.730 | −0.050 / −0.583 | 80.95 / 86.58 | 27.42 / 26.45 |
| OR II, H=7 | 0.879 / 0.853 | 0.357 / 0.714 | −0.071 / −0.546 | 80.20 / 85.24 | 26.60 / 25.82 |

The baseline wins item-day pooled WAPE and MAE in all six cells, and the model wins store-day aggregate WAPE and RMSE in all six cells, by a wide margin at the aggregate level (aggregate WAPE about 3–3.5× lower on M5 and 2× lower on Online Retail II). The mechanism is visible in the bias column: a trailing median of a sparse series is zero on most days, so it earns a low item-day absolute error while under-forecasting total demand by 28–58 %. Pooled WAPE is minimised by a conditional median [Kolassa, 2020]; the Tweedie-objective model estimates a conditional mean. The best method by pooled WAPE was a trailing median in all six cells and the best method by aggregate WAPE was a boosted model in all six; rank agreement between the two scores over the 21 methods was low (Kendall τ between −0.06 and 0.38, nominally significant only on Online Retail II; Table T3). **This is the main finding: for these data the statement "the learned model beats the baseline" has no metric-free truth value.**

## 11. Uncertainty design (H4)

The crossed series × week-block interval was 21–47 % wider than the series-only interval of the historical benchmark (Table T2; ratio 1.21–1.29 on M5, 1.46–1.47 on Online Retail II) and agreed closely with the stationary-bootstrap alternative. Under the series-only design the M5 CA_1 H=28 estimate (−2.6 %) would have been "significant" (interval −5.1 to −0.2) while the crossed interval includes zero; on Online Retail II H=28 the series-only upper limit is 0.0. The direction of every estimate is against the model, so the design choice changes the strength of the statement, not its sign.

## 12. Where the learned model helps: segments and features (H7, H5; exploratory)

*Segments (Table T4).* On M5 CA_1 the model improved on the matched baseline for frequent (+6.3 % [3.3, 9.5], 50 series), smooth (+7.9 % at H=28), and high-volume series (+4.8 % [0.8, 7.8]) and was worse for intermittent (−8.0 % [−12.0, −3.8]; 300 series) and low-volume series (−35.0 % [−44.9, −25.8]). The pattern was **not replicated** on M5 TX_1 (frequent +2.1 % [−1.7, 6.0]; high volume −2.4 % [−5.7, 0.7]) nor on Online Retail II; the segment advantage should be regarded as store-specific. Segment intervals resample series within the segment and carry the same dependence caveats.

*Feature groups (M5 CA_1, H=28, same selected variant, no re-tuning; Holm over 4).* Removing the calendar group (5 features) worsened pooled WAPE by 2.6 % [1.1, 4.3]; removing the history-statistics group (7 features) by 3.5 % [2.3, 4.5] (both Holm p < 0.001). Removing price features (4) changed WAPE by 0.8 % [−0.1, 1.8] (Holm p = 0.19) and static identifiers (3) by 0.3 % [−0.4, 0.8] (Holm p = 0.38). The model's price coefficients are consequently not evidenced as useful for reducing forecast error here; this study makes no statement about price *effects*.

## 13. Post-hoc follow-up: is it the objective? (E1; exploratory, added after seeing Sections 9–10)

To test the objective-mismatch explanation, the same LightGBM configuration was refitted with an L1 objective at every test origin (no validation selection; H = 28).

| Cell | L1 pooled WAPE | L1 aggregate WAPE | L1 bias | L1 vs matched baseline [95 % CI] | L1 vs best any-information baseline | L1 vs Tweedie model |
|---|---|---|---|---|---|---|
| M5 CA_1 | 0.699 | 0.370 | −0.366 | +3.4 % [+2.0, +4.8] | −0.5 % [−2.6, +1.3] | +5.9 % [+3.7, +8.2] |
| M5 TX_1 | 0.743 | 0.450 | −0.445 | +0.8 % [−1.9, +2.9] | −2.4 % [−5.5, +0.1] | +10.9 % [+8.2, +13.8] |
| Online Retail II | 0.787 | 0.523 | −0.491 | +9.9 % [+8.0, +11.8] | +9.9 % [+8.0, +11.8] | +13.1 % [+8.8, +18.1] |

With the median objective the model matches or beats the matched median baseline in pooled WAPE (clearly on two of three datasets) and ties the fresh one on M5, but its aggregate WAPE rises from 0.105–0.360 (Tweedie) to 0.370–0.523 and its bias becomes −0.37 to −0.49. No single configuration wins both scores. Because E1 was designed after the confirmatory results, it is reported as exploratory and does not enter H1/H2.

## 14. Prediction intervals (H6)

Mondrian split-conformal 80 % intervals calibrated on validation predictions of the same method gave overall test coverage of 0.802 and 0.802 (M5 CA_1), 0.794 and 0.793 (TX_1) and 0.807 and 0.810 (Online Retail II) for the learned model — within the pre-specified ±0.05 of 0.80 — and per-origin coverage between 0.775 and 0.824. Coverage was not uniform across demand segments: frequent series were under-covered (0.66–0.78) while intermittent series were covered at 0.81–0.82 (Table T5), as expected when bins are defined by predicted size rather than by demand pattern. Baseline intervals constructed the same way over-covered on M5 (0.83–0.87) and under-covered on Online Retail II (0.77–0.79). Interval widths were comparable for the model and baselines on M5 (e.g. 2.50 vs 2.29 units) but wider for the model on Online Retail II (53.5 vs 35.6 units). Only marginal coverage is claimed.

## 15. Results: customer-inactivity classification (proxy label)

*Data and label.* On Online Retail II a customer is "inactive" if there is no invoice in the 90 days after the cutoff. This is an operational proxy and is **not observed churn**. Test prevalence of inactivity was 0.677 (origin A) and 0.565 (origin B); the validation prevalences were 0.648 and 0.677 — a label shift between validation and test at origin B.

**Table 3. Discrimination and calibration on the test snapshot.**

| Origin | Method | ROC-AUC | PR-AUC | Brier (skill vs prevalence) | log-loss | ECE (10 equal-width) |
|---|---|---|---|---|---|---|
| A | logistic regression, raw | 0.804 | 0.881 | 0.165 (0.243) | 0.505 | 0.083 |
| A | logistic regression, Platt on validation | 0.804 | 0.881 | 0.160 (0.268) | 0.489 | 0.038 |
| A | recency-rank baseline | 0.776 | 0.871 | – | – | – |
| B | random forest, raw | 0.799 | 0.818 | 0.188 (0.235) | 0.556 | 0.092 |
| B | random forest, Platt on validation | 0.799 | 0.818 | 0.196 (0.203) | 0.584 | 0.126 |
| B | recency-rank baseline | 0.762 | 0.798 | – | – | – |

*Confirmatory comparison (C).* The primary classifier (chosen on validation PR-AUC) beat the best recency baseline in ROC-AUC (+0.028 [0.017, 0.039] at A; +0.037 [0.029, 0.044] at B; Holm p < 0.001) and in PR-AUC (+0.010 [0.002, 0.018], Holm p = 0.021 at A; +0.020 [0.011, 0.029], Holm p < 0.001 at B), so C was supported under the pre-registered rule; the PR-AUC gain at origin A is small. Among the four classifiers the test ROC-AUCs differed by at most 0.009 at either origin.

*Calibration is separate from discrimination.* Platt scaling fitted on validation improved calibration at origin A (ECE 0.083 → 0.038; Brier 0.165 → 0.160) but **worsened** it at origin B (ECE 0.092 → 0.126; log-loss 0.556 → 0.584) where the validation prevalence (0.677) differed from the test prevalence (0.565). Discrimination was unchanged by calibration (equal AUCs). A calibrator fitted on one period should therefore not be trusted when prevalence shifts.

*One-threshold metrics.* The single maximum-F1 threshold chosen on validation produced test accuracy 0.762 (A) and 0.691 (B), against majority-class accuracies of 0.677 and 0.565, with recall 0.955 and 0.966 and precision 0.757 and 0.653 (confusion matrices in Table S2b). Because inactivity is the majority class and the F1-optimal threshold flags nearly everyone, accuracy is dominated by prevalence, and top-decile lift is capped (1.40 at A against a maximum of 1/0.677 = 1.48); these metrics are reported but not used for conclusions.

*Customer-disjoint sensitivity.* With a random 50/50 customer split (models and baseline fixed from the main run) the origin-B advantage held (ROC-AUC +0.041 [0.030, 0.053]; PR-AUC +0.028 [0.016, 0.040]) but the origin-A advantage was no longer distinguishable from zero (ROC-AUC +0.011 [−0.006, 0.028]; PR-AUC −0.002 [−0.016, 0.012]), with half the training and test customers. The origin-A result is therefore fragile. (An earlier design for this check, removing all test customers from training, was vacuous — every earlier customer is in the test snapshot — and was replaced; see the plan's deviations log.)

## 16. Summary of confirmatory status

| Hypothesis | Status |
|---|---|
| H1 learned model beats matched baseline (6 tests) | **Not supported** (3 contradicted, 3 inconclusive) |
| H2 learned model beats best baseline of any information set (6 tests) | **Not supported** (4 contradicted, 2 inconclusive) |
| H3 rankings differ by aggregation level | Observed: best method differs in all 6 cells |
| H4 crossed intervals wider than series-only | Observed: 1.21–1.47× |
| H5 feature groups (exploratory) | Calendar and history statistics helped; price and static identifiers not distinguishable from zero |
| H6 conformal coverage within ±0.05 | Met overall (0.793–0.810); not met by demand segment |
| H7 segment differences (exploratory) | Present on M5 CA_1; not replicated on M5 TX_1 or Online Retail II |
| C classification beats recency baseline | Supported at both origins; origin-A gain fragile to customer sub-sampling |

## 17. Discussion

**What the evidence supports.** On three public retail collections, a validation-selected gradient-boosting forecaster did not beat the best simple baseline in item-day pooled WAPE, once that baseline was chosen on validation data and the interval respected dependence across series and weeks. The loss is small on M5 CA_1 and Online Retail II (−2.6 % to −3.7 %, mostly inconclusive) and large on M5 TX_1 (−11 %). The same model was far better at the store-day aggregate level and on RMSE. The best method therefore depends on which loss one cares about: item-day absolute error rewards forecasts near the conditional median — zero for most sparse series — whereas stock, staffing and revenue planning at store level rewards unbiased totals. The L1 refit illustrates the trade-off: a model that wins item-day WAPE gives up aggregate accuracy and carries a strong negative bias.

**Why this matters for practice.** Reporting a single pooled WAPE against seasonal naive — the common comparison — would have shown the boosted models winning (seasonal naive WAPE was 0.89 on M5 CA_1 H=28, against 0.74 for the model), whereas the strongest simple baseline reverses the sign. The strength of the reference and the scoring level are therefore first-order design decisions, not details.

**Relation to prior work.** The strength of boosted trees on M5-type data [Januschowski et al., 2022; Bojer & Meldgaard, 2021] is not contradicted: the model beat most baselines and won at the aggregate level and in RMSE. What is added is a measurement of how much of that advantage depends on the baseline and metric under dependence-aware inference, in the spirit of the evaluation guidance of Hewamalage et al. [2023] and Kolassa [2020]. Spiliotis et al. [2022] report ML gains on SKU demand; our result is a boundary condition for such claims, not a refutation, since the data, the metric and the baseline sets differ.

**Interpretation limits.** (a) The conformal result concerns marginal coverage only. (b) The ablations measure association with forecast error in one store at one horizon; they do not show that price affects demand (nor that it does not). (c) The segment pattern replicated in one of two M5 stores and in none of the Online Retail II samples. (d) The classification label is inactivity, and its calibration result shows only that prevalence shift can invalidate a validation-fitted calibrator.

**What would change the conclusion.** A median-targeting (or quantile) model selected on validation WAPE from the start; a probabilistic baseline for intervals; larger or different datasets; tuned neural or foundation models [Ansari et al., 2024] (not evaluated); or a decision-relevant loss (inventory cost) instead of WAPE.

## 18. Verification and reproducibility

A separate script that does not import the study's metric or inference code recomputed the pooled WAPE, bias, aggregate WAPE and by-block WAPE of the selected model and baselines from the stored predictions of each cell and checked arrays, row uniqueness, window ordering, selection-before-test file order, and the argmin selection rules: 24/24 checks passed in each of the six cells and 19/19 in each of four ablation runs. The repository's earlier benchmark was audited first: its stored metrics were recomputed from stored predictions (maximum difference 5.2 × 10⁻¹⁰) and four historical runs were re-executed into a new directory (c2 and f2 identical; f1 identical on 266 shared numbers; c1 differing in two numbers by at most 1.5 × 10⁻⁵). Twenty-three unit tests cover the leak-free baselines, metric policies, bootstrap and conformal behaviour. The plan and code were hashed before the first confirmatory run, and every deviation (including the post-hoc E1 and the replaced customer-disjoint design) is logged in the plan. Details: `REPRODUCIBILITY.md`.

## 19. Limitations and threats to validity

*Construct validity.* WAPE favours median-type forecasts on sparse data; the 2 % minimum-relevant-gain threshold is a declared but arbitrary choice; the classification label is a proxy.
*Internal validity.* One random seed per model and one machine; seed variance was not estimated. A small hyper-parameter grid (≤ 2 variants per family) was used; stronger tuning could narrow the gap. Matched baselines use the same information staleness as the models, fresh baselines use more recent information — both are reported, but the choice of the "primary" reference is itself data-dependent (made on validation data).
*Statistical conclusion validity.* The crossed bootstrap is an approximation to two-way dependence, checked with the stationary bootstrap; the Diebold–Mariano test is exploratory on short aggregate series; the p-values of exactly 0 from 2000 draws are reported as "< 0.001". Six confirmatory tests were adjusted; exploratory results were not and are labelled.
*External validity.* Two Walmart stores (350-series subsets) and one UK wholesaler's top 100 SKUs; retail only; all public. No data from Indian SMEs or any real customer is used, and no conclusion should be transferred to them. M5 CA_1 and TX_1 are not independent samples of retail practice.
*Post-hoc analysis.* E1 was designed after seeing the confirmatory results; it is hypothesis-generating.
*Not evaluated.* Deep or foundation models, probabilistic forecasters, hierarchical reconciliation, promotion data, inventory-cost metrics, the M5 competition metric, other horizons, seed variance.

## 20. Declarations (to be completed by the authors)

* **Authors and affiliations:** not provided. **Corresponding author:** not provided.
* **Funding:** none stated in the project materials; the authors must declare it.
* **Competing interests:** none stated; the authors must declare it.
* **Author contributions (CRediT):** to be assigned by the authors.
* **Ethics:** only public, secondary, non-interventional data are used; no ethics approval is claimed or needed to be claimed by this draft — the authors and venue decide.
* **Data availability:** M5 (Makridakis et al., Kaggle competition data) and Online Retail II (UCI repository) are public; their licence terms must be confirmed by the authors before redistribution (recorded in `inventory/experiment_inventory.json`; the raw files are not redistributed here). Stored predictions, selections and analysis outputs are in `research/forecast_study_v1/results/`.
* **Code availability:** `research/forecast_study_v1/` (hashes in `FREEZE.json`).
* **Use of generative AI:** the study code, analysis scripts and this draft were prepared with an AI coding assistant (Claude) under the project owner's direction. Venues such as Elsevier journals require a declaration of generative-AI use in manuscript preparation; the authors must review all text and make the declaration.

## 21. Conclusion

For intermittent retail demand, whether a boosted-tree forecaster beats simple baselines is not settled by the model: against the strongest validation-selected baseline and with dependence-aware uncertainty, the pre-specified comparison on item-day pooled WAPE was not supported in any of six cells, while the same models were three times better at the store-day level on M5. The choice of baseline strength, metric and aggregation level should be reported and justified before claims of superiority are made. Within the learned model, calendar and history-statistic features carried the measurable gain; price features did not. On an inactivity proxy label, a learned classifier modestly out-discriminated a recency rule, and a validation-fitted calibrator failed when prevalence shifted.

## 22. References (verified records only; see `LITERATURE_REVIEW.md` for verification marks)

* Angelopoulos, A. N., & Bates, S. (2023). Conformal prediction: A gentle introduction. *Foundations and Trends in Machine Learning*, 16(4), 494–591. doi:10.1561/2200000101
* Ansari, A. F., et al. (2024). Chronos: Learning the language of time series. *Transactions on Machine Learning Research*; arXiv:2403.07815.
* Bergmeir, C., & Benítez, J. M. (2012). On the use of cross-validation for time series predictor evaluation. *Information Sciences*, 191, 192–213. doi:10.1016/j.ins.2011.12.028
* Bojer, C. S., & Meldgaard, J. P. (2021). Kaggle forecasting competitions: An overlooked learning opportunity. *International Journal of Forecasting*, 37(2), 587–603. doi:10.1016/j.ijforecast.2020.07.007
* Chen, T., & Guestrin, C. (2016). XGBoost: A scalable tree boosting system. *Proc. KDD '16*. doi:10.1145/2939672.2939785
* Croston, J. D. (1972). Forecasting and stock control for intermittent demands. *Journal of the Operational Research Society*, 23(3), 289–303. doi:10.1057/jors.1972.50
* Damato, S., Rubattu, N., Azzimonti, D., & Corani, G. (2026). Intermittent time series forecasting: local vs global models. arXiv:2601.14031 (preprint, not peer reviewed when read).
* Diebold, F. X., & Mariano, R. S. (1995). Comparing predictive accuracy. *Journal of Business & Economic Statistics*, 13(3), 253–263. doi:10.1080/07350015.1995.10524599
* Fildes, R., Ma, S., & Kolassa, S. (2022). Retail forecasting: Research and practice. *International Journal of Forecasting*, 38(4), 1283–1318. doi:10.1016/j.ijforecast.2019.06.004
* Gibbs, I., & Candès, E. (2021). Adaptive conformal inference under distribution shift. *Advances in Neural Information Processing Systems*, 34. arXiv:2106.00170
* Guo, C., Pleiss, G., Sun, Y., & Weinberger, K. Q. (2017). On calibration of modern neural networks. *Proc. 34th ICML*, PMLR 70, 1321–1330.
* Hewamalage, H., Ackermann, K., & Bergmeir, C. (2023). Forecast evaluation for data scientists: common pitfalls and best practices. *Data Mining and Knowledge Discovery*, 37(2), 788–832. doi:10.1007/s10618-022-00894-5
* Holm, S. (1979). A simple sequentially rejective multiple test procedure. *Scandinavian Journal of Statistics*, 6(2), 65–70.
* Hyndman, R. J., & Koehler, A. B. (2006). Another look at measures of forecast accuracy. *International Journal of Forecasting*, 22(4), 679–688. doi:10.1016/j.ijforecast.2006.03.001
* Januschowski, T., Wang, Y., Torkkola, K., Erkkilä, T., Hasson, H., & Gasthaus, J. (2022). Forecasting with trees. *International Journal of Forecasting*, 38(4), 1473–1481. doi:10.1016/j.ijforecast.2021.10.004
* Ke, G., et al. (2017). LightGBM: A highly efficient gradient boosting decision tree. *Advances in Neural Information Processing Systems*, 30.
* Kolassa, S. (2020). Why the "best" point forecast depends on the error or accuracy measure. *International Journal of Forecasting*, 36(1), 208–211. doi:10.1016/j.ijforecast.2019.02.017
* Künsch, H. R. (1989). The jackknife and the bootstrap for general stationary observations. *The Annals of Statistics*, 17(3), 1217–1241. doi:10.1214/aos/1176347265
* Makridakis, S., Spiliotis, E., & Assimakopoulos, V. (2022a). M5 accuracy competition: Results, findings, and conclusions. *International Journal of Forecasting*, 38(4), 1346–1364. doi:10.1016/j.ijforecast.2021.11.013
* Politis, D. N., & Romano, J. P. (1994). The stationary bootstrap. *Journal of the American Statistical Association*, 89(428), 1303–1313. doi:10.1080/01621459.1994.10476870
* Prokhorenkova, L., et al. (2018). CatBoost: unbiased boosting with categorical features. *Advances in Neural Information Processing Systems*, 31, 6638–6648.
* Saito, T., & Rehmsmeier, M. (2015). The precision-recall plot is more informative than the ROC plot when evaluating binary classifiers on imbalanced datasets. *PLOS ONE*, 10(3), e0118432. doi:10.1371/journal.pone.0118432
* Spiliotis, E., Makridakis, S., Semenoglou, A.-A., & Assimakopoulos, V. (2022). Comparison of statistical and machine learning methods for daily SKU demand forecasting. *Operational Research*, 22(3), 3037–3061. doi:10.1007/s12351-020-00605-2
* Syntetos, A. A., & Boylan, J. E. (2005). The accuracy of intermittent demand estimates. *International Journal of Forecasting*, 21(2), 303–314. doi:10.1016/j.ijforecast.2004.10.001
* Tashman, L. J. (2000). Out-of-sample tests of forecasting accuracy: an analysis and review. *International Journal of Forecasting*, 16(4), 437–450. doi:10.1016/S0169-2070(00)00065-0
* Teunter, R. H., Syntetos, A. A., & Babai, M. Z. (2011). Intermittent demand: Linking forecasting to inventory obsolescence. *European Journal of Operational Research*, 214(3), 606–615. doi:10.1016/j.ejor.2011.05.018

*Datasets:* M5 Accuracy competition data (Walmart); Online Retail II, UCI Machine Learning Repository (donor citation, licence and access terms to be confirmed by the authors; see Section 20).

**Appendices (separate files in this directory):** A. `EXPERIMENT_PLAN.md` (pre-registration and deviations log); B. `results/TABLES.md` (all generated tables incl. segments, conformal coverage, leave-one-out, S2 details); C. `EVIDENCE_CLAIM_MATRIX.md`; D. `REPRODUCIBILITY.md`; E. `RESEARCH_AUDIT.md`, `LITERATURE_REVIEW.md`; F. figures `manuscript/figures/fig1–4.svg` (forest plot of H1/H2; pooled vs aggregate WAPE; segment plot; conformal coverage by origin).
