# Supermarket Sales (Myanmar) — dataset card

> **Regional, not Indian.** This dataset is from **Myanmar** (branches in
> Yangon, Mandalay, Naypyitaw). It is integrated as a *South/Southeast
> Asian emerging‑market retail* benchmark because no genuinely Indian
> retail dataset could be obtained without Kaggle authentication (see
> `docs/DATASET_DOWNLOAD_INSTRUCTIONS.md`). **The research paper must not
> describe this dataset as Indian.**

## What it is
One row per invoice for a supermarket company operating **3 branches over
~3 months (2019‑01‑01 … 2019‑03‑30)**, across **6 product lines**
(Health and beauty, Electronic accessories, Home and lifestyle, Sports and
travel, Food and beverages, Fashion accessories).

- **Rows:** 1,000 · **Nulls:** 0 · **Duplicate rows:** 0
- Rich fields: `Unit price, Quantity, Total, Cost of goods sold, Gross income, Gross margin percentage, Payment, Customer type, Gender`.

## Source, license, citation
- **Origin:** widely‑circulated "Supermarket sales" dataset, attributed on Kaggle to *Aung Pyae* — <https://www.kaggle.com/datasets/aungpyaeap/supermarket-sales>.
- **Copy used:** Plotly's public **MIT‑licensed** `datasets` repository — `https://raw.githubusercontent.com/plotly/datasets/master/supermarket_Sales.csv` (public, no auth). Downloaded **2026‑08‑28**. MD5 = `b281aeb11d2676751186461d83bdfc99`.
- **License:** Plotly repo is MIT. The original Kaggle upload's license is unspecified/"other"; it is broadly used for teaching. Treat as freely usable for research **with attribution**, not a formally licensed corpus.
- **Data type:** `mixed` — the uploader calls it historical records; some secondary sources treat it as simulated/anonymised. Marked conservatively.

Raw file in `raw/` is **never modified** (gitignored — re‑download with the URL above).

## Supported DecisionGPT tasks
| Task | Supported | How |
|---|---|---|
| **Forecasting** (small) | ✅ *with caveat* | `ml/preprocessing/supermarket_sales_adapter.py` → `processed/regional_retail_forecasting.csv`: daily `units_sold` per `Branch\|Product line` (18 series × ~89 days). **Very small** — illustrative only. |
| **Business analytics (margin)** | ✅ *descriptive* | `processed/regional_retail_analytics.csv` adds `revenue, cogs, gross_income, margin_pct`. **Not consumed by any model**; for the paper's descriptive analytics only. |
| Churn / customer analytics | ❌ | No stable customer identity across invoices. |
| Causal / Digital Twin (active) / Multi‑Agent / Ablation | ❌ / ➖ | Keeps the synthetic controlled scenarios; a model trained here stays `experimental`. |
| Indian‑context validation | ❌ | Myanmar. |

## Adapter transforms (raw → canonical)
1. Parse `Date` (`M/D/YYYY`).
2. `series_id = f"{Branch}|{Product line}"` (18 series).
3. Daily aggregate per series: `units_sold = Σ Quantity`, `price = Σ(Quantity·Unit price)/Σ Quantity`.
4. `marketing_spend = 0`, `promotion_flag = 0` (no such field — held at 0, never invented).
5. Forecasting output: exactly `series_id, date, units_sold, price, marketing_spend, promotion_flag`.
6. Analytics output additionally: `revenue = Σ Total`, `cogs = Σ Cost of goods sold`, `gross_income = Σ Gross income`, `margin_pct = gross_income / revenue`.

**No leakage:** reuses the existing leakage‑safe forecasting feature builder
and chronological split; no target‑derived column added.

## Known limitations
See `metadata.json → known_limitations`. In short: Myanmar not India;
tiny (89 days); ambiguous provenance; no marketing/promo signal.
