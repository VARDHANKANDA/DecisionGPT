# Generated tables (make_report.py)

## T1. Primary model and references: pooled vs store-day aggregate WAPE and bias

| cell | method | pooled WAPE | store-day aggregate WAPE | rel. bias | MAE | RMSE |
|---|---|---|---|---|---|---|
| M5 CA_1, H=28 | primary model: lightgbm:tweedie | 0.743 | 0.105 | -0.083 | 1.113 | 2.257 |
| M5 CA_1, H=28 | best matched baseline: matched:trailing_median28 | 0.724 | 0.306 | -0.299 | 1.084 | 2.454 |
| M5 CA_1, H=28 | best baseline (any info): fresh:trailing_median28 | 0.695 | 0.298 | -0.290 | 1.042 | 2.371 |
| M5 CA_1, H=7 | primary model: lightgbm:tweedie | 0.707 | 0.082 | -0.039 | 1.059 | 2.130 |
| M5 CA_1, H=7 | best matched baseline: matched:trailing_median28 | 0.682 | 0.288 | -0.280 | 1.021 | 2.325 |
| M5 CA_1, H=7 | best baseline (any info): fresh:trailing_median28 | 0.675 | 0.286 | -0.278 | 1.012 | 2.310 |
| M5 TX_1, H=28 | primary model: lightgbm:tweedie | 0.835 | 0.114 | -0.065 | 0.927 | 2.069 |
| M5 TX_1, H=28 | best matched baseline: matched:trailing_median28 | 0.749 | 0.347 | -0.339 | 0.832 | 2.130 |
| M5 TX_1, H=28 | best baseline (any info): fresh:trailing_median28 | 0.726 | 0.340 | -0.332 | 0.806 | 2.076 |
| M5 TX_1, H=7 | primary model: lightgbm:tweedie | 0.789 | 0.099 | -0.036 | 0.876 | 1.912 |
| M5 TX_1, H=7 | best matched baseline: matched:trailing_median28 | 0.710 | 0.329 | -0.321 | 0.788 | 2.020 |
| M5 TX_1, H=7 | best baseline (any info): fresh:trailing_median28 | 0.703 | 0.326 | -0.318 | 0.781 | 2.001 |
| Online Retail II, H=28 | primary model: lightgbm:tweedie | 0.906 | 0.360 | -0.050 | 27.424 | 80.951 |
| Online Retail II, H=28 | best matched baseline: matched:trailing_median28 | 0.874 | 0.730 | -0.583 | 26.453 | 86.575 |
| Online Retail II, H=7 | primary model: lightgbm:tweedie | 0.879 | 0.357 | -0.071 | 26.597 | 80.201 |
| Online Retail II, H=7 | best matched baseline: matched:trailing_median28 | 0.853 | 0.714 | -0.546 | 25.815 | 85.241 |
| Online Retail II, H=7 | best baseline (any info): fresh:trailing_median28 | 0.854 | 0.713 | -0.535 | 25.859 | 85.143 |

## T2. Bootstrap designs for H1 (relative WAPE improvement vs matched reference)

| cell | crossed series x week [95% CI] | stationary weeks [95% CI] | series-only (historical) [95% CI] | crossed/series-only width |
|---|---|---|---|---|
| M5 CA_1, H=28 | -2.6% [-5.8, 0.3] | -2.6% [-6.0, 0.2] | -2.6% [-5.1, -0.2] | 1.21 |
| M5 CA_1, H=7 | -3.7% [-6.4, -1.1] | -3.7% [-6.2, -1.5] | -3.7% [-5.8, -1.7] | 1.29 |
| M5 TX_1, H=28 | -11.4% [-14.8, -8.2] | -11.4% [-15.0, -8.1] | -11.4% [-14.1, -8.8] | 1.23 |
| M5 TX_1, H=7 | -11.1% [-14.3, -8.1] | -11.1% [-14.2, -8.1] | -11.1% [-13.7, -8.7] | 1.24 |
| Online Retail II, H=28 | -3.7% [-10.4, 1.8] | -3.7% [-10.3, 2.3] | -3.7% [-8.3, 0.0] | 1.46 |
| Online Retail II, H=7 | -3.0% [-8.4, 1.7] | -3.0% [-8.2, 1.5] | -3.0% [-6.7, 0.1] | 1.47 |

## T3. Rank agreement between pooled and store-day aggregate WAPE (21 methods)

| cell | Kendall tau | p | best by pooled WAPE | best by aggregate WAPE |
|---|---|---|---|---|
| M5 CA_1, H=28 | 0.16 | 0.319 | fresh__trailing_median28 | catboost__depth6 |
| M5 CA_1, H=7 | 0.14 | 0.379 | fresh__trailing_median28 | lightgbm__tweedie |
| M5 TX_1, H=28 | -0.06 | 0.694 | fresh__trailing_median28 | catboost__depth6 |
| M5 TX_1, H=7 | 0.07 | 0.649 | fresh__trailing_median28 | lightgbm__tweedie |
| Online Retail II, H=28 | 0.31 | 0.049 | fresh__trailing_median28 | lightgbm__tweedie |
| Online Retail II, H=7 | 0.38 | 0.019 | matched__trailing_median28 | lightgbm__tweedie |

## T4. Segments (exploratory): improvement of the primary model over the matched reference, 95% crossed CI

| cell | segment | n series | WAPE model | WAPE matched ref | rel. improvement [95% CI] |
|---|---|---|---|---|---|
| M5 CA_1, H=28 | frequency=frequent | 50 | 0.547 | 0.584 | 6.3% [3.3, 9.5] |
| M5 CA_1, H=28 | frequency=intermittent_or_sparse | 300 | 0.913 | 0.846 | -8.0% [-12.0, -3.8] |
| M5 CA_1, H=28 | volume=high | 116 | 0.616 | 0.647 | 4.8% [0.8, 7.8] |
| M5 CA_1, H=28 | volume=low | 117 | 1.295 | 0.959 | -35.0% [-44.9, -25.8] |
| M5 CA_1, H=28 | volume=mid | 117 | 1.029 | 0.945 | -8.8% [-12.6, -5.5] |
| M5 CA_1, H=28 | pattern=erratic | 13 | - | - | not estimated (<20 series) |
| M5 CA_1, H=28 | pattern=intermittent | 256 | 0.898 | 0.832 | -7.9% [-12.6, -3.1] |
| M5 CA_1, H=28 | pattern=lumpy | 44 | 0.976 | 0.899 | -8.5% [-16.0, -2.4] |
| M5 CA_1, H=28 | pattern=smooth | 37 | 0.489 | 0.531 | 7.9% [4.9, 11.2] |
| M5 CA_1, H=7 | frequency=frequent | 50 | 0.531 | 0.551 | 3.7% [0.5, 7.2] |
| M5 CA_1, H=7 | frequency=intermittent_or_sparse | 300 | 0.860 | 0.795 | -8.2% [-11.2, -5.0] |
| M5 CA_1, H=7 | volume=high | 116 | 0.580 | 0.599 | 3.1% [0.2, 5.8] |
| M5 CA_1, H=7 | volume=low | 117 | 1.259 | 0.954 | -32.1% [-41.7, -23.1] |
| M5 CA_1, H=7 | volume=mid | 117 | 0.990 | 0.908 | -9.0% [-12.4, -6.1] |
| M5 CA_1, H=7 | pattern=erratic | 13 | - | - | not estimated (<20 series) |
| M5 CA_1, H=7 | pattern=intermittent | 256 | 0.842 | 0.783 | -7.5% [-11.1, -4.2] |
| M5 CA_1, H=7 | pattern=lumpy | 44 | 0.933 | 0.844 | -10.5% [-17.3, -4.4] |
| M5 CA_1, H=7 | pattern=smooth | 37 | 0.472 | 0.502 | 6.0% [2.7, 9.8] |
| M5 TX_1, H=28 | frequency=frequent | 39 | 0.579 | 0.592 | 2.1% [-1.7, 6.0] |
| M5 TX_1, H=28 | frequency=intermittent_or_sparse | 311 | 1.010 | 0.858 | -17.8% [-22.2, -14.4] |
| M5 TX_1, H=28 | volume=high | 117 | 0.703 | 0.687 | -2.4% [-5.7, 0.7] |
| M5 TX_1, H=28 | volume=low | 117 | 1.317 | 0.883 | -49.1% [-68.6, -31.6] |
| M5 TX_1, H=28 | volume=mid | 116 | 1.271 | 1.017 | -25.0% [-32.4, -19.0] |
| M5 TX_1, H=28 | pattern=erratic | 12 | - | - | not estimated (<20 series) |
| M5 TX_1, H=28 | pattern=intermittent | 262 | 1.040 | 0.870 | -19.5% [-24.9, -14.8] |
| M5 TX_1, H=28 | pattern=lumpy | 49 | 0.956 | 0.836 | -14.4% [-22.8, -8.0] |
| M5 TX_1, H=28 | pattern=smooth | 27 | 0.540 | 0.560 | 3.5% [-0.1, 7.3] |
| M5 TX_1, H=7 | frequency=frequent | 39 | 0.535 | 0.550 | 2.7% [-0.9, 6.2] |
| M5 TX_1, H=7 | frequency=intermittent_or_sparse | 311 | 0.964 | 0.821 | -17.4% [-21.5, -14.1] |
| M5 TX_1, H=7 | volume=high | 117 | 0.654 | 0.642 | -1.9% [-4.6, 1.0] |
| M5 TX_1, H=7 | volume=low | 117 | 1.273 | 0.865 | -47.2% [-65.6, -31.6] |
| M5 TX_1, H=7 | volume=mid | 116 | 1.241 | 0.993 | -24.9% [-31.4, -19.6] |
| M5 TX_1, H=7 | pattern=erratic | 12 | - | - | not estimated (<20 series) |
| M5 TX_1, H=7 | pattern=intermittent | 262 | 0.998 | 0.836 | -19.3% [-24.4, -14.9] |
| M5 TX_1, H=7 | pattern=lumpy | 49 | 0.901 | 0.792 | -13.7% [-21.5, -8.1] |
| M5 TX_1, H=7 | pattern=smooth | 27 | 0.519 | 0.533 | 2.7% [-1.0, 6.7] |
| Online Retail II, H=28 | frequency=frequent | 25 | 0.825 | 0.826 | 0.1% [-8.5, 6.6] |
| Online Retail II, H=28 | frequency=intermittent_or_sparse | 75 | 0.979 | 0.917 | -6.7% [-15.4, 0.6] |
| Online Retail II, H=28 | volume=high | 33 | 0.850 | 0.856 | 0.7% [-6.9, 7.1] |
| Online Retail II, H=28 | volume=low | 34 | 1.132 | 0.913 | -23.9% [-46.9, -7.9] |
| Online Retail II, H=28 | volume=mid | 33 | 0.956 | 0.902 | -6.0% [-14.1, 0.2] |
| Online Retail II, H=28 | pattern=erratic | 25 | 0.825 | 0.826 | 0.1% [-8.5, 6.6] |
| Online Retail II, H=28 | pattern=intermittent | 1 | - | - | not estimated (<20 series) |
| Online Retail II, H=28 | pattern=lumpy | 74 | 0.972 | 0.916 | -6.1% [-14.2, 1.1] |
| Online Retail II, H=7 | frequency=frequent | 25 | 0.800 | 0.815 | 1.8% [-4.2, 7.0] |
| Online Retail II, H=7 | frequency=intermittent_or_sparse | 75 | 0.950 | 0.887 | -7.0% [-15.0, -0.5] |
| Online Retail II, H=7 | volume=high | 33 | 0.826 | 0.835 | 1.1% [-4.7, 6.8] |
| Online Retail II, H=7 | volume=low | 34 | 1.055 | 0.882 | -19.6% [-35.6, -6.7] |
| Online Retail II, H=7 | volume=mid | 33 | 0.938 | 0.884 | -6.2% [-13.2, -0.3] |
| Online Retail II, H=7 | pattern=erratic | 25 | 0.800 | 0.815 | 1.8% [-4.2, 7.0] |
| Online Retail II, H=7 | pattern=intermittent | 1 | - | - | not estimated (<20 series) |
| Online Retail II, H=7 | pattern=lumpy | 74 | 0.944 | 0.886 | -6.5% [-13.4, -0.0] |

## T5. 80% Mondrian split-conformal coverage (calibrated on validation predictions of the same method)

| cell | method | overall coverage | mean width | min / max coverage over test blocks | frequent / intermittent coverage |
|---|---|---|---|---|---|
| M5 CA_1, H=28 | model | 0.802 | 2.50 | 0.793 / 0.811 | 0.725 / 0.815 |
| M5 CA_1, H=28 | reference_any | 0.862 | 2.31 | 0.846 / 0.878 | 0.673 / 0.894 |
| M5 CA_1, H=28 | reference_matched | 0.854 | 2.29 | 0.839 / 0.868 | 0.658 / 0.886 |
| M5 CA_1, H=7 | model | 0.802 | 2.42 | 0.793 / 0.816 | 0.713 / 0.817 |
| M5 CA_1, H=7 | reference_any | 0.860 | 2.06 | 0.845 / 0.874 | 0.649 / 0.895 |
| M5 CA_1, H=7 | reference_matched | 0.866 | 2.33 | 0.852 / 0.881 | 0.681 / 0.897 |
| M5 TX_1, H=28 | model | 0.794 | 1.82 | 0.779 / 0.816 | 0.660 / 0.811 |
| M5 TX_1, H=28 | reference_any | 0.834 | 1.30 | 0.828 / 0.845 | 0.489 / 0.878 |
| M5 TX_1, H=28 | reference_matched | 0.830 | 1.30 | 0.825 / 0.838 | 0.477 / 0.874 |
| M5 TX_1, H=7 | model | 0.793 | 1.79 | 0.775 / 0.808 | 0.677 / 0.807 |
| M5 TX_1, H=7 | reference_any | 0.840 | 1.30 | 0.834 / 0.851 | 0.500 / 0.882 |
| M5 TX_1, H=7 | reference_matched | 0.839 | 1.30 | 0.833 / 0.848 | 0.497 / 0.882 |
| Online Retail II, H=28 | model | 0.807 | 53.52 | 0.797 / 0.820 | 0.762 / 0.822 |
| Online Retail II, H=28 | reference_any | 0.771 | 35.56 | 0.730 / 0.813 | 0.757 / 0.775 |
| Online Retail II, H=28 | reference_matched | 0.771 | 35.56 | 0.730 / 0.813 | 0.757 / 0.775 |
| Online Retail II, H=7 | model | 0.810 | 53.64 | 0.785 / 0.824 | 0.777 / 0.821 |
| Online Retail II, H=7 | reference_any | 0.791 | 38.74 | 0.769 / 0.804 | 0.774 / 0.796 |
| Online Retail II, H=7 | reference_matched | 0.790 | 38.54 | 0.762 / 0.807 | 0.780 / 0.793 |

## T6. Leave-one-origin-out relative improvement vs matched reference (headline estimate with each block removed)

| cell | drop 1 | drop 2 | drop 3 | drop 4 | drop 5 | drop 6 |
|---|---|---|---|---|---|---|
| M5 CA_1, H=28 | -2.5% | -2.0% | -2.5% | -2.6% | -3.2% | -2.9% |
| M5 CA_1, H=7 | -3.5% | -3.7% | -3.5% | -3.7% | -4.0% | -3.8% |
| M5 TX_1, H=28 | -11.6% | -11.7% | -11.2% | -11.5% | -11.1% | -11.2% |
| M5 TX_1, H=7 | -11.6% | -10.9% | -10.8% | -11.3% | -11.0% | -10.9% |
| Online Retail II, H=28 | -2.1% | -4.4% | -2.6% | -4.6% | -3.0% | -5.5% |
| Online Retail II, H=7 | -2.4% | -3.2% | -2.8% | -3.2% | -2.6% | -4.1% |

# S2: customer inactivity (PROXY label: no invoice in the following 90 days; not churn)

## S2a. Discrimination, calibration and threshold metrics on the test snapshot (primary model chosen on validation PR-AUC)

| origin | method | ROC-AUC | PR-AUC | log-loss | Brier | Brier skill vs prevalence | ECE (10 equal-width) | ECE (10 equal-mass) | top-decile lift |
|---|---|---|---|---|---|---|---|---|---|
| A (test prevalence 0.677) | logistic_regression (raw) | 0.804 | 0.881 | 0.505 | 0.165 | 0.243 | 0.083 | 0.080 | 1.40 |
| A (test prevalence 0.677) | logistic_regression (platt) | 0.804 | 0.881 | 0.489 | 0.160 | 0.268 | 0.038 | 0.043 | 1.40 |
| A (test prevalence 0.677) | logistic_regression (isotonic) | 0.803 | 0.872 | 0.489 | 0.160 | 0.269 | 0.037 | 0.038 | 1.39 |
| A | baseline recency_rank (rank score) | 0.776 | 0.871 | - | - | - | - | - | 1.41 |
| A | constant score (majority/prevalence) | 0.500 | 0.677 | - | - | - | - | - | 1.00 |
| B (test prevalence 0.565) | random_forest (raw) | 0.799 | 0.818 | 0.556 | 0.188 | 0.235 | 0.092 | 0.092 | 1.63 |
| B (test prevalence 0.565) | random_forest (platt) | 0.799 | 0.818 | 0.584 | 0.196 | 0.203 | 0.126 | 0.126 | 1.63 |
| B (test prevalence 0.565) | random_forest (isotonic) | 0.797 | 0.806 | 0.590 | 0.196 | 0.201 | 0.126 | 0.126 | 1.60 |
| B | baseline recency_rank (rank score) | 0.762 | 0.798 | - | - | - | - | - | 1.60 |
| B | constant score (majority/prevalence) | 0.500 | 0.565 | - | - | - | - | - | 1.00 |

## S2b. One validation-chosen threshold (maximum F1) applied to the test snapshot

| origin | method | threshold | precision | recall | F1 | accuracy | majority-class accuracy | TP | FP | FN | TN |
|---|---|---|---|---|---|---|---|---|---|---|---|
| A | logistic_regression (raw) | 0.412 | 0.757 | 0.955 | 0.844 | 0.762 | 0.677 | 3202 | 1029 | 151 | 569 |
| A | logistic_regression (Platt) | 0.460 | 0.757 | 0.955 | 0.844 | 0.762 | 0.677 | 3202 | 1029 | 151 | 569 |
| A | recency_rank | 29.000 | 0.753 | 0.898 | 0.819 | 0.731 | 0.677 | 3011 | 989 | 342 | 609 |
| B | random_forest (raw) | 0.409 | 0.653 | 0.966 | 0.779 | 0.691 | 0.565 | 2868 | 1522 | 101 | 765 |
| B | random_forest (Platt) | 0.403 | 0.653 | 0.966 | 0.779 | 0.691 | 0.565 | 2868 | 1522 | 101 | 765 |
| B | recency_rank | 37.000 | 0.644 | 0.913 | 0.755 | 0.665 | 0.565 | 2710 | 1501 | 259 | 786 |

## S2c. Paired difference primary model minus best baseline (customer bootstrap, B=2000) and Holm over 4 tests

| origin | model | baseline | metric | difference | 95% CI | raw p | Holm p |
|---|---|---|---|---|---|---|---|
| A | logistic_regression | recency_rank | roc_auc | +0.0282 | [+0.0173, +0.0390] | <0.001 | <0.001 |
| A | logistic_regression | recency_rank | pr_auc | +0.0099 | [+0.0020, +0.0182] | 0.021 | 0.021 |
| B | random_forest | recency_rank | roc_auc | +0.0366 | [+0.0295, +0.0438] | <0.001 | <0.001 |
| B | random_forest | recency_rank | pr_auc | +0.0196 | [+0.0108, +0.0288] | <0.001 | <0.001 |

Decision per metric under the pre-registered rule: {'roc_auc': 'SUPPORTED', 'pr_auc': 'SUPPORTED'}.

## S2d. All four classifiers, uncalibrated test ROC-AUC / PR-AUC

| origin | logistic_regression | random_forest | xgboost | catboost |
|---|---|---|---|---|
| A | 0.804 / 0.881 | 0.813 / 0.887 | 0.808 / 0.884 | 0.805 / 0.880 |
| B | 0.794 / 0.814 | 0.799 / 0.818 | 0.795 / 0.813 | 0.794 / 0.812 |

## S2e. Customer-disjoint sensitivity (random 50/50 customer split; model and baseline fixed from the main run)

| origin | rows train / val / test | model ROC-AUC | baseline ROC-AUC | diff ROC-AUC [95% CI] | diff PR-AUC [95% CI] |
|---|---|---|---|---|---|
| A | 5085 / 2291 / 2477 | 0.789 | 0.778 | +0.0109 [-0.0064, +0.0285] | -0.0022 [-0.0162, +0.0124] |
| B | 7376 / 2474 / 2624 | 0.796 | 0.755 | +0.0411 [+0.0297, +0.0533] | +0.0278 [+0.0159, +0.0398] |

# H5: feature-group ablations (EXPLORATORY; M5 CA_1, H=28, no re-tuning)

| removed group | features removed | WAPE full | WAPE ablated | change when removed | 95% CI of full-vs-ablated improvement | Holm p |
|---|---|---|---|---|---|---|
| calendar | 5 | 0.743 | 0.762 | +2.63% | [+1.13, +4.31]% | <0.001 |
| history_stats | 7 | 0.743 | 0.769 | +3.50% | [+2.31, +4.51]% | <0.001 |
| price | 4 | 0.743 | 0.749 | +0.82% | [-0.14, +1.78]% | 0.192 |
| static_ids | 3 | 0.743 | 0.745 | +0.26% | [-0.39, +0.84]% | 0.376 |

# E1: POST-HOC exploratory: same LightGBM with the L1 (median) objective, no validation selection

| cell | method | pooled WAPE | store-day aggregate WAPE | rel. bias | L1 vs matched ref [95% CI] | L1 vs any-info ref [95% CI] | L1 vs Tweedie primary [95% CI] |
|---|---|---|---|---|---|---|---|
| M5 CA_1, H=28 | LightGBM L1 (post-hoc) | 0.699 | 0.370 | -0.366 | +3.4% [+2.0, +4.8] | -0.5% [-2.6, +1.3] | +5.9% [+3.7, +8.2] |
| M5 CA_1, H=28 | LightGBM Tweedie (primary) | 0.743 | 0.105 | -0.083 | | | |
| M5 CA_1, H=28 | matched median baseline | 0.724 | 0.306 | -0.299 | | | |
| M5 TX_1, H=28 | LightGBM L1 (post-hoc) | 0.743 | 0.450 | -0.445 | +0.8% [-1.9, +2.9] | -2.4% [-5.5, +0.1] | +10.9% [+8.2, +13.8] |
| M5 TX_1, H=28 | LightGBM Tweedie (primary) | 0.835 | 0.114 | -0.065 | | | |
| M5 TX_1, H=28 | matched median baseline | 0.749 | 0.347 | -0.339 | | | |
| Online Retail II, H=28 | LightGBM L1 (post-hoc) | 0.787 | 0.523 | -0.491 | +9.9% [+8.0, +11.8] | +9.9% [+8.0, +11.8] | +13.1% [+8.8, +18.1] |
| Online Retail II, H=28 | LightGBM Tweedie (primary) | 0.906 | 0.360 | -0.050 | | | |
| Online Retail II, H=28 | matched median baseline | 0.874 | 0.730 | -0.583 | | | |
