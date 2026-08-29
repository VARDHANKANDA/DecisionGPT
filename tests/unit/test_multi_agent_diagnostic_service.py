"""Multi-Agent degradation diagnostic — trace extraction, override detection,
failure classification, aggregation, determinism, traceability, no fabrication.
"""
import pytest

from app.services import multi_agent_diagnostic_service as diag
from app.services import multi_scenario_service as ms
from app.services import model_registry_service


# --- classifier (pure) -------------------------------------------------


def _base_trace(**over):
    t = {
        "disagreement": True, "kpi_is_proxy": False, "goal_primary_kpi": "revenue",
        "dt_best_strategy": "Price +5%", "final_strategy": "Marketing +10%",
        "d_candidate_names": ["Marketing +10%", "Price -5%"],
        "d_candidates": [
            {"strategy": "Marketing +10%", "final_score": 0.0, "ba1": 0.5, "fa1": 0.5, "rm1": 0.5, "round2_moved": False},
            {"strategy": "Price -5%", "final_score": -0.04, "ba1": 0.5, "fa1": 0.42, "rm1": 0.5, "round2_moved": False},
        ],
    }
    t.update(over)
    return t


def test_classify_match_when_no_disagreement():
    mode, _ = diag._classify(_base_trace(disagreement=False))
    assert mode == diag.MATCH


def test_classify_unsupported_kpi():
    mode, _ = diag._classify(_base_trace(kpi_is_proxy=True, goal_primary_kpi="inventory_risk"))
    assert mode == diag.UNSUPPORTED_KPI


def test_classify_candidate_set_mismatch():
    # 'Price +5%' (DT best) not in D's generated candidate set
    mode, ev = diag._classify(_base_trace())
    assert mode == diag.CANDIDATE_SET_MISMATCH
    assert "not in Full DecisionGPT's generated candidate set" in ev.lower() or "not in full" in ev.lower()


def test_classify_risk_overrule():
    t = _base_trace(
        d_candidate_names=["Price +5%", "Marketing -10%"],
        final_strategy="Marketing -10%",
        d_candidates=[
            {"strategy": "Price +5%", "final_score": -0.5, "ba1": 0.5, "fa1": 0.5, "rm1": 0.0, "round2_moved": False},
            {"strategy": "Marketing -10%", "final_score": 0.0, "ba1": 0.5, "fa1": 0.5, "rm1": 0.5, "round2_moved": False},
        ],
    )
    mode, ev = diag._classify(t)
    assert mode == diag.RISK_OVERRULE
    assert "risk manager" in ev.lower()


def test_classify_agent_overrule():
    t = _base_trace(
        d_candidate_names=["Price +5%", "Marketing +10%"],
        d_candidates=[
            {"strategy": "Price +5%", "final_score": 0.0, "ba1": 0.5, "fa1": 0.5, "rm1": 0.5, "round2_moved": False},
            {"strategy": "Marketing +10%", "final_score": 0.2, "ba1": 0.7, "fa1": 0.7, "rm1": 0.5, "round2_moved": False},
        ],
    )
    mode, _ = diag._classify(t)
    assert mode == diag.AGENT_OVERRULE


def test_classify_tie_break():
    t = _base_trace(
        d_candidate_names=["Price +5%", "Marketing +10%"],
        d_candidates=[
            {"strategy": "Price +5%", "final_score": 0.0, "ba1": 0.5, "fa1": 0.5, "rm1": 0.5, "round2_moved": False},
            {"strategy": "Marketing +10%", "final_score": 0.0, "ba1": 0.5, "fa1": 0.5, "rm1": 0.5, "round2_moved": False},
        ],
    )
    mode, _ = diag._classify(t)
    assert mode == diag.TIE_BREAK


# --- aggregation -----------------------------------------------------


def test_aggregate_candidate_coverage_block():
    traces = [
        {"disagreement": True, "improvement": -0.4, "failure_mode": diag.CANDIDATE_SET_MISMATCH,
         "dt_best_revenue": 100.0, "dt_best_kpi_attainment": 0.4, "final_goal_achievement": 0.0,
         "causal_evidence_level": "assumed", "confidence": 0.13, "risk_manager_top_pick": "M",
         "dt_best_strategy": "Price +5%", "dt_candidate_count": 6, "full_candidate_count": 6,
         "dt_best_strategy_present_in_full": False, "dt_best_strategy_supported": True,
         "scenario_id": "S01", "seed": 42, "goal_objective": "increase_revenue"},
        {"disagreement": True, "improvement": -0.1, "failure_mode": diag.RISK_OVERRULE,
         "dt_best_revenue": 200.0, "dt_best_kpi_attainment": 0.6, "final_goal_achievement": 0.0,
         "causal_evidence_level": "assumed", "confidence": 0.13, "risk_manager_top_pick": "M",
         "dt_best_strategy": "Price +5%", "dt_candidate_count": 6, "full_candidate_count": 8,
         "dt_best_strategy_present_in_full": True, "dt_best_strategy_supported": True,
         "scenario_id": "S02", "seed": 42, "goal_objective": "increase_profit"},
        {"disagreement": True, "improvement": -0.5, "failure_mode": diag.UNSUPPORTED_KPI,
         "dt_best_revenue": 50.0, "dt_best_kpi_attainment": 0.5, "final_goal_achievement": 0.0,
         "causal_evidence_level": "assumed", "confidence": 0.1, "risk_manager_top_pick": "M",
         "dt_best_strategy": "Price +5%", "dt_candidate_count": 6, "full_candidate_count": 5,
         "dt_best_strategy_present_in_full": False, "dt_best_strategy_supported": False,  # proxy KPI
         "scenario_id": "S04", "seed": 42, "goal_objective": "reduce_inventory_risk"},
    ]
    cov = diag._aggregate(traces, [42])["candidate_coverage"]
    assert cov["pairs_checked"] == 3
    assert cov["dt_best_present_in_full"] == 1
    assert cov["candidate_coverage_rate"] == pytest.approx(1 / 3, abs=1e-3)
    # only S01 is a MISSING *supported* strategy — S04's is not supported for its goal
    assert cov["missing_supported_strategy_rate"] == pytest.approx(1 / 3, abs=1e-3)
    assert cov["invariant_dt_best_present_when_supported"] is False
    assert cov["missing_pairs"] == [
        {"scenario_id": "S01", "seed": 42, "dt_best_strategy": "Price +5%", "goal_objective": "increase_revenue"}
    ]


def test_aggregate_counts_and_rates():
    traces = [
        {"disagreement": True, "improvement": -0.4, "failure_mode": diag.CANDIDATE_SET_MISMATCH,
         "dt_best_revenue": 100.0, "dt_best_kpi_attainment": 0.4, "final_goal_achievement": 0.0,
         "causal_evidence_level": "assumed", "confidence": 0.13, "risk_manager_top_pick": "M", "dt_best_strategy": "P"},
        {"disagreement": True, "improvement": -0.6, "failure_mode": diag.RISK_OVERRULE,
         "dt_best_revenue": 200.0, "dt_best_kpi_attainment": 0.6, "final_goal_achievement": 0.0,
         "causal_evidence_level": "assumed", "confidence": 0.13, "risk_manager_top_pick": "M", "dt_best_strategy": "P"},
        {"disagreement": False, "improvement": 0.0, "failure_mode": diag.MATCH,
         "dt_best_revenue": 50.0, "dt_best_kpi_attainment": 0.5, "final_goal_achievement": 0.5,
         "causal_evidence_level": "assumed", "confidence": 0.2, "risk_manager_top_pick": "P", "dt_best_strategy": "P"},
    ]
    agg = diag._aggregate(traces, [42])
    assert agg["total_scenario_seed_pairs"] == 3
    assert agg["digital_twin_to_final"] == {"unchanged": 1, "overridden": 2, "override_rate": 0.6667}
    assert agg["override_outcomes"]["degraded"] == 2
    assert agg["override_outcomes"]["override_degradation_rate"] == 1.0
    assert agg["failure_modes"][diag.CANDIDATE_SET_MISMATCH]["count"] == 1
    # CAUSAL_PENALTY / CONFIDENCE_PENALTY are 0 by construction, with the note
    assert agg["failure_modes"][diag.CAUSAL_PENALTY]["count"] == 0
    assert "by construction" in agg["failure_modes"][diag.CAUSAL_PENALTY]["note"]
    assert agg["digital_twin_mean_goal_achievement"] == pytest.approx(0.5, abs=1e-4)
    assert agg["full_decisiongpt_mean_goal_achievement"] == pytest.approx(0.1667, abs=1e-3)


# --- end-to-end (small, deterministic) ------------------------------


def test_diagnostic_small_run_deterministic_and_traceable(db_session, monkeypatch):
    model_registry_service.sync_from_file_registry(db_session)
    monkeypatch.setattr(ms, "SCENARIOS", ms.SCENARIOS[:2])   # S01 revenue, S02 profit
    r1 = diag.run_diagnostic(db_session, seeds=[42])
    r2 = diag.run_diagnostic(db_session, seeds=[42])

    assert r1["total_scenario_seed_pairs"] == 2
    assert len(r1["traces"]) == 2
    # every trace carries only decision-time / simulated fields — no "actual outcome"
    for t in r1["traces"]:
        assert not any("actual" in k for k in t)
        assert t["failure_mode"] in {
            diag.MATCH, diag.AGENT_OVERRULE, diag.RISK_OVERRULE, diag.CANDIDATE_SET_MISMATCH,
            diag.OPTIMIZER_RERANKING, diag.UNSUPPORTED_KPI, diag.TIE_BREAK,
            diag.NO_VALID_STRATEGY, diag.OTHER,
        }
        assert t["mechanism_evidence"]          # non-empty evidence sentence

    # deterministic: same seeds -> identical classification + numbers
    def norm(res):
        return [
            (t["scenario_id"], t["seed"], t["dt_best_strategy"], t["final_strategy"],
             t["failure_mode"], t["improvement"])
            for t in res["traces"]
        ]

    assert norm(r1) == norm(r2)


def test_diagnostic_d_selection_matches_multi_scenario_observation(db_session, monkeypatch):
    """Traceability: the diagnostic's Full-pipeline selection for a (scenario,
    seed) reproduces the multi_scenario_architecture arch-D observation."""
    from app.services import multi_scenario_service

    model_registry_service.sync_from_file_registry(db_session)
    monkeypatch.setattr(ms, "SCENARIOS", ms.SCENARIOS[:1])
    monkeypatch.setattr(multi_scenario_service, "SCENARIOS", multi_scenario_service.SCENARIOS[:1])

    arch = multi_scenario_service.run_multi_scenario_architecture(db_session, seeds=[42])
    d_obs = next(o for o in arch["observations"] if o["architecture"] == "D")

    diagnostic = diag.run_diagnostic(db_session, seeds=[42])
    d_trace = diagnostic["traces"][0]

    assert d_trace["scenario_id"] == d_obs["scenario_id"]
    assert d_trace["final_strategy"] == d_obs["selected_strategy"]
    assert d_trace["final_goal_achievement"] == pytest.approx(d_obs["goal_achievement"], abs=1e-4)
