# India Agri-Commodity Daily Market Prices (AGMARKNET)

**Status: `DATA_PENDING`.** The integration is complete and tested; the raw
data is not committed because the data.gov.in public *demo* API key is
rate-limited (~10 records/call) and its quota was exhausted during
integration. See "How to populate" below.

| Field | Value |
|---|---|
| Dataset | India Agri-Commodity Daily Market Prices (AGMARKNET) |
| `dataset_id` | `external-india-mandi-prices-v1` |
| Source | Open Government Data (OGD) Platform India — `data.gov.in`, resource `35985678-0d79-46b4-9ed6-6f13308a1d24` ("Variety-wise Daily Market Prices Data of Commodity") |
| Publisher | Directorate of Marketing & Inspection (DMI), Dept. of Agriculture & Farmers Welfare, Government of India — system: **AGMARKNET** |
| Source URL | https://www.data.gov.in/catalog/variety-wise-daily-market-prices-data-commodity |
| Licence | **Government Open Data License – India (GODL-India)** — https://www.data.gov.in/Godl |
| Geography | **India** (multi-state) |
| `data_type` | `real` |
| Business domain | Agricultural produce market committee (APMC / mandi) wholesale trade — daily min/max/modal price per commodity × market × variety |
| Evidence level | `REAL_INDIAN_EXTERNAL_BENCHMARK` |

## Raw schema

`Arrival_Date, State, District, Market, Commodity, Variety, Grade, Min_Price,
Max_Price, Modal_Price`. **There is no transaction-quantity field.**

## Canonical mapping (`ml/preprocessing/india_mandi_adapter.py`, seed 42)

Because the source has no quantity, this is a **price-forecasting** benchmark.

| Canonical column | Filled with |
|---|---|
| `series_id` | `MANDI_<Commodity>__<Market>` |
| `date` | `Arrival_Date` (parsed `%d/%m/%Y`) |
| `units_sold` | **daily MODAL PRICE (INR/quintal)** — the value forecast. The canonical `units_sold` slot is *reused*; nothing is fabricated. |
| `price` | 28-day **backward** rolling median of modal price, shifted 1 day (strictly past info — no leakage). Leading rows fall back to the series' first modal price. |
| `marketing_spend` | `0` — absent in source, **not invented** |
| `promotion_flag` | `0` — absent in source, **not invented** |
| `modal_price`, `min_price`, `max_price` | extra self-documenting columns; the trainer reads only the canonical ones |

Same-day multiple variety/grade quotes are collapsed to their median. Rows
with unparseable dates or non-positive modal price are dropped. Series with
< 60 daily observations are dropped. Chronological split only.

`build_regional_analytics()` additionally produces a state × commodity × month
descriptive table (avg modal price, volatility, spread %, active markets,
MoM % change) — not consumed by any training task.

## Supported / unsupported tasks

- **Supported:** price forecasting (naive / linear / xgboost), regional price analytics.
- **Not supported:** demand/quantity forecasting (no quantity), churn / customer
  analytics (no customer data), causal-graph evaluation (no controlled
  interventions), Digital-Twin wiring (benchmark only — model stays
  `experimental`), multi-agent evaluation, ablation study.

## Known limitations

- Wholesale **agri-commodity** prices, **not SME retail transactions** — do not
  present as representative of Indian SME retail.
- Price series are near-random-walk → the naive lag baseline is strong. Report
  **MAE / RMSE**.
- Curated to a fixed set of high-liquidity `(commodity × market)` series — not a
  national sample.

## How to populate (`DATA_PENDING` → active)

```bash
# Option A - free registered key (recommended; full pull < 1 min)
#   register at https://data.gov.in/user/register, then:
DATA_GOV_IN_API_KEY=<your-key> python scripts/download_india_datasets.py

# Option B - published demo key (works, but slow: ~30-60 min, rate-limited)
python scripts/download_india_datasets.py

# then, either option:
python scripts/build_external_datasets.py
DATABASE_URL=sqlite:///./backend/dev.db python scripts/register_external_datasets.py
DATABASE_URL=sqlite:///./backend/dev.db python scripts/run_external_benchmarks.py --seed 42
```

The raw file `raw/india_mandi_prices_raw.csv` is written once and then **never
modified**; it is gitignored.
