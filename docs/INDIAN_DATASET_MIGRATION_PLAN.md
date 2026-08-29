# Internal Cleanup Plan — Replace Non-Indian Benchmarks with Indian Data

Status: executed 2026-08-28. This is the short plan written **before** any file
was changed (task Step 1). The outcome is in
`docs/INDIAN_DATASET_INTEGRATION_REPORT.md`.

## Phase 1 — audit result (what exists today)

Non-Indian external benchmark layer added in the previous task
(commit `8df9b88`). Everything is **additive**, script-driven, and lives
outside migrations/seeds, so retiring it needs **no DB migration** and touches
**no core module**.

| Artifact | Path | Action |
|---|---|---|
| Raw data (gitignored) | `data/external/{m5_forecasting,uci_online_retail,regional_retail}/raw/` | move under `_retired_non_indian/` (stays gitignored) |
| Processed CSVs | same dirs `/processed/*.csv` | move under `_retired_non_indian/` (kept for reproducibility) |
| Metadata | same dirs `metadata.{json,md}` | move; prepend `RETIRED_NON_INDIAN_BENCHMARK` note |
| Adapters | `ml/preprocessing/{m5_adapter,uci_online_retail_adapter,supermarket_sales_adapter}.py` | keep in place (inert unless called); no longer in the default build |
| Build script | `scripts/build_external_datasets.py` | default → India; non-Indian behind `--retired` |
| Register script | `scripts/register_external_datasets.py` | default → India; `--retired` prefixes name/source with `RETIRED_NON_INDIAN_BENCHMARK` |
| Benchmark script | `scripts/run_external_benchmarks.py` | default → India; `--retired` reproduces the archived runs |
| Unit tests | `tests/unit/test_external_adapters.py` | keep (retired-adapter contract still verified); repoint the committed-file test to India |
| Integration test | `tests/integration/test_external_dataset_integration.py` | repoint to the India dataset; keep all safety assertions |
| Docs | `EXTERNAL_DATASET_INTEGRATION_REPORT.md`, `DATASET_DOWNLOAD_INSTRUCTIONS.md`, `EXPERIMENT_GUIDE.md`, `data/README.md`, `DATASET_INTEGRATION_AUDIT.md` | banner / restructure to mark UK-US-Myanmar retired, India active |
| DB rows (local `backend/dev.db` only, gitignored) | `research_datasets` / `research_dataset_versions` / `models` | re-created from scripts; retired slugs simply not re-registered. Any that remain are renamed `RETIRED_NON_INDIAN_BENCHMARK …` |

Reproducibility is preserved: the archived processed CSVs, metadata, adapters,
and a `--retired` path in all three scripts remain, so every historical run can
be regenerated. Nothing is force-deleted.

## Phase 2 — retire

`git mv data/external/{m5_forecasting,uci_online_retail,regional_retail} data/external/_retired_non_indian/`.
Add `data/external/_retired_non_indian/README.md` (status = `RETIRED_NON_INDIAN_BENCHMARK`).
Rewrite the three scripts with an `--retired` opt-in; default target becomes India.

## Phase 3-6 — Indian dataset

**Dataset A — India Agri-Commodity Daily Market Prices (AGMARKNET).**
- Source: data.gov.in resource `35985678-0d79-46b4-9ed6-6f13308a1d24`
  ("Variety-wise Daily Market Prices Data of Commodity"), Directorate of
  Marketing & Inspection (DMI), Ministry of Agriculture & Farmers Welfare, GoI.
- License: **Government Open Data License – India (GODL-India)**.
- Geography: India (multi-state). Real. Daily, 2006→present, 81M rows.
- Fields: `Arrival_Date, State, District, Market, Commodity, Variety, Grade,
  Min_Price, Max_Price, Modal_Price`. **No transaction-quantity field.**
- Acquisition: `scripts/download_india_datasets.py` — paginated API pull for a
  curated, deterministic list of `(state, commodity, market)` series →
  `raw/india_agmarknet_raw.csv` (raw, never modified, gitignored).
- Adapter: `ml/preprocessing/india_agmarknet_adapter.py`
  - `build_forecasting(raw)` → canonical `series_id,date,units_sold,price,marketing_spend,promotion_flag`.
    Because the source has **no quantity**, this is a **price-forecasting**
    benchmark: the canonical `units_sold` slot carries the **daily modal price
    (INR/quintal)** being forecast; `price` = 28-day backward rolling median of
    modal price (strictly backward-looking exogenous feature — no leakage);
    `marketing_spend = promotion_flag = 0` (absent in source — not invented).
    Extra self-documenting columns `modal_price/min_price/max_price` are also
    emitted (the trainer selects only the canonical columns).
  - `build_regional_analytics(raw)` → state×commodity×month descriptive table
    (avg modal price, volatility, spread%, active markets, MoM% change). Not a
    training task.
- Chronological split only; seed 42; reuse the existing leakage-safe
  `build_forecasting_features` + `chronological_split`.

**Dataset B / Dataset C (churn):** no openly-licensed, directly-downloadable
Indian *transaction-level* or *churn* dataset exists — the open Indian data
landscape is price series (data.gov.in), and transaction datasets are
Kaggle-auth-gated (not permitted). Documented as **pending**; the synthetic
churn dataset is retained for controlled churn experiments.

## Phase 7-13

Register A + its analytics table through the existing
`research_dataset_service`; benchmark-train forecasting (naive/linear/xgboost,
experimental only) via `training_service`; regression suite + `audit_e2e.py`;
write `INDIAN_DATASET_INTEGRATION_REPORT.md` + `FINAL_DATASET_INVENTORY.md`.
