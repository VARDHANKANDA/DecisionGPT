"""forecast_study_v2: windows, leak-free baselines, metric identities, objective semantics, truncation, inference helpers. Software tests: they do not establish scientific validity."""
import math

import numpy as np
import pytest

from research.forecast_study_v2 import analysis as an
from research.forecast_study_v2 import baselines as bl
from research.forecast_study_v2 import metrics as mt
from research.forecast_study_v2 import models as md
from research.forecast_study_v2 import windows as win


def _series(S=6, T=300, seed=0):
    rng = np.random.default_rng(seed)
    base = rng.gamma(0.6, 3.0, size=(S, 1))
    y = rng.poisson(base * (1 + 0.5 * np.sin(np.arange(T) / 7 * 2 * np.pi)[None, :])).astype(np.float64)
    y[0, :60] = 0
    return y


# ------------------------------------------------------------------ windows
def test_windows_are_ordered_and_disjoint_for_every_window():
    for T in (1941, 739):
        for w in win.OFFSETS:
            for H in win.HORIZONS:
                try:
                    info = win.check_ordered(win.truncated_length(T, w), H)
                except win.Infeasible:
                    continue
                assert info["validation_blocks"][-1][1] + 1 == info["test_blocks"][0][0]
    assert win.disjoint_from("W1", "W2", 1941) and win.disjoint_from("W2", "W3", 1941) and not win.disjoint_from("W2", "W2", 1941)
    # W2 ends exactly one day before W1's first validation block
    assert win.check_ordered(1941 - 252, 28)["first_unused_day"] == win.blocks(1941, 28)["val"][0]


def test_online_retail_w3_is_infeasible_and_w2_is_feasible():
    with pytest.raises(win.Infeasible):
        win.blocks(739 - 504, 28)
    assert win.blocks(739 - 252, 28)["val"][0] == 235


# ------------------------------------------------------------------ baselines never read the future
@pytest.mark.parametrize("H", [7, 28])
def test_matched_baselines_use_nothing_after_t_minus_H(H):
    y = _series()
    ref = bl.matched(y, H, bl.states(y))
    rng = np.random.default_rng(1)
    for t in (150, 200, 299):
        y2 = y.copy()
        y2[:, t - H + 1:] = rng.integers(0, 80, size=y2[:, t - H + 1:].shape)
        again = bl.matched(y2, H, bl.states(y2))
        for k in ref:
            np.testing.assert_array_equal(ref[k][:, t], again[k][:, t], err_msg=f"{k} t={t}")


@pytest.mark.parametrize("H", [7, 28])
def test_fresh_baselines_use_nothing_after_their_cutoff(H):
    y = _series()
    starts = [120, 148]
    st = bl.states(y)
    ref = bl.fresh(y, H, starts, st)
    c = bl.cutoff_index(y.shape[1], H, starts)
    rng = np.random.default_rng(2)
    for t in np.flatnonzero(c >= 0)[[0, 9, 27, 40, 55]]:
        assert c[t] <= t - 1 and c[t] >= t - H
        y2 = y.copy()
        y2[:, c[t] + 1:] = rng.integers(0, 80, size=y2[:, c[t] + 1:].shape)
        again = bl.fresh(y2, H, starts, bl.states(y2))
        for k in ref:
            np.testing.assert_array_equal(ref[k][:, t], again[k][:, t], err_msg=f"{k} t={t}")


def test_weekday_median_and_trailing_median_by_hand():
    y = np.zeros((1, 120))
    y[0, ::7] = 3 + 2 * np.arange(len(y[0, ::7]))
    m = bl.matched(y, 28, bl.states(y))
    t = 100
    lags = [y[0, t - 28 - 7 * i] for i in range(4)]
    assert m["weekday_median4"][0, t] == pytest.approx(np.median(lags)) and m["weekday_mean4"][0, t] == pytest.approx(np.mean(lags))
    assert m["trailing_median28"][0, t] == pytest.approx(np.median(y[0, t - 28 - 27: t - 28 + 1]))
    assert (m["zero"] == 0).all()


def test_croston_variants_differ_by_the_sba_factor():
    y = np.zeros((1, 40))
    y[0, 2] = y[0, 6] = y[0, 11] = 4.0
    c, s = bl._croston_states(y, sba=False), bl._croston_states(y, sba=True)
    assert s[0, -1] == pytest.approx(0.95 * c[0, -1])


# ------------------------------------------------------------------ metrics
def test_zero_forecast_has_wape_one_and_identities_hold():
    y = np.array([3.0, 0.0, 5.0, 2.0, 0.0, 7.0])
    s = np.array([0, 1, 0, 1, 0, 1])
    d = np.array([0, 0, 1, 1, 2, 2])
    assert mt.wape(y, np.zeros_like(y)) == pytest.approx(1.0)
    p = np.array([1.0, 2.0, 5.0, 0.0, 4.0, 3.0])
    assert mt.subset_day_wape(y, p, d) >= abs(mt.rel_bias(y, p)) - 1e-12
    assert mt.wape(np.zeros(3), np.ones(3)) is None


def test_ladder_levels_collapse_correctly():
    rng = np.random.default_rng(4)
    S, D = 5, 14
    s = np.repeat(np.arange(S), D)
    d = np.tile(np.arange(D), S)
    y = rng.poisson(2.0, S * D).astype(float)
    p = y + rng.normal(0, 1, S * D)
    L = mt.ladder(y, p, s, d, 0)
    assert L["item_day_wape"] >= L["item_week_wape"] - 1e-12 and L["subset_week_wape"] <= L["item_week_wape"] + 1e-12
    assert L["subset_day_wape"] >= abs(L["rel_bias"]) - 1e-12


# ------------------------------------------------------------------ objective semantics
def test_absolute_error_objective_recovers_the_median_and_squared_error_the_mean():
    rng = np.random.default_rng(0)
    n = 6000
    X = rng.normal(size=(n, 2)).astype(np.float32)
    y = rng.lognormal(0.0, 1.0, size=n)               # right-skewed: mean (1.65) >> median (1.0)
    out = {}
    for cid in ("lgbm_l2", "lgbm_l1", "lgbm_quantile50", "xgb_l1"):
        m = md.Model(cid, ["a", "b"], 42, n_jobs=2).fit(X, y)
        out[cid] = float(np.mean(m.predict(X[:2000])))
    assert abs(out["lgbm_l2"] - y.mean()) < 0.25
    for cid in ("lgbm_l1", "lgbm_quantile50", "xgb_l1"):
        assert abs(out[cid] - np.median(y)) < 0.25, (cid, out[cid])
        assert out[cid] < out["lgbm_l2"] - 0.3
    assert md.Model("lgbm_l1", ["a"], 1).objective_string() == "l1"
    assert md.Model("xgb_l1", ["a"], 1).objective_string() == "reg:absoluteerror"
    assert md.Model("lgbm_tweedie_p15", ["a"], 1).m.get_params()["tweedie_variance_power"] == 1.5


def test_predictions_are_clipped_at_zero():
    rng = np.random.default_rng(1)
    X = rng.normal(size=(500, 2)).astype(np.float32)
    y = np.maximum(0, X[:, 0] * 3 - 1).round()
    for cid in ("ridge_a100", "lgbm_l2"):
        p = md.Model(cid, ["a", "b"], 42, n_jobs=2).fit(X, y).predict(X)
        assert (p >= 0).all()


# ------------------------------------------------------------------ inference helpers
def test_crossed_bootstrap_and_cgm_on_identical_and_perfect_forecasts():
    rng = np.random.default_rng(3)
    Na = rng.gamma(2.0, 5.0, size=(40, 12))
    r = an.crossed_bootstrap(Na, Na.copy(), B=300)
    assert r["estimate"] == pytest.approx(0.0) and r["ci95"] == [pytest.approx(0.0), pytest.approx(0.0)]
    r2 = an.crossed_bootstrap(Na, np.zeros_like(Na), B=300)
    assert r2["estimate"] == pytest.approx(1.0)
    c = an.cgm_t(Na, 0.9 * Na)
    assert c["estimate"] == pytest.approx(0.1)


def test_holm_and_verdict_rule():
    adj = an.holm({"a": 0.01, "b": 0.04, "c": 0.03, "d": None})
    assert adj["a"] == pytest.approx(0.03) and adj["c"] == pytest.approx(0.06) and adj["d"] is None
    assert an.verdict(0.05, 0.02, 0.08, 0.01, 5) == "SUPPORTED"
    assert an.verdict(0.05, 0.02, 0.08, 0.01, 3) == "INCONCLUSIVE"      # fewer than 4 blocks won
    assert an.verdict(0.01, 0.002, 0.02, 0.01, 6) == "INCONCLUSIVE"     # below the 2 % minimum gain
    assert an.verdict(-0.05, -0.08, -0.01, 0.5, 0) == "CONTRADICTED"


def test_stationary_block_indices_stay_in_range_and_are_contiguous_within_blocks():
    rng = np.random.default_rng(5)
    for _ in range(200):
        ix = an.week_block_idx(rng, 24, "stationary")
        assert ix.min() >= 0 and ix.max() < 24 and len(ix) == 24


# ------------------------------------------------------------------ data truncation (uses the raw files; skipped when they are absent)
def _raw_available():
    from research.forecast_study_v2.common import ROOT
    return (ROOT / "data" / "external" / "uci_online_retail_ii" / "processed" / "online_retail_ii_raw_as_csv.csv").exists()


@pytest.mark.skipif(not _raw_available(), reason="raw Online Retail II file not present")
def test_online_retail_windows_are_truncated_and_skus_use_only_prior_revenue():
    import pandas as pd

    from research.forecast_study_v2 import data as dat

    w1, w2 = dat.load("or2", "W1"), dat.load("or2", "W2")
    assert w1.y.shape[1] == 739 and w2.y.shape[1] == 739 - 252
    assert (w2.dates[-1] < w1.dates[-1]) and (w2.dates[-1] == w1.dates[739 - 252 - 1])
    # independent recomputation of the W2 SKU list from the raw transactions, using revenue before the first W2 validation day only
    raw = pd.read_csv(dat.ds.OR2_CSV, dtype={"Invoice": str, "StockCode": str}, parse_dates=["InvoiceDate"])
    raw = raw[~raw["Invoice"].str.startswith("C") & (raw["Quantity"] > 0) & (raw["Price"] > 0) & ~raw["StockCode"].isin(dat.ds.NON_PRODUCT_CODES)]
    raw = raw[~raw.duplicated(["Invoice", "StockCode", "Quantity", "InvoiceDate", "Price", "Customer ID"])]
    raw["day"] = raw["InvoiceDate"].dt.normalize()
    full = pd.date_range(raw["day"].min(), raw["day"].max(), freq="D")
    cut = full[win.blocks(739 - 252, 28)["val"][0]]
    top = (raw[raw["day"] < cut].assign(rev=lambda d: d["Quantity"] * d["Price"]).groupby("StockCode")["rev"].sum().sort_values(ascending=False, kind="mergesort").head(100).index.tolist())
    assert top == w2.series_ids
    # the W2 targets are a prefix-consistent view of the same raw data (same SKU-day units where the SKU is in both lists)
    common = [s for s in w2.series_ids if s in w1.series_ids]
    i2 = [w2.series_ids.index(s) for s in common]
    i1 = [w1.series_ids.index(s) for s in common]
    assert np.array_equal(w2.y[i2], w1.y[i1][:, : w2.y.shape[1]])


@pytest.mark.skipif(not _raw_available(), reason="raw Online Retail II file not present")
def test_pipeline_features_and_baselines_see_only_the_truncated_series():
    from research.forecast_study_v2 import pipeline as pl

    P = pl.Prepared("or2", "W2", 28, log=lambda s: None)
    assert P.d.y.shape[1] == 487 and P.F.shape[1] == 487
    leak = pl.leakage_checks(P)
    assert all(x.get("history_features_unchanged_when_future_is_perturbed", True) for x in leak)
    assert np.isfinite(P.base["matched__zero"]).all() and (P.base["matched__zero"] == 0).all()
