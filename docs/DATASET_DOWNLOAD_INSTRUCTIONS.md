# DecisionGPT — External Dataset Download Instructions

DecisionGPT's active external benchmark is a real **Indian** dataset. The
non-Indian datasets from the earlier task are **retired** (kept only for
reproducibility) and appear at the bottom of this file.

> No download here bypasses authentication, licensing, CAPTCHA, or terms of
> service. Where a source needs an account, manual steps are given and nothing
> is faked.

The **processed** CSVs (`data/external/<name>/processed/*.csv`) are committed
and are enough to register + benchmark-train. The **raw** files are *not*
committed (gitignored under `data/external/**/raw/`); you only need them to
regenerate the processed CSVs.

---

## 1. India Agri-Commodity Daily Market Prices (AGMARKNET) — ACTIVE

Genuine Indian benchmark. Public JSON REST API on data.gov.in — no login.

```bash
python scripts/download_india_datasets.py            # writes raw/india_mandi_prices_raw.csv
python scripts/build_external_datasets.py            # -> processed/*.csv (seed 42)
```

- **Source:** Open Government Data (OGD) Platform India — `data.gov.in`,
  resource `35985678-0d79-46b4-9ed6-6f13308a1d24`
  ("Variety-wise Daily Market Prices Data of Commodity").
  Directorate of Marketing & Inspection (DMI), Ministry of Agriculture &
  Farmers Welfare, Government of India. Underlying system: AGMARKNET.
- **Licence:** **Government Open Data License – India (GODL-India)** —
  <https://www.data.gov.in/Godl>. Free use with attribution.
- **Geography:** India (multi-state). `data_type: real`.
- **Fields:** `Arrival_Date, State, District, Market, Commodity, Variety,
  Grade, Min_Price, Max_Price, Modal_Price`. **No transaction-quantity field.**
- **Access notes:**
  - `download_india_datasets.py` uses the **demo API key that data.gov.in
    publishes in its own API docs**. That key is rate-limited to ~10
    records/call with a short burst window, so the script paginates with
    `sort[Arrival_Date]=asc`, paces requests, checkpoints each series under
    `raw/_parts/`, and resumes on restart. A full pull of the curated series
    list takes ~30–60 min on the demo key.
  - **Faster:** register a free key at <https://data.gov.in/user/register>
    (a manual, legitimate step — an account is required) and run with
    `DATA_GOV_IN_API_KEY=<your key> python scripts/download_india_datasets.py`.
    A registered key returns 1000 records/call, so the pull takes < 1 min.
  - The curated `(State, Commodity, Market)` series list is hard-coded in the
    script (deterministic). Edit `SERIES` there to change coverage.
- **Because the source has no quantity**, this is a **price-forecasting**
  benchmark: the canonical `units_sold` column carries the daily **modal
  price (INR/quintal)**; `price` is a 28-day backward rolling median (no
  leakage); `marketing_spend` / `promotion_flag` are `0` (absent in source —
  not invented). See `data/external/india_mandi_prices/metadata.md`.

## 2. A genuine Indian *transaction-level* / *churn* dataset — PENDING (manual)

Not integrated. Every Indian retail/e-commerce **transaction** dataset with the
required shape (date, product/category, quantity, price/revenue, customer) that
was located is **behind a Kaggle account + rules acceptance** (e.g.
"Amazon Sale Report (India)", "E-commerce Sales Dataset"), or lacks a date
column ("BigMart Sales" — no clearly-licensed public mirror), or is
commodity-price-only ("Department of Consumer Affairs" retail prices — SPA-only
catalog, no generic API resource). Bypassing Kaggle auth is not permitted, so
this is documented for manual acquisition and is **not** part of the automatic
integration. The synthetic churn dataset is retained for controlled churn
experiments.

To add one yourself:

1. Pick ONE and record its **licence** and whether it is **real or synthetic**.
2. Download it **through the source's own UI/API after accepting its terms**.
   Do not scrape.
3. Put raw file(s) in `data/external/indian_business/raw/` (create the folder).
4. Write `data/external/indian_business/{metadata.json, metadata.md}` following
   `data/external/india_mandi_prices/` (source, source_url, **verified
   licence**, citation, download_date, `geography: "India"`, `data_type`).
5. Add `ml/preprocessing/indian_business_adapter.py` mapping columns to a
   canonical schema (`series_id, date, units_sold, price, marketing_spend=0,
   promotion_flag=0` for forecasting; the churn canonical for churn). Reuse the
   leakage-safe `build_forecasting_features` / `chronological_split` /
   stratified split.
6. Wire it into `scripts/build_external_datasets.py`,
   `scripts/register_external_datasets.py`,
   `scripts/run_external_benchmarks.py` (mirror the `india` entries).
7. Re-run the regression suite.

---

## RETIRED — non-Indian datasets (reproducibility only)

Retired from the active evaluation because DecisionGPT targets Indian SMEs.
Data + metadata + adapters live under `data/external/_retired_non_indian/`.
Reproduce with the `--retired` flag:

```bash
python scripts/build_external_datasets.py    --retired
python scripts/register_external_datasets.py --retired
python scripts/run_external_benchmarks.py    --retired
```

### R1. UCI Online Retail — UK
```bash
mkdir -p data/external/_retired_non_indian/uci_online_retail/raw
curl -L -o data/external/_retired_non_indian/uci_online_retail/raw/online_retail.zip \
  "https://archive.ics.uci.edu/static/public/352/online+retail.zip"
cd data/external/_retired_non_indian/uci_online_retail/raw && unzip -o online_retail.zip
```
UCI ML Repository dataset 352 · CC BY 4.0 · `Online Retail.xlsx` MD5 `8f8e6d94ba88f976f4d8290cb2dea7fd`.

### R2. Supermarket Sales — Myanmar
```bash
mkdir -p data/external/_retired_non_indian/regional_retail/raw
curl -L -o data/external/_retired_non_indian/regional_retail/raw/supermarket_sales.csv \
  "https://raw.githubusercontent.com/plotly/datasets/master/supermarket_Sales.csv"
```
Plotly MIT-licensed `datasets` repo · `supermarket_sales.csv` MD5 `b281aeb11d2676751186461d83bdfc99` · Myanmar, **not India**.

### R3. M5 Forecasting — USA
```bash
mkdir -p data/external/_retired_non_indian/m5_forecasting/raw
curl -L -o data/external/_retired_non_indian/m5_forecasting/raw/m5.zip \
  "https://github.com/Nixtla/m5-forecasts/raw/main/datasets/m5.zip"
cd data/external/_retired_non_indian/m5_forecasting/raw && unzip -o m5.zip
```
M5 competition (Walmart) via Nixtla's MIT mirror · `m5.zip` MD5 `333d81b51e52a6f7a20540a2f0f092bf`.
Original Kaggle path: free account + `kaggle competitions download -c m5-forecasting-accuracy`.
Citation: Makridakis, S., Spiliotis, E., & Assimakopoulos, V. (2022). *The M5 competition.* IJF 38(4), 1325–1336.
