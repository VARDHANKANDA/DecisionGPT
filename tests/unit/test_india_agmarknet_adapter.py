"""India Agri-Commodity mandi-price adapter - contract, determinism, no-leakage.

Builds a tiny synthetic RAW csv (the real pull is gitignored) so this runs
fast on a fresh clone.
"""
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from ml.preprocessing import FORECASTING_CANONICAL_COLUMNS, india_agmarknet_adapter


def _raw(tmp_path, n_days=400):
    raw = tmp_path / "raw"
    raw.mkdir()
    rng = np.random.default_rng(0)
    rows = []
    start = datetime(2015, 1, 1)
    specs = [
        ("Maharashtra", "Onion", "Lasalgaon", 1500),
        ("Karnataka", "Tomato", "Kolar", 900),
    ]
    for state, commodity, market, base in specs:
        price = float(base)
        for i in range(n_days):
            price = max(200.0, price + rng.normal(0, base * 0.02))
            d = start + timedelta(days=i)
            modal = round(price, -1)
            rows.append(
                dict(
                    Arrival_Date=d.strftime("%d/%m/%Y"),
                    State=state, District="X", Market=market,
                    Commodity=commodity, Variety="Local", Grade="FAQ",
                    Min_Price=modal - 50, Max_Price=modal + 50, Modal_Price=modal,
                )
            )
            # a second same-day quote (different variety) - must be collapsed
            if i % 7 == 0:
                rows.append(
                    dict(
                        Arrival_Date=d.strftime("%d/%m/%Y"),
                        State=state, District="X", Market=market,
                        Commodity=commodity, Variety="Other", Grade="Medium",
                        Min_Price=modal - 30, Max_Price=modal + 70, Modal_Price=modal + 20,
                    )
                )
    # junk rows that must be dropped
    rows.append(dict(Arrival_Date="bad-date", State="Maharashtra", District="X",
                     Market="Lasalgaon", Commodity="Onion", Variety="L", Grade="F",
                     Min_Price=1, Max_Price=1, Modal_Price=0))
    pd.DataFrame(rows).to_csv(raw / "india_agmarknet_raw.csv", index=False)
    return raw


def test_forecasting_schema_and_price_semantics(tmp_path):
    raw = _raw(tmp_path)
    fc = india_agmarknet_adapter.build_forecasting(raw)

    assert list(fc.columns)[:6] == FORECASTING_CANONICAL_COLUMNS
    assert (fc["marketing_spend"] == 0).all()
    assert (fc["promotion_flag"] == 0).all()
    assert (fc["units_sold"] > 0).all()
    assert (fc["price"] > 0).all()
    # documented semantics: the canonical units_sold slot carries the modal price
    assert np.allclose(fc["units_sold"].to_numpy(), fc["modal_price"].to_numpy())
    # one row per (series, date) after collapsing same-day variety quotes
    assert not fc.duplicated(["series_id", "date"]).any()
    assert fc["series_id"].str.startswith("MANDI_").all()
    assert fc["series_id"].nunique() == 2


def test_price_feature_is_backward_only_no_leakage(tmp_path):
    raw = _raw(tmp_path)
    fc = india_agmarknet_adapter.build_forecasting(raw).sort_values(["series_id", "date"])

    for _, g in fc.groupby("series_id"):
        modal = g["modal_price"].to_numpy()
        price = g["price"].to_numpy()
        # price[t] must be explainable purely by modal[:t] (a trailing median /
        # the series' first value) - never equal to a *future* modal value and
        # never using modal[t] itself.
        for t in range(1, len(g)):
            past = modal[:t]
            lo, hi = past.min(), past.max()
            assert lo - 1e-6 <= price[t] <= hi + 1e-6, (
                f"price[{t}]={price[t]} outside past range [{lo},{hi}] - leakage"
            )


def test_adapter_is_deterministic(tmp_path):
    raw = _raw(tmp_path)
    a = india_agmarknet_adapter.build_forecasting(raw)
    b = india_agmarknet_adapter.build_forecasting(raw)
    pd.testing.assert_frame_equal(a, b)


def test_regional_analytics_table(tmp_path):
    raw = _raw(tmp_path)
    an = india_agmarknet_adapter.build_regional_analytics(raw)
    for col in ("State", "Commodity", "month", "avg_modal_price",
                "price_volatility_std", "avg_spread_pct", "active_markets",
                "mom_pct_change"):
        assert col in an.columns
    assert (an["avg_modal_price"] > 0).all()
    assert (an["price_volatility_std"] >= 0).all()
    assert (an["active_markets"] >= 1).all()


def test_committed_india_processed_file_trains(tmp_path):
    from pathlib import Path

    p = (Path(__file__).resolve().parents[2]
         / "data/external/india_agmarknet/processed/india_agmarknet_forecasting.csv")
    if not p.exists():
        pytest.skip("india_agmarknet_forecasting.csv not built "
                    "(run scripts/download_india_datasets.py + build_external_datasets.py)")
    from ml.training.train_forecasting import REQUIRED_COLUMNS, train_one

    df = pd.read_csv(p)
    assert all(c in df.columns for c in REQUIRED_COLUMNS)
    r = train_one(df, "naive", random_seed=42)
    assert r["metrics"]["mae"] >= 0 and r["test_rows"] > 0
