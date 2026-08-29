# India E-Commerce Orders (Benroshan)  (`INDIA_REAL_BUSINESS`)

**Status: ACTIVE.** Small real Indian e-commerce order dataset.

| | |
|---|---|
| Source | Kaggle `benroshan/ecommerce-data` — "Sales details from Indian e-commerce website" |
| URL | https://www.kaggle.com/datasets/benroshan/ecommerce-data |
| Acquisition | Kaggle **public anonymous** dataset-download endpoint (CC0 — no login, no token) |
| Licence | **CC0: Public Domain** |
| Geography | India, 19 states · `data_type: real` |
| **Provenance** | **UNVERIFIED** — uploader: *"received from my University, original author unknown"* |
| Date range | 2018-04-01 .. 2019-03-31 (12 months) |
| Size | ~500 orders / 1500 line items / 36 monthly targets |

## Fields
**Present:** order id/date, customer name, state, city, category, sub-category,
quantity, `Amount` (= line revenue INR), profit, monthly category target.
**Absent (never invented):** unit price, discount, ship date, marketing,
inventory, customer id, churn label.

## Processed outputs (`scripts/build_external_datasets.py --only benroshan`)
| File | Grain | Rows |
|---|---|---|
| `india_ecommerce_analytics.csv` | category × state | 57 |
| `india_ecommerce_target_attainment.csv` | category × month vs Target | 36 |
| `india_ecommerce_forecasting.csv` | daily total units (1 zero-filled series) | 365 |

`price` in the forecasting frame is a **DERIVED** implied unit price (daily
revenue ÷ daily units, ffilled); `marketing_spend`/`promotion_flag` = 0.

## Supported / not supported
- **Supported:** sales / profit-margin / geographic analytics, target-attainment,
  a **small** forecasting benchmark.
- **Not:** discount analysis (no field), unit-price/elasticity pricing, churn /
  customer analytics, causal evaluation, large-scale forecasting.

## Limitations
Provenance unverified; small (~500 orders, 3 categories, 1 year); profit values
volatile; forecasting series is small & high-variance (analytics is the primary use).
