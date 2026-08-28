# DecisionGPT — Dataset Integration Audit (Phase 0)

Inspection performed **before any change to working code**. Goal: add a
small external benchmark suite without touching the existing architecture,
datasets, models, or migrations.

---

## 1. Existing dataset inventory

| Kind | Location | Consumed by | Notes |
|---|---|---|---|
| Platform forecasting | `data/platform/forecasting/sales_timeseries.csv` + `metadata.json` (`platform-forecasting-v1`) | `ml/pipeline/loaders.load_platform_dataset("forecasting", …)` → `ml/training/train_forecasting.run()` | Synthetic, `SYNTHETIC` evidence level, 29 200 rows (40 series × 730 days, 2023‑01‑01…2024‑12‑30), seed 42. Columns: `series_id, date, units_sold, revenue, price, marketing_spend, promotion_flag`. |
| Platform churn | `data/platform/churn/customers.csv` + `metadata.json` (`platform-churn-v1`) | `load_platform_dataset("churn", …)` → `train_churn.run()` | Synthetic, 6 000 rows. Columns: `customer_id, tenure_days, recency_days, frequency, avg_order_value, monetary_value, support_tickets, discount_usage_rate, churned`. |
| Empty platform domains | `data/platform/{marketing,pricing,inventory,causal,benchmarks}/.gitkeep` | — | No dataset; `dataset_registry_service` skips them. |
| Controlled synthetic scenarios (in‑code) | `decision_architecture_service._seed_synthetic_business`, `causal_evaluation_service._generate_synthetic_series` | Experiment Runner (`decision_architecture`, `multi_agent`, `ablation`, `causal`) | Known causal ground truth `A→B→C`; ephemeral synthetic business for architecture/ablation. **Must be preserved.** |
| Uploaded research datasets | DB (`research_datasets`, `research_dataset_versions`) + files under `settings.research_data_path` (`data/research_uploads/`, gitignored) | `research_dataset_service`, `training_service` (`dataset_version_id`) | Created via `POST /research/datasets/upload`. Auto‑validated, schema‑inspected, quality‑reported, versioned (re‑upload → v2). |

**Nothing in `data/platform/` or the synthetic scenarios is removed or modified by this integration.**

---

## 2. Existing model input schemas (verified in code)

### Forecasting — `ml/training/train_forecasting.train_one(df, model_type, seed, params)`
`REQUIRED_COLUMNS = ["series_id", "date", "units_sold", "price", "marketing_spend", "promotion_flag"]`
- `clean_dataframe(df, date_columns=["date"])` → parse dates, drop exact dups, sort.
- `build_forecasting_features` → per‑`series_id` `lag_1, lag_7, rolling_mean_7, rolling_mean_28` (all `.shift(1)` → **backward only**), `day_of_week, is_weekend, month`, pass‑through `price, marketing_spend, promotion_flag`. Target `units_sold`. Drops rows without a full 28‑day window.
- `chronological_split(featured, "date", 0.7/0.15/0.15)` on **unique date boundaries** → a calendar date never straddles partitions → **no future leakage**.
- Guards: ≥ 30 usable rows after feature engineering; non‑empty train & test.
- Model types: `naive`, `linear`, `xgboost`. Metrics: `mae, rmse, mape` (+ `shap_global_importance` for xgboost).

### Churn — `ml/training/train_churn.train_one(...)`
`base_cols = ["tenure_days", "recency_days", "frequency", "avg_order_value", "monetary_value", "churned"]`
- `build_churn_features` adds `purchase_rate_per_year`, `recency_ratio`. `FEATURE_COLUMNS` = the 5 base numeric + those 2 derived. `support_tickets`/`discount_usage_rate` **deliberately excluded** (an SME can't supply them at inference).
- `train_test_split(X, y, test_size=0.2, stratify=y, random_state=seed)`.
- Guards: ≥ 50 rows; ≥ 2 target classes.
- Model types: `logistic_regression`, `random_forest`, `xgboost`. Metrics: `precision, recall, f1, roc_auc`.

### Not a training task (in‑code only)
Digital Twin simulation, Causal Graph build, Multi‑Agent debate, Ablation — driven by the SME pipeline / synthetic scenarios, **not** by an uploaded dataset. External datasets cannot and must not be forced into them.

---

## 3. Existing supported tasks

`training_service.SUPPORTED = {"forecasting": {...}, "churn": {...}}` — these are the **only** tasks the Training Center advertises, and the only ones an external dataset can train.

`experiment_service.SUPPORTED_EXPERIMENT_TYPES = {forecasting, churn, digital_twin, causal, decision_architecture, multi_agent, ablation}`. The `forecasting`/`churn` experiment types call `train_*.run()` which is **hard‑wired to the platform dataset** — they are not dataset‑parameterised.

---

## 4. Dataset Registry capabilities

`research_dataset_service.upload_dataset(db, *, name, domain, filename, content, description, source, license, created_by)`:
- Accepts **CSV / XLSX / Parquet** (Parquet needs `pyarrow` — **not installed here**, so CSV/XLSX only in this environment).
- `domain ∈ {forecasting, churn, marketing, pricing, inventory, causal, benchmarks, other}`.
- Validates via `ml/pipeline/validation.validate_dataframe` (missing columns, missing‑value counts, duplicate rows, emptiness).
- Records schema (`{name, dtype}` per column), missing summary, duplicates summary, quality report, `validation_ok`.
- **Versions automatically**: re‑upload the same `name` → `v2, v3, …`.
- Stores raw bytes under `settings.research_data_path`; never SME‑reachable.
- `source` and `license` free‑text fields already exist on `ResearchDataset` → **"External Benchmark" provenance needs no schema change**.
- Frontend **Dataset Registry** page already renders `source` / `license` / `domain` for uploaded datasets and `evidence_level` for platform datasets → **no frontend change needed**.

---

## 5. Training Center capabilities

`training_service.start_training(db, *, task, model_type, dataset_version_id=None, platform_domain=None, parameters=None, random_seed=42)`:
- With `dataset_version_id` → loads that uploaded version's dataframe and trains `train_one`.
- Creates a `TrainingRun` (`pending → running → completed | failed`) recording: `random_seed`, `dataset_version_id`, `dataset_version_label` (`upload:<slug>:v<n>`), `task`, `model_type`, `parameters_json`, `features_json`, `target`, `started_at`, `completed_at`, `metrics_json` (+ `train_rows`/`test_rows`), `model_id`, `model_name`, `model_version`, `artifact_path`, `status`, `error_message`.
- Registers an `MLModel` with **`status="experimental"`**, `source="training_center"`, unique `v<n>` per `model_name`, and **`write_index=False`** so a later `models/sync` never auto‑activates it.
- Production inference (`model_registry_service.get_active_model` / `select_best_model`) only ever picks `status="active"` → **an externally‑trained model has zero effect on SME behaviour until explicitly promoted.**

**Conclusion:** the Training Center already *is* a dataset‑aware, fully‑reproducible experiment runner for training tasks. No new experiment infrastructure is required.

---

## 6. External dataset compatibility matrix

| Dataset | Forecasting | Churn (derived) | Customer analytics | Digital Twin | Causal eval | Multi‑Agent eval | Ablation | Indian‑context |
|---|---|---|---|---|---|---|---|---|
| **M5 Forecasting** (Walmart US) | ✅ via adapter | ❌ no customer id | ⚠️ limited | ➖ benchmark only (not wired to SME Twin) | ❌ | ❌ | ❌ | ❌ US |
| **UCI Online Retail** (UK) | ✅ via adapter (subsample) | ✅ **DERIVED** label, optional, time‑aware | ✅ RFM | ➖ benchmark only | ❌ | ❌ | ❌ | ❌ UK |
| **Supermarket Sales** (Myanmar) | ✅ via adapter (small) | ❌ no repeat customers | ✅ incl. real cost/margin | ➖ benchmark only | ❌ | ❌ | ❌ | ❌ Myanmar (regional, **not** India) |
| Existing synthetic forecasting | ✅ | — | — | ✅ (active model) | — | — | — | illustrative only |
| Existing synthetic churn | — | ✅ | — | — | — | — | — | illustrative only |
| Synthetic causal / scenario | — | — | — | ✅ | ✅ known ground truth | ✅ | ✅ | — |

**Legend:** ✅ genuinely compatible · ⚠️ partial / caveated · ➖ possible but not connected · ❌ not applicable.

**Key honesty points:**
- No external dataset is wired into the SME **Digital Twin**, **Causal Graph**, or **Multi‑Agent** engines. Those keep using the synthetic scenarios (known ground truth) — as the task requires.
- M5 / UCI / Supermarket Sales are **predictive‑model benchmarks** (forecasting; UCI additionally derived‑churn). They demonstrate the *training + evaluation pipeline* on real‑world data; they do not claim causal validity or SME generalisation.
- **No genuinely Indian dataset was auto‑downloadable** (the well‑known ones — BigMart, Indian e‑commerce sets — are Kaggle‑gated; bypassing Kaggle auth is prohibited). Supermarket Sales (Myanmar) is integrated as a **regional emerging‑market** dataset, honestly labelled, **not** as "Indian". Manual acquisition of an Indian dataset is documented in `docs/DATASET_DOWNLOAD_INSTRUCTIONS.md`.

---

## 7. Required preprocessing

Every external dataset needs a **schema adapter** (raw → canonical). Raw files are never modified.

| Dataset | Raw shape | Adapter output (canonical) | Key transforms |
|---|---|---|---|
| **M5** | wide daily sales (`d_1…d_1941`), separate `calendar.csv`, `sell_prices.csv` | `series_id, date, units_sold, price, marketing_spend(=0), promotion_flag(=0)` | melt wide→long; join `calendar` for real `date`; join `sell_prices` (per `wm_yr_wk`) for `price`; **subsample N series** (deterministic, seed 42) to keep the file small; drop leading all‑zero warm‑up per series. `marketing_spend`/`promotion_flag` **held at 0 — M5 has no such signal** (documented, not invented). |
| **UCI Online Retail** | one row per invoice line | forecasting: `series_id(=StockCode), date, units_sold, price, marketing_spend(=0), promotion_flag(=0)` · churn: `tenure_days, recency_days, frequency, avg_order_value, monetary_value, churned` | drop cancellations (`InvoiceNo` starts `C`), `Quantity ≤ 0`, `UnitPrice ≤ 0`, null `CustomerID` (churn only); daily aggregate per product; subsample top‑N products by volume. **Derived churn:** observation window (first 9 months) vs holdout (last ~3 months); `churned=1` iff active in observation, silent in holdout; **all features computed on the observation window only** → no future leakage. |
| **Supermarket Sales** | one row per invoice | forecasting: `series_id(=Branch|Product line), date, units_sold, price, marketing_spend(=0), promotion_flag(=0)` · analytics: adds `revenue, cogs, gross_income, margin_pct` (not consumed by current models) | parse `M/D/YYYY` dates; daily aggregate per (branch × product line); ~89 days only → **small‑data caveat documented**. |

No adapter touches the Digital Twin / Causal / Multi‑Agent code.

---

## 8. Proposed integration plan

1. Preserve raw under `data/external/<name>/raw/` (gitignored — large).
2. `data/external/<name>/{metadata.json, metadata.md}` — provenance, license, citation, columns, supported/unsupported tasks, limitations. **Committed.**
3. `ml/preprocessing/<name>_adapter.py` — pure functions `raw → canonical DataFrame`, fixed seed, fully documented. **Committed.**
4. `scripts/build_external_datasets.py` — runs every adapter, writes `data/external/<name>/processed/*.csv` (small, deterministic). **Processed CSVs committed** so a fresh clone can train without the multi‑GB raw.
5. `scripts/register_external_datasets.py` — registers each processed CSV through the **existing** `research_dataset_service.upload_dataset` with `source="External Benchmark — <name> (<data_type>)"`, real `license`, provenance `description`. Idempotent.
6. `scripts/run_external_benchmarks.py` — for each *genuinely compatible* (dataset, task, model_type), calls `training_service.start_training` (→ `experimental` models + `TrainingRun` provenance rows). Prints a summary table.
7. New tests under `tests/` for adapters (schema, leakage, determinism) and one end‑to‑end "register → train (experimental) → active models unchanged" check. **Additive only.**
8. `docs/DATASET_DOWNLOAD_INSTRUCTIONS.md` (M5 manual path + Indian dataset), `docs/EXTERNAL_DATASET_INTEGRATION_REPORT.md` (final report), update `data/README.md` and `docs/EXPERIMENT_GUIDE.md`.

**No changes** to: any model, migration, endpoint, existing service, existing experiment, the Digital Twin / Causal / Multi‑Agent / Ablation code, the frontend.

---

## 9. Files that would need modification

**New only** — nothing existing is edited except three docs that gain a section:

| File | Change |
|---|---|
| `ml/preprocessing/__init__.py`, `ml/preprocessing/{m5_adapter,uci_online_retail_adapter,supermarket_sales_adapter}.py` | new |
| `scripts/{build_external_datasets,register_external_datasets,run_external_benchmarks}.py` | new |
| `data/external/**` (`raw/` gitignored, `processed/*.csv` + `metadata.*` committed), `data/README.md` | new / append |
| `docs/{DATASET_INTEGRATION_AUDIT,DATASET_DOWNLOAD_INSTRUCTIONS,EXTERNAL_DATASET_INTEGRATION_REPORT}.md` | new |
| `docs/EXPERIMENT_GUIDE.md` | **append** an "External benchmark datasets" section |
| `.gitignore` | **append** `data/external/**/raw/` |
| `tests/unit/test_external_adapters.py`, `tests/integration/test_external_dataset_integration.py` | new |

---

## 10. Risks of breaking existing functionality

| Risk | Likelihood | Mitigation |
|---|---|---|
| Externally‑trained model replaces an active production model | **None** | `training_service` forces `status="experimental"`, `write_index=False`; `select_best_model` only reads `status="active"`. A test asserts active models are unchanged after external training. |
| A new dependency destabilises the environment | Low | No new runtime dependency. Adapters use `pandas` (already present); Parquet stays out (no `pyarrow`). |
| Committing multi‑GB raw data bloats the repo | Medium | `data/external/**/raw/` gitignored; only small deterministic `processed/*.csv` + metadata committed; manual re‑download documented. |
| Adapter introduces target leakage | Low | Forecasting reuses the existing leakage‑safe `build_forecasting_features` + `chronological_split`. Derived churn uses an explicit observation/holdout time split with features on the observation window only; a test asserts no holdout‑window row informs a feature. |
| Existing 177 tests regress | **Very low** | All changes are new files. Full suite + frontend build + eslint + clean‑DB migration re‑run after integration. |
| Paper over‑claims Indian relevance | Medium (documentation risk) | Supermarket Sales labelled *Myanmar / regional*, never *Indian*; `country_context` recorded per dataset; report §12 states exactly what each dataset can and cannot support. |
| Experiment Runner needs extending | Low | It does **not** — the Training Center already provides dataset‑aware, reproducible training. No change made. |

---

## Decision

Proceed with the plan in §8. It is **purely additive**, reuses the existing
Dataset Registry + Training Center + Model Registry, preserves all
synthetic data and controlled experiments, keeps every externally‑trained
model `experimental`, and introduces no data leakage or unsupported claims.
