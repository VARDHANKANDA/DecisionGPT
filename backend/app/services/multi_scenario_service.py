"""Research Console — Multi-scenario Decision Architecture & Ablation runs.

Answers, across DIVERSE controlled synthetic SME decision scenarios:
    "Does Digital Twin + Dynamic Causal Graph + Multi-Agent reasoning provide
     measurable value over simpler decision architectures?"

This module ONLY adds scenario generation + statistical aggregation. It calls
the *existing* decision_architecture_service / ablation_service code unchanged
(same architectures, same ablation meanings, same production pipeline). The
legacy single-scenario experiments are preserved untouched as
`legacy_single_scenario_result`.

Design (docs/MULTI_SCENARIO_EXPERIMENT_PROTOCOL.md, docs/STATISTICAL_ANALYSIS.md):
  * 12 deterministic scenarios (S01..S12) that vary business type, margin,
    demand level, price sensitivity, marketing effectiveness, inventory,
    goal and target.
  * seeds [42, 43, 44, 45, 46].
  * Fairness: for one (scenario, seed) every architecture gets the SAME
    generated business, goal, candidate grid, seed and evaluation horizon.
  * goal_achievement is measured against the scenario's OWN primary KPI
    (revenue / profit / orders), identically for every architecture.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
from scipy import stats
from sqlalchemy.orm import Session

from app.services import ablation_service, decision_architecture_service as da

SEEDS = [42, 43, 44, 45, 46]
ARCH_LABEL = {
    "A": "Prediction only",
    "B": "Prediction + Digital Twin",
    "C": "Prediction + Digital Twin + Single Agent",
    "D": "Full DecisionGPT",
}


@dataclass(frozen=True)
class ScenarioSpec:
    scenario_id: str
    label: str
    industry: str
    primary_lever: str            # documentation only
    goal_objective: str
    goal_primary_kpi: str
    goal_target_percent: float
    time_horizon: int
    unit_cost: float
    selling_price: float
    demand_low: int
    demand_high: int
    promo_uplift: int             # extra units on a promo day == price sensitivity
    promo_price: float
    marketing_every_days: int     # 0 == no marketing at all
    marketing_spend: int
    marketing_attributed_revenue: int   # marketing effectiveness
    with_inventory: bool = False


# 12 scenarios. Deliberately diverse; all within capabilities the existing
# architecture can legitimately simulate. `reduce_churn` is intentionally NOT
# used: the candidate-strategy grid has no retention lever and the synthetic
# generator has no churn-shaped customer data (a genuine capability boundary,
# per the task's "replace unsupported scenarios" rule — documented).
SCENARIOS: list[ScenarioSpec] = [
    ScenarioSpec("S01", "Clothing Retail — revenue via pricing", "Apparel Retail", "pricing",
                 "increase_revenue", "revenue", 12.0, 2, 200, 600, 8, 14, 3, 540, 6, 900, 4000),
    ScenarioSpec("S02", "Clothing Retail — profit via pricing", "Apparel Retail", "pricing",
                 "increase_profit", "profit", 12.0, 2, 200, 600, 8, 14, 3, 540, 6, 900, 4000),
    ScenarioSpec("S03", "Electronics Retail — sales via marketing", "Electronics Retail", "marketing",
                 "increase_sales", "orders", 15.0, 2, 2000, 3200, 3, 7, 2, 3000, 2, 4000, 14000),
    ScenarioSpec("S04", "Grocery Retail — inventory risk", "Grocery Retail", "inventory",
                 "reduce_inventory_risk", "inventory_risk", 10.0, 2, 38, 46, 40, 70, 8, 43, 4, 1500, 5000,
                 with_inventory=True),
    ScenarioSpec("S05", "Furniture Retail — high-ticket profit", "Furniture Retail", "pricing",
                 "increase_profit", "profit", 15.0, 3, 6000, 12000, 1, 3, 1, 11400, 6, 1200, 3000),
    ScenarioSpec("S06", "E-commerce — revenue via marketing", "E-commerce", "marketing",
                 "increase_revenue", "revenue", 20.0, 2, 250, 520, 12, 22, 6, 470, 2, 3000, 12000),
    ScenarioSpec("S07", "Apparel E-commerce — marketing ROI", "Apparel E-commerce", "marketing",
                 "improve_marketing_roi", "marketing_roi", 15.0, 2, 300, 650, 10, 18, 5, 585, 2, 3500, 16000),
    ScenarioSpec("S08", "Consumer Goods — thin-margin profit", "Consumer Goods", "inventory",
                 "increase_profit", "profit", 10.0, 2, 80, 110, 25, 45, 10, 99, 4, 1200, 4000,
                 with_inventory=True),
    ScenarioSpec("S09", "Regional Retail — sales, price-sensitive", "Regional Retail", "pricing",
                 "increase_sales", "orders", 12.0, 2, 150, 300, 15, 30, 12, 264, 6, 800, 3000),
    ScenarioSpec("S10", "Small Manufacturing — cost/profit", "Small Manufacturing", "inventory",
                 "increase_profit", "profit", 8.0, 3, 400, 560, 5, 9, 1, 532, 0, 0, 0,
                 with_inventory=True),
    ScenarioSpec("S11", "Mixed Retail — revenue via marketing", "Mixed Retail", "marketing",
                 "increase_revenue", "revenue", 15.0, 2, 200, 450, 18, 30, 5, 410, 3, 1200, 7000),
    ScenarioSpec("S12", "Small E-commerce — conservative revenue", "Small E-commerce", "conservative",
                 "increase_revenue", "revenue", 8.0, 2, 220, 480, 6, 11, 2, 456, 5, 500, 2500),
]


# --- statistics -------------------------------------------------------------


def _summ(values: list[float | None]) -> dict | None:
    xs = np.array([v for v in values if v is not None], dtype=float)
    if xs.size == 0:
        return None
    n = int(xs.size)
    mean = float(xs.mean())
    std = float(xs.std(ddof=1)) if n > 1 else 0.0
    if n > 1:
        half = float(stats.t.ppf(0.975, n - 1) * std / np.sqrt(n))
        ci = [round(mean - half, 4), round(mean + half, 4)]
    else:
        ci = None
    return {
        "n": n, "mean": round(mean, 4), "median": round(float(np.median(xs)), 4),
        "std": round(std, 4), "min": round(float(xs.min()), 4), "max": round(float(xs.max()), 4),
        "ci95": ci,
    }


def _paired(full: list[float], other: list[float], metric: str, other_label: str) -> dict:
    a = np.array(full, dtype=float)
    b = np.array(other, dtype=float)
    d = a - b
    n = int(d.size)
    wins = int((d > 1e-9).sum())
    losses = int((d < -1e-9).sum())
    ties = n - wins - losses
    out = {
        "comparison": f"Full (D) vs {other_label}", "metric": metric, "n_pairs": n,
        "mean_difference": round(float(d.mean()), 4),
        "median_difference": round(float(np.median(d)), 4),
        "std_difference": round(float(d.std(ddof=1)) if n > 1 else 0.0, 4),
        "full_wins": wins, "ties": ties, "full_losses": losses,
    }
    if n > 1 and d.std(ddof=1) > 0:
        half = float(stats.t.ppf(0.975, n - 1) * d.std(ddof=1) / np.sqrt(n))
        out["mean_difference_ci95"] = [round(float(d.mean()) - half, 4), round(float(d.mean()) + half, 4)]
    else:
        out["mean_difference_ci95"] = None

    nonzero = int((np.abs(d) > 1e-9).sum())
    if np.allclose(d, 0.0) or nonzero < 2:
        reason = (
            "all paired differences are exactly zero"
            if np.allclose(d, 0.0)
            else f"only {nonzero} non-zero paired difference(s)"
        )
        out["test"] = "Wilcoxon signed-rank"
        out["statistic"] = None
        out["p_value"] = None
        out["effect_size_r"] = None
        out["interpretation"] = (
            f"Statistical significance not assessed ({reason}); the test's assumptions are not met. "
            f"Descriptive result only: mean paired difference {d.mean():+.4f}."
        )
        return out
    try:
        res = stats.wilcoxon(a, b, zero_method="wilcox", correction=False, alternative="two-sided")
        w, p = float(res.statistic), float(res.pvalue)
        nz = int((np.abs(d) > 1e-9).sum())
        z = stats.norm.ppf(p / 2) if p < 1 else 0.0
        r = round(abs(z) / np.sqrt(nz), 4) if nz > 0 else None
        out.update(test="Wilcoxon signed-rank (paired on scenario x seed)", statistic=round(w, 4),
                   p_value=round(p, 6), effect_size_r=r)
        if p < 0.05:
            direction = "higher" if d.mean() > 0 else "lower"
            out["interpretation"] = (
                f"Full DecisionGPT showed statistically significantly {direction} {metric} than "
                f"{other_label} across the {n} paired scenario/seed evaluations (p={p:.4f})."
            )
        else:
            out["interpretation"] = (
                f"No statistically significant difference in {metric} between Full DecisionGPT and "
                f"{other_label} (Wilcoxon p={p:.4f}). Descriptive means differ by "
                f"{d.mean():+.4f}."
            )
    except ValueError as exc:  # e.g. all-zero after zero handling
        out.update(test="Wilcoxon signed-rank", statistic=None, p_value=None, effect_size_r=None,
                   interpretation=f"Significance not assessed ({exc}).")
    return out


# --- runners --------------------------------------------------------------


def run_multi_scenario_architecture(db: Session, seeds: list[int] | None = None) -> dict:
    seeds = seeds or SEEDS
    observations: list[dict] = []
    for sc in SCENARIOS:
        kpi = da.kpi_for_metric(sc.goal_primary_kpi)
        for seed in seeds:
            business_id, goal_id = da._seed_synthetic_business(db, seed, sc)
            try:
                results = [
                    da._run_architecture_a(db, business_id),
                    da._run_architecture_b(db, business_id, sc.goal_target_percent, kpi),
                    da._run_architecture_c(db, business_id, sc.goal_target_percent, kpi),
                    da._run_architecture_d(db, business_id, goal_id, sc.goal_target_percent, kpi),
                ]
            finally:
                da._cleanup_synthetic_business(db, business_id)
            for r in results:
                observations.append({
                    "scenario_id": sc.scenario_id, "scenario_label": sc.label,
                    "primary_lever": sc.primary_lever, "goal_objective": sc.goal_objective,
                    "goal_primary_kpi": sc.goal_primary_kpi, "kpi_measured": kpi,
                    "goal_target_percent": sc.goal_target_percent, "seed": seed,
                    "architecture": r.architecture, "architecture_label": r.label,
                    "selected_strategy": r.selected_strategy_name,
                    "goal_achievement": r.goal_achievement,
                    "risk_adjusted_score": r.risk_adjusted_score,
                    "confidence": r.confidence,
                    "latency_seconds": r.latency_seconds,
                })

    by_arch = {a: [o for o in observations if o["architecture"] == a] for a in "ABCD"}
    aggregates = {
        a: {
            m: _summ([o[m] for o in by_arch[a]])
            for m in ("goal_achievement", "risk_adjusted_score", "confidence", "latency_seconds")
        }
        for a in "ABCD"
    }

    # paired: same (scenario, seed) key order for Full vs A and Full vs B
    key = lambda o: (o["scenario_id"], o["seed"])  # noqa: E731
    d_map = {key(o): o for o in by_arch["D"]}
    paired = {}
    for other in ("A", "B"):
        o_map = {key(o): o for o in by_arch[other]}
        keys = sorted(set(d_map) & set(o_map))
        paired[f"D_vs_{other}"] = _paired(
            [d_map[k]["goal_achievement"] for k in keys],
            [o_map[k]["goal_achievement"] for k in keys],
            "goal_achievement", ARCH_LABEL[other],
        )

    # robustness: each architecture vs Full, per scenario/seed
    robustness = {}
    for other in ("A", "B", "C"):
        o_map = {key(o): o for o in by_arch[other]}
        keys = sorted(set(d_map) & set(o_map))
        diff = np.array([o_map[k]["goal_achievement"] - d_map[k]["goal_achievement"] for k in keys])
        robustness[other] = {
            "vs_full_wins": int((diff > 1e-9).sum()),      # this arch beats Full
            "vs_full_ties": int((np.abs(diff) <= 1e-9).sum()),
            "vs_full_losses": int((diff < -1e-9).sum()),
        }
    ga_d = np.array([o["goal_achievement"] for o in by_arch["D"]])
    robustness["D_distribution"] = {
        "best": round(float(ga_d.max()), 4), "worst": round(float(ga_d.min()), 4),
        "median": round(float(np.median(ga_d)), 4),
        "std": round(float(ga_d.std(ddof=1)), 4) if ga_d.size > 1 else 0.0,
    }

    # failure-mode analysis (correlational, not causal)
    thresh = float(np.quantile(ga_d, 0.34))
    failures = []
    for o in by_arch["D"]:
        if o["goal_achievement"] <= max(thresh, 1e-9) or o["goal_achievement"] == 0.0:
            factors = []
            if (o["confidence"] or 1.0) < 0.2:
                factors.append("low decision confidence (<0.20)")
            if o["risk_adjusted_score"] <= 0.0:
                factors.append("non-positive risk-adjusted score")
            if o["goal_primary_kpi"] in ("marketing_roi", "inventory_risk"):
                factors.append("goal KPI not directly simulated (revenue proxy used)")
            b_key = (o["scenario_id"], o["seed"])
            b_ga = {key(x): x for x in by_arch["B"]}.get(b_key, {}).get("goal_achievement")
            if b_ga is not None and b_ga - o["goal_achievement"] > 1e-9:
                factors.append("simpler architecture B did better on this scenario/seed")
            failures.append({
                "scenario_id": o["scenario_id"], "seed": o["seed"],
                "goal_objective": o["goal_objective"], "selected_strategy": o["selected_strategy"],
                "goal_achievement": o["goal_achievement"],
                "risk_adjusted_score": o["risk_adjusted_score"], "confidence": o["confidence"],
                "associated_factors": factors or ["none identified"],
            })

    return {
        "label": "SYNTHETIC_SCENARIO_SUITE",
        "scenario_count": len(SCENARIOS), "seed_count": len(seeds), "seeds": seeds,
        "evaluation_count": len(observations),
        "aggregation_method": "sample mean / median / std; 95% CI = Student-t on the mean (n per architecture = scenario_count x seed_count)",
        "statistical_method": "paired Wilcoxon signed-rank on scenario x seed (scipy.stats.wilcoxon, two-sided, zero_method='wilcox')",
        "metric_definition": "goal_achievement = attainment of the scenario's own primary KPI (revenue/profit/orders); marketing_roi & inventory_risk use revenue attainment as a documented proxy",
        "scenarios": [asdict(s) for s in SCENARIOS],
        "observations": observations,
        "aggregates": aggregates,
        "paired": paired,
        "robustness": robustness,
        "failure_mode_analysis": failures,
    }


def run_multi_scenario_ablation(db: Session, seeds: list[int] | None = None) -> dict:
    seeds = seeds or SEEDS
    observations: list[dict] = []
    for sc in SCENARIOS:
        for seed in seeds:
            study = ablation_service.run_ablation_study(db, seed=seed, scenario=sc)
            full = next(c for c in study.configs if c.config == "A")
            for c in study.configs:
                observations.append({
                    "scenario_id": sc.scenario_id, "scenario_label": sc.label,
                    "goal_objective": sc.goal_objective, "seed": seed,
                    "config": c.config, "config_label": c.label,
                    "component_removed": (c.components_removed or ["(none)"])[0],
                    "selected_strategy": c.selected_strategy_name,
                    "goal_achievement": c.goal_achievement,
                    "risk_adjusted_score": c.risk_adjusted_score,
                    "confidence": c.confidence,
                    "delta_goal_achievement_vs_full": round(full.goal_achievement - c.goal_achievement, 4),
                    "delta_risk_adjusted_vs_full": round(full.risk_adjusted_score - c.risk_adjusted_score, 2),
                    "delta_confidence_vs_full": (
                        round(full.confidence - c.confidence, 4)
                        if full.confidence is not None and c.confidence is not None else None
                    ),
                })

    configs = ["A", "B", "C", "D", "E", "F"]
    by_cfg = {c: [o for o in observations if o["config"] == c] for c in configs}
    aggregates = {
        c: {
            "config_label": by_cfg[c][0]["config_label"] if by_cfg[c] else c,
            "component_removed": by_cfg[c][0]["component_removed"] if by_cfg[c] else "",
            "goal_achievement": _summ([o["goal_achievement"] for o in by_cfg[c]]),
            "risk_adjusted_score": _summ([o["risk_adjusted_score"] for o in by_cfg[c]]),
            "confidence": _summ([o["confidence"] for o in by_cfg[c]]),
            "delta_goal_achievement_vs_full": _summ([o["delta_goal_achievement_vs_full"] for o in by_cfg[c]]),
            "delta_risk_adjusted_vs_full": _summ([o["delta_risk_adjusted_vs_full"] for o in by_cfg[c]]),
        }
        for c in configs
    }

    # paired: Full vs each ablation on goal_achievement
    key = lambda o: (o["scenario_id"], o["seed"])  # noqa: E731
    a_map = {key(o): o for o in by_cfg["A"]}
    paired = {}
    for c in ("B", "C", "D", "E", "F"):
        c_map = {key(o): o for o in by_cfg[c]}
        keys = sorted(set(a_map) & set(c_map))
        paired[f"Full_vs_{c}"] = _paired(
            [a_map[k]["goal_achievement"] for k in keys],
            [c_map[k]["goal_achievement"] for k in keys],
            "goal_achievement", f"{c} ({c_map[keys[0]]['config_label'] if keys else c})",
        )

    return {
        "label": "SYNTHETIC_SCENARIO_SUITE",
        "scenario_count": len(SCENARIOS), "seed_count": len(seeds), "seeds": seeds,
        "evaluation_count": len(observations),
        "aggregation_method": "sample mean / median / std; 95% CI = Student-t on the mean",
        "statistical_method": "paired Wilcoxon signed-rank on scenario x seed (Full vs each ablation)",
        "scenarios": [asdict(s) for s in SCENARIOS],
        "observations": observations,
        "aggregates": aggregates,
        "paired": paired,
    }
