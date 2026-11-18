from app.services.llm_service import LLMService


def test_parses_profit_goal_with_percent_and_horizon():
    parsed = LLMService().parse_goal("Increase profit by 15% in the next 3 months.")
    assert parsed.objective == "increase_profit"
    assert parsed.target_value == 15.0
    assert parsed.target_unit == "percent"
    assert parsed.primary_kpi == "profit"
    assert parsed.time_horizon_months == 3
    assert parsed.parse_warnings == []


def test_parses_churn_goal():
    parsed = LLMService().parse_goal("Reduce churn by 10%")
    assert parsed.objective == "reduce_churn"
    assert parsed.primary_kpi == "churn_rate"
    assert parsed.target_value == 10.0


def test_unparseable_text_returns_warnings_not_a_crash():
    parsed = LLMService().parse_goal("Make the business better somehow.")
    assert parsed.objective is None
    assert parsed.target_value is None
    assert len(parsed.parse_warnings) >= 1
