"""What a registered model is FOR, and whether it may be used for a given business task.

A model that loads and predicts is not thereby applicable: it must have been trained on the same target, in the same units, at the same
aggregation, for a comparable population. The record (``lifecycle_json['applicability']``) is written at training time; models that
predate it get an inferred record that says so (``source = 'inferred'``) and is never more permissive than the evidence allows.

Eligibility flags
* ``business_level_forecast``: may produce a business's own daily-unit forecast (needs aggregation ``business_daily_total``, a
  population that is that one business, non-synthetic provenance, and recent business scale inside the training range).
* ``price_scenarios``: may be used to estimate a price effect. Never true on the current evidence: no registered model was trained
  with identifying price variation, and this flag additionally needs a recorded identification result.
* ``customer_scoring``: may score a business's customers as a probability; needs observed (non-synthetic) labels.
"""
from __future__ import annotations

from typing import Any

SYNTHETIC = "synthetic_platform"
UPLOADED = "uploaded_dataset"
OWN_HISTORY = "business_own_history"


def _infer(model: Any) -> dict[str, Any]:
    ds = str(getattr(model, "dataset_version", "") or "")
    mtype = str(getattr(model, "model_type", "") or "")
    forecasting = mtype.startswith("forecasting") or str(getattr(model, "model_name", "")).startswith("sales_forecast")
    if ds.startswith("platform-forecasting"):
        prov, pop = SYNTHETIC, "40 synthetic series (platform-forecasting-v1)"
    elif ds.startswith("platform-churn"):
        prov, pop = SYNTHETIC, "6,000 synthetic customers (platform-churn-v1)"
    elif ds.startswith("upload:"):
        prov, pop = UPLOADED, "a research-console upload (population and aggregation not recorded)"
    else:
        prov, pop = "unknown", "not recorded"
    if forecasting:
        return {
            "provenance": prov, "target": "units_sold", "target_unit": "units per series per day" if prov == SYNTHETIC else "not recorded",
            "aggregation": "per_series_daily" if prov == SYNTHETIC else "not_recorded", "population": pop, "business_id": None,
            "task": "recursive next-day forecast, horizon up to 90 days", "horizon_max_days": 90,
            "evaluation_scope": "held-out chronological block of the same population" if prov == SYNTHETIC else "not recorded",
        }
    return {
        "provenance": prov, "target": "churned", "target_unit": "binary label", "aggregation": "per_customer_snapshot", "population": pop,
        "business_id": None, "task": "score customers by similarity to customers labelled as churned", "horizon_max_days": None,
        "evaluation_scope": "stratified held-out customers of the same population" if prov == SYNTHETIC else "not recorded",
    }


def describe(model: Any) -> dict[str, Any]:
    """The applicability record of ``model`` (recorded if present, otherwise inferred and marked as such)."""
    life = getattr(model, "lifecycle_json", None) or {}
    meta_app = ((life.get("run_metadata") or {}).get("applicability")) or life.get("applicability")
    rec = dict(meta_app) if isinstance(meta_app, dict) else {**_infer(model), "source": "inferred"}
    rec.setdefault("source", "recorded")
    task = "forecasting" if str(getattr(model, "model_type", "")).startswith("forecasting") else "churn"
    synthetic = rec.get("provenance") == SYNTHETIC
    reasons: list[str] = []
    if synthetic:
        reasons.append("trained on synthetic platform data only")
    if rec.get("provenance") in ("unknown", None):
        reasons.append("training-data provenance is not recorded")
    flags = {"business_level_forecast": False, "price_scenarios": False, "customer_scoring": False}
    if task == "forecasting":
        if rec.get("aggregation") != "business_daily_total":
            reasons.append(f"aggregation is {rec.get('aggregation')!r}, not the business's daily total of units")
        if not rec.get("business_id"):
            reasons.append("not trained for one specific business (a model trained on other populations is not used for a business forecast)")
        flags["business_level_forecast"] = bool(
            not synthetic and rec.get("provenance") in (UPLOADED, OWN_HISTORY) and rec.get("aggregation") == "business_daily_total"
            and rec.get("business_id") and rec.get("target") == "units_sold" and rec.get("target_unit", "").startswith("units")
        )
        flags["price_scenarios"] = bool(flags["business_level_forecast"] and (rec.get("price_identification") or {}).get("identified") is True)
        if not flags["price_scenarios"]:
            reasons.append("no recorded evidence that price sensitivity was identified when this model was trained")
    else:
        flags["customer_scoring"] = bool(not synthetic and rec.get("label_provenance_observed") is True)
        if not flags["customer_scoring"]:
            reasons.append("the churn label is not recorded as observed customer behaviour")
    return {**rec, "task_family": task, "eligible_for": flags, "reasons": reasons,
            "eligible_for_production_use": any(flags.values())}


def assess_business_forecast(model: Any, business_id: str, recent_mean_units: float | None,
                             training_range: tuple[float, float] | None) -> tuple[bool, list[str]]:
    """May ``model`` produce the forecast for THIS business? ``(eligible, reasons)``; an artifact that merely loads is never enough."""
    d = describe(model)
    reasons = list(d["reasons"]) if not d["eligible_for"]["business_level_forecast"] else []
    if d["eligible_for"]["business_level_forecast"]:
        if d.get("business_id") != business_id:
            reasons.append("trained for a different business")
        if training_range and recent_mean_units is not None and not (training_range[0] <= recent_mean_units <= training_range[1]):
            reasons.append(f"the business's recent scale ({recent_mean_units:.1f} units/day) is outside the training range "
                           f"({training_range[0]:.0f}-{training_range[1]:.0f})")
    return (not reasons, reasons)
