from app.services import decision_architecture_service, model_registry_service
from app.models.business import Business


def test_run_produces_all_four_architectures_and_cleans_up(db_session):
    model_registry_service.sync_from_file_registry(db_session)

    run = decision_architecture_service.run_decision_architecture_experiment(db_session, seed=1)

    assert [r.architecture for r in run.results] == ["A", "B", "C", "D"]
    for r in run.results:
        assert r.latency_seconds >= 0

    # A never recommends a strategy (no decision-making mechanism).
    a = run.results[0]
    assert a.selected_strategy_name is None
    assert a.expected_benefit == 0.0

    # B, C, D all had real data to work with and should have selected something.
    for r in run.results[1:]:
        assert r.selected_strategy_name is not None

    # The synthetic business must be fully cleaned up afterwards.
    remaining = db_session.query(Business).filter(Business.name.like("Research Synthetic Business%")).count()
    assert remaining == 0


def test_goal_achievement_is_bounded_and_real(db_session):
    model_registry_service.sync_from_file_registry(db_session)
    run = decision_architecture_service.run_decision_architecture_experiment(db_session, seed=2)
    for r in run.results:
        assert 0.0 <= r.goal_achievement <= 1.0


def test_cleanup_happens_even_if_an_architecture_raises(db_session, monkeypatch):
    model_registry_service.sync_from_file_registry(db_session)

    def boom(*args, **kwargs):
        raise RuntimeError("simulated failure")

    monkeypatch.setattr(decision_architecture_service, "_run_architecture_d", boom)

    try:
        decision_architecture_service.run_decision_architecture_experiment(db_session, seed=3)
    except RuntimeError:
        pass

    remaining = db_session.query(Business).filter(Business.name.like("Research Synthetic Business%")).count()
    assert remaining == 0
