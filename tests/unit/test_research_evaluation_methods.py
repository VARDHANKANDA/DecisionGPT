"""Model comparison, risk-calibration metrics, causal identification and architecture-evaluation read model.

All inputs are tiny synthetic frames built here; expected values are computed by hand or by plain arithmetic, never read from stored runs."""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from app.services import architecture_evaluation_service as arch
from app.services import causal_identification_service as causal
from app.services import model_comparison_service as mc
from app.services import risk_assessment_service as risk


# ------------------------------------------------------------------ metrics against known examples
def test_regression_metrics_known_values():
    m = mc.regression_metrics([100, 200, 300, 400], [110, 190, 330, 360])
    assert m["n"] == 4
    assert m["mae"] == pytest.approx((10 + 10 + 30 + 40) / 4)
    assert m["rmse"] == pytest.approx(np.sqrt((100 + 100 + 900 + 1600) / 4))
    assert m["bias"] == pytest.approx((10 - 10 + 30 - 40) / 4)
    assert m["r2"] == pytest.approx(1 - 2700 / 50000)
    assert m["mape_pct"] == pytest.approx(np.mean([0.1, 0.05, 0.1, 0.1]) * 100)


def test_mape_is_suppressed_for_near_zero_targets_not_reported_as_a_number():
    m = mc.regression_metrics([0, 5, 10, 8], [1, 5, 9, 8])
    assert m["mape_pct"] is None and "near zero" in m["mape_note"]


def test_r2_is_undefined_not_zero_when_target_is_constant_or_tiny():
    assert mc.regression_metrics([5, 5, 5], [4, 5, 6])["r2"] is None
    assert mc.regression_metrics([1, 2], [1, 2])["r2"] is None


# ------------------------------------------------------------------ leakage safety and the split
def _series(days=140, seed=0, gap=None):
    rng = np.random.default_rng(seed)
    d = pd.date_range("2025-01-01", periods=days, freq="D")
    y = 100 + 20 * np.sin(np.arange(days) * 2 * np.pi / 7) + rng.normal(0, 3, days)
    df = pd.DataFrame({"series_id": "s", "date": d, "y": y})
    if gap is not None:
        df.loc[gap, "y"] = np.nan
    return df


def test_features_for_day_t_never_use_day_t_or_later():
    base = _series()
    feats_a, cols = mc.make_features(base, with_covariates=False)
    tampered = base.copy()
    tampered.loc[tampered["date"] >= "2025-03-01", "y"] += 10_000  # change the future of an earlier day
    feats_b, _ = mc.make_features(tampered, with_covariates=False)
    early = feats_a["date"] < pd.Timestamp("2025-03-01")
    a = feats_a.loc[early, cols].reset_index(drop=True)
    b = feats_b[feats_b["date"] < pd.Timestamp("2025-03-01")][cols].reset_index(drop=True)
    pd.testing.assert_frame_equal(a, b)  # earlier rows' features are unchanged by later observations
    assert "y" not in cols


def test_split_is_chronological_and_disjoint():
    dates = list(pd.date_range("2025-01-01", periods=100))
    s = mc.split_dates(dates)
    assert max(s["train"]) < min(s["val"]) and max(s["val"]) < min(s["test"])
    assert len(s["train"]) + len(s["val"]) + len(s["test"]) == 100
    assert len(s["test"]) == 15


def test_a_missing_day_is_not_imputed_and_drops_dependent_rows():
    df = _series(days=60, gap=30)
    feats, _ = mc.make_features(df, with_covariates=False)
    assert pd.Timestamp("2025-01-31") not in set(feats["date"])  # the target itself is missing: no row
    assert pd.Timestamp("2025-02-01") not in set(feats["date"])  # lag_1 would be missing
    assert not feats.isna().any().any()


# ------------------------------------------------------------------ the pipeline
def test_comparison_is_deterministic_and_baseline_is_reported():
    df = _series(days=160)
    r1 = mc.run_dataset("pos_daily_revenue", seed=7, df_override=df, load_info={})
    r2 = mc.run_dataset("pos_daily_revenue", seed=7, df_override=df, load_info={})
    assert r1["status"] == "completed"
    for k in r1["models"]:
        assert r1["models"][k]["test"] == r2["models"][k]["test"]
    assert mc.BASELINE_KEY in r1["models"] and r1["selection"]["selected"] != mc.BASELINE_KEY
    assert r1["checks"]["train_before_val_before_test"] is True
    assert "test period not used" in r1["selection"]["rule"]
    u = r1["uncertainty"]
    assert 0 <= u["empirical_coverage_test"] <= 1 and u["nominal_coverage"] == pytest.approx(0.8)


def test_too_little_data_gives_insufficient_data_not_a_benchmark():
    r = mc.run_dataset("pos_daily_revenue", seed=1, df_override=_series(days=30), load_info={})
    assert r["status"] == "insufficient_data" and "models" not in r and "No benchmark was produced" in r["reason"]


def test_unknown_dataset_is_rejected():
    with pytest.raises(ValueError):
        mc.run_dataset("nope")


# ------------------------------------------------------------------ calibration metrics
def test_ece_and_brier_against_hand_computed_values():
    y = np.array([0, 0, 1, 1])
    p = np.array([0.1, 0.1, 0.9, 0.9])
    ece, table = risk.expected_calibration_error(y, p, bins=10)
    assert ece == pytest.approx(0.1)  # both occupied bins are off by 0.1
    assert sum(b["n"] for b in table) == 4
    m = risk.probability_metrics(y, p)
    assert m["brier"] == pytest.approx(0.01)
    assert m["brier_baseline_prevalence"] == pytest.approx(0.25)
    assert m["brier_skill_score"] == pytest.approx(1 - 0.01 / 0.25)


def test_churn_calibration_reports_insufficient_data_for_one_class_or_tiny_sets():
    tiny = pd.DataFrame({"tenure_days": [100] * 10, "recency_days": [5] * 10, "frequency": [2] * 10, "avg_order_value": [10.0] * 10,
                         "monetary_value": [20.0] * 10, "churned": [0] * 10})
    assert risk.run_churn_calibration(df=tiny)["status"] == "insufficient_data"
    assert risk.run_churn_calibration(df=tiny.drop(columns=["churned"]))["status"] == "blocked"


def test_decision_risk_score_is_never_given_a_calibration_value():
    out = risk.get_risk_assessment(None, recorded_outcomes=0)
    drs = out["decision_risk_score"]
    assert drs["status"] == "not_evaluated" and drs["recorded_real_outcomes"] == 0
    assert any(not p["met"] for p in drs["prerequisites"])
    assert out["definitions"][0]["is_probability"] is False


# ------------------------------------------------------------------ causal identification
def test_pair_without_treatment_variation_is_unsupported_and_has_no_effect_number():
    df = pd.DataFrame({"marketing_spend": [0.0] * 50, "units_sold": np.arange(50), "date": pd.date_range("2025-01-01", periods=50)})
    p = causal._assess_pair("t", df, "marketing_spend", "units_sold", ["date"], "none", "", False)
    assert p["status"] == "unsupported" and any("no variation" in r for r in p["reasons"])
    assert "estimate" not in p and "effect" not in p


def test_missing_columns_make_a_pair_unsupported():
    p = causal._assess_pair("t", pd.DataFrame({"a": [1]}), "marketing_spend", "units_sold", [], "x", "", False)
    assert p["status"] == "unsupported" and "not present" in p["reasons"][0]


def test_known_truth_simulation_recovers_a_planted_multiplicative_effect():
    rng = np.random.default_rng(3)
    rows = []
    for s in range(12):
        base, trend = rng.uniform(50, 150), rng.uniform(0, 0.05)
        for i in range(150):
            promo = int(rng.random() < 0.1)
            demand = (base + trend * i) * (1.30 if promo else 1.0)
            rows.append({"series_id": f"s{s}", "date": pd.Timestamp("2025-01-01") + pd.Timedelta(days=i), "y": max(0, round(demand + rng.normal(0, demand * 0.03))),
                         "marketing_spend": 1000 + rng.normal(0, 50), "promotion_flag": promo, "price": 100.0})
    r = causal.simulate_known_truth(pd.DataFrame(rows), seed=1, draws=30)
    assert 22 <= r["estimate_pct"] <= 38  # planted +30%
    assert r["ci95_pct"][0] <= r["estimate_pct"] <= r["ci95_pct"][1]
    assert abs(r["balance_standardised_mean_differences"]["marketing_spend"]) < 0.5


# ------------------------------------------------------------------ architecture read model
def test_architecture_a_is_not_applicable_rather_than_a_zero():
    fake = {"architecture_comparison": {"experiment_id": "e", "seed": 1, "created_at": "x", "goal_target_percent": 15.0, "rows": [
        {"architecture": "A", "label": "Prediction only", "selected_strategy": None, "goal_achievement": 0.0, "risk_adjusted_score": 0.0, "expected_benefit": 0.0,
         "latency_seconds": 1.0, "note": ""},
        {"architecture": "B", "label": "B", "selected_strategy": "Price +5%", "goal_achievement": 0.33, "risk_adjusted_score": 10.0, "expected_benefit": 20.0,
         "latency_seconds": 2.0, "note": ""}]}}
    sd = arch._single_decision(fake)
    a, b = sd["rows"]
    assert a["status"] == "not_applicable" and a["goal_achievement"] is None and a["expected_benefit"] is None
    assert b["status"] == "evaluated" and b["goal_achievement"] == 0.33
    assert sd["n_decisions_per_architecture"] == 1 and any("one decision" in c.lower() for c in sd["caveats"])


def test_architecture_primary_evidence_comes_from_stored_files_and_is_labelled_simulated():
    ev = arch._primary_evidence()
    if ev is None:
        pytest.skip("stored R1 evidence not present in this checkout")
    assert ev["evidence_type"] == "simulated"
    assert ev["design"]["decisions_per_architecture"] == ev["design"]["scenarios"] * ev["design"]["seeds"]
    assert {r["key"] for r in ev["architectures"]} == {"A", "B", "C", "D"}
    assert all(r["mean_regret"] is not None and r["ci95"] for r in ev["architectures"])


# ------------------------------------------------------------------ frozen evidence is untouched
def test_frozen_manifest_and_spec_match_the_hashes_recorded_by_live_runs():
    from app.services import research_validation_service as v

    checks = {c["id"]: c for c in v.evidence_integrity()}
    if "frozen_spec" not in checks:
        pytest.skip("no live run stored")
    assert checks["frozen_spec"]["status"] == "passed" and checks["frozen_manifest"]["status"] == "passed"
    assert checks["run_completeness"]["status"] == "warning"  # every stored live run is partial: never reported as complete
