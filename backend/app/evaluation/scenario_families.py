"""Parameterised scenario generation for the upgraded controlled evaluation.

PURE: stdlib + numpy only. No production service, Digital Twin, or
``decision_service`` import. Nothing here touches
``multi_scenario_service.SCENARIOS`` (the frozen 12).

An ``EvalScenario`` is a PARAMETER SET + a history *specification*. The concrete
day-by-day history the system ingests is realised per ``(scenario, seed)`` by
``realise_history`` so that seeds are genuine independent replicates (mirroring
the frozen study, where the 5 seeds each generated a different business). A
``reference_history`` at a canonical seed is stored for provenance / hashing /
pre-run factor extraction.

Every scenario is reproducible from ``(master_seed, family_id, family_index)`` and
is fully machine-readable: scenario_id, family_id, seed, master_seed, params,
history_spec, reference_history, constraints, objective {"kpi","sense"},
feasible_actions (the identical set every A/B/C/D condition selects from; built to
match the production candidate templates and re-verified by the harness),
eval_reference_actions (+ the explicit no-op), uncertainty, noise,
perturbation_config, provenance, content_hash.

Action vocabulary is EXACTLY the production one: price_change / marketing_change /
inventory_change (percentage deltas). No new action types are introduced.
"""
from __future__ import annotations

import hashlib
import json
import random
from dataclasses import asdict, dataclass, field
from typing import Callable

import numpy as np

GENERATOR_VERSION = "upgraded_eval_scenarios_v2"

ActionDict = dict
ActionTuple = tuple
NOOP: ActionTuple = ()


# --------------------------------------------------------------------------- #
# production-candidate action templates (mirror strategy_generation_service)  #
# --------------------------------------------------------------------------- #
def _a(*pairs) -> ActionTuple:
    return tuple({"type": t, "value": float(v)} for t, v in pairs)


_REVENUE_ACTIONS = [
    _a(("marketing_change", 10)), _a(("marketing_change", 20)),
    _a(("price_change", 5)), _a(("price_change", 10)),
    _a(("price_change", -3)), _a(("price_change", -5)), _a(("price_change", -10)),
    _a(("marketing_change", 10), ("price_change", -5)),
]
_SALES_ACTIONS = list(_REVENUE_ACTIONS)
_PROFIT_ACTIONS_BASE = [
    _a(("price_change", 5)), _a(("price_change", 10)),
    _a(("marketing_change", -10)), _a(("marketing_change", -20)),
    _a(("price_change", 5), ("marketing_change", -10)),
]
_PROFIT_ACTIONS_ROI_POS = _PROFIT_ACTIONS_BASE + [_a(("marketing_change", 10))]
_INVENTORY_RISK_ACTIONS = [
    _a(("inventory_change", 20)), _a(("inventory_change", 10)),
    _a(("inventory_change", -10)), _a(("inventory_change", -20)),
    _a(("price_change", 5), ("inventory_change", -10)),
]


def production_candidate_actions(objective: str, *, marketing_roi_positive: bool = False,
                                 has_inventory: bool = False) -> list[ActionTuple]:
    if objective == "increase_revenue":
        return list(_REVENUE_ACTIONS)
    if objective == "increase_sales":
        return list(_SALES_ACTIONS)
    if objective == "increase_profit":
        return list(_PROFIT_ACTIONS_ROI_POS if marketing_roi_positive else _PROFIT_ACTIONS_BASE)
    if objective == "reduce_inventory_risk":
        return list(_INVENTORY_RISK_ACTIONS) if has_inventory else []
    raise ValueError(f"scenario_families: unsupported objective {objective!r}")


# --------------------------------------------------------------------------- #
# scenario dataclass                                                         #
# --------------------------------------------------------------------------- #
@dataclass
class EvalScenario:
    scenario_id: str
    family_id: str
    family_label: str
    family_description: str
    seed: int                            # canonical seed used for reference_history
    master_seed: int
    partition: str
    params: dict
    history_spec: dict                   # kwargs for _history(); realised per (scenario, seed)
    reference_history: dict              # history at the canonical seed (provenance / hashing / pre-run factors)
    constraints: dict
    objective: dict                      # {"kpi": str, "sense": "max"|"min"}
    feasible_actions: list
    eval_reference_actions: list
    uncertainty: dict
    noise: dict
    perturbation_config: dict
    provenance: dict = field(default_factory=dict)

    def content_hash(self) -> str:
        payload = {
            "generator_version": GENERATOR_VERSION,
            "family_id": self.family_id, "seed": self.seed, "master_seed": self.master_seed,
            "params": self.params, "history_spec": self.history_spec,
            "reference_history": self.reference_history, "constraints": self.constraints,
            "objective": self.objective,
            "feasible_actions": [[dict(x) for x in a] for a in self.feasible_actions],
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()

    def to_dict(self) -> dict:
        d = asdict(self)
        d["feasible_actions"] = [[dict(x) for x in a] for a in self.feasible_actions]
        d["eval_reference_actions"] = [[dict(x) for x in a] for a in self.eval_reference_actions]
        d["content_hash"] = self.content_hash()
        return d

    @staticmethod
    def from_dict(d: dict) -> "EvalScenario":
        """Rebuild a scenario from a ``scenario_manifest.json`` entry. Actions are
        restored as tuples-of-dicts; ``content_hash`` is recomputed and, when the
        manifest recorded one, checked."""
        def _acts(seq):
            return [tuple(dict(x) for x in a) for a in seq]
        sc = EvalScenario(
            scenario_id=d["scenario_id"], family_id=d["family_id"],
            family_label=d["family_label"], family_description=d["family_description"],
            seed=int(d["seed"]), master_seed=int(d["master_seed"]),
            partition=d.get("partition", "unassigned"), params=dict(d["params"]),
            history_spec=dict(d["history_spec"]), reference_history=dict(d["reference_history"]),
            constraints=dict(d["constraints"]), objective=dict(d["objective"]),
            feasible_actions=_acts(d["feasible_actions"]),
            eval_reference_actions=_acts(d["eval_reference_actions"]),
            uncertainty=dict(d.get("uncertainty") or {}), noise=dict(d.get("noise") or {}),
            perturbation_config=dict(d.get("perturbation_config") or {}),
            provenance=dict(d.get("provenance") or {}),
        )
        if d.get("content_hash") and d["content_hash"] != sc.content_hash():
            raise ValueError(f"content_hash mismatch for {sc.scenario_id}: manifest "
                             f"{d['content_hash']} != recomputed {sc.content_hash()}")
        return sc


# --------------------------------------------------------------------------- #
# history realisation                                                        #
# --------------------------------------------------------------------------- #
def _history(rng: random.Random, p: dict, *, days: int = 90, price_band_pct: float = 0.0,
             demand_noise_sd: float = 0.08, drop_rate: float = 0.0, trend_break: float = 0.0,
             obs_price_jitter_pct: float = 0.0, constant_price: bool = False) -> dict:
    p0 = p["base_price"]
    s0 = p["marketing_base_spend"]
    d0 = p["base_demand"]
    price = np.full(days, p0, dtype=float)
    if price_band_pct > 0 and not constant_price:
        step = p0 * price_band_pct / 100.0 / 6.0
        walk = np.cumsum(np.array([rng.uniform(-step, step) for _ in range(days)]))
        walk -= walk.mean()
        price = np.clip(p0 + walk, p0 * (1 - price_band_pct / 100.0), p0 * (1 + price_band_pct / 100.0))
    if not constant_price:
        for d in range(days):
            if d % 10 == 0:
                price[d] *= 0.94
            if obs_price_jitter_pct:
                price[d] *= 1.0 + rng.uniform(-obs_price_jitter_pct, obs_price_jitter_pct) / 100.0

    units = np.array([
        max(1.0, d0 * (1 + rng.gauss(0, demand_noise_sd)) + (0.15 * d0 if d % 10 == 0 else 0.0))
        for d in range(days)
    ], dtype=float)
    if trend_break > 0:
        cut = int(days * 2 / 3)
        units[cut:] *= (1 + trend_break)
    mkt = np.array([s0 + rng.uniform(-0.1, 0.1) * s0 for _ in range(days)], dtype=float)

    idx = list(range(days))
    if drop_rate > 0:
        keep = [d for d in idx if rng.random() >= drop_rate]
        idx = keep or idx[: max(10, days // 3)]

    return {
        "days": len(idx),
        "day_offsets": idx,
        "price": [round(float(price[d]), 4) for d in idx],
        "units": [round(float(units[d]), 4) for d in idx],
        "marketing_spend": [round(float(mkt[d]), 4) for d in idx],
        "stock": None,
    }


def realise_history(scenario: "EvalScenario", seed: int) -> dict:
    """The concrete day-by-day history the system ingests for one (scenario,
    seed). Deterministic in (scenario_id, seed); different seeds are genuine
    independent replicates (they are not deterministic re-runs of one history)."""
    rng = random.Random(f"{scenario.scenario_id}:{int(seed)}:{GENERATOR_VERSION}")
    spec = dict(scenario.history_spec)
    inv_cap = spec.pop("with_inventory_cap", None)
    h = _history(rng, scenario.params, **spec)
    if inv_cap is not None:
        h["stock"] = [round(float(inv_cap) * 1.05, 4) for _ in h["day_offsets"]]
    return h


# --------------------------------------------------------------------------- #
# family scaffolding                                                         #
# --------------------------------------------------------------------------- #
def _base_params(rng: random.Random) -> dict:
    base_price = float(rng.choice([80, 120, 200, 400, 900, 3000]))
    margin = rng.uniform(0.18, 0.55)
    return {
        "base_price": base_price,
        "unit_cost": round(base_price * (1 - margin), 4),
        "base_demand": float(rng.choice([40, 90, 150, 300, 600, 2200])),
        "price_elasticity": round(rng.uniform(-1.8, -0.5), 4),
        "marketing_response": round(rng.uniform(0.3, 1.6), 4),
        "marketing_base_spend": float(rng.choice([500, 900, 1200, 3000, 4000])),
        "kappa": 1.0,
        "holding_rate": 0.0,
        "capacity_cap": float("inf"),
        "inventory_cap": float("inf"),
        "horizon_days": 14,
        "target_percent": 12.0,
    }


_STD_PERTURBATIONS = {
    "input_noise": [0.25, 0.5, 0.75],
    "forecast_error_bias": [0.25, 0.5],
    "missing_values": [0.2, 0.4],
    "uncertainty_inflation": [0.5, 1.0],
    "constraint_tighten": [0.25, 0.5],
    "constraint_relax": [0.25, 0.5],
    "distribution_shift": [0.3, 0.6],
    "contradictory_signals": [0.5, 1.0],
    "extreme_but_feasible": [1.0],
    "adversarial": [1.0],
}


@dataclass(frozen=True)
class FamilySpec:
    family_id: str
    label: str
    description: str
    partition_group: int
    builder: Callable[[random.Random, int, int], EvalScenario]


def _mk(fam: FamilySpec, rng: random.Random, index: int, master_seed: int, *,
        params: dict, history_spec: dict, constraints: dict, objective: dict,
        marketing_roi_positive: bool = False, has_inventory: bool = False,
        uncertainty: dict, noise: dict) -> EvalScenario:
    # The ephemeral business seeded by the harness always records a positive
    # marketing ROI (attributed_revenue > spend), so for a profit objective the
    # production ``strategy_generation_service`` ALWAYS emits its extra
    # "marketing +10%" candidate. The declared feasible set must therefore
    # include it, or the identical-action-space invariant fails at run time
    # (verified in the Phase-3 dry run).
    roi_pos = marketing_roi_positive or objective["kpi_objective"] == "increase_profit"
    feasible = production_candidate_actions(
        objective["kpi_objective"], marketing_roi_positive=roi_pos,
        has_inventory=has_inventory,
    )
    obj = {"kpi": objective["kpi"], "sense": objective["sense"]}
    canonical_seed = 40_000 + index
    sc = EvalScenario(
        scenario_id=f"{fam.family_id}__{index:04d}",
        family_id=fam.family_id, family_label=fam.label, family_description=fam.description,
        seed=canonical_seed, master_seed=master_seed, partition="unassigned",
        params=params, history_spec=history_spec, reference_history={},
        constraints=constraints, objective=obj,
        feasible_actions=feasible, eval_reference_actions=feasible + [NOOP],
        uncertainty=uncertainty, noise=noise,
        perturbation_config={"supported": dict(_STD_PERTURBATIONS)},
        provenance={
            "generator_version": GENERATOR_VERSION, "family_id": fam.family_id,
            "family_index": index, "master_seed": master_seed,
            "goal_objective": objective["kpi_objective"],
            "marketing_roi_positive": roi_pos,
            "action_space_policy": "production_candidate_templates",
        },
    )
    sc.reference_history = realise_history(sc, canonical_seed)
    return sc


# --------------------------------------------------------------------------- #
# family builders                                                            #
# --------------------------------------------------------------------------- #
def _f_demand_uncertainty(rng, i, ms):
    p = _base_params(rng)
    spec = {"days": 90, "demand_noise_sd": round(rng.uniform(0.18, 0.35), 4)}
    return _mk(FAMILIES["demand_uncertainty"], rng, i, ms, params=p, history_spec=spec, constraints={},
               objective={"kpi": "revenue", "sense": "max", "kpi_objective": "increase_revenue"},
               uncertainty={"demand_noise_sd": spec["demand_noise_sd"]},
               noise={"obs_noise_sd": 0.0, "missing_rate": 0.0})


def _f_price_uncertainty(rng, i, ms):
    p = _base_params(rng)
    band = round(rng.uniform(15, 35), 4)
    spec = {"days": 90, "price_band_pct": band, "demand_noise_sd": 0.1}
    return _mk(FAMILIES["price_uncertainty"], rng, i, ms, params=p, history_spec=spec,
               constraints={"price_floor_pct": -15.0, "price_ceiling_pct": 15.0},
               objective={"kpi": "revenue", "sense": "max", "kpi_objective": "increase_revenue"},
               uncertainty={"price_band_pct": band}, noise={"obs_noise_sd": 0.0, "missing_rate": 0.0})


def _f_inventory_constraint(rng, i, ms):
    p = _base_params(rng)
    cap = round(p["base_demand"] * rng.uniform(0.80, 0.98), 4)
    p["inventory_cap"] = cap
    spec = {"days": 90, "demand_noise_sd": 0.12, "with_inventory_cap": cap}
    return _mk(FAMILIES["inventory_constraint"], rng, i, ms, params=p, history_spec=spec,
               constraints={"inventory_cap": cap}, has_inventory=True,
               objective={"kpi": "orders", "sense": "max", "kpi_objective": "reduce_inventory_risk"},
               uncertainty={"inventory_cap_ratio": cap / p["base_demand"]},
               noise={"obs_noise_sd": 0.0, "missing_rate": 0.0})


def _f_cash_constraint(rng, i, ms):
    p = _base_params(rng)
    cap = round(p["marketing_base_spend"] * rng.uniform(1.02, 1.12), 4)
    spec = {"days": 90, "demand_noise_sd": 0.12}
    return _mk(FAMILIES["cash_constraint"], rng, i, ms, params=p, history_spec=spec,
               constraints={"cash_cap": cap},
               objective={"kpi": "revenue", "sense": "max", "kpi_objective": "increase_revenue"},
               uncertainty={"cash_headroom_pct": (cap / p["marketing_base_spend"] - 1) * 100},
               noise={"obs_noise_sd": 0.0, "missing_rate": 0.0})


def _f_capacity_constraint(rng, i, ms):
    p = _base_params(rng)
    cap = round(p["base_demand"] * rng.uniform(1.02, 1.10), 4)
    p["capacity_cap"] = cap
    spec = {"days": 90, "demand_noise_sd": 0.1}
    return _mk(FAMILIES["capacity_constraint"], rng, i, ms, params=p, history_spec=spec,
               constraints={"capacity_cap": cap},
               objective={"kpi": "profit", "sense": "max", "kpi_objective": "increase_profit"},
               uncertainty={"capacity_ratio": cap / p["base_demand"]},
               noise={"obs_noise_sd": 0.0, "missing_rate": 0.0})


def _f_promotion_decision(rng, i, ms):
    p = _base_params(rng)
    p["price_elasticity"] = round(rng.uniform(-2.2, -1.3), 4)
    spec = {"days": 90, "price_band_pct": round(rng.uniform(8, 18), 4), "demand_noise_sd": 0.1}
    return _mk(FAMILIES["promotion_decision"], rng, i, ms, params=p, history_spec=spec,
               constraints={"price_floor_pct": -20.0, "price_ceiling_pct": 12.0},
               objective={"kpi": "revenue", "sense": "max", "kpi_objective": "increase_revenue"},
               uncertainty={"elasticity": p["price_elasticity"]},
               noise={"obs_noise_sd": 0.0, "missing_rate": 0.0})


def _f_resource_allocation(rng, i, ms):
    p = _base_params(rng)
    p["marketing_response"] = round(rng.uniform(0.9, 1.6), 4)
    spec = {"days": 90, "price_band_pct": 8.0, "demand_noise_sd": 0.12}
    return _mk(FAMILIES["resource_allocation"], rng, i, ms, params=p, history_spec=spec,
               constraints={"cash_cap": round(p["marketing_base_spend"] * 1.25, 4),
                            "price_floor_pct": -12.0, "price_ceiling_pct": 12.0},
               objective={"kpi": "profit", "sense": "max", "kpi_objective": "increase_profit"},
               uncertainty={"marketing_response": p["marketing_response"]},
               noise={"obs_noise_sd": 0.0, "missing_rate": 0.0})


def _f_supplier_uncertainty(rng, i, ms):
    p = _base_params(rng)
    p["unit_cost"] = round(p["base_price"] * rng.uniform(0.82, 0.94), 4)
    spec = {"days": 90, "demand_noise_sd": 0.14}
    return _mk(FAMILIES["supplier_uncertainty"], rng, i, ms, params=p, history_spec=spec,
               constraints={"price_floor_pct": -8.0, "price_ceiling_pct": 15.0},
               objective={"kpi": "profit", "sense": "max", "kpi_objective": "increase_profit"},
               uncertainty={"gross_margin": 1 - p["unit_cost"] / p["base_price"]},
               noise={"obs_noise_sd": 0.0, "missing_rate": 0.0})


def _f_competing_objectives(rng, i, ms):
    p = _base_params(rng)
    p["price_elasticity"] = round(rng.uniform(-1.9, -1.4), 4)
    p["unit_cost"] = round(p["base_price"] * rng.uniform(0.80, 0.90), 4)
    spec = {"days": 90, "price_band_pct": 10.0, "demand_noise_sd": 0.1}
    return _mk(FAMILIES["competing_objectives"], rng, i, ms, params=p, history_spec=spec,
               constraints={"price_floor_pct": -12.0, "price_ceiling_pct": 15.0},
               objective={"kpi": "profit", "sense": "max", "kpi_objective": "increase_profit"},
               uncertainty={"elasticity": p["price_elasticity"],
                            "gross_margin": 1 - p["unit_cost"] / p["base_price"]},
               noise={"obs_noise_sd": 0.0, "missing_rate": 0.0})


def _f_asymmetric_risk(rng, i, ms):
    p = _base_params(rng)
    p["price_elasticity"] = round(rng.uniform(-0.5, -0.2), 4)
    spec = {"days": 90, "price_band_pct": 2.0, "demand_noise_sd": 0.08}
    return _mk(FAMILIES["asymmetric_risk"], rng, i, ms, params=p, history_spec=spec,
               constraints={"price_floor_pct": -10.0, "price_ceiling_pct": 15.0},
               objective={"kpi": "revenue", "sense": "max", "kpi_objective": "increase_revenue"},
               uncertainty={"elasticity": p["price_elasticity"], "price_band_pct": 2.0},
               noise={"obs_noise_sd": 0.0, "missing_rate": 0.0})


def _f_delayed_effects(rng, i, ms):
    p = _base_params(rng)
    p["kappa"] = round(rng.uniform(0.25, 0.55), 4)
    spec = {"days": 90, "demand_noise_sd": 0.1}
    return _mk(FAMILIES["delayed_effects"], rng, i, ms, params=p, history_spec=spec, constraints={},
               objective={"kpi": "revenue", "sense": "max", "kpi_objective": "increase_revenue"},
               uncertainty={"kappa": p["kappa"]}, noise={"obs_noise_sd": 0.0, "missing_rate": 0.0})


def _f_noisy_observations(rng, i, ms):
    p = _base_params(rng)
    spec = {"days": 90, "demand_noise_sd": round(rng.uniform(0.25, 0.4), 4),
            "obs_price_jitter_pct": round(rng.uniform(3, 8), 4)}
    return _mk(FAMILIES["noisy_observations"], rng, i, ms, params=p, history_spec=spec, constraints={},
               objective={"kpi": "revenue", "sense": "max", "kpi_objective": "increase_revenue"},
               uncertainty={}, noise={"obs_demand_noise_sd": spec["demand_noise_sd"],
                                      "obs_price_jitter_pct": spec["obs_price_jitter_pct"]})


def _f_missing_observations(rng, i, ms):
    p = _base_params(rng)
    dr = round(rng.uniform(0.25, 0.45), 4)
    spec = {"days": 90, "demand_noise_sd": 0.12, "drop_rate": dr}
    return _mk(FAMILIES["missing_observations"], rng, i, ms, params=p, history_spec=spec, constraints={},
               objective={"kpi": "revenue", "sense": "max", "kpi_objective": "increase_revenue"},
               uncertainty={}, noise={"missing_rate": dr, "obs_noise_sd": 0.0})


def _f_conflicting_signals(rng, i, ms):
    p = _base_params(rng)
    p["price_elasticity"] = round(rng.uniform(-2.0, -1.5), 4)
    spec = {"days": 90, "demand_noise_sd": 0.1, "trend_break": round(rng.uniform(0.25, 0.5), 4)}
    return _mk(FAMILIES["conflicting_signals"], rng, i, ms, params=p, history_spec=spec,
               constraints={"price_floor_pct": -12.0, "price_ceiling_pct": 12.0},
               objective={"kpi": "revenue", "sense": "max", "kpi_objective": "increase_revenue"},
               uncertainty={"elasticity": p["price_elasticity"], "history_trend_break": True},
               noise={"obs_noise_sd": 0.0, "missing_rate": 0.0})


def _f_low_data(rng, i, ms):
    # Spans the frozen pipeline's MIN_HISTORY_DAYS=35 boundary on purpose: shorter
    # instances are expected to hit the pre-registered ``insufficient_data``
    # exclusion (they exercise that path); longer-but-still-short instances run
    # and contribute genuinely data-constrained evidence.
    p = _base_params(rng)
    days = int(rng.choice([30, 33, 36, 40, 44, 48]))
    spec = {"days": days, "demand_noise_sd": 0.15}
    return _mk(FAMILIES["low_data"], rng, i, ms, params=p, history_spec=spec, constraints={},
               objective={"kpi": "revenue", "sense": "max", "kpi_objective": "increase_revenue"},
               uncertainty={"history_days": days, "spans_min_history_threshold": True},
               noise={"obs_noise_sd": 0.0, "missing_rate": 0.0})


def _f_high_volatility(rng, i, ms):
    p = _base_params(rng)
    p["unit_cost"] = round(p["base_price"] * rng.uniform(0.86, 0.93), 4)
    p["price_elasticity"] = round(rng.uniform(-2.4, -1.6), 4)
    spec = {"days": 90, "price_band_pct": round(rng.uniform(25, 40), 4),
            "demand_noise_sd": round(rng.uniform(0.35, 0.5), 4)}
    return _mk(FAMILIES["high_volatility"], rng, i, ms, params=p, history_spec=spec,
               constraints={"price_floor_pct": -20.0, "price_ceiling_pct": 20.0},
               objective={"kpi": "profit", "sense": "max", "kpi_objective": "increase_profit"},
               uncertainty={"stress": True, "elasticity": p["price_elasticity"]},
               noise={"obs_demand_noise_sd": spec["demand_noise_sd"]})


def _f_adversarial_risk_trap(rng, i, ms):
    p = _base_params(rng)
    p["price_elasticity"] = round(rng.uniform(-0.35, -0.15), 4)
    spec = {"days": 90, "demand_noise_sd": 0.06, "constant_price": True}
    return _mk(FAMILIES["adversarial_risk_trap"], rng, i, ms, params=p, history_spec=spec,
               constraints={"price_floor_pct": -10.0, "price_ceiling_pct": 15.0},
               objective={"kpi": "profit", "sense": "max", "kpi_objective": "increase_profit"},
               uncertainty={"elasticity": p["price_elasticity"], "constant_price_history": True,
                            "adversarial": True},
               noise={"obs_noise_sd": 0.0, "missing_rate": 0.0})


FAMILIES: dict[str, FamilySpec] = {
    "demand_uncertainty":    FamilySpec("demand_uncertainty", "Demand uncertainty",
                                        "Wide day-to-day demand variance; revenue objective.", 0, _f_demand_uncertainty),
    "price_uncertainty":     FamilySpec("price_uncertainty", "Price uncertainty",
                                        "Historical price varies widely within a band (non-degenerate range).", 0, _f_price_uncertainty),
    "inventory_constraint":  FamilySpec("inventory_constraint", "Inventory constraint",
                                        "Stock cap near baseline demand; orders objective.", 1, _f_inventory_constraint),
    "cash_constraint":       FamilySpec("cash_constraint", "Cash constraint",
                                        "Marketing budget only marginally above status quo.", 1, _f_cash_constraint),
    "capacity_constraint":   FamilySpec("capacity_constraint", "Capacity constraint",
                                        "Production capacity near baseline demand; profit objective.", 1, _f_capacity_constraint),
    "promotion_decision":    FamilySpec("promotion_decision", "Promotion decision",
                                        "Strongly price-elastic demand; promo-depth choice.", 2, _f_promotion_decision),
    "resource_allocation":   FamilySpec("resource_allocation", "Resource allocation",
                                        "Both levers responsive under a shared budget; profit objective.", 2, _f_resource_allocation),
    "supplier_uncertainty":  FamilySpec("supplier_uncertainty", "Supplier uncertainty",
                                        "Thin, volatile gross margin; profit objective.", 3, _f_supplier_uncertainty),
    "competing_objectives":  FamilySpec("competing_objectives", "Competing objectives",
                                        "Revenue-optimal action differs from profit-optimal; objective is profit.", 3, _f_competing_objectives),
    "asymmetric_risk":       FamilySpec("asymmetric_risk", "Asymmetric risk",
                                        "Inelastic demand (price rise best) but narrow price history.", 4, _f_asymmetric_risk),
    "delayed_effects":       FamilySpec("delayed_effects", "Delayed effects",
                                        "Marketing effect only partly realised within the decision horizon.", 4, _f_delayed_effects),
    "noisy_observations":    FamilySpec("noisy_observations", "Noisy observations",
                                        "High observation noise on the ingested history; clean ground truth.", 5, _f_noisy_observations),
    "missing_observations":  FamilySpec("missing_observations", "Missing observations",
                                        "25-45% of history days dropped.", 5, _f_missing_observations),
    "conflicting_signals":   FamilySpec("conflicting_signals", "Conflicting signals",
                                        "Recent history trends up but demand is strongly price-elastic.", 6, _f_conflicting_signals),
    "low_data":              FamilySpec("low_data", "Low data",
                                        "30-48 days of history, spanning the pipeline's 35-day minimum.", 6, _f_low_data),
    "high_volatility":       FamilySpec("high_volatility", "High volatility (stress)",
                                        "Extreme-but-feasible: max demand noise, min margin, wide price band.", 7, _f_high_volatility),
    "adversarial_risk_trap": FamilySpec("adversarial_risk_trap", "Adversarial risk trap",
                                        "Constant price history + inelastic demand: risk heuristic vs true optimum.", 7, _f_adversarial_risk_trap),
}

FAMILY_IDS: list[str] = list(FAMILIES.keys())
assert len(FAMILY_IDS) >= 15, "at least 15 scenario families are required"

MAX_SUPPORTED_INSTANCES = 100_000


def generate_suite(n: int, master_seed: int, families: list[str] | None = None) -> list[EvalScenario]:
    fam_ids = families or FAMILY_IDS
    if n < len(fam_ids):
        raise ValueError(f"n ({n}) must be >= number of families ({len(fam_ids)})")
    if n > MAX_SUPPORTED_INSTANCES:
        raise ValueError(f"n ({n}) exceeds MAX_SUPPORTED_INSTANCES ({MAX_SUPPORTED_INSTANCES})")
    out: list[EvalScenario] = []
    per_family_index: dict[str, int] = {fid: 0 for fid in fam_ids}
    for k in range(n):
        fid = fam_ids[k % len(fam_ids)]
        idx = per_family_index[fid]
        per_family_index[fid] += 1
        rng = random.Random(f"{master_seed}:{GENERATOR_VERSION}:{fid}:{idx}")
        out.append(FAMILIES[fid].builder(rng, idx, master_seed))
    return out


def partition_families(master_seed: int, dev: float = 0.60, val: float = 0.20,
                       test: float = 0.20, families: list[str] | None = None) -> dict[str, list[str]]:
    fam_ids = sorted(families or FAMILY_IDS, key=lambda f: (FAMILIES[f].partition_group, f))
    if abs((dev + val + test) - 1.0) > 1e-6:
        raise ValueError("dev + val + test must sum to 1.0")
    rng = random.Random(f"{master_seed}:family_partition_v1")
    shuffled = list(fam_ids)
    rng.shuffle(shuffled)
    m = len(shuffled)
    n_dev = max(1, round(m * dev))
    n_val = max(1, round(m * val))
    n_dev = min(n_dev, m - 2)
    n_val = min(n_val, m - n_dev - 1)
    parts = {
        "development": sorted(shuffled[:n_dev]),
        "validation": sorted(shuffled[n_dev:n_dev + n_val]),
        "locked_test": sorted(shuffled[n_dev + n_val:]),
    }
    allf = parts["development"] + parts["validation"] + parts["locked_test"]
    assert sorted(allf) == sorted(fam_ids)
    assert len(set(allf)) == len(allf)
    for name in ("development", "validation", "locked_test"):
        assert parts[name]
    return parts


def assign_partitions(scenarios: list[EvalScenario], partition_map: dict[str, list[str]]) -> None:
    lookup = {fid: part for part, fids in partition_map.items() for fid in fids}
    for sc in scenarios:
        sc.partition = lookup.get(sc.family_id, "unassigned")


def suite_checksum(scenarios: list[EvalScenario]) -> str:
    h = hashlib.sha256()
    for sc in sorted(scenarios, key=lambda s: s.scenario_id):
        h.update(sc.content_hash().encode())
    return h.hexdigest()
