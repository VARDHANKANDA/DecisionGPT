"""Unit tests for backend/app/evaluation/harness.py (Phase 2).

DB-free helper tests + ONE mocked ``run_instance`` smoke test that exercises the
harness wiring without running the real production pipeline. The full 50+/locked
evaluation is NOT run here (Phase 2 stop condition).
"""
from types import SimpleNamespace

import pytest

from app.evaluation import harness as hz
from app.evaluation import scenario_families as sf


# --------------------------------------------------------------------------- #
# DB-free helpers                                                            #
# --------------------------------------------------------------------------- #
def test_sig_and_space_hash_are_order_insensitive_and_stable():
    a1 = ({"type": "price_change", "value": -5.0}, {"type": "marketing_change", "value": 10.0})
    a2 = ({"type": "marketing_change", "value": 10.0}, {"type": "price_change", "value": -5.0})
    assert hz._sig(a1) == hz._sig(a2)
    assert hz._space_hash([a1, a2]) == hz._space_hash([a2, a1])


def test_verify_identical_action_space_ok_and_mismatch():
    s = sf.generate_suite(len(sf.FAMILY_IDS), master_seed=1)[0]     # increase_revenue -> 8 production actions
    ok, detail = hz.verify_identical_action_space(s, list(s.feasible_actions))
    assert ok and detail["identical"] is True and detail["declared_count"] == detail["resolved_count"]

    dropped = list(s.feasible_actions)[:-1]
    ok2, detail2 = hz.verify_identical_action_space(s, dropped)
    assert not ok2 and detail2["only_declared"]


def test_map_selection_to_action_uses_production_naming():
    from app.services.decision_service import strategy_name_for_actions
    feasible = [
        ({"type": "marketing_change", "value": 10.0},),
        ({"type": "price_change", "value": -5.0},),
        ({"type": "marketing_change", "value": 10.0}, {"type": "price_change", "value": -5.0}),
    ]
    name = strategy_name_for_actions([{"type": "price_change", "value": -5.0}])
    act, in_set = hz._map_selection_to_action(name, feasible)
    assert in_set and act == feasible[1]

    # a name outside the feasible set is parsed but flagged not-in-set
    outside = strategy_name_for_actions([{"type": "price_change", "value": 25.0}])
    act2, in_set2 = hz._map_selection_to_action(outside, feasible)
    assert not in_set2 and act2 == ({"type": "price_change", "value": 25.0},)


def test_parse_strategy_name_roundtrip_and_failure():
    assert hz._parse_strategy_name("Marketing +10% & Price -5%") == (
        {"type": "marketing_change", "value": 10.0}, {"type": "price_change", "value": -5.0})
    assert hz._parse_strategy_name("not a strategy name") is None


def test_exclusion_logic():
    ok = hz.ConditionResult("A", "ok", None, None, None, None, None, None, None, 0.0)
    bad = hz.ConditionResult("B", "error", None, None, None, None, None, None, None, 0.0)
    assert hz._exclusion(True, {"A": ok, "B": ok, "C": ok})[0] is False
    assert hz._exclusion(False, {"A": ok, "B": ok, "C": ok}) == (True, "identical_action_space_invariant_failed")
    ex, reason = hz._exclusion(True, {"A": ok, "B": bad, "C": ok})
    assert ex and "B" in reason


# --------------------------------------------------------------------------- #
# mocked run_instance smoke test                                             #
# --------------------------------------------------------------------------- #
def _fake_output(revenue, profit, units, risk_score):
    return SimpleNamespace(
        expected_revenue=revenue, baseline_revenue=revenue * 0.9,
        expected_profit=profit, baseline_profit=profit * 0.9,
        expected_units_sold=units, baseline_units_sold=units * 0.9,
        risk_score=risk_score, risk_level=("LOW" if risk_score < 0.15 else "HIGH"),
        revenue_upper_bound=revenue * 1.1, revenue_lower_bound=revenue * 0.9,
        inventory_constrained=False, model_name="fake", model_version="v0",
    )


@pytest.fixture()
def _mock_pipeline(monkeypatch):
    """Replace the three production entry points + agents with light, deterministic
    fakes so the harness wiring can be exercised without the real pipeline."""
    def fake_generate_candidates(db, business_id, goal):
        # mirror the production revenue action set for the eval scenario's objective
        acts = sf.production_candidate_actions(goal.objective)
        cands = [SimpleNamespace(actions=[dict(x) for x in a],
                                 name="c", rationale="", goal_alignment="", targets=[], assumptions=[])
                 for a in acts]
        return SimpleNamespace(goal_id=goal.id, objective=goal.objective, candidates=cands,
                               excluded=[], constraints_applied=[], notes=[])

    def fake_simulate_strategy(db, business_id, actions, **kw):
        # a monotone toy: a small price rise helps revenue; big marketing helps a bit; risk from |price move|
        pp = next((a.value for a in actions if a.type == "price_change"), 0.0)
        mp = next((a.value for a in actions if a.type == "marketing_change"), 0.0)
        rev = 20000.0 * (1 + 0.004 * pp + 0.0015 * mp)
        prof = rev - 12000.0
        units = 200.0 * (1 + 0.001 * mp - 0.002 * pp)
        risk = min(1.0, abs(pp) / 8.0)
        return SimpleNamespace(output=_fake_output(rev, prof, units, risk))

    def fake_analyze_goal(db, business_id, goal_id, options=None):
        assert options is None, "condition D must call analyze_goal with default PipelineOptions"
        from app.services.decision_service import strategy_name_for_actions
        return SimpleNamespace(
            selected_strategy_name=strategy_name_for_actions([{"type": "price_change", "value": 5}]),
            confidence=0.14,
            expected_outcome={"expected_revenue": 20400.0, "baseline_revenue": 20000.0,
                              "expected_profit": 8400.0, "baseline_profit": 8000.0,
                              "expected_units_sold": 198.0, "baseline_units_sold": 200.0},
            trace={}, strategy_generation={}, alternatives=[],
        )

    monkeypatch.setattr("app.services.strategy_generation_service.generate_candidates", fake_generate_candidates)
    monkeypatch.setattr("app.analytics.digital_twin_service.simulate_strategy", fake_simulate_strategy)
    monkeypatch.setattr("app.services.decision_service.analyze_goal", fake_analyze_goal)
    for mod, fn in (("business_analyst", lambda o, g, **k: SimpleNamespace(score=0.5)),
                    ("financial_advisor", lambda o, g, **k: SimpleNamespace(score=0.5)),
                    ("risk_manager", lambda o, g, **k: SimpleNamespace(score=1 - o.risk_score)),
                    ("single_agent", None)):
        if fn is not None:
            monkeypatch.setattr(f"app.agents.{mod}.evaluate", fn)
    monkeypatch.setattr("app.agents.single_agent.evaluate",
                        lambda o: SimpleNamespace(score=round((o.expected_revenue / o.baseline_revenue - 1)
                                                              * (1 - o.risk_score), 4)))
    # digital_twin_service.Action is a real dataclass; keep it.
    return monkeypatch


def test_run_instance_smoke_produces_exogenous_primary_and_checks_invariant(db_session, _mock_pipeline):
    scn = next(s for s in sf.generate_suite(30, master_seed=20260906)
               if s.family_id == "demand_uncertainty")
    res = hz.run_instance(db_session, scn, seed=40000)

    assert isinstance(res, hz.InstanceResult)
    assert res.scenario_id == scn.scenario_id
    assert res.action_space_invariant_ok is True          # fake generator mirrors the declared set
    assert res.exclude_from_primary is False

    for cond in ("A", "B", "C", "D"):
        c = res.conditions[cond]
        # PRIMARY metric is the EXOGENOUS normalised regret / performance, in [0, 1]
        assert c["primary_regret"] is None or 0.0 <= c["primary_regret"] <= 1.0
        assert c["primary_normalized"] is None or 0.0 <= c["primary_normalized"] <= 1.0

    # baselines came from ground_truth, not the pipeline
    assert res.baselines["oracle"]["status"] == "ok"
    assert res.baselines["naive"]["action_key"] == "noop"

    # D used the frozen default options (asserted inside fake_analyze_goal)
    assert res.conditions["D"]["status"] in ("ok", "pick_outside_feasible_set")
    # secondary internal metric is recorded but clearly separate from the primary
    assert "secondary_goal_achievement" in res.conditions["D"]

    # mechanism factors present (pre-run + merged)
    assert set(res.factors) >= {"uncertainty", "constraint_tightness", "risk_exposure",
                                "action_space_size"}
    assert res.agent_diagnostics["assessable"] in (True, False)


def test_run_instance_marks_insufficient_data_when_twin_fails_on_all_actions(db_session, _mock_pipeline, monkeypatch):
    scn = next(s for s in sf.generate_suite(30, master_seed=20260906) if s.family_id == "demand_uncertainty")

    def failing_sim(db, business_id, actions, **kw):
        raise RuntimeError("InsufficientDataError: not enough history")

    monkeypatch.setattr("app.analytics.digital_twin_service.simulate_strategy", failing_sim)
    monkeypatch.setattr("app.services.decision_service.analyze_goal",
                        lambda db, b, g, options=None: (_ for _ in ()).throw(
                            RuntimeError("InsufficientDataError: not enough history")))
    res = hz.run_instance(db_session, scn, seed=40000)
    assert res.conditions["B"]["status"] == "insufficient_data"
    assert res.conditions["C"]["status"] == "insufficient_data"
    assert res.conditions["D"]["status"] == "insufficient_data"
    assert res.exclude_from_primary is True
    assert res.exclude_reason == "insufficient_data"
    # condition A still completes (it recommends the status quo and never calls the twin)
    assert res.conditions["A"]["status"] == "ok"


def test_run_instance_flags_invariant_violation_for_exclusion(db_session, _mock_pipeline, monkeypatch):
    scn = next(s for s in sf.generate_suite(30, master_seed=20260906)
               if s.family_id == "demand_uncertainty")

    def short_generate(db, business_id, goal):
        full = sf.production_candidate_actions(goal.objective)[:-2]   # drop 2 -> invariant fails
        cands = [SimpleNamespace(actions=[dict(x) for x in a], name="c", rationale="",
                                 goal_alignment="", targets=[], assumptions=[]) for a in full]
        return SimpleNamespace(goal_id=goal.id, objective=goal.objective, candidates=cands,
                               excluded=[], constraints_applied=[], notes=[])

    monkeypatch.setattr("app.services.strategy_generation_service.generate_candidates", short_generate)
    res = hz.run_instance(db_session, scn, seed=40000)
    assert res.action_space_invariant_ok is False
    assert res.exclude_from_primary is True
    assert res.exclude_reason == "identical_action_space_invariant_failed"
