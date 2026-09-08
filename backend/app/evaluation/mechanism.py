"""Scenario-property extraction and component-interaction analysis.

PURE: stdlib + numpy only. No production dependency. ``ground_truth`` is used for
the closed-form objective (that module is itself pipeline-independent).

Purpose (Phase 12): move beyond "component X changed the score" toward
"component X helps under conditions Y and hurts under conditions Z", using the
CONTROLLED design only. This is a *component-level effect under controlled
simulation* analysis; it is NOT causal inference about real businesses and must
never be described as such.

For each scenario we extract interpretable factors:
  * uncertainty            (scenario-declared demand / price noise)
  * constraint_tightness   (how binding the tightest constraint is at status quo, 0..1)
  * objective_conflict     (Spearman-style disagreement between the revenue-optimal
                            and the scenario-objective-optimal action rankings)
  * prediction_error       (|Digital-Twin projection - ground truth| for a reference
                            action; filled post-run by the harness)
  * risk_exposure          (analytic proxy of the frozen R0 extrapolation-overshoot
                            for the ground-truth-best action; the harness also
                            records the REAL DT risk_score, which is preferred)
  * action_space_size      (number of feasible actions)
  * agent_disagreement     (pstdev of the three agent scores on the best action;
                            filled post-run by the harness)

Then, for each contrast in {B-A, C-B, D-B} (per-scenario aggregated), we fit an
OLS of the contrast on the standardised factors (numpy lstsq, with a cluster
bootstrap CI per coefficient) and, separately, bucket the contrast by factor
tertiles.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from app.evaluation import ground_truth as gt

MECHANISM_VERSION = "eval_mechanism_v1"

FACTOR_NAMES = (
    "uncertainty",
    "constraint_tightness",
    "objective_conflict",
    "prediction_error",
    "risk_exposure",
    "action_space_size",
    "agent_disagreement",
)


# --------------------------------------------------------------------------- #
# per-scenario factor extraction (pre-run)                                   #
# --------------------------------------------------------------------------- #
def _constraint_tightness(scenario: Any) -> float:
    """0 == no binding constraint at status quo; -> 1 as a constraint bites hard."""
    p = dict(scenario.params)
    c = dict(scenario.constraints)
    base = gt.evaluate(scenario, ())
    d0 = base.breakdown["demand"]
    tight = 0.0
    inv = c.get("inventory_cap")
    if inv is not None and np.isfinite(inv):
        tight = max(tight, float(np.clip(1.0 - inv / max(1e-9, d0), 0.0, 1.0)))
    cap = c.get("capacity_cap")
    if cap is not None and np.isfinite(cap):
        tight = max(tight, float(np.clip(1.0 - cap / max(1e-9, d0), 0.0, 1.0)))
    cash = c.get("cash_cap")
    if cash is not None:
        headroom = cash / max(1e-9, p["marketing_base_spend"]) - 1.0   # fraction of extra spend allowed
        tight = max(tight, float(np.clip(1.0 - headroom / 0.30, 0.0, 1.0)))  # 30% headroom => not tight
    return round(tight, 6)


def _objective_conflict(scenario: Any) -> float:
    """1 - Spearman rank correlation between the feasible-action ranking under a
    pure-revenue objective and under the scenario's own objective. 0 == aligned,
    2 == perfectly reversed."""
    acts = list(scenario.feasible_actions)
    if len(acts) < 3:
        return 0.0
    rev_scn = type(scenario)(**{**scenario.__dict__, "objective": {"kpi": "revenue", "sense": "max"}})
    rev_vals = np.array([gt.evaluate(rev_scn, a).value for a in acts])
    own_vals = np.array([gt.evaluate(scenario, a).value for a in acts])
    rr = _rankdata(rev_vals)
    oo = _rankdata(own_vals)
    if rr.std() < 1e-9 or oo.std() < 1e-9:
        return 0.0
    rho = float(np.corrcoef(rr, oo)[0, 1])
    return round(1.0 - rho, 6)


def _rankdata(x: np.ndarray) -> np.ndarray:
    order = np.argsort(np.argsort(x))
    return order.astype(float)


def _risk_exposure_proxy(scenario: Any) -> float:
    """Analytic proxy of the FROZEN R0 extrapolation-overshoot heuristic
    (``digital_twin_service._risk_from_extrapolation``), reproduced OFFLINE for a
    mechanism factor only — no call is made into the Digital Twin. The harness
    additionally records the REAL ``risk_score`` from the sims it runs; that real
    value is preferred by ``interaction_analysis`` when present.

    R0: overshoot of a feature value beyond its historical [min, max], normalised
    by (max - min). Here we evaluate it for the ground-truth-best feasible action.
    """
    hist = getattr(scenario, "reference_history", None) or {}
    price = np.asarray(hist.get("price") or [], dtype=float)
    mkt = np.asarray(hist.get("marketing_spend") or [], dtype=float)
    if price.size == 0:
        return 0.0
    p_lo, p_hi = float(price.min()), float(price.max())
    m_lo, m_hi = (float(mkt.min()), float(mkt.max())) if mkt.size else (0.0, 0.0)
    p0 = dict(scenario.params)["base_price"]
    s0 = dict(scenario.params)["marketing_base_spend"]

    orc = gt.oracle(scenario, list(scenario.feasible_actions))
    if orc.get("status") != "ok":
        return 0.0
    pct = gt.action_pcts(orc["action"])
    price_val = p0 * (1 + pct["price_change"] / 100.0)
    mkt_val = s0 * (1 + pct["marketing_change"] / 100.0)

    def _overshoot(value, lo, hi):
        span = hi - lo
        if span <= 1e-9:
            return 1.0 if abs(value - lo) > 1e-9 else 0.0
        if value < lo:
            return (lo - value) / span
        if value > hi:
            return (value - hi) / span
        return 0.0

    over = max(_overshoot(price_val, p_lo, p_hi),
              _overshoot(mkt_val, m_lo, m_hi) if mkt.size else 0.0)
    return round(float(min(over, 1.0)), 6)


def extract_factors(scenario: Any) -> dict:
    """Pre-run factors (no pipeline needed)."""
    unc = scenario.uncertainty or {}
    unc_scalar = 0.0
    for k in ("demand_noise_sd", "obs_noise_sd", "price_band_pct", "history_trend_break", "stress"):
        v = unc.get(k)
        if isinstance(v, bool):
            unc_scalar = max(unc_scalar, 1.0 if v else 0.0)
        elif isinstance(v, (int, float)):
            unc_scalar = max(unc_scalar, float(v) / (35.0 if k == "price_band_pct" else 1.0))
    return {
        "uncertainty": round(float(np.clip(unc_scalar, 0.0, 3.0)), 6),
        "constraint_tightness": _constraint_tightness(scenario),
        "objective_conflict": _objective_conflict(scenario),
        "prediction_error": None,          # filled post-run
        "risk_exposure": _risk_exposure_proxy(scenario),
        "risk_exposure_source": "analytic_R0_proxy",
        "action_space_size": float(len(scenario.feasible_actions)),
        "agent_disagreement": None,        # filled post-run
    }


def merge_run_factors(pre: dict, *, prediction_error: float | None = None,
                      agent_disagreement: float | None = None,
                      real_risk_score: float | None = None) -> dict:
    out = dict(pre)
    if prediction_error is not None:
        out["prediction_error"] = round(float(prediction_error), 6)
    if agent_disagreement is not None:
        out["agent_disagreement"] = round(float(agent_disagreement), 6)
    if real_risk_score is not None:
        out["risk_exposure"] = round(float(real_risk_score), 6)
        out["risk_exposure_source"] = "digital_twin_risk_score"
    return out


# --------------------------------------------------------------------------- #
# interaction analysis                                                       #
# --------------------------------------------------------------------------- #
@dataclass
class InteractionResult:
    contrast: str
    n_scenarios: int
    ols_coefficients: dict          # factor -> {"beta": .., "ci95": [lo, hi]}
    tertile_means: dict             # factor -> {"low": .., "mid": .., "high": ..}
    note: str


def _standardise(x: np.ndarray) -> np.ndarray:
    sd = x.std()
    return (x - x.mean()) / sd if sd > 1e-9 else np.zeros_like(x)


def interaction_analysis(scenario_factors: dict[str, dict],
                         contrast_by_scenario: dict[str, float], *,
                         contrast: str, n_boot: int = 5000, seed: int = 4242) -> dict:
    """``scenario_factors``: scenario_id -> factor dict (from extract/merge).
    ``contrast_by_scenario``: scenario_id -> per-scenario contrast value
    (e.g. mean of D_metric - B_metric over seeds). Returns OLS coefficients on
    standardised factors + tertile-bucketed contrast means."""
    keys = sorted(set(scenario_factors) & set(contrast_by_scenario))
    usable_factors = [
        f for f in FACTOR_NAMES
        if sum(1 for k in keys if isinstance(scenario_factors[k].get(f), (int, float))) >= max(6, len(keys) // 2)
    ]
    if len(keys) < 6 or not usable_factors:
        return {"contrast": contrast, "n_scenarios": len(keys),
                "note": "insufficient scenarios or factor coverage for interaction analysis",
                "usable_factors": usable_factors}

    y = np.array([contrast_by_scenario[k] for k in keys], dtype=float)
    cols = []
    for f in usable_factors:
        raw = np.array([float(scenario_factors[k].get(f) or 0.0) for k in keys], dtype=float)
        cols.append(_standardise(raw))
    X = np.column_stack([np.ones(len(keys))] + cols)

    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    rng = np.random.default_rng(seed)
    boots = np.zeros((n_boot, X.shape[1]))
    for b in range(n_boot):
        idx = rng.integers(0, len(keys), size=len(keys))
        bb, *_ = np.linalg.lstsq(X[idx], y[idx], rcond=None)
        boots[b] = bb
    lo = np.percentile(boots, 2.5, axis=0)
    hi = np.percentile(boots, 97.5, axis=0)

    coeffs = {"intercept": {"beta": round(float(beta[0]), 6),
                            "ci95": [round(float(lo[0]), 6), round(float(hi[0]), 6)]}}
    for j, f in enumerate(usable_factors, start=1):
        coeffs[f] = {"beta": round(float(beta[j]), 6),
                     "ci95": [round(float(lo[j]), 6), round(float(hi[j]), 6)]}

    tertiles = {}
    for f in usable_factors:
        raw = np.array([float(scenario_factors[k].get(f) or 0.0) for k in keys])
        if raw.std() < 1e-9:
            continue
        q1, q2 = np.percentile(raw, [33.333, 66.667])
        buckets = {"low": [], "mid": [], "high": []}
        for k, r in zip(keys, raw):
            b = "low" if r <= q1 else ("high" if r > q2 else "mid")
            buckets[b].append(contrast_by_scenario[k])
        tertiles[f] = {b: (round(float(np.mean(v)), 6) if v else None) for b, v in buckets.items()}

    return {
        "contrast": contrast,
        "n_scenarios": len(keys),
        "usable_factors": usable_factors,
        "ols_coefficients_on_standardised_factors": coeffs,
        "tertile_contrast_means": tertiles,
        "note": ("component-level effect under controlled simulation; "
                 "coefficients are associational within the designed suite, not causal"),
    }
