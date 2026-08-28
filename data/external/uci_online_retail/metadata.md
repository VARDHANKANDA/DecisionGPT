# UCI Online Retail — dataset card

## What it is
A **real** transactional dataset from a UK‑based, registered non‑store online
retailer, covering **2010‑12‑01 to 2011‑12‑09**. One row per invoice line
item. The company mainly sells unique all‑occasion giftware; many customers
are wholesalers.

- **Rows (raw):** 541,909
- **Distinct customers:** 4,372 (135,080 rows have no `CustomerID` — guest/aggregated)
- **Distinct product codes:** 4,070
- **Columns:** `InvoiceNo, StockCode, Description, Quantity, InvoiceDate, UnitPrice, CustomerID, Country`

## Source, license, citation
- **Source:** UCI Machine Learning Repository, Dataset 352 — <https://archive.ics.uci.edu/dataset/352/online+retail>
- **Downloaded from:** `https://archive.ics.uci.edu/static/public/352/online+retail.zip` (public, no authentication), on **2026‑08‑28**.
- **License:** Creative Commons Attribution 4.0 International (CC BY 4.0), as published by the UCI ML Repository.
- **Citation:** Chen, D. (2015). *Online Retail* [Dataset]. UCI Machine Learning Repository. <https://doi.org/10.24432/C5BW33>
- **Raw checksums (MD5):** `Online Retail.xlsx` = `8f8e6d94ba88f976f4d8290cb2dea7fd`; `online_retail.zip` = `333d81b51e52a6f7a20540a2f0f092bf`

Raw files live in `raw/` and are **never modified** (and are gitignored — re‑download with the URL above).

## Supported DecisionGPT tasks
| Task | Supported | How |
|---|---|---|
| **Forecasting** | ✅ | `ml/preprocessing/uci_online_retail_adapter.py` → `processed/uci_forecasting.csv` (daily units per product, top‑N by volume, canonical schema). |
| **Customer analytics (RFM)** | ✅ | `processed/uci_customer_rfm.csv` — recency/frequency/monetary per customer. |
| **Churn (DERIVED)** | ✅ *optional* | `processed/uci_churn_derived.csv` — see below. |
| Causal graph evaluation | ❌ | No controlled ground truth. |
| Digital Twin (as an *active* SME model) | ❌ | Benchmark only; any model trained on it stays `experimental`. |
| Multi‑Agent / Ablation | ❌ | Not a training dataset for these. |
| Indian‑context validation | ❌ | UK retailer. |

## DERIVED CHURN LABEL — exact definition
The raw data has **no churn flag**. The adapter constructs one with a
**time‑aware** split so there is **no future leakage**:

1. Observation window = `2010‑12‑01 … 2011‑09‑09` (first ~9 months).
2. Holdout window = `2011‑09‑10 … 2011‑12‑09` (last ~3 months).
3. Keep only customers with ≥ 1 valid purchase in the **observation** window.
4. `churned = 1` if that customer made **zero** valid purchases in the **holdout** window, else `0`.
5. **Every feature** (`tenure_days, recency_days, frequency, avg_order_value, monetary_value`) is computed **using observation‑window transactions only**. `recency_days` is measured from the observation‑window end date.
6. "Valid purchase": `Quantity > 0`, `UnitPrice > 0`, `InvoiceNo` not starting with `C` (cancellation), non‑null `CustomerID`.

This is a standard inactivity‑based proxy. It is labelled **`DERIVED CHURN LABEL`**
everywhere and does **not** replace `platform-churn-v1` (the controlled
synthetic churn benchmark), which remains the reproducibility baseline.

## Adapter cleaning (forecasting)
- Drop cancellations, `Quantity ≤ 0`, `UnitPrice ≤ 0`, and non‑product stock codes (`POST`, `DOT`, `M`, `BANK CHARGES`, `AMAZONFEE`, `CRUK`, `PADS`, `S`, `D`, `C2`, gift‑card codes).
- Daily aggregate per `StockCode`: `units_sold = Σ Quantity`, `price = Σ(Quantity·UnitPrice) / Σ Quantity`.
- `marketing_spend = 0`, `promotion_flag = 0` — the dataset carries no such signal (held at 0, never invented).
- Keep the **top‑N products by total units** (default `N = 40`, deterministic) so the processed file stays small and each series has enough history for the 28‑day rolling features.

## Known limitations
See `metadata.json → known_limitations`. In short: one UK retailer; extreme skew; no marketing/promo signal; derived (not observed) churn.
