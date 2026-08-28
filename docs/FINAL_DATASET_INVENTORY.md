# Final Dataset Inventory

**Date:** 2026-08-29 · Strategy: **`REAL INDIAN DATA  +  CONTROLLED SYNTHETIC DATA`**

Non-Indian datasets are **not** active. See
`docs/INDIAN_DATASET_INTEGRATION_REPORT.md`.

## Active datasets

| Dataset | Geography | Type | Task | Status |
|---|---|---|---|---|
| India Agri-Commodity Daily Market Prices (AGMARKNET) — forecasting | India | Real | Price forecasting | **Active (DATA_PENDING raw pull)** |
| India Agri-Commodity Daily Market Prices — regional analytics | India | Real | Regional price analytics (descriptive) | **Active (DATA_PENDING raw pull)** |
| `platform-forecasting-v1` | Synthetic | Synthetic | Controlled forecasting | Active |
| `platform-churn-v1` | Synthetic | Synthetic | Controlled churn | Active |
| Synthetic causal scenario | Synthetic | Synthetic | Causal-graph validation (known ground truth) | Active |
| Synthetic decision scenarios | Synthetic | Synthetic | Digital-Twin eval · architecture comparison · ablation | Active |

`DATA_PENDING` = integration complete and tested; raw bytes not committed
because the data.gov.in demo API key is rate-limited. One documented command
populates it (`data/external/india_mandi_prices/metadata.md`). All scripts and
tests degrade gracefully until then.

## Pending (not integrated — no legally-accessible source found)

| Dataset | Geography | Type | Task | Status |
|---|---|---|---|---|
| Indian retail / e-commerce **transaction** dataset | India | Real | Analytics / forecasting / customer | **Pending** — Kaggle-auth-gated; manual path in `DATASET_DOWNLOAD_INSTRUCTIONS.md §2` |
| Indian **churn / retention** dataset | India | Real | Churn | **Pending** — no open source; synthetic churn retained for controlled experiments |

## Retired — `RETIRED_NON_INDIAN_BENCHMARK` (reproducibility only, not active)

| Dataset | Geography | Type | Task | Status |
|---|---|---|---|---|
| M5 Forecasting | USA | Real | Forecasting | Retired — `data/external/_retired_non_indian/m5_forecasting/`, `scripts/*.py --retired` |
| UCI Online Retail | UK | Real | Forecasting / derived churn / RFM | Retired — `data/external/_retired_non_indian/uci_online_retail/` |
| Supermarket Sales | Myanmar | Mixed | Forecasting / margin analytics | Retired — `data/external/_retired_non_indian/regional_retail/` |

## Per-dataset task support (active + pending Indian)

| Task | India Mandi Prices | `platform-forecasting-v1` | `platform-churn-v1` | Synthetic causal | Synthetic decision scenarios |
|---|---|---|---|---|---|
| Sales / demand forecasting | ❌ no quantity in source | ✅ | ❌ | ❌ | ❌ |
| **Price** forecasting | ✅ (DATA_PENDING) | ➖ (synthetic units) | ❌ | ❌ | ❌ |
| Churn | ❌ no customer data | ❌ | ✅ | ❌ | ❌ |
| Customer analytics | ❌ | ❌ | ➖ | ❌ | ❌ |
| Digital Twin evaluation | ⚠️ benchmark only (model stays experimental) | ✅ | ✅ | ❌ | ✅ |
| Causal evaluation | ❌ no interventions | ❌ | ❌ | ✅ (ground truth) | ➖ |
| Multi-agent evaluation | ❌ | ❌ | ❌ | ❌ | ✅ |
| Ablation study | ❌ | ➖ | ➖ | ➖ | ✅ |
| Indian-context validation | ✅ (wholesale agri prices — **not** SME retail) | ❌ synthetic | ❌ synthetic | ❌ synthetic | ❌ synthetic |

Legend: ✅ supported · ⚠️ benchmark-only · ➖ partial/indirect · ❌ not supported.

## Finalization verification (2026-08-29)

| Check | Result |
|---|---|
| Backend test suite (`backend/.venv`, `pytest`) | **191 passed, 1 skipped, 0 failed** (was 187 passed; +5 new India adapter tests, +1 skip = the committed-file test until `DATA_PENDING` clears) |
| Frontend `next build` | ✅ clean (26 routes; no frontend change) |
| `next lint` (ESLint) | ✅ 0 errors (1 pre-existing unrelated warning in `auth-context.tsx`) |
| Alembic migration round-trip `0001→0005` up / down-to-base / up | ✅ 29 tables (no migration added) |
| `scripts/audit_e2e.py` | ✅ 18/18 SME flow + research pipeline + exports + access control |
| `build_external_datasets.py --retired` byte-identical | ✅ (git shows retired CSVs as pure renames) |
