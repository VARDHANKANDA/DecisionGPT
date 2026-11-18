# Production ML roadmap

> **Update 2026-10-15 (outcome tracking):** expectations, owner responses and observed outcomes are now recorded and compared under explicit
> rules; see `docs/BUSINESS_OUTCOME_TRACKING.md`. No model is retrained or promoted from outcomes.

> **Update 2026-10-15 (validation phase):** evidence levels, the per-capability requirements and the real-data validation workflow are in
> `docs/REAL_WORLD_VALIDATION_PLAN.md`. Added: reproducible forecast and customer-score validation reports, artifact hashes, one price gate.

> **Update 2026-10-15 (second pass):** the business forecast no longer uses the synthetic-trained models, applicability is recorded and
> enforced, price options the data cannot support are withheld, and interval reliability is verified on held-out origins. See
> `docs/BUSINESS_FORECASTING.md` for previous vs new behaviour. Findings F3, F4 and F6 below are updated in section 8.

Written 2026-10-15 from a read-only audit of the working tree (HEAD `41c1d14` + uncommitted changes). Evidence is the code and the stored
registry/DB state, not the earlier reports. **No production model selection was changed during the audit.** The "Status" column in
section 7 is updated as stages land.

## 1. Production versus research-only

| Capability | Production (reachable from the API/UI) | Research-only (not reachable from SME endpoints) |
|---|---|---|
| Sales forecast | `forecast_service.forecast_sales` → one registered model chosen by `select_forecast_model` among `sales_forecast_{naive,linear,xgboost}`; currently **XGBoost v1** (lowest recorded test MAE 15.14) | `ml/benchmark`: Ridge, Random Forest, HistGradientBoosting, LightGBM, CatBoost, ensembles, M5 / Online Retail II runs |
| Churn | `churn_service.predict_churn` → one of `churn_{logistic_regression,random_forest,xgboost}`; currently **logistic regression v1** (ROC-AUC 0.7978) | CatBoost, soft voting, stacking, calibrators, inactivity proxy on Online Retail II |
| Digital Twin / decisions | `digital_twin_service.simulate_strategy` runs the **same registered forecaster twice** (baseline vs scenario); fixed-formula agents and optimiser (`backend/app/agents/*`, `decision_service.analyze_goal`) | R1 constant-elasticity simulation (`backend/app/evaluation/r1`), upgraded harness, oracle/greedy/SLSQP baselines |
| Chat analytics | OpenAI classification → deterministic query engine → verified facts; optional validated restatement | – |
| Preprocessing | SME: `data_ingestion_service` / `data_platform_service` (profile, clean, validate, transform); research: `research_preprocessing_service` (config, row counts, per-step records, input/output checksums) | `ml/benchmark/datasets.py` cleaning rules for public data |

## 2. Models behind each live endpoint

| Endpoint | Model resolved at request time | Artifact | Recorded metrics (all on **synthetic** training data) |
|---|---|---|---|
| `POST /businesses/{id}/analytics/forecast` | `select_forecast_model` → `sales_forecast_xgboost` v1 | `models/sales_forecast_xgboost/v1/model.joblib` | MAE 15.14, RMSE 21.86, MAPE 10.3 (platform series, units per series-day) |
| `POST /businesses/{id}/analytics/churn` | `select_best_model` over 3 candidates → `churn_logistic_regression` v1 | `models/churn_logistic_regression/v1/model.joblib` | ROC-AUC 0.7978, F1 0.669 (label is a synthetic logistic draw) |
| `POST /businesses/{id}/digital-twin/simulate`, `POST …/decisions/analyze` | the forecaster above, twice | same | same; price response ±0.04%, unsigned (see `ML_BENCHMARK_REPORT.md` §6) |
| `GET …/explain`, SHAP | tree models only (XGBoost) | same | – |

State in `backend/dev.db` (`models` table): v1 **active** for all six names; v2 **archived** for linear / naive / xgboost (Training Center runs on an
uploaded file, MAPE 110–276%). `models/registry_index.jsonl` has six v1 lines. An unregistered `models/sales_forecast_xgboost/v2/` directory
exists with MAE 0.0 (a degenerate fit on an upload), not used.

## 3. Data dependencies and feature availability at inference

* **Forecast features** (`ml/features/forecasting_features.FEATURE_COLUMNS`, 10): `lag_1, lag_7, rolling_mean_7, rolling_mean_28, day_of_week,
  is_weekend, month, price, marketing_spend, promotion_flag`. At inference they come from `forecast_service.build_feature_row`
  (`promotion_flag` is **hard-coded 0**; `price` is the business-wide mean realised price per unit = revenue / units; `marketing_spend` is a
  7-day mean of campaign spend, 0 when none).
* **Churn features** (7): `tenure_days, recency_days, frequency, avg_order_value, monetary_value, purchase_rate_per_year, recency_ratio`; built
  by the shared `build_churn_features` from `customers` rows (needs ≥ 30 customers with first/last purchase date, frequency, monetary value).
* **Sufficiency gates:** forecast needs ≥ 35 calendar days and ≥ 20 days with sales; churn ≥ 30 complete customers.

## 4. Findings (verified in the code)

| # | Finding | Evidence | User impact | Likelihood |
|---|---|---|---|---|
| F1 | **Training commands can silently become production.** `sync_from_file_registry` marks the *last index line of every name as `active` and archives the rest*; no validation, no record of who/why, no rollback. | `model_registry_service.sync_from_file_registry` | A bad or synthetic-only retrain replaces the live model | High |
| F2 | **Trainers overwrite version `v1`** (hard-coded) and write `model.joblib` non-atomically; the index is append-only with duplicate entries. | `train_forecasting.run`, `train_churn.run`, `registry.save_model_artifact` | Interrupted or repeated training can corrupt or replace the active artifact; history is lost | Medium |
| F3 | **Train/serve domain mismatch.** The forecaster is trained on per-series synthetic units (mean 128/day) but applied to a business's *total* daily units (typically ~10/day) and an averaged price. | probes in `ML_BENCHMARK_REPORT.md` §6; `build_daily_series` | Out-of-range inputs; numbers are not calibrated to the business | High |
| F4 | **Forecast interval is not statistically justified.** ±1.28 × the model's synthetic *test RMSE*, constant over the horizon, regardless of the business's scale or recursion depth. The response also returns the synthetic model's own test metrics. | `forecast_sales`, `run_recursive_forecast` | Users read a precise-looking band that has no coverage guarantee | High |
| F5 | **No staleness or horizon guard.** `horizon_days` is an unbounded query parameter; no check that the last observation is recent. | `post_forecast` | Resource abuse; confident forecasts from old data | Medium |
| F6 | **Price scenarios are not identified.** The model's price response is unsigned and tiny; decisions can still select a price change. A limitation note was added to simulations, but a decision does not carry it. | P1 run, `digital_twin_service` | A price action may be recommended without support | High |
| F7 | **Churn provenance is invisible.** The response field is `churn_probability` and the metrics are the synthetic model's; the UI/API do not say the label is synthetic or what "churn" means. | `ChurnResultOut`, `predict_churn` | Users may take the number as a calibrated real-world probability | High |
| F8 | **No upload size or row limits.** `await file.read()` loads the whole file; no per-tenant cap. | `endpoints/data.py` | Memory exhaustion / slow requests | Medium |
| F9 | **Feature parity is assumed, not tested.** Training and inference share `FEATURE_COLUMNS` but there is no runtime contract (names, order, dtype, NaN) and no parity test. | `forecast_service.build_feature_row` vs `build_forecasting_features` | A silent change in either breaks predictions | Medium |
| F10 | **Model is reloaded on every request** (`joblib.load` per call) and `build_daily_series` is recomputed in the same request by several paths. | `load_model`, `_load_model`, `forecast_sales` | Latency; memory churn under concurrency | Medium |
| F11 | Duplicated selection logic existed between forecast and Digital Twin; **fixed** in the previous task (`select_forecast_model`). | – | – | – |
| F12 | Dependency drift: `requirements.txt` pins pandas 2.2.3 / scikit-learn 1.5.2 but the venv has 3.0.5 / 1.9.0; registry pickles were written under 1.5.2. | `pip` vs requirements | Unpickle warnings; reproducibility | Medium |
| F13 | The test suite writes `experiments/results/*.json` as a side effect. | `train_*.run` called by tests | Result-directory pollution | Low |
| F14 | Missing days in the sales table are filled with **0 units** (retail: no sale = 0 is usually right, but a gap in the upload is not a zero). | `build_daily_series` | Under-forecast after upload gaps | Medium |

## 5. What is solid already
Tenant scoping on every business endpoint (tested), provider kill switches and network isolation, the deterministic analytics engine with
validated explanations, WAPE and validation metrics in the trainers, registry selection on validation metrics when present, the research
preprocessing run record (config, rows in/out, checksums), historical-artifact hash pinning.

## 6. Principles for the staged work
Smallest change that fixes the finding; backward compatible (existing manifests, index and DB rows keep working); new training runs create
**new versions**; promotion is explicit and recorded; unsupported cases return an explicit limitation rather than a number; every stage
ships with tests and a recorded exit code.

## 7. Staged plan and status (updated 2026-10-15 after implementation)

| Stage | Scope | Findings | Status |
|---|---|---|---|
| A | This roadmap | – | **done** |
| B | Safe model lifecycle: immutable versions, atomic writes, candidate → validated → active, automated checks, recorded promotion, rollback (`docs/MODEL_LIFECYCLE.md`, migration 0010) | F1, F2 | **done** (18 tests + 2 API) |
| C | Feature contract and parity test; horizon bound; staleness / short-history / scale / synthetic-training warnings; empirical back-tested interval or an explicit "not calibrated" flag; churn provenance and score meaning | F3, F4, F5, F7, F9, F14 | **done** for the registered models (10 + 14 tests) |
| D | Decision safeguard: the price-identification result is attached to any decision whose selected option changes price; no score, ranking or confidence changed | F6 | **done** as annotation; the underlying price response is still not identified (needs real price variation) |
| E | Upload size / row limits with plain-language failures; request bodies read with a bound | F8 | **done**. The wider "versioned processed outputs for tenant data" is covered by existing run records (data_prep_runs, research preprocessing records), not rebuilt |
| F | Observability: sanitised request id, processing-time header, access log without query/body; model/data version and warnings on forecast and churn responses; UI shows limits | – | **done** |
| G | Performance: measured model load 1–66 ms and a back-tested forecast request 0.4–0.8 s | F10 | **measured, no change**: caching was not justified. A cache would have to be keyed by (name, version, file mtime) and cleared on promotion/rollback (the hook exists) |
| H | Regression suite and operational validation | all | see the final report for exit codes |

Resolved findings: F1, F2, F4 (interval is empirical or flagged), F5, F7, F8, F9, F11, F13. Mitigated, not solved: F3 (warned, not fixed:
the model is still trained on per-series synthetic units), F6 (flagged), F14 (visible in warnings), F12 (versions recorded per run).
Open: a model trained on real business data is the only fix for F3/F6; F10 only if load grows.

Not planned (no measured product requirement): new algorithms, promoting CatBoost/LightGBM/ensembles, retraining production models on
synthetic data.


## 8. Second pass: forecasting scale mismatch, applicability and price decisions

| Finding | Previous behaviour | New behaviour | Status |
|---|---|---|---|
| F3 scale mismatch | the synthetic XGBoost forecaster (mean 128 units per series-day) forecast a business's total daily units | the forecast is built from the business's own history; a registered model enters only if its recorded applicability says it was trained for that business's daily totals (none is) | **fixed** for `/analytics/forecast`, the assistant, reports and architecture A |
| F4 interval | constant ±1.28 × synthetic test RMSE, later an unverified empirical band | empirical band from the business's backtest, coverage verified on holdout origins, otherwise "indicative"; limited estimates use a labelled heuristic | **fixed** |
| F6 price decisions | price options could be ranked and recommended; What-If showed a price effect | withheld (not simulated or ranked) in production decisions and What-If when unidentified; research runs unchanged | **fixed** for the product paths |
| Applicability | none | recorded at training; inferred (and labelled) for legacy models; checked by lifecycle validation | **new** |
| Bootstrap v1 models | shown as active, indistinguishable from validated | `validation_status = not_validated_bootstrap`, "not eligible for business use" | **labelled** |
| Data readiness | upload checks only | `GET /data/forecast-readiness` | **new** |

Still open: the Digital Twin's marketing/inventory scenario effects come from the registered synthetic model (flagged, not business-validated);
no business-specific learned model exists (needs ≥ 180 days per business and recorded outcomes); churn is a synthetic-label score.
