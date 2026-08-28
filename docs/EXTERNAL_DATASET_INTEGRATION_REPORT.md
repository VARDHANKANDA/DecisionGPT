# External Benchmark Dataset Integration — Final Report

**Date:** 2026-08-28
**Scope:** Add real-world / regional benchmark datasets to DecisionGPT's research
evaluation **without changing the platform architecture, the synthetic datasets,
the production models, or any existing experiment.**

All work is **additive**. No existing service, model, migration, API endpoint,
frontend page, Digital Twin / Causal Graph / Multi-Agent module, or synthetic
dataset was modified. The external datasets flow through the **existing** Dataset
Registry (`research_dataset_service`), the **existing** Training Center
(`training_service`), and the **existing** Model Registry lifecycle
(`experimental` → `active`).

Companion documents:
`docs/DATASET_INTEGRATION_AUDIT.md` (Phase 0 inspection),
`docs/DATASET_DOWNLOAD_INSTRUCTIONS.md` (legitimate acquisition steps),
`data/README.md` (synthetic vs external separation),
`data/external/<name>/metadata.{json,md}` (per-dataset provenance).

---

## 1. Datasets successfully integrated

Three external datasets were acquired through legitimate public access and
integrated as **External Benchmark** datasets. No authentication, licensing,
CAPTCHA, or terms-of-service restriction was bypassed.

| # | Dataset | Country context | `data_type` | Acquisition |
|---|---|---|---|---|
| 1 | **UCI Online Retail** | United Kingdom | `real` | `curl` from UCI ML Repository (no account) |
| 2 | **M5 Forecasting** | United States (Walmart / CA, TX, WI) | `real` | `curl` from Nixtla's public MIT-licensed `m5-forecasts` mirror (no account) |
| 3 | **Supermarket Sales (regional)** | **Myanmar — explicitly NOT India** | `mixed` | `curl` from Plotly's MIT-licensed `datasets` repo (no account) |

These produced **6 registered dataset versions** in the existing registry (one per
processed table), each with `validation_ok = true`:

| Registry name | `dataset_id` | Domain | Rows |
|---|---|---|---|
| External UCI Online Retail — Forecasting | `external-uci-online-retail-forecasting` | forecasting | 9,730 |
| External UCI Online Retail — Derived Churn | `external-uci-online-retail-derived-churn` | churn | 3,360 |
| External UCI Online Retail — Customer RFM | `external-uci-online-retail-customer-rfm` | other | 3,360 |
| External M5 Forecasting Benchmark | `external-m5-forecasting-benchmark` | forecasting | 76,901 |
| External Regional Retail (Myanmar) — Forecasting | `external-regional-retail-myanmar-forecasting` | forecasting | 761 |
| External Regional Retail (Myanmar) — Analytics | `external-regional-retail-myanmar-analytics` | other | 761 |

Every registry entry carries `source` beginning with `External Benchmark - …
(data_type=…)` so the Research Console and the paper can always tell it apart
from the bundled synthetic data (`evidence_level: SYNTHETIC`).

---

## 2. Datasets requiring manual download

| Dataset | Status | Reason | Where documented |
|---|---|---|---|
| **A genuine Indian-context retail transaction dataset** | **NOT integrated** — manual only | Every candidate with the required shape (date, product/category, quantity, price/revenue) is behind a **Kaggle account + rules acceptance** (e.g. "Amazon Sale Report (India)", "E-commerce Sales Dataset"), or lacks a date column (BigMart Sales), or is commodity-price only and needs a data.gov.in API key. Bypassing Kaggle authentication is not permitted, so nothing was faked. | `docs/DATASET_DOWNLOAD_INSTRUCTIONS.md` §4 — a full 7-step manual path (pick + verify licence, download via the source UI/API after accepting terms, add `metadata.{json,md}`, add `ml/preprocessing/indian_business_adapter.py`, wire into the 3 scripts, re-run regression). |
| **M5 Forecasting — original Kaggle copy** | Integrated via public mirror; Kaggle path also documented | The repo uses Nixtla's MIT-licensed redistribution (`github.com/Nixtla/m5-forecasts`, `m5.zip` MD5 `333d81b51e52a6f7a20540a2f0f092bf`). Users who prefer the canonical Kaggle download have `Option B` (account + `kaggle competitions download -c m5-forecasting-accuracy`). | `docs/DATASET_DOWNLOAD_INSTRUCTIONS.md` §3 |

**The paper must not describe the Myanmar dataset as Indian.** Until an Indian
dataset is manually added, the Indian-context claim is limited to the wording in
`DATASET_DOWNLOAD_INSTRUCTIONS.md` §4: *"evaluated additionally on a regional
(Southeast Asian) retail dataset; a genuine Indian-context dataset integration
path is documented but not yet populated."*

---

## 3. Dataset source and license

| Dataset | Source | Source URL | License (verified — not invented) | Citation |
|---|---|---|---|---|
| **UCI Online Retail** | UCI Machine Learning Repository, Dataset 352 | `https://archive.ics.uci.edu/dataset/352/online+retail` | **CC BY 4.0** (UCI ML Repository) | Chen, D. (2015). *Online Retail* [Dataset]. UCI Machine Learning Repository. https://doi.org/10.24432/C5BW33 |
| **M5 Forecasting** | M5 Forecasting competition (Univ. of Nicosia / Makridakis Open Forecasting Center); data provided by **Walmart**. Copy used: Nixtla `m5-forecasts` mirror. | `https://www.kaggle.com/competitions/m5-forecasting-accuracy` | Underlying data is **Walmart's**, released under the **M5 competition rules** (unchanged by redistribution). Nixtla's mirror tooling is **MIT**. Verify competition terms before redistributing your own copy. | Makridakis, S., Spiliotis, E., & Assimakopoulos, V. (2022). *The M5 competition: Background, organization, and implementation.* International Journal of Forecasting, 38(4), 1325–1336. https://doi.org/10.1016/j.ijforecast.2021.07.007 |
| **Supermarket Sales (regional)** | "Supermarket sales" dataset (attributed on Kaggle to *Aung Pyae*). Copy used: **Plotly public `datasets` repository**. | `https://www.kaggle.com/datasets/aungpyaeap/supermarket-sales` (copy via `https://github.com/plotly/datasets`) | Plotly `datasets` repo is **MIT-licensed**. Original Kaggle upload lists licence as **unspecified/other**; widely used for education. Treated as: freely usable for research **with attribution**; **not a formally licensed corpus**. | Aung Pyae. *Supermarket sales* [Data set]. Kaggle. |

Raw-file integrity (recorded in each `metadata.json` / download doc):
`Online Retail.xlsx` MD5 `8f8e6d94ba88f976f4d8290cb2dea7fd`;
`m5.zip` MD5 `333d81b51e52a6f7a20540a2f0f092bf` (verified against the 50 MB
download);
`supermarket_sales.csv` MD5 `b281aeb11d2676751186461d83bdfc99`.

**Raw data is never modified** and is git-ignored (`data/external/**/raw/`,
≈580 MB). Only small, deterministic `processed/*.csv` files (produced solely by
`scripts/build_external_datasets.py`, seed 42) are committed.

---

## 4. Dataset statistics

### UCI Online Retail
| Table | Rows | Series / entities | Date range | Notes |
|---|---|---|---|---|
| `uci_forecasting.csv` | 9,730 | 40 products (`UCI_<StockCode>`) | 2010-12-01 → 2011-12-09 | daily units per top-40 product by revenue; revenue-weighted price |
| `uci_churn_derived.csv` | 3,360 | 3,360 customers | observation ≤ 2011-09-09, holdout 2011-09-10 → 2011-12-09 | **DERIVED** inactivity label; class balance not-churned **1,917** / churned **1,443** |
| `uci_customer_rfm.csv` | 3,360 | 3,360 customers | — | recency / frequency / monetary + tenure, avg order value |

Cleaning applied before aggregation: dropped cancellations (`InvoiceNo` starts
`C`), `Quantity ≤ 0`, `UnitPrice ≤ 0`, non-product stock codes (POST, DOT,
M, BANK CHARGES, …), letter-only codes, exact duplicates.

### M5 Forecasting
| Table | Rows | Series | Date range | Notes |
|---|---|---|---|---|
| `m5_forecasting.csv` | 76,901 | 40 (`<item_id>__<store_id>`) | 2011-01-29 → 2016-05-22 | deterministic top-40 item×store by total units; weekly `sell_price` forward/back-filled to daily; leading zero-sales rows trimmed per series |

### Supermarket Sales (regional, Myanmar)
| Table | Rows | Series | Date range | Notes |
|---|---|---|---|---|
| `regional_retail_forecasting.csv` | 761 | 18 (`SS_<Branch>|<Product line>`) | 2019-01-01 → 2019-03-30 | daily units + mean unit price per branch×product-line. **Only ~3 months** — small |
| `regional_retail_analytics.csv` | 761 | 18 | 2019-01-01 → 2019-03-30 | adds `revenue`, `cogs`, `gross_income`, `margin_pct` (real cost-of-goods fields) |

In every external forecasting table `marketing_spend = 0` and
`promotion_flag = 0` — **these datasets carry no such signal; the values are held
at zero, not invented.**

---

## 5. Dataset-to-task mapping

Legend: ✅ supported and demonstrated · ⚠️ supported but weak (small / noisy) ·
❌ not supported (documented reason) · *benchmark-only* = may be evaluated but the
resulting model **stays `experimental`** and never wires into a live SME module.

| Task | UCI Online Retail | M5 Forecasting | Regional Retail (Myanmar) |
|---|---|---|---|
| **Forecasting** | ✅ 40 series, 13 months | ✅ 40 series, 5+ years (strongest external benchmark) | ⚠️ 18 series, ~3 months only — indicative, not conclusive |
| **Churn** | ✅ **DERIVED** inactivity label, time-aware split (see §6). Does **not** replace `platform-churn-v1` | ❌ no customer-level data | ❌ no repeat-customer identity across invoices |
| **Customer Analytics** | ✅ RFM table (3,360 customers) | ❌ no customer data | ❌ invoice-level only, no customer identity |
| **Digital Twin** | ⚠️ *benchmark-only* — predictive backbone can be scored; model stays `experimental`, never becomes an active SME twin | ⚠️ *benchmark-only* | ⚠️ *benchmark-only* |
| **Causal Evaluation** | ❌ no controlled ground-truth interventions (only the synthetic `causal` dataset has these) | ❌ same | ❌ same |
| **Multi-Agent Evaluation** | ❌ no decision/strategy transcripts | ❌ same | ❌ same |
| **Ablation** | ❌ not used for ablation (ablations run on synthetic controlled scenarios) | ❌ same | ❌ same |
| **Indian-context Validation** | ❌ UK data | ❌ US data | ❌ **Myanmar, not India** — regional emerging-market proxy only |

**No external dataset feeds the SME Digital Twin, Causal Graph, or Multi-Agent
engines.** Those keep the synthetic controlled scenarios with known ground truth.

---

## 6. Preprocessing performed

Isolated, dataset-specific adapters were added under `ml/preprocessing/` (pure
`raw → canonical` functions, fixed `SEED = 42`). They **reuse** the existing
leakage-safe feature builders (`build_forecasting_features`, all lags
`.shift(1)` backward-only) and the existing splitters
(`chronological_split` for time series, stratified `train_test_split` for churn).
No new experiment or training infrastructure was created.

| Adapter | Produces | Key transforms | Leakage controls |
|---|---|---|---|
| `uci_online_retail_adapter.py` | forecasting, RFM, derived churn | clean cancellations/returns/non-products; top-40 by revenue; daily aggregation; revenue-weighted price | forecasting → chronological split on unique dates; features backward-only |
| `m5_adapter.py` | forecasting | deterministic top-40 item×store by total units; wide→long melt; join real `calendar.csv` for dates; weekly→daily price ffill/bfill; trim leading zero-sales | chronological split; no future calendar/price info in training features |
| `supermarket_sales_adapter.py` | forecasting, analytics | parse `%m/%d/%Y`; branch×product-line daily aggregation; margin fields from real `cogs` | chronological split |

### DERIVED CHURN LABEL (UCI) — exact methodology

- **Observation window:** 2010-12-01 → **2011-09-09**. All features
  (`tenure_days`, `recency_days`, `frequency`, `avg_order_value`,
  `monetary_value`) are computed **only** from transactions in this window.
- **Holdout window:** 2011-09-10 → 2011-12-09 (used **only** to assign the label,
  never for features).
- **Label:** `churned = 1` iff the customer was active in the observation window
  **and** made **zero** purchases in the holdout window; else `churned = 0`.
- Customers with no observation-window activity are excluded.
- `inf` values (division artefacts) replaced with `NaN`, then rows dropped.
- Result: 3,360 customers, 1,443 churned / 1,917 retained.
- **This is an inactivity proxy, not an observed churn event.** It is registered
  as a separate dataset (`external-uci-online-retail-derived-churn`), its
  description begins `DERIVED CHURN LABEL (inactivity-based, time-aware split)`,
  and it **does not modify or replace `platform-churn-v1`.**

---

## 7. Models trained

12 training jobs were run through `training_service.start_training(...)`
(`random_seed = 42`), one per compatible (dataset, model_type). Every resulting
model entered the Model Registry as **`experimental`** with
`source = "training_center"`. **Zero** were promoted.

| Dataset version | Task | Model types trained | Train / test rows |
|---|---|---|---|
| `external-uci-online-retail-forecasting` v1 | forecasting | naive, linear, xgboost | 5,652 / 1,526 |
| `external-m5-forecasting-benchmark` v1 | forecasting | naive, linear, xgboost | 52,821 / 11,480 |
| `external-regional-retail-myanmar-forecasting` v1 | forecasting | naive, linear, xgboost | 156 / 54 |
| `external-uci-online-retail-derived-churn` v1 | churn | logistic_regression, random_forest, xgboost | 2,688 / 672 |

Model rows created (all `status = experimental`, none active):
`sales_forecast_{naive,linear,xgboost}` v2 (UCI), v3 (M5), v4 (regional);
`churn_{logistic_regression,random_forest,xgboost}` v2 (UCI derived churn).

---

## 8. Experiment results

Real metrics recorded by the Training Center (seed 42, chronological / stratified
split). **MAPE is reported by the pipeline but is unreliable here** — external
retail data has many zero / near-zero sales days, so MAPE explodes
(e.g. M5 xgboost MAPE ≈ 6.0 × 10⁷ %). **Use MAE / RMSE.**

### Forecasting (lower is better)

| Dataset | Model | MAE | RMSE |
|---|---|---|---|
| **UCI Online Retail** | naive | 126.28 | 328.98 |
| | linear | **93.80** | 245.12 |
| | xgboost | 101.58 | 248.51 |
| **M5 Forecasting** | naive | 13.03 | 19.68 |
| | linear | 10.65 | 15.72 |
| | xgboost | **9.98** | **15.00** |
| **Regional Retail (Myanmar)** ⚠️ tiny test set (54 rows) | naive | 3.96 | 5.58 |
| | linear | 3.35 | 4.64 |
| | xgboost | **3.22** | **4.24** |

Learned models beat the naive baseline on all three datasets (UCI: linear −26 %
MAE; M5: xgboost −23 % MAE; regional: xgboost −19 % MAE — but the regional result
rests on 54 test rows and is **indicative only**).

### Derived churn — UCI (higher is better)

| Model | Precision | Recall | F1 | ROC-AUC |
|---|---|---|---|---|
| logistic_regression | 0.594 | 0.654 | 0.623 | **0.720** |
| random_forest | 0.585 | 0.657 | 0.619 | 0.717 |
| xgboost | 0.593 | 0.671 | **0.630** | 0.715 |

AUC ≈ 0.72 across three model families — a modest, honest signal for an
**inactivity-derived** label, not an observed-churn result.

Reproduce:
```bash
python scripts/build_external_datasets.py        # raw -> processed/*.csv (needs raw/, see download doc)
python scripts/register_external_datasets.py     # into the existing Dataset Registry
python scripts/run_external_benchmarks.py --seed 42
```

---

## 9. Models that remain experimental

**All 12** models trained on external data are `status = experimental` and were
**never promoted**. Verified programmatically in
`scripts/run_external_benchmarks.py` (`assert not non_experimental`) and in the
integration tests.

| Model registry status | Count | Detail |
|---|---|---|
| `active` | **6** | Unchanged synthetic baselines: `sales_forecast_{naive,linear,xgboost}` v1, `churn_{logistic_regression,random_forest,xgboost}` v1 |
| `experimental` | **12** | Every external-dataset model listed in §7 |
| `archived` | 0 | — |

`model_registry_service.select_best_model(...)` and `get_active_model(...)` were
confirmed to still return the **v1 active** synthetic models (different `id` from
any experimental model). No selection behaviour changed.

---

## 10. Existing functionality verified

| Check | Result |
|---|---|
| Platform (synthetic) datasets `platform-forecasting-v1`, `platform-churn-v1`, `causal`, benchmarks | **Untouched** — still present, `evidence_level: SYNTHETIC` |
| Dataset Registry surfaces | Still exactly `{platform, uploaded}` — no duplicate registry; platform side still reports SYNTHETIC, uploaded side reports `External Benchmark` |
| Active production models | **6 active v1, unchanged**; `select_best_model` / `get_active_model` behaviour identical |
| Existing controlled experiments / Experiment Runner | Unchanged — no existing experiment modified; external benchmarks use the same runner additively |
| Digital Twin / Causal Graph / Multi-Agent engines | **Not modified** — no external dataset wired in |
| Alembic migrations | **No new migration.** Clean-DB `0001 → 0005` upgrade + downgrade round-trip still green (29 tables, head `0005`) |
| Frontend | `next build` clean — 26 routes; **ESLint clean** (0 errors); research dashboard unchanged |
| End-to-end audit (`scripts/audit_e2e.py`) | **18/18** SME decision-flow steps + research pipeline + access-control checks pass |

---

## 11. Test results

Backend suite run in `backend/.venv` (`pytest`):

| Suite | Result |
|---|---|
| **Full backend suite** | **187 passed, 0 failed** (177 pre-existing baseline + 10 new) |
| New: `tests/unit/test_external_adapters.py` | 6 passed — adapter schema/cleaning, derived-churn time-awareness + no leakage (`churned.sum() == 4`, `recency_days ≤ 200`), determinism (`assert_frame_equal`), M5 schema + zero marketing, supermarket forecasting + analytics, committed-file training contract |
| New: `tests/integration/test_external_dataset_integration.py` | 3 passed — register + train → **experimental only** + active set unchanged + `select_best_model` still returns active; derived-churn labelled `External Benchmark` / `DERIVED CHURN LABEL`; registry still separates platform vs external |
| Frontend `next build` | pass — 26 routes |
| `next lint` (ESLint) | pass — 0 errors |
| Clean-DB migration round-trip | pass — `0001→0005` up + down |

No test was weakened, skipped, or deleted. New tests use tiny synthetic **raw**
fixtures so they run on a fresh clone without the multi-GB raw files, and an
isolation fixture (`isolate_research_artifacts`) points
`research_data_path` / `MODELS_ROOT` at a tmp dir so the rest of the integration
suite still reads the real baseline models.

---

## 12. Research paper usage

**Permitted:**

- Report external forecasting results (MAE / RMSE) for **UCI Online Retail** and
  **M5 Forecasting** as evidence that the predictive backbone generalises beyond
  the synthetic generator to **real** transaction data.
- Report the **regional (Myanmar) Supermarket Sales** result as an *emerging-market
  retail* data point, **explicitly labelled non-Indian and small** (~3 months,
  54 test rows — indicative only).
- Report the **UCI derived-churn** AUC ≈ 0.72, **explicitly** as an
  *inactivity-derived proxy label with a time-aware observation/holdout split*,
  not an observed-churn outcome.
- State that external-data models are held as `experimental` and do not affect
  the SME-facing system.
- State the hybrid strategy: *synthetic controlled data (known causal ground
  truth) + real external benchmarks (predictive generalisation) + a regional
  emerging-market dataset*.

**Not permitted (guard-rails):**

- ❌ Do **not** call the Myanmar dataset Indian, or claim Indian SME performance.
  The genuine Indian dataset is documented for manual addition only.
- ❌ Do **not** claim universal Indian SME applicability.
- ❌ Do **not** claim causal validity from these datasets — they have no
  controlled interventions; causal evaluation stays on the synthetic `causal`
  dataset.
- ❌ Do **not** present synthetic and real results merged or without stating each
  result's dataset origin and `data_type` (`real` / `mixed` / `synthetic`).
- ❌ Do **not** claim synthetic results prove real-world generalisation — that is
  precisely what the external benchmarks are separately for.
- ❌ Do **not** describe the derived churn number as observed churn.

---

## Per-dataset task-support summary

### UCI Online Retail (UK, `real`, CC BY 4.0)
Forecasting ✅ · Churn ✅ (DERIVED, time-aware, does not replace `platform-churn-v1`) ·
Customer Analytics ✅ (RFM) · Digital Twin ⚠️ benchmark-only (stays experimental) ·
Causal Evaluation ❌ · Multi-Agent Evaluation ❌ · Ablation ❌ ·
Indian-context Validation ❌ (UK data).

### M5 Forecasting (USA / Walmart, `real`, M5 competition terms + Nixtla MIT mirror)
Forecasting ✅ (strongest external benchmark: 40 series × 5+ years) · Churn ❌ (no customer data) ·
Customer Analytics ❌ · Digital Twin ⚠️ benchmark-only (stays experimental) ·
Causal Evaluation ❌ · Multi-Agent Evaluation ❌ · Ablation ❌ ·
Indian-context Validation ❌ (US data).

### Supermarket Sales (Myanmar, `mixed`, Plotly MIT repo)
Forecasting ⚠️ (18 series, ~3 months — indicative only) ·
Margin / business analytics ✅ (real `cogs` / `gross_income`) · Churn ❌ (no customer identity) ·
Customer Analytics ❌ · Digital Twin ⚠️ benchmark-only (stays experimental) ·
Causal Evaluation ❌ · Multi-Agent Evaluation ❌ · Ablation ❌ ·
Indian-context Validation ❌ (**Myanmar, not India** — regional proxy only).

### Genuine Indian-context dataset
**Not integrated.** Could not be obtained without bypassing Kaggle
authentication. Manual acquisition path fully documented in
`docs/DATASET_DOWNLOAD_INSTRUCTIONS.md` §4.

---

## Acceptance checklist

| Criterion | Status |
|---|---|
| Architecture intact (no redesign / refactor) | ✅ |
| Synthetic datasets intact | ✅ |
| External data legally sourced & documented | ✅ (UCI CC BY 4.0; M5 competition terms + MIT mirror; Plotly MIT) |
| Raw data preserved, never modified, git-ignored | ✅ |
| `metadata.json` + `metadata.md` per dataset | ✅ |
| Compatibility verified **before** use (Phase 0 audit) | ✅ (`docs/DATASET_INTEGRATION_AUDIT.md`) |
| No fabricated values / results / licences / citations | ✅ |
| No data leakage (time-aware splits, backward-only features) | ✅ (reuses existing leakage-safe builders; tested) |
| New models `experimental`, never auto-promoted | ✅ (12/12) |
| Active production models unchanged | ✅ (6 active v1) |
| Existing experiments still work | ✅ |
| Provenance reproducible (seed, scripts, checksums) | ✅ |
| Paper distinguishes synthetic vs real | ✅ (§12 guard-rails) |
| Full backend test suite passes | ✅ 187 passed / 0 failed |
| Frontend build passes | ✅ 26 routes |
| ESLint clean | ✅ 0 errors |
| Existing Dataset Registry reused (no duplicate) | ✅ |
