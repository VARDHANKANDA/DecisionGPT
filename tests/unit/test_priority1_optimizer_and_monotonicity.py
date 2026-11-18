"""Tests verifying Priority 1: scenario propagation, constraint handling, monotonicity, and optimizer behavior."""
import pytest
from app.agents import business_analyst, financial_advisor, risk_manager, single_agent, strategy_optimizer
from app.agents.strategy_optimizer import compute_strategy_score, resolve
from app.analytics.digital_twin_service import SimulationOutput
from app.models.goal import Goal


def _dummy_output(units=100.0, base_units=100.0, rev=1000.0, base_rev=1000.0,
                  profit=200.0, base_profit=200.0, risk_score=0.1, risk_level="LOW",
                  inventory_constrained=False, band_width=100.0):
    return SimulationOutput(
        expected_units_sold=units,
        baseline_units_sold=base_units,
        expected_revenue=rev,
        baseline_revenue=base_rev,
        expected_profit=profit,
        baseline_profit=base_profit,
        profit_note=None,
        customer_impact=0,
        inventory_constrained=inventory_constrained,
        risk_level=risk_level,
        risk_score=risk_score,
        revenue_lower_bound=rev - band_width / 2,
        revenue_upper_bound=rev + band_width / 2,
        model_name="test_model",
        model_version="v1",
    )


def _dummy_goal(kpi="revenue", target=10.0):
    return Goal(
        business_id="biz-1",
        objective="increase_revenue",
        target_value=target,
        target_unit="percent",
        primary_kpi=kpi,
        time_horizon=14,
        status="active",
    )


def test_monotonicity_business_analyst_growth():
    """Higher projected unit sales growth must produce weakly monotonic higher BA score."""
    goal = _dummy_goal()
    out1 = _dummy_output(units=110.0, base_units=100.0)  # +10%
    out2 = _dummy_output(units=120.0, base_units=100.0)  # +20%
    out3 = _dummy_output(units=90.0, base_units=100.0)   # -10%

    ba1 = business_analyst.evaluate(out1, goal).score
    ba2 = business_analyst.evaluate(out2, goal).score
    ba3 = business_analyst.evaluate(out3, goal).score

    assert ba3 < ba1 < ba2
    assert ba1 == pytest.approx(0.60, abs=1e-3)
    assert ba2 == pytest.approx(0.70, abs=1e-3)
    assert ba3 == pytest.approx(0.40, abs=1e-3)


def test_monotonicity_risk_manager_safety():
    """Higher extrapolation risk score must monotonically reduce RM safety score."""
    goal = _dummy_goal()
    out_low = _dummy_output(risk_score=0.05, risk_level="LOW")
    out_mid = _dummy_output(risk_score=0.30, risk_level="MODERATE")
    out_high = _dummy_output(risk_score=0.60, risk_level="HIGH")

    rm_low = risk_manager.evaluate(out_low, goal).score
    rm_mid = risk_manager.evaluate(out_mid, goal).score
    rm_high = risk_manager.evaluate(out_high, goal).score

    assert rm_high < rm_mid < rm_low


def test_constraint_handling_inventory_penalty():
    """Operational constraint: inventory exhaustion must trigger dedicated 0.15 penalty."""
    goal = _dummy_goal()
    out_unconstrained = _dummy_output(inventory_constrained=False)
    out_constrained = _dummy_output(inventory_constrained=True)

    rm_u = risk_manager.evaluate(out_unconstrained, goal)
    rm_c = risk_manager.evaluate(out_constrained, goal)

    assert any("inventory" in r.lower() for r in rm_c.risks)
    assert rm_u.score - rm_c.score == pytest.approx(0.15, abs=1e-3)


def test_constraint_handling_high_risk_peer_challenge():
    """High extrapolation risk must cause RM to challenge optimistic peers in peer review."""
    goal = _dummy_goal()
    out = _dummy_output(units=130.0, risk_score=0.65, risk_level="HIGH")
    ba = business_analyst.evaluate(out, goal)
    fa = financial_advisor.evaluate(out, goal)
    rm = risk_manager.evaluate(out, goal)

    rev = risk_manager.review(rm, {"business_analyst": ba, "financial_advisor": fa}, out)
    assert not rev.concurs
    assert any("HIGH" in c for c in rev.challenges)


def test_optimizer_lambda_calibration_tradeoff():
    """Verifies that calibrated lambda=0.25 prevents crushing profitable strategies."""
    ba_score = 0.68   # strong growth (+18%)
    fa_score = 0.68
    rm_score = 0.40   # moderate risk deduction (1 - RM = 0.60)

    # Status-quo / passive action:
    ba_passive = 0.50
    fa_passive = 0.50
    rm_passive = 0.95  # minimal risk (1 - RM = 0.05)

    # With lambda = 1.0 (uncalibrated production):
    score_prod_growth = compute_strategy_score(ba_score, fa_score, rm_score, risk_penalty_weight=1.0)
    score_prod_passive = compute_strategy_score(ba_passive, fa_passive, rm_passive, risk_penalty_weight=1.0)
    # 0.68 - 0.60 = 0.08 vs 0.50 - 0.05 = 0.45:
    assert score_prod_growth < score_prod_passive  # Pathology confirmed: passive action erroneously wins under lambda=1.0

    # With lambda = 0.25 (calibrated):
    score_calib_growth = compute_strategy_score(ba_score, fa_score, rm_score, risk_penalty_weight=0.25)
    score_calib_passive = compute_strategy_score(ba_passive, fa_passive, rm_passive, risk_penalty_weight=0.25)
    # 0.68 - 0.15 = 0.53 vs 0.50 - 0.0125 = 0.4875:
    assert score_calib_growth > score_calib_passive  # High-payoff action correctly preserved


def test_peer_review_ablation_isolation():
    """Verifies that empty reviews list isolates Round 1 scores without modification."""
    goal = _dummy_goal()
    out = _dummy_output(units=90.0, base_units=100.0, risk_score=0.4)
    ba = business_analyst.evaluate(out, goal)
    fa = financial_advisor.evaluate(out, goal)
    rm = risk_manager.evaluate(out, goal)
    round1 = {"business_analyst": ba, "financial_advisor": fa, "risk_manager": rm}

    # With peer review:
    rev = [business_analyst.review(ba, {"financial_advisor": fa, "risk_manager": rm}, out)]
    res_reviewed = resolve(round1, rev, out, risk_penalty_weight=0.25)

    # Without peer review:
    res_unreviewed = resolve(round1, [], out, risk_penalty_weight=0.25)

    assert res_unreviewed.round2_scores == res_unreviewed.round1_scores
    assert len(res_unreviewed.conflicts) == 0


def test_calibrated_multiplicative_scoring_non_negative():
    """Multiplicative scoring prevents negative numbers and bounds scores strictly to [0, 1]."""
    # Worst case: low growth (0.2), zero safety (RM=0.0)
    score_linear = compute_strategy_score(0.2, 0.2, 0.0, risk_penalty_weight=1.0, scoring_mode="linear")
    score_calib = compute_strategy_score(0.2, 0.2, 0.0, risk_penalty_weight=1.0, scoring_mode="calibrated")

    assert score_linear == -0.80  # Negative utility pathology in linear formula
    assert score_calib == 0.0     # Calibrated score is non-negative and bounded
    assert 0.0 <= score_calib <= 1.0


def test_peer_review_bidirectional_reconciliation():
    """Positive peer consensus on margin and safety lifts BA/FA scores constructively."""
    goal = _dummy_goal(kpi="profit", target=15.0)
    out = _dummy_output(units=105.0, base_units=100.0, profit=250.0, base_profit=200.0, risk_score=0.05, risk_level="LOW")
    ba = business_analyst.evaluate(out, goal)
    fa = financial_advisor.evaluate(out, goal)
    rm = risk_manager.evaluate(out, goal)

    assert ba.score == pytest.approx(0.55, abs=1e-3)
    assert fa.score == pytest.approx(0.75, abs=1e-3)
    assert rm.score >= 0.70

    # Peer review with positive confirmation
    rev_ba = business_analyst.review(ba, {"financial_advisor": fa, "risk_manager": rm}, out)
    rev_fa = financial_advisor.review(fa, {"business_analyst": ba, "risk_manager": rm}, out)

    assert rev_ba.adjusted_score is not None
    assert rev_ba.adjusted_score > ba.score  # Constructive upward reconciliation (+0.03)
    assert rev_fa.adjusted_score is not None
    assert rev_fa.adjusted_score > fa.score  # Constructive upward reconciliation (+0.03)


def test_duplicate_objection_deduplication():
    """Identical challenges across peer reviews must not duplicate in ResolvedDecision.conflicts."""
    goal = _dummy_goal()
    out = _dummy_output(units=130.0, risk_score=0.70, risk_level="HIGH")
    ba = business_analyst.evaluate(out, goal)
    fa = financial_advisor.evaluate(out, goal)
    rm = risk_manager.evaluate(out, goal)
    round1 = {"business_analyst": ba, "financial_advisor": fa, "risk_manager": rm}

    rev_rm = risk_manager.review(rm, {"business_analyst": ba, "financial_advisor": fa}, out)
    # Pass review list with a duplicated review
    res = resolve(round1, [rev_rm, rev_rm], out)

    unique_challenges = {(c["raised_by"], c["concern"]) for c in res.conflicts}
    assert len(res.conflicts) == len(unique_challenges)  # Zero duplicates in conflict trace


def test_edge_case_zero_demand_and_missing_profit():
    """Evaluates zero sales baseline and missing unit cost without error or fabrication."""
    goal = _dummy_goal(kpi="revenue")
    out_zero = _dummy_output(units=0.0, base_units=0.0, rev=0.0, base_rev=0.0, profit=None, base_profit=None)
    ba = business_analyst.evaluate(out_zero, goal)
    fa = financial_advisor.evaluate(out_zero, goal)

    assert ba.score == 0.50  # Neutral baseline
    assert fa.score == 0.50  # Neutral baseline
    assert fa.meta["basis"] == "revenue"  # Honest fallback


def test_hard_constraint_preservation_under_extreme_risk():
    """Confirms that extreme extrapolation risk (risk_score >= 0.8) and inventory exhaustion
    continue to favor the safe baseline even under calibrated scoring."""
    goal = _dummy_goal()
    out_extreme = _dummy_output(units=150.0, base_units=100.0, risk_score=0.85, risk_level="HIGH", inventory_constrained=True)
    out_safe = _dummy_output(units=100.0, base_units=100.0, risk_score=0.02, risk_level="LOW", inventory_constrained=False)

    ba_ext = business_analyst.evaluate(out_extreme, goal)
    fa_ext = financial_advisor.evaluate(out_extreme, goal)
    rm_ext = risk_manager.evaluate(out_extreme, goal)

    ba_safe = business_analyst.evaluate(out_safe, goal)
    fa_safe = financial_advisor.evaluate(out_safe, goal)
    rm_safe = risk_manager.evaluate(out_safe, goal)

    score_ext = compute_strategy_score(ba_ext.score, fa_ext.score, rm_ext.score, risk_penalty_weight=0.35, scoring_mode="calibrated")
    score_safe = compute_strategy_score(ba_safe.score, fa_safe.score, rm_safe.score, risk_penalty_weight=0.35, scoring_mode="calibrated")

    # Safe strategy must strictly win over extreme risk with inventory failure
    assert score_safe > score_ext
    assert rm_ext.score < 0.20

