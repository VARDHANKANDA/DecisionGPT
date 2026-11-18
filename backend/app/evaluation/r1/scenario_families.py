"""R1 scenario environment — 26 structurally distinct action-responsive families.

Built on the **verified** V2 System-A history engine
(``scenario_families_v2._history_v2`` / ``_base_params_v2`` / ``_couple_system_B``)
— demand responds to historical price and marketing via a log-linear power law,
with identifiable variation (V2 pre-lock diagnostic: median OLS elasticity
recovery error ≈ 0.10). The exogenous scorer remains ``app.evaluation.ground_truth``
("System B", additive-linear, unchanged, independent).

Each of the 26 families is a distinct decision mechanism (Section 9 list), not a
cosmetic label: elasticity regime, marketing-response regime, asymmetric
lever elasticity, competing objectives, asymmetric risk, inventory / capacity /
budget binding, delayed marketing / price effects, seasonality strength (3
levels), conflicting signals, observation degradation (noisy / missing / sparse),
demand saturation, diminishing marketing returns, promotion threshold, high /
low uncertainty, interacting constraints, regime shift, nonlinear response.

PURE: stdlib + numpy. No production / pipeline / ground_truth import.
"""
from __future__ import annotations

import hashlib
import math
import random
from dataclasses import dataclass
from typing import Callable

import numpy as np

from app.evaluation.scenario_families import NOOP, production_candidate_actions
from app.evaluation.scenario_families_v2 import (
    EvalScenarioV2, _STD_PERTURBATIONS, _base_params_v2, _couple_system_B, _history_v2,
)

GENERATOR_VERSION = "r1_eval_scenarios_v1"
ENV_VERSION = "system_A_action_responsive_v1"   # same verified engine as V2


class EvalScenarioR1(EvalScenarioV2):
    """Identical shape to EvalScenarioV2; distinct id prefix + generator stamp."""

    def content_hash(self) -> str:  # re-stamp with the R1 generator version
        import json
        payload = {
            "generator_version": GENERATOR_VERSION, "env_version": ENV_VERSION,
            "family_id": self.family_id, "seed": self.seed, "master_seed": self.master_seed,
            "params": self.params, "history_spec": self.history_spec,
            "reference_history": self.reference_history, "constraints": self.constraints,
            "objective": self.objective,
            "feasible_actions": [[dict(x) for x in a] for a in self.feasible_actions],
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()

    @staticmethod
    def from_dict(d: dict) -> "EvalScenarioR1":
        def _acts(seq):
            return [tuple(dict(x) for x in a) for a in seq]
        sc = EvalScenarioR1(
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


def realise_history(scenario, seed: int) -> dict:
    """Per-(scenario, seed) history via the verified V2 System-A engine."""
    h = hashlib.sha256(f"{scenario.scenario_id}:{seed}:{GENERATOR_VERSION}".encode()).hexdigest()
    rng = np.random.default_rng(int(h[:16], 16))
    return _history_v2(rng, scenario.params, **dict(scenario.history_spec))


# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class FamilySpecR1:
    family_id: str
    label: str
    description: str
    group: int
    builder: Callable


def _spec(**kw) -> dict:
    base = dict(days=90, price_walk_pct=18.0, spend_walk_pct=22.0, sigma_obs=0.12,
                season_amp=0.10, promo_freq=0, promo_depth=0.0, drop_rate=0.0,
                obs_price_jitter_pct=0.0, trend_break=0.0, cost_drift=0.0, narrow_price=False)
    base.update(kw)
    return base


def _mk(fam: FamilySpecR1, rng: random.Random, idx: int, ms: int, *, params: dict,
        history_spec: dict, constraints: dict, kpi_objective: str, kpi: str, sense: str,
        has_inventory: bool = False, uncertainty: dict, noise: dict) -> EvalScenarioR1:
    roi_pos = kpi_objective == "increase_profit"
    feasible = production_candidate_actions(kpi_objective, marketing_roi_positive=roi_pos,
                                            has_inventory=has_inventory)
    canonical = 60_000 + idx
    sc = EvalScenarioR1(
        scenario_id=f"r1_{fam.family_id}__{idx:04d}",
        family_id=fam.family_id, family_label=fam.label, family_description=fam.description,
        seed=canonical, master_seed=ms, partition="unassigned",
        params=params, history_spec=history_spec, reference_history={},
        constraints=constraints, objective={"kpi": kpi, "sense": sense},
        feasible_actions=feasible, eval_reference_actions=feasible + [NOOP],
        uncertainty=uncertainty, noise=noise,
        perturbation_config={"supported": dict(_STD_PERTURBATIONS)},
        provenance={"generator_version": GENERATOR_VERSION, "env_version": ENV_VERSION,
                    "family_id": fam.family_id, "family_index": idx, "master_seed": ms,
                    "goal_objective": kpi_objective, "marketing_roi_positive": roi_pos,
                    "system_A": "power-law demand response to historical price & marketing (verified V2 engine)",
                    "system_B": "ground_truth.exogenous_objective_v1 (unchanged, additive-linear)",
                    "AB_coupling": "eps ~ a_elast + N(0,.35); mr ~ f(a_mkt)·(1+N(0,.25))"},
    )
    sc.reference_history = realise_history(sc, canonical)
    return sc


def _rev(rng, fam, i, ms, *, ael, amk, spec, cons=None, unc=None, kappa=1.0):
    p = _base_params_v2(rng); p["a_elast"] = round(ael, 4); p["a_mkt"] = round(amk, 4)
    _couple_system_B(p, rng, kappa=kappa)
    return _mk(fam, rng, i, ms, params=p, history_spec=spec, constraints=(cons or {}),
               kpi_objective="increase_revenue", kpi="revenue", sense="max",
               uncertainty=(unc or {"a_elast": p["a_elast"], "sigma_obs": spec["sigma_obs"]}),
               noise={"obs_noise_sd": spec["sigma_obs"], "missing_rate": spec["drop_rate"]})


def _prof(rng, fam, i, ms, *, ael, amk, spec, cons=None, unc=None, has_inv=False, kappa=1.0):
    p = _base_params_v2(rng); p["a_elast"] = round(ael, 4); p["a_mkt"] = round(amk, 4)
    _couple_system_B(p, rng, kappa=kappa)
    return _mk(fam, rng, i, ms, params=p, history_spec=spec, constraints=(cons or {}),
               kpi_objective="increase_profit", kpi="profit", sense="max", has_inventory=has_inv,
               uncertainty=(unc or {"a_elast": p["a_elast"], "gross_margin": 1 - p["unit_cost"] / p["base_price"]}),
               noise={"obs_noise_sd": spec["sigma_obs"], "missing_rate": spec["drop_rate"]})


# ---- 26 families ---------------------------------------------------------- #
def _f_price_elastic(r, i, m):        return _rev(r, F["price_elastic"], i, m, ael=r.uniform(-2.6, -1.7), amk=r.uniform(0.12, 0.24), spec=_spec(price_walk_pct=r.uniform(16, 28)))
def _f_price_inelastic(r, i, m):      return _rev(r, F["price_inelastic"], i, m, ael=r.uniform(-0.55, -0.15), amk=r.uniform(0.12, 0.24), spec=_spec(price_walk_pct=r.uniform(14, 24)), cons={"price_floor_pct": -12.0, "price_ceiling_pct": 15.0})
def _f_strong_marketing(r, i, m):     return _rev(r, F["strong_marketing"], i, m, ael=r.uniform(-1.6, -0.9), amk=r.uniform(0.36, 0.50), spec=_spec(spend_walk_pct=r.uniform(28, 44)))
def _f_weak_marketing(r, i, m):       return _rev(r, F["weak_marketing"], i, m, ael=r.uniform(-2.1, -1.3), amk=r.uniform(0.02, 0.08), spec=_spec(spend_walk_pct=r.uniform(20, 32)))
def _f_asym_price_marketing(r, i, m): return _rev(r, F["asym_price_marketing"], i, m, ael=r.uniform(-0.7, -0.35), amk=r.uniform(0.34, 0.48), spec=_spec(price_walk_pct=r.uniform(14, 24), spend_walk_pct=r.uniform(26, 40)))
def _f_competing_objectives(r, i, m):
    p = _base_params_v2(r); p["unit_cost"] = round(p["base_price"] * r.uniform(0.80, 0.90), 4)
    p["a_elast"] = round(r.uniform(-1.9, -1.4), 4); p["a_mkt"] = round(r.uniform(0.15, 0.30), 4); _couple_system_B(p, r)
    return _mk(F["competing_objectives"], r, i, m, params=p, history_spec=_spec(price_walk_pct=r.uniform(12, 22)),
              constraints={"price_floor_pct": -12.0, "price_ceiling_pct": 15.0},
              kpi_objective="increase_profit", kpi="profit", sense="max",
              uncertainty={"gross_margin": 1 - p["unit_cost"] / p["base_price"], "a_elast": p["a_elast"], "objective_conflict_by_design": True},
              noise={"obs_noise_sd": 0.12, "missing_rate": 0.0})
def _f_asymmetric_risk(r, i, m):
    return _rev(r, F["asymmetric_risk"], i, m, ael=r.uniform(-0.5, -0.2), amk=r.uniform(0.10, 0.22),
               spec=_spec(price_walk_pct=r.uniform(3.0, 6.0), narrow_price=True, sigma_obs=0.08),
               cons={"price_floor_pct": -10.0, "price_ceiling_pct": 15.0},
               unc={"narrow_price_history": True, "adversarial_to_risk_heuristic": True})
def _f_inventory_bound(r, i, m):
    p = _base_params_v2(r); p["a_elast"] = round(r.uniform(-1.6, -0.8), 4); p["a_mkt"] = round(r.uniform(0.14, 0.30), 4)
    cap = round(p["base_demand"] * r.uniform(0.70, 0.95), 4); p["inventory_cap"] = cap; _couple_system_B(p, r)
    return _mk(F["inventory_bound"], r, i, m, params=p, history_spec=_spec(),
              constraints={"inventory_cap": cap}, kpi_objective="reduce_inventory_risk", kpi="orders", sense="max",
              has_inventory=True, uncertainty={"inventory_cap_ratio": cap / p["base_demand"], "a_elast": p["a_elast"]},
              noise={"obs_noise_sd": 0.12, "missing_rate": 0.0})
def _f_capacity_bound(r, i, m):
    p = _base_params_v2(r); p["a_elast"] = round(r.uniform(-1.5, -0.7), 4); p["a_mkt"] = round(r.uniform(0.16, 0.34), 4)
    cap = round(p["base_demand"] * r.uniform(0.80, 1.00), 4); p["capacity_cap"] = cap; _couple_system_B(p, r)
    return _mk(F["capacity_bound"], r, i, m, params=p, history_spec=_spec(),
              constraints={"capacity_cap": cap}, kpi_objective="increase_profit", kpi="profit", sense="max",
              uncertainty={"capacity_ratio": cap / p["base_demand"], "a_elast": p["a_elast"]},
              noise={"obs_noise_sd": 0.12, "missing_rate": 0.0})
def _f_budget_bound(r, i, m):
    p = _base_params_v2(r); p["a_elast"] = round(r.uniform(-1.5, -0.8), 4); p["a_mkt"] = round(r.uniform(0.24, 0.42), 4); _couple_system_B(p, r)
    cap = round(p["marketing_base_spend"] * r.uniform(1.03, 1.14), 4)
    return _mk(F["budget_bound"], r, i, m, params=p, history_spec=_spec(spend_walk_pct=r.uniform(22, 36)),
              constraints={"cash_cap": cap}, kpi_objective="increase_revenue", kpi="revenue", sense="max",
              uncertainty={"cash_headroom_pct": (cap / p["marketing_base_spend"] - 1) * 100, "a_elast": p["a_elast"]},
              noise={"obs_noise_sd": 0.12, "missing_rate": 0.0})
def _f_delayed_marketing(r, i, m):   return _rev(r, F["delayed_marketing"], i, m, ael=r.uniform(-1.9, -1.2), amk=r.uniform(0.24, 0.40), spec=_spec(spend_walk_pct=r.uniform(24, 38)), kappa=r.uniform(0.25, 0.5), unc={"kappa_horizon_decay": True, "a_elast": None})
def _f_delayed_price(r, i, m):       return _rev(r, F["delayed_price"], i, m, ael=r.uniform(-2.2, -1.4), amk=r.uniform(0.12, 0.24), spec=_spec(price_walk_pct=r.uniform(14, 24), trend_break=r.uniform(-0.2, -0.08)), unc={"lagged_price_effect_proxy": True, "a_elast": None})
def _f_seasonal_demand(r, i, m):     return _rev(r, F["seasonal_demand"], i, m, ael=r.uniform(-1.7, -1.0), amk=r.uniform(0.14, 0.28), spec=_spec(season_amp=r.uniform(0.14, 0.22)))
def _f_strong_seasonality(r, i, m):  return _rev(r, F["strong_seasonality"], i, m, ael=r.uniform(-1.7, -1.0), amk=r.uniform(0.14, 0.28), spec=_spec(season_amp=r.uniform(0.30, 0.42)))
def _f_weak_seasonality(r, i, m):    return _rev(r, F["weak_seasonality"], i, m, ael=r.uniform(-1.9, -1.1), amk=r.uniform(0.14, 0.28), spec=_spec(season_amp=r.uniform(0.02, 0.06)))
def _f_conflicting_signals(r, i, m): return _rev(r, F["conflicting_signals"], i, m, ael=r.uniform(-2.4, -1.6), amk=r.uniform(0.12, 0.26), spec=_spec(trend_break=r.uniform(0.25, 0.45), price_walk_pct=r.uniform(12, 22)), cons={"price_floor_pct": -12.0, "price_ceiling_pct": 12.0}, unc={"recent_uptrend_vs_elastic": True, "a_elast": None})
def _f_noisy_observations(r, i, m):  return _rev(r, F["noisy_observations"], i, m, ael=r.uniform(-1.7, -0.9), amk=r.uniform(0.14, 0.28), spec=_spec(sigma_obs=r.uniform(0.28, 0.40), obs_price_jitter_pct=r.uniform(3, 9)), unc={"observation_noise": True})
def _f_missing_observations(r, i, m):
    dr = round(r.uniform(0.25, 0.45), 4)
    return _rev(r, F["missing_observations"], i, m, ael=r.uniform(-1.9, -0.9), amk=r.uniform(0.14, 0.28), spec=_spec(drop_rate=dr), unc={"missing_rate": dr})
def _f_sparse_history(r, i, m):
    days = int(r.choice([36, 40, 44, 48, 52]))
    return _rev(r, F["sparse_history"], i, m, ael=r.uniform(-1.9, -0.9), amk=r.uniform(0.14, 0.28), spec=_spec(days=days), unc={"history_days": days, "data_constrained": True})
def _f_demand_saturation(r, i, m):
    p = _base_params_v2(r); p["a_elast"] = round(r.uniform(-1.4, -0.8), 4); p["a_mkt"] = round(r.uniform(0.16, 0.30), 4)
    cap = round(p["base_demand"] * r.uniform(1.00, 1.10), 4); p["capacity_cap"] = cap; _couple_system_B(p, r)
    return _mk(F["demand_saturation"], r, i, m, params=p, history_spec=_spec(),
              constraints={"capacity_cap": cap}, kpi_objective="increase_revenue", kpi="revenue", sense="max",
              uncertainty={"saturation_ratio": cap / p["base_demand"], "a_elast": p["a_elast"]},
              noise={"obs_noise_sd": 0.12, "missing_rate": 0.0})
def _f_diminishing_marketing(r, i, m): return _rev(r, F["diminishing_marketing"], i, m, ael=r.uniform(-1.7, -1.0), amk=r.uniform(0.05, 0.12), spec=_spec(spend_walk_pct=r.uniform(26, 40)), unc={"diminishing_returns": True})
def _f_promotion_threshold(r, i, m): return _rev(r, F["promotion_threshold"], i, m, ael=r.uniform(-2.7, -1.9), amk=r.uniform(0.12, 0.24), spec=_spec(price_walk_pct=r.uniform(10, 20), promo_freq=14, promo_depth=r.uniform(0.10, 0.18)), cons={"price_floor_pct": -25.0, "price_ceiling_pct": 12.0}, unc={"deep_cut_optimal": True, "a_elast": None})
def _f_high_uncertainty(r, i, m):    return _prof(r, F["high_uncertainty"], i, m, ael=r.uniform(-2.2, -1.3), amk=r.uniform(0.14, 0.28), spec=_spec(sigma_obs=r.uniform(0.32, 0.44), price_walk_pct=r.uniform(28, 42)), cons={"price_floor_pct": -20.0, "price_ceiling_pct": 20.0}, unc={"stress": True, "sigma_obs_high": True})
def _f_low_uncertainty(r, i, m):     return _rev(r, F["low_uncertainty"], i, m, ael=r.uniform(-1.9, -1.1), amk=r.uniform(0.14, 0.28), spec=_spec(sigma_obs=r.uniform(0.03, 0.06)))
def _f_interacting_constraints(r, i, m):
    p = _base_params_v2(r); p["a_elast"] = round(r.uniform(-1.6, -0.9), 4); p["a_mkt"] = round(r.uniform(0.20, 0.36), 4)
    inv = round(p["base_demand"] * r.uniform(0.75, 0.95), 4); p["inventory_cap"] = inv; _couple_system_B(p, r)
    cash = round(p["marketing_base_spend"] * r.uniform(1.04, 1.12), 4)
    return _mk(F["interacting_constraints"], r, i, m, params=p, history_spec=_spec(),
              constraints={"inventory_cap": inv, "cash_cap": cash}, kpi_objective="reduce_inventory_risk",
              kpi="orders", sense="max", has_inventory=True,
              uncertainty={"inventory_cap_ratio": inv / p["base_demand"], "both_constraints_bind": True, "a_elast": p["a_elast"]},
              noise={"obs_noise_sd": 0.12, "missing_rate": 0.0})
def _f_regime_shift(r, i, m):        return _rev(r, F["regime_shift"], i, m, ael=r.uniform(-2.2, -1.2), amk=r.uniform(0.14, 0.28), spec=_spec(trend_break=r.uniform(0.20, 0.40), price_walk_pct=r.uniform(14, 24)), unc={"mid_series_regime_break": True, "a_elast": None})
def _f_nonlinear_response(r, i, m):
    p = _base_params_v2(r); p["a_elast"] = round(r.uniform(-2.6, -1.8), 4); p["a_mkt"] = round(r.uniform(0.16, 0.30), 4)
    cap = round(p["base_demand"] * r.uniform(1.00, 1.08), 4); p["capacity_cap"] = cap; _couple_system_B(p, r)
    return _mk(F["nonlinear_response"], r, i, m, params=p, history_spec=_spec(price_walk_pct=r.uniform(18, 30)),
              constraints={"capacity_cap": cap}, kpi_objective="increase_revenue", kpi="revenue", sense="max",
              uncertainty={"strong_elasticity_plus_saturation": True, "a_elast": p["a_elast"]},
              noise={"obs_noise_sd": 0.12, "missing_rate": 0.0})


_DEFS = [
    ("price_elastic", "Price-elastic demand", "Strong negative price elasticity; revenue.", 0, _f_price_elastic),
    ("price_inelastic", "Price-inelastic demand", "Weak price elasticity; a price rise is optimal.", 0, _f_price_inelastic),
    ("strong_marketing", "Strong marketing response", "Large marketing exponent; wide spend history.", 1, _f_strong_marketing),
    ("weak_marketing", "Weak marketing response", "Marketing exponent near zero; price is the lever.", 1, _f_weak_marketing),
    ("asym_price_marketing", "Asymmetric lever elasticity", "Inelastic to price, elastic to marketing.", 1, _f_asym_price_marketing),
    ("competing_objectives", "Competing objectives", "Revenue-optimal != profit-optimal; objective is profit.", 2, _f_competing_objectives),
    ("asymmetric_risk", "Asymmetric risk", "Inelastic (price rise best) but narrow price history.", 2, _f_asymmetric_risk),
    ("inventory_bound", "Inventory-bound", "Stock cap below demand; orders objective.", 3, _f_inventory_bound),
    ("capacity_bound", "Capacity-bound", "Production cap near demand; profit objective.", 3, _f_capacity_bound),
    ("budget_bound", "Budget-constrained", "Marketing budget marginally above status quo.", 3, _f_budget_bound),
    ("delayed_marketing", "Delayed marketing effects", "System-B marketing effect only partly realised in-horizon.", 4, _f_delayed_marketing),
    ("delayed_price", "Delayed price effects", "History shows a slow demand decay after prior price moves.", 4, _f_delayed_price),
    ("seasonal_demand", "Seasonal demand", "Moderate weekly seasonal amplitude.", 5, _f_seasonal_demand),
    ("strong_seasonality", "Strong seasonality", "Large weekly seasonal amplitude.", 5, _f_strong_seasonality),
    ("weak_seasonality", "Weak seasonality", "Near-flat seasonality.", 5, _f_weak_seasonality),
    ("conflicting_signals", "Conflicting signals", "Recent demand uptrend but strongly elastic.", 6, _f_conflicting_signals),
    ("noisy_observations", "Noisy observations", "High observation noise + price jitter.", 6, _f_noisy_observations),
    ("missing_observations", "Missing observations", "25-45% of history days dropped.", 6, _f_missing_observations),
    ("sparse_history", "Sparse history", "36-52 days of history (above the 35-day pipeline minimum).", 6, _f_sparse_history),
    ("demand_saturation", "Demand saturation", "Capacity ceiling just above current demand.", 7, _f_demand_saturation),
    ("diminishing_marketing", "Diminishing marketing returns", "Very concave marketing response.", 7, _f_diminishing_marketing),
    ("promotion_threshold", "Promotion threshold", "Strongly elastic; deep price cut optimal; -25% floor.", 7, _f_promotion_threshold),
    ("high_uncertainty", "High uncertainty", "Large log-normal noise + wide price walk; profit.", 8, _f_high_uncertainty),
    ("low_uncertainty", "Low uncertainty", "Very small observation noise; clean signal.", 8, _f_low_uncertainty),
    ("interacting_constraints", "Interacting constraints", "Inventory and cash both bind.", 8, _f_interacting_constraints),
    ("regime_shift", "Regime shift", "Mid-series structural break in demand level.", 9, _f_regime_shift),
    ("nonlinear_response", "Nonlinear response", "Strong elasticity plus a saturation ceiling.", 9, _f_nonlinear_response),
]
F: dict[str, FamilySpecR1] = {fid: FamilySpecR1(fid, lab, desc, grp, fn) for fid, lab, desc, grp, fn in _DEFS}
FAMILY_IDS = list(F.keys())
assert len(FAMILY_IDS) >= 24, f"need >= 24 families, have {len(FAMILY_IDS)}"
MAX_SUPPORTED_INSTANCES = 100_000


def generate_suite(n: int, master_seed: int, families: list[str] | None = None) -> list[EvalScenarioR1]:
    fam_ids = families or FAMILY_IDS
    if n < len(fam_ids):
        raise ValueError(f"n ({n}) must be >= number of families ({len(fam_ids)})")
    out: list[EvalScenarioR1] = []
    per: dict[str, int] = {f: 0 for f in fam_ids}
    for k in range(n):
        fid = fam_ids[k % len(fam_ids)]
        idx = per[fid]; per[fid] += 1
        rng = random.Random(f"{master_seed}:{GENERATOR_VERSION}:{fid}:{idx}")
        out.append(F[fid].builder(rng, idx, master_seed))
    return out


def partition_families(master_seed: int, families: list[str] | None = None) -> dict[str, list[str]]:
    """Deterministic **stratified round-robin** family-level holdout, pattern
    ``[locked, dev, dev, val, locked, locked, dev]`` walked over the
    group-ordered (shuffled-within-group) family list. Locked-heavy on purpose:
    the R1 development-stage pilot showed a large between-scenario SD for the
    D_vs_B paired difference (~0.31), so the locked partition must be large to
    reach the pre-registered planned power at MEI = 0.05 (docs/R1_PREREGISTRATION.md
    §9 / power_analysis.json). Ratio is fixed at design time from the *variance
    magnitude* only (Section 12 permits development-stage information); no family
    is placed by its outcome. Gives ≈ 12 locked, ≈ 4 validation, ≈ 11 development
    families across all 10 structural super-groups."""
    fam_ids = families or FAMILY_IDS
    groups: dict[int, list[str]] = {}
    for f in fam_ids:
        groups.setdefault(F[f].group, []).append(f)
    ordered: list[str] = []
    for g in sorted(groups):
        gl = sorted(groups[g])
        random.Random(f"{master_seed}:r1_family_partition_v1:{g}").shuffle(gl)
        ordered.extend(gl)
    pattern = ["locked_test", "development", "development", "validation",
               "locked_test", "locked_test", "development"]
    parts: dict[str, list[str]] = {"development": [], "validation": [], "locked_test": []}
    for i, f in enumerate(ordered):
        parts[pattern[i % len(pattern)]].append(f)
    for k in parts:
        parts[k] = sorted(parts[k])
    allf = parts["development"] + parts["validation"] + parts["locked_test"]
    assert sorted(allf) == sorted(fam_ids) and len(set(allf)) == len(allf)
    assert all(parts[k] for k in parts), parts
    return parts


def assign_partitions(scenarios, pmap: dict[str, list[str]]) -> None:
    lut = {f: part for part, fs in pmap.items() for f in fs}
    for s in scenarios:
        s.partition = lut.get(s.family_id, "unassigned")


def suite_checksum(scenarios) -> str:
    h = hashlib.sha256()
    for s in sorted(scenarios, key=lambda x: x.scenario_id):
        h.update(s.content_hash().encode())
    return h.hexdigest()
