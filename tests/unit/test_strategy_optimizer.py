"""Strategy optimizer scoring formula — the fixed §7 rule and the research-only
risk-penalty sensitivity weight (docs/RISK_MANAGER_DIAGNOSTIC_REPORT.md).

The production formula is never changed: `risk_penalty_weight` defaults to 1.0
and every production caller uses the default. A weight of 0.0 is a labelled
sensitivity variant that drops ONLY the risk-penalty term from the ranking
score — the Risk Manager still produces its score.
"""
from app.agents.strategy_optimizer import FORMULA_VERSION, compute_strategy_score


def test_default_weight_is_the_fixed_v2_formula():
    # (BA+FA)/2 - (1-RM)
    assert compute_strategy_score(0.6, 0.4, 0.5) == round((0.6 + 0.4) / 2 - (1 - 0.5), 4)
    assert compute_strategy_score(0.5, 0.5, 0.0) == round(0.5 - 1.0, 4)  # RM=0 -> full penalty
    assert compute_strategy_score(0.5, 0.5, 1.0) == round(0.5 - 0.0, 4)  # RM=1 -> no penalty
    assert FORMULA_VERSION == "v2"


def test_explicit_weight_one_equals_default():
    for ba, fa, rm in [(0.5, 0.5, 0.0), (0.6, 0.4, 0.5), (0.7, 0.3, 0.9), (0.55, 0.62, 0.0)]:
        assert compute_strategy_score(ba, fa, rm, risk_penalty_weight=1.0) == compute_strategy_score(ba, fa, rm)


def test_zero_weight_removes_only_the_risk_penalty_term():
    # penalty-free score is the mean growth score alone, regardless of RM
    assert compute_strategy_score(0.5, 0.5, 0.0, risk_penalty_weight=0.0) == 0.5
    assert compute_strategy_score(0.6, 0.4, 0.0, risk_penalty_weight=0.0) == 0.5
    assert compute_strategy_score(0.575, 0.575, 0.0, risk_penalty_weight=0.0) == 0.575
    # RM score no longer moves the result
    assert compute_strategy_score(0.5, 0.5, 0.0, risk_penalty_weight=0.0) == compute_strategy_score(
        0.5, 0.5, 1.0, risk_penalty_weight=0.0
    )


def test_bounded_lambda_weights_scale_the_penalty_linearly():
    # R2 variants: final = growth - λ·(1-RM). λ ∈ {0.25, 0.50, 0.75}.
    growth_ba, growth_fa, rm = 0.5, 0.5, 0.0   # (1-RM) = 1.0
    for lam in (0.25, 0.50, 0.75):
        assert compute_strategy_score(growth_ba, growth_fa, rm, risk_penalty_weight=lam) == round(
            0.5 - lam * 1.0, 4
        )
    # a partially-safe strategy: penalty shrinks with λ
    assert compute_strategy_score(0.5, 0.5, 0.4, risk_penalty_weight=0.5) == round(0.5 - 0.5 * 0.6, 4)


def test_zero_weight_lifts_a_price_move_above_a_zero_benefit_marketing_move():
    # the exact mechanism the diagnostic isolates: a price strategy with strong
    # growth scores but RM=0 loses under the production formula, wins without it.
    price_default = compute_strategy_score(0.575, 0.575, 0.0)          # 0.575 - 1.0 = -0.425
    marketing_default = compute_strategy_score(0.5, 0.5, 0.5)           # 0.5 - 0.5 = 0.0
    assert price_default < marketing_default

    price_pf = compute_strategy_score(0.575, 0.575, 0.0, risk_penalty_weight=0.0)   # 0.575
    marketing_pf = compute_strategy_score(0.5, 0.5, 0.5, risk_penalty_weight=0.0)   # 0.5
    assert price_pf > marketing_pf
