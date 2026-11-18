"""Adapters for the openly-licensed Indian business datasets
(Benroshan e-commerce = INDIA_REAL_BUSINESS; Kundan = SYNTHETIC_INDIAN_CONTEXT).

Tiny synthetic RAW fixtures - the real raw files are gitignored.
"""
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from ml.preprocessing import FORECASTING_CANONICAL_COLUMNS, india_customer_adapter, india_ecommerce_adapter


# --- Benroshan e-commerce -------------------------------------------------


def _ecom_raw(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    rng = np.random.default_rng(0)
    orders, details = [], []
    start = datetime(2018, 4, 1)
    oid = 25600
    for i in range(120):
        oid += 1
        d = start + timedelta(days=int(rng.integers(0, 360)))
        state = ["Maharashtra", "Gujarat", "Delhi", "Karnataka"][i % 4]
        orders.append({"Order ID": f"B-{oid}", "Order Date": d.strftime("%d-%m-%Y"),
                       "CustomerName": f"Cust{i}", "State": state, "City": "X"})
        for _ in range(int(rng.integers(1, 4))):
            cat = ["Furniture", "Clothing", "Electronics"][int(rng.integers(0, 3))]
            details.append({"Order ID": f"B-{oid}", "Amount": float(rng.integers(50, 3000)),
                            "Profit": float(rng.integers(-500, 800)), "Quantity": int(rng.integers(1, 10)),
                            "Category": cat, "Sub-Category": "sub"})
    # 5 trailing all-NaN rows that must be dropped
    for _ in range(5):
        orders.append({k: np.nan for k in ["Order ID", "Order Date", "CustomerName", "State", "City"]})
    pd.DataFrame(orders).to_csv(raw / "List of Orders.csv", index=False)
    pd.DataFrame(details).to_csv(raw / "Order Details.csv", index=False)
    tgt = [{"Month of Order Date": (start + pd.DateOffset(months=m)).strftime("%b-%y"),
            "Category": c, "Target": 10000 + m * 100}
           for m in range(12) for c in ["Furniture", "Clothing", "Electronics"]]
    pd.DataFrame(tgt).to_csv(raw / "Sales target.csv", index=False)
    return raw


def test_ecommerce_analytics_and_targets(tmp_path):
    raw = _ecom_raw(tmp_path)
    an = india_ecommerce_adapter.build_analytics(raw)
    for col in ("category", "State", "orders", "units", "revenue", "profit", "margin_pct", "avg_order_value"):
        assert col in an.columns
    assert (an["orders"] >= 1).all()
    ta = india_ecommerce_adapter.build_target_attainment(raw)
    assert {"category", "month", "actual_revenue", "target", "attainment_pct"} <= set(ta.columns)


def test_ecommerce_forecasting_frame(tmp_path):
    raw = _ecom_raw(tmp_path)
    fc = india_ecommerce_adapter.build_forecasting(raw)
    assert list(fc.columns) == FORECASTING_CANONICAL_COLUMNS
    assert fc["series_id"].nunique() == 1
    assert (fc["marketing_spend"] == 0).all() and (fc["promotion_flag"] == 0).all()
    assert (fc["units_sold"] >= 0).all()
    assert (fc["price"] > 0).all()               # derived implied unit price, ffilled
    # zero-filled: it is a contiguous daily calendar
    d = pd.to_datetime(fc["date"])
    assert (d.diff().dropna() == pd.Timedelta(days=1)).all()


def test_ecommerce_adapter_deterministic(tmp_path):
    raw = _ecom_raw(tmp_path)
    pd.testing.assert_frame_equal(
        india_ecommerce_adapter.build_forecasting(raw), india_ecommerce_adapter.build_forecasting(raw)
    )


# --- Kundan customer behaviour (SIMULATED) ------------------------------


def _cust_raw(tmp_path, n=400):
    raw = tmp_path / "raw"
    raw.mkdir()
    rng = np.random.default_rng(1)
    purchased = rng.integers(0, 2, n)
    df = pd.DataFrame({
        "customer_id": range(n), "session_id": range(n),
        "visit_date": "01-06-2024",
        "unit_price": rng.uniform(50, 2000, n).round(2),
        "quantity": rng.integers(1, 5, n),
        "discount_percent": rng.integers(0, 30, n),
        "discount_amount": rng.uniform(0, 400, n).round(2),
        "pages_viewed": rng.integers(1, 30, n),
        "time_on_site_sec": rng.integers(10, 2000, n),
        "added_to_cart": rng.integers(0, 2, n),
        "device_type": rng.integers(0, 3, n), "user_type": rng.integers(0, 2, n),
        "marketing_channel": rng.integers(0, 6, n), "product_category": rng.integers(0, 8, n),
        "visit_month": rng.integers(1, 13, n), "visit_weekday": rng.integers(0, 7, n),
        "visit_season": rng.integers(0, 4, n),
        "purchased": purchased,
        # leakage columns that MUST be excluded
        "revenue": np.where(purchased == 1, rng.uniform(100, 5000, n), 0.0),
        "revenue_normalized": 0.0,
        "cart_abandoned": 1 - purchased,
        "rating": rng.integers(1, 6, n),
        "review_text": rng.integers(0, 5, n),
    })
    df.to_csv(raw / "Ecommerce.csv", index=False)
    return raw


def test_customer_purchase_prediction_frame_no_leakage(tmp_path):
    raw = _cust_raw(tmp_path)
    pp = india_customer_adapter.build_purchase_prediction(raw)
    assert set(pp.columns) == set(india_customer_adapter.FEATURE_COLUMNS) | {"purchased"}
    for leak in ("revenue", "revenue_normalized", "cart_abandoned", "rating", "review_text"):
        assert leak not in pp.columns
    assert set(pp["purchased"].unique()) <= {0, 1}
    assert pp["purchased"].nunique() == 2


def test_customer_adapter_deterministic(tmp_path):
    raw = _cust_raw(tmp_path)
    pd.testing.assert_frame_equal(
        india_customer_adapter.build_purchase_prediction(raw),
        india_customer_adapter.build_purchase_prediction(raw),
    )


def test_committed_ecommerce_forecasting_trains_if_built():
    from pathlib import Path

    p = Path(__file__).resolve().parents[2] / "data/external/india_ecommerce/processed/india_ecommerce_forecasting.csv"
    if not p.exists():
        pytest.skip("india_ecommerce_forecasting.csv not built")
    from ml.training.train_forecasting import REQUIRED_COLUMNS, train_one

    df = pd.read_csv(p)
    assert all(c in df.columns for c in REQUIRED_COLUMNS)
    r = train_one(df, "naive", random_seed=42)
    assert r["metrics"]["mae"] >= 0 and r["test_rows"] > 0
