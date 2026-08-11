"""Strategy Optimizer — docs/MULTI_AGENT_SPECIFICATION.md §2, §7.

The one fixed scoring formula (§7: "Fix the scoring formula before final
experiments"), version-tagged so experiments referencing it stay
reproducible even if it's revised later:

    strategy_score = normalized_goal_benefit - normalized_risk_penalty

where `normalized_goal_benefit` is the mean of the Business Analyst and
Financial Advisor scores (do they independently think this strategy grows
the business?) and `normalized_risk_penalty` is `1 - risk_manager_score`
(the Risk Manager's score is already a 0..1 safety score). This is how
"agent disagreement" (§2 Strategy Optimizer bullet) gets resolved: a
strategy the growth-focused agents like but the Risk Manager doesn't gets
pulled back down, rather than any agent's number being overridden.
"""

FORMULA_VERSION = "v1"


def compute_strategy_score(
    business_analyst_score: float, financial_advisor_score: float, risk_manager_score: float
) -> float:
    goal_benefit = (business_analyst_score + financial_advisor_score) / 2
    risk_penalty = 1.0 - risk_manager_score
    return round(goal_benefit - risk_penalty, 4)
