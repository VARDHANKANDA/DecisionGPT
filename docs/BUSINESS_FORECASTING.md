# Business forecasting, model applicability and price decisions

Implemented 2026-10-15 (follow-up to `PRODUCTION_ML_ROADMAP.md`). Tests: `tests/unit/test_business_forecast.py`,
`tests/integration/test_forecast_and_churn_guards.py`, `test_digital_twin_price_withholding.py`, `test_decision_price_caution.py`,
`test_model_lifecycle.py`, `test_training_readiness.py`.

## 1. The forecast a business sees
| | Before | Now |
|---|---|---|
| Source | the registered XGBoost/linear/naive model trained on 40 synthetic series (mean 128 units per series-day), applied to the business's total daily units | simple methods fitted **only on the business's own history** (`business_forecast_service`) |
| Target | implicit | explicit: `units_sold` per calendar day, summed over all products (`target`, `target_unit`, `aggregation = business_daily_total` in the response) |
| Method choice | none (one registered model) | rolling-origin backtest on the business's own days; candidates: trailing mean 28 (baseline), trailing median 28, same-weekday mean of 4 weeks, seasonal-naive 7 |
| Seasonal methods | – | considered only with ≥ 8 weeks of history and chosen only if ≥ 5% better than the baseline on the selection origins **and** better on an untouched holdout |
| Interval | ±1.28 × the synthetic model's test RMSE, constant | 80% empirical quantile of the chosen method's own backtest errors per horizon step; coverage **verified on holdout origins** using only the selection origins' errors |
| Reliability flag | `interval_reliable` whenever ≥ 5 origins existed | true only if observed holdout coverage is within ±0.15 of 0.80 on ≥ 20 held-out points; otherwise "indicative" with a warning |
| Little history | forecast anyway | < 14 days or < 7 days with sales: **refused** with the reason; 14–55 days (or too few origins): a **limited estimate** (28-day average, heuristic band, `interval_reliable = false`, `validation.status = not_validated`) |

Measured behaviour of the interval method (synthetic stationary series, 25 runs, horizon 7): mean holdout coverage **0.82** against the 0.80
nominal (min 0.68, max 0.96; flagged reliable in 24 of 25). With a weekly pattern, horizon 14: mean 0.87 (min 0.70; reliable 21 of 25). These
are properties of the method on synthetic data; a real business's own backtest is what the API reports.

Chronology and leakage: origins step back 7 days from the end; the most recent third (min 2) is a holdout never used to select; every
prediction at an origin uses only earlier days (tested by perturbing the future); origins overlap when the horizon exceeds 7 days, so the
backtest errors are dependent and the intervals are approximate (stated in the response).

Paths now using business-specific data: `POST /analytics/forecast`, the assistant's "what will my sales look like" answer, the Forecast
report, and architecture "A". The response keeps `model_name`, `model_version`, `metrics`, `points`; `model_name` is
`business_baseline:<method>`.

## 2. Model applicability
Every model has an applicability record (`lifecycle_json.applicability`, written at training time; older models get an *inferred* record that
says `source = inferred`): provenance, target, target unit, aggregation, population, task and horizon, feature contract, evaluation scope and
eligibility flags (`business_level_forecast`, `price_scenarios`, `customer_scoring`) with reasons.

* A model is used for a business forecast only if it was trained on **that business's** daily totals, from non-synthetic data, and the
  business's recent scale lies inside its training range. Loading successfully is not applicability.
* The registered v1 models are synthetic per-series models: **ineligible** for business forecasts, price scenarios and customer-level
  probabilities. They remain registered and `active` (backward compatibility), are never labelled validated, and the registry shows
  "not validated (first version)" and "not eligible for business use".
* Lifecycle validation now has a blocking `applicability_recorded` check and a non-blocking `eligible_for_production_use` warning.

## 3. Price decisions
* **Decisions endpoint** (`price_response_gate`): when the business's own history cannot identify a price response (< 28 days, < 5
  distinct average prices or < 5% variation), every candidate that changes price is **not simulated, ranked or recommended**; it is listed
  in `skipped_strategies` as withheld, the reasoning says what is needed, and other candidates are scored exactly as before (tested: scores
  unchanged). If every candidate changes price the endpoint refuses with the same explanation (422).
* **What-If endpoint**: a scenario containing a price change returns `price_response = {status: not_identified, withheld: true, needed: [...]}`
  and **no effect figures** (expected units/revenue/profit/range are null); the baseline and the risk indication are kept. When the data
  supports an association the figures are shown, labelled `association_only` and never `reliable`.
* **Research runs** (default `PipelineOptions`) are unchanged so the frozen evaluations remain reproducible; they only annotate.
* Needed to evaluate price changes: ≥ 28 days, ≥ 5 distinct average prices, ≥ 5% variation, ideally a deliberate price test held for weeks.

## 4. Data readiness (`GET /businesses/{id}/data/forecast-readiness`)
Tenant-scoped facts: target and units, date range, zero-sale days and the longest zero run (closure, stockout or upload gap: the data cannot
tell), returns, duplicates, non-positive prices, revenue ≠ quantity × price, possible stockouts from inventory, upload sources, currency
(assumed INR) and time zone (none). `ready_for_forecast` and `ready_for_training` with explicit blockers (≥ 180 days and ≥ 100 days with
sales). It never claims a file is real SME data: provenance is the uploader's statement.

## 5. Remaining limitations
* The Digital Twin still uses the registered synthetic model as its scenario engine for **marketing and inventory** effects; those figures
  carry an explicit "not trained for this business's daily totals" assumption but are not business-validated. The price effect is withheld
  when unidentified; marketing/inventory effects are not yet.
* No model is trained on a business's own data yet; the lifecycle, readiness report and applicability records are what such a model needs.
* Churn scores come from a synthetic-label model (labelled as such); a business-specific churn model needs observed outcomes.

## 6. Validation report on a business's own data (read-only)

`POST /businesses/{id}/validation/forecast/run` (body `{"horizons": [7, 14, 28]}`, 1 to 3 horizons of 1 to 90 days) backtests the product's
forecasting methods on that business's own history and stores the report as an analysis run
(`GET /validation/runs`, `GET /validation/runs/{id}`). It reports, per horizon: MAE, RMSE, WAPE (null with a stated reason when the actual
total is zero), signed and relative bias, holdout comparison against the naive last-value, seasonal-naive and trailing-mean references, the
interval's observed coverage and mean width, the series class (regular, intermittent, sparse), calendar days without sales rows, and the
dataset sha256, configuration, code revision and timestamp. It changes no model. Evidence level: an own-history backtest, not business
impact and not production approval. `POST /validation/customer-scores/run` does the equivalent for the customer score against later
inactivity in the business's own sales (a proxy), at two cutoffs; calibration is explicitly not evaluated.

