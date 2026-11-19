# India local-store POS register (`INDIA_REAL_BUSINESS`, provenance unverified)

| | |
|---|---|
| Source | Kaggle `alankuriyan/retail-sales-register-data` — https://www.kaggle.com/datasets/alankuriyan/retail-sales-register-data |
| Licence | **CC BY-NC-SA 4.0** — attribution, non-commercial, share-alike |
| Acquired | 2026-10-07, Kaggle public anonymous endpoint (no login/token); raw zip sha256 `2ee177e8…bd59` |
| Size / dates | 94,290 line items · 2025-01-01 → 2025-03-31 (89 days) · 1,682 distinct product names |
| Status | Downloaded into `data/external/india_pos_register/`; **not** registered in the app, **not** in the backend |

## Why it was judged real (evidence from the file, not the description)
- Indian item names in local usage (`ULLI`, `NEDRA POKA`, `MALLILLA`, `PAPPDAM`) beside brands (Aashirvaad, Amul); truncated register abbreviations (`CAD DAIRY MIL`).
- GST slabs 0 / 5 / 18 % (plus rare 28 / 40 %); milk fixed at ₹28 on all 3,046 lines while onion (₹20–100), tomato (₹17–30), egg (₹4–12) vary like market prices.
- Weighed fractional quantities (0.25, 0.55 kg) on 36% of lines; Sunday sales ≈ 40% of Monday's; daily revenue CV 0.32.
- `qty × rate` equals a printed amount on 99.94% of lines even though the export's amount columns are shifted between rows.
- Not synthetic by the usual tests: no sequential artificial IDs, no uniform categorical/numeric distributions, 549 natural repeat lines.
Authenticity remains an inference; the uploader gives no store name or paper.

## Transformations (lossless — `scripts/prepare_india_pos_register.py`)
Remove thousands separators; coerce numerics; parse dd/mm/yyyy; recompute `line_amount_inr = qty × rate`; flag (never drop) 549 exact duplicate rows; keep both raw amount columns. Raw file untouched in `raw/` (git-ignored like other external raw data).

## Fits / does not fit
- **Fits:** descriptive questions with exact answers (total sales for a month/week, top products by revenue, GST share, busiest weekday, price change of a product); a short daily product-level forecasting benchmark.
- **Does not fit:** churn/customer analysis (no customer id), decisions with outcomes (no promotions/stock), anything needing > 1 season.
- **Backend:** fractional quantities and free-text products do not fit the fixed integer `sales.quantity` schema. No schema change was made; ingest only if you decide to scale quantities (a material change — ask first).
