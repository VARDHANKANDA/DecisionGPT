"""Research Console — Principled Risk Manager calibration study
(docs/RISK_MANAGER_CALIBRATION_REPORT.md, docs/RISK_CALIBRATION_ANALYSIS.md).

The Risk Manager diagnostic (`risk_manager_diagnostic` `ba56e42b`) established:
the risk-penalty term is the *proximate* mechanism of the Full-vs-Digital-Twin
gap, the Risk Manager faithfully transmits the Digital Twin's extrapolation
risk, and that risk score degenerates when a feature's history barely varies
(`_risk_from_extrapolation` normalises by `max - min`, which collapses toward
zero → any price move reads as risk 1.0).

This module runs a CONTROLLED calibration study. It changes ONLY how
extrapolation risk is *estimated* (R1) or how strongly it *contributes to
ranking* (R2 λ) — never the Digital Twin's predicted units / revenue / profit,
the candidate set, the agent growth scores, the causal evidence, or the
scenario generation. Every variant is EXPERIMENTAL; production stays R0/D0.

Variants (task section 3):
  R0        current production formula (== D0)                — reference
  D1        risk penalty un-weighted (λ = 0)                  — reference
  R1        robust historical scale for extrapolation risk
  R2-0.25   R0 risk, ranking penalty λ = 0.25
  R2-0.50   R0 risk, ranking penalty λ = 0.50
  R2-0.75   R0 risk, ranking penalty λ = 0.75
  R3        R1 risk + the λ chosen by a PRE-SPECIFIED criterion
"""
from __future__ import annotations

from statistics import mean

from sqlalchemy.orm import Session

from app.analytics import digital_twin_service as dtsvc
from app.analytics import forecast_service
from app.analytics.digital_twin_service import Action
from app.core.errors import AppError
from app.models.strategy import Strategy
from app.services import decision_service
from app.services import multi_agent_diagnostic_service as mad
from app.services import multi_scenario_service as ms
from app.services import risk_manager_diagnostic_service as rmd
from app.services.decision_service import PipelineOptions

_TOL = 1e-4

# Reference conditions (preserved from earlier experiments — NOT re-selected).
REFERENCE_VARIANTS: list[tuple[str, dict]] = [
    ("R0", {}),
    ("D1", {"risk_penalty_in_ranking": False}),
]
# Pre-specified calibration variants (task section 3). No continuous search.
R2_LAMBDAS = [0.25, 0.50, 0.75]
CALIBRATION_VARIANTS: list[tuple[str, dict]] = (
    [("R1", {"risk_model": "R1"})]
    + [(f"R2-{lam:.2f}", {"risk_penalty_lambda": lam}) for lam in R2_LAMBDAS]
)

# --- R3 pre-specified selection criterion (task sections 3 & 12) -----------
# Chosen BEFORE looking at R3 results. Among λ ∈ {0.25, 0.50, 0.75}, take the
# SMALLEST λ whose R2-λ run:
#   (a) does not reduce mean risk-adjusted score below D0 (R0), AND
#   (b) keeps mean confidence ≥ 0.60 × D0's mean confidence
#       (i.e. avoids the D1-style confidence collapse).
# If no λ qualifies, R3 falls back to the documented midpoint λ = 0.50.
R3_CONFIDENCE_FLOOR_FRAC = 0.60
R3_FALLBACK_LAMBDA = 0.50


def _opts(**over) -> PipelineOptions:
    return PipelineOptions(**over)


def _variant_options(spec: dict) -> PipelineOptions:
    return _opts(
        risk_model=spec.get("risk_model"),
        risk_penalty_in_ranking=spec.get("risk_penalty_in_ranking", True),
        risk_penalty_lambda=spec.get("risk_penalty_lambda", 1.0),
    )


def _raw_extrapolation_distance(history, actions: list[dict]) -> float:
    """Natural-unit distance the requested scenario pushes price / marketing
    beyond the observed history range (0 if inside). Model-independent."""
    (_bp, _bm, sp, sm, _bt) = dtsvc.compute_scenario_inputs(
        history, [Action(type=a["type"], value=a["value"]) for a in actions]
    )
    p_lo, p_hi = float(history["price"].min()), float(history["price"].max())
    m_lo, m_hi = float(history["marketing_spend"].min()), float(history["marketing_spend"].max())
    dp = max(0.0, sp - p_hi, p_lo - sp)
    dm = max(0.0, sm - m_hi, m_lo - sm)
    return round(max(dp, dm), 4)


def _harvest_variant(db: Session, sc, seed: int, variant: str, spec: dict) -> dict:
    """One (scenario, seed, variant). Seeds a FRESH ephemeral business (identical
    by determinism to every other variant's, keyed on scenario_id:seed), runs
    the real pipeline once with this variant's options, harvests the trace, then
    cleans up — so no variant's persisted Strategy / AgentEvaluation rows can
    contaminate another's harvest."""
    import pandas as pd

    from app.services import decision_architecture_service as da

    kpi = mad_kpi(sc)
    target = sc.goal_target_percent
    opts = _variant_options(spec)
    lam = 0.0 if not opts.risk_penalty_in_ranking else opts.risk_penalty_lambda

    business_id, goal_id = da._seed_synthetic_business(db, seed, sc)
    history = forecast_service.build_daily_series(db, business_id)
    history["date"] = pd.to_datetime(history["date"])
    try:
        return _do_harvest(db, business_id, goal_id, sc, seed, variant, opts, lam, kpi, target, history)
    finally:
        da._cleanup_synthetic_business(db, business_id)


def _do_harvest(db, business_id, goal_id, sc, seed, variant, opts, lam, kpi, target, history) -> dict:
    res = decision_service.analyze_goal(db, business_id, goal_id, opts)
    agents = rmd._persisted_agent_round1(db, business_id)
    sims = rmd._persisted_sims(db, business_id)
    finals = {c["strategy_name"]: c for c in res.debate.get("all_candidates", [])}
    actions_by_name = {
        s.strategy_name: (s.actions_json or [])
        for s in db.query(Strategy).filter(Strategy.business_id == business_id).all()
    }

    grid = mad._dt_candidates(db, business_id, kpi, target)
    dt_best = max(grid, key=lambda c: c["expected_revenue"]) if grid else None

    strategy_rows = []
    for name, fc in finals.items():
        sim = sims.get(name, {})
        ar = agents.get(name, {})
        ba, fa, rm = ar.get("business_analyst"), ar.get("financial_advisor"), ar.get("risk_manager")
        dt_risk = sim.get("risk_score")
        b, e = rmd._kpi_pair(sim, kpi)
        actions = actions_by_name.get(name, [])
        strategy_rows.append({
            "strategy_id": fc.get("strategy_id"), "strategy_name": name,
            "digital_twin_risk": round(dt_risk, 4) if dt_risk is not None else None,
            "calibrated_risk": round(dt_risk, 4) if dt_risk is not None else None,
            "raw_extrapolation_distance": _raw_extrapolation_distance(history, actions) if actions else 0.0,
            "BA_score": ba, "FA_score": fa, "RM_score": rm,
            "risk_penalty_weight": lam,
            "risk_penalty": round(lam * (1.0 - (rm if rm is not None else 0.0)), 4),
            "final_score": fc.get("final_score"),
            "is_dt_best": dt_best is not None and name == dt_best["strategy"],
            "is_selected": name == res.selected_strategy_name,
        })

    outcome = res.expected_outcome
    return {
        "scenario_id": sc.scenario_id, "seed": seed, "variant": variant,
        "calibration_variant": variant,
        "calibration_parameters": {
            "risk_model": opts.risk_model or "R0",
            "risk_penalty_lambda": lam,
        },
        "risk_formula_version": (
            dtsvc.RISK_FORMULA_VERSION_ROBUST if opts.risk_model not in (None, "R0")
            else dtsvc.RISK_FORMULA_VERSION
        ),
        "selected_strategy": res.selected_strategy_name,
        "goal_achievement": rmd._kpi_ga_from_outcome(outcome, target, kpi),
        "risk_adjusted_score": rmd._risk_adjusted(outcome),
        "confidence": res.confidence,
        "selected_dt_risk": outcome.get("risk_score"),
        "dt_sweep_best_strategy": dt_best["strategy"] if dt_best else None,
        "dt_sweep_best_attainment": dt_best["kpi_attainment"] if dt_best else 0.0,
        "is_dt_best": dt_best is not None and res.selected_strategy_name == dt_best["strategy"],
        "improvement_vs_dt_best": round(
            rmd._kpi_ga_from_outcome(outcome, target, kpi)
            - (dt_best["kpi_attainment"] if dt_best else 0.0), 4),
        "strategy_rows": strategy_rows,
    }


def mad_kpi(sc) -> str:
    from app.services import decision_architecture_service as da
    return da.kpi_for_metric(sc.goal_primary_kpi)


# --- zero-variance diagnostic (task section 8) ----------------------------

def _zero_variance_diagnostic() -> dict:
    import pandas as pd

    histories = {
        "constant": [100.0] * 5,
        "low_variance": [99.0, 100.0, 101.0, 100.0, 100.0],
        "normal_variance": [95.0, 100.0, 105.0, 100.0, 98.0],
    }
    moves = {"+5%": 1.05, "+10%": 1.10, "-5%": 0.95}
    out: dict = {}
    for hname, series in histories.items():
        df = pd.DataFrame({"price": series, "marketing_spend": [0.0] * len(series)})
        ranges = {"price": (min(series), max(series)), "marketing_spend": (0.0, 0.0)}
        stats = dtsvc._feature_history_stats(df)
        row = {}
        for mname, mult in moves.items():
            v = 100.0 * mult
            _, r0 = dtsvc._risk_from_extrapolation(ranges, {"price": v, "marketing_spend": 0.0})
            _, r1 = dtsvc._calibrated_risk_from_extrapolation(
                stats, {"price": v, "marketing_spend": 0.0}, "R1")
            row[mname] = {"R0": r0, "R1": r1}
        out[hname] = row
    return out


# --- risk ordering / monotonicity (task section 7) ----------------------

def _spearman(xs: list[float], ys: list[float]) -> float | None:
    pairs = [(x, y) for x, y in zip(xs, ys) if x is not None and y is not None]
    n = len(pairs)
    if n < 3:
        return None
    try:
        from scipy import stats as _st
        rho, _p = _st.spearmanr([p[0] for p in pairs], [p[1] for p in pairs])
        return None if rho != rho else round(float(rho), 4)  # NaN guard
    except Exception:  # noqa: BLE001
        return None


def _monotonicity_violations(rows_by_pair: dict) -> list[dict]:
    """Price +10% must not be scored SAFER (lower risk) than Price +5% for the
    same scenario/seed."""
    bad = []
    for (scn, seed), rows in rows_by_pair.items():
        by_name = {r["strategy_name"]: r for r in rows}
        p5, p10 = by_name.get("Price +5%"), by_name.get("Price +10%")
        if p5 and p10 and p5["digital_twin_risk"] is not None and p10["digital_twin_risk"] is not None:
            if p10["digital_twin_risk"] < p5["digital_twin_risk"] - _TOL:
                bad.append({"scenario_id": scn, "seed": seed,
                            "price5_risk": p5["digital_twin_risk"],
                            "price10_risk": p10["digital_twin_risk"]})
    return bad


# --- per-variant aggregation ------------------------------------------------

_summ = ms._summ


def _variant_aggregate(variant: str, obs: list[dict]) -> dict:
    ok = [o for o in obs if not o.get("error")]
    all_rows = [r for o in ok for r in o["strategy_rows"]]
    rows_by_pair: dict = {}
    for o in ok:
        rows_by_pair.setdefault((o["scenario_id"], o["seed"]), []).extend(o["strategy_rows"])

    disagreements = [o for o in ok if not o["is_dt_best"]]
    impr = [o for o in disagreements if o["improvement_vs_dt_best"] > _TOL]
    degr = [o for o in disagreements if o["improvement_vs_dt_best"] < -_TOL]
    neut = [o for o in disagreements if abs(o["improvement_vs_dt_best"]) <= _TOL]

    viol = _monotonicity_violations(rows_by_pair)
    rho = _spearman(
        [r["raw_extrapolation_distance"] for r in all_rows],
        [r["digital_twin_risk"] for r in all_rows],
    )

    return {
        "variant": variant,
        "n_pairs": len(ok),
        "goal_achievement": _summ([o["goal_achievement"] for o in ok]),
        "risk_adjusted_score": _summ([o["risk_adjusted_score"] for o in ok]),
        "confidence": _summ([o["confidence"] for o in ok]),
        "mean_selected_dt_risk": round(mean([o["selected_dt_risk"] for o in ok
                                             if o["selected_dt_risk"] is not None]), 4) if ok else None,
        "mean_strategy_dt_risk": round(mean([r["digital_twin_risk"] for r in all_rows
                                             if r["digital_twin_risk"] is not None]), 4) if all_rows else None,
        "mean_strategy_rm_score": round(mean([r["RM_score"] for r in all_rows
                                              if r["RM_score"] is not None]), 4) if all_rows else None,
        "dt_best_agreement_rate": round(sum(1 for o in ok if o["is_dt_best"]) / len(ok), 4) if ok else None,
        "override_rate": round(len(disagreements) / len(ok), 4) if ok else None,
        "override_improved": len(impr),
        "override_degraded": len(degr),
        "override_neutral": len(neut),
        "risk_monotonicity": {
            "spearman_rho_distance_vs_risk": rho,
            "price10_safer_than_price5_violations": len(viol),
            "violation_pairs": viol,
        },
    }


def _paired_vs_r0(variant: str, v_obs: list[dict], r0_obs: list[dict]) -> dict:
    key = lambda o: (o["scenario_id"], o["seed"])  # noqa: E731
    vm = {key(o): o for o in v_obs if not o.get("error")}
    rm = {key(o): o for o in r0_obs if not o.get("error")}
    keys = sorted(set(vm) & set(rm))
    out = ms._paired(
        [vm[k]["goal_achievement"] for k in keys],
        [rm[k]["goal_achievement"] for k in keys],
        "goal_achievement", "R0 (D0 / production)",
    )
    out["comparison"] = f"{variant} vs R0 (D0 / production)"
    out["difference_is"] = f"{variant} - R0"
    out[f"{variant}_wins"] = out.pop("full_wins")
    out["r0_wins"] = out.pop("full_losses")
    return out


# --- pre-specified verdict (task sections 12 & 14) ----------------------

CRITERIA = [
    "improves goal achievement over D0",
    "does not eliminate risk ordering (Spearman rho stays positive & meaningful)",
    "no systematic Price+10%-safer-than-Price+5% monotonicity violations",
    "improves or preserves risk-adjusted performance vs D0",
    "avoids the D1 confidence collapse (mean confidence >= 0.60 x D0)",
    "remains interpretable (a single documented formula / weight)",
    "does not require scenario-specific tuning (one global parameter set)",
]


def _criteria_eval(v_agg: dict, r0_agg: dict) -> dict:
    r0_ga = (r0_agg["goal_achievement"] or {}).get("mean", 0.0)
    r0_ra = (r0_agg["risk_adjusted_score"] or {}).get("mean", 0.0)
    r0_conf = (r0_agg["confidence"] or {}).get("mean", 0.0)
    ga = (v_agg["goal_achievement"] or {}).get("mean", 0.0)
    ra = (v_agg["risk_adjusted_score"] or {}).get("mean", 0.0)
    conf = (v_agg["confidence"] or {}).get("mean", 0.0)
    rho = v_agg["risk_monotonicity"]["spearman_rho_distance_vs_risk"]
    viol = v_agg["risk_monotonicity"]["price10_safer_than_price5_violations"]

    checks = {
        "improves_goal_achievement": ga > r0_ga + _TOL,
        "preserves_risk_ordering": rho is not None and rho >= 0.3,
        "no_monotonicity_violations": viol == 0,
        "preserves_risk_adjusted": ra >= r0_ra - _TOL,
        "no_confidence_collapse": conf >= R3_CONFIDENCE_FLOOR_FRAC * r0_conf - _TOL,
        "interpretable": True,   # all variants are one documented formula / weight
        "no_scenario_specific_tuning": True,   # one global parameter set per variant
    }
    passed = sum(1 for v in checks.values() if v)
    if passed == len(checks):
        verdict = "PROMISING"
    elif checks["improves_goal_achievement"] and checks["preserves_risk_ordering"] \
            and checks["no_monotonicity_violations"] and passed >= 5:
        verdict = "PARTIALLY PROMISING"
    else:
        verdict = "NO SATISFACTORY CALIBRATION"
    return {"checks": checks, "criteria_passed": passed, "criteria_total": len(checks),
            "verdict": verdict}


def _select_r3_lambda(r2_aggs: dict, r0_agg: dict) -> tuple[float, str]:
    r0_ra = (r0_agg["risk_adjusted_score"] or {}).get("mean", 0.0)
    r0_conf = (r0_agg["confidence"] or {}).get("mean", 0.0)
    for lam in sorted(R2_LAMBDAS):
        agg = r2_aggs.get(f"R2-{lam:.2f}")
        if agg is None:
            continue
        ra = (agg["risk_adjusted_score"] or {}).get("mean", 0.0)
        conf = (agg["confidence"] or {}).get("mean", 0.0)
        if ra >= r0_ra - _TOL and conf >= R3_CONFIDENCE_FLOOR_FRAC * r0_conf - _TOL:
            return lam, (
                f"smallest λ in {sorted(R2_LAMBDAS)} whose R2 run keeps risk-adjusted "
                f"score ≥ D0 and confidence ≥ {R3_CONFIDENCE_FLOOR_FRAC:g}×D0 → λ={lam:g}")
    return R3_FALLBACK_LAMBDA, (
        f"no λ met the pre-specified criterion; using the documented fallback midpoint "
        f"λ={R3_FALLBACK_LAMBDA:g}")


# --- runner ---------------------------------------------------------------

def _err_row(sc, seed, variant, msg) -> dict:
    return {
        "scenario_id": sc.scenario_id, "seed": seed, "variant": variant, "error": msg,
        "strategy_rows": [], "goal_achievement": 0.0, "risk_adjusted_score": 0.0,
        "confidence": None, "is_dt_best": False, "improvement_vs_dt_best": 0.0,
        "selected_dt_risk": None, "dt_sweep_best_attainment": 0.0,
    }


def _sweep(db: Session, seeds: list[int], variant: str, spec: dict) -> list[dict]:
    rows = []
    for sc in ms.SCENARIOS:
        for seed in seeds:
            try:
                rows.append(_harvest_variant(db, sc, seed, variant, spec))
            except AppError as exc:
                rows.append(_err_row(sc, seed, variant, exc.message))
    return rows


def run_risk_calibration(db: Session, seeds: list[int] | None = None) -> dict:
    seeds = seeds or ms.SEEDS

    observations: dict[str, list[dict]] = {}
    for variant, spec in REFERENCE_VARIANTS + CALIBRATION_VARIANTS:
        observations[variant] = _sweep(db, seeds, variant, spec)

    r0_agg = _variant_aggregate("R0", observations["R0"])
    d1_agg = _variant_aggregate("D1", observations["D1"])
    r2_aggs = {v: _variant_aggregate(v, observations[v])
               for v, _ in CALIBRATION_VARIANTS if v.startswith("R2-")}

    # R3 = R1 risk + the pre-specified λ (selection rule fixed before this call)
    r3_lambda, r3_rule = _select_r3_lambda(r2_aggs, r0_agg)
    observations["R3"] = _sweep(
        db, seeds, "R3", {"risk_model": "R1", "risk_penalty_lambda": r3_lambda})

    variants = ["R0", "D1", "R1", "R2-0.25", "R2-0.50", "R2-0.75", "R3"]
    aggregates = {}
    for v in variants:
        aggregates[v] = (r0_agg if v == "R0" else d1_agg if v == "D1"
                         else r2_aggs.get(v) or _variant_aggregate(v, observations[v]))
    paired = {v: _paired_vs_r0(v, observations[v], observations["R0"])
              for v in variants if v != "R0"}

    # Digital Twin reference (architecture B rule) — identical across variants
    dt_mean = round(mean([o["dt_sweep_best_attainment"] for o in observations["R0"]
                          if not o.get("error")]), 4)

    criteria = {v: _criteria_eval(aggregates[v], r0_agg)
                for v in ("R1", "R2-0.25", "R2-0.50", "R2-0.75", "R3")}

    # overall verdict = best verdict among the genuine calibration variants
    order = {"PROMISING": 2, "PARTIALLY PROMISING": 1, "NO SATISFACTORY CALIBRATION": 0}
    best_variant = max(criteria, key=lambda v: order[criteria[v]["verdict"]])
    overall_verdict = criteria[best_variant]["verdict"]

    return {
        "label": "RISK_MANAGER_CALIBRATION",
        "seeds": seeds, "scenario_count": len(ms.SCENARIOS), "seed_count": len(seeds),
        "total_scenario_seed_pairs": len(ms.SCENARIOS) * len(seeds),
        "aggregation_method": "sample mean / median / std; 95% CI = Student-t on the mean",
        "statistical_method": "paired Wilcoxon signed-rank (variant − R0) on scenario × seed",
        "risk_formula_versions": {
            "R0": dtsvc.RISK_FORMULA_VERSION,
            "R1_R3": dtsvc.RISK_FORMULA_VERSION_ROBUST,
            "robust_scale_rel_floor": dtsvc.ROBUST_SCALE_REL_FLOOR,
        },
        "r3_selection": {"lambda": r3_lambda, "rule": r3_rule},
        "digital_twin_mean_goal_achievement": dt_mean,
        "variants": variants,
        "aggregates": aggregates,
        "paired_vs_r0": paired,
        "zero_variance_diagnostic": _zero_variance_diagnostic(),
        "pre_specified_criteria": CRITERIA,
        "criteria_evaluation": criteria,
        "verdict": overall_verdict,
        "verdict_by_variant": {v: criteria[v]["verdict"] for v in criteria},
        "best_calibration_variant": best_variant,
        "observations": {v: observations[v] for v in variants},
    }
