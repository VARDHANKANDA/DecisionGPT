"""Action-responsive synthetic environments for the upgraded controlled
evaluation **V2**.

PURE: stdlib + numpy only. No production service, Digital Twin, ``decision_service``
or ``ground_truth`` import. Independent of ``scenario_families`` (V1) except for
the *production candidate templates* (which mirror
``strategy_generation_service`` and are shared, unchanged domain facts).

Why V2 exists: in V1 the historical ``units`` series was generated independently
of the historical ``price`` / ``marketing`` series, so no action-response was
identifiable from the data and Decision Simulation (condition B) collapsed to a
constant "+10% price" policy on 100% of executions. V2's **System A** history
generator makes historical demand genuinely respond to historical price and
marketing, with real (non-degenerate) variation in the price and spend series so
the response is identifiable.

System A (this module, ``realise_history``) vs System B
(``ground_truth.evaluate``, unchanged from V1):

  System A : d_t = d0 · (p_t/p0)**a_elast · (s_t/s0)**a_mkt · season_t
                   · inv_avail_t · exp(N(0, sigma_obs))            (log-linear, stochastic)
  System B : d   = d0 · max(0, 1 + eps·Δp/100) + mr·(Δs/1000)·kappa  (additive-linear, deterministic)

They describe the same domain but are **different functional forms**. The System-B
parameters (eps, mr, kappa) are drawn as **noisy monotone functions** of the
System-A parameters (a_elast, a_mkt) so a system that recovers the historical
response gets *useful but imperfect* guidance about the true objective — not a
copy of it, and not something unrelated.
"""
from __future__ import annotations

import hashlib
import json
import math
import random
from dataclasses import asdict, dataclass, field
from typing import Callable

import numpy as np

from app.evaluation.scenario_families import NOOP, production_candidate_actions

GENERATOR_VERSION = "upgraded_eval_scenarios_v3"
ENV_VERSION = "system_A_action_responsive_v1"

ActionTuple = tuple


# --------------------------------------------------------------------------- #
# scenario dataclass (self-contained copy; stamps GENERATOR_VERSION = v3)     #
# --------------------------------------------------------------------------- #
@dataclass
class EvalScenarioV2:
    scenario_id: str
    family_id: str
    family_label: str
    family_description: str
    seed: int
    master_seed: int
    partition: str
    params: dict                     # System-B params + recorded System-A params
    history_spec: dict               # kwargs for _history_v2 (System A)
    reference_history: dict          # realisation at the canonical seed
    constraints: dict
    objective: dict                  # {"kpi","sense"}
    feasible_actions: list
    eval_reference_actions: list
    uncertainty: dict
    noise: dict
    perturbation_config: dict
    provenance: dict = field(default_factory=dict)

    def content_hash(self) -> str:
        payload = {
            "generator_version": GENERATOR_VERSION, "env_version": ENV_VERSION,
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
    def from_dict(d: dict) -> "EvalScenarioV2":
        def _acts(seq):
            return [tuple(dict(x) for x in a) for a in seq]
        sc = EvalScenarioV2(
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
            raise ValueError(f"content_hash mismatch for {sc.scenario_id}")
        return sc


# --------------------------------------------------------------------------- #
# System-A history generator                                                 #
# --------------------------------------------------------------------------- #
def _np_rng(scenario_id: str, seed: int) -> np.random.Generator:
    h = hashlib.sha256(f"{scenario_id}:{seed}:{GENERATOR_VERSION}".encode()).hexdigest()
    return np.random.default_rng(int(h[:16], 16))


def _history_v2(rng: np.random.Generator, p: dict, *, days: int,
                price_walk_pct: float, spend_walk_pct: float, sigma_obs: float,
                season_amp: float, promo_freq: int = 0, promo_depth: float = 0.0,
                drop_rate: float = 0.0, obs_price_jitter_pct: float = 0.0,
                trend_break: float = 0.0, cost_drift: float = 0.0,
                narrow_price: bool = False) -> dict:
    """System A. Historical demand RESPONDS to the historical price and marketing
    series via a log-linear (power-law) model. Price and spend carry real,
    identifiable variation. Per-seed multiplicative log-normal noise."""
    p0 = float(p["base_price"]); s0 = float(p["marketing_base_spend"]); d0 = float(p["base_demand"])
    a_elast = float(p["a_elast"]); a_mkt = float(p["a_mkt"])
    cap = float(p.get("capacity_cap", math.inf))
    inv_cap = float(p.get("inventory_cap", math.inf))

    # --- price series: mean-reverting walk + regular promo cycles ------------
    #     (real, identifiable variation: log-price SD target ~0.08-0.16 for the
    #      non-narrow families; the V1 bug was near-zero price variation)
    band = max(1.0, price_walk_pct) / 100.0
    if narrow_price:
        band = min(band, 0.04)
    lp = np.zeros(days)
    theta = 0.15  # mean reversion
    for d in range(1, days):
        lp[d] = lp[d - 1] * (1 - theta) + rng.normal(0.0, band / 2.2)
    lp = np.clip(lp - lp.mean(), math.log(1 - band), math.log(1 + band))
    price = p0 * np.exp(lp)
    if not narrow_price:
        pf = promo_freq if promo_freq else 12
        pd_ = promo_depth if promo_depth else 0.10
        for d in range(pf // 2, days, max(3, pf)):
            price[d] *= (1.0 - pd_)
    if obs_price_jitter_pct:
        price = price * (1.0 + rng.uniform(-obs_price_jitter_pct, obs_price_jitter_pct, size=days) / 100.0)
    price = np.maximum(price, 0.01 * p0)

    # --- marketing spend series: mean-reverting walk -------------------------
    sband = max(1.0, spend_walk_pct) / 100.0
    sl = np.zeros(days)
    for d in range(1, days):
        sl[d] = sl[d - 1] * 0.85 + rng.normal(0.0, sband / 2.5)
    sl = np.clip(sl - sl.mean(), math.log(1 - sband), math.log(1 + sband))
    spend = np.maximum(s0 * np.exp(sl), 0.05 * s0)

    # --- multiplicative seasonality (weekly) ----------------------------------
    t = np.arange(days)
    season = 1.0 + season_amp * np.sin(2 * math.pi * t / 7.0)

    # --- ACTION-RESPONSIVE demand (System A power law) -----------------------
    price_factor = (price / p0) ** a_elast                 # a_elast < 0  => higher price, lower demand
    mkt_factor = (spend / s0) ** a_mkt                     # a_mkt > 0    => higher spend, higher demand
    lognoise = np.exp(rng.normal(0.0, sigma_obs, size=days))
    demand = d0 * price_factor * mkt_factor * season * lognoise
    if trend_break:
        c = int(days * 2 / 3)
        demand[c:] *= (1.0 + trend_break)

    # --- fulfilment ceilings (inventory / capacity families) ----------------
    on_hand = None
    if math.isfinite(inv_cap):
        on_hand = np.full(days, inv_cap * 1.05)
    units = demand.copy()
    if math.isfinite(cap):
        units = np.minimum(units, cap)
    if on_hand is not None:
        units = np.minimum(units, on_hand)
    units = np.maximum(units, 1.0)

    # --- optional cost drift (recorded only; affects System B via params) ---
    # (cost_drift is applied to params by the family builder, not here)

    idx = list(range(days))
    if drop_rate > 0:
        keep = [d for d in idx if rng.random() >= drop_rate]
        idx = keep or idx[: max(12, days // 3)]

    return {
        "days": len(idx),
        "day_offsets": idx,
        "price": [round(float(price[d]), 4) for d in idx],
        "units": [round(float(units[d]), 4) for d in idx],
        "marketing_spend": [round(float(spend[d]), 4) for d in idx],
        "stock": ([round(float(on_hand[d]), 4) for d in idx] if on_hand is not None else None),
    }


def realise_history(scenario: EvalScenarioV2, seed: int) -> dict:
    """The concrete history the system ingests for one (scenario, seed).
    Deterministic in (scenario_id, seed); different seeds are genuine independent
    replicates (per-seed log-normal noise + independent random walks)."""
    rng = _np_rng(scenario.scenario_id, int(seed))
    spec = dict(scenario.history_spec)
    return _history_v2(rng, scenario.params, **spec)


# --------------------------------------------------------------------------- #
# parameter draw + System-A -> System-B coupling                             #
# --------------------------------------------------------------------------- #
def _base_params_v2(rng: random.Random) -> dict:
    base_price = float(rng.choice([80, 150, 300, 600, 1500]))
    margin = rng.uniform(0.22, 0.55)
    return {
        "base_price": base_price,
        "unit_cost": round(base_price * (1 - margin), 4),
        "base_demand": float(rng.choice([50, 120, 250, 500, 1500])),
        "marketing_base_spend": float(rng.choice([600, 1000, 2500, 4000])),
        "kappa": 1.0,
        "holding_rate": 0.0,
        "capacity_cap": math.inf,
        "inventory_cap": math.inf,
        "horizon_days": 14,
        "target_percent": 12.0,
    }


def _couple_system_B(p: dict, rng: random.Random, *, kappa: float = 1.0) -> None:
    """Draw System-B objective parameters as NOISY MONOTONE functions of the
    System-A parameters already in ``p`` (``a_elast``, ``a_mkt``). Mutates ``p``.
    This is a parameter relationship, NOT shared code with ``ground_truth``."""
    a_elast = p["a_elast"]; a_mkt = p["a_mkt"]
    p["price_elasticity"] = round(float(np.clip(a_elast + rng.gauss(0, 0.35), -3.0, -0.15)), 4)
    mr = (0.4 + 3.0 * a_mkt) * (1.0 + rng.gauss(0, 0.25))
    p["marketing_response"] = round(float(np.clip(mr, 0.2, 2.0)), 4)
    p["kappa"] = round(float(np.clip(kappa + rng.gauss(0, 0.05), 0.2, 1.0)), 4)


# --------------------------------------------------------------------------- #
# families                                                                   #
# --------------------------------------------------------------------------- #
_STD_PERTURBATIONS = {
    "input_noise": [0.25, 0.5, 0.75], "forecast_error_bias": [0.25, 0.5],
    "missing_values": [0.2, 0.4], "uncertainty_inflation": [0.5, 1.0],
    "constraint_tighten": [0.25, 0.5], "constraint_relax": [0.25, 0.5],
    "distribution_shift": [0.3, 0.6], "contradictory_signals": [0.5, 1.0],
    "extreme_but_feasible": [1.0], "adversarial": [1.0],
}


@dataclass(frozen=True)
class FamilySpecV2:
    family_id: str
    label: str
    description: str
    partition_group: int
    builder: Callable[[random.Random, int, int], EvalScenarioV2]


def _mk(fam: FamilySpecV2, rng: random.Random, index: int, master_seed: int, *,
        params: dict, history_spec: dict, constraints: dict, kpi_objective: str,
        kpi: str, sense: str, has_inventory: bool = False,
        uncertainty: dict, noise: dict) -> EvalScenarioV2:
    roi_pos = kpi_objective == "increase_profit"
    feasible = production_candidate_actions(kpi_objective, marketing_roi_positive=roi_pos,
                                            has_inventory=has_inventory)
    canonical_seed = 50_000 + index
    sc = EvalScenarioV2(
        scenario_id=f"v2_{fam.family_id}__{index:04d}",
        family_id=fam.family_id, family_label=fam.label, family_description=fam.description,
        seed=canonical_seed, master_seed=master_seed, partition="unassigned",
        params=params, history_spec=history_spec, reference_history={},
        constraints=constraints, objective={"kpi": kpi, "sense": sense},
        feasible_actions=feasible, eval_reference_actions=feasible + [NOOP],
        uncertainty=uncertainty, noise=noise,
        perturbation_config={"supported": dict(_STD_PERTURBATIONS)},
        provenance={"generator_version": GENERATOR_VERSION, "env_version": ENV_VERSION,
                    "family_id": fam.family_id, "family_index": index, "master_seed": master_seed,
                    "goal_objective": kpi_objective, "marketing_roi_positive": roi_pos,
                    "system_A": "power-law demand response to historical price & marketing",
                    "system_B": "ground_truth.exogenous_objective_v1 (unchanged)",
                    "AB_coupling": "eps ~ a_elast + N(0,.35); mr ~ f(a_mkt)·(1+N(0,.25))"},
    )
    sc.reference_history = realise_history(sc, canonical_seed)
    return sc


def _spec(**kw) -> dict:
    base = dict(days=90, price_walk_pct=18.0, spend_walk_pct=20.0, sigma_obs=0.12,
                season_amp=0.10, promo_freq=0, promo_depth=0.0, drop_rate=0.0,
                obs_price_jitter_pct=0.0, trend_break=0.0, cost_drift=0.0, narrow_price=False)
    base.update(kw)
    return base


def _rev(rng, fam, i, ms, *, ael, amk, spec, cons=None, unc=None, kappa=1.0):
    p = _base_params_v2(rng)
    p["a_elast"] = round(ael, 4); p["a_mkt"] = round(amk, 4)
    _couple_system_B(p, rng, kappa=kappa)
    return _mk(fam, rng, i, ms, params=p, history_spec=spec, constraints=(cons or {}),
               kpi_objective="increase_revenue", kpi="revenue", sense="max",
               uncertainty=(unc or {"sigma_obs": spec["sigma_obs"], "a_elast": p["a_elast"]}),
               noise={"obs_noise_sd": spec["sigma_obs"], "missing_rate": spec["drop_rate"]})


def _prof(rng, fam, i, ms, *, ael, amk, spec, cons=None, unc=None, has_inv=False, kappa=1.0):
    p = _base_params_v2(rng)
    p["a_elast"] = round(ael, 4); p["a_mkt"] = round(amk, 4)
    _couple_system_B(p, rng, kappa=kappa)
    return _mk(fam, rng, i, ms, params=p, history_spec=spec, constraints=(cons or {}),
               kpi_objective="increase_profit", kpi="profit", sense="max", has_inventory=has_inv,
               uncertainty=(unc or {"sigma_obs": spec["sigma_obs"], "a_elast": p["a_elast"],
                                    "gross_margin": 1 - p["unit_cost"] / p["base_price"]}),
               noise={"obs_noise_sd": spec["sigma_obs"], "missing_rate": spec["drop_rate"]})


# ---- 22 families, grouped for the family-level partition -------------------- #
def _f_elastic_demand(r, i, m):        return _rev(r, F["elastic_demand"], i, m, ael=r.uniform(-2.6, -1.6), amk=r.uniform(0.12, 0.28), spec=_spec(price_walk_pct=r.uniform(14, 26)))
def _f_inelastic_demand(r, i, m):      return _rev(r, F["inelastic_demand"], i, m, ael=r.uniform(-0.55, -0.15), amk=r.uniform(0.10, 0.25), spec=_spec(price_walk_pct=r.uniform(12, 22)), cons={"price_floor_pct": -12.0, "price_ceiling_pct": 15.0})
def _f_unit_elastic(r, i, m):          return _rev(r, F["unit_elastic"], i, m, ael=r.uniform(-1.15, -0.85), amk=r.uniform(0.12, 0.30), spec=_spec(price_walk_pct=r.uniform(12, 24)))
def _f_high_marketing_response(r, i, m): return _rev(r, F["high_marketing_response"], i, m, ael=r.uniform(-1.7, -1.0), amk=r.uniform(0.32, 0.46), spec=_spec(spend_walk_pct=r.uniform(24, 40)))
def _f_low_marketing_response(r, i, m): return _rev(r, F["low_marketing_response"], i, m, ael=r.uniform(-2.1, -1.3), amk=r.uniform(0.03, 0.10), spec=_spec(spend_walk_pct=r.uniform(18, 30)))
def _f_inventory_bound(r, i, m):
    p = _base_params_v2(r); p["a_elast"] = round(r.uniform(-1.6, -0.8), 4); p["a_mkt"] = round(r.uniform(0.12, 0.30), 4)
    cap = round(p["base_demand"] * r.uniform(0.70, 0.95), 4); p["inventory_cap"] = cap
    _couple_system_B(p, r)
    return _mk(F["inventory_bound"], r, i, m, params=p, history_spec=_spec(),
              constraints={"inventory_cap": cap}, kpi_objective="reduce_inventory_risk",
              kpi="orders", sense="max", has_inventory=True,
              uncertainty={"inventory_cap_ratio": cap / p["base_demand"], "a_elast": p["a_elast"]},
              noise={"obs_noise_sd": 0.12, "missing_rate": 0.0})
def _f_capacity_bound(r, i, m):
    p = _base_params_v2(r); p["a_elast"] = round(r.uniform(-1.5, -0.7), 4); p["a_mkt"] = round(r.uniform(0.15, 0.35), 4)
    cap = round(p["base_demand"] * r.uniform(0.80, 1.00), 4); p["capacity_cap"] = cap
    _couple_system_B(p, r)
    return _mk(F["capacity_bound"], r, i, m, params=p, history_spec=_spec(),
              constraints={"capacity_cap": cap}, kpi_objective="increase_profit",
              kpi="profit", sense="max",
              uncertainty={"capacity_ratio": cap / p["base_demand"], "a_elast": p["a_elast"]},
              noise={"obs_noise_sd": 0.12, "missing_rate": 0.0})
def _f_cash_constrained(r, i, m):
    p = _base_params_v2(r); p["a_elast"] = round(r.uniform(-1.5, -0.8), 4); p["a_mkt"] = round(r.uniform(0.20, 0.40), 4)
    _couple_system_B(p, r)
    cap = round(p["marketing_base_spend"] * r.uniform(1.03, 1.15), 4)
    return _mk(F["cash_constrained"], r, i, m, params=p, history_spec=_spec(spend_walk_pct=r.uniform(20, 34)),
              constraints={"cash_cap": cap}, kpi_objective="increase_revenue", kpi="revenue", sense="max",
              uncertainty={"cash_headroom_pct": (cap / p["marketing_base_spend"] - 1) * 100, "a_elast": p["a_elast"]},
              noise={"obs_noise_sd": 0.12, "missing_rate": 0.0})
def _f_thin_margin_profit(r, i, m):
    p = _base_params_v2(r); p["unit_cost"] = round(p["base_price"] * r.uniform(0.84, 0.94), 4)
    p["a_elast"] = round(r.uniform(-1.6, -0.7), 4); p["a_mkt"] = round(r.uniform(0.12, 0.30), 4); _couple_system_B(p, r)
    return _mk(F["thin_margin_profit"], r, i, m, params=p, history_spec=_spec(),
              constraints={"price_floor_pct": -8.0, "price_ceiling_pct": 15.0},
              kpi_objective="increase_profit", kpi="profit", sense="max",
              uncertainty={"gross_margin": 1 - p["unit_cost"] / p["base_price"], "a_elast": p["a_elast"]},
              noise={"obs_noise_sd": 0.12, "missing_rate": 0.0})
def _f_fat_margin_profit(r, i, m):
    p = _base_params_v2(r); p["unit_cost"] = round(p["base_price"] * r.uniform(0.40, 0.55), 4)
    p["a_elast"] = round(r.uniform(-1.6, -0.7), 4); p["a_mkt"] = round(r.uniform(0.15, 0.35), 4); _couple_system_B(p, r)
    return _mk(F["fat_margin_profit"], r, i, m, params=p, history_spec=_spec(),
              constraints={}, kpi_objective="increase_profit", kpi="profit", sense="max",
              uncertainty={"gross_margin": 1 - p["unit_cost"] / p["base_price"], "a_elast": p["a_elast"]},
              noise={"obs_noise_sd": 0.12, "missing_rate": 0.0})
def _f_competing_objectives(r, i, m):
    p = _base_params_v2(r); p["unit_cost"] = round(p["base_price"] * r.uniform(0.80, 0.90), 4)
    p["a_elast"] = round(r.uniform(-1.9, -1.4), 4); p["a_mkt"] = round(r.uniform(0.15, 0.32), 4); _couple_system_B(p, r)
    return _mk(F["competing_objectives"], r, i, m, params=p, history_spec=_spec(price_walk_pct=r.uniform(12, 22)),
              constraints={"price_floor_pct": -12.0, "price_ceiling_pct": 15.0},
              kpi_objective="increase_profit", kpi="profit", sense="max",
              uncertainty={"gross_margin": 1 - p["unit_cost"] / p["base_price"], "a_elast": p["a_elast"],
                           "objective_conflict_by_design": True},
              noise={"obs_noise_sd": 0.12, "missing_rate": 0.0})
def _f_asymmetric_risk(r, i, m):
    return _rev(r, F["asymmetric_risk"], i, m, ael=r.uniform(-0.5, -0.2), amk=r.uniform(0.10, 0.25),
               spec=_spec(price_walk_pct=r.uniform(3.0, 6.0), narrow_price=True, sigma_obs=0.08),
               cons={"price_floor_pct": -10.0, "price_ceiling_pct": 15.0},
               unc={"a_elast": None, "narrow_price_history": True, "adversarial_to_risk_heuristic": True})
def _f_delayed_effects(r, i, m):
    return _rev(r, F["delayed_effects"], i, m, ael=r.uniform(-2.0, -1.3), amk=r.uniform(0.20, 0.38),
               spec=_spec(spend_walk_pct=r.uniform(22, 36)), kappa=r.uniform(0.25, 0.5),
               unc={"kappa_horizon_decay": True, "a_elast": None})
def _f_high_volatility(r, i, m):
    return _prof(r, F["high_volatility"], i, m, ael=r.uniform(-2.2, -1.4), amk=r.uniform(0.14, 0.30),
                spec=_spec(sigma_obs=r.uniform(0.30, 0.40), price_walk_pct=r.uniform(30, 45)),
                cons={"price_floor_pct": -20.0, "price_ceiling_pct": 20.0},
                unc={"stress": True, "sigma_obs_high": True})
def _f_low_volatility(r, i, m):
    return _rev(r, F["low_volatility"], i, m, ael=r.uniform(-1.9, -1.2), amk=r.uniform(0.12, 0.28),
               spec=_spec(sigma_obs=r.uniform(0.04, 0.08)))
def _f_seasonal_strong(r, i, m):
    return _rev(r, F["seasonal_strong"], i, m, ael=r.uniform(-1.9, -1.2), amk=r.uniform(0.14, 0.30),
               spec=_spec(season_amp=r.uniform(0.25, 0.40)))
def _f_noisy_observations(r, i, m):
    return _rev(r, F["noisy_observations"], i, m, ael=r.uniform(-1.6, -0.7), amk=r.uniform(0.12, 0.28),
               spec=_spec(sigma_obs=r.uniform(0.28, 0.38), obs_price_jitter_pct=r.uniform(3, 8)),
               unc={"observation_noise": True, "sigma_obs": None})
def _f_missing_observations(r, i, m):
    dr = round(r.uniform(0.25, 0.45), 4)
    return _rev(r, F["missing_observations"], i, m, ael=r.uniform(-1.7, -0.6), amk=r.uniform(0.12, 0.28),
               spec=_spec(drop_rate=dr), unc={"missing_rate": dr})
def _f_low_data(r, i, m):
    days = int(r.choice([36, 40, 44, 48]))
    return _rev(r, F["low_data"], i, m, ael=r.uniform(-1.7, -0.6), amk=r.uniform(0.12, 0.28),
               spec=_spec(days=days), unc={"history_days": days, "data_constrained": True})
def _f_conflicting_signals(r, i, m):
    return _rev(r, F["conflicting_signals"], i, m, ael=r.uniform(-2.4, -1.6), amk=r.uniform(0.12, 0.28),
               spec=_spec(trend_break=r.uniform(0.25, 0.45), price_walk_pct=r.uniform(12, 22)),
               cons={"price_floor_pct": -12.0, "price_ceiling_pct": 12.0},
               unc={"recent_uptrend_vs_elastic": True, "a_elast": None})
def _f_promotion_decision(r, i, m):
    return _rev(r, F["promotion_decision"], i, m, ael=r.uniform(-2.6, -1.8), amk=r.uniform(0.12, 0.26),
               spec=_spec(price_walk_pct=r.uniform(10, 20), promo_freq=14, promo_depth=r.uniform(0.08, 0.16)),
               cons={"price_floor_pct": -25.0, "price_ceiling_pct": 12.0},
               unc={"deep_cut_optimal": True, "a_elast": None})
def _f_supplier_shock(r, i, m):
    p = _base_params_v2(r); p["unit_cost"] = round(p["base_price"] * r.uniform(0.70, 0.85), 4)
    p["a_elast"] = round(r.uniform(-1.6, -0.8), 4); p["a_mkt"] = round(r.uniform(0.12, 0.28), 4); _couple_system_B(p, r)
    drift = round(r.uniform(0.10, 0.25), 4)
    # cost erosion: raise unit_cost by drift (System B sees the shocked cost)
    p["unit_cost"] = round(p["unit_cost"] * (1 + drift), 4)
    return _mk(F["supplier_shock"], r, i, m, params=p, history_spec=_spec(cost_drift=drift),
              constraints={"price_floor_pct": -8.0, "price_ceiling_pct": 18.0},
              kpi_objective="increase_profit", kpi="profit", sense="max",
              uncertainty={"cost_shock": drift, "gross_margin": 1 - p["unit_cost"] / p["base_price"], "a_elast": p["a_elast"]},
              noise={"obs_noise_sd": 0.12, "missing_rate": 0.0})


F: dict[str, FamilySpecV2] = {}
_DEFS = [
    ("elastic_demand", "Elastic demand", "Strong price elasticity; revenue.", 0, _f_elastic_demand),
    ("inelastic_demand", "Inelastic demand", "Weak price elasticity; revenue; price-band constraint.", 0, _f_inelastic_demand),
    ("unit_elastic", "Near unit-elastic", "Elasticity near -1 (knife-edge); revenue.", 0, _f_unit_elastic),
    ("high_marketing_response", "High marketing response", "Large marketing exponent; wide spend history.", 1, _f_high_marketing_response),
    ("low_marketing_response", "Low marketing response", "Small marketing exponent; spend nearly inert.", 1, _f_low_marketing_response),
    ("inventory_bound", "Inventory-bound", "Stock cap below demand; orders objective.", 2, _f_inventory_bound),
    ("capacity_bound", "Capacity-bound", "Production cap near demand; profit objective.", 2, _f_capacity_bound),
    ("cash_constrained", "Cash-constrained", "Marketing budget marginally above status quo.", 2, _f_cash_constrained),
    ("thin_margin_profit", "Thin-margin profit", "Gross margin 6-16%; profit objective.", 3, _f_thin_margin_profit),
    ("fat_margin_profit", "Fat-margin profit", "Gross margin 45-60%; profit objective.", 3, _f_fat_margin_profit),
    ("competing_objectives", "Competing objectives", "Revenue-optimal != profit-optimal; objective is profit.", 3, _f_competing_objectives),
    ("asymmetric_risk", "Asymmetric risk", "Inelastic (price rise best) + narrow price history.", 4, _f_asymmetric_risk),
    ("delayed_effects", "Delayed effects", "System-B marketing effect only partly realised in-horizon.", 4, _f_delayed_effects),
    ("high_volatility", "High volatility", "Large log-normal noise + wide price walk; profit.", 5, _f_high_volatility),
    ("low_volatility", "Low volatility", "Very small observation noise; revenue.", 5, _f_low_volatility),
    ("seasonal_strong", "Strong seasonality", "Large weekly seasonal amplitude; revenue.", 5, _f_seasonal_strong),
    ("noisy_observations", "Noisy observations", "High obs noise + price jitter; clean System-B truth.", 6, _f_noisy_observations),
    ("missing_observations", "Missing observations", "25-45% of history days dropped.", 6, _f_missing_observations),
    ("low_data", "Low data", "36-48 days of history (above the 35-day pipeline minimum).", 6, _f_low_data),
    ("conflicting_signals", "Conflicting signals", "Recent demand uptrend but strongly elastic.", 7, _f_conflicting_signals),
    ("promotion_decision", "Promotion decision", "Strongly elastic; deep price cut optimal; -25% floor.", 7, _f_promotion_decision),
    ("supplier_shock", "Supplier cost shock", "Unit cost shocked up 10-25%; profit objective.", 7, _f_supplier_shock),
]
for _fid, _lab, _desc, _grp, _fn in _DEFS:
    F[_fid] = FamilySpecV2(_fid, _lab, _desc, _grp, _fn)

FAMILIES_V2 = F
FAMILY_IDS_V2 = list(F.keys())
assert len(FAMILY_IDS_V2) >= 20, f"need >= 20 families, have {len(FAMILY_IDS_V2)}"
MAX_SUPPORTED_INSTANCES = 100_000


def generate_suite(n: int, master_seed: int, families: list[str] | None = None) -> list[EvalScenarioV2]:
    fam_ids = families or FAMILY_IDS_V2
    if n < len(fam_ids):
        raise ValueError(f"n ({n}) must be >= number of families ({len(fam_ids)})")
    if n > MAX_SUPPORTED_INSTANCES:
        raise ValueError("n exceeds MAX_SUPPORTED_INSTANCES")
    out: list[EvalScenarioV2] = []
    per: dict[str, int] = {f: 0 for f in fam_ids}
    for k in range(n):
        fid = fam_ids[k % len(fam_ids)]
        idx = per[fid]; per[fid] += 1
        rng = random.Random(f"{master_seed}:{GENERATOR_VERSION}:{fid}:{idx}")
        out.append(F[fid].builder(rng, idx, master_seed))
    return out


def partition_families(master_seed: int, families: list[str] | None = None) -> dict[str, list[str]]:
    """Deterministic **stratified round-robin** family-level holdout.

    Families are ordered by structural super-group (``partition_group``), then
    shuffled within each group by a fixed seed, then walked with the repeating
    pattern ``[dev, dev, val, dev, locked]`` (≈ 60/20/20). Because the walk runs
    over the group-ordered list, the validation and locked families are drawn
    from *different* structural super-groups rather than depending on a lucky
    single shuffle (this directly addresses the V1 audit's "locked test covers
    only a few structural regimes"). No family appears in two partitions.
    Chosen and fixed at design time; independent of any outcome.
    """
    fam_ids = families or FAMILY_IDS_V2
    groups: dict[int, list[str]] = {}
    for fid in fam_ids:
        groups.setdefault(F[fid].partition_group, []).append(fid)
    ordered: list[str] = []
    for g in sorted(groups):
        gl = sorted(groups[g])
        random.Random(f"{master_seed}:family_partition_v2:{g}").shuffle(gl)
        ordered.extend(gl)
    pattern = ["development", "development", "validation", "locked_test"]
    parts: dict[str, list[str]] = {"development": [], "validation": [], "locked_test": []}
    for i, fid in enumerate(ordered):
        parts[pattern[i % len(pattern)]].append(fid)
    for k in parts:
        parts[k] = sorted(parts[k])
    allf = parts["development"] + parts["validation"] + parts["locked_test"]
    assert sorted(allf) == sorted(fam_ids) and len(set(allf)) == len(allf)
    assert all(parts[k] for k in parts), parts
    return parts


def assign_partitions(scenarios: list[EvalScenarioV2], pmap: dict[str, list[str]]) -> None:
    lut = {fid: part for part, fids in pmap.items() for fid in fids}
    for s in scenarios:
        s.partition = lut.get(s.family_id, "unassigned")


def suite_checksum(scenarios: list[EvalScenarioV2]) -> str:
    h = hashlib.sha256()
    for s in sorted(scenarios, key=lambda x: x.scenario_id):
        h.update(s.content_hash().encode())
    return h.hexdigest()
