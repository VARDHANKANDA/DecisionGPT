# DATA_AUDIT — forecast_study_v2 (Phase A)

Measured from the raw files on 2026-10-22 (`tools/data_audit.py` → `results/data_audit.json`; `tools/independent_targets_check.py` → `results/independent_targets_check.json`). No forecast outcome is involved.

## 1. Sources, versions, terms

| dataset | source / version | observation period, frequency | hash (SHA-256 of the raw file used) | terms |
|---|---|---|---|---|
| M5 Forecasting – Accuracy (CA_1, TX_1, WI_1) | Kaggle competition data (University of Nicosia / Makridakis et al.), `sales_train_evaluation.csv` (d_1–d_1941), `calendar.csv`, `sell_prices.csv` | daily, 2011-01-29 → 2016-05-22 (1,941 days) | sales `4b4a47c4…` (full hashes in `results/data_audit.json`); calendar `d12b5914…`; prices `9da3ad1f…` | Kaggle competition rules: non-commercial/academic use; **no redistribution** (`DATA_RIGHTS_AUDIT.md`) |
| Online Retail II | UCI ML Repository, donor Daqing Chen (2012; donated 2019); the repository's CSV conversion of the xlsx (`source_sheet` column) | transactions 2009-12-01 → 2011-12-09 (739 calendar days) | `5f45b06f…` | CC BY 4.0; cite Chen (2012), doi:10.24432/C5CG6D |

## 2. Entities and targets

* **M5 stores.** A department-stratified random draw (seed 20261015) of 350 (CA_1, TX_1) or 349 (WI_1) series per store from the series whose first non-zero sale is on or before d_1100 (CA_1: 2,673 of 3,049 eligible; TX_1: 2,661; WI_1: 2,677). Products launched later are excluded, so the samples are not random draws of the stores' assortments. The draw uses no information after d_1100 and is identical for every window. WI_1 has never been used by a forecasting experiment in this repository (`WINDOW_USE_AUDIT.md`).
* **Online Retail II.** The 100 SKUs with the largest revenue before the window's first validation block (re-selected per window; the W1 list equals v1's, the W2 list is derived independently and was recomputed from raw transactions by a unit test and by `independent_targets_check`). Daily gross units after cleaning: cancellation invoices (19,494 rows), non-positive quantity (3,457) or price (2,750), non-product stock codes (4,581) and exact duplicate lines (33,666, 3.2 %) dropped, leaving 1,003,423 of 1,067,371 rows. **Returns are excluded from demand** (the target is gross sales units). Calendar days without trading are zeros. Rows without a customer ID are kept for demand. The target is not "net" demand and the exact-duplicate rule may remove genuine repeated scans; this is a documented modelling choice, not verified against the retailer.
* **Independent rebuild.** For every dataset and window the arrays built by the study loader equal the values read directly from the raw files (M5: per-series, per-day equality; Online Retail II: independent cleaning, SKU ranking and aggregation): **all 11 dataset-windows identical** (`independent_targets_check.json`; W3 for Online Retail II is infeasible by design).

## 3. Window properties (all from raw data)

| dataset – window | series | days kept (T′) | scored span (dates) | zero share, all days | zero share, test rows | frequent / sparse series |
|---|---|---|---|---|---|---|
| CA_1 – W1 | 350 | 1,941 | 2015-09-14 → 2016-05-22 | 0.601 | 0.538 | 50 / 300 |
| CA_1 – W2 | 350 | 1,689 | 2015-01-05 → 2015-09-13 | 0.609 | 0.542 | 46 / 304 |
| CA_1 – W3 | 350 | 1,437 | 2014-04-28 → 2015-01-04 | 0.618 | 0.562 | 46 / 304 |
| TX_1 – W1 / W2 / W3 | 350 | 1,941 / 1,689 / 1,437 | same spans | 0.671 / 0.677 / 0.686 | 0.628 / 0.619 / 0.651 | 39/311, 33/317, 36/314 |
| WI_1 – W1 / W2 / W3 | 349 | 1,941 / 1,689 / 1,437 | same spans | 0.662 / 0.679 / 0.697 | 0.534 / 0.577 / 0.587 | 39/310, 41/308, 35/314 |
| Online Retail II – W1 | 100 | 739 | 2011-04-02 → 2011-12-09 | 0.374 | 0.317 | 25 / 75 |
| Online Retail II – W2 | 100 | 487 | 2010-07-24 → 2011-04-01 | 0.387 | 0.402 | 17 / 83 (segments from 235 days of history, not 365) |

"Zero share, test rows" is over all series-days of the six test blocks (before the price-listing filter). Segments use ADI/CV² (cutoffs 1.32/0.49) and volume terciles from the days before the first validation block (at most 365); nothing from validation or test periods.

## 4. Data quality findings

* No negative or missing values in any window; M5 targets are integers; there are **0 days with positive demand on days without a price listing** across the full history (so the eligible-row rule removes only structurally-zero rows). The share of series-days without a listing is 12–26 % and grows in earlier windows (items not yet launched).
* **The price-listing rule is an assumption:** M5's documentation is understood to state that a missing price means the item was not sold that week; whether listing is known ex ante to a forecaster is assumed, not verified. All methods are scored on the same rows, so the comparison is unaffected, but absolute WAPE and zero shares depend on the rule.
* Online Retail II W2 covers the period containing the 2010 Christmas peak with at most one prior Christmas season of training history; the history before the first W2 test origin is 319 days. Its series are high-volume wholesale SKUs (top 10 % of series hold about 35 % of demand), not typical intermittent demand.
* Outliers: Online Retail II has very large single-order quantities; they are retained (no winsorising) because they are the demand being forecast, and they make pooled WAPE sensitive to a few SKU-days.
* Duplicates and returns: handled as above. Prior experiments that used the same data: `WINDOW_USE_AUDIT.md`.

## 5. Open data-audit items

The ex-ante availability of the price listing; the retailer-side meaning of Online Retail II duplicate lines; M5 eligibility excludes later-launched products; the processed Online Retail II CSV is a conversion of the UCI workbook performed earlier in the project (the conversion script is not part of this study).
