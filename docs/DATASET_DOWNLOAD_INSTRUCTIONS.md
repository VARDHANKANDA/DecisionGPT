# DecisionGPT — External Dataset Download Instructions

The **processed** benchmark CSVs (`data/external/<name>/processed/*.csv`) are
committed and are enough to register the datasets and run the benchmark
training (`scripts/register_external_datasets.py` +
`scripts/run_external_benchmarks.py`).

The **raw** files are *not* committed (they total ~580 MB and are gitignored
under `data/external/**/raw/`). You only need the raw files if you want to
**regenerate** the processed CSVs with `scripts/build_external_datasets.py`
(e.g. to change the subsample size or the churn window).

> No download here bypasses authentication, licensing, CAPTCHA, or terms of
> service. Where a source requires an account (Kaggle), manual steps are
> given and nothing is faked.

---

## 1. UCI Online Retail  — automatic, no account

```bash
mkdir -p data/external/uci_online_retail/raw
curl -L -o data/external/uci_online_retail/raw/online_retail.zip \
  "https://archive.ics.uci.edu/static/public/352/online+retail.zip"
cd data/external/uci_online_retail/raw && unzip -o online_retail.zip   # -> "Online Retail.xlsx"
```

- **Source:** UCI Machine Learning Repository, dataset 352 — <https://archive.ics.uci.edu/dataset/352/online+retail>
- **License:** CC BY 4.0
- **Expected files:** `raw/Online Retail.xlsx` (≈23 MB), `raw/online_retail.zip`
- **MD5:** `Online Retail.xlsx` = `8f8e6d94ba88f976f4d8290cb2dea7fd`

## 2. Supermarket Sales (Myanmar, regional)  — automatic, no account

```bash
mkdir -p data/external/regional_retail/raw
curl -L -o data/external/regional_retail/raw/supermarket_sales.csv \
  "https://raw.githubusercontent.com/plotly/datasets/master/supermarket_Sales.csv"
```

- **Origin:** "Supermarket sales" (attributed on Kaggle to *Aung Pyae*) — <https://www.kaggle.com/datasets/aungpyaeap/supermarket-sales>
- **Copy used:** Plotly's MIT‑licensed public `datasets` repo (link above).
- **Expected file:** `raw/supermarket_sales.csv` (≈131 KB). **MD5:** `b281aeb11d2676751186461d83bdfc99`
- **Note:** Myanmar, **not India**. Integrated as a regional emerging‑market retail benchmark.

## 3. M5 Forecasting  — public mirror OR manual Kaggle

### Option A — public mirror (used by this repo; no account)
```bash
mkdir -p data/external/m5_forecasting/raw
curl -L -o data/external/m5_forecasting/raw/m5.zip \
  "https://github.com/Nixtla/m5-forecasts/raw/main/datasets/m5.zip"
cd data/external/m5_forecasting/raw && unzip -o m5.zip
# -> calendar.csv, sales_train_validation.csv, sales_train_evaluation.csv,
#    sales_test_*.csv, sell_prices.csv, weights_*.csv
```
- **Mirror:** `github.com/Nixtla/m5-forecasts` — the redistribution used by Nixtla's MIT‑licensed `datasetsforecast` package. **MD5(`m5.zip`)** = `333d81b51e52a6f7a20540a2f0f092bf`.
- The **underlying M5 data is Walmart's**, released for the M5 competition; its terms are unchanged by redistribution. Verify the competition terms before redistributing your own copy.

### Option B — original Kaggle (requires a free Kaggle account + rules acceptance)
1. Create/sign in to a Kaggle account and open <https://www.kaggle.com/competitions/m5-forecasting-accuracy>.
2. Click **"Join Competition"** / accept the rules (one‑time).
3. `pip install kaggle`, place your `kaggle.json` API token in `~/.kaggle/`.
4. `kaggle competitions download -c m5-forecasting-accuracy -p data/external/m5_forecasting/raw`
5. `unzip` into `raw/`. You will get `calendar.csv`, `sales_train_evaluation.csv`, `sell_prices.csv`, etc.

- **Citation:** Makridakis, S., Spiliotis, E., & Assimakopoulos, V. (2022). *The M5 competition: Background, organization, and implementation.* International Journal of Forecasting, 38(4), 1325–1336.

---

## 4. A genuine Indian‑context retail dataset  — MANUAL (not auto‑integrated)

**No Indian retail transaction dataset with the required shape (date,
product/category, quantity, price/revenue) could be obtained without a
Kaggle account.** Bypassing Kaggle authentication is not permitted, so this
dataset is **documented for manual acquisition and is NOT part of the
automatic integration.** The regional Supermarket Sales dataset (Myanmar,
§2) is integrated instead, honestly labelled as regional — **the paper must
not describe it as Indian.**

To add a real Indian dataset yourself:

1. Pick ONE and record its **licence** and whether it is **real or synthetic**:
   - *"E‑commerce Sales Dataset" / "Amazon Sale Report" (India)* — Kaggle (various uploaders). Contains order date, SKU/category, qty, amount, ship‑state. Licence varies by upload — **check it**.
   - *"BigMart Sales"* — Kaggle. Indian retail *chain* context, but it has **no date column** → it does **not** fit the forecasting canonical schema without heavy reshaping; use only for descriptive analytics.
   - *data.gov.in* retail/consumption series (needs a free API key) — mostly commodity **price** series, not transaction‑level sales.
2. Download it **through the source's own UI/API after accepting its terms**. Do not scrape.
3. Place the raw file(s) in `data/external/indian_business/raw/` (create the folder).
4. Write `data/external/indian_business/{metadata.json, metadata.md}` following the pattern of the other three (source, source_url, **verified licence**, citation, download_date, `country_context: "India"`, `data_type`).
5. Add an adapter `ml/preprocessing/indian_business_adapter.py` mapping the columns to the forecasting canonical schema (`series_id, date, units_sold, price, marketing_spend=0, promotion_flag=0`). Reuse the leakage‑safe `build_forecasting_features` + `chronological_split`.
6. Wire it into `scripts/build_external_datasets.py`, `scripts/register_external_datasets.py`, `scripts/run_external_benchmarks.py` (mirror the `regional` entries).
7. Re‑run the regression suite.

Until then, the paper's Indian‑context claim should be limited to:
> *evaluated additionally on a regional (Southeast Asian) retail dataset; a
> genuine Indian‑context dataset integration path is documented but not yet
> populated.*
