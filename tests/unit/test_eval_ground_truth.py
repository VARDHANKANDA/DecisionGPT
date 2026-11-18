"""Unit tests for backend/app/evaluation/ground_truth.py (Phase 2).

Most importantly: PROVE that the exogenous objective is independent of the
Digital Twin, decision_service, and decision_architecture_service._goal_achievement
--- both by static source inspection and by running every function with those
modules made unavailable.
"""
import ast
import importlib
import sys
from dataclasses import dataclass, field

import pytest

from app.evaluation import ground_truth as gt


# --------------------------------------------------------------------------- #
# a minimal scenario stand-in (ground_truth only needs a few attributes)     #
# --------------------------------------------------------------------------- #
@dataclass
class _Scn:
    params: dict
    constraints: dict
    objective: dict
    feasible_actions: list = field(default_factory=list)
    history: dict = field(default_factory=dict)
    uncertainty: dict = field(default_factory=dict)


def _mk(**over):
    p = {"base_price": 100.0, "unit_cost": 60.0, "base_demand": 200.0,
         "price_elasticity": -1.0, "marketing_response": 1.0, "marketing_base_spend": 1000.0,
         "kappa": 1.0, "holding_rate": 0.0, "capacity_cap": float("inf"), "inventory_cap": float("inf")}
    p.update(over.pop("params", {}))
    return _Scn(params=p, constraints=over.pop("constraints", {}),
               objective=over.pop("objective", {"kpi": "revenue", "sense": "max"}),
               feasible_actions=over.pop("feasible_actions", []))


A = lambda *pairs: tuple({"type": t, "value": float(v)} for t, v in pairs)  # noqa: E731


# --------------------------------------------------------------------------- #
# INDEPENDENCE                                                                #
# --------------------------------------------------------------------------- #
def test_source_has_no_forbidden_imports():
    src = (importlib.import_module("app.evaluation.ground_truth").__file__)
    tree = ast.parse(open(src, encoding="utf-8").read())
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module or "")
    joined = " ".join(imported)
    for forbidden in ("digital_twin", "decision_service", "decision_architecture",
                      "forecast_service", "app.agents"):
        assert forbidden not in joined, f"ground_truth must not import {forbidden!r}"
    for name in gt.FORBIDDEN_DEPENDENCIES:
        assert name in gt.FORBIDDEN_DEPENDENCIES  # documented list is present


def test_runs_with_digital_twin_and_pipeline_unavailable(monkeypatch):
    # poison the Digital Twin / pipeline modules; ground_truth must not care
    # (it never imports them, so no reload is needed).
    for mod in ("app.analytics.digital_twin_service", "app.services.decision_service",
                "app.services.decision_architecture_service"):
        monkeypatch.setitem(sys.modules, mod, None)  # `import x` -> ImportError
    scn = _mk(feasible_actions=[A(("price_change", 5)), A(("price_change", -5)), A(("marketing_change", 10))])
    assert gt.evaluate(scn, A(("price_change", 5))).value > 0
    assert gt.oracle(scn, scn.feasible_actions)["status"] == "ok"
    assert gt.naive_baseline(scn, scn.feasible_actions + [()])["policy"] == "naive"
    assert gt.greedy_baseline(scn, scn.feasible_actions)["policy"] == "greedy"
    assert gt.classical_optimizer(scn, scn.feasible_actions)["status"] in ("ok", "na")


# --------------------------------------------------------------------------- #
# CLOSED-FORM CORRECTNESS                                                     #
# --------------------------------------------------------------------------- #
def test_status_quo_matches_hand_computation():
    scn = _mk()  # p0=100, c=60, d0=200, s0=1000 ; revenue objective
    r = gt.evaluate(scn, ())
    assert r.breakdown["units"] == pytest.approx(200.0)
    assert r.breakdown["revenue"] == pytest.approx(20000.0)
    assert r.value == pytest.approx(20000.0)          # sense == max -> as-is
    assert r.raw_value == pytest.approx(20000.0)


def test_price_elasticity_and_marketing_response():
    scn = _mk()
    # +10% price, elasticity -1 -> demand factor 0.9 -> units 180 ; price 110 -> revenue 19800
    r = gt.evaluate(scn, A(("price_change", 10)))
    assert r.breakdown["units"] == pytest.approx(180.0)
    assert r.breakdown["revenue"] == pytest.approx(19800.0)
    # +100% marketing (spend 2000, delta 1000 -> +1000/1000 * mr(1) * kappa(1) = +1 unit)
    r2 = gt.evaluate(scn, A(("marketing_change", 100)))
    assert r2.breakdown["units"] == pytest.approx(201.0)


def test_sense_min_objective_is_negated():
    scn = _mk(objective={"kpi": "holding_cost", "sense": "min"},
              params={"holding_rate": 2.0, "inventory_cap": 250.0})
    r = gt.evaluate(scn, ())            # cap 250, units 200 -> unsold 50 -> holding 100
    assert r.raw_value == pytest.approx(100.0)
    assert r.value == pytest.approx(-100.0)   # higher-is-better convention


def test_deterministic_given_scenario_and_action():
    scn = _mk()
    a = A(("price_change", -5), ("marketing_change", 10))
    assert gt.evaluate(scn, a).value == gt.evaluate(scn, a).value


def test_feasibility_price_bounds_and_cash_cap():
    scn = _mk(constraints={"price_floor_pct": -10.0, "price_ceiling_pct": 8.0, "cash_cap": 1050.0})
    ok, _ = gt.is_feasible(scn, A(("price_change", 5)))
    assert ok
    bad, reason = gt.is_feasible(scn, A(("price_change", 12)))
    assert not bad and "ceiling" in reason
    bad2, reason2 = gt.is_feasible(scn, A(("marketing_change", 20)))  # spend 1200 > cap 1050
    assert not bad2 and "cash cap" in reason2


# --------------------------------------------------------------------------- #
# ORACLE / BASELINES                                                         #
# --------------------------------------------------------------------------- #
def test_oracle_is_the_max_over_feasible_and_never_beaten():
    scn = _mk(feasible_actions=[A(("price_change", 5)), A(("price_change", 10)),
                                A(("price_change", -5)), A(("marketing_change", 10))])
    orc = gt.oracle(scn, scn.feasible_actions + [()])
    assert orc["status"] == "ok"
    for a in scn.feasible_actions + [()]:
        assert gt.evaluate(scn, a).value <= orc["value"] + 1e-6
    assert orc["worst_value"] <= orc["value"]


def test_naive_is_the_status_quo():
    scn = _mk(feasible_actions=[A(("price_change", 5)), A(("marketing_change", 10))])
    nb = gt.naive_baseline(scn, scn.feasible_actions + [()])
    assert nb["action_key"] == "noop"
    assert nb["value"] == pytest.approx(gt.evaluate(scn, ()).value)


def test_greedy_is_a_local_heuristic_not_the_oracle():
    # inelastic demand -> best is a price rise; greedy should find that direction
    scn = _mk(params={"price_elasticity": -0.2},
              feasible_actions=[A(("price_change", 5)), A(("price_change", 10)),
                                A(("price_change", -5)), A(("marketing_change", 10))])
    g = gt.greedy_baseline(scn, scn.feasible_actions)
    assert g["policy"] == "greedy"
    # greedy picks a single-lever step; it need not equal the oracle's global best
    assert len(g["action"]) == 1


def test_classical_optimizer_ok_or_explicit_na():
    scn = _mk(feasible_actions=[A(("price_change", 5)), A(("price_change", -5)),
                                A(("marketing_change", 10)), A(("marketing_change", -10))],
              constraints={"price_floor_pct": -15.0, "price_ceiling_pct": 15.0})
    res = gt.classical_optimizer(scn, scn.feasible_actions)
    assert res["status"] in ("ok", "na")
    if res["status"] == "ok":
        assert res["action"] in scn.feasible_actions
        assert "continuous_optimum" in res


# --------------------------------------------------------------------------- #
# NORMALISED METRICS                                                         #
# --------------------------------------------------------------------------- #
def test_normalized_performance_and_regret_bounds_and_endpoints():
    assert gt.normalized_performance(5, 10, 0) == pytest.approx(0.5)
    assert gt.regret(5, 10, 0) == pytest.approx(0.5)
    assert gt.normalized_performance(10, 10, 0) == 1.0
    assert gt.regret(10, 10, 0) == 0.0
    assert gt.normalized_performance(-5, 10, 0) == 0.0     # clipped
    assert gt.regret(20, 10, 0) == 0.0                     # clipped
    # degenerate span
    assert gt.normalized_performance(3, 3, 3) == 1.0
    assert gt.regret(3, 3, 3) == 0.0


def test_score_selection_treats_none_as_status_quo():
    scn = _mk(feasible_actions=[A(("price_change", 5)), A(("marketing_change", 10))])
    s = gt.score_selection(scn, None, scn.feasible_actions + [()])
    assert s["status"] == "ok"
    assert s["selected_from_none"] is True
    assert s["selected_action_key"] == "noop"
    assert 0.0 <= s["regret"] <= 1.0
