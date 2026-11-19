# PROTOCOL_V3 — fresh-window evaluation with classical statistical baselines (forecast_study_v3)

Status: written 2026-10-22 **before** any modelling, scoring or inspection of the outcome data of the three evaluation stores. Internal timestamped hash freeze (`FREEZE3.json`), **not** a public pre-registration. This is a separately versioned study: it does **not** modify, extend or pool with `forecast_study_v2`, whose results, freeze and manuscript stay as they are.

## 1. Why this study exists

The v2 audit (`research/forecast_study_v2/quality_gate/`) found that the claim "the learned model beats the best simple baseline" rests on 31 prespecified simple baselines and no classical statistical competitors (ETS, ARIMA, Theta), and that all v2 windows have been examined. This study asks, on data whose targets no experiment has scored: **does the item-day advantage of the validation-selected learned model persist when ETS, ARIMA and Theta are added to the baseline set?** It does not search for new models.

## 2. Evaluation data (fresh at the entity level and at the period level)

* **Dataset:** M5 Forecasting–Accuracy (Kaggle; non-commercial/academic use; no redistribution — nothing derived from it is to be published).
* **Stores:** CA_2, TX_2, WI_2 — the lowest-numbered store of each state not used as an evaluated entity by any earlier experiment (v1, v2, historical benchmarks). Checked in the repository (`WINDOW_USE_AUDIT.md`, grep of all code/results for these store ids): only the retired Training Center benchmark touched 10 series in these stores (CA_2 3, TX_2 5, WI_2 2), as training/validation/test data on the periods before and after the study window; those 40 series (all stores) are **excluded** here.
* **Window W4:** 756 trailing days removed (T′ = 1,185). Validation blocks start at day 933 (0-based; 2013-08-19), six 28-day test blocks end at day 1,184 (2014-04-27). Disjoint from v2's W1, W2, W3 (W3 starts at day 1,185). The period's targets were never scored for any entity in the repository (they served only as training rows in v1/v2 fits of other windows and in the retired benchmark).
* **Series:** 350 department-stratified random series per store (seed 20261022 fixed here), among series whose first non-zero sale is on or before day 848 (= first validation day 933 − 85, the same margin as v2's W3 rule) and which are not among the 40 retired-benchmark series. The v2 rule "first sale ≤ day 1100" would have used information from inside W4's validation/test period and is therefore **not** reused.
* **Rows, features, eligibility, targets:** exactly as v2 (direct forecasts of daily units, minimum lag H ∈ {28, 7}, global models refit per block on target days in [o − 730, o − 1], eligibility = a listed selling price on the target day and ≥ 84 days of history).
* **Disclosure of data access before the freeze:** the loader unit test read the full sales arrays of CA_2 (no model, no score, nothing inspected). A timing pilot of the statistical models used only CA_1 W1 data (already scored in v1).

## 3. Models and baselines

* **Learned candidates:** the eight v2 candidates unchanged (LightGBM Tweedie 1.1/1.5, L2, L1, L1-small, quantile 0.5; XGBoost L1; ridge); same base hyper-parameters; no tuning; reference model = LightGBM Tweedie 1.1; seed 42, extra seeds 43, 44 for the item-day-selected model.
* **Baselines:** the 31 v2 baselines (16 estimators × matched/fresh; all-zero once) **plus six statistical baselines** from Nixtla `statsforecast` 2.1.1 (separate environment, `requirements_stats.txt`): `AutoETS(season_length=7)`, `AutoARIMA(season_length=7, approximation=True, max_p=2, max_q=2, max_P=1, max_Q=1, max_d=1, max_D=1, nmodels=40)`, `AutoTheta(season_length=7)`, each as `matched__<m>` and `fresh__<m>` (37 baselines in total). Each model sees the last 730 days of the series' history; forecasts are clipped at 0; a series whose fit fails or whose forecast is not finite receives the mean of its last 91 observed days (counted and reported per block).
* **Statistical information sets (differences from the simple baselines, declared):**
  `matched<H>`: fitted once per 28-day block on history through day o − H, forecast horizons H … H + 27 — never fresher than the learned models for any target day and *staler* for later days of the block (a handicap to the local models, because refitting every day is not feasible);
  `fresh`: fitted once per block on history through day o − 1, horizons 1 … 28 — at H = 7 this is **staler than the simple fresh baselines, which are refreshed weekly** (v2 definition), i.e. the comparison with the "any information" set favours the simple baselines.
* Model selection, baseline selection (lowest mean validation WAPE of the endpoint over the three validation blocks; ties by name), validation-only, exactly as v2; `matched` baselines for H1/H3, any information set for H1b.

## 4. Hypotheses, decision rule and inference (identical to v2's frozen rules)

Confirmatory family: 3 stores × H ∈ {28, 7} = **6 cells**, window W4 only. Holm correction within each hypothesis family across the 6 cells.

| id | comparison | role |
|---|---|---|
| H1 | item-day-selected model vs best matched baseline of the **expanded** set (matched among the 31 + matched ETS/ARIMA/Theta), pooled item-day WAPE | **primary** |
| H1b | the same vs the best baseline of **any** information set of the expanded set | secondary |
| H2 | the same model vs the Tweedie 1.1 reference model | secondary |
| H3 | subset-day-selected model vs best matched baseline of the expanded set, subset-day WAPE | secondary |
| H1-orig, H3-orig | H1/H3 against the best matched baseline of the original 31 only (selected on validation) | secondary, for continuity with v2 |

Verdict per cell: SUPPORTED iff Holm p < 0.05 **and** the 95 % interval excludes 0 **and** improvement ≥ 2 % **and** the model wins ≥ 4 of 6 test blocks; CONTRADICTED iff the interval lies below 0; otherwise INCONCLUSIVE. Dual-method rule: the verdict stands only if the secondary method gives the same verdict with its own Holm adjustment, otherwise INCONCLUSIVE. Item-day: paired crossed (series × 7-day block) bootstrap, B = 10,000, seed 20261024 (primary); two-way cluster-robust delta method, t(G − 1) (secondary). Subset-day: iid-week bootstrap (primary), stationary bootstrap with mean block 3 weeks (secondary). **Rules are not changed after outcomes are seen.**

**Declared robustness reports (do not change any verdict):** (a) H1 recomputed with weeks resampled in stationary blocks (mean 3 weeks) and the lag-1 autocorrelation of the weekly differences; (b) descriptive item-day WAPE of every statistical baseline and of the best simple baseline; (c) seed sensitivity (seeds 43, 44).

## 5. Interpretation rules (stated before outcomes)

* H1 supported in ≥ 5 of 6 cells → "on fresh data the item-day advantage persists against the expanded baseline set (these stores, this window)". 3–4 cells → mixed. ≤ 2 cells → "not replicated".
* If a statistical baseline is the best matched baseline in a cell it is reported as such; no cell is excluded or re-run.
* If the H1-orig result differs from the H1 result, the difference is attributed to the statistical baselines and reported as such.
* Results are reported whatever they are; they are a **separate confirmatory family** that is never merged into the v2 counts.
* Stopping/failure rules: a failed stage is re-run unchanged; if a configuration change is unavoidable it is logged in `DEVIATIONS_V3.md` with its reason before any outcome is read; no outcome-dependent change is permitted.

## 6. Procedure (order enforced by `run_v3.sh` and the pipeline)

1. Freeze (`freeze3 create`). 2. `prep` (series arrays and block definitions only). 3. `statval` (statistical forecasts for the three validation blocks). 4. `validation` (learned models and all 37 baselines on the validation blocks → `selection.json`). 5. `stattest` (statistical forecasts for the test blocks; refuses to run unless `selection.json` exists). 6. `test` (v2 pipeline; verifies both freezes; fits only the selected models and the reference). 7. `analysis`.

## 7. Environment and reproducibility

Learned models: the pinned v2 environment (Python 3.12.0, numpy 2.5.2, pandas 3.0.5, scikit-learn 1.9.0, lightgbm 4.7.0, xgboost 3.4.0). Statistical baselines: a separate environment (`requirements_stats.txt`; pandas 2.3.3 there, numpy arrays cross the boundary). Seeds and configs are stored with every cell. Expected compute: statistical baselines ≈ 28,000 series-block fits per model per store (measured pilot ≈ 0.4 s ETS/Theta, ≈ 1 s ARIMA per series-origin under load), learned models ≈ 10–20 min per cell pair. Raw M5 data and sales-bearing arrays are not to be shared.

## 8. Limitations declared in advance

Three stores of one retailer and one period; same candidate models as v2 (no tuning, no neural or probabilistic models); statistical models fitted once per block with the information handicaps of §3; ARIMA search restricted for compute (`nmodels=40`, small order caps); WAPE endpoints only; the design is informed by the v2 results; same-agent development and verification (no external validation).

## 9. Pre-freeze activity (see `DEVIATIONS_V3.md`)

A plumbing dry run of the full chain (prep → statistical validation forecasts → validation → statistical test forecasts → test) was executed on CA_1, window W1 (already scored in v1), with Theta only, into a scratch directory; it completed and produced finite statistical baselines inside `predictions.npz`, a `selection.json` that contains them, and `test_fits_after_selection = true`. An earlier, mistaken attempt touched CA_1 on the W4 period (not an evaluated store), was stopped before any model fit or score, and its outputs were never opened. Timing pilots used CA_1 W1 data. No data of CA_2, TX_2 or WI_2 was modelled, scored or inspected before this freeze (the loader unit test read the CA_2 sales array only to check the eligibility rule).
