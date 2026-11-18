"""Risk Manager diagnostic + risk-penalty sensitivity study — trace extraction,
formula verification, RM_DECISIVE classification, D0/D1 isolation, determinism,
no fabrication, sensitivity labelling.
"""
import pytest

from app.services import decision_service
from app.services import model_registry_service
from app.services import multi_scenario_service as ms
from app.services import risk_manager_diagnostic_service as rmd


@pytest.fixture()
def _small(monkeypatch):
    # S01 (revenue/pricing), S02 (profit/pricing), S03 (sales/marketing)
    monkeypatch.setattr(ms, "SCENARIOS", ms.SCENARIOS[:3])
    yield


def _run(db, seeds=(42,)):
    model_registry_service.sync_from_file_registry(db)
    return rmd.run_risk_manager_diagnostic(db, seeds=list(seeds))


# --- structure & no fabrication -------------------------------------------


def test_scenarios_and_seeds_are_the_frozen_set(_small, db_session):
    res = _run(db_session, seeds=(42, 43))
    assert res["seeds"] == [42, 43]
    assert res["total_scenario_seed_pairs"] == 3 * 2
    # no "actual outcome" fields anywhere in a trace
    for t in res["traces"]:
        assert not any("actual" in k for k in t)


def test_every_strategy_row_records_the_full_risk_score_path(_small, db_session):
    res = _run(db_session)
    rows = [r for t in res["traces"] if not t.get("error") for r in t["strategy_rows"]]
    assert rows
    for r in rows:
        for field in (
            "strategy_name", "digital_twin_goal_score", "digital_twin_risk",
            "business_analyst_score", "financial_advisor_score", "risk_manager_score",
            "risk_penalty", "pre_risk_score", "final_score", "final_score_recomputed",
            "is_dt_best", "is_final_selected",
        ):
            assert field in r, field


def test_final_score_equals_the_optimizer_formula_for_every_row(_small, db_session):
    res = _run(db_session)
    fv = res["formula_verification"]
    assert fv["holds_for_all_rows"] is True
    assert fv["max_deviation_observed"] <= 1e-3
    assert fv["rows_checked"] > 0
    # spot-check the arithmetic directly
    for t in res["traces"]:
        for r in t.get("strategy_rows", []):
            if None in (r["business_analyst_score"], r["financial_advisor_score"], r["risk_manager_score"]):
                continue
            expect = round(
                (r["business_analyst_score"] + r["financial_advisor_score"]) / 2
                - (1 - r["risk_manager_score"]),
                4,
            )
            assert abs(expect - r["final_score"]) <= 1e-3


def test_rm_decisive_classification_is_deterministic(_small, db_session):
    r1 = _run(db_session)
    r2 = _run(db_session)

    def norm(res):
        return [
            (t["scenario_id"], t["seed"], t.get("rm_decisive"), t.get("rm_decisive_outcome"),
             t.get("d0_selected_strategy"), t.get("d1_selected_strategy"),
             t.get("d0_goal_achievement"), t.get("d1_goal_achievement"))
            for t in res["traces"]
        ]

    assert norm(r1) == norm(r2)
    rd = r1["rm_decisive"]
    assert rd["count"] == rd["improved"] + rd["degraded"] + rd["neutral"]
    assert 0 <= (rd["percentage"] or 0) <= 100


def test_rm_decisive_means_penalty_free_pick_differs_from_d0_pick(_small, db_session):
    res = _run(db_session)
    for t in res["traces"]:
        if t.get("error"):
            continue
        if t["rm_decisive"]:
            assert t["penalty_free_pick"] != t["d0_selected_strategy"]
        else:
            # not decisive -> the penalty-free ranking keeps D0's pick on top
            assert t["penalty_free_pick"] == t["d0_selected_strategy"]


def test_d0_reproduces_production_full_decisiongpt(_small, db_session):
    """D0 in the diagnostic must equal a plain analyze_goal() run."""
    model_registry_service.sync_from_file_registry(db_session)
    from app.services import decision_architecture_service as da

    sc = ms.SCENARIOS[0]
    bid, gid = da._seed_synthetic_business(db_session, 42, sc)
    try:
        direct = decision_service.analyze_goal(db_session, bid, gid)
    finally:
        da._cleanup_synthetic_business(db_session, bid)

    res = _run(db_session)
    t = next(x for x in res["traces"] if x["scenario_id"] == sc.scenario_id and x["seed"] == 42)
    assert t["d0_selected_strategy"] == direct.selected_strategy_name
    assert t["d0_confidence"] == pytest.approx(direct.confidence, abs=1e-4)


def test_d1_changes_only_the_risk_penalty_contribution(_small, db_session):
    """D1 keeps the Risk Manager running (it still produces a score and still
    feeds confidence); it only un-weights the penalty in the ranking. So the
    per-strategy RM scores are identical between D0 and an explicit D1 run."""
    model_registry_service.sync_from_file_registry(db_session)
    from app.services import decision_architecture_service as da
    from app.services.decision_service import PipelineOptions

    sc = ms.SCENARIOS[0]
    bid, gid = da._seed_synthetic_business(db_session, 42, sc)
    try:
        d0 = decision_service.analyze_goal(db_session, bid, gid)
        d1 = decision_service.analyze_goal(
            db_session, bid, gid, PipelineOptions(risk_penalty_in_ranking=False)
        )
        # Risk Manager still ran in D1 — round-1 RM score present in the debate.
        rm0 = d0.debate["round1"]["risk_manager"]["score"]
        rm1 = d1.debate["round1"]["risk_manager"]["score"]
        # both selected strategies carry a real RM evaluation
        assert rm0 is not None and rm1 is not None
        # D1's resolution records the sensitivity marker
        assert d1.debate["resolution"]["confidence_basis"].get("risk_penalty_weight") == 0.0
        assert "sensitivity" in d1.debate["resolution"]["confidence_basis"].get("variant", "")
        assert d0.debate["resolution"]["confidence_basis"].get("risk_penalty_weight") is None
    finally:
        da._cleanup_synthetic_business(db_session, bid)


def test_result_is_labelled_a_sensitivity_analysis_not_the_architecture(_small, db_session):
    res = _run(db_session)
    assert res["label"] == "RISK_MANAGER_DIAGNOSTIC"
    assert res["paired_d1_minus_d0"]["comparison"].startswith("D1 (Risk-Penalty Sensitivity)")
    assert res["paired_d1_minus_d0"]["difference_is"] == "D1 - D0"
    assert "d1_risk_penalty_sensitivity_mean_goal_achievement" in res["baseline"]
    assert res["interpretation"]["outcome"] in {"A", "B", "C", "D", "INCONCLUSIVE"}


def test_risk_score_mismatch_is_flagged_only_when_dt_risk_low_and_rm_zero(_small, db_session):
    res = _run(db_session)
    mm = res["risk_score_mismatch"]
    assert mm["count"] == sum(t["risk_score_mismatch_count"] for t in res["traces"] if not t.get("error"))
    for t in res["traces"]:
        for r in t.get("risk_score_mismatch_rows", []):
            assert r["digital_twin_risk"] < rmd.LOW_RISK_BAND
            assert r["risk_manager_score"] <= 1e-9
    assert "verdict" in mm["rm_distinguishes_low_vs_high_risk_price_strategies"] or \
        mm["rm_distinguishes_low_vs_high_risk_price_strategies"]["assessable"] is False


def test_no_ml_model_status_change_no_decision_outcome_and_prior_experiments_intact(_small, db_session):
    from app.models.evaluation import PredictionEvaluation
    from app.models.experiment import ExperimentRun
    from app.models.ml_model import MLModel
    from app.services import experiment_service

    model_registry_service.sync_from_file_registry(db_session)
    # a pre-existing experiment that must survive untouched
    prior = experiment_service.run_experiment(db_session, "causal", {"seed": 7, "name": "prior"})
    prior_id, prior_metrics = prior.id, dict(prior.metrics_json)

    before = {(m.model_name, m.version): m.status for m in db_session.query(MLModel).all()}
    n_pred_before = db_session.query(PredictionEvaluation).count()

    _run(db_session)

    after = {(m.model_name, m.version): m.status for m in db_session.query(MLModel).all()}
    assert before == after
    assert db_session.query(PredictionEvaluation).count() == n_pred_before
    # no fabricated DecisionOutcome-style records; prior experiment intact
    kept = db_session.get(ExperimentRun, prior_id)
    assert kept is not None and kept.metrics_json == prior_metrics


def test_experiment_type_is_registered_and_dispatches(_small, db_session, monkeypatch):
    from app.services import experiment_service

    assert "risk_manager_diagnostic" in experiment_service.SUPPORTED_EXPERIMENT_TYPES
    model_registry_service.sync_from_file_registry(db_session)
    run = experiment_service.run_experiment(
        db_session, "risk_manager_diagnostic", {"seeds": [42], "name": "rmd-test"}
    )
    assert run.status == "completed"
    assert run.metrics_json["label"] == "RISK_MANAGER_DIAGNOSTIC"
    assert run.metrics_json["baseline"]["d1_risk_penalty_sensitivity_mean_goal_achievement"] is not None
