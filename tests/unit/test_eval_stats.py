"""Unit tests for backend/app/evaluation/stats.py (Phase 2). Pure module."""
import numpy as np
import pytest

from app.evaluation import stats as st


def test_summary_basic():
    s = st.summary([1, 2, 3, 4, 5])
    assert s["n"] == 5 and s["mean"] == 3.0 and s["median"] == 3.0
    assert s["student_t_ci95"] is not None
    assert st.summary([])["n"] == 0


def test_win_tie_loss_and_rank_biserial_are_estimator_based():
    a = [1, 1, 1, 1, 0]
    b = [0, 0, 0, 0, 0]
    wtl = st.win_tie_loss(a, b)
    assert (wtl["a_wins"], wtl["ties"], wtl["a_losses"], wtl["n_nonzero"]) == (4, 1, 0, 4)
    # 4 favourable, 0 unfavourable, 4 non-zero -> (4 - 0) / 4 = 1.0
    assert st.rank_biserial(a, b) == pytest.approx(1.0)
    # mixed
    assert st.rank_biserial([1, -1, 1, 0], [0, 0, 0, 0]) == pytest.approx((2 - 1) / 3)
    # all tied -> undefined
    assert st.rank_biserial([2, 2, 2], [2, 2, 2]) is None


def test_rank_biserial_does_not_depend_on_the_p_value():
    # two datasets with identical win/tie/loss pattern but different magnitudes
    r1 = st.rank_biserial([0.01, 0.01, 0.01, 0.0], [0, 0, 0, 0])
    r2 = st.rank_biserial([50.0, 50.0, 50.0, 0.0], [0, 0, 0, 0])
    assert r1 == r2 == pytest.approx(1.0)   # p-derived quantities would differ; the estimator does not


def test_wilcoxon_undefined_paths_are_explicit():
    r0 = st.wilcoxon_signed_rank([0.3, 0.3, 0.3], [0.3, 0.3, 0.3])
    assert r0["p_value"] is None and "undefined" in r0["reason"]
    r1 = st.wilcoxon_signed_rank([1, 0, 0, 0], [0, 0, 0, 0])
    assert r1["p_value"] is None and r1["n_nonzero"] == 1
    r2 = st.wilcoxon_signed_rank([5, 4, 6, 7, 3], [0, 0, 0, 0, 0])
    assert r2["p_value"] is not None and r2["n_nonzero"] == 5


def test_scenario_level_aggregate_collapses_seeds():
    obs = [
        {"scenario_id": "s1", "m": 0.2}, {"scenario_id": "s1", "m": 0.4},
        {"scenario_id": "s2", "m": 1.0}, {"scenario_id": "s2", "m": 1.0},
    ]
    agg = st.scenario_level_aggregate(obs, metric="m")
    assert agg == {"s1": pytest.approx(0.3), "s2": pytest.approx(1.0)}


def test_cluster_bootstrap_is_reproducible_and_brackets_the_point():
    a = {f"s{i}": float(i) + 0.5 for i in range(12)}
    b = {f"s{i}": float(i) for i in range(12)}
    r1 = st.cluster_bootstrap_paired(a, b, n_boot=2000, seed=1)
    r2 = st.cluster_bootstrap_paired(a, b, n_boot=2000, seed=1)
    assert r1 == r2
    assert r1["point"] == pytest.approx(0.5)
    assert r1["ci95"][0] <= r1["point"] <= r1["ci95"][1]
    assert st.cluster_bootstrap_paired({"s1": 1.0}, {"s1": 0.0})["point"] is None


def test_paired_scenario_analysis_bundle_shape():
    a = {f"s{i}": 0.6 for i in range(10)}
    b = {f"s{i}": 0.9 for i in range(10)}
    res = st.paired_scenario_analysis(a, b, label="D_vs_B")
    assert res["n_scenarios"] == 10
    assert res["wins_ties_losses"] == [0, 0, 10]
    assert res["rank_biserial"] == pytest.approx(-1.0)
    assert res["primary_effect_size"] == "matched_pairs_rank_biserial"
    assert res["primary_interval"] == "paired_scenario_cluster_bootstrap"
    assert res["cluster_bootstrap"]["point"] == pytest.approx(-0.3)


def test_holm_correction_step_down_and_none_passthrough():
    out = st.holm_correction({"c1": 0.001, "c2": 0.02, "c3": 0.20, "c4": None}, alpha=0.05)
    r = out["results"]
    assert out["n_tests_corrected"] == 3
    assert r["c1"]["p_holm"] == pytest.approx(0.003)      # 3 * 0.001
    assert r["c1"]["reject_at_alpha"] is True
    assert r["c2"]["p_holm"] == pytest.approx(0.04)       # 2 * 0.02
    assert r["c3"]["reject_at_alpha"] is False
    assert r["c4"]["p_raw"] is None and r["c4"]["reject_at_alpha"] is False
    # monotonicity of adjusted p across the ordered family
    ordered = sorted((v["rank"], v["p_holm"]) for v in r.values() if v["rank"])
    ps = [p for _, p in ordered]
    assert ps == sorted(ps)


def test_simulate_power_runs_and_scales_with_effect():
    lo = st.simulate_power(st.PowerAssumptions(
        n_scenarios=17, n_seeds=10, min_effect_of_interest=0.02,
        metric_sd_between_scenarios=0.15, within_scenario_seed_sd=0.10, n_sim=400))
    hi = st.simulate_power(st.PowerAssumptions(
        n_scenarios=17, n_seeds=10, min_effect_of_interest=0.20,
        metric_sd_between_scenarios=0.15, within_scenario_seed_sd=0.10, n_sim=400))
    assert 0.0 <= lo["estimated_power"] <= 1.0
    assert hi["estimated_power"] >= lo["estimated_power"]      # bigger assumed effect -> not less power
    assert "not derived from observed results" in lo["assumptions"]["note"]
