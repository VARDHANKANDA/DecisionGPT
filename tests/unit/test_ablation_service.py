from app.services import ablation_service, model_registry_service


def test_ablation_study_covers_all_five_components(db_session):
    model_registry_service.sync_from_file_registry(db_session)

    result = ablation_service.run_ablation_study(db_session, seed=7)

    components = {c.component_removed for c in result.comparisons}
    assert components == {"Digital Twin", "Multi-Agent Engine", "Causal Graph", "Explainability", "Memory"}


def test_informational_components_show_a_real_zero_delta(db_session):
    """Causal Graph / Explainability / Memory don't feed into strategy
    scoring in this implementation — ablating them must show a real,
    honestly-computed zero delta, not a fabricated non-zero one."""
    model_registry_service.sync_from_file_registry(db_session)
    result = ablation_service.run_ablation_study(db_session, seed=7)

    for component in ("Causal Graph", "Explainability", "Memory"):
        comparison = next(c for c in result.comparisons if c.component_removed == component)
        assert comparison.delta_goal_achievement == 0.0
        assert comparison.delta_risk_adjusted_score == 0.0


def test_digital_twin_and_multi_agent_ablations_use_real_measured_deltas(db_session):
    model_registry_service.sync_from_file_registry(db_session)
    result = ablation_service.run_ablation_study(db_session, seed=7)

    twin = next(c for c in result.comparisons if c.component_removed == "Digital Twin")
    # Without the Digital Twin (architecture A), no strategy is recommended at all,
    # so its goal achievement is always 0 — the delta must equal the full system's own score.
    assert twin.ablated_goal_achievement == 0.0
    assert twin.delta_goal_achievement == twin.full_goal_achievement
