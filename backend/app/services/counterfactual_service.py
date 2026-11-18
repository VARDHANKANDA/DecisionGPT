"""Counterfactual Analysis — three DIFFERENT things, never interchangeable, always labelled:

1. ``deterministic_scenario`` — plain arithmetic on the owner's recent figures with explicitly stated assumptions (an elasticity the owner can set;
   default 0 = "no demand response"). It shows what the numbers would be IF those assumptions held. It is not a prediction.
2. ``model_prediction`` — the existing what-if simulation (a trained forecasting model re-run with changed price/marketing inputs). A
   model-based projection of association learned from history; it is not causal.
3. ``causal_counterfactual`` — only when a saved difference-in-differences analysis classified as ``causal_estimate`` exists: the changed products'
   observed outcome after the change versus the outcome that analysis implies they would have had without it, under its stated assumptions.

If none of these can be produced the response says so; nothing is invented.
"""
from __future__ import annotations

from datetime import timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.analytics import digital_twin_service as dt
from app.analytics import kpi_service
from app.core import clock
from app.core.errors import AppError
from app.services import analysis_run_service as runs
from app.services import kpi_monitor_service as kms

LABELS = {
    "deterministic_scenario": "Deterministic scenario calculation",
    "model_prediction": "Model-based prediction (not causal)",
    "causal_counterfactual": "Causal counterfactual estimate (under stated assumptions)",
}
NOT_ESTABLISHED = {
    "deterministic_scenario": "It does not say what WOULD happen. Real customers may respond differently from the assumption you chose.",
    "model_prediction": "It does not establish that the change would cause the result; the model learned how past prices/marketing moved with sales, which may reflect other factors.",
    "causal_counterfactual": "It rests on assumptions (parallel trends, no simultaneous changes, no spillovers) that cannot be proven from data. It describes the products and period analysed only.",
}
LEVERS = {"price_change_pct": "price", "marketing_change_pct": "marketing"}


def _result(mode: str, headline: str, **kw: Any) -> dict[str, Any]:
    return {"mode": mode, "label": LABELS.get(mode, mode), "headline": headline, "what_it_does_not_establish": NOT_ESTABLISHED.get(mode), "generated_on": clock.today().isoformat(), **kw}


def deterministic_scenario(db: Session, business_id: str, lever: str, change_pct: float, elasticity: float = 0.0, baseline_days: int = 30, anchor: str = "today") -> dict[str, Any]:
    if lever not in LEVERS or not (-90 <= change_pct <= 300) or not (-5 <= elasticity <= 5) or baseline_days not in kms.ALLOWED_PERIODS:
        return _result("deterministic_scenario", "The scenario is not configured correctly.", classification="not_configured",
                       reason="lever must be price_change_pct or marketing_change_pct, change between -90% and +300%, elasticity between -5 and 5, and a valid baseline period.")
    end = kms.resolve_end(db, business_id, anchor)
    snap = kpi_service.compute_kpis(db, business_id, baseline_days, end=end)
    if snap.orders == 0:
        return _result("deterministic_scenario", "There are no sales in the baseline period, so no scenario can be calculated.", classification="not_enough_data")
    p = change_pct / 100.0
    base_rev, orders = snap.revenue, snap.orders
    if lever == "price_change_pct":
        # revenue = price × units; units respond by elasticity × price change (elasticity 0 = no response)
        units_factor = max(0.0, 1 + elasticity * p)
        new_rev = base_rev * (1 + p) * units_factor
        assume = [f"Price changes by {change_pct:+g}% on every sale.", f"Units change by {elasticity:g} × the price change (elasticity {elasticity:g}); 0 means customers do not react.", "Costs per unit are unchanged."]
    else:
        # marketing: only the owner's stated sales response is applied (elasticity of sales to marketing spend)
        new_rev = base_rev * max(0.0, 1 + elasticity * p)
        assume = [f"Marketing spend changes by {change_pct:+g}%.", f"Sales change by {elasticity:g} × the spend change; 0 means no effect on sales.", "No change in anything else."]
    diff = new_rev - base_rev
    return _result("deterministic_scenario", f"If these assumptions held, sales over {baseline_days} days would be ₹{new_rev:,.0f} instead of ₹{base_rev:,.0f} ({diff:+,.0f}).",
                   classification="calculated", baseline={"period_days": baseline_days, "end": end.isoformat(), "sales": base_rev, "orders": orders},
                   scenario={"lever": lever, "change_pct": change_pct, "elasticity": elasticity, "sales": round(new_rev, 2), "difference": round(diff, 2)},
                   assumptions=assume, uncertainty="No uncertainty interval: this is arithmetic, not an estimate. The result is exactly as good as the assumption.")


def model_prediction(db: Session, business_id: str, lever: str, change_pct: float) -> dict[str, Any]:
    if lever not in LEVERS:
        return _result("model_prediction", "Choose price or marketing.", classification="not_configured")
    action_type = "price_change" if lever == "price_change_pct" else "marketing_change"
    try:
        sim = dt.api_view(db, business_id, dt.simulate_strategy(db, business_id, [dt.Action(type=action_type, value=change_pct)]), 14)
    except AppError as exc:
        return _result("model_prediction", f"A model-based prediction is not available: {exc.message}", classification="not_enough_data", reason=exc.message)
    o = sim.output
    if o.expected_revenue is None:    # the price effect is withheld: never quote a figure for it
        pr = o.price_response or {}
        return _result("model_prediction", "A price effect cannot be estimated for your business, so no figure is shown. " + str(pr.get("message", "")),
                       classification="not_available", reason=pr.get("message"), needed=pr.get("needed", []), simulation_id=sim.id,
                       baseline_revenue=o.baseline_revenue, assumptions=o.assumptions)
    diff = o.expected_revenue - o.baseline_revenue
    return _result("model_prediction", f"The model projects sales of about ₹{o.expected_revenue:,.0f} versus ₹{o.baseline_revenue:,.0f} without the change ({diff:+,.0f}).",
                   classification="model_based", simulation_id=sim.id, baseline_revenue=o.baseline_revenue, expected_revenue=o.expected_revenue, difference=round(diff, 2),
                   interval={"lower": o.revenue_lower_bound, "upper": o.revenue_upper_bound, "note": "Model prediction interval, not a guarantee."},
                   risk={"level": o.risk_level, "score": o.risk_score}, model=f"{o.model_name} {o.model_version}", assumptions=o.assumptions,
                   uncertainty="The risk level reflects how far the change lies outside what your history covers. If the model barely responds to this input, the difference can be near zero even when the real effect is not.")


def causal_counterfactual(db: Session, business_id: str, analysis_id: str | None) -> dict[str, Any]:
    if not analysis_id:
        return _result("causal_counterfactual", "Choose a saved Causal AI analysis.", classification="not_configured")
    try:
        saved = runs.get(db, business_id, analysis_id, "causal")
    except AppError:
        return _result("causal_counterfactual", "That analysis was not found.", classification="not_configured")
    res = saved["result"]
    if res.get("classification") != "causal_estimate":
        return _result("causal_counterfactual", "A causal counterfactual cannot be produced: the saved analysis did not yield a causal estimate "
                       f"(it was classified '{res.get('classification')}').", classification="not_available", source_analysis=analysis_id)
    est, means = res["estimate"], res["group_means"]
    obs = means["changed_after"]
    cf = obs - est["effect_per_product_day"]
    return _result("causal_counterfactual", f"Observed {obs:,.2f} per product per day after the change; without it, the analysis implies about {cf:,.2f} "
                   f"(difference {est['effect_per_product_day']:+,.2f}).", classification="causal_estimate", source_analysis=analysis_id, observed_after=obs, counterfactual_after=round(cf, 3),
                   difference=est["effect_per_product_day"], ci95=est["ci95"], unit=est["unit"], assumptions=res.get("assumptions"), products=res.get("products"),
                   intervention_date=res.get("intervention_date"), uncertainty="95% interval on the difference shown above; the assumptions list states what is unverified.")


def run(db: Session, business_id: str, params: dict[str, Any]) -> dict[str, Any]:
    mode = params.get("mode")
    if mode == "deterministic_scenario":
        res = deterministic_scenario(db, business_id, params.get("lever", ""), float(params.get("change_pct", 0)), float(params.get("elasticity", 0)),
                                     int(params.get("baseline_days", 30)), params.get("anchor", "today"))
    elif mode == "model_prediction":
        res = model_prediction(db, business_id, params.get("lever", ""), float(params.get("change_pct", 0)))
    elif mode == "causal_counterfactual":
        res = causal_counterfactual(db, business_id, params.get("analysis_id"))
    else:
        res = {"mode": mode, "label": "Unknown", "headline": "mode must be deterministic_scenario, model_prediction or causal_counterfactual.", "classification": "not_configured"}
    row = runs.save(db, business_id, "counterfactual", mode, res.get("headline"), params, res, status="completed")
    return {"id": row.id, **res}


# kept for symmetry with the other engines (used by tests)
def window(days: int) -> timedelta:
    return timedelta(days=days)
