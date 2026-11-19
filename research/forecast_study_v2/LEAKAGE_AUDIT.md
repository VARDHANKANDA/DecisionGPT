# LEAKAGE_AUDIT — forecast_study_v2 (Phase A)

Pre-freeze audit of the design and code (2026-10-22). Evidence: `tests/unit/test_forecast_study_v2.py` (17 tests), `tools/independent_targets_check.py`, the v1 independent audit (`../forecast_study_v1/audit_v1/`), code reading of `ml/benchmark/features.py` and `direct.py`.

## 1. Checks and results

| # | question | result | evidence |
|---|---|---|---|
| 1 | Is every feature available at the forecast origin? | **Yes** for history features: row t uses sales up to t − H only (`lag_{H+k}`, rolling means/std, non-zero share, days since sale, same-weekday mean). Calendar features (day of week/month, events, SNAP) are known in advance. **M5 price features** use the listed price of day t and earlier prices (`sell_price`, 91-day relative price, 7-day change, days since change): weekly prices are published in advance — an assumption. Static codes (department, category, item id) are fixed identifiers. | code reading; `assert_no_future_leakage` perturbs everything after a cutoff and requires identical history features (run at 3 cutoffs per cell in the validation stage; unit test on Online Retail II W2) |
| 2 | Is the series physically truncated before anything is computed? | **Yes.** `data.load` slices the arrays to T′ before features, baselines, segments and (Online Retail II) SKU selection; `windows.py` removes the trailing days; a unit test confirms W2 arrays are prefix views of W1, that Online Retail II W2 SKUs are recomputed from raw revenue **before the window's first validation day only**, and that no pipeline object has a column ≥ T′. | tests; `independent_targets_check.json` |
| 3 | Do training or validation targets leak into test scoring? | **No by construction:** training rows for the block starting at o have target day ≤ o − 1; validation blocks end before the first test block; the pipeline's validation stage never reads a test block (`stage_validation` loops over `blocks["val"]` only). | code; `windows.check_ordered` asserted for every cell |
| 4 | Are hyper-parameters and model choices made on validation data only? | **Yes.** The candidate set and base hyper-parameters are fixed in `models.py` before any window result; selection per endpoint uses the mean of the three validation blocks; selection is written to disk before any test fit; the test stage verifies this by file order and refuses to run if the freeze changed. **Design information from W1** (post-hoc E1; audit) shaped the candidate list: disclosed. | `pipeline.py`; `freeze.py` |
| 5 | Is preprocessing fitted on the right subset? | The learned models use raw features with native NaN handling (LightGBM/XGBoost); ridge uses the repository's imputer/scaler/one-hot pipeline fitted on the training rows of the block only. No global scaling or target transformation is applied. | `models.py`, `ml/benchmark/models.py` |
| 6 | Are forecast horizons and cutoffs correct? | **Yes for the definition used.** The *minimum lag* H is the staleness of the freshest history input; for H = 28 the first day of a block is forecast from data ending 28 days earlier (not from the day before the block), for H = 7 each day has its own origin. This is **not** the M5 competition setting; it is a direct-H-step design, documented in the protocol. | `baselines.py` unit tests (matched gap = H; fresh gap 1…H) |
| 7 | Do baselines use only past information? | **Yes.** State-based baselines are causal (`state[:, e]` uses `y[:, :e+1]`); lags are taken relative to the target day with offsets ≥ H (matched) or ≥ gap (fresh); the unit tests overwrite everything after the cutoff and require identical forecasts for 16 estimators in both information sets, at both H. The v1 baselines (a subset) were independently re-implemented from raw data in the v1 audit and matched row by row. | tests; v1 audit step 1 |
| 8 | Does any test result influence feature selection, model choice, stopping or thresholds? | **No.** There are no thresholds; early stopping is not used (fixed number of trees); the test stage fits only the prespecified configurations. The only post-selection look at test data is the analysis. | protocol §5, §12 |
| 9 | Customer-level splits (classification thread)? | The classification thread is **not** part of this study's confirmatory plan (separate exploratory report); the v1 audit documents its overlap and chronology. | `exploratory/INACTIVITY_REPORT.md` |

## 2. Leakage risks and exposure (all disclosed, none eliminated)

1. **Historical exposure to W1 results.** W1 was scored repeatedly (benchmark, v1, E1, ablations, S2, audit); the new candidate list reflects what was learned there. W1 is therefore never confirmatory (`WINDOW_USE_AUDIT.md`).
2. **Period-level exposure of W2/W3.** Their periods served as training rows in v1 and as descriptive statistics and in an in-sample price regression; a retired benchmark scored a disjoint set of 40 M5 series over days 1,649–1,940 and validated on 1,358–1,648. No evaluated entity's W2/W3 target was scored.
3. **Pre-freeze smoke runs in v1** saw some W1 test outputs (disclosed in the v1 audit); not relevant to W2/W3.
4. **Price-listing eligibility** (data audit §4): an assumption about ex-ante knowledge; identical across methods.
5. **M5 sample eligibility** uses first-sale ≤ d_1100 (information before every window).
6. **Online Retail II SKU selection** uses revenue before the first validation block of each window only (tested).
7. **Randomness shared across windows:** the same M5 series draw is used in all windows (by design; entity-level overlap between windows is a dependence that the replication analysis cannot remove).
8. **LightGBM determinism:** `deterministic=True, force_row_wise=True`; XGBoost `hist` with fixed seed; results may still differ across thread counts and library versions in the last digits.

## 3. Residual items to verify after the run

Selection-before-test file order per cell (`results.json: test_fits_after_selection`); independent recomputation of baselines and metrics from raw data (`verify_independent.py`); perturbation test on the final feature tensors of every cell (`leakage_checks` in `selection.json`).
