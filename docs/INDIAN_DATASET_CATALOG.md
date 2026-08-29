# Indian Dataset Catalog

Every dataset DecisionGPT uses, by category. Non-Indian datasets are **retired**
and shown only for completeness. See `docs/INDIAN_SME_DATA_ARCHITECTURE.md` for
how the layers fit together, `docs/INDIAN_DATASET_EVALUATION.md` for the
candidate scoring, and `docs/FINAL_DATASET_INVENTORY.md` for the one-line
status table.

---

## INDIA_REAL_BUSINESS

### India E-Commerce Orders (Benroshan)
| | |
|---|---|
| Dataset | `external-india-ecommerce-v1` |
| Source | Kaggle `benroshan/ecommerce-data` — "Sales details from Indian e-commerce website" |
| URL | https://www.kaggle.com/datasets/benroshan/ecommerce-data |
| Acquisition | Kaggle public **anonymous** download endpoint (CC0 — no login/token) |
| License | **CC0: Public Domain** |
| Geography | India, 19 states · `data_type: real` |
| **Provenance** | **UNVERIFIED** — uploader: *"received from my University, original author unknown"* |
| Rows | 500 orders / 1500 line items / 36 monthly targets |
| Date range | 2018-04-01 .. 2019-03-31 |
| Business domain | E-commerce retail (Furniture / Clothing / Electronics) |
| Fields present | order id/date, customer name, state, city, category, sub-category, quantity, `Amount` (line revenue), profit, monthly category target |
| Fields absent (not invented) | unit price, discount, ship date, marketing, inventory, customer id, churn |
| Derived | `price` (forecasting) = daily revenue ÷ daily units, ffilled; `marketing_spend`/`promotion_flag` = 0; `margin_pct`, `avg_order_value`, `attainment_pct` |
| Supported tasks | sales / profit-margin / geographic analytics, target-attainment, **small** forecasting benchmark |
| Unsupported tasks | discount analysis, unit-price/elasticity pricing, churn / customer analytics, causal evaluation, large-scale forecasting |
| Preprocessing | `ml/preprocessing/india_ecommerce_adapter.py` (seed 42): drop blank/dup rows, join orders+lines, dayfirst dates, daily zero-fill, existing chronological split |
| Benchmark | forecasting naive/linear/xgboost via the Training Center (all `experimental`; active models unchanged). xgboost MAE 15.27 vs naive 19.92 on 51 test days — **indicative only** |
| Limitations | provenance unverified; small; volatile profit; forecasting series small/high-variance |
| Paper usage | Table 1 row labelled `INDIA_REAL_BUSINESS`, reported separately from synthetic and from AGMARKNET; primarily descriptive Indian retail analytics |

### Real Indian *transaction* dataset with full field richness — still pending
The candidates with unit-price + discount + ship-date + long history
(`winstonbobby/indian-retail-sales`, `abuhumzakhan/store-data`) are **templated
/ generated** (Global Superstore template; Faker names + sequential IDs) — see
`docs/INDIAN_DATASET_EVALUATION.md`. Rejected rather than mislabelled.

---

## SYNTHETIC_INDIAN_CONTEXT

### India E-Commerce Customer Behaviour (SIMULATED)
| | |
|---|---|
| Dataset | `external-india-customer-synthetic-v1` |
| Source | Kaggle `kundanbedmutha/indian-e-commerce-customer-behavior-and-purchase` |
| URL | https://www.kaggle.com/datasets/kundanbedmutha/indian-e-commerce-customer-behavior-and-purchase |
| Acquisition | Kaggle public **anonymous** download endpoint (CC BY 4.0 — no login/token) |
| License | **CC BY 4.0** |
| `data_type` | **synthetic** — the Kaggle page states the rows were "generated to simulate realistic online shopping behavior" |
| Geography | India (stated; locations integer-coded) · Rows 25,000 · Date visit_date 2024 |
| Task | **purchase prediction** — binary `purchased` (22.5% positive) |
| Features | unit_price, quantity, discount_percent/amount, pages_viewed, time_on_site_sec, added_to_cart, device_type, user_type, marketing_channel, product_category, visit_month/weekday/season |
| Excluded as leakage | `revenue`/`revenue_normalized` (non-zero iff purchased), `cart_abandoned` (near-complement — **not** churn), `rating`/`review_*` (post-purchase), identifiers |
| Preprocessing | `ml/preprocessing/india_customer_adapter.py` (seed 42) |
| Benchmark | `scripts/run_india_customer_benchmark.py` — **standalone** sklearn (logistic/RF/xgboost), stratified 75/25. **Not an `MLModel`, not wired into the Training Center.** ROC-AUC ≈ 0.75; default-threshold P/R poor (imbalance) |
| Unsupported tasks | churn (no target); real-world customer analytics; training/influencing any production model |
| Paper usage | only as a clearly-labelled `SYNTHETIC_INDIAN_CONTEXT` demonstration; never in real-world tables; never averaged with real results |

### UPI Payment Transactions India — not integrated
`maulikgajera/upi-payment-transactions-india` (CC0) is **synthetic** ("simulates
that ecosystem", "fraud labels generated via a probabilistic model") and the
brief requires it stay context-only. Referenced here as a synthetic
digital-payments **context** reference; not registered, not trained.

---

## INDIA_PUBLIC_CONTEXT

### India Festival & Holiday Calendar
| | |
|---|---|
| Dataset | `external-india-festivals-v1` |
| Source | `holidays` Python library (MIT) — India national + state gazetted calendar |
| URL | https://github.com/vacanza/holidays |
| Geography | India (national + TN, KL, KA, MH, WB, GJ, DL, UP) |
| Data type | real (generated offline from a maintained library; version pinned `holidays==0.103`) |
| License | MIT (library); underlying facts are public government notifications |
| Rows | 351 events / 3,287 daily rows |
| Date range | 2019-01-01 .. 2027-12-31 |
| Business domain | Retail / consumer demand seasonality |
| Supported tasks | exogenous seasonality feature for forecasting; demand-seasonality context |
| Unsupported tasks | standalone forecasting target; causal evaluation; any SME-private analysis |
| Preprocessing | `ml/preprocessing/india_festival_adapter.py` — national+8-state union, festival_type by name, offline distance-to-festival features |
| Known limitations | future lunar-festival dates follow the library's projection; 8-state sample; context only |
| Paper usage | optional `INDIA_PUBLIC_CONTEXT` covariate; not a target; not causal evidence |

### India Macroeconomic Context — RBI Policy Repo Rate
| | |
|---|---|
| Dataset | `external-india-macro-v1` |
| Source | Reserve Bank of India — Monetary Policy Committee resolutions |
| URL | https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx |
| Geography | India (national monetary policy) |
| Data type | real |
| License | Government of India public information (attribution expected) |
| Rows | 107 months |
| Date range | 2019-02 .. 2027-12 (monthly, forward-filled) |
| Business domain | Macro context for SME finance / demand |
| Supported tasks | macro-context covariate; finance-scenario context |
| Unsupported tasks | standalone target; causal evaluation; SME-private analysis |
| Preprocessing | `ml/preprocessing/india_macro_adapter.py` — forward-fill repo rate from published change points; MoM change |
| Known limitations | **only the repo rate so far**; CPI / WPI / GDP growth / IIP / fuel price / FX are available from MoSPI / data.gov.in but sit behind the same rate-limited API as AGMARKNET → documented `PENDING`, not fabricated |
| Paper usage | optional `INDIA_PUBLIC_CONTEXT` covariate; observational only |

---

## INDIA_AGRICULTURAL_PRICE

### India Agri-Commodity Daily Market Prices (AGMARKNET)
| | |
|---|---|
| Dataset | `external-india-agmarknet-v1` |
| Source | data.gov.in resource `35985678-0d79-46b4-9ed6-6f13308a1d24` — Directorate of Marketing & Inspection (DMI), Ministry of Agriculture & Farmers Welfare, GoI; system AGMARKNET |
| URL | https://www.data.gov.in/catalog/variety-wise-daily-market-prices-data-commodity |
| Geography | India (multi-state) |
| Data type | real |
| License | **Government Open Data License – India (GODL-India)** |
| Rows | `DATA_PENDING` — curated ~800 daily obs per (commodity × market) series across 8 series |
| Date range | source spans 2006-present |
| Business domain | Agricultural produce market (mandi) **wholesale price** series |
| Supported tasks | **price** forecasting (naive / linear / xgboost); regional price analytics |
| Unsupported tasks | demand/quantity forecasting (no quantity field); churn / customer analytics; causal evaluation; SME-retail representativeness |
| Preprocessing | `ml/preprocessing/india_agmarknet_adapter.py` — canonical `units_sold` slot carries the daily **modal price** (INR/quintal); `price` = 28-day backward rolling median (no leakage); `marketing_spend` / `promotion_flag` = 0 (absent, not invented) |
| Known limitations | wholesale agri prices, **NOT** Indian SME retail transactions; demo API key rate-limited (`DATA_PENDING`); near-random-walk series → strong naive baseline (report MAE/RMSE) |
| Paper usage | supplementary Indian **price-series** benchmark, labelled `INDIA_AGRICULTURAL_PRICE`; never described as SME retail |

**Status: `DATA_PENDING`.** Populate with
`DATA_GOV_IN_API_KEY=<free key> python scripts/download_india_datasets.py`
then `build_external_datasets.py` → `register_external_datasets.py` →
`run_external_benchmarks.py --seed 42`. See
`data/external/india_agmarknet/metadata.md`.

---

## Still pending — a *large, field-rich* real Indian transaction dataset

The integrated Benroshan set (above) is real but **small and field-limited**
(no unit price / discount / ship date, ~500 orders). A large real Indian
transaction dataset with full field richness under an open licence was still
not found:

| Candidate | Blocker |
|---|---|
| `winstonbobby/indian-retail-sales`, `abuhumzakhan/store-data` | field-rich but **templated / Faker-generated** — synthetic, not real (see `INDIAN_DATASET_EVALUATION.md`) |
| "Amazon Sale Report (India)" and similar | Kaggle datasets that are **not CC0/CC-BY** are not anonymously downloadable |
| BigMart Sales | no clearly-licensed public mirror; **no date column** |
| DoCA daily retail prices | SPA-only catalog, not on the generic data.gov.in `/resource/` API |

The **primary** Indian business data source remains the SME's own upload (the
product design). Manual path for adding another dataset:
`docs/DATASET_DOWNLOAD_INSTRUCTIONS.md §2`.

### Business-population context (UDYAM / ASUSE / ASI) — extension points

Aggregate statistical publications, not row-level data:

| Source | Would provide | Integration path |
|---|---|---|
| **UDYAM** (udyamregistration.gov.in) | state × sector MSME registration counts, enterprise-type split | scrape-free download not available; state aggregates could be entered as a small cited context table |
| **ASUSE** (Annual Survey of Unincorporated Sector Enterprises, MoSPI) | unincorporated-enterprise population, employment, GVA by state / activity | published as factsheets/tables; a small cited context CSV is a valid future addition |
| **ASI** (Annual Survey of Industries, MoSPI) | registered-manufacturing inputs / outputs / employment / capital / value added | same |

These are **Tier-3 extension points** — the canonical shape is noted here; no
data is fabricated for them.

---

## SYNTHETIC_CONTROLLED (retained, unchanged)

| Dataset | Purpose |
|---|---|
| `platform-forecasting-v1` | controlled forecasting baseline, known generative process |
| `platform-churn-v1` | controlled churn experiments (**the only churn dataset** — no real Indian churn benchmark exists) |
| synthetic `causal` scenario | causal-graph evaluation with known ground truth (Precision / Recall / F1 / SHD) |
| synthetic decision scenarios | Digital-Twin eval, decision-architecture comparison, ablation study |

---

## RETIRED_NON_INDIAN (not active — reproducibility only)

| Dataset | Geography | Location |
|---|---|---|
| M5 Forecasting | USA | `data/external/_retired_non_indian/m5_forecasting/` |
| UCI Online Retail | UK | `data/external/_retired_non_indian/uci_online_retail/` |
| Supermarket Sales | Myanmar | `data/external/_retired_non_indian/regional_retail/` |

Reproduce with `scripts/*.py --retired`. Never present as representing Indian SMEs.

---

## Tier-3 future SME upload layers (canonical shapes, no data yet)

| Layer | Canonical fields (proposed) | Enables |
|---|---|---|
| Supplier | supplier_id, product_id, lead_time_days, on_time_rate, defect_rate, price | supplier-risk in inventory / procurement decisions |
| HR | period, headcount, attrition_rate, avg_salary, overtime_hours | cost-structure & capacity scenarios |
| Competitor | date, product/category, competitor_price, competitor_promo_flag | price-positioning scenarios |
| Weather | date, temperature, rainfall_mm, humidity, condition | seasonality for weather-sensitive sectors only |
| Customer reviews | date, product_id, rating, review_text | NLP sentiment → product-performance signal |
| UPI / payments | date, method, txn_count, txn_value, failure_rate | payment-mix & cash-flow context |
| Geographic enrichment | pincode/city → tier, population, per-capita income | market-context conditioning |

DecisionGPT must say *"cannot use X because X data was not provided"* rather
than invent any of these.
