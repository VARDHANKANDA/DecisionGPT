"""Building blocks of research/forecast_study_v1: leak-free baselines, metric policies, dependence-aware inference, conformal intervals, windows, segments."""
import math

import numpy as np
import pytest

from research.forecast_study_v1 import baselines as bl
from research.forecast_study_v1 import inference as inf
from research.forecast_study_v1 import metrics as mt
from research.forecast_study_v1 import protocol as pr


def _series(S=6, T=240, seed=0):
    rng = np.random.default_rng(seed)
    base = rng.gamma(0.6, 3.0, size=(S, 1))
    y = rng.poisson(base * (1 + 0.5 * np.sin(np.arange(T) / 7 * 2 * np.pi)[None, :])).astype(np.float64)
    y[0, :60] = 0                                        # a series that starts late
    return y


# ------------------------------------------------------------------ baselines never look past their cutoff
@pytest.mark.parametrize("H", [7, 28])
def test_matched_baselines_use_nothing_after_t_minus_H(H):
    y = _series()
    ref = bl.matched(y, H)
    rng = np.random.default_rng(1)
    for t in (100, 150, 200, 239):
        e = t - H
        y2 = y.copy()
        y2[:, e + 1:] = rng.integers(0, 80, size=y2[:, e + 1:].shape)           # rewrite everything after the cutoff
        again = bl.matched(y2, H)
        for name in bl.NAMES:
            np.testing.assert_array_equal(ref[name][:, t], again[name][:, t], err_msg=f"{name} at t={t} changed when the future changed")


@pytest.mark.parametrize("H,starts", [(28, [112, 140]), (7, [112, 140])])
def test_fresh_baselines_use_nothing_after_their_cutoff_and_cutoff_is_fresh_but_not_future(H, starts):
    y = _series()
    c = bl.cutoff_index(y.shape[1], H, starts)
    covered = np.flatnonzero(c >= 0)
    assert covered.size == 56 and all(c[t] <= t - 1 and c[t] >= t - H for t in covered)      # at least as recent as matched, never the future
    ref = bl.fresh(y, H, starts)
    rng = np.random.default_rng(2)
    for t in covered[[0, 10, 27, 40, 55]]:
        y2 = y.copy()
        y2[:, c[t] + 1:] = rng.integers(0, 80, size=y2[:, c[t] + 1:].shape)
        again = bl.fresh(y2, H, starts)
        for name in bl.NAMES:
            np.testing.assert_array_equal(ref[name][:, t], again[name][:, t], err_msg=f"{name} at t={t}")
    assert np.isnan(ref["naive"][:, 0]).all()                                      # days outside the blocks are not forecast


def test_fresh_h28_uses_one_cutoff_for_the_whole_block_and_h7_one_per_week():
    c28 = bl.cutoff_index(300, 28, [100])
    assert set(c28[100:128]) == {99} and c28[99] == -1 and c28[128] == -1
    c7 = bl.cutoff_index(300, 7, [100])
    assert list(c7[100:107]) == [99] * 7 and list(c7[107:114]) == [106] * 7 and list(c7[121:128]) == [120] * 7


def test_croston_sba_and_tsb_match_hand_computation():
    y = np.zeros((1, 12))
    y[0, 2] = 3.0
    y[0, 5] = 3.0
    sba = bl.croston_sba_states(y)[0]
    assert sba[0] == 0 and sba[1] == 0                                    # nothing before the first demand
    assert sba[2] == pytest.approx((1 - 0.1 / 2) * 3.0 / 3.0)            # z=3, first interval p=3 (three periods since the start)
    assert sba[5] == pytest.approx((1 - 0.1 / 2) * 3.0 / 3.0)            # second demand 3 periods later: unchanged
    tsb = bl.tsb_states(y)[0]
    assert tsb[2] == pytest.approx((1 / 3) * 3.0)                         # first-demand probability = observed frequency so far
    assert tsb[3] == pytest.approx((1 / 3 + 0.1 * (0 - 1 / 3)) * 3.0)     # probability decays on a zero day


def test_every_baseline_is_finite_wherever_history_exists_and_nonnegative():
    y = _series()
    for H in (7, 28):
        m = bl.matched(y, H)
        f = bl.fresh(y, H, [112, 140])
        for name in bl.NAMES:
            assert np.isfinite(m[name][:, 120:]).all() and (m[name][:, 120:] >= 0).all()
            blk = f[name][:, 112:168]
            assert np.isfinite(blk).all() and (blk >= 0).all()


# ------------------------------------------------------------------ metrics: undefined cases are None, never 0
def test_wape_bias_policies_and_sign():
    y, p = np.array([10.0, 20.0, 30.0]), np.array([12.0, 18.0, 33.0])
    assert mt.wape(y, p) == pytest.approx(7 / 60) and mt.rel_bias(y, p) == pytest.approx(3 / 60)      # positive = over-forecast
    assert mt.wape(np.zeros(3), p) is None and mt.rel_bias(np.zeros(3), p) is None
    assert mt.mae(np.array([]), np.array([])) is None
    assert not hasattr(mt, "mape")                                                                         # no defensible denominator policy: deliberately absent


def test_rmsse_excludes_constant_history_and_counts_it():
    hist = np.array([[1.0, 2.0, 1.0, 2.0], [5.0, 5.0, 5.0, 5.0]])
    scale = mt.series_scale(hist)
    assert scale[0] == pytest.approx(1.0) and scale[1] == 0.0
    y, p = np.array([2.0, 4.0, 5.0, 5.0]), np.array([1.0, 3.0, 6.0, 5.0])
    v, used, excluded = mt.rmsse_mean(y, p, np.array([0, 0, 1, 1]), scale)
    assert used == 1 and excluded == 1 and v == pytest.approx(1.0)


def test_aggregate_wape_differs_from_pooled_when_errors_cancel():
    y = np.array([10.0, 10.0, 10.0, 10.0])
    p = np.array([15.0, 5.0, 15.0, 5.0])
    day = np.array([0, 0, 1, 1])
    assert mt.wape(y, p) == pytest.approx(0.5) and mt.aggregate_wape(y, p, day) == pytest.approx(0.0)


# ------------------------------------------------------------------ inference
def _grid(S=40, W=12, seed=3, week_shock=0.0, true_gain=0.0):
    rng = np.random.default_rng(seed)
    base = rng.gamma(2.0, 5.0, size=(S, W))
    D = base * 10
    shock = rng.normal(0, week_shock, size=(1, W))
    Na = D * 0.7 * np.exp(rng.normal(0, 0.1, size=(S, W)) + shock)
    Nb = D * 0.7 * (1 - true_gain) * np.exp(rng.normal(0, 0.1, size=(S, W)) - shock)       # the shared week shock moves a and b in opposite directions
    return Na, Nb, D


def test_identical_forecasts_give_zero_improvement_and_a_perfect_one_gives_one():
    Na, _, D = _grid()
    r = inf.crossed_bootstrap(Na, Na.copy(), D, B=200)
    assert r["estimate"] == pytest.approx(0.0) and r["ci95"][0] == pytest.approx(0.0) and r["p_two_sided"] == 1.0
    r2 = inf.crossed_bootstrap(Na, np.zeros_like(Na), D, B=200)
    assert r2["estimate"] == pytest.approx(1.0) and r2["ci95"] == [pytest.approx(1.0), pytest.approx(1.0)]


def test_crossed_interval_is_wider_than_series_only_when_weeks_share_a_shock():
    """The reason for the crossed design: a week-level shock that hits the two forecasters differently is invisible to a series-only bootstrap."""
    Na, Nb, D = _grid(week_shock=0.25)
    crossed = inf.crossed_bootstrap(Na, Nb, D, B=600)
    series_only = inf.series_only_bootstrap(Na, Nb, D, B=600)
    wc = crossed["ci95"][1] - crossed["ci95"][0]
    ws = series_only["ci95"][1] - series_only["ci95"][0]
    assert wc > 2.5 * ws


def test_crossed_interval_has_about_nominal_coverage_when_the_truth_is_zero_difference():
    hit = 0
    trials = 80
    for k in range(trials):
        Na, Nb, D = _grid(week_shock=0.15, seed=100 + k)
        r = inf.crossed_bootstrap(Na, Nb, D, B=250, seed=k)
        # the population mean difference is zero (shock is symmetric around 0): the interval should usually contain the long-run value
        hit += r["ci95"][0] <= 0.0 <= r["ci95"][1]
    assert hit / trials >= 0.85


def test_detects_a_real_improvement():
    Na, Nb, D = _grid(true_gain=0.15, week_shock=0.05)
    r = inf.crossed_bootstrap(Na, Nb, D, B=400)
    assert r["estimate"] == pytest.approx(0.15, abs=0.04) and r["ci95"][0] > 0 and r["p_two_sided"] < 0.05


def test_segment_bootstrap_resamples_within_the_subset():
    Na, Nb, D = _grid(true_gain=0.2)
    sub = np.arange(0, 10)
    r = inf.crossed_bootstrap(Na, Nb, D, B=100, series_subset=sub)
    assert r["n_series"] == 10


def test_holm_matches_the_textbook_example_and_ignores_undefined():
    adj = inf.holm({"a": 0.01, "b": 0.04, "c": 0.03, "d": None})
    assert adj["a"] == pytest.approx(0.03) and adj["c"] == pytest.approx(0.06) and adj["b"] == pytest.approx(0.06) and adj["d"] is None


def test_diebold_mariano_identical_losses_and_clear_difference():
    a = np.abs(np.random.default_rng(0).normal(size=200)) + 1
    same = inf.diebold_mariano(a, a.copy(), h=7)
    assert same["statistic"] == 0.0 and same["p_two_sided"] == pytest.approx(1.0)
    better = inf.diebold_mariano(a + 0.5, a, h=7)
    assert better["statistic"] > 5 and better["p_two_sided"] < 1e-6 and better["mean_loss_diff"] == pytest.approx(0.5)
    assert inf.diebold_mariano(a[:5], a[:5])["statistic"] is None


# ------------------------------------------------------------------ conformal
def test_conformal_quantile_is_the_finite_sample_order_statistic():
    r = np.arange(1, 10, dtype=float)               # n = 9, level 0.8 -> ceil(10 * 0.8) = 8th smallest
    assert inf.conformal_quantile(r, 0.8) == 8.0
    assert inf.conformal_quantile(r[:2], 0.99) is None            # too few residuals: undefined, not a guess


def test_mondrian_conformal_covers_exchangeable_data_and_uses_calibration_bins_only():
    rng = np.random.default_rng(5)
    n = 6000
    pred = rng.gamma(2.0, 3.0, size=n)
    y = np.maximum(0, pred + rng.normal(0, 0.4 * np.sqrt(pred + 0.1)))
    cal, test = slice(0, 3000), slice(3000, n)
    out = inf.mondrian_conformal(pred[cal], y[cal], pred[test], level=0.8, n_bins=3)
    rep = inf.interval_report(y[test], pred[test], out["half_width"])
    assert abs(rep["coverage"] - 0.8) < 0.04 and rep["n_excluded"] == 0
    assert out["edges"] == [float(e) for e in inf.mondrian_edges(pred[cal])]                  # edges come from calibration predictions


def test_interval_coverage_is_not_credited_with_negative_lower_bounds():
    rep = inf.interval_report(np.array([0.0, 10.0]), np.array([1.0, 1.0]), np.array([2.0, 2.0]))
    assert rep["coverage"] == 0.5 and rep["mean_width"] == pytest.approx(3.0)   # both intervals are [0, 3]: the lower bound is clipped at 0 and the width uses the clipped bound


# ------------------------------------------------------------------ windows and segments
def test_windows_for_m5_end_exactly_at_the_official_evaluation_window():
    w = pr.windows(1941)
    assert w["test"][0] == 1773 and w["test"][-1] == 1913 and w["test"][-1] + 27 == 1940
    assert w["val"] == [1689, 1717, 1745]
    info = pr.assert_windows_ordered(1941)
    assert info["disjoint_and_ordered"] and info["validation_blocks"][-1][1] + 1 == info["test_blocks"][0][0]


def test_windows_leave_no_overlap_for_any_length_long_enough():
    for T in (739, 1000, 1941):
        pr.assert_windows_ordered(T)


def test_segments_use_only_history_before_the_first_validation_block():
    y = _series(S=40, T=500, seed=9)
    cut = 300
    a = pr.segments(y, cut)
    y2 = y.copy()
    y2[:, cut:] = np.random.default_rng(1).integers(0, 90, size=y2[:, cut:].shape)
    b = pr.segments(y2, cut)
    assert a["pattern"] == b["pattern"] and a["volume"] == b["volume"] and a["adi"] == b["adi"]
    assert set(a["frequency"]) <= {"frequent", "intermittent_or_sparse"} and a["history_days"] == 300
