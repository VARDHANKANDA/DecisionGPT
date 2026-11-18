"""Leakage-safe features for direct multi-step demand forecasting.

Direct strategy with horizon ``H``: the features for target day ``t`` use the sales history up to day ``t - H`` only (``o = t - H`` is
the forecast origin). Known-in-advance covariates (calendar, selling price, SNAP flag, events) may use day ``t`` itself because M5
publishes them ahead of time; nothing derived from the target ``y`` at or after ``t - H + 1`` ever enters a row.

All arrays are indexed ``[series, day]``; feature tensors are ``[series, day, feature]`` with NaN where the history is too short.
``assert_no_future_leakage`` perturbs the future and checks that no feature at an earlier origin changes.
"""
from __future__ import annotations

import warnings

import numpy as np

LAG_OFFSETS = (0, 7, 14, 21, 28)  # lags H + offset
ROLL_WINDOWS = (7, 28, 84)


def _shift_right(a: np.ndarray, k: int) -> np.ndarray:
    """out[:, t] = a[:, t - k] (NaN for t < k). ``a`` is [series, day]."""
    out = np.full_like(a, np.nan, dtype=np.float32)
    if k < a.shape[1]:
        out[:, k:] = a[:, : a.shape[1] - k]
    return out


def _window_mean_std(y: np.ndarray, w: int) -> tuple[np.ndarray, np.ndarray]:
    """Mean and std of the w days ending at each index (inclusive); NaN until w days exist."""
    cs = np.concatenate([np.zeros((y.shape[0], 1)), np.cumsum(y.astype(np.float64), axis=1)], axis=1)
    cs2 = np.concatenate([np.zeros((y.shape[0], 1)), np.cumsum(y.astype(np.float64) ** 2, axis=1)], axis=1)
    T = y.shape[1]
    mean = np.full(y.shape, np.nan, dtype=np.float64)
    var = np.full(y.shape, np.nan, dtype=np.float64)
    if T >= w:
        s = cs[:, w:] - cs[:, : T - w + 1]
        s2 = cs2[:, w:] - cs2[:, : T - w + 1]
        mean[:, w - 1:] = s / w
        var[:, w - 1:] = np.maximum(s2 / w - (s / w) ** 2, 0.0)
    return mean.astype(np.float32), np.sqrt(var).astype(np.float32)


def feature_names(H: int) -> list[str]:
    names = [f"lag_{H + o}" for o in LAG_OFFSETS]
    names += [f"roll_mean_{w}" for w in ROLL_WINDOWS] + ["roll_std_28", "nonzero_share_28", "days_since_sale", "same_weekday_mean4"]
    names += ["dow", "dom", "month", "event", "snap", "sell_price", "rel_price_91", "price_change_7", "days_since_price_change", "dept_code", "cat_code", "item_code"]
    return names


def build_direct_features(y: np.ndarray, price: np.ndarray, cal, static: dict[str, np.ndarray], H: int = 28) -> tuple[np.ndarray, list[str]]:
    """Feature tensor [series, day, feature] for target day ``day`` with origin ``day - H``."""
    n, T = y.shape
    y = y.astype(np.float32)
    feats: list[np.ndarray] = []
    # history features are computed AT the origin index e, then shifted forward by H so row t holds the value known at t - H
    for o in LAG_OFFSETS:
        feats.append(_shift_right(y, H + o))
    for w in ROLL_WINDOWS:
        m, s = _window_mean_std(y, w)
        feats.append(_shift_right(m, H))
        if w == 28:
            std28 = _shift_right(s, H)
    feats.append(std28)
    nz, _ = _window_mean_std((y > 0).astype(np.float32), 28)
    feats.append(_shift_right(nz, H))
    idx = np.broadcast_to(np.arange(T), (n, T))
    last = np.maximum.accumulate(np.where(y > 0, idx, -1), axis=1)
    dsl = np.where(last < 0, 365, np.minimum(idx - last, 365)).astype(np.float32)
    feats.append(_shift_right(dsl, H))
    sw = (feats[0] + feats[1] + feats[2] + feats[3]) / 4.0  # lag_H, lag_H+7, lag_H+14, lag_H+21
    feats.append(sw.astype(np.float32))
    # calendar (known at target day)
    for col in ("dow", "dom", "month", "event", "snap"):
        feats.append(np.broadcast_to(np.asarray(cal[col], dtype=np.float32), (n, T)).copy())
    # price features (selling prices are published in advance; they may use day t and earlier prices only)
    feats.append(price.astype(np.float32))
    med = np.full(price.shape, np.nan, dtype=np.float32)
    for t in range(T):
        lo = max(0, t - 90)
        win = price[:, lo: t + 1]
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)  # all-NaN windows (item not on sale yet) give NaN by design
            med[:, t] = np.nanmedian(win, axis=1)
    feats.append((price / med).astype(np.float32))
    prev7 = _shift_right(price.astype(np.float32), 7)
    feats.append((price / prev7 - 1.0).astype(np.float32))
    # days since the price last changed (as known at day t)
    changed = np.zeros(price.shape, dtype=bool)
    changed[:, 1:] = ~np.isclose(price[:, 1:], price[:, :-1], equal_nan=True)
    lastc = np.maximum.accumulate(np.where(changed, idx, 0), axis=1)
    feats.append(np.minimum(idx - lastc, 365).astype(np.float32))
    for key in ("dept_code", "cat_code", "item_code"):
        feats.append(np.broadcast_to(np.asarray(static[key], dtype=np.float32)[:, None], (n, T)).copy())
    F = np.stack(feats, axis=2).astype(np.float32)
    names = feature_names(H)
    assert F.shape[2] == len(names), (F.shape, len(names))
    return F, names


def valid_mask(y: np.ndarray, price: np.ndarray, H: int = 28, min_history: int = 84) -> np.ndarray:
    """Rows usable for training / scoring: the item is on sale on the target day and at least ``min_history`` days precede the origin."""
    n, T = y.shape
    ok = ~np.isnan(price)
    ok[:, : H + min_history] = False
    return ok


def assert_no_future_leakage(y: np.ndarray, price: np.ndarray, cal, static, H: int, origin: int, rng_seed: int = 0) -> bool:
    """Perturb ``y`` strictly after ``origin`` and verify the features of every target day ``t <= origin + H`` that was computable at the
    origin are unchanged for history-derived columns. Returns True when no leakage is detected."""
    F0, names = build_direct_features(y, price, cal, static, H)
    y2 = y.copy()
    rng = np.random.default_rng(rng_seed)
    y2[:, origin + 1:] = rng.integers(0, 50, size=y2[:, origin + 1:].shape)
    F1, _ = build_direct_features(y2, price, cal, static, H)
    hist_cols = [i for i, n in enumerate(names) if n.startswith(("lag_", "roll_", "nonzero", "days_since_sale", "same_weekday"))]
    sl = slice(0, origin + H + 1)  # targets whose origin (t - H) <= origin
    a, b = F0[:, sl][:, :, hist_cols], F1[:, sl][:, :, hist_cols]
    return bool(np.array_equal(a, b, equal_nan=True))
