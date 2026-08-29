# Indian Dataset Evaluation

Evaluation of the candidate datasets. **All were downloaded and inspected
directly** — Kaggle's public dataset-download endpoint serves CC0 / CC-BY
datasets to anonymous clients (no login, no API token, no ToS bypass). The
GitHub repo was inspected via raw URLs.

## Summary table

| Dataset | Geography | Real / Synthetic | Rows | Date | Sales | Qty | Unit price | Profit | Customer | License | SME relevance | **Decision** |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **Benroshan e-commerce** (`benroshan/ecommerce-data`) | India (19 states) | **Real** (provenance unverified) | 500 orders / 1500 lines | 2018-04 → 2019-03 | ✅ `Amount` | ✅ | ❌ (derive from Amount/Qty) | ✅ | name only | **CC0** | High (small) | **INTEGRATE — `INDIA_REAL_BUSINESS` (primary real)** |
| **Kundan customer behaviour** (`kundanbedmutha/...`) | India (coded) | **Synthetic** ("generated to simulate") | 25,000 sessions | 2024 | ✅ `revenue` (leaky) | ✅ | ✅ | ❌ | session-level | **CC BY 4.0** | Medium (synthetic) | **INTEGRATE — `SYNTHETIC_INDIAN_CONTEXT`, standalone purchase-prediction benchmark only** |
| **Winston Bobby "Indian Retail Sales"** (`winstonbobby/indian-retail-sales`) | India (labels) | **Synthetic / templated** | 2,534 | 2010-2013 | ✅ | ✅ | ✅ | ❌ | segment only | CC0 | Low | **REJECT** — verbatim Tableau *Global Superstore* template (Order Priority / Ship Mode / Freight / "Processed Meat" product line, "Hotels / Hospitals" segments). Not real Indian retail. |
| **Abu Humza Khan "Store Data"** (`abuhumzakhan/store-data`) | India (`Country=India`) | **Synthetic / generated** | 100,000 | 2019-2023 | ✅ | ✅ | ❌ | ✅ | Faker names | CC0 | Low | **REJECT** — Faker Western names ("Curtis Krause"), sequential `CUST00001` / `ORD00001` / `PROD00001` IDs, templated product names ("Burgers - 718"), 61% of `Sales Date` unparseable. Volume ≠ authenticity. |
| **Maulik Gajera "UPI Transactions India"** (`maulikgajera/upi-payment-transactions-india`) | India | **Synthetic** ("simulates", "fraud labels generated via a probabilistic model") | 20,000 txns | 2024 | payment amount | — | — | — | user/merchant (synthetic) | CC0 | Context-only | **REJECT for training; catalog as context** — synthetic **and** must remain context-only per the brief. Not integrated as a dataset; noted as a digital-payments context reference. |

The GitHub repo `AtharvaZalkikar/indian-ecommerce-sales-analysis/data` contains
`List of Orders.csv` + `Order Details.csv` + derived `merged_orders*.csv` — it
is a **mirror of the Benroshan dataset** plus that author's own joins. We use
the **original Benroshan files** (which also include `Sales target.csv`, absent
from the mirror). Provenance preserved: Kaggle `benroshan/ecommerce-data`, CC0.

## 1–5 scores

| Criterion | Benroshan | Kundan | Winston Bobby | Store Data | UPI |
|---|---:|---:|---:|---:|---:|
| Indian relevance | 4 | 3 | 2 | 2 | 3 |
| SME relevance | 4 | 3 | 2 | 2 | 1 |
| Transaction richness | 3 | 3 | 4 | 4 | 2 |
| Temporal richness | 2 | 3 | 4 | 4 | 3 |
| Forecasting usefulness | 2 | 1 | 4 | 3 | 1 |
| Pricing usefulness | 2 | 3 | 4 | 2 | 1 |
| Profit usefulness | 4 | 1 | 4 | 4 | 1 |
| Customer usefulness | 2 | 4 | 1 | 2 | 2 |
| Digital-Twin usefulness | 3 | 2 | 3 | 2 | 1 |
| Research reproducibility | 4 | 4 | 4 | 3 | 3 |
| Provenance | 2 | 3 | 3 | 2 | 3 |
| Licensing | 5 | 5 | 5 | 5 | 5 |
| **Weighted decision** | **Integrate (real, primary)** | **Integrate (synthetic, customer)** | Reject (templated) | Reject (generated) | Reject (synthetic, context-only) |

Benroshan scores lower on temporal/forecasting richness than the synthetic
candidates but is the **only one that is plausibly a real Indian business
extract**. Per the brief ("Do not select a dataset merely because it has many
rows"; "If a Kaggle dataset claims to be realistic but is actually generated,
classify it as synthetic"), Store Data and Winston Bobby are rejected despite
their size and field richness.

## Selected combination

| Role | Dataset | Category |
|---|---|---|
| **Primary Indian business dataset** | Benroshan e-commerce | `INDIA_REAL_BUSINESS` |
| **Secondary Indian business dataset** | *(none)* — Winston Bobby and Store Data are synthetic/templated; documented, not integrated | — |
| **Customer dataset** | Kundan customer behaviour | `SYNTHETIC_INDIAN_CONTEXT` (standalone purchase-prediction benchmark) |
| **Context dataset (UPI)** | Not integrated | referenced as synthetic digital-payments context only |
| **Agricultural price** | AGMARKNET (unchanged) | `INDIA_AGRICULTURAL_PRICE` (`DATA_PENDING`) |
| **Controlled synthetic** | `platform-*` (unchanged) | `SYNTHETIC_CONTROLLED` |

## Benchmark results

### Benroshan e-commerce forecasting (seed 42, daily total units, 51 test days)
| Model | MAE | RMSE |
|---|---:|---:|
| naive | 19.92 | 31.25 |
| linear | 18.47 | 28.51 |
| xgboost | **15.27** | **23.89** |

All three models registered as `experimental`; the 6 active production models
were unchanged (asserted). **Small dataset — indicative only.** MAPE omitted
(many zero-sales days).

### Kundan purchase prediction (seed 42, standalone, 6,250 test rows, 22.5% positive)
| Model | Precision | Recall | F1 | ROC-AUC |
|---|---:|---:|---:|---:|
| logistic_regression | 0.00 | 0.00 | 0.00 | **0.760** |
| random_forest | 0.38 | 0.06 | 0.11 | 0.744 |
| xgboost | 0.36 | 0.01 | 0.02 | 0.757 |

ROC-AUC ≈ 0.75 (real ranking signal); default-threshold precision/recall are
poor due to class imbalance. **Synthetic data — reported under
`SYNTHETIC_INDIAN_CONTEXT`, never combined with real results.** Not registered
as an `MLModel`.

## Limitations

- **Benroshan provenance is unverified** (uploader: "received from my
  university, original author unknown"). No strong population claims.
- Benroshan is small (~500 orders, 3 categories, 1 year) — analytics-primary;
  the forecasting benchmark is small and high-variance.
- Benroshan has **no unit price / discount / ship date** — pricing scenarios
  are limited; discount analysis is unavailable.
- Kundan is **simulated**; its categorical columns are integer-coded with no
  decode map; `cart_abandoned` is **not** churn.
- No genuine large-scale real Indian retail **transaction** dataset with full
  field richness was found under an open licence — the strong-field candidates
  are templated/generated.
