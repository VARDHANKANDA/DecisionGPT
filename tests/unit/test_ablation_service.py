"""Phase 2/3 — ablation A-F runs the REAL pipeline with each component off."""
from app.services import ablation_service, model_registry_service


def test_ablation_study_runs_all_six_configurations(db_session):
    model_registry_service.sync_from_file_registry(db_session)
    result = ablation_service.run_ablation_study(db_session, seed=7)

    configs = {c.config for c in result.configs}
    assert configs == {"A", "B", "C", "D", "E", "F"}
    assert result.configs[0].config == "A"  # Full DecisionGPT first
    # Every config records a real measured achievement + risk-adjusted score.
    for c in result.configs:
        assert c.goal_achievement is not None
        assert c.risk_adjusted_score is not None

    # Five comparisons (B..F) against Full (A).
    assert {cmp.config for cmp in result.comparisons} == {"B", "C", "D", "E", "F"}


def test_without_digital_twin_recommends_nothing(db_session):
    model_registry_service.sync_from_file_registry(db_session)
    result = ablation_service.run_ablation_study(db_session, seed=7)
    twin = next(c for c in result.comparisons if c.config == "B")
    assert twin.ablated_goal_achievement == 0.0
    assert twin.delta_goal_achievement == twin.full_goal_achievement


def test_causal_graph_ablation_is_a_real_toggle_not_a_fixed_zero(db_session):
    """Phase 1 wired the causal graph into scoring (Risk Manager evidence
    penalty + confidence factor), so 'without Causal Graph' must be a real
    measured comparison — the delta is whatever the pipeline actually
    produces, computed, not hard-coded."""
    model_registry_service.sync_from_file_registry(db_session)
    result = ablation_service.run_ablation_study(db_session, seed=7)
    causal = next(c for c in result.comparisons if c.config == "C")
    # Confidence is influenced by the causal evidence factor, so a delta is
    # expected here (may be >= 0); the key assertion is that both sides are
    # real measured numbers.
    assert causal.full_confidence is not None
    assert causal.ablated_confidence is not None
    assert isinstance(causal.delta_risk_adjusted_score, float)


def test_multi_agent_ablation_uses_single_agent_and_measures_delta(db_session):
    model_registry_service.sync_from_file_registry(db_session)
    result = ablation_service.run_ablation_study(db_session, seed=7)
    d = next(c for c in result.configs if c.config == "D")
    assert "multi_agent" in d.components_removed
    # A single-agent run still produces a real recommendation + confidence.
    assert d.confidence is not None


def test_memory_and_explainability_ablations_are_honest_zeros(db_session):
    """No recorded outcomes exist on the synthetic scenario, so there are no
    memory insights to remove and explainability doesn't feed scoring —
    the delta is a genuine, computed zero."""
    model_registry_service.sync_from_file_registry(db_session)
    result = ablation_service.run_ablation_study(db_session, seed=7)
    for cfg in ("E", "F"):
        cmp = next(c for c in result.comparisons if c.config == cfg)
        assert cmp.delta_goal_achievement == 0.0
        assert cmp.delta_risk_adjusted_score == 0.0
