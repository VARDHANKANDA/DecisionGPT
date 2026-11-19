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
