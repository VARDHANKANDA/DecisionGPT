"""Unit tests of forecast_study_v3 (fresh-window evaluation with classical statistical baselines). Passing tests show the code behaves as written, not that the design is valid."""
from __future__ import annotations

import numpy as np
import pytest

from research.forecast_study_v2 import windows as win
from research.forecast_study_v3_fresh_stats import stat_forecasts as sf
from research.forecast_study_v3_fresh_stats import v3common as C


class Serial:
    def map(self, fn, it):
        return [fn(x) for x in it]


def test_w4_window_is_disjoint_from_the_used_windows_and_ordered():
    T_full = 1941
    spans = {w: (T_full - off - 28 * 9, T_full - off) for w, off in {**win.OFFSETS, C.WINDOW: C.WINDOW_OFFSET}.items()}
    a = spans[C.WINDOW]
    assert a == (933, 1185)
    for w in ("W1", "W2", "W3"):
        b = spans[w]
        assert a[1] <= b[0] or b[1] <= a[0]
    # the series-eligibility cut-off uses nothing from the validation or test period
    assert C.MAX_FIRST_SALE_DAY < spans[C.WINDOW][0]
    assert C.MAX_FIRST_SALE_DAY == spans[C.WINDOW][0] - 85


def test_install_adds_the_window_without_changing_the_v2_files():
    from research.forecast_study_v3_fresh_stats import data3

    data3.install()
    assert win.OFFSETS["W4"] == 756 and win.OFFSETS["W1"] == 0
    b = win.blocks(win.truncated_length(1941, "W4"), 28)
    assert b["val"][0] == 933 and b["test"][-1] + 28 == 1185
    win.check_ordered(win.truncated_length(1941, "W4"), 28)


def test_history_slice_never_returns_days_after_the_end():
    y = np.arange(40, dtype=float)[None, :].repeat(3, axis=0)
    h = sf.history(y, 20)
    assert h.shape[1] == 21 and h.max() == 20


@pytest.mark.parametrize("kind", ["fresh", "matched28", "matched7"])
def test_statistical_forecasts_do_not_depend_on_the_future(kind, monkeypatch):
    rng = np.random.default_rng(0)
    T, S, o = 900, 30, 700
    y = rng.poisson(1.0, (S, T)).astype(np.float32)

    def stub(hist, model, h_max):                       # stands in for the statsforecast fit: any function of the history only
        return np.repeat(hist[:, -91:].mean(axis=1, keepdims=True), h_max, axis=1) + hist[:, -7:].sum(axis=1, keepdims=True) * 0.01, 0

    monkeypatch.setattr(sf, "fit_forecast", stub)
    f0, _ = sf.block_forecast(y, o, kind, "ets", Serial())
    end = o - 1 if kind == "fresh" else o - int(kind.replace("matched", ""))
    y2 = y.copy()
    y2[:, end + 1:] = rng.integers(0, 99, y2[:, end + 1:].shape)
    f1, _ = sf.block_forecast(y2, o, kind, "ets", Serial())
    assert np.array_equal(f0, f1) and f0.shape == (S, 28)


def test_matched_information_is_never_fresher_than_the_learned_models():
    for H in (28, 7):
        for o in (700, 728):
            end_matched, end_models = o - H, o - H                     # the earliest target day o has information through o - H; later days only more
            assert end_matched <= end_models <= o - 1


def test_fallback_is_used_and_counted(monkeypatch):
    # real fit_forecast with a model that always raises -> every series gets the trailing 91-day mean
    monkeypatch.setattr(sf, "_model", lambda name: (_ for _ in ()).throw(RuntimeError("boom")))
    hist = np.random.default_rng(1).poisson(2.0, (4, 200)).astype(float)
    pytest.importorskip("pandas")
    try:
        import statsforecast  # noqa: F401
    except Exception:
        pytest.skip("statsforecast is not installed in this environment")
    out, nfb = sf.fit_forecast(hist, "ets", 28)
    assert nfb == 4 and np.allclose(out[:, 0], hist[:, -91:].mean(axis=1))


def test_stat_array_assembly_places_blocks(tmp_path, monkeypatch):
    from research.forecast_study_v3_fresh_stats import run_v3

    monkeypatch.setattr(C, "RESULTS", tmp_path)
    monkeypatch.setattr(run_v3.C, "RESULTS", tmp_path)
    d = tmp_path / "stat" / "m5_ca2"
    d.mkdir(parents=True)
    np.save(d / "matched28_ets_o100.npy", np.full((2, 28), 5.0, dtype=np.float32))
    np.save(d / "fresh_theta_o128.npy", np.full((2, 28), 7.0, dtype=np.float32))
    a = run_v3.stat_arrays("m5_ca2", 28, 2, 200)
    assert np.isfinite(a["matched__ets"][:, 100:128]).all() and np.isnan(a["matched__ets"][:, :100]).all() and np.isnan(a["matched__ets"][:, 128:]).all()
    assert (a["fresh__theta"][:, 128:156] == 7.0).all() and np.isnan(a["matched__arima"]).all()


def test_loader_rule_matches_raw_data():
    from research.forecast_study_v3_fresh_stats import data3

    m = data3.load_m5_subset_v3("CA_2")
    assert len(m.meta) == 350 and m.info["negative_units"] == 0
    retired = data3.retired_pairs()
    assert not any((it, "CA_2") in retired for it in m.meta["item_id"])
    first = (m.y > 0).argmax(axis=1) + 1
    assert (first <= C.MAX_FIRST_SALE_DAY).all()
    assert m.info["units_sold_on_days_without_price"] == 0
