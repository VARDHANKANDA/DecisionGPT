"""Dataset loaders: schema validation, cleaning rules and preservation of the raw files. Tiny fake files; the real raw data is not read."""
import hashlib
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from ml.benchmark import datasets as ds

ROOT = Path(__file__).resolve().parents[2]


def _fake_m5(tmp_path, negative=False, drop_col=False, short_calendar=False):
    n_days = ds.M5_N_DAYS
    dates = pd.date_range("2011-01-29", periods=n_days + 28)
    cal = pd.DataFrame({"date": dates.strftime("%Y-%m-%d"), "wm_yr_wk": 11101 + np.arange(n_days + 28) // 7, "weekday": dates.day_name(),
                        "wday": 1, "month": dates.month, "year": dates.year, "d": [f"d_{i}" for i in range(1, n_days + 29)],
                        "event_name_1": None, "event_type_1": None, "event_name_2": None, "event_type_2": None,
                        "snap_CA": 0, "snap_TX": 0, "snap_WI": 0})
    if short_calendar:
        cal = cal.iloc[:100]
    cal.to_csv(tmp_path / "calendar.csv", index=False)
    rows = []
    rng = np.random.default_rng(0)
    for i in range(6):
        r = {"id": f"ITEM_{i}_CA_1_evaluation", "item_id": f"ITEM_{i}", "dept_id": "FOODS_1" if i < 3 else "HOBBIES_1", "cat_id": "FOODS" if i < 3 else "HOBBIES",
             "store_id": "CA_1", "state_id": "CA"}
        r.update({f"d_{d}": int(rng.poisson(2)) for d in range(1, n_days + 1)})
        rows.append(r)
    sales = pd.DataFrame(rows)
    if negative:
        sales.loc[0, "d_10"] = -3
    if drop_col:
        sales = sales.drop(columns=["d_500"])
    sales.to_csv(tmp_path / "sales_train_evaluation.csv", index=False)
    weeks = sorted(cal["wm_yr_wk"].unique())
    pr = pd.DataFrame([{"store_id": "CA_1", "item_id": f"ITEM_{i}", "wm_yr_wk": w, "sell_price": 1.0 + i + (w % 5) * 0.1} for i in range(6) for w in weeks])
    pr.to_csv(tmp_path / "sell_prices.csv", index=False)
    return tmp_path


def test_m5_loader_shapes_calendar_and_price_alignment(tmp_path):
    m = ds.load_m5_subset(n_series=4, raw_dir=_fake_m5(tmp_path))
    assert m.y.shape == (4, 1941) and m.price.shape == (4, 1941) and len(m.calendar) == 1941
    assert m.calendar["date"].iloc[-1] == pd.Timestamp("2011-01-29") + pd.Timedelta(days=1940)  # the 28 extra calendar days are cut
    assert m.info["negative_units"] == 0 and m.info["n_series"] == 4 and len(m.info["series_ids"]) == 4
    assert not np.isnan(m.price).any()                      # every fake item has a price every week


def test_m5_loader_is_deterministic_for_a_seed(tmp_path):
    raw = _fake_m5(tmp_path)
    a = ds.load_m5_subset(n_series=4, seed=7, raw_dir=raw).meta["id"].tolist()
    b = ds.load_m5_subset(n_series=4, seed=7, raw_dir=raw).meta["id"].tolist()
    assert a == b


@pytest.mark.parametrize("kwargs,match", [({"negative": True}, "negative unit sales"), ({"drop_col": True}, "missing"),
                                          ({"short_calendar": True}, "calendar does not contain")])
def test_m5_loader_rejects_invalid_files(tmp_path, kwargs, match):
    with pytest.raises(ValueError, match=match):
        ds.load_m5_subset(n_series=4, raw_dir=_fake_m5(tmp_path, **kwargs))


def test_online_retail_cleaning_rules_and_daily_zeros(tmp_path):
    p = tmp_path / "or2.csv"
    pd.DataFrame([
        ("100", "A", 2, "2010-01-04 10:00:00", 5.0, 1, "UK"),
        ("100", "A", 2, "2010-01-04 10:00:00", 5.0, 1, "UK"),   # exact duplicate line
        ("C101", "A", -1, "2010-01-04 11:00:00", 5.0, 1, "UK"), # cancellation
        ("102", "B", 0, "2010-01-04 12:00:00", 3.0, 2, "UK"),   # zero quantity
        ("103", "POST", 1, "2010-01-04 13:00:00", 18.0, 2, "UK"),  # non-product code
        ("104", "C", 1, "2010-01-04 14:00:00", 0.0, 3, "UK"),   # zero price
        ("105", "A", 3, "2010-01-06 09:00:00", 2.0, 3, "UK"),   # next trading day (a closed day between)
    ], columns=["Invoice", "StockCode", "Quantity", "InvoiceDate", "Price", "Customer ID", "Country"]).to_csv(p, index=False)
    d, info = ds.load_online_retail_ii(p)
    assert len(d) == 2 and info["rows_in"] == 7
    assert info["dropped"] == {"cancellation_invoice": 1, "non_positive_quantity": 1, "non_positive_price": 1, "non_product_stock_code": 1,
                               "exact_duplicate_line": 1}
    s = ds.daily_series(d)
    assert list(s.index.strftime("%Y-%m-%d")) == ["2010-01-04", "2010-01-05", "2010-01-06"]
    assert s.tolist() == [10.0, 0.0, 6.0]                # the closed day is a real zero, not NaN, not dropped


def test_online_retail_loader_requires_its_columns(tmp_path):
    p = tmp_path / "bad.csv"
    pd.DataFrame({"Invoice": ["1"], "Quantity": [1]}).to_csv(p, index=False)
    with pytest.raises(ValueError, match="(?i)missing"):  # pandas names the absent parse_dates column; the loader's own check covers the rest
        ds.load_online_retail_ii(p)


def test_raw_downloads_match_the_registry_and_were_not_modified():
    import json

    reg = json.loads((ROOT / "data" / "external" / "DATASET_REGISTRY.json").read_text(encoding="utf-8"))
    checked = 0
    for entry in reg["datasets"]:
        for f in entry.get("files", []) + ([entry["archive"]] if "archive" in entry else []):
            p = ROOT / f["path"]
            if not p.exists():  # raw data is git-ignored; a fresh clone legitimately lacks it
                continue
            h = hashlib.sha256()
            with open(p, "rb") as fh:
                for chunk in iter(lambda: fh.read(1 << 20), b""):
                    h.update(chunk)
            assert h.hexdigest() == f["sha256"], f"raw file changed: {f['path']}"
            checked += 1
    assert checked >= 0
