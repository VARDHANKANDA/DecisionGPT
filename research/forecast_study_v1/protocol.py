"""Datasets, windows and demand segments of the forecasting study (all fixed in EXPERIMENT_PLAN.md before any new result was inspected).

Window design (days are 0-based column indices of the ``[series, day]`` matrices, ``T`` = number of days):
  * 6 retraining origins, one per 28-day block, covering the LAST 168 days: block starts  T-168, T-140, ..., T-28  (the last block ends at T-1).
  * 3 validation blocks immediately before them: starts T-252, T-224, T-196. Variant/family/baseline selection uses ONLY these.
  * For a block starting at ``o`` the learned model is trained on rows whose TARGET day is in ``[o-730, o-1]`` and forecasts target days ``[o, o+27]`` with
    features whose minimum lag is ``H`` (so day ``t`` uses history up to ``t - H`` and no information after day ``o - 1`` is used to fit anything).
  * H in {7, 28}: ``H`` is the minimum lag of the features (the staleness of the freshest history input), the "forecast horizon" in the direct strategy.
For M5 (T = 1941) the last block is exactly the official evaluation window (d_1914..d_1941).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from ml.benchmark import datasets as ds
from ml.benchmark import f2_retail as f2
from ml.benchmark import features as ft

BLOCK = 28
N_TEST = 6
N_VAL = 3
TRAIN_SPAN = 730
MIN_HISTORY = 84
HORIZONS = (7, 28)
DATASETS = ("m5_ca1", "m5_tx1", "or2_top100")
SEGMENT_HISTORY = 365          # days before the first validation block used to classify series (no information from validation or test windows)
ADI_CUTOFF, CV2_CUTOFF = 1.32, 0.49   # Syntetos-Boylan convention (also used by forecast_validation_service)


@dataclass
class Dataset:
    key: str
    y: np.ndarray
    price: np.ndarray
    cal: pd.DataFrame
    static: dict[str, np.ndarray]
    series_ids: list[str]
    dates: pd.DatetimeIndex
    drop_features: tuple[str, ...]
    info: dict[str, Any] = field(default_factory=dict)

    @property
    def T(self) -> int:
        return self.y.shape[1]


def windows(T: int) -> dict[str, list[int]]:
    test = [T - BLOCK * N_TEST + BLOCK * k for k in range(N_TEST)]
    val = [test[0] - BLOCK * (N_VAL - j) for j in range(N_VAL)]
    return {"test": test, "val": val}


def load(key: str) -> Dataset:
    if key in ("m5_ca1", "m5_tx1"):
        store = {"m5_ca1": "CA_1", "m5_tx1": "TX_1"}[key]
        m = ds.load_m5_subset(store=store, n_series=350)
        static = {k: m.meta[c].astype("category").cat.codes.to_numpy() for k, c in (("dept_code", "dept_id"), ("cat_code", "cat_id"), ("item_code", "item_id"))}
        return Dataset(key, m.y, m.price, m.calendar, static, m.meta["id"].tolist(), pd.DatetimeIndex(m.calendar["date"]), (), m.info)
    if key == "or2_top100":
        d, info = ds.load_online_retail_ii()
        full, _, _, _ = f2.build_arrays(d)
        first_val = windows(len(full))["val"][0]
        full, _, units, top = f2.build_arrays(d, top_k=100, first_val_origin=first_val)
        cal = f2._calendar(full)
        n = units.shape[0]
        static = {"dept_code": np.zeros(n), "cat_code": np.zeros(n), "item_code": np.arange(n)}
        info = dict(info) | {"top_skus_rule": "100 SKUs with the largest revenue before the first validation block", "n_series": n}
        return Dataset(key, units, np.ones_like(units, dtype=np.float32), cal, static, [str(s) for s in top], pd.DatetimeIndex(full),
                       ("sell_price", "rel_price_91", "price_change_7", "days_since_price_change", "dept_code", "cat_code"), info)
    raise ValueError(key)


def build_features(d: Dataset, H: int):
    """Leakage-safe direct features (historical builder, unchanged) with the dataset's dropped columns removed, and the valid-row mask."""
    F, names = ft.build_direct_features(d.y, d.price, d.cal, d.static, H)
    valid = ft.valid_mask(d.y, d.price, H, MIN_HISTORY)
    if d.drop_features:
        keep = [i for i, n in enumerate(names) if n not in d.drop_features]
        F, names = F[:, :, keep], [names[i] for i in keep]
        valid = np.ones_like(valid, dtype=bool)
        valid[:, : H + MIN_HISTORY] = False
    return F, names, valid


def segments(y: np.ndarray, first_val_start: int) -> dict[str, Any]:
    """Demand-frequency and volume segments from the SEGMENT_HISTORY days before the first validation block (nothing from validation or test)."""
    h = y[:, max(0, first_val_start - SEGMENT_HISTORY): first_val_start].astype(float)
    nz = (h > 0).sum(axis=1)
    adi = np.where(nz > 0, h.shape[1] / np.maximum(nz, 1), np.inf)
    cv2 = np.full(y.shape[0], np.nan)
    for i in range(y.shape[0]):
        v = h[i][h[i] > 0]
        cv2[i] = (v.std(ddof=0) / v.mean()) ** 2 if v.size > 1 else 0.0
    pattern = np.where(adi < ADI_CUTOFF, np.where(cv2 < CV2_CUTOFF, "smooth", "erratic"), np.where(cv2 < CV2_CUTOFF, "intermittent", "lumpy"))
    freq = np.where(adi < ADI_CUTOFF, "frequent", "intermittent_or_sparse")
    mean = h.mean(axis=1)
    cuts = np.quantile(mean, [1 / 3, 2 / 3])
    volume = np.where(mean <= cuts[0], "low", np.where(mean <= cuts[1], "mid", "high"))
    return {"adi": adi.tolist(), "cv2": cv2.tolist(), "pattern": pattern.tolist(), "frequency": freq.tolist(), "volume": volume.tolist(), "volume_cuts": [float(c) for c in cuts],
            "history_days": int(h.shape[1]), "counts": {k: {v: int((np.asarray(a) == v).sum()) for v in sorted(set(a))} for k, a in (("pattern", pattern), ("frequency", freq), ("volume", volume))}}


def assert_windows_ordered(T: int) -> dict[str, Any]:
    w = windows(T)
    val_end = w["val"][-1] + BLOCK - 1
    ok = (val_end < w["test"][0] and w["test"][-1] + BLOCK - 1 == T - 1 and all(w["test"][i] + BLOCK == w["test"][i + 1] for i in range(N_TEST - 1))
          and all(w["val"][i] + BLOCK == w["val"][i + 1] for i in range(N_VAL - 1)) and w["val"][-1] + BLOCK == w["test"][0])
    if not ok:
        raise AssertionError(f"windows overlap or leave a gap: {w}")
    return {"validation_blocks": [[o, o + BLOCK - 1] for o in w["val"]], "test_blocks": [[o, o + BLOCK - 1] for o in w["test"]], "disjoint_and_ordered": True,
            "train_rows_target_days": "[o-730, o-1] for each block start o"}
