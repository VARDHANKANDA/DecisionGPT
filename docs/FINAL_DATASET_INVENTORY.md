# Final Dataset Inventory

**Date:** 2026-08-29 · Strategy:
**SME-owned operational data + Indian public context + controlled synthetic**

Full catalog: `docs/INDIAN_DATASET_CATALOG.md` · Architecture:
`docs/INDIAN_SME_DATA_ARCHITECTURE.md`.

## Active datasets

| Dataset | Category | Geography | Type | Task | Status |
|---|---|---|---|---|---|
| SME-uploaded sales / customers / products / inventory / **finance** / **marketing** / **business profile** | *(SME-private)* | India | Real | the actual SME recommendations | **Primary source** — canonical schema + capability detection |
| India Festival & Holiday Calendar | `INDIA_PUBLIC_CONTEXT` | India | Real (holidays lib, pinned) | seasonality context feature | **Active** — committed CSVs |
| India Macro Context — RBI repo rate | `INDIA_PUBLIC_CONTEXT` | India | Real | macro / finance context feature | **Active** — committed CSV (CPI/WPI/GDP `PENDING`) |
| India Agri-Commodity Daily Market Prices (AGMARKNET) — forecasting | `INDIA_AGRICULTURAL_PRICE` | India | Real | **price** forecasting | **Active, `DATA_PENDING` raw pull** |
| AGMARKNET — regional price analytics | `INDIA_AGRICULTURAL_PRICE` | India | Real | descriptive price analytics | **Active, `DATA_PENDING` raw pull** |
| `platform-forecasting-v1` | `SYNTHETIC_CONTROLLED` | Synthetic | Synthetic | controlled forecasting | Active |
| `platform-churn-v1` | `SYNTHETIC_CONTROLLED` | Synthetic | Synthetic | controlled churn (only churn dataset) | Active |
| Synthetic causal scenario | `SYNTHETIC_CONTROLLED` | Synthetic | Synthetic | causal-graph validation (ground truth) | Active |
| Synthetic decision scenarios | `SYNTHETIC_CONTROLLED` | Synthetic | Synthetic | Digital-Twin eval · architecture comparison · ablation | Active |

`DATA_PENDING` (AGMARKNET) = integration complete + tested; raw bytes not
committed because the data.gov.in demo API key is rate-limited. One command
populates it (`data/external/india_agmarknet/metadata.md`). Build / register /
benchmark scripts and the test suite degrade gracefully until then.

## Pending — not integrated (no legally-accessible source)

| Dataset | Why pending |
|---|---|
| Indian retail / e-commerce **transaction** dataset | Kaggle-auth-gated; BigMart has no date column & no clear licence. Manual path: `DATASET_DOWNLOAD_INSTRUCTIONS.md §2`. **SME upload is the primary route for this data.** |
| Indian **churn / retention** dataset | no open source — synthetic churn retained for controlled experiments |
| CPI / WPI / GDP / IIP / FX macro series | MoSPI / data.gov.in, same rate-limited API as AGMARKNET — documented, not fabricated |
| UDYAM / ASUSE / ASI business-population context | aggregate publications, not row-level; Tier-3 extension points in the catalog |

## Retired — `RETIRED_NON_INDIAN` (reproducibility only, not active)

| Dataset | Geography | Location |
|---|---|---|
| M5 Forecasting | USA | `data/external/_retired_non_indian/m5_forecasting/` (`scripts/*.py --retired`) |
| UCI Online Retail | UK | `data/external/_retired_non_indian/uci_online_retail/` |
| Supermarket Sales | Myanmar | `data/external/_retired_non_indian/regional_retail/` |

## Per-dataset task support

| Task | AGMARKNET | Festivals | Macro | `platform-forecasting` | `platform-churn` | Synthetic causal | Synthetic decision |
|---|---|---|---|---|---|---|---|
| Sales / demand forecasting | ❌ no quantity | ➖ context feature | ➖ context feature | ✅ | ❌ | ❌ | ❌ |
| **Price** forecasting | ✅ (`DATA_PENDING`) | ❌ | ❌ | ➖ | ❌ | ❌ | ❌ |
| Churn | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ |
| Customer analytics | ❌ | ❌ | ❌ | ❌ | ➖ | ❌ | ❌ |
| Digital Twin evaluation | ⚠️ benchmark only | ➖ input feature | ➖ input feature | ✅ | ✅ | ❌ | ✅ |
| Causal evaluation | ❌ no interventions | ❌ | ❌ | ❌ | ❌ | ✅ (ground truth) | ➖ |
| Multi-agent evaluation | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| Ablation study | ❌ | ❌ | ❌ | ➖ | ➖ | ➖ | ✅ |
| Indian-context validation | ✅ agri **wholesale price** (not SME retail) | ✅ seasonality context | ✅ macro context | ❌ synthetic | ❌ synthetic | ❌ synthetic | ❌ synthetic |

Legend: ✅ supported · ⚠️ benchmark-only · ➖ partial / feature-only · ❌ not supported.

## Verification (2026-08-29)

| Check | Result |
|---|---|
| Backend test suite (`backend/.venv`, `pytest`) | **201 passed, 1 skipped, 0 failed** (was 191; +10 new: context adapters, dataset-category classifier, capability + finance + business-profile layers; +1 pre-existing skip = AGMARKNET committed-file test until `DATA_PENDING` clears) |
| Frontend `next build` | ✅ clean (26 routes) |
| `next lint` (ESLint) | ✅ 0 errors (1 pre-existing unrelated warning in `auth-context.tsx`) |
| Alembic migration `0001 → 0006` up / down-to-base / up | ✅ 30 tables (`+finance_records`; `+9` nullable `businesses` columns) |
| `scripts/audit_e2e.py` | ✅ 18/18 SME flow + research pipeline + exports + access control |
| `build_external_datasets.py --retired` byte-identical | ✅ (git shows retired CSVs as pure renames) |
| New model auto-promotion | none — no new models trained this task (AGMARKNET still `DATA_PENDING`); active models unchanged |
