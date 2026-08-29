# Indian Dataset Integration — Report

**Date:** 2026-08-29
**Objective:** Replace the non-Indian external benchmark layer (M5 / UCI Online
Retail / Myanmar Supermarket Sales) with the best available **Indian** business
data, **without changing the DecisionGPT architecture, the synthetic datasets,
the production models, or any existing experiment.**

All work is **additive or a safe move**. No core module, migration, endpoint,
model, or synthetic dataset was modified. The Indian dataset flows through the
**existing** Dataset Registry (`research_dataset_service`), Training Center
(`training_service`), and Model Registry lifecycle (`experimental` → `active`).

Companion docs: `docs/INDIAN_DATASET_MIGRATION_PLAN.md` (the pre-change plan),
`docs/FINAL_DATASET_INVENTORY.md`, `docs/DATASET_DOWNLOAD_INSTRUCTIONS.md`,
`data/external/india_agmarknet/metadata.md`,
`data/external/_retired_non_indian/README.md`.

> **Follow-up (2026-08-29):** a later task added the full Indian SME data
> *layer* around this benchmark work — SME upload layers (finance, business
> profile), capability detection, and Indian public-context datasets (festival
> calendar, RBI macro). AGMARKNET was renamed `india_agmarknet` and labelled
> `INDIA_AGRICULTURAL_PRICE`. See **`docs/INDIAN_SME_DATA_ARCHITECTURE.md`** and
> **`docs/INDIAN_DATASET_CATALOG.md`**.

---

## 1. Non-Indian datasets removed / retired

Retired from the **active India-focused evaluation** because DecisionGPT
targets Indian SMEs. **Nothing was force-deleted** — reproducibility and
traceability are preserved.

| Dataset | Geography | Retirement action |
|---|---|---|
| **M5 Forecasting** | USA (Walmart) | dir → `data/external/_retired_non_indian/m5_forecasting/`; dropped from default scripts; reproducible via `--retired` |
| **UCI Online Retail** | UK | dir → `data/external/_retired_non_indian/uci_online_retail/`; same |
| **Supermarket Sales** | Myanmar | dir → `data/external/_retired_non_indian/regional_retail/`; same |

What was retired, per artifact:

| Artifact | Disposition |
|---|---|
| Raw downloads | moved under `_retired_non_indian/**/raw/` (still gitignored, unmodified) |
| Processed CSVs | moved under `_retired_non_indian/**/processed/` (kept for reproducibility) |
| `metadata.{json,md}` | moved with the dirs |
| Adapters (`ml/preprocessing/{m5,uci_online_retail,supermarket_sales}_adapter.py`) | **kept in place** (inert unless called); still covered by `tests/unit/test_external_adapters.py` |
| `scripts/build_external_datasets.py` / `register_external_datasets.py` / `run_external_benchmarks.py` | default target is now **India**; the non-Indian sets are behind an explicit `--retired` flag |
| Registry entries / dataset versions / models | only in the local gitignored `backend/dev.db`; recreated by scripts. If ever re-registered, `--retired` prefixes the name and `source` with `RETIRED_NON_INDIAN_BENCHMARK` |
| Docs | `EXTERNAL_DATASET_INTEGRATION_REPORT.md` carries a **SUPERSEDED** banner; `DATASET_INTEGRATION_AUDIT.md` a historical note; `DATASET_DOWNLOAD_INSTRUCTIONS.md` moved them to a "RETIRED" section; `EXPERIMENT_GUIDE.md` / `data/README.md` rewritten |

Verified: `python scripts/build_external_datasets.py --retired` regenerates the
three retired processed CSVs **byte-identically** (git shows them as pure
renames, no content change).

---

## 2. Indian datasets discovered and evaluated

| Candidate | Source | Licence | Verdict |
|---|---|---|---|
| **AGMARKNET daily mandi prices** | data.gov.in resource `35985678-…` (DMI, Min. of Agriculture) | **GODL-India** | **SELECTED** — genuine, open, clearly licensed, historical (2006→), multi-state, date + price + product + market. Only weakness: no quantity field, and the *public demo* API key is heavily rate-limited. |
| "Amazon Sale Report (India)", "E-commerce Sales Dataset" | Kaggle | varies / unclear | rejected — Kaggle account + rules acceptance required; bypassing auth not permitted |
| BigMart Sales | Analytics Vidhya practice problem | not stated; GitHub mirrors unlicensed | rejected — no clearly-licensed public copy; also **no date column** (unfit for chronological forecasting) |
| DoCA daily retail prices of essential commodities | data.gov.in (Dept. of Consumer Affairs) | GODL-India | rejected — catalog is SPA-only; not served through the generic `/resource/` API; per-year file attachments only |
| data.gov.in "Current Daily Mandi Price" (`9ef84268-…`) | data.gov.in | GODL-India | rejected — **today's snapshot only**, no history → no chronological split |

Selection scored against the task's 10 criteria: Indian context ✅, real ✅,
clear source ✅, clear licence (GODL-India) ✅, large (81M source rows) ✅,
date column ✅, suitable target (modal price) ✅, enough features (price
level + spread + market/commodity) ⚠️ (no quantity/marketing), reproducible ✅
(fixed series list, seed 42, checksummed adapter), architecture-compatible ✅
(canonical forecasting schema, existing pipeline).

---

## 3. Indian dataset selected — source & licence

| Field | Value |
|---|---|
| Dataset | **India Agri-Commodity Daily Market Prices (AGMARKNET)** |
| `dataset_id` | `external-india-agmarknet-v1` |
| Source | Open Government Data (OGD) Platform India — `data.gov.in`, resource `35985678-0d79-46b4-9ed6-6f13308a1d24` ("Variety-wise Daily Market Prices Data of Commodity") |
| Publisher | Directorate of Marketing & Inspection (DMI), Dept. of Agriculture & Farmers Welfare, Government of India — system **AGMARKNET** |
| Source URL | https://www.data.gov.in/catalog/variety-wise-daily-market-prices-data-commodity |
| API | `https://api.data.gov.in/resource/35985678-0d79-46b4-9ed6-6f13308a1d24` (public JSON REST) |
| **Licence** | **Government Open Data License – India (GODL-India)** — https://www.data.gov.in/Godl (free use with attribution) |
| Geography | **India**, multi-state · `data_type: real` |
| Citation | Directorate of Marketing & Inspection (DMI), Dept. of Agriculture & Farmers Welfare, Government of India. *Variety-wise Daily Market Prices Data of Commodity* [Data set]. Open Government Data (OGD) Platform India, data.gov.in. |

Acquisition is through the **plain public API** — no login, no scraping, no
ToS bypass. `scripts/download_india_datasets.py` uses the demo API key that
data.gov.in publishes in its own API documentation, paginating with
`sort[Arrival_Date]=asc` and checkpointing each series.

---

## 4. Current status — `DATA_PENDING`

The **integration is complete and green**; the **raw data is not yet
committed**. During integration the data.gov.in *demo* key's quota
(~10 records/call, short burst window) was exhausted, so a full historical
pull could not be completed in-session. Registering a **free** data.gov.in key
removes the limit (1000 records/call → full pull in < 1 min); an account is
required, which the automated agent is not permitted to create.

Populate with one command (see `data/external/india_agmarknet/metadata.md`):

```bash
DATA_GOV_IN_API_KEY=<free key>  python scripts/download_india_datasets.py   # or omit for the slow demo-key path
python scripts/build_external_datasets.py
DATABASE_URL=sqlite:///./backend/dev.db python scripts/register_external_datasets.py
DATABASE_URL=sqlite:///./backend/dev.db python scripts/run_external_benchmarks.py --seed 42
```

Every script **degrades gracefully** while `DATA_PENDING`: the build, register
and benchmark steps print `SKIP` and exit 0; the test suite passes (the
committed-file tests `skip`); nothing else is affected.

---

## 5. What was built (ready to run the moment the data lands)

| Component | File | Notes |
|---|---|---|
| Legitimate downloader | `scripts/download_india_datasets.py` | public data.gov.in JSON API; demo key or `DATA_GOV_IN_API_KEY`; `sort[Arrival_Date]=asc` pagination; per-series checkpoints under `raw/_parts/`; fixed deterministic `SERIES` list |
| Adapter | `ml/preprocessing/india_agmarknet_adapter.py` | `build_forecasting()` → canonical schema (price-forecasting); `build_regional_analytics()` → state×commodity×month table; seed 42; reuses the leakage-safe `build_forecasting_features` + `chronological_split` |
| Build wiring | `scripts/build_external_datasets.py` | default `--only india`; `_check_forecasting` validation; `--retired` for the archived set |
| Registry wiring | `scripts/register_external_datasets.py` | `research_dataset_service.upload_dataset(...)`; source `External Benchmark - India … (data_type=real)`, licence GODL-India; idempotent |
| Benchmark wiring | `scripts/run_external_benchmarks.py` | `training_service.start_training(...)`, seed 42, forecasting × {naive, linear, xgboost}; asserts every new model is `experimental` and the active set is unchanged |
| Metadata | `data/external/india_agmarknet/metadata.{json,md}` | full provenance + `status: DATA_PENDING` + canonical-mapping table |
| Tests | `tests/unit/test_india_agmarknet_adapter.py` (6) | tiny synthetic RAW fixture: canonical schema, `units_sold == modal_price`, **price feature is backward-only (no leakage)**, determinism, zero marketing/promotion, analytics table; committed-file training test `skip`s until data lands |
| Integration test | `tests/integration/test_external_dataset_integration.py` | repointed to an India-shaped dataset: register → train → **experimental only** + active set unchanged + `select_best_model` still returns the active model; a retired dataset stays labelled `RETIRED_NON_INDIAN_BENCHMARK`; registry still `{platform, uploaded}` |

### Preprocessing (no leakage)

- **Time-series → chronological split only** (`chronological_split`, unique-date
  boundaries) — reused, not reimplemented.
- Features (`build_forecasting_features`): all lags/rolling means are
  `.shift(1)` backward-only — reused.
- `price` column = 28-day **backward** rolling median of modal price, shifted 1
  day; leading rows fall back to the series' first modal price (known at t0).
  A dedicated unit test asserts `price[t]` never lies outside the range of
  `modal_price[:t]` — i.e. it never uses present or future information.
- `marketing_spend` / `promotion_flag` held at `0` — absent in source,
  **not invented**.
- Because the source has **no quantity**, the canonical `units_sold` slot
  carries the **daily modal price (INR/quintal)** — this is a documented column
  *reuse*, not fabrication; `modal_price` is also emitted verbatim as an extra
  column.

### Model Registry safety

`run_external_benchmarks.py` trains through `training_service.start_training`,
which forces `status="experimental"` and `write_index=False`. The script then
asserts `not non_experimental` and `active_before == active_after`. No active
SME production model is touched or replaced.

---

## 6. Synthetic datasets retained

Unchanged and still active — they provide the controlled experiments the paper
depends on:

| Dataset | Purpose |
|---|---|
| `platform-forecasting-v1` (`data/platform/forecasting/`) | controlled forecasting baseline; known generative process |
| `platform-churn-v1` (`data/platform/churn/`) | controlled churn experiments (**the only churn dataset** — no real Indian churn benchmark exists yet) |
| synthetic `causal` scenario | causal-graph evaluation with **known ground truth** (Precision / Recall / F1 / SHD) |
| synthetic decision scenarios | Digital-Twin evaluation, decision-architecture comparison, ablation study |

Final strategy: **`REAL INDIAN DATA  +  CONTROLLED SYNTHETIC DATA`** — target-domain
validation *and* reproducible architecture evaluation, never one at the expense
of the other.

---

## 7. Models trained / benchmark results

**None yet** — blocked on `DATA_PENDING`. When the data lands,
`run_external_benchmarks.py` trains forecasting × {naive, linear, xgboost}
(seed 42) on `external-india-agmarknet-forecasting`, recording for each run:
dataset, dataset_version, seed, model_name, model_version, parameters, start/end
timestamps, metrics (MAE / RMSE / MAPE), status — via the existing `TrainingRun`
+ `MLModel` lifecycle. All resulting models enter as `experimental`.

Metrics guidance for this dataset: report **MAE / RMSE**; MAPE is noisy on
price series with sharp spikes. The naive lag baseline is expected to be
strong (price series are near-random-walk) — that is the correct, honest
baseline to beat.

---

## 8. Research paper usage

**Permitted**
- Report Indian **price-forecasting** MAE / RMSE (naive vs linear vs xgboost)
  on `external-india-agmarknet-forecasting` as evidence the predictive
  pipeline runs on real Indian government data, in a separate table row labelled
  `Geography: India · Type: Real`.
- Keep synthetic results in their own rows (`Type: Synthetic`); **never average
  across real and synthetic**.
- Describe the dataset precisely: *AGMARKNET daily wholesale mandi modal prices*.

**Not permitted**
- Calling this SME retail data, or claiming Indian SME retail performance from
  it (it is agri-commodity **wholesale price** data).
- Claiming universal Indian SME applicability.
- Claiming causal validity from it (no interventions — causal evaluation stays
  on the synthetic `causal` dataset).
- Presenting the retired M5 / UK / Myanmar datasets as representing Indian SMEs.

---

## 9. Remaining limitations

1. **`DATA_PENDING`** — the real raw pull needs a free data.gov.in API key (or a
   long demo-key session). One documented command populates it.
2. **No quantity** in the Indian source → price forecasting only, not demand.
3. **Wholesale, not SME retail** — a genuine Indian SME transaction dataset
   remains **pending** (open Indian data is price-series; transaction datasets
   are Kaggle-auth-gated). Documented in `DATASET_DOWNLOAD_INSTRUCTIONS.md §2`.
4. **No real Indian churn dataset** → the synthetic churn dataset is retained for
   controlled churn experiments; a real Indian churn benchmark is pending.

---

## 10. Verification

| Check | Result |
|---|---|
| Backend test suite (`backend/.venv`, `pytest`) | **191 passed, 1 skipped, 0 failed** (was 187 passed) |
| New unit tests (`test_india_agmarknet_adapter.py`) | 6 — schema, price semantics, **no-leakage**, determinism, analytics; committed-file training test `skip`s until `DATA_PENDING` clears |
| Integration tests (`test_external_dataset_integration.py`) | 3 — experimental-only + active unchanged, retired-labelling, registry separation |
| Retired reproducibility | `build_external_datasets.py --retired` → byte-identical processed CSVs (git renames only) |
| Synthetic datasets | untouched |
| Core architecture / migrations / active models | unchanged (no migration added; `0001→0005` round-trip green, 29 tables) |
| Frontend build + ESLint | ✅ clean (no frontend change; 26 routes, 0 lint errors) |
| `scripts/audit_e2e.py` | ✅ 18/18 SME flow + research pipeline + exports + access control |
