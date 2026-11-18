"""Exogenous ground-truth objective for the upgraded controlled evaluation.

THIS MODULE IS DELIBERATELY INDEPENDENT of DecisionGPT's internal scoring.

It must NEVER import or call:
  * app.analytics.digital_twin_service       (the Digital Twin)
  * app.services.decision_service            (the production pipeline)
  * app.services.decision_architecture_service  (incl. ``_goal_achievement`` /
                                                 ``_kpi_goal_achievement``)
  * app.analytics.forecast_service
  * app.agents.*

It imports only the standard library, ``numpy``, and (optionally) ``scipy`` for
the classical-optimizer baseline. ``tests/unit/test_eval_ground_truth.py`` proves
this independence both by static source inspection and by running every function
with the Digital Twin / pipeline unavailable.

The objective is a closed-form deterministic economic model parameterised
entirely by the scenario. Given (scenario, action) it returns a single number;
"higher is always better" (a ``sense == "min"`` objective is returned negated).

Model (``exogenous_objective_v1``) --- distinct in functional form from the
Digital Twin's recursive last-value extrapolation:

    price        = p0 * (1 + price_pct/100)
    mkt_spend    = s0 * (1 + mkt_pct/100)
    demand       = d0 * max(0, 1 + eps * price_pct/100)                 # linear own-price elasticity
                   + mr * ((mkt_spend - s0) / 1000) * kappa            # marketing response (kappa < 1 => lagged/partial)
    eff_inv_cap  = inventory_cap * (1 + inv_pct/100)
    units        = clip(demand, 0, min(eff_inv_cap, capacity_cap))
    revenue      = price * units
    cost         = unit_cost * units + mkt_spend
    profit       = revenue - cost
    holding_cost = holding_rate * max(0, eff_inv_cap - units)

    objective value:  revenue | profit | orders(=units)  -> as-is (sense "max")
                      holding_cost                        -> negated (sense "min")
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np

GROUND_TRUTH_VERSION = "exogenous_objective_v1"

# Modules this file must never depend on (asserted by the independence test).
FORBIDDEN_DEPENDENCIES = (
    "digital_twin_service",
    "decision_service",
    "decision_architecture_service",
    "forecast_service",
    "goal_achievement",
    "app.agents",
)

_EPS = 1e-9


# --------------------------------------------------------------------------- #
# action parsing                                                             #
# --------------------------------------------------------------------------- #
ActionTuple = tuple  # tuple of {"type": str, "value": float} dicts


def action_key(action: ActionTuple) -> str:
    parts = sorted(f"{a['type']}={a['value']:+g}" for a in action)
    return "|".join(parts) if parts else "noop"


def action_pcts(action: ActionTuple) -> dict[str, float]:
    """Extract per-lever percentage deltas from an action tuple. Missing levers
    default to 0. Unknown lever types raise (the evaluation vocabulary is the
    production one: price_change / marketing_change / inventory_change)."""
    out = {"price_change": 0.0, "marketing_change": 0.0, "inventory_change": 0.0}
    for a in action:
        t = a["type"]
        if t not in out:
            raise ValueError(f"ground_truth: unsupported action type {t!r}")
        out[t] = float(a["value"])
    return out


# --------------------------------------------------------------------------- #
# closed-form objective                                                      #
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class ObjectiveResult:
    value: float                 # "higher is better" (sense-min objectives are negated)
    raw_value: float             # the un-negated objective quantity
    feasible: bool
    infeasible_reason: str | None
    breakdown: dict[str, float] = field(default_factory=dict)


def _params(scenario: Any) -> dict[str, float]:
    p = dict(scenario.params)
    p.setdefault("kappa", 1.0)
    p.setdefault("holding_rate", 0.0)
    p.setdefault("capacity_cap", math.inf)
    p.setdefault("inventory_cap", math.inf)
    return p


def _objective_kpi(scenario: Any) -> tuple[str, str]:
    obj = scenario.objective
    kpi = obj["kpi"] if isinstance(obj, dict) else obj.kpi
    sense = obj["sense"] if isinstance(obj, dict) else obj.sense
    return kpi, sense


def is_feasible(scenario: Any, action: ActionTuple) -> tuple[bool, str | None]:
    p = _params(scenario)
    c = dict(scenario.constraints)
    pct = action_pcts(action)
    price_pct = pct["price_change"]
    mkt_spend = p["marketing_base_spend"] * (1 + pct["marketing_change"] / 100.0)

    floor = c.get("price_floor_pct")
    ceil = c.get("price_ceiling_pct")
    if floor is not None and price_pct < floor - _EPS:
        return False, f"price change {price_pct:+g}% below floor {floor:+g}%"
    if ceil is not None and price_pct > ceil + _EPS:
        return False, f"price change {price_pct:+g}% above ceiling {ceil:+g}%"

    cash_cap = c.get("cash_cap")
    if cash_cap is not None and mkt_spend > cash_cap + _EPS:
        return False, f"marketing spend {mkt_spend:.1f} exceeds cash cap {cash_cap:.1f}"
    return True, None


def evaluate(scenario: Any, action: ActionTuple) -> ObjectiveResult:
    """Deterministic given (scenario, action). No randomness, no external calls."""
    p = _params(scenario)
    pct = action_pcts(action)
    kpi, sense = _objective_kpi(scenario)

    price = p["base_price"] * (1 + pct["price_change"] / 100.0)
    mkt_spend = p["marketing_base_spend"] * (1 + pct["marketing_change"] / 100.0)
    demand_price_factor = max(0.0, 1.0 + p["price_elasticity"] * pct["price_change"] / 100.0)
    mkt_delta_k = (mkt_spend - p["marketing_base_spend"]) / 1000.0
    demand_mkt_units = p["marketing_response"] * mkt_delta_k * p["kappa"]
    demand = p["base_demand"] * demand_price_factor + demand_mkt_units

    eff_inv_cap = p["inventory_cap"] * (1 + pct["inventory_change"] / 100.0)
    hard_cap = min(eff_inv_cap, p["capacity_cap"])
    units = max(0.0, min(demand, hard_cap))

    revenue = price * units
    cost = p["unit_cost"] * units + mkt_spend
    profit = revenue - cost
    unsold_cap = max(0.0, (eff_inv_cap if math.isfinite(eff_inv_cap) else units) - units)
    holding_cost = p["holding_rate"] * unsold_cap

    raw = {
        "revenue": revenue,
        "profit": profit,
        "orders": units,
        "holding_cost": holding_cost,
    }[kpi]
    value = raw if sense == "max" else -raw

    feasible, reason = is_feasible(scenario, action)
    return ObjectiveResult(
        value=round(float(value), 6),
        raw_value=round(float(raw), 6),
        feasible=feasible,
        infeasible_reason=reason,
        breakdown={
            "price": round(price, 4),
            "marketing_spend": round(mkt_spend, 4),
            "demand": round(demand, 4),
            "units": round(units, 4),
            "revenue": round(revenue, 4),
            "cost": round(cost, 4),
            "profit": round(profit, 4),
            "holding_cost": round(holding_cost, 4),
        },
    )


# --------------------------------------------------------------------------- #
# baselines & oracle  (NONE of these call DecisionGPT)                       #
# --------------------------------------------------------------------------- #
def _noop_action(feasible_actions: list[ActionTuple]) -> ActionTuple:
    for a in feasible_actions:
        if all(abs(float(x["value"])) < _EPS for x in a) or len(a) == 0:
            return a
    # fall back to the smallest-magnitude action
    return min(feasible_actions, key=lambda a: sum(abs(float(x["value"])) for x in a))


def oracle(scenario: Any, feasible_actions: list[ActionTuple]) -> dict:
    """Best feasible action under the ground-truth objective. Exhaustive over the
    supplied feasible set. This is an UPPER-BOUND REFERENCE, not a deployable
    policy, and it does not call DecisionGPT."""
    scored = []
    for a in feasible_actions:
        r = evaluate(scenario, a)
        if r.feasible:
            scored.append((a, r.value, r))
    if not scored:
        return {"status": "no_feasible_action", "action": None, "value": None}
    scored.sort(key=lambda t: t[1], reverse=True)
    best_a, best_v, _ = scored[0]
    worst_v = scored[-1][1]
    return {
        "status": "ok",
        "action": best_a,
        "action_key": action_key(best_a),
        "value": best_v,
        "worst_value": worst_v,
        "n_feasible": len(scored),
        "ranking": [{"action_key": action_key(a), "value": v} for a, v, _ in scored],
    }


def naive_baseline(scenario: Any, feasible_actions: list[ActionTuple]) -> dict:
    """Status quo: take no action (or the smallest-magnitude feasible action)."""
    a = _noop_action(feasible_actions)
    r = evaluate(scenario, a)
    return {"policy": "naive", "action": a, "action_key": action_key(a), "value": r.value, "feasible": r.feasible}


def greedy_baseline(scenario: Any, feasible_actions: list[ActionTuple], step_pct: float = 1.0) -> dict:
    """Local first-order heuristic: estimate the objective slope w.r.t. each lever
    at the status quo by a +/- ``step_pct`` finite difference (using the closed
    form ONLY locally, never enumerating the full set), pick the single lever and
    sign with the best local improvement, then snap to the nearest feasible
    single-lever action of that lever. Distinct from ``oracle`` (which enumerates
    everything)."""
    base = evaluate(scenario, ()).value
    best_lever, best_sign, best_slope = None, 0.0, 0.0
    for lever in ("price_change", "marketing_change", "inventory_change"):
        up = evaluate(scenario, ({"type": lever, "value": step_pct},)).value
        dn = evaluate(scenario, ({"type": lever, "value": -step_pct},)).value
        for cand_val, cand_sign in ((up, +1.0), (dn, -1.0)):
            slope = (cand_val - base)
            if slope > best_slope + _EPS:
                best_slope, best_lever, best_sign = slope, lever, cand_sign
    if best_lever is None:
        a = _noop_action(feasible_actions)
        r = evaluate(scenario, a)
        return {"policy": "greedy", "action": a, "action_key": action_key(a), "value": r.value,
                "feasible": r.feasible, "note": "no locally improving lever"}

    # snap: nearest feasible single-lever action of best_lever in the chosen sign
    same_lever = []
    for a in feasible_actions:
        pcts = action_pcts(a)
        nz = [k for k, v in pcts.items() if abs(v) > _EPS]
        if nz == [best_lever] and pcts[best_lever] * best_sign > 0:
            same_lever.append((a, abs(pcts[best_lever])))
    if same_lever:
        chosen = min(same_lever, key=lambda t: t[1])[0]  # smallest magnitude step in that direction
    else:
        chosen = _noop_action(feasible_actions)
    r = evaluate(scenario, chosen)
    return {"policy": "greedy", "action": chosen, "action_key": action_key(chosen),
            "value": r.value, "feasible": r.feasible, "lever": best_lever, "sign": best_sign}


def classical_optimizer(scenario: Any, feasible_actions: list[ActionTuple]) -> dict:
    """Continuous relaxation: optimise the closed-form objective over continuous
    lever percentages within bounds + the cash constraint, then project the
    continuous optimum to the nearest feasible discrete action. Represents a
    standard operations-research approach ON THE MODELLED OBJECTIVE. Returns
    ``{"status": "na", ...}`` where no smooth well-defined formulation exists.
    Does not call DecisionGPT."""
    try:
        from scipy.optimize import minimize
    except Exception as exc:  # pragma: no cover - scipy is a declared dependency
        return {"status": "na", "reason": f"scipy unavailable: {exc}"}

    c = dict(scenario.constraints)
    p = _params(scenario)
    # variable order: [price_pct, marketing_pct, inventory_pct]
    bounds = [
        (c.get("price_floor_pct", -15.0), c.get("price_ceiling_pct", 15.0)),
        (-30.0, 30.0),
        (0.0, 30.0),
    ]

    def neg_obj(x: np.ndarray) -> float:
        act = (
            {"type": "price_change", "value": float(x[0])},
            {"type": "marketing_change", "value": float(x[1])},
            {"type": "inventory_change", "value": float(x[2])},
        )
        return -evaluate(scenario, act).value

    cons = []
    cash_cap = c.get("cash_cap")
    if cash_cap is not None:
        cons.append({
            "type": "ineq",
            "fun": lambda x: cash_cap - p["marketing_base_spend"] * (1 + x[1] / 100.0),
        })

    res = minimize(neg_obj, x0=np.zeros(3), method="SLSQP", bounds=bounds,
                   constraints=cons, options={"maxiter": 200, "ftol": 1e-9})
    if not res.success and not np.isfinite(res.fun):
        return {"status": "na", "reason": f"optimizer did not converge: {res.message}"}

    cont = res.x

    def _l1(a: ActionTuple) -> float:
        pc = action_pcts(a)
        return (abs(pc["price_change"] - cont[0])
                + abs(pc["marketing_change"] - cont[1])
                + abs(pc["inventory_change"] - cont[2]))

    feas = [a for a in feasible_actions if is_feasible(scenario, a)[0]]
    if not feas:
        return {"status": "na", "reason": "no feasible discrete action to project onto"}
    projected = min(feas, key=_l1)
    r = evaluate(scenario, projected)
    return {
        "status": "ok",
        "policy": "classical_optimizer",
        "continuous_optimum": {"price_pct": round(float(cont[0]), 3),
                               "marketing_pct": round(float(cont[1]), 3),
                               "inventory_pct": round(float(cont[2]), 3)},
        "action": projected,
        "action_key": action_key(projected),
        "value": r.value,
        "feasible": r.feasible,
        "projection_l1_gap": round(_l1(projected), 3),
    }


# --------------------------------------------------------------------------- #
# normalised metrics                                                         #
# --------------------------------------------------------------------------- #
def normalized_performance(value: float, oracle_value: float, worst_value: float) -> float:
    """(value - worst) / (oracle - worst), clipped to [0, 1]. 1.0 == oracle."""
    span = oracle_value - worst_value
    if abs(span) < _EPS:
        return 1.0
    return round(float(np.clip((value - worst_value) / span, 0.0, 1.0)), 6)


def regret(value: float, oracle_value: float, worst_value: float) -> float:
    """Normalised regret: (oracle - value) / (oracle - worst), clipped to [0, 1].
    0.0 == oracle (no regret)."""
    span = oracle_value - worst_value
    if abs(span) < _EPS:
        return 0.0
    return round(float(np.clip((oracle_value - value) / span, 0.0, 1.0)), 6)


def score_selection(scenario: Any, selected_action: ActionTuple | None,
                    feasible_actions: list[ActionTuple], oracle_result: dict | None = None) -> dict:
    """The PRIMARY-metric bundle for one condition's selected action.

    ``selected_action = None`` (a condition that recommends nothing) is scored as
    the status-quo / no-op action, so 'do nothing' is a real, comparable policy
    rather than a missing value."""
    orc = oracle_result or oracle(scenario, feasible_actions)
    if orc.get("status") != "ok":
        return {"status": orc.get("status", "no_oracle"), "primary_value": None,
                "normalized_performance": None, "regret": None}
    act = selected_action if selected_action is not None else _noop_action(feasible_actions)
    r = evaluate(scenario, act)
    return {
        "status": "ok",
        "selected_action_key": action_key(act),
        "selected_from_none": selected_action is None,
        "primary_value": r.value,
        "primary_raw_value": r.raw_value,
        "feasible": r.feasible,
        "infeasible_reason": r.infeasible_reason,
        "oracle_value": orc["value"],
        "worst_value": orc["worst_value"],
        "normalized_performance": normalized_performance(r.value, orc["value"], orc["worst_value"]),
        "regret": regret(r.value, orc["value"], orc["worst_value"]),
        "breakdown": r.breakdown,
    }
