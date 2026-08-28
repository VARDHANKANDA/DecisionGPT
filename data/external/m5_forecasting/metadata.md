# M5 Forecasting — dataset card

## What it is
The **M5 Forecasting – Accuracy** competition dataset: **real** daily unit
sales for Walmart, at *item × store* granularity, across 10 stores in
**California, Texas and Wisconsin (USA)**, for **1,941 days** starting
**2011‑01‑29**. Provided with a calendar (events, SNAP days) and weekly
sell‑prices.

- **Series (full):** 30,490 item×store combinations
- **Days (training, `sales_train_evaluation`):** 1,941 (`d_1 … d_1941`)
- **Files:** `calendar.csv`, `sales_train_validation.csv` (`d_1..d_1913`), `sales_train_evaluation.csv` (`d_1..d_1941`), `sales_test_*`, `sell_prices.csv`, `weights_*`

## Source, license, citation
- **Original competition:** M5 Forecasting – Accuracy, University of Nicosia / Makridakis Open Forecasting Center; sales data provided by **Walmart**. Hosted on Kaggle: <https://www.kaggle.com/competitions/m5-forecasting-accuracy>.
- **Kaggle requires** an account and acceptance of the competition rules to download the original files. **This was not bypassed.**
- **Copy used here:** Nixtla's public redistribution `https://github.com/Nixtla/m5-forecasts` (`datasets/m5.zip`), which the MIT‑licensed `datasetsforecast` package uses. Downloaded **2026‑08‑28**. MD5(`m5.zip`) = `333d81b51e52a6f7a20540a2f0f092bf`.
- **License:** the underlying M5 data is Walmart's, released for the M5 competition; its terms are unchanged by redistribution. **Verify the M5 competition terms before redistributing your own copy.** Nixtla's tooling wrapper is MIT.
- **Citation:** Makridakis, S., Spiliotis, E., & Assimakopoulos, V. (2022). *The M5 competition: Background, organization, and implementation.* International Journal of Forecasting, 38(4), 1325–1336.

Raw files live in `raw/` and are **never modified** (gitignored — see `docs/DATASET_DOWNLOAD_INSTRUCTIONS.md` to obtain them).

## Supported DecisionGPT tasks
| Task | Supported | How |
|---|---|---|
| **Forecasting** (benchmark) | ✅ | `ml/preprocessing/m5_adapter.py` → `processed/m5_forecasting.csv` (canonical schema, 40‑series deterministic subsample). |
| Demand‑prediction comparison vs the synthetic baseline | ✅ | Train the same `naive/linear/xgboost` model types via the Training Center; compare in **Model Performance** / **Paper Results Table 1**. |
| Digital Twin (as an *active* SME model) | ➖ | Possible in principle, but any model trained here stays `experimental` and never becomes the active forecasting model, so it does **not** feed the SME Digital Twin. |
| Churn / customer analytics | ❌ | No customer‑level data. |
| Causal / Multi‑Agent / Ablation | ❌ | Not a training dataset for these; those keep their synthetic controlled scenarios. |
| Indian‑context validation | ❌ | US data. |

## Adapter transforms (raw → canonical)
1. Read `sales_train_evaluation.csv` (wide: `d_1 … d_1941`).
2. **Select 40 series** deterministically: the 40 `item_id × store_id` pairs with the highest total units over the full window (tie‑break by id; `seed = 42`).
3. `melt` wide → long: one row per (series, day).
4. Join `calendar.csv` on `d_*` → real `date`, `wm_yr_wk`.
5. Join `sell_prices.csv` on (`store_id`, `item_id`, `wm_yr_wk`) → weekly `sell_price`; **forward/back‑fill within each series** to a daily `price`. Rows before a product's first recorded price are dropped.
6. `series_id = "<item_id>__<store_id>"`, `units_sold = <daily value>`, `price = <daily filled sell_price>`, `marketing_spend = 0`, `promotion_flag = 0`.
7. Trim each series' **leading run of all‑zero sales** (pre‑launch) so lag/rolling features start from real activity.
8. Output columns: exactly `series_id, date, units_sold, price, marketing_spend, promotion_flag` (the forecasting canonical schema).

**No leakage:** the downstream `build_forecasting_features` + `chronological_split`
(unique‑date boundaries) are reused unchanged. The adapter adds no
target‑derived column.

## Known limitations
See `metadata.json → known_limitations`: US big‑box retail; no marketing/promo
signal (held at 0, never invented); weekly→daily price fill; 40‑series slice.
