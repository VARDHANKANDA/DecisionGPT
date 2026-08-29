"""Multi-scenario architecture / ablation experiment machinery.

Covers: scenario determinism + uniqueness + variation, statistical
aggregation correctness, fairness (one business per scenario/seed, shared by
every architecture), reproducibility, traceability, and no-leakage.
"""
import numpy as np
import pytest

from app.services import multi_scenario_service as ms
from app.services import decision_architecture_service as da
from app.services import model_registry_service


# --- scenarios -----------------------------------------------------------


def test_scenario_ids_unique_and_stable():
    ids = [s.scenario_id for s in ms.SCENARIOS]
    assert ids == sorted(ids)
    assert len(ids) == len(set(ids)) == 12
    assert ids[0] == "S01" and ids[-1] == "S12"


def test_scenarios_are_meaningfully_different():
    industries = {s.industry for s in ms.SCENARIOS}
    objectives = {s.goal_objective for s in ms.SCENARIOS}
    margins = {round((s.selling_price - s.unit_cost) / s.selling_price, 2) for s in ms.SCENARIOS}
    demand_mid = {(s.demand_low + s.demand_high) // 2 for s in ms.SCENARIOS}
    assert len(industries) >= 10
    assert objectives >= {"increase_revenue", "increase_profit", "increase_sales"}
    assert len(margins) >= 6          # varied gross margin
    assert max(demand_mid) >= 4 * min(demand_mid)   # varied demand scale
    assert any(s.with_inventory for s in ms.SCENARIOS)
    assert any(s.marketing_every_days == 0 for s in ms.SCENARIOS)   # a no-marketing scenario
    assert "reduce_churn" not in objectives          # documented exclusion


def test_scenario_generation_is_deterministic(db_session):
    sc = ms.SCENARIOS[0]
    b1, g1 = da._seed_synthetic_business(db_session, 42, sc)
    rows1 = _sales_fingerprint(db_session, b1)
    da._cleanup_synthetic_business(db_session, b1)

    b2, g2 = da._seed_synthetic_business(db_session, 42, sc)
    rows2 = _sales_fingerprint(db_session, b2)
    da._cleanup_synthetic_business(db_session, b2)

    assert rows1 == rows2                    # same (scenario, seed) -> identical business
    # a different seed changes the generated data
    b3, _ = da._seed_synthetic_business(db_session, 43, sc)
    rows3 = _sales_fingerprint(db_session, b3)
    da._cleanup_synthetic_business(db_session, b3)
    assert rows3 != rows1


def _sales_fingerprint(db, business_id):
    from app.models.sale import Sale

    return sorted(
        (str(s.sale_date), int(s.quantity), float(s.unit_price))
        for s in db.query(Sale).filter(Sale.business_id == business_id).all()
    )


# --- statistics --------------------------------------------------------


def test_summ_matches_numpy_and_t_interval():
    from scipy import stats

    xs = [0.0, 0.2, 0.4, 0.4, 0.5, 0.9, 1.0, 0.3, 0.6, 0.1]
    s = ms._summ(xs)
    arr = np.array(xs)
    assert s["n"] == 10
    assert s["mean"] == pytest.approx(float(arr.mean()), abs=1e-4)
    assert s["std"] == pytest.approx(float(arr.std(ddof=1)), abs=1e-4)
    assert s["median"] == pytest.approx(float(np.median(arr)), abs=1e-4)
    half = stats.t.ppf(0.975, 9) * arr.std(ddof=1) / np.sqrt(10)
    assert s["ci95"][0] == pytest.approx(float(arr.mean() - half), abs=1e-4)
    assert s["ci95"][1] == pytest.approx(float(arr.mean() + half), abs=1e-4)


def test_summ_handles_degenerate_input():
    assert ms._summ([]) is None
    one = ms._summ([0.5])
    assert one["n"] == 1 and one["std"] == 0.0 and one["ci95"] is None
    assert ms._summ([None, None]) is None


def test_paired_all_zero_differences_reports_not_assessed():
    out = ms._paired([0.3, 0.3, 0.3], [0.3, 0.3, 0.3], "goal_achievement", "B")
    assert out["p_value"] is None
    assert "not assessed" in out["interpretation"].lower()
    assert out["full_wins"] == 0 and out["ties"] == 3 and out["full_losses"] == 0


def test_paired_runs_wilcoxon_when_differences_exist():
    full = [0.5, 0.6, 0.4, 0.7, 0.5, 0.6, 0.55, 0.62]
    other = [0.2, 0.3, 0.35, 0.4, 0.25, 0.3, 0.28, 0.31]
    out = ms._paired(full, other, "goal_achievement", "A")
    assert out["test"].startswith("Wilcoxon")
    assert out["p_value"] is not None and 0.0 <= out["p_value"] <= 1.0
    assert out["full_wins"] == 8
    assert out["mean_difference"] > 0


# --- end-to-end (small) ------------------------------------------------


def test_multi_scenario_architecture_small_run_is_traceable(db_session, monkeypatch):
    model_registry_service.sync_from_file_registry(db_session)
    monkeypatch.setattr(ms, "SCENARIOS", ms.SCENARIOS[:2])   # 2 scenarios keeps it fast
    result = ms.run_multi_scenario_architecture(db_session, seeds=[42, 43])

    assert result["scenario_count"] == 2 and result["seed_count"] == 2
    assert result["evaluation_count"] == 2 * 2 * 4            # scenarios x seeds x architectures
    assert len(result["observations"]) == result["evaluation_count"]

    # every aggregate traces back to the individual observations
    ga_d = [o["goal_achievement"] for o in result["observations"] if o["architecture"] == "D"]
    agg_d = result["aggregates"]["D"]["goal_achievement"]
    assert agg_d["n"] == len(ga_d)
    assert agg_d["mean"] == pytest.approx(float(np.mean(ga_d)), abs=1e-4)

    # fairness: for one (scenario, seed) all 4 architectures share the target
    for sid in ("S01", "S02"):
        for seed in (42, 43):
            grp = [o for o in result["observations"]
                   if o["scenario_id"] == sid and o["seed"] == seed]
            assert len(grp) == 4
            assert len({o["goal_target_percent"] for o in grp}) == 1
            assert len({o["kpi_measured"] for o in grp}) == 1

    # paired blocks exist and are keyed on the same pairs
    assert set(result["paired"]) == {"D_vs_A", "D_vs_B"}
    assert result["paired"]["D_vs_A"]["n_pairs"] == 4

    # no leakage: observations carry only decision-time / simulated fields,
    # never an "actual_outcome"
    assert not any("actual" in k for o in result["observations"] for k in o)


def test_same_scenario_seed_reproduces_same_architecture_result(db_session, monkeypatch):
    model_registry_service.sync_from_file_registry(db_session)
    monkeypatch.setattr(ms, "SCENARIOS", ms.SCENARIOS[:1])
    r1 = ms.run_multi_scenario_architecture(db_session, seeds=[42])
    r2 = ms.run_multi_scenario_architecture(db_session, seeds=[42])

    def key(o):
        return (o["scenario_id"], o["seed"], o["architecture"])

    m1 = {key(o): (o["goal_achievement"], o["risk_adjusted_score"], o["selected_strategy"]) for o in r1["observations"]}
    m2 = {key(o): (o["goal_achievement"], o["risk_adjusted_score"], o["selected_strategy"]) for o in r2["observations"]}
    assert m1 == m2
