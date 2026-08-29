"""Research Console — Multi-Agent degradation diagnostic (analysis only).

The multi-scenario experiment measured that **Full DecisionGPT (D) achieves
lower goal achievement than Prediction + Digital Twin (B)** across the 12x5
scenario suite (mean 0.084 vs 0.486; Wilcoxon p < 0.0001; D loses 45/60).
This module does NOT change the architecture, the agents, the Digital Twin or
the experiment methodology. It **re-runs the deterministic architecture
scenarios** (same seeds, same scenario specs, LLM template mode) and, before
each ephemeral business is cleaned up, harvests the full decision trace the
pipeline itself produced:

    Digital-Twin candidate ranking  (decision_architecture_service._simulate_all_candidates,
                                     the fixed CANDIDATE_GRID that architecture B/C sweep)
        -> per-candidate Business Analyst / Financial Advisor / Risk Manager
           round-1 + round-2 scores  (persisted AgentEvaluation rows)
        -> strategy_optimizer final_score per candidate  (DecisionResult.debate)
        -> the strategy the Full pipeline selected  + its goal achievement

From those traces it builds the disagreement dataset, classifies the
mechanism for every Full-vs-DigitalTwin disagreement, and quantifies each.
Nothing is fabricated; every row corresponds to one deterministic
(scenario, seed) re-execution and matches the stored
`multi_scenario_architecture` observation for architecture D.
"""
from __future__ import annotations

from statistics import mean

from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.agent import AgentEvaluation
from app.models.strategy import Strategy
from app.services import decision_architecture_service as da
from app.services import decision_service
from app.services import multi_scenario_service as ms

# failure-mode categories (task section 3)
AGENT_OVERRULE = "AGENT_OVERRULE"
RISK_OVERRULE = "RISK_OVERRULE"
CANDIDATE_SET_MISMATCH = "CANDIDATE_SET_MISMATCH"   # DT-best strategy absent from D's generated set
OPTIMIZER_RERANKING = "OPTIMIZER_RERANKING"
CAUSAL_PENALTY = "CAUSAL_PENALTY"
CONFIDENCE_PENALTY = "CONFIDENCE_PENALTY"
UNSUPPORTED_KPI = "UNSUPPORTED_KPI"
TIE_BREAK = "TIE_BREAK"
NO_VALID_STRATEGY = "NO_VALID_STRATEGY"
MATCH = "MATCH"                                       # D picked the same strategy as the DT sweep
OTHER = "OTHER"

_TOL = 1e-4


def _kpi_pair(o, kpi: str):
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


def _dt_candidates(db: Session, business_id: str, kpi: str, target_pct: float) -> list[dict]:
    """The fixed CANDIDATE_GRID sweep — exactly what architectures B and C see."""
    rows = []
    for name, sim in da._simulate_all_candidates(db, business_id):
        o = sim.output
        od = {
            "expected_revenue": o.expected_revenue, "baseline_revenue": o.baseline_revenue,
            "expected_profit": o.expected_profit, "baseline_profit": o.baseline_profit,
            "expected_units_sold": o.expected_units_sold, "baseline_units_sold": o.baseline_units_sold,
        }
        b, e = _kpi_pair(od, kpi)
        rows.append({
            "strategy": name, "expected_revenue": round(o.expected_revenue, 2),
            "risk_score": round(o.risk_score, 4),
            "kpi_attainment": _attain(b, e, target_pct),
        })
    return rows


def _persisted_agent_scores(db: Session, business_id: str) -> dict:
    """{strategy_name: {"round1": {ba,fa,rm}, "round2": {...}, "conflicts": n}}
    from the AgentEvaluation rows the pipeline just wrote."""
    out: dict[str, dict] = {}
    strategies = {s.id: s.strategy_name for s in db.query(Strategy).filter(Strategy.business_id == business_id).all()}
    for ev in db.query(AgentEvaluation).filter(AgentEvaluation.strategy_id.in_(list(strategies))).all():
        name = strategies.get(ev.strategy_id)
        if name is None:
            continue
        j = ev.evaluation_json or {}
        rnd = j.get("round")
        rec = out.setdefault(name, {"round1": {}, "round2": {}, "conflicts": 0})
        if rnd == 1:
            rec["round1"][ev.agent_name] = float(ev.score) if ev.score is not None else None
        elif rnd == 2:
            if ev.score is not None:
                rec["round2"][ev.agent_name] = float(ev.score)
            rec["conflicts"] += len(j.get("challenges", []) or [])
    return out


def _classify(trace: dict) -> tuple[str, str]:
    """Return (failure_mode, evidence sentence). Only assigns a mechanism the
    trace actually supports."""
    if not trace["disagreement"]:
        return MATCH, "Full DecisionGPT selected the same strategy the Digital-Twin sweep ranked first."

    if trace["kpi_is_proxy"]:
        return UNSUPPORTED_KPI, (
            f"Scenario KPI '{trace['goal_primary_kpi']}' is not directly simulated; goal "
            "achievement uses a revenue proxy, so a Full-vs-DigitalTwin ranking difference here "
            "is not attributable to the agents."
        )

    dt_name = trace["dt_best_strategy"]
    d_names = set(trace["d_candidate_names"])
    if dt_name not in d_names:
        return CANDIDATE_SET_MISMATCH, (
            f"The Digital-Twin's best strategy ('{dt_name}') is NOT in Full DecisionGPT's "
            f"generated candidate set {sorted(d_names)}. The agents never scored it — the "
            "strategy generator (strategy_generation_service) did not produce it for this goal."
        )

    dsc = {c["strategy"]: c for c in trace["d_candidates"]}
    dt_in_d = dsc.get(dt_name)
    fin = dsc.get(trace["final_strategy"])
    if dt_in_d is None or fin is None:
        return OTHER, "Could not line up the DT-best and final strategies in the trace."

    if abs((dt_in_d["final_score"] or 0) - (fin["final_score"] or 0)) <= _TOL:
        return TIE_BREAK, (
            f"'{dt_name}' and the selected '{trace['final_strategy']}' have equal optimizer "
            f"final_score ({fin['final_score']}); selection fell to candidate-generation order."
        )

    # the DT-best is in the set but scored below the winner — which term flipped it?
    dt_growth = ((dt_in_d["ba1"] or 0) + (dt_in_d["fa1"] or 0)) / 2
    fin_growth = ((fin["ba1"] or 0) + (fin["fa1"] or 0)) / 2
    dt_riskpen = 1.0 - (dt_in_d["rm1"] or 0)
    fin_riskpen = 1.0 - (fin["rm1"] or 0)
    round2_moved = dt_in_d.get("round2_moved") or fin.get("round2_moved")

    if round2_moved:
        return OPTIMIZER_RERANKING, (
            "Round-2 peer-review self-adjustments changed the ranking: "
            f"'{dt_name}' fell below '{trace['final_strategy']}' only after round-2 score moves."
        )
    if fin_growth > dt_growth + _TOL and fin_riskpen <= dt_riskpen + _TOL:
        return AGENT_OVERRULE, (
            f"Business Analyst + Financial Advisor scored '{trace['final_strategy']}' higher on "
            f"growth ((BA+FA)/2 {fin_growth:.3f} vs {dt_growth:.3f}) than the Digital-Twin's "
            f"revenue-best '{dt_name}', with no larger risk penalty."
        )
    if dt_riskpen > fin_riskpen + _TOL and dt_growth >= fin_growth - _TOL:
        return RISK_OVERRULE, (
            f"The Risk Manager scored '{dt_name}' less safe (risk penalty {dt_riskpen:.3f} vs "
            f"{fin_riskpen:.3f}); that penalty alone dropped its final_score below "
            f"'{trace['final_strategy']}'."
        )
    return OTHER, (
        f"'{dt_name}' final_score {dt_in_d['final_score']} < '{trace['final_strategy']}' "
        f"{fin['final_score']}, but no single term (growth / risk / round-2) explains the flip."
    )


def run_diagnostic(db: Session, seeds: list[int] | None = None) -> dict:
    seeds = seeds or ms.SEEDS
    traces: list[dict] = []

    for sc in ms.SCENARIOS:
        kpi = da.kpi_for_metric(sc.goal_primary_kpi)
        kpi_is_proxy = sc.goal_primary_kpi not in ("revenue", "profit", "orders")
        for seed in seeds:
            business_id, goal_id = da._seed_synthetic_business(db, seed, sc)
            row = {
                "scenario_id": sc.scenario_id, "seed": seed,
                "goal_objective": sc.goal_objective, "goal_primary_kpi": sc.goal_primary_kpi,
                "kpi_measured": kpi, "kpi_is_proxy": kpi_is_proxy,
                "goal_target_percent": sc.goal_target_percent,
            }
            try:
                dt_cands = _dt_candidates(db, business_id, kpi, sc.goal_target_percent)
                dt_best = max(dt_cands, key=lambda c: c["expected_revenue"])   # architecture B's rule
                row["dt_best_strategy"] = dt_best["strategy"]
                row["dt_best_revenue"] = dt_best["expected_revenue"]
                row["dt_best_kpi_attainment"] = dt_best["kpi_attainment"]
                row["dt_candidate_ranking"] = [c["strategy"] for c in
                                               sorted(dt_cands, key=lambda c: -c["expected_revenue"])]

                res = decision_service.analyze_goal(db, business_id, goal_id)
                agent_scores = _persisted_agent_scores(db, business_id)
                by_final = {c["strategy_name"]: c for c in res.debate.get("all_candidates", [])}

                d_candidates = []
                for name, fs in by_final.items():
                    a = agent_scores.get(name, {"round1": {}, "round2": {}, "conflicts": 0})
                    r1, r2 = a["round1"], a["round2"]
                    d_candidates.append({
                        "strategy": name, "final_score": fs.get("final_score"),
                        "confidence": fs.get("confidence"), "conflicts": len(fs.get("conflicts") or []),
                        "ba1": r1.get("business_analyst"), "fa1": r1.get("financial_advisor"),
                        "rm1": r1.get("risk_manager"),
                        "round2_moved": any(k in r2 and r2[k] is not None and r1.get(k) is not None
                                            and abs(r2[k] - r1[k]) > 1e-9 for k in r1),
                    })
                d_candidates.sort(key=lambda c: (c["final_score"] or -1e9), reverse=True)

                b, e = _kpi_pair(res.expected_outcome, kpi)
                final_ga = _attain(b, e, sc.goal_target_percent)
                b2, e2 = _kpi_pair(res.expected_outcome, "revenue")

                ev = (res.causal_context or {}).get("strongest_pathway_evidence") or \
                     (res.causal_context or {}).get("evidence_level") or "unknown"

                rm_pick = max(d_candidates, key=lambda c: (c["rm1"] or -1)) if d_candidates else None

                row.update({
                    "final_strategy": res.selected_strategy_name,
                    "final_score": res.selected_strategy_score,
                    "final_goal_achievement": final_ga,
                    "final_revenue_attainment": _attain(b2, e2, sc.goal_target_percent),
                    "confidence": res.confidence,
                    "causal_evidence_level": ev,
                    "d_candidates": d_candidates,
                    "d_candidate_names": [c["strategy"] for c in d_candidates],
                    "risk_manager_top_pick": rm_pick["strategy"] if rm_pick else None,
                    "disagreement": res.selected_strategy_name != dt_best["strategy"],
                    "improvement": round(final_ga - dt_best["kpi_attainment"], 4),
                })
            except AppError as exc:
                row.update({
                    "final_strategy": None, "final_goal_achievement": 0.0,
                    "disagreement": True, "improvement": round(0.0 - row.get("dt_best_kpi_attainment", 0.0), 4),
                    "error": exc.message, "d_candidates": [], "d_candidate_names": [],
                })
            finally:
                da._cleanup_synthetic_business(db, business_id)

            mode, evidence = _classify(row)
            row["failure_mode"] = mode
            row["mechanism_evidence"] = evidence
            traces.append(row)

    return {"label": "MULTI_AGENT_DIAGNOSTIC", **_aggregate(traces, seeds)}


def _aggregate(traces: list[dict], seeds: list[int]) -> dict:
    n = len(traces)
    disagreements = [t for t in traces if t["disagreement"]]
    improved = [t for t in disagreements if t["improvement"] > _TOL]
    degraded = [t for t in disagreements if t["improvement"] < -_TOL]
    neutral = [t for t in disagreements if abs(t["improvement"]) <= _TOL]

    modes = [AGENT_OVERRULE, RISK_OVERRULE, CANDIDATE_SET_MISMATCH, OPTIMIZER_RERANKING,
             CAUSAL_PENALTY, CONFIDENCE_PENALTY, UNSUPPORTED_KPI, TIE_BREAK, NO_VALID_STRATEGY, OTHER]
    failure_modes = {}
    for m in modes:
        rows = [t for t in traces if t["failure_mode"] == m]
        if not rows and m in (CAUSAL_PENALTY, CONFIDENCE_PENALTY):
            failure_modes[m] = {
                "count": 0, "percent": 0.0, "mean_dt_revenue": None,
                "mean_final_goal_achievement": None,
                "note": "0 by construction — the causal-evidence factor only scales `confidence`, "
                        "never `final_score`, so it cannot change strategy selection (verified in "
                        "strategy_optimizer.resolve).",
            }
            continue
        failure_modes[m] = {
            "count": len(rows),
            "percent": round(100 * len(rows) / n, 1) if n else 0.0,
            "mean_dt_revenue": round(mean([r["dt_best_revenue"] for r in rows if r.get("dt_best_revenue") is not None]), 1)
            if any(r.get("dt_best_revenue") is not None for r in rows) else None,
            "mean_final_goal_achievement": round(mean([r["final_goal_achievement"] for r in rows]), 4) if rows else None,
        }

    # central hypothesis (task section 5): agents override the DT-best without objective gain
    overrides_with_dt_in_set = [t for t in disagreements
                                if t["failure_mode"] in (AGENT_OVERRULE, RISK_OVERRULE,
                                                         OPTIMIZER_RERANKING, TIE_BREAK)]
    ov = len(overrides_with_dt_in_set)
    ov_impr = len([t for t in overrides_with_dt_in_set if t["improvement"] > _TOL])
    ov_degr = len([t for t in overrides_with_dt_in_set if t["improvement"] < -_TOL])
    ov_neut = ov - ov_impr - ov_degr

    # risk-manager effect (section 7)
    rm_disagree = [t for t in traces if t.get("risk_manager_top_pick")
                   and t.get("dt_best_strategy") and t["risk_manager_top_pick"] != t["dt_best_strategy"]]

    # optimizer reranking (section 8): DT-best -> final changed
    rerank_unchanged = [t for t in traces if not t["disagreement"]]

    # causal-evidence effect (section 6)
    by_ev: dict[str, list[dict]] = {}
    for t in traces:
        by_ev.setdefault(t.get("causal_evidence_level", "unknown"), []).append(t)
    causal_effect = {
        lvl: {
            "count": len(rows),
            "mean_final_goal_achievement": round(mean([r["final_goal_achievement"] for r in rows]), 4),
            "mean_confidence": round(mean([r["confidence"] for r in rows if r.get("confidence") is not None]), 4)
            if any(r.get("confidence") is not None for r in rows) else None,
        }
        for lvl, rows in sorted(by_ev.items())
    }
    causal_note = (
        "Insufficient variation to evaluate a causal-evidence effect on strategy selection: "
        if len(by_ev) < 2 else ""
    ) + ("the causal-evidence factor is applied to `confidence` only (strategy_optimizer.resolve), "
         "so by construction it cannot change which strategy is selected.")

    dt_mean_ga = round(mean([t["dt_best_kpi_attainment"] for t in traces
                             if t.get("dt_best_kpi_attainment") is not None]), 4)
    full_mean_ga = round(mean([t["final_goal_achievement"] for t in traces]), 4)

    return {
        "seeds": seeds,
        "scenario_count": len(ms.SCENARIOS),
        "seed_count": len(seeds),
        "total_scenario_seed_pairs": n,
        "digital_twin_to_final": {
            "unchanged": len(rerank_unchanged),
            "overridden": len(disagreements),
            "override_rate": round(len(disagreements) / n, 4) if n else 0.0,
        },
        "override_outcomes": {
            "improved": len(improved), "degraded": len(degraded), "neutral": len(neutral),
            "override_improvement_rate": round(len(improved) / len(disagreements), 4) if disagreements else 0.0,
            "override_degradation_rate": round(len(degraded) / len(disagreements), 4) if disagreements else 0.0,
            "override_neutral_rate": round(len(neutral) / len(disagreements), 4) if disagreements else 0.0,
        },
        "failure_modes": failure_modes,
        "central_hypothesis": {
            "statement": "The multi-agent layer frequently overrides the Digital Twin's "
                         "highest-scoring strategy WITHOUT sufficient objective evidence, lowering "
                         "goal achievement.",
            "agent_layer_overrides_dt_best_in_its_own_set": ov,
            "of_those_improved": ov_impr, "of_those_degraded": ov_degr, "of_those_neutral": ov_neut,
            "verdict": _hypothesis_verdict(ov, ov_degr, ov_impr, failure_modes, n),
        },
        "risk_manager_effect": {
            "disagreement_rate_vs_dt_best": round(len(rm_disagree) / n, 4) if n else 0.0,
            "disagreements": len(rm_disagree),
            "of_those_degraded": len([t for t in rm_disagree if t["improvement"] < -_TOL]),
            "of_those_improved": len([t for t in rm_disagree if t["improvement"] > _TOL]),
        },
        "optimizer_effect": {
            "dt_best_to_final_change_rate": round(len(disagreements) / n, 4) if n else 0.0,
            "mean_goal_achievement_when_unchanged": round(
                mean([t["final_goal_achievement"] for t in rerank_unchanged]), 4) if rerank_unchanged else None,
            "mean_goal_achievement_when_changed": round(
                mean([t["final_goal_achievement"] for t in disagreements]), 4) if disagreements else None,
            "note": "strategy_optimizer.resolve applies the fixed formula "
                    "(BA+FA)/2 - (1-RM); it performs no independent re-ranking beyond that "
                    "and the round-2 self-adjustments.",
        },
        "causal_evidence_effect": {"by_level": causal_effect, "note": causal_note},
        "digital_twin_mean_goal_achievement": dt_mean_ga,
        "full_decisiongpt_mean_goal_achievement": full_mean_ga,
        "failure_analysis_figure": {
            "digital_twin_best": n,
            "unchanged": len(rerank_unchanged),
            "overridden": len(disagreements),
            "overridden_improved": len(improved),
            "overridden_degraded": len(degraded),
            "overridden_neutral": len(neutral),
        },
        "traces": traces,
    }


def _hypothesis_verdict(ov: int, ov_degr: int, ov_impr: int, failure_modes: dict, n: int) -> str:
    csm = failure_modes.get(CANDIDATE_SET_MISMATCH, {}).get("count", 0)
    parts = []
    if csm > ov:
        parts.append(
            f"PARTIALLY SUPPORTED / RE-SPECIFIED. The dominant mechanism is NOT an agent overrule: "
            f"in {csm}/{n} pairs the Digital-Twin's best strategy is absent from Full DecisionGPT's "
            f"generated candidate set (strategy_generation_service), so the agents never scored it."
        )
    if ov:
        parts.append(
            f"Where the DT-best strategy IS in the candidate set, the agent layer changed the "
            f"selection {ov} time(s): {ov_degr} degraded the objective, {ov_impr} improved it. "
            + ("This supports the hypothesis for those cases." if ov_degr >= ov_impr
               else "The overrides that did occur mostly helped.")
        )
    else:
        parts.append("Where the DT-best strategy was in the candidate set, the agent layer never "
                     "changed the objective-optimal selection.")
    return " ".join(parts)
