# Final Dataset Inventory

**Date:** 2026-08-29 · Strategy:
**SME-owned operational data + Indian public context + controlled synthetic**

Full catalog: `docs/INDIAN_DATASET_CATALOG.md` · Architecture:
`docs/INDIAN_SME_DATA_ARCHITECTURE.md`.

## Active datasets

| Dataset | Category | Geography | Type | Task | Status |
|---|---|---|---|---|---|
| SME-uploaded sales / customers / products / inventory / **finance** / **marketing** / **business profile** | *(SME-private)* | India | Real | the actual SME recommendations | **Primary source** — canonical schema + capability detection |
| **India E-Commerce Orders (Benroshan)** | `INDIA_REAL_BUSINESS` | India | **Real** (provenance unverified) | analytics + small forecasting benchmark | **Active** — CC0, committed processed CSVs |
| **India E-Commerce Customer Behaviour** | `SYNTHETIC_INDIAN_CONTEXT` | India | **Synthetic** (simulated) | purchase-prediction (standalone benchmark) | **Active** — CC BY 4.0; not an `MLModel` |
| India Festival & Holiday Calendar | `INDIA_PUBLIC_CONTEXT` | India | Real (holidays lib, pinned) | seasonality context feature | **Active** — committed CSVs |
| India Macro Context — RBI repo rate | `INDIA_PUBLIC_CONTEXT` | India | Real | macro / finance context feature | **Active** — committed CSV (CPI/WPI/GDP `PENDING`) |
| India Agri-Commodity Daily Market Prices (AGMARKNET) | `INDIA_AGRICULTURAL_PRICE` | India | Real | **price** forecasting + regional analytics | **Active, `DATA_PENDING` raw pull** |
| `platform-forecasting-v1` | `SYNTHETIC_CONTROLLED` | Synthetic | Synthetic | controlled forecasting | Active |
| `platform-churn-v1` | `SYNTHETIC_CONTROLLED` | Synthetic | Synthetic | controlled churn (only churn dataset) | Active |
| Synthetic causal scenario | `SYNTHETIC_CONTROLLED` | Synthetic | Synthetic | causal-graph validation (ground truth) | Active |
| Synthetic decision scenarios | `SYNTHETIC_CONTROLLED` | Synthetic | Synthetic | Digital-Twin eval · architecture comparison · ablation | Active |

**Evaluated and rejected** (see `docs/INDIAN_DATASET_EVALUATION.md`):
`winstonbobby/indian-retail-sales` (Global Superstore template),
`abuhumzakhan/store-data` (Faker-generated), `maulikgajera/upi-payment-transactions-india`
(synthetic; context-only per brief). All CC0 — rejected on authenticity, not licence.

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

| Task | Benroshan e-com | Kundan customer | AGMARKNET | Festivals | Macro | `platform-forecasting` | `platform-churn` | Synthetic causal | Synthetic decision |
|---|---|---|---|---|---|---|---|---|---|
| Sales / demand forecasting | ⚠️ small daily series | ❌ | ❌ no quantity | ➖ feature | ➖ feature | ✅ | ❌ | ❌ | ❌ |
| **Price** forecasting | ❌ (derived price only) | ❌ | ✅ (`DATA_PENDING`) | ❌ | ❌ | ➖ | ❌ | ❌ | ❌ |
| Sales / profit / geo analytics | ✅ | ❌ | ➖ regional | ❌ | ❌ | ➖ | ❌ | ❌ | ❌ |
| Purchase prediction | ❌ | ✅ (synthetic, standalone) | ❌ | ❌ | ❌ | ❌ | ➖ | ❌ | ❌ |
| Churn | ❌ | ❌ (no target) | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ |
| Digital Twin evaluation | ⚠️ benchmark only | ❌ | ⚠️ benchmark only | ➖ feature | ➖ feature | ✅ | ✅ | ❌ | ✅ |
| Causal evaluation | ❌ observational | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ (ground truth) | ➖ |
| Multi-agent evaluation | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| Ablation study | ❌ | ❌ | ❌ | ❌ | ❌ | ➖ | ➖ | ➖ | ✅ |
| Indian-context validation | ✅ real retail (small) | ⚠️ synthetic only | ✅ agri wholesale price | ✅ seasonality | ✅ macro | ❌ synthetic | ❌ synthetic | ❌ synthetic | ❌ synthetic |

Legend: ✅ supported · ⚠️ benchmark-only · ➖ partial / feature-only · ❌ not supported.

## Verification (2026-08-29)

| Check | Result |
|---|---|
| Backend test suite (`backend/.venv`, `pytest`) | **209 passed, 1 skipped, 0 failed** (was 201; +8 new: Benroshan + Kundan adapters, dataset-category `SYNTHETIC_INDIAN_CONTEXT` / `INDIA_REAL_*`; +1 pre-existing skip = AGMARKNET committed-file test until `DATA_PENDING` clears) |
| Frontend `next build` | ✅ clean (26 routes) |
| `next lint` (ESLint) | ✅ 0 errors (1 pre-existing unrelated warning in `auth-context.tsx`) |
| Alembic migration `0001 → 0006` up / down-to-base / up | ✅ 30 tables (no new migration this task) |
| `scripts/audit_e2e.py` | ✅ 18/18 SME flow + research pipeline + exports + access control |
| Benroshan forecasting benchmark | ✅ 3/3 runs `completed`, all `experimental`; **active model set unchanged (6 → 6)** — asserted |
| Kundan purchase-prediction benchmark | ✅ standalone sklearn; **not an `MLModel`, not in the Training Center** |
| `build_external_datasets.py --retired` byte-identical | ✅ (retired CSVs pure renames) |
