"""Research Console — Multi-Agent Evaluation (docs Phase 6,
docs/RESEARCH_SPECIFICATION.md §8 baselines, §10 ablation).

Reads the latest recorded decision-architecture / multi-agent / ablation
experiments for the configuration comparison, and aggregates real
``Decision.debate_json`` for the debate statistics. Never uses the term
"agent accuracy" (there is no ground-truth decision benchmark). Every
configuration shown is one for which a real experiment result exists.
"""
from statistics import mean

from sqlalchemy.orm import Session

from app.models.decision import Decision
from app.models.experiment import ExperimentRun


def _latest(db: Session, experiment_type: str) -> ExperimentRun | None:
    return (
        db.query(ExperimentRun)
        .filter(ExperimentRun.experiment_type == experiment_type, ExperimentRun.status == "completed")
        .order_by(ExperimentRun.created_at.desc())
        .first()
    )


def _latest_n(db: Session, experiment_type: str, n: int) -> list[ExperimentRun]:
    return (
        db.query(ExperimentRun)
        .filter(ExperimentRun.experiment_type == experiment_type, ExperimentRun.status == "completed")
        .order_by(ExperimentRun.created_at.desc())
        .limit(n)
        .all()
    )


def _architecture_rows(run: ExperimentRun | None) -> list[dict]:
    if run is None:
        return []
    results = (run.metrics_json or {}).get("results", [])
    return [
        {
            "architecture": r.get("architecture"),
            "label": r.get("label"),
            "selected_strategy": r.get("selected_strategy_name"),
            "goal_achievement": r.get("goal_achievement"),
            "risk_adjusted_score": r.get("risk_adjusted_score"),
            "expected_benefit": r.get("expected_benefit"),
            "latency_seconds": r.get("latency_seconds"),
            "note": r.get("note", ""),
        }
        for r in results
    ]


def _debate_analysis(db: Session) -> dict:
    decisions = (
        db.query(Decision).order_by(Decision.created_at.desc()).all()
    )
    with_debate = [d for d in decisions if isinstance(d.debate_json, dict) and d.debate_json.get("multi_agent")]
    if not with_debate:
        return {
            "decisions_with_debate": 0,
            "message": "No multi-agent decisions have been recorded yet — run a decision analysis to populate debate statistics.",
        }

    conflict_counts = []
    score_change_events = 0
    agreements = 0
    confidences = []
    agents_involved = []
    for d in with_debate:
        dj = d.debate_json
        res = dj.get("resolution", {}) or {}
        conflicts = res.get("conflicts", []) or []
        conflict_counts.append(len(conflicts))
        if not conflicts:
            agreements += 1
        r1 = res.get("round1_scores", {}) or {}
        r2 = res.get("round2_scores", {}) or {}
        for agent, s1 in r1.items():
            if agent in r2 and abs((r2[agent] or 0) - (s1 or 0)) > 1e-9:
                score_change_events += 1
        if isinstance(res.get("confidence"), (int, float)):
            confidences.append(res["confidence"])
        agents_involved.append(len(dj.get("round1", {}) or {}))

    sample = with_debate[0].debate_json
    return {
        "decisions_with_debate": len(with_debate),
        "avg_agents_involved": round(mean(agents_involved), 2) if agents_involved else None,
        "total_conflicts": sum(conflict_counts),
        "avg_conflicts_per_decision": round(mean(conflict_counts), 2) if conflict_counts else 0,
        "decisions_with_full_agreement": agreements,
        "post_review_score_changes": score_change_events,
        "avg_confidence": round(mean(confidences), 4) if confidences else None,
        "latest_decision": {
            "decision_id": with_debate[0].id,
            "rounds": sample.get("rounds"),
            "round1_scores": (sample.get("resolution", {}) or {}).get("round1_scores"),
            "round2_scores": (sample.get("resolution", {}) or {}).get("round2_scores"),
            "conflicts": (sample.get("resolution", {}) or {}).get("conflicts"),
            "resolution_rationale": (sample.get("resolution", {}) or {}).get("resolution_rationale"),
            "confidence": (sample.get("resolution", {}) or {}).get("confidence"),
        },
    }


def _diagnostic_summary(run: ExperimentRun | None) -> dict | None:
    """The multi-agent degradation diagnostic (research-only). Every number
    comes straight from the stored multi_agent_diagnostic experiment — no
    recomputation, no hard-coded metric."""
    if run is None:
        return None
    m = run.metrics_json or {}
    traces = m.get("traces", [])
    # a compact scenario/seed drill-down (the full traces stay in the export)
    drill = [
        {
            "scenario_id": t.get("scenario_id"), "seed": t.get("seed"),
            "goal_objective": t.get("goal_objective"),
            "digital_twin_best": t.get("dt_best_strategy"),
            "final_strategy": t.get("final_strategy"),
            "disagreement": t.get("disagreement"),
            "failure_mode": t.get("failure_mode"),
            "improvement": t.get("improvement"),
            "final_goal_achievement": t.get("final_goal_achievement"),
            "risk_manager_top_pick": t.get("risk_manager_top_pick"),
            "mechanism_evidence": t.get("mechanism_evidence"),
        }
        for t in traces
    ]
    return {
        "experiment_id": run.id,
        "experiment_name": run.experiment_name,
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "seeds": m.get("seeds"),
        "total_scenario_seed_pairs": m.get("total_scenario_seed_pairs"),
        "candidate_coverage": m.get("candidate_coverage"),
        "digital_twin_to_final": m.get("digital_twin_to_final"),
        "override_outcomes": m.get("override_outcomes"),
        "failure_modes": m.get("failure_modes"),
        "central_hypothesis": m.get("central_hypothesis"),
        "risk_manager_effect": m.get("risk_manager_effect"),
        "optimizer_effect": m.get("optimizer_effect"),
        "causal_evidence_effect": m.get("causal_evidence_effect"),
        "digital_twin_mean_goal_achievement": m.get("digital_twin_mean_goal_achievement"),
        "full_decisiongpt_mean_goal_achievement": m.get("full_decisiongpt_mean_goal_achievement"),
        "failure_analysis_figure": m.get("failure_analysis_figure"),
        "scenario_drilldown": drill,
    }


def _risk_manager_diagnostic_summary(run: ExperimentRun | None) -> dict | None:
    """The Risk Manager diagnostic + risk-penalty sensitivity study
    (research-only). Every number is read from the stored
    risk_manager_diagnostic experiment — nothing recomputed, nothing
    hard-coded. D1 is a labelled sensitivity variant, NOT the architecture."""
    if run is None:
        return None
    m = run.metrics_json or {}
    traces = m.get("traces", [])
    drill = [
        {
            "scenario_id": t.get("scenario_id"), "seed": t.get("seed"),
            "goal_objective": t.get("goal_objective"),
            "d0_selected_strategy": t.get("d0_selected_strategy"),
            "d1_selected_strategy": t.get("d1_selected_strategy"),
            "d0_goal_achievement": t.get("d0_goal_achievement"),
            "d1_goal_achievement": t.get("d1_goal_achievement"),
            "d0_confidence": t.get("d0_confidence"),
            "d1_confidence": t.get("d1_confidence"),
            "rm_decisive": t.get("rm_decisive"),
            "rm_decisive_outcome": t.get("rm_decisive_outcome"),
            "rm_top_pick": t.get("rm_top_pick"),
            "dt_sweep_best_strategy": t.get("dt_sweep_best_strategy"),
            "risk_score_mismatch_count": t.get("risk_score_mismatch_count"),
        }
        for t in traces
    ]
    return {
        "experiment_id": run.id,
        "experiment_name": run.experiment_name,
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "seeds": m.get("seeds"),
        "total_scenario_seed_pairs": m.get("total_scenario_seed_pairs"),
        "baseline": m.get("baseline"),
        "formula_verification": m.get("formula_verification"),
        "risk_manager_disagreement": m.get("risk_manager_disagreement"),
        "rm_decisive": m.get("rm_decisive"),
        "risk_score_mismatch": m.get("risk_score_mismatch"),
        "d0_vs_d1": m.get("d0_vs_d1"),
        "paired_d1_minus_d0": m.get("paired_d1_minus_d0"),
        "interpretation": m.get("interpretation"),
        "scenario_drilldown": drill,
    }


def _risk_calibration_summary(run: ExperimentRun | None) -> dict | None:
    """The principled Risk Manager calibration study (research-only). Every
    number is read from the stored risk_manager_calibration experiment. All
    variants are EXPERIMENTAL — production stays R0 / D0."""
    if run is None:
        return None
    m = run.metrics_json or {}
    return {
        "experiment_id": run.id,
        "experiment_name": run.experiment_name,
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "seeds": m.get("seeds"),
        "total_scenario_seed_pairs": m.get("total_scenario_seed_pairs"),
        "risk_formula_versions": m.get("risk_formula_versions"),
        "r3_selection": m.get("r3_selection"),
        "digital_twin_mean_goal_achievement": m.get("digital_twin_mean_goal_achievement"),
        "variants": m.get("variants"),
        "aggregates": m.get("aggregates"),
        "paired_vs_r0": m.get("paired_vs_r0"),
        "zero_variance_diagnostic": m.get("zero_variance_diagnostic"),
        "pre_specified_criteria": m.get("pre_specified_criteria"),
        "criteria_evaluation": m.get("criteria_evaluation"),
        "verdict": m.get("verdict"),
        "verdict_by_variant": m.get("verdict_by_variant"),
        "best_calibration_variant": m.get("best_calibration_variant"),
    }


def get_agent_evaluation(db: Session) -> dict:
    arch_run = _latest(db, "decision_architecture")
    ablation_run = _latest(db, "ablation")
    multi_agent_run = _latest(db, "multi_agent")
    diagnostic_runs = _latest_n(db, "multi_agent_diagnostic", 2)
    rm_diagnostic_run = _latest(db, "risk_manager_diagnostic")
    rm_calibration_run = _latest(db, "risk_manager_calibration")

    architecture_rows = _architecture_rows(arch_run)

    single_vs_multi = None
    if multi_agent_run is not None:
        m = multi_agent_run.metrics_json or {}
        single_vs_multi = {
            "experiment_id": multi_agent_run.id,
            "single_agent": m.get("single_agent"),
            "multi_agent": m.get("multi_agent"),
        }

    empty_state = None
    if arch_run is None and multi_agent_run is None:
        empty_state = (
            "No decision-architecture or multi-agent experiment has been run yet. Run one from "
            "Experiments (type 'decision_architecture' or 'multi_agent') to compare configurations."
        )

    return {
        "architecture_comparison": {
            "experiment_id": arch_run.id if arch_run else None,
            "seed": arch_run.random_seed if arch_run else None,
            "created_at": arch_run.created_at.isoformat() if arch_run and arch_run.created_at else None,
            "goal_target_percent": (arch_run.metrics_json or {}).get("goal_target_percent") if arch_run else None,
            "rows": architecture_rows,
        },
        "single_vs_multi_agent": single_vs_multi,
        "ablation": {
            "experiment_id": ablation_run.id if ablation_run else None,
            "configs": (ablation_run.metrics_json or {}).get("configs", []) if ablation_run else [],
            "comparisons": (ablation_run.metrics_json or {}).get("comparisons", []) if ablation_run else [],
        },
        "debate_analysis": _debate_analysis(db),
        "multi_agent_diagnostic": _diagnostic_summary(diagnostic_runs[0] if diagnostic_runs else None),
        "multi_agent_diagnostic_previous": (
            _diagnostic_summary(diagnostic_runs[1]) if len(diagnostic_runs) > 1 else None
        ),
        "risk_manager_diagnostic": _risk_manager_diagnostic_summary(rm_diagnostic_run),
        "risk_manager_calibration": _risk_calibration_summary(rm_calibration_run),
        "empty_state": empty_state,
    }
