"""Research Console — Risk Manager diagnostic + controlled risk-penalty
sensitivity study (docs/RISK_MANAGER_DIAGNOSTIC_REPORT.md).

The candidate-space confound is fixed (docs/CANDIDATE_SPACE_CORRECTION_REPORT.md)
and Full DecisionGPT still trails Prediction + Digital Twin (0.084 vs 0.486,
p < 0.0001). Every Full-vs-DigitalTwin disagreement now routes through the
Risk Manager: price-increase strategies receive RM = 0.0 -> risk penalty 1.0,
which the optimizer's `(BA+FA)/2 - (1-RM)` formula turns into a decisive
negative term.

This module does NOT modify the Risk Manager, its weights, thresholds, penalty
formula or categories. It:

  1. TRACE — re-runs the deterministic S01..S12 x seeds scenarios and, from the
     stored pipeline artefacts (AgentEvaluation + DigitalTwinSimulation rows +
     DecisionResult.debate), records the complete risk-score path for every
     strategy: DT risk -> RM score -> risk penalty -> optimizer final score ->
     selection. It verifies `final_score == (BA+FA)/2 - (1-RM)` per row.
  2. CALIBRATION — compares each strategy's DT-simulated risk against its RM
     score, per price / marketing lever family. Flags RISK_SCORE_MISMATCH where
     DT risk is LOW but the RM score is zero.
  3. RM DECISIVE — for every scenario/seed, recomputes the ranking with the
     risk-penalty term removed and classifies the pair RM_DECISIVE /
     RM_NON_DECISIVE (would the selection change?), with the objective outcome.
  4/5. D0 vs D1 — runs the real pipeline twice per scenario/seed:
       D0 = Full DecisionGPT (production).
       D1 = Full DecisionGPT with `risk_penalty_in_ranking=False` — the Risk
            Manager STILL runs and STILL feeds confidence; only its ranking
            weight is zero. D1 is a *sensitivity variant*, never "the
            architecture".
  6. STATS — paired Wilcoxon (D1 - D0) via the existing research protocol.

Nothing is fabricated; every number is read from one deterministic
(scenario, seed) re-execution.
"""
from __future__ import annotations

from statistics import mean

from sqlalchemy.orm import Session

from app.agents.strategy_optimizer import compute_strategy_score
from app.core.errors import AppError
from app.models.agent import AgentEvaluation
from app.models.digital_twin import DigitalTwinSimulation
from app.models.strategy import Strategy
from app.services import decision_architecture_service as da
from app.services import decision_service
from app.services import multi_agent_diagnostic_service as mad
from app.services import multi_scenario_service as ms
from app.services.decision_service import PipelineOptions

_TOL = 1e-4
_FORMULA_TOL = 1e-3
# A DT risk score below this is the Digital Twin's own "LOW" extrapolation band
# (digital_twin_service._risk_from_extrapolation: risk_score < 0.15 -> LOW).
LOW_RISK_BAND = 0.15

# The named lever families the calibration step reports on (task section 2).
CALIBRATION_STRATEGIES = [
    "Price +5%", "Price +10%", "Price -3%", "Price -5%",
    "Marketing +10%", "Marketing +20%", "Marketing -10%",
]


def _kpi_pair(o: dict, kpi: str):
    if kpi == "profit" and o.get("expected_profit") is not None and o.get("baseline_profit") is not None:
        return o["baseline_profit"], o["expected_profit"]
    if kpi == "orders":
        return o.get("baseline_units_sold", 0.0), o.get("expected_units_sold", 0.0)
    return o.get("baseline_revenue", 0.0), o.get("expected_revenue", 0.0)


def _attain(base: float, exp: float, target_pct: float) -> float:
    if abs(base) <= 1e-9:
        return 0.0
    pct = (exp - base) / base * 100.0
    return round(min(1.0, max(0.0, pct / target_pct)), 4)


def _kpi_ga_from_outcome(outcome: dict, target_pct: float, kpi: str) -> float:
    b, e = _kpi_pair(outcome, kpi)
    return _attain(b, e, target_pct)


def _risk_adjusted(outcome: dict) -> float:
    benefit = outcome["expected_revenue"] - outcome["baseline_revenue"]
    return round(benefit * (1.0 - outcome["risk_score"]), 2)


def _persisted_agent_round1(db: Session, business_id: str) -> dict:
    """{strategy_name: {business_analyst, financial_advisor, risk_manager}} from
    the round-1 AgentEvaluation rows the pipeline just wrote for this business."""
    names = {s.id: s.strategy_name for s in
             db.query(Strategy).filter(Strategy.business_id == business_id).all()}
    out: dict[str, dict] = {}
    for ev in (db.query(AgentEvaluation)
               .filter(AgentEvaluation.strategy_id.in_(list(names))).all()):
        j = ev.evaluation_json or {}
        if j.get("round") != 1:
            continue
        name = names.get(ev.strategy_id)
        if name is None:
            continue
        out.setdefault(name, {})[ev.agent_name] = (
            float(ev.score) if ev.score is not None else None
        )
    return out


def _persisted_sims(db: Session, business_id: str) -> dict:
    """{strategy_name: output_state_json (+ risk_score)} from DigitalTwinSimulation."""
    names = {s.id: s.strategy_name for s in
             db.query(Strategy).filter(Strategy.business_id == business_id).all()}
    out: dict[str, dict] = {}
    for sim in (db.query(DigitalTwinSimulation)
                .filter(DigitalTwinSimulation.business_id == business_id).all()):
        name = names.get(sim.strategy_id)
        if name is None:
            continue
        o = dict(sim.output_state_json or {})
        if sim.risk_score is not None:
            o["risk_score"] = float(sim.risk_score)
        out[name] = o
    return out


def _trace_one(db: Session, sc, seed: int) -> dict:
    """One (scenario, seed): run D0, harvest the full risk-score path, run the
    RM-decisive recomputation, then run D1 (risk penalty un-weighted)."""
    kpi = da.kpi_for_metric(sc.goal_primary_kpi)
    kpi_is_proxy = sc.goal_primary_kpi not in ("revenue", "profit", "orders")
    target = sc.goal_target_percent

    business_id, goal_id = da._seed_synthetic_business(db, seed, sc)
    row: dict = {
        "scenario_id": sc.scenario_id, "seed": seed,
        "goal_objective": sc.goal_objective, "goal_primary_kpi": sc.goal_primary_kpi,
        "kpi_measured": kpi, "kpi_is_proxy": kpi_is_proxy, "goal_target_percent": target,
    }
    try:
        # --- D0: production Full DecisionGPT --------------------------------
        res0 = decision_service.analyze_goal(db, business_id, goal_id)
        agents = _persisted_agent_round1(db, business_id)
        sims = _persisted_sims(db, business_id)
        finals = {c["strategy_name"]: c for c in res0.debate.get("all_candidates", [])}

        # DT sweep best (architecture B's rule — the fixed CANDIDATE_GRID),
        # kept for continuity with the multi-agent diagnostic's numbers.
        grid = mad._dt_candidates(db, business_id, kpi, target)
        dt_sweep_best = max(grid, key=lambda c: c["expected_revenue"])["strategy"] if grid else None
        dt_sweep_best_attn = (
            max(grid, key=lambda c: c["expected_revenue"])["kpi_attainment"] if grid else 0.0
        )

        strategy_rows: list[dict] = []
        max_formula_dev = 0.0
        for name, fc in finals.items():
            sim = sims.get(name, {})
            ar = agents.get(name, {})
            ba = ar.get("business_analyst")
            fa = ar.get("financial_advisor")
            rm = ar.get("risk_manager")
            dt_risk = sim.get("risk_score")
            b, e = _kpi_pair(sim, kpi)
            dt_goal_score = _attain(b, e, target)
            pre_risk = round(((ba or 0.0) + (fa or 0.0)) / 2, 4)
            risk_penalty = round(1.0 - (rm if rm is not None else 0.0), 4)
            final_calc = (
                compute_strategy_score(ba, fa, rm) if None not in (ba, fa, rm) else None
            )
            final_stored = fc.get("final_score")
            dev = (
                abs(final_calc - final_stored)
                if final_calc is not None and final_stored is not None else 0.0
            )
            max_formula_dev = max(max_formula_dev, dev)
            strategy_rows.append({
                "strategy_id": fc.get("strategy_id"),
                "strategy_name": name,
                "digital_twin_goal_score": dt_goal_score,
                "digital_twin_risk": round(dt_risk, 4) if dt_risk is not None else None,
                "risk_level": sim.get("risk_level"),
                "business_analyst_score": ba,
                "financial_advisor_score": fa,
                "risk_manager_score": rm,
                "risk_penalty": risk_penalty,
                "pre_risk_score": pre_risk,
                "final_score": final_stored,
                "final_score_recomputed": final_calc,
                "formula_holds": dev <= _FORMULA_TOL,
                "is_dt_best": name == dt_sweep_best,
                "is_final_selected": name == res0.selected_strategy_name,
                # penalty-free rank key (task section 3): (BA+FA)/2 alone
                "penalty_free_score": pre_risk,
            })

        # --- RM-decisive recomputation (task section 3) -------------------
        ranked_d0 = sorted(
            strategy_rows, key=lambda r: (r["final_score"] if r["final_score"] is not None else -1e9),
            reverse=True,
        )
        ranked_pf = sorted(
            strategy_rows, key=lambda r: r["penalty_free_score"], reverse=True,
        )
        d0_pick = ranked_d0[0]["strategy_name"] if ranked_d0 else None
        pf_pick = ranked_pf[0]["strategy_name"] if ranked_pf else None
        rm_decisive = bool(d0_pick and pf_pick and d0_pick != pf_pick)
        rm_decisive_outcome = None
        if rm_decisive:
            ga_d0 = next(r["digital_twin_goal_score"] for r in strategy_rows if r["strategy_name"] == d0_pick)
            ga_pf = next(r["digital_twin_goal_score"] for r in strategy_rows if r["strategy_name"] == pf_pick)
            if ga_pf > ga_d0 + _TOL:
                rm_decisive_outcome = "improved"
            elif ga_pf < ga_d0 - _TOL:
                rm_decisive_outcome = "degraded"
            else:
                rm_decisive_outcome = "neutral"

        # RM top pick (highest RM safety score among D0's candidates)
        rm_scored = [r for r in strategy_rows if r["risk_manager_score"] is not None]
        rm_top_pick = (
            max(rm_scored, key=lambda r: r["risk_manager_score"])["strategy_name"]
            if rm_scored else None
        )

        # --- risk-score mismatch flags (task section 2) ------------------
        mismatch = [
            {"strategy_name": r["strategy_name"], "digital_twin_risk": r["digital_twin_risk"],
             "risk_manager_score": r["risk_manager_score"]}
            for r in strategy_rows
            if r["digital_twin_risk"] is not None and r["risk_manager_score"] is not None
            and r["digital_twin_risk"] < LOW_RISK_BAND and r["risk_manager_score"] <= 1e-9
        ]

        d0_outcome = res0.expected_outcome
        d0_ga = _kpi_ga_from_outcome(d0_outcome, target, kpi)

        # --- D1: same pipeline, risk penalty un-weighted ----------------
        res1 = decision_service.analyze_goal(
            db, business_id, goal_id, PipelineOptions(risk_penalty_in_ranking=False)
        )
        d1_outcome = res1.expected_outcome
        d1_ga = _kpi_ga_from_outcome(d1_outcome, target, kpi)

        row.update({
            "d0_selected_strategy": res0.selected_strategy_name,
            "d1_selected_strategy": res1.selected_strategy_name,
            "d0_goal_achievement": d0_ga,
            "d1_goal_achievement": d1_ga,
            "d0_risk_adjusted_score": _risk_adjusted(d0_outcome),
            "d1_risk_adjusted_score": _risk_adjusted(d1_outcome),
            "d0_confidence": res0.confidence,
            "d1_confidence": res1.confidence,
            "dt_sweep_best_strategy": dt_sweep_best,
            "dt_sweep_best_attainment": dt_sweep_best_attn,
            "d0_is_dt_best": res0.selected_strategy_name == dt_sweep_best,
            "d1_is_dt_best": res1.selected_strategy_name == dt_sweep_best,
            "rm_top_pick": rm_top_pick,
            "rm_disagrees_with_dt_best": bool(rm_top_pick and dt_sweep_best and rm_top_pick != dt_sweep_best),
            "rm_decisive": rm_decisive,
            "rm_decisive_outcome": rm_decisive_outcome,
            "penalty_free_pick": pf_pick,
            "d1_matches_penalty_free_pick": res1.selected_strategy_name == pf_pick,
            "formula_max_deviation": round(max_formula_dev, 6),
            "formula_holds_all_rows": max_formula_dev <= _FORMULA_TOL,
            "risk_score_mismatch_count": len(mismatch),
            "risk_score_mismatch_rows": mismatch,
            "strategy_rows": strategy_rows,
        })
    except AppError as exc:
        row.update({
            "error": exc.message,
            "d0_selected_strategy": None, "d1_selected_strategy": None,
            "d0_goal_achievement": 0.0, "d1_goal_achievement": 0.0,
            "d0_risk_adjusted_score": 0.0, "d1_risk_adjusted_score": 0.0,
            "d0_confidence": None, "d1_confidence": None,
            "rm_decisive": False, "rm_decisive_outcome": None,
            "d0_is_dt_best": False, "d1_is_dt_best": False,
            "rm_disagrees_with_dt_best": False,
            "formula_holds_all_rows": True, "formula_max_deviation": 0.0,
            "risk_score_mismatch_count": 0, "risk_score_mismatch_rows": [],
            "strategy_rows": [],
        })
    finally:
        da._cleanup_synthetic_business(db, business_id)
    return row


def run_risk_manager_diagnostic(db: Session, seeds: list[int] | None = None) -> dict:
    seeds = seeds or ms.SEEDS
    traces = [_trace_one(db, sc, seed) for sc in ms.SCENARIOS for seed in seeds]
    return {"label": "RISK_MANAGER_DIAGNOSTIC", **_aggregate(traces, seeds)}


# --- aggregation ---------------------------------------------------------

_summ = ms._summ  # reuse the validated research summariser (mean/median/std/95% CI)


def _aggregate(traces: list[dict], seeds: list[int]) -> dict:
    n = len(traces)
    ok = [t for t in traces if not t.get("error")]

    d0_ga = [t["d0_goal_achievement"] for t in ok]
    d1_ga = [t["d1_goal_achievement"] for t in ok]

    # --- baseline (task section 14) -----------------------------------
    # Digital Twin mean = architecture B rule over the fixed CANDIDATE_GRID,
    # measured exactly as the multi-agent diagnostic does.
    dt_mean = round(mean([t["dt_sweep_best_attainment"] for t in ok]), 4) if ok else None
    d0_mean = round(mean(d0_ga), 4) if d0_ga else None
    d1_mean = round(mean(d1_ga), 4) if d1_ga else None

    rm_disagree = [t for t in ok if t.get("rm_disagrees_with_dt_best")]
    rm_decisive = [t for t in ok if t.get("rm_decisive")]
    rm_dec_impr = [t for t in rm_decisive if t.get("rm_decisive_outcome") == "improved"]
    rm_dec_degr = [t for t in rm_decisive if t.get("rm_decisive_outcome") == "degraded"]
    rm_dec_neut = [t for t in rm_decisive if t.get("rm_decisive_outcome") == "neutral"]

    # --- risk-score mismatch ----------------------------------------
    all_strategy_rows = [r for t in ok for r in t["strategy_rows"]]
    inspected = [r for r in all_strategy_rows
                 if r["digital_twin_risk"] is not None and r["risk_manager_score"] is not None]
    mismatch_rows = [r for r in inspected
                     if r["digital_twin_risk"] < LOW_RISK_BAND and r["risk_manager_score"] <= 1e-9]

    def _family(name: str) -> dict:
        rows = [r for r in inspected if r["strategy_name"] == name]
        if not rows:
            return {"strategy": name, "observations": 0}
        return {
            "strategy": name, "observations": len(rows),
            "mean_digital_twin_risk": round(mean([r["digital_twin_risk"] for r in rows]), 4),
            "mean_risk_manager_score": round(mean([r["risk_manager_score"] for r in rows]), 4),
            "rm_score_zero_rate": round(
                sum(1 for r in rows if r["risk_manager_score"] <= 1e-9) / len(rows), 4),
            "dt_risk_low_rate": round(
                sum(1 for r in rows if r["digital_twin_risk"] < LOW_RISK_BAND) / len(rows), 4),
        }

    calibration_table = [_family(s) for s in CALIBRATION_STRATEGIES]
    distinguishes = _rm_distinguishes(inspected)

    # --- D0 vs D1 comparison table (task section 10) ----------------
    d0_vs_d1 = {
        "goal_achievement": {"D0": _summ(d0_ga), "D1": _summ(d1_ga)},
        "risk_adjusted_score": {
            "D0": _summ([t["d0_risk_adjusted_score"] for t in ok]),
            "D1": _summ([t["d1_risk_adjusted_score"] for t in ok]),
        },
        "confidence": {
            "D0": _summ([t["d0_confidence"] for t in ok]),
            "D1": _summ([t["d1_confidence"] for t in ok]),
        },
        "dt_best_agreement_rate": {
            "D0": round(sum(1 for t in ok if t["d0_is_dt_best"]) / len(ok), 4) if ok else None,
            "D1": round(sum(1 for t in ok if t["d1_is_dt_best"]) / len(ok), 4) if ok else None,
        },
        "override_rate_vs_dt_best": {
            "D0": round(sum(1 for t in ok if not t["d0_is_dt_best"]) / len(ok), 4) if ok else None,
            "D1": round(sum(1 for t in ok if not t["d1_is_dt_best"]) / len(ok), 4) if ok else None,
        },
    }

    # --- paired D1 - D0 (task sections 5 & 6) -----------------------
    paired = ms._paired(d1_ga, d0_ga, "goal_achievement", "D0 (Full DecisionGPT)")
    paired["comparison"] = "D1 (Risk-Penalty Sensitivity) vs D0 (Full DecisionGPT)"
    paired["difference_is"] = "D1 - D0"
    paired["d1_wins"] = paired.pop("full_wins")
    paired["d0_wins"] = paired.pop("full_losses")
    _pd = paired.get("mean_difference")
    if paired.get("p_value") is None:
        paired["interpretation"] = (
            "Significance not assessed (see reason). Descriptive: mean D1-D0 goal-achievement "
            f"difference {_pd:+.4f} across {paired['n_pairs']} paired scenario/seed evaluations."
        )
    else:
        _sig = paired["p_value"] < 0.05
        _dir = "higher" if _pd > 0 else ("lower" if _pd < 0 else "equal")
        paired["interpretation"] = (
            f"D1 (risk penalty un-weighted) goal achievement is {_dir} than D0 by {_pd:+.4f} "
            f"(Wilcoxon p={paired['p_value']:.4f}, "
            + ("statistically significant" if _sig else "not significant")
            + f", r={paired.get('effect_size_r')})."
        )

    selection_changed = [t for t in ok if t["d0_selected_strategy"] != t["d1_selected_strategy"]]

    return {
        "seeds": seeds, "scenario_count": len(ms.SCENARIOS), "seed_count": len(seeds),
        "total_scenario_seed_pairs": n, "evaluated_pairs": len(ok),
        "aggregation_method": "sample mean / median / std; 95% CI = Student-t on the mean",
        "statistical_method": "paired Wilcoxon signed-rank (D1 - D0) on scenario x seed",
        "baseline": {
            "full_decisiongpt_mean_goal_achievement": d0_mean,
            "digital_twin_mean_goal_achievement": dt_mean,
            "d1_risk_penalty_sensitivity_mean_goal_achievement": d1_mean,
        },
        "formula_verification": {
            "checked": "final_score == (BA+FA)/2 - (1-RM) for every strategy row",
            "max_deviation_observed": round(max(
                [t.get("formula_max_deviation", 0.0) for t in ok] or [0.0]), 6),
            "holds_for_all_rows": all(t.get("formula_holds_all_rows", True) for t in ok),
            "rows_checked": len(all_strategy_rows),
        },
        "risk_manager_disagreement": {
            "disagreements_vs_dt_best": len(rm_disagree),
            "disagreement_rate": round(len(rm_disagree) / len(ok), 4) if ok else None,
        },
        "rm_decisive": {
            "count": len(rm_decisive),
            "percentage": round(100 * len(rm_decisive) / len(ok), 1) if ok else None,
            "improved": len(rm_dec_impr),
            "degraded": len(rm_dec_degr),
            "neutral": len(rm_dec_neut),
            "definition": "removing ONLY the risk-penalty term changes the selected strategy",
            "pairs": [
                {"scenario_id": t["scenario_id"], "seed": t["seed"],
                 "d0_pick": t["d0_selected_strategy"], "penalty_free_pick": t["penalty_free_pick"],
                 "outcome": t["rm_decisive_outcome"]}
                for t in rm_decisive
            ],
        },
        "risk_score_mismatch": {
            "count": len(mismatch_rows),
            "strategy_rows_inspected": len(inspected),
            "percentage": round(100 * len(mismatch_rows) / len(inspected), 1) if inspected else None,
            "definition": f"DT risk < {LOW_RISK_BAND} (LOW band) but RM score == 0.0",
            "rm_distinguishes_low_vs_high_risk_price_strategies": distinguishes,
            "calibration_table": calibration_table,
        },
        "d0_vs_d1": d0_vs_d1,
        "paired_d1_minus_d0": paired,
        "selection_changed_pairs": len(selection_changed),
        "d1_matches_penalty_free_recompute_rate": round(
            sum(1 for t in ok if t.get("d1_matches_penalty_free_pick")) / len(ok), 4) if ok else None,
        "interpretation": _interpret(d0_mean, d1_mean, dt_mean, paired, len(rm_decisive), len(ok)),
        "traces": traces,
    }


def _rm_distinguishes(inspected: list[dict]) -> dict:
    """Does the RM score vary with DT risk among price strategies? If every
    price strategy gets RM=0 regardless of its DT risk, it does not."""
    price = [r for r in inspected if r["strategy_name"].startswith("Price ")]
    if len(price) < 2:
        return {"assessable": False, "note": "fewer than 2 price-strategy observations"}
    rm_scores = [r["risk_manager_score"] for r in price]
    dt_risks = [r["digital_twin_risk"] for r in price]
    rm_spread = round(max(rm_scores) - min(rm_scores), 4)
    dt_spread = round(max(dt_risks) - min(dt_risks), 4)
    all_zero = all(s <= 1e-9 for s in rm_scores)
    return {
        "assessable": True,
        "price_strategy_observations": len(price),
        "rm_score_spread": rm_spread,
        "dt_risk_spread": dt_spread,
        "rm_score_all_zero_for_price": all_zero,
        "verdict": (
            "NO — every price strategy receives RM score 0.0 regardless of its DT-simulated risk"
            if all_zero else
            ("PARTIAL — RM score varies but weakly" if rm_spread < 0.2 else
             "YES — RM score tracks DT risk across price strategies")
        ),
    }


def _interpret(d0: float | None, d1: float | None, dt: float | None,
               paired: dict, rm_decisive: int, n_ok: int) -> dict:
    if d0 is None or d1 is None or dt is None:
        return {"outcome": "INCONCLUSIVE", "text": "No evaluable pairs."}
    delta = round(d1 - d0, 4)
    gap_closed = round((d1 - d0) / (dt - d0), 4) if abs(dt - d0) > 1e-9 else None
    p = paired.get("p_value")
    sig = p is not None and p < 0.05

    if delta > 0.02 and d1 >= dt - 0.1:
        outcome = "A"
        answer_improve = "YES"
        answer_explains = "YES"
        text = (
            f"D1 (risk penalty un-weighted) reaches mean goal achievement {d1:.3f} vs D0 {d0:.3f} "
            f"(Δ {delta:+.3f}) and approaches the Digital Twin's {dt:.3f}. The risk-penalty term is "
            f"the dominant bottleneck."
        )
    elif delta > 0.02:
        outcome = "B"
        answer_improve = "PARTIALLY"
        answer_explains = "PARTIALLY"
        text = (
            f"D1 improves over D0 ({d1:.3f} vs {d0:.3f}, Δ {delta:+.3f}"
            + (f", {gap_closed:.0%} of the D0→DigitalTwin gap" if gap_closed is not None else "")
            + f") but stays far below the Digital Twin's {dt:.3f}. The risk penalty contributes to "
            f"the degradation without fully explaining it — inspect BA/FA scoring / candidate "
            f"ranking next."
        )
    elif abs(delta) <= 0.02:
        outcome = "C"
        answer_improve = "NO"
        answer_explains = "NO"
        text = (
            f"Removing only the risk-penalty term does not move the objective "
            f"(D1 {d1:.3f} vs D0 {d0:.3f}, Δ {delta:+.3f}). The risk penalty is not the primary "
            f"cause of the Full-vs-Digital-Twin gap"
            + (f"; {rm_decisive}/{n_ok} pairs are RM-decisive on *selection* but the alternative "
               f"the agents then pick is no better on the objective." if rm_decisive else ".")
            + " Inspect BA/FA scoring or candidate ranking next."
        )
    else:
        outcome = "D"
        answer_improve = "NO"
        answer_explains = "NO"
        text = (
            f"D1 is worse than D0 ({d1:.3f} vs {d0:.3f}, Δ {delta:+.3f}). Un-weighting the risk "
            f"penalty degrades the objective — reported honestly."
        )
    return {
        "outcome": outcome,
        "removing_rm_penalty_improves_full": answer_improve,
        "rm_penalty_explains_the_gap": answer_explains,
        "paired_significant": sig,
        "delta_d1_minus_d0": delta,
        "fraction_of_gap_closed": gap_closed,
        "text": text,
    }
