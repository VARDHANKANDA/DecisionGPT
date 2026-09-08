"""``r1_dt`` — the minimal research-only Decision-Simulation correction.

It wraps the **production** ``digital_twin_service.simulate_strategy`` and
replaces ONLY the scenario-side ``expected_units_sold`` / ``expected_revenue`` /
``expected_profit`` with a per-instance, data-estimated **constant-elasticity**
demand response:

    u_a  = u_base · price_effect(p_a/p̄ ; ε̂) · marketing_effect(s_a/s̄ ; â) · fulfil_cap
    price_effect(r ; ε̂)    = clip( r ** ε̂ , 0 , 5 )      # ε̂ < 0  (demand curves slope down)
    marketing_effect(m ; â) = clip( m ** â , 0 , 5 )      # â ∈ [0,1] (diminishing returns)

``u_base`` = the production Digital Twin's baseline forecast (unchanged — the
production model still supplies the demand *level*, seasonality and autoregressive
dynamics). ``ε̂``, ``â`` are estimated by OLS of ``log(units)`` on ``log(price)``
+ ``log(marketing_spend)`` + weekday controls over the business's OWN seeded
history (the price/marketing columns the production model reads but does not
learn from). Fallback to the frozen scenario generator's ``a_elast`` / ``a_mkt``
(a documented, per-instance-logged information advantage) only when the history
is too short / has degenerate price variation / yields an implausible sign.

``risk_score`` / ``risk_level`` and every other field come straight from the
production result. No hand-tuned coefficient favours any condition.

PURE except for lazy production imports used only to (a) call the real simulator
and (b) read the seeded history and known inventory. No ``ground_truth`` import,
no oracle, no objective value, no future outcome.
"""
from __future__ import annotations

import contextlib
import math
from dataclasses import replace
from typing import Any

import numpy as np

R1_DT_VERSION = "r1_dt_constant_elasticity_v1"

# frozen coefficients (pre-registered; NOT tuned):
_EPS_CLIP = (-4.0, -0.05)     # estimated price elasticity must be strictly negative (rule 1)
_AMK_CLIP = (0.0, 1.0)        # marketing exponent: non-negative, diminishing returns
_EFFECT_CLIP = (0.0, 5.0)     # guard against extreme extrapolation of the power law
_MIN_HISTORY_ROWS = 20
_MIN_LOGPRICE_SD = 0.01


# --------------------------------------------------------------------------- #
# elasticity estimation from the business's own seeded history               #
# --------------------------------------------------------------------------- #
def estimate_response(db, business_id: str, scenario: Any) -> dict:
    """OLS log(units) ~ log(price) + log(spend) + weekday dummies over the seeded
    daily series. Returns {eps_hat, amk_hat, method, n_rows, logprice_sd, r2}."""
    from app.analytics import forecast_service as fs

    try:
        daily = fs.build_daily_series(db, business_id)
    except Exception:
        daily = None

    def _fallback(reason: str) -> dict:
        p = getattr(scenario, "params", {}) or {}
        ael = p.get("a_elast")
        amk = p.get("a_mkt")
        if ael is not None:
            return {"eps_hat": float(np.clip(float(ael), *_EPS_CLIP)),
                    "amk_hat": float(np.clip(float(amk if amk is not None else 0.2), *_AMK_CLIP)),
                    "method": "fallback_generator", "reason": reason, "n_rows": 0,
                    "logprice_sd": None, "r2": None}
        return {"eps_hat": -1.0, "amk_hat": 0.2, "method": "fallback_default",
                "reason": reason, "n_rows": 0, "logprice_sd": None, "r2": None}

    if daily is None or len(daily) < _MIN_HISTORY_ROWS:
        return _fallback("history_too_short")

    p = np.asarray(daily["price"], float)
    u = np.asarray(daily["units_sold"], float)
    m = np.asarray(daily["marketing_spend"], float)
    dow = np.asarray(pd_dayofweek(daily), float)
    mask = (p > 0) & (u > 0) & (m > 0)
    if mask.sum() < _MIN_HISTORY_ROWS:
        return _fallback("insufficient_positive_rows")
    lp = np.log(p[mask]); lu = np.log(u[mask]); lm = np.log(m[mask]); dw = dow[mask]
    logprice_sd = float(lp.std())
    if logprice_sd < _MIN_LOGPRICE_SD:
        return _fallback("degenerate_price_variation")

    cols = [np.ones(mask.sum()), lp - lp.mean(), lm - lm.mean()]
    for k in range(1, 7):                         # weekday dummies (Sunday = reference)
        cols.append((dw == k).astype(float))
    X = np.column_stack(cols)
    try:
        beta, *_ = np.linalg.lstsq(X, lu, rcond=None)
    except np.linalg.LinAlgError:
        return _fallback("rank_deficient")
    resid = lu - X @ beta
    ss_tot = float(((lu - lu.mean()) ** 2).sum()) or 1.0
    r2 = 1.0 - float((resid ** 2).sum()) / ss_tot
    eps_raw = float(beta[1]); amk_raw = float(beta[2])
    if not (_EPS_CLIP[0] <= eps_raw <= _EPS_CLIP[1]):
        fb = _fallback("implausible_elasticity_sign_or_magnitude")
        fb["eps_ols_raw"] = round(eps_raw, 4); fb["amk_ols_raw"] = round(amk_raw, 4)
        fb["r2"] = round(r2, 4); fb["n_rows"] = int(mask.sum()); fb["logprice_sd"] = round(logprice_sd, 4)
        return fb
    return {"eps_hat": float(np.clip(eps_raw, *_EPS_CLIP)),
            "amk_hat": float(np.clip(amk_raw, *_AMK_CLIP)),
            "method": "ols", "reason": None, "n_rows": int(mask.sum()),
            "logprice_sd": round(logprice_sd, 4), "r2": round(r2, 4),
            "eps_ols_raw": round(eps_raw, 4), "amk_ols_raw": round(amk_raw, 4)}


def pd_dayofweek(daily) -> list[int]:
    import pandas as pd
    return list(pd.to_datetime(daily["date"]).dt.dayofweek)


# --------------------------------------------------------------------------- #
# the corrected simulator (closure over one scenario)                        #
# --------------------------------------------------------------------------- #
def make_r1_simulate_strategy(scenario: Any, real_simulate_strategy):
    """Return a drop-in replacement for ``digital_twin_service.simulate_strategy``
    bound to ``scenario``. Calls the real simulator, then overrides only the
    scenario-side demand / revenue / profit with the constant-elasticity model."""
    from app.analytics.digital_twin_service import ACTION_VALUE_BOUNDS  # noqa: F401 (parity check)

    est_cache: dict = {}

    def r1_simulate_strategy(db, business_id, actions, goal_id=None, horizon_days: int = 14,
                             strategy_id=None, causal_context=None, risk_model=None):
        base = real_simulate_strategy(db, business_id, actions, goal_id=goal_id,
                                      horizon_days=horizon_days, strategy_id=strategy_id,
                                      causal_context=causal_context, risk_model=risk_model)
        o = base.output
        by_type = {a.type: a.value for a in actions}
        price_pct = float(by_type.get("price_change", 0.0))
        mkt_pct = float(by_type.get("marketing_change", 0.0))
        inv_pct = by_type.get("inventory_change")

        key = business_id
        if key not in est_cache:
            est_cache[key] = estimate_response(db, business_id, scenario)
        est = est_cache[key]
        eps_hat = est["eps_hat"]; amk_hat = est["amk_hat"]

        r_p = max(1e-6, 1.0 + price_pct / 100.0)
        r_m = max(1e-6, 1.0 + mkt_pct / 100.0)
        price_effect = float(np.clip(r_p ** eps_hat, *_EFFECT_CLIP))
        mkt_effect = float(np.clip(r_m ** amk_hat, *_EFFECT_CLIP))

        u_base = float(o.baseline_units_sold or 0.0)
        u_a = max(0.0, u_base * price_effect * mkt_effect)

        # fulfilment ceilings a real Digital Twin would know (NOT the objective / oracle):
        inv_constrained = bool(o.inventory_constrained)
        if inv_pct is not None:
            from app.analytics.digital_twin_service import _current_inventory_units
            cur = _current_inventory_units(db, business_id) or 0.0
            available = cur * (1.0 + float(inv_pct) / 100.0)
            if available > 0 and u_a > available:
                u_a = available; inv_constrained = True
        cap = (getattr(scenario, "constraints", {}) or {}).get("capacity_cap")
        if cap is not None and math.isfinite(cap) and u_a > cap:
            u_a = float(cap); inv_constrained = True

        baseline_price = (float(o.baseline_revenue) / u_base) if u_base > 1e-9 else 0.0
        p_a = baseline_price * (1.0 + price_pct / 100.0)
        unit_cost = None
        if o.baseline_profit is not None and u_base > 1e-9:
            unit_cost = baseline_price - float(o.baseline_profit) / u_base

        expected_revenue = round(u_a * p_a, 2)
        expected_profit = (round(u_a * (p_a - unit_cost), 2) if unit_cost is not None else o.expected_profit)

        new_output = replace(
            o,
            expected_units_sold=round(u_a, 2),
            expected_revenue=expected_revenue,
            expected_profit=expected_profit,
            inventory_constrained=inv_constrained,
            revenue_lower_bound=round(expected_revenue * 0.9, 2),
            revenue_upper_bound=round(expected_revenue * 1.1, 2),
            assumptions=list(o.assumptions) + [
                f"[r1_dt {R1_DT_VERSION}] scenario demand replaced by constant-elasticity model: "
                f"eps_hat={round(eps_hat,3)} amk_hat={round(amk_hat,3)} method={est['method']} "
                f"(baseline level, seasonality, risk score unchanged from production)."
            ],
        )
        try:
            return replace(base, output=new_output)
        except Exception:
            base.output = new_output
            return base

    r1_simulate_strategy._r1_estimates = est_cache          # inspectable by the harness
    r1_simulate_strategy._r1_scenario_id = getattr(scenario, "scenario_id", None)
    return r1_simulate_strategy


@contextlib.contextmanager
def r1_dt_active(scenario: Any):
    """Install ``r1_dt`` for the duration of one instance, then restore the
    production simulator. Nothing outside this context is affected."""
    from app.analytics import digital_twin_service as dts

    real = dts.simulate_strategy
    patched = make_r1_simulate_strategy(scenario, real)
    dts.simulate_strategy = patched
    try:
        yield patched
    finally:
        dts.simulate_strategy = real
