"""Unit tests for the benchmark package (``ml/benchmark``): features, split integrity, leakage, metrics, ensembles, churn labelling,
out-of-fold stacking, calibration, serialization, and preservation of historical artifacts. Small synthetic arrays only; no network."""
import hashlib
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import pytest

from ml.benchmark import churn, direct, ensembles as ens, evaluate as ev, features as ft, models as zoo

ROOT = Path(__file__).resolve().parents[2]


def _toy(n=6, T=260, seed=0):
    rng = np.random.default_rng(seed)
    y = rng.poisson(3.0, size=(n, T)).astype(np.float32)
    price = (10 + rng.normal(0, 0.3, size=(n, T))).astype(np.float32)
    dates = pd.date_range("2020-01-01", periods=T)
    cal = pd.DataFrame({"dow": dates.dayofweek, "dom": dates.day, "month": dates.month, "event": 0, "snap": 0})
    static = {"dept_code": np.arange(n) % 2, "cat_code": np.zeros(n), "item_code": np.arange(n)}
    return y, price, cal, static


# ------------------------------------------------------------------ features and leakage
def test_history_features_use_only_data_up_to_the_origin():
    y, price, cal, static = _toy()
    for origin in (120, 180, 230):
        assert ft.assert_no_future_leakage(y, price, cal, static, H=28, origin=origin)


def test_the_leakage_checker_catches_a_deliberately_leaky_feature(monkeypatch):
    """Negative control: shifting history by H-1 instead of H lets day t see y[t-H+1]; the checker must fail."""
    y, price, cal, static = _toy()
    real = ft._shift_right
    monkeypatch.setattr(ft, "_shift_right", lambda a, k: real(a, k - 1 if k >= 28 else k))
    assert ft.assert_no_future_leakage(y, price, cal, static, H=28, origin=150) is False


def test_lag_feature_is_exactly_the_value_H_days_earlier():
    y, price, cal, static = _toy()
    F, names = ft.build_direct_features(y, price, cal, static, H=28)
    j = names.index("lag_28")
    assert np.array_equal(F[:, 100, j], y[:, 72])
    assert np.isnan(F[:, 20, j]).all()  # not computable yet: NaN, never zero-filled


def test_rolling_features_never_include_the_target_day_or_origin_plus_one():
    y, price, cal, static = _toy()
    F, names = ft.build_direct_features(y, price, cal, static, H=28)
    j = names.index("roll_mean_7")
    t = 150
    assert np.allclose(F[:, t, j], y[:, t - 28 - 6: t - 28 + 1].mean(axis=1), atol=1e-5)


def test_training_rows_for_an_origin_have_targets_strictly_before_it():
    y, price, cal, static = _toy()
    F, names = ft.build_direct_features(y, price, cal, static, H=28)
    valid = ft.valid_mask(y, price, 28)
    origin = 200
    X, yy, s, d = direct.rows(F, valid, y, 0, origin - 1)
    assert d.max() < origin and len(yy) > 0
    Xv, yv, sv, dv = direct.rows(F, valid, y, origin, origin + 27)
    assert dv.min() >= origin and dv.max() <= origin + 27
    # the validation window's history features reference only days < origin + 28 - 28 + ... i.e. <= window day - 28
    assert (dv - 28).max() <= origin - 1 + 27


# ------------------------------------------------------------------ metrics
def test_wape_and_zero_denominator_are_explicit():
    assert ev.wape(np.array([0.0, 0.0]), np.array([1.0, 2.0])) is None  # undefined, never 0
    assert ev.wape(np.array([10.0, 10.0]), np.array([12.0, 8.0])) == pytest.approx(0.2)
    m = ev.metrics(np.zeros(4), np.ones(4), np.array([0, 0, 1, 1]))
    assert m["wape"] is None and m["bias"] is None and m["mae"] == 1.0


def test_rmsse_excludes_constant_history_series_and_counts_them():
    sc = ev.series_scale(np.array([[1, 1, 1, 1.0], [0, 2, 0, 2.0]]))
    m = ev.metrics(np.array([1.0, 1.0, 2.0, 2.0]), np.array([1.0, 1.0, 1.0, 1.0]), np.array([0, 0, 1, 1]), sc)
    assert m["rmsse_series_excluded_constant_history"] == 1 and m["rmsse_mean"] is not None


def test_paired_bootstrap_detects_a_real_difference_and_refuses_few_series():
    rng = np.random.default_rng(1)
    n, k = 60, 20
    series = np.repeat(np.arange(n), k)
    y = rng.poisson(5, n * k).astype(float)
    good = y + rng.normal(0, 0.5, n * k)
    bad = y + rng.normal(0, 3.0, n * k)
    r = ev.paired_cluster_bootstrap(y, good, bad, series, draws=400)
    assert r["difference_a_minus_b"] < 0 and r["ci95"][1] < 0
    few = ev.paired_cluster_bootstrap(y[: 3 * k], good[: 3 * k], bad[: 3 * k], series[: 3 * k])
    assert few["ci95"] is None and few["draws"] == 0


# ------------------------------------------------------------------ ensembles
def test_nnls_weights_are_a_convex_combination_and_recover_a_known_mixture():
    rng = np.random.default_rng(2)
    a, b, c = rng.normal(size=(3, 500)) + 10
    y = 0.7 * a + 0.3 * b
    w = ens.nnls_weights(np.column_stack([a, b, c]), y)
    assert (w >= 0).all() and w.sum() == pytest.approx(1.0)
    assert w[0] == pytest.approx(0.7, abs=0.03) and w[2] < 0.03


def test_degenerate_weights_fall_back_to_equal():
    w = ens.nnls_weights(np.zeros((5, 3)), np.zeros(5))
    assert np.allclose(w, 1 / 3)


def test_ensemble_methods_never_receive_test_data_by_construction():
    """The ensemble helpers take arrays only; the weights come from validation predictions passed explicitly."""
    import inspect

    assert list(inspect.signature(ens.nnls_weights).parameters) == ["val_preds", "val_y"]


# ------------------------------------------------------------------ models: fit, inference, serialization
@pytest.mark.parametrize("family,variant", [("linear", "ols"), ("ridge", "alpha1"), ("hist_gradient_boosting", "depth4"),
                                            ("xgboost", "depth4"), ("lightgbm", "l2"), ("catboost", "depth6"), ("random_forest", "leaf5")])
def test_every_family_fits_predicts_nonnegative_and_reloads_identically(family, variant, tmp_path):
    if family == "catboost":
        pytest.importorskip("catboost")
    if family == "lightgbm":
        pytest.importorskip("lightgbm")
    y, price, cal, static = _toy(n=4, T=200)
    F, names = ft.build_direct_features(y, price, cal, static, H=28)
    valid = ft.valid_mask(y, price, 28)
    X, yy, _, _ = direct.rows(F, valid, y, 0, 199)
    p = zoo.build(family, variant, names, seed=3).fit(X[:300], yy[:300])
    pred = p.predict(X[300:])
    assert pred.shape == (len(X) - 300,) and len(X) > 330 and (pred >= 0).all() and np.isfinite(pred).all()
    path = tmp_path / "m.joblib"
    joblib.dump(p, path)
    assert np.allclose(joblib.load(path).predict(X[300:]), pred)
    again = zoo.build(family, variant, names, seed=3).fit(X[:300], yy[:300]).predict(X[300:])
    assert np.allclose(again, pred, atol=1e-6)  # same seed -> same predictions


# ------------------------------------------------------------------ churn / inactivity
def _tx(rows):
    return pd.DataFrame(rows, columns=["Customer ID", "Invoice", "StockCode", "day", "revenue"]).assign(day=lambda d: pd.to_datetime(d["day"]))


def test_inactivity_label_and_features_respect_the_cutoff():
    d = _tx([
        (1, "A1", "X", "2011-01-10", 10.0),   # before cutoff -> feature
        (1, "A2", "X", "2011-03-20", 20.0),   # after cutoff, inside label window -> active
        (2, "B1", "Y", "2011-02-01", 5.0),    # before cutoff, never returns -> inactive
        (2, "B2", "Y", "2011-07-15", 99.0),   # beyond the 90-day window -> must NOT make customer 2 active
        (3, "C1", "Z", "2011-03-01", 7.0),    # purchase ON the cutoff day: label window, not a feature; customer unknown before cutoff
    ])
    s = churn.snapshot(d, "2011-03-01").set_index("customer_id")
    assert set(s.index) == {1, 2}                      # customer 3 first appears on the cutoff day: not known before it
    assert s.loc[1, "inactive_90d"] == 0 and s.loc[2, "inactive_90d"] == 1
    assert s.loc[1, "monetary"] == 10.0 and s.loc[1, "frequency"] == 1   # the 2011-03-20 invoice is not in the features
    assert s.loc[1, "recency_days"] == 50


def test_temporal_integrity_holds_for_the_real_cutoffs_and_fails_for_overlap(monkeypatch):
    d = _tx([(1, "A", "X", "2011-12-09", 1.0), (1, "B", "X", "2009-12-01", 1.0)])
    assert all(v for k, v in churn.check_temporal_integrity(d).items() if k != "data_last_day")
    monkeypatch.setitem(churn.CUTOFFS, "train", ["2010-06-01", "2010-07-01"])  # 30 days apart < 90-day windows
    assert churn.check_temporal_integrity(d)["train_label_windows_non_overlapping"] is False


class _Memoriser:
    """Predicts the training label for a row it has seen and 0.5 for anything else: any in-sample prediction is obvious."""

    def fit(self, X, y):
        self.table = {tuple(r): v for r, v in zip(X.tolist(), y.tolist())}
        return self

    def predict_proba(self, X):
        p = np.array([self.table.get(tuple(r), 0.5) for r in X.tolist()])
        return np.column_stack([1 - p, p])


def test_stacking_meta_features_are_strictly_out_of_fold():
    rng = np.random.default_rng(0)
    X = rng.normal(size=(200, 3))
    y = rng.integers(0, 2, 200)
    oof = churn.oof_predictions(lambda seed: {"memoriser": _Memoriser()}, X, y, groups=np.repeat(np.arange(50), 4), seed=0)
    assert np.all(oof["memoriser"] == 0.5)  # every row was predicted by a model that never saw it


def test_grouped_folds_never_split_a_customer():
    from sklearn.model_selection import GroupKFold

    groups = np.repeat(np.arange(30), 4)
    for tr, te in GroupKFold(5).split(np.zeros((120, 1)), np.zeros(120), groups):
        assert not set(groups[tr]) & set(groups[te])


def test_metrics_threshold_and_calibration_helpers():
    y = np.array([0, 0, 1, 1])
    assert churn.ece(np.array([0, 1] * 50), np.full(100, 0.5)) == pytest.approx(0.0)
    t = churn.threshold_metrics(y, np.array([0.1, 0.6, 0.4, 0.9]), 0.5)
    assert (t["tp"], t["fp"], t["fn"], t["tn"]) == (1, 1, 1, 1) and t["cost"] == churn.COST_FP + churn.COST_FN
    p = churn.prob_metrics(y, np.array([0.1, 0.2, 0.8, 0.9]))
    assert p["roc_auc"] == 1.0 and p["brier"] < p["brier_prevalence_baseline"]


def test_a_single_class_target_is_rejected_not_manufactured():
    X = np.random.default_rng(0).normal(size=(40, 3))
    with pytest.raises(ValueError, match="unsupported target"):
        churn.evaluate_classifiers(X, np.zeros(40, int), X, np.zeros(40, int), X, np.zeros(40, int))


def test_evaluate_classifiers_end_to_end_on_a_learnable_toy_problem():
    rng = np.random.default_rng(5)
    X = rng.normal(size=(900, 4))
    y = (X[:, 0] + 0.5 * rng.normal(size=900) > 0).astype(int)
    r = churn.evaluate_classifiers(X[:500], y[:500], X[500:700], y[500:700], X[700:], y[700:], groups_train=np.arange(500) // 2, seed=1, bootstrap=50)
    expected_base_models = {"logistic_regression", "random_forest", "xgboost"}
    try:
        import catboost  # noqa: F401
        expected_base_models.add("catboost")
    except ImportError:
        pass
    assert set(r["base_models"]) == expected_base_models
    for name in ("soft_voting", "stacking_logistic_meta", "logistic_regression"):
        assert 0.8 < r["models"][name]["uncalibrated"]["test"]["roc_auc"] <= 1.0
        assert set(r["models"][name]) >= {"uncalibrated", "sigmoid", "isotonic"}
    assert r["models"]["xgboost"]["isotonic"]["thresholds_chosen_on_validation"]["cost_min"] > 0


# ------------------------------------------------------------------ preservation of historical artifacts
def test_historical_artifacts_are_unchanged():
    ref = json.loads((ROOT / "experiments" / "ml_benchmark_v1" / "HISTORICAL_HASHES.json").read_text(encoding="utf-8"))["files"]
    assert len(ref) >= 15
    for rel, sha in ref.items():
        p = ROOT / rel
        assert p.exists(), rel
        assert hashlib.sha256(p.read_bytes()).hexdigest() == sha, f"historical artifact changed: {rel}"
