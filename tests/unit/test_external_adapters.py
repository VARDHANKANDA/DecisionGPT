"""External benchmark adapters - contract, determinism, and leakage checks.

These build tiny synthetic RAW fixtures (the real multi-GB raw files are
gitignored), so they run fast and on a fresh clone.
"""
from datetime import datetime, timedelta

import pandas as pd
import pytest

from ml.preprocessing import (
    CHURN_CANONICAL_COLUMNS,
    FORECASTING_CANONICAL_COLUMNS,
    m5_adapter,
    supermarket_sales_adapter,
    uci_online_retail_adapter,
)


# --- UCI Online Retail --------------------------------------------------


def _uci_raw(tmp_path):
    """~10 customers, invoices across the observation and holdout windows."""
    rows = []
    inv = 1000
    # observation window purchases (all customers active here)
    for cid in range(10):
        for k in range(3):
            inv += 1
            rows.append(
                dict(
                    InvoiceNo=str(inv),
                    StockCode=f"SKU{cid % 4}",
                    Description="x",
                    Quantity=5 + k,
                    InvoiceDate=datetime(2011, 3, 1) + timedelta(days=cid * 5 + k),
                    UnitPrice=2.5,
                    CustomerID=17000 + cid,
                    Country="United Kingdom",
                )
            )
    # holdout window: only customers 0-5 return -> 6,7,8,9 are "churned"
    for cid in range(6):
        inv += 1
        rows.append(
            dict(
                InvoiceNo=str(inv),
                StockCode="SKU0",
                Description="x",
                Quantity=4,
                InvoiceDate=datetime(2011, 10, 15) + timedelta(days=cid),
                UnitPrice=3.0,
                CustomerID=17000 + cid,
                Country="United Kingdom",
            )
        )
    # a cancellation + a bad row that must be dropped
    rows.append(dict(InvoiceNo="C9999", StockCode="SKU0", Description="x", Quantity=-3,
                     InvoiceDate=datetime(2011, 3, 2), UnitPrice=2.5, CustomerID=17000, Country="UK"))
    rows.append(dict(InvoiceNo="8888", StockCode="POST", Description="postage", Quantity=1,
                     InvoiceDate=datetime(2011, 3, 2), UnitPrice=18.0, CustomerID=17001, Country="UK"))
    raw = tmp_path / "raw"
    raw.mkdir()
    pd.DataFrame(rows).to_excel(raw / "Online Retail.xlsx", index=False)
    return raw


def test_uci_forecasting_schema_and_cleaning(tmp_path):
    raw = _uci_raw(tmp_path)
    fc = uci_online_retail_adapter.build_forecasting(raw, top_n_products=4)
    assert list(fc.columns) == FORECASTING_CANONICAL_COLUMNS
    assert (fc["marketing_spend"] == 0).all()
    assert (fc["promotion_flag"] == 0).all()
    assert (fc["units_sold"] > 0).all()          # cancellation + negative dropped
    assert not fc["series_id"].str.contains("POST").any()  # non-product code dropped


def test_uci_derived_churn_label_is_time_aware_and_no_leakage(tmp_path):
    raw = _uci_raw(tmp_path)
    churn = uci_online_retail_adapter.build_churn_derived(raw)
    assert list(churn.columns) == CHURN_CANONICAL_COLUMNS
    assert set(churn["churned"].unique()) == {0, 1}
    # customers 6-9 had no holdout-window purchase -> churned; 0-5 -> not.
    assert churn["churned"].sum() == 4
    assert (churn["churned"] == 0).sum() == 6
    # recency is measured from the observation-window end, never negative,
    # and never uses a holdout-window date (holdout is mid-Oct; observation
    # ends 2011-09-09, so max recency < ~200 days from the last obs purchase).
    assert (churn["recency_days"] >= 0).all()
    assert (churn["recency_days"] <= 200).all()


def test_uci_adapter_is_deterministic(tmp_path):
    raw = _uci_raw(tmp_path)
    a = uci_online_retail_adapter.build_forecasting(raw, top_n_products=4)
    b = uci_online_retail_adapter.build_forecasting(raw, top_n_products=4)
    pd.testing.assert_frame_equal(a, b)


# --- M5 ---------------------------------------------------------------


def _m5_raw(tmp_path, n_days=60):
    raw = tmp_path / "raw"
    raw.mkdir()
    d_cols = [f"d_{i + 1}" for i in range(n_days)]
    sales = pd.DataFrame(
        [
            {"item_id": "FOODS_1_001", "dept_id": "FOODS_1", "cat_id": "FOODS",
             "store_id": "CA_1", "state_id": "CA", **{c: (i % 5) for i, c in enumerate(d_cols)}},
            {"item_id": "FOODS_1_002", "dept_id": "FOODS_1", "cat_id": "FOODS",
             "store_id": "CA_1", "state_id": "CA", **{c: (i % 3 + 1) for i, c in enumerate(d_cols)}},
        ]
    )
    sales.to_csv(raw / "sales_train_evaluation.csv", index=False)
    start = datetime(2011, 1, 29)
    cal = pd.DataFrame(
        {
            "date": [(start + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(n_days)],
            "wm_yr_wk": [11101 + (i // 7) for i in range(n_days)],
            "weekday": "Saturday", "wday": 1, "month": 1, "year": 2011,
            "event_name_1": "NA", "event_type_1": "NA", "event_name_2": "NA",
            "event_type_2": "NA", "snap_CA": 0, "snap_TX": 0, "snap_WI": 0,
        }
    )
    cal.to_csv(raw / "calendar.csv", index=False)
    weeks = sorted(cal["wm_yr_wk"].unique())
    prices = pd.DataFrame(
        [{"store_id": "CA_1", "item_id": it, "wm_yr_wk": w, "sell_price": 3.5}
         for it in ("FOODS_1_001", "FOODS_1_002") for w in weeks]
    )
    prices.to_csv(raw / "sell_prices.csv", index=False)
    return raw


def test_m5_forecasting_schema_and_zero_marketing(tmp_path):
    raw = _m5_raw(tmp_path)
    fc = m5_adapter.build_forecasting(raw, n_series=2)
    assert list(fc.columns) == FORECASTING_CANONICAL_COLUMNS
    assert fc["series_id"].nunique() == 2
    assert (fc["marketing_spend"] == 0).all() and (fc["promotion_flag"] == 0).all()
    assert (fc["price"] > 0).all()
    assert fc["units_sold"].dtype.kind in "iu"
    # dates come from the real calendar, sorted per series
    assert fc.groupby("series_id")["date"].apply(lambda s: s.is_monotonic_increasing).all()


# --- Supermarket Sales (Myanmar) -----------------------------------


def _ss_raw(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    rows = []
    for i in range(39):
        d = datetime(2019, 1, 1) + timedelta(days=i)
        for br in ("A", "B"):
            for pl in ("Food and beverages", "Fashion accessories"):
                rows.append(
                    {
                        "Invoice ID": f"{br}{i}{pl[:2]}", "Branch": br, "City": "Yangon",
                        "Customer type": "Member", "Gender": "Female", "Product line": pl,
                        "Unit price": 10.0, "Quantity": (i % 4) + 1, "Tax 5%": 1.0,
                        "Total": ((i % 4) + 1) * 10.5, "Date": d.strftime("%m/%d/%Y"), "Time": "10:00",
                        "Payment": "Cash", "Cost of goods sold": ((i % 4) + 1) * 8.0,
                        "Gross margin percentage": 4.76, "Gross income": ((i % 4) + 1) * 2.5,
                        "Customer stratification rating": 7.0,
                    }
                )
    pd.DataFrame(rows).to_csv(raw / "supermarket_sales.csv", index=False)
    return raw


def test_supermarket_forecasting_and_analytics(tmp_path):
    raw = _ss_raw(tmp_path)
    fc = supermarket_sales_adapter.build_forecasting(raw)
    assert list(fc.columns) == FORECASTING_CANONICAL_COLUMNS
    assert fc["series_id"].nunique() == 4  # 2 branches x 2 product lines
    assert (fc["marketing_spend"] == 0).all()

    an = supermarket_sales_adapter.build_analytics(raw)
    for col in ("revenue", "cogs", "gross_income", "margin_pct"):
        assert col in an.columns
    assert (an["margin_pct"].between(0, 1)).all()


# --- processed files (if built) train through the real pipeline -------


@pytest.mark.parametrize(
    "path,task",
    [
        ("data/external/regional_retail/processed/regional_retail_forecasting.csv", "forecasting"),
        ("data/external/uci_online_retail/processed/uci_churn_derived.csv", "churn"),
    ],
)
def test_committed_processed_files_satisfy_training_contract(path, task):
    from pathlib import Path

    p = Path(__file__).resolve().parents[2] / path
    if not p.exists():
        pytest.skip(f"{path} not built (run scripts/build_external_datasets.py)")
    df = pd.read_csv(p)
    if task == "forecasting":
        from ml.training.train_forecasting import REQUIRED_COLUMNS, train_one

        assert all(c in df.columns for c in REQUIRED_COLUMNS)
        r = train_one(df, "naive", random_seed=42)
        assert r["metrics"]["mae"] >= 0 and r["test_rows"] > 0
    else:
        from ml.training.train_churn import train_one

        r = train_one(df, "logistic_regression", random_seed=42)
        assert 0.0 <= r["metrics"]["roc_auc"] <= 1.0 and r["test_rows"] > 0
