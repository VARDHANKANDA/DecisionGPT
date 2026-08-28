# `_retired_non_indian/` — RETIRED_NON_INDIAN_BENCHMARK

**Status: `RETIRED_NON_INDIAN_BENCHMARK` — not part of the active India-focused
research evaluation.**

DecisionGPT's research focus is **Indian SMEs**. The three datasets below were
integrated in an earlier task as generic real-world / regional benchmarks.
They are **geographically non-Indian** and have been retired from the active
dataset selection, the default benchmark scripts, the Research Dashboard, and
the paper's evaluation tables.

| Folder | Dataset | Geography | Why retired |
|---|---|---|---|
| `m5_forecasting/` | M5 Forecasting (Walmart) | **USA** | not Indian |
| `uci_online_retail/` | UCI Online Retail | **UK** | not Indian |
| `regional_retail/` | Supermarket Sales | **Myanmar** | not Indian (was only ever an honest regional proxy) |

## Nothing was force-deleted

Kept here for **reproducibility and traceability**:

- `*/processed/*.csv` — the exact processed CSVs used by the historical runs.
- `*/metadata.{json,md}` — full provenance (source, licence, citation, checksums).
- `*/raw/` — the unmodified raw downloads (gitignored; re-fetch per
  `docs/DATASET_DOWNLOAD_INSTRUCTIONS.md`, "Retired" section).
- The adapters `ml/preprocessing/{m5_adapter,uci_online_retail_adapter,supermarket_sales_adapter}.py`
  remain in the tree (inert unless explicitly called).
- All three benchmark scripts still reproduce these under an explicit
  `--retired` flag:
  ```bash
  python scripts/build_external_datasets.py    --retired
  python scripts/register_external_datasets.py --retired   # registers as "RETIRED_NON_INDIAN_BENCHMARK ..."
  python scripts/run_external_benchmarks.py    --retired
  ```

## Do not

- present any dataset in this folder as representing Indian SMEs;
- include it in the default `data/external/` active set;
- add its results to the paper's main evaluation tables without the
  `RETIRED / non-Indian` label.

See `docs/INDIAN_DATASET_INTEGRATION_REPORT.md` for the active Indian data
strategy.
