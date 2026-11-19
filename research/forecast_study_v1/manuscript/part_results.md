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
