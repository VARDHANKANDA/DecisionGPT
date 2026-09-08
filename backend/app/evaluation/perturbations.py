"""Evaluation-only perturbations for robustness testing.

PURE: stdlib + numpy only. No production dependency.

A perturbation is an EVALUATION TRANSFORMATION applied to the *observations the
system under test ingests* (the scenario ``history`` arrays and the ``constraints``
the ephemeral business/goal reflect). It NEVER changes the ground-truth economic
parameters, so the oracle / normalised regret are always computed against the
TRUE optimum — degradation therefore measures "the system saw corrupted /
shifted / adversarial data and was still graded against reality".

Nothing here alters production robustness behaviour; the frozen pipeline is
unchanged.

Each perturbation takes ``(history, constraints, severity, rng)`` with
``severity in [0, 1]`` and returns ``(new_history, new_constraints, meta)``.
"""
from __future__ import annotations

import copy
import random
from typing import Callable

import numpy as np

PERTURBATION_VERSION = "eval_perturbations_v1"


def _arr(hist: dict, key: str) -> np.ndarray:
    return np.asarray(hist.get(key) or [], dtype=float)


def _rng(seed) -> random.Random:
    return seed if isinstance(seed, random.Random) else random.Random(seed)


# --------------------------------------------------------------------------- #
# perturbations                                                              #
# --------------------------------------------------------------------------- #
def input_noise(history, constraints, severity, rng):
    r = _rng(rng)
    h = copy.deepcopy(history)
    sd = 0.30 * severity
    for key in ("units", "price", "marketing_spend"):
        vals = _arr(h, key)
        if vals.size:
            h[key] = [round(float(max(0.0, v * (1.0 + r.gauss(0, sd)))), 4) for v in vals]
    return h, dict(constraints), {"kind": "input_noise", "severity": severity, "noise_sd": sd}


def forecast_error_bias(history, constraints, severity, rng):
    r = _rng(rng)
    h = copy.deepcopy(history)
    sign = r.choice((-1.0, 1.0))
    drift = 0.40 * severity * sign
    units = _arr(h, "units")
    if units.size:
        cut = int(units.size * 2 / 3)
        units[cut:] = units[cut:] * (1.0 + drift)
        h["units"] = [round(float(max(0.0, v)), 4) for v in units]
    return h, dict(constraints), {"kind": "forecast_error_bias", "severity": severity, "drift": drift}


def missing_values(history, constraints, severity, rng):
    r = _rng(rng)
    h = copy.deepcopy(history)
    drop = min(0.6, 0.5 * severity + 0.1)
    offs = h.get("day_offsets") or list(range(len(h.get("units") or [])))
    keep_idx = [i for i in range(len(offs)) if r.random() >= drop]
    if len(keep_idx) < max(10, len(offs) // 4):
        keep_idx = list(range(max(10, len(offs) // 4)))
    for key in ("day_offsets", "price", "units", "marketing_spend", "stock"):
        if h.get(key) is not None:
            h[key] = [h[key][i] for i in keep_idx]
    h["days"] = len(keep_idx)
    return h, dict(constraints), {"kind": "missing_values", "severity": severity, "drop_rate": drop,
                                  "kept": len(keep_idx)}


def uncertainty_inflation(history, constraints, severity, rng):
    r = _rng(rng)
    h = copy.deepcopy(history)
    jitter = 0.20 * severity
    units = _arr(h, "units")
    price = _arr(h, "price")
    if units.size:
        h["units"] = [round(float(max(0.0, v * (1 + r.uniform(-jitter, jitter) * 1.5))), 4) for v in units]
    if price.size:
        h["price"] = [round(float(max(0.01, v * (1 + r.uniform(-jitter, jitter)))), 4) for v in price]
    return h, dict(constraints), {"kind": "uncertainty_inflation", "severity": severity, "jitter": jitter}


def constraint_tighten(history, constraints, severity, rng):
    c = dict(constraints)
    f = 1.0 - 0.5 * severity
    for k in ("cash_cap", "inventory_cap", "capacity_cap"):
        if c.get(k) is not None:
            c[k] = round(float(c[k]) * f, 4)
    if "price_ceiling_pct" in c:
        c["price_ceiling_pct"] = round(float(c["price_ceiling_pct"]) * f, 4)
    return copy.deepcopy(history), c, {"kind": "constraint_tighten", "severity": severity, "factor": f}


def constraint_relax(history, constraints, severity, rng):
    c = dict(constraints)
    f = 1.0 + 0.5 * severity
    for k in ("cash_cap", "inventory_cap", "capacity_cap"):
        if c.get(k) is not None:
            c[k] = round(float(c[k]) * f, 4)
    return copy.deepcopy(history), c, {"kind": "constraint_relax", "severity": severity, "factor": f}


def distribution_shift(history, constraints, severity, rng):
    h = copy.deepcopy(history)
    shift = 0.5 * severity
    units = _arr(h, "units")
    if units.size:
        cut = int(units.size * 2 / 3)
        units[cut:] = units[cut:] * (1.0 + shift)
        h["units"] = [round(float(max(0.0, v)), 4) for v in units]
    return h, dict(constraints), {"kind": "distribution_shift", "severity": severity, "shift": shift}


def contradictory_signals(history, constraints, severity, rng):
    """Push recent demand UP and recent price UP together, so a naive forecast
    says 'grow' while the price trend says 'demand fell as price rose'."""
    h = copy.deepcopy(history)
    amt = 0.4 * severity
    units = _arr(h, "units")
    price = _arr(h, "price")
    if units.size:
        cut = int(units.size * 3 / 4)
        units[cut:] = units[cut:] * (1.0 + amt)
        price[cut:] = price[cut:] * (1.0 + amt)
        h["units"] = [round(float(max(0.0, v)), 4) for v in units]
        h["price"] = [round(float(max(0.01, v)), 4) for v in price]
    return h, dict(constraints), {"kind": "contradictory_signals", "severity": severity, "amount": amt}


def extreme_but_feasible(history, constraints, severity, rng):
    r = _rng(rng)
    h = copy.deepcopy(history)
    units = _arr(h, "units")
    if units.size:
        # maximal-but-valid volatility: alternate large up/down swings
        swing = 0.5 * severity
        h["units"] = [round(float(max(1.0, v * (1 + (swing if i % 2 else -swing)))), 4)
                      for i, v in enumerate(units)]
    c = dict(constraints)
    for k in ("cash_cap", "inventory_cap", "capacity_cap"):
        if c.get(k) is not None:
            c[k] = round(float(c[k]) * (1.0 - 0.15 * severity), 4)   # near the feasibility edge
    return h, c, {"kind": "extreme_but_feasible", "severity": severity}


def adversarial(history, constraints, severity, rng):
    """Compress the historical price range toward a single value so the
    extrapolation-risk heuristic (R0) over-penalises ANY price move — a targeted
    diagnostic, clearly labelled adversarial."""
    h = copy.deepcopy(history)
    price = _arr(h, "price")
    if price.size:
        centre = float(np.median(price))
        pull = severity
        h["price"] = [round(float(centre + (v - centre) * (1.0 - pull)), 4) for v in price]
    return h, dict(constraints), {"kind": "adversarial", "severity": severity,
                                  "note": "history price range compressed toward its median"}


PERTURBATIONS: dict[str, Callable] = {
    "input_noise": input_noise,
    "forecast_error_bias": forecast_error_bias,
    "missing_values": missing_values,
    "uncertainty_inflation": uncertainty_inflation,
    "constraint_tighten": constraint_tighten,
    "constraint_relax": constraint_relax,
    "distribution_shift": distribution_shift,
    "contradictory_signals": contradictory_signals,
    "extreme_but_feasible": extreme_but_feasible,
    "adversarial": adversarial,
}


def apply(name: str, history: dict, constraints: dict, severity: float, seed) -> tuple[dict, dict, dict]:
    if name not in PERTURBATIONS:
        raise KeyError(f"unknown perturbation {name!r}; known: {sorted(PERTURBATIONS)}")
    if not (0.0 <= severity <= 1.0):
        raise ValueError("severity must be in [0, 1]")
    return PERTURBATIONS[name](history, constraints, float(severity), _rng(seed))


def degradation_curve(metric_by_severity: dict[float, float], *, baseline: float | None = None,
                      higher_is_better: bool = True) -> dict:
    """Summarise a per-severity metric series into a degradation curve."""
    sev = sorted(metric_by_severity)
    vals = [metric_by_severity[s] for s in sev]
    base = baseline if baseline is not None else (vals[0] if vals else None)
    if base is None or not vals:
        return {"severities": sev, "values": vals, "baseline": base}
    drops = [(base - v) if higher_is_better else (v - base) for v in vals]
    # severity at which the metric has degraded by >= 50% of the baseline
    half = 0.5 * abs(base)
    sev_at_half = next((s for s, dr in zip(sev, drops) if dr >= half), None)
    _trapezoid = getattr(np, "trapezoid", getattr(np, "trapz", None))
    auc = float(_trapezoid(drops, sev)) if (len(sev) > 1 and _trapezoid) else 0.0
    return {
        "severities": sev, "values": [round(float(v), 6) for v in vals],
        "baseline": round(float(base), 6),
        "degradation": [round(float(d), 6) for d in drops],
        "severity_at_50pct_degradation": sev_at_half,
        "auc_degradation": round(auc, 6),
    }
