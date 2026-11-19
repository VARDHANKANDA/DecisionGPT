# India E-Commerce Customer Behaviour — SIMULATED  (`SYNTHETIC_INDIAN_CONTEXT`)

**Status: ACTIVE — standalone benchmark only.** The Kaggle page states the
25,000 rows were *"generated to simulate realistic online shopping behavior in
the Indian market"* → **this is simulated data**, classified
`SYNTHETIC_INDIAN_CONTEXT`. Its metrics are **never** combined with real results.

| | |
|---|---|
| Source | Kaggle `kundanbedmutha/indian-e-commerce-customer-behavior-and-purchase` |
| URL | https://www.kaggle.com/datasets/kundanbedmutha/indian-e-commerce-customer-behavior-and-purchase |
| Acquisition | Kaggle **public anonymous** endpoint (CC BY 4.0 — no login, no token) |
| Licence | **CC BY 4.0** |
| `data_type` | **synthetic** (explicitly generated) |
| Date range | visit_date 2024-01-01 .. 2024-12-30 |
| Size | 25,000 sessions × 29 columns |

## Task: purchase prediction (binary `purchased`, 22.5% positive)
Features (pre-decision only): unit_price, quantity, discount_percent/amount,
pages_viewed, time_on_site_sec, added_to_cart, device_type, user_type,
marketing_channel, product_category, visit_month/weekday/season.

**Excluded as leakage:** `revenue`/`revenue_normalized` (non-zero iff purchased),
`cart_abandoned` (near-complement of the target — **not** churn), `rating` /
`review_*` (post-purchase), identifiers / raw date.

## Benchmark
`scripts/run_india_customer_benchmark.py` — standalone sklearn
(logistic / RF / xgboost), stratified 75/25, seed 42. **Not registered as an
`MLModel`; not wired into the Training Center** → zero risk to production
models. Results: `benchmark_results.json`.

## Limitations
Simulated; categorical columns are integer-coded with no decode map;
default-threshold precision/recall are poor (class imbalance) — **ROC-AUC
(~0.75) is the informative metric**.

## Not supported
Churn (no target); real-world customer analytics; training/influencing any
production model.
