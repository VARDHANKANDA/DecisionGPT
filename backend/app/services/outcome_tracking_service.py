"""Business outcome tracking (docs/BUSINESS_OUTCOME_TRACKING.md).

Records what was expected, what the owner did, and what was observed afterwards; compares an expectation with an observation only when
they describe the same metric, units, scope and window; and reports accuracy and (separately) why business impact cannot be inferred.

Rules this module enforces, each tested:
* unknown stays unknown: a missing observation is ``pending``/``invalid`` with a reason, never 0;
* a displayed, accepted or modified recommendation is never 'executed' unless the owner records that it was;
* history is append-only: a correction is a new revision with a reason;
* an expectation is never compared with data it could already see (``in_sample``) or with a different window / metric / unit;
* an expectation from a model that is not eligible for business-level figures is stored but marked not comparable;
* nothing here trains, promotes or changes the eligibility of a model, and no impact is attributed to DecisionGPT.
"""
from __future__ import annotations

import math
from datetime import date, timedelta
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy import func, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import set_committed_value

from app.analytics import forecast_service
from app.core import clock
from app.core.errors import ConflictError, InsufficientDataError, NotFoundError, ValidationFailedError
from app.db.snapshot import read_snapshot
from app.models.business import Business
from app.models.common import utcnow
from app.models.decision import Decision, DecisionOutcome
from app.models.marketing import MarketingCampaign
from app.models.ml_model import MLModel
from app.models.sale import Sale
from app.models.tracking import (
    ACTION_STATUSES, DESIGNS, METRICS, OBS_STATUSES, RESPONSES, SCOPE_BUSINESS_TOTAL, SOURCE_KINDS,
    DecisionResponse, OutcomeObservation, TrackedExpectation,
)
from app.services import forecast_validation_service as fv

DECISION_HORIZON_DAYS = 14        # the decision pipeline's default scenario horizon is 14 days; it is not stored on the decision
MAX_WINDOW_DAYS = 366
MIN_COMPARABLE_FOR_SUMMARY = 5    # provisional engineering policy: fewer comparable cases are listed, not summarised
MIN_PCT_DENOMINATOR = 1.0         # provisional: a percentage error is not reported when the observed value is below 1 unit of the metric
AGGREGATION_RULE = ("per group (metric, source kind, horizon bucket): the unweighted mean of per-forecast absolute and signed errors; "
                    "WAPE = sum of absolute errors / sum of observed values; only fully compared (not partial, not excluded) cases "
                    "contribute; groups are never combined")
HORIZON_BUCKETS = [(7, "1-7 days"), (14, "8-14 days"), (30, "15-30 days"), (10_000, "over 30 days")]

LIMITATIONS = [
    "An expectation is a figure for the business total over the window, not for any product or customer.",
    "Zero-sale days inside a window that has later data are counted as zero units; the sales table cannot tell a closed day from a gap.",
    "A comparison of expected and observed values measures predictive accuracy only; it is not evidence that an action changed the outcome.",
]


# ------------------------------------------------------------------------------------------------ small helpers
def _commit(db: Session) -> None:
    """Commit, or roll back completely and re-raise: a failure between validation and persistence never leaves a partial record
    or a session stuck in a failed transaction."""
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise


def _num(v: Any) -> float | None:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _business_is_demo(db: Session, business_id: str) -> bool:
    b = db.get(Business, business_id)
    if b is None:
        return False
    return bool((b.description or "").startswith("Synthetic demonstration") or "(demo)" in (b.name or "").lower())


def _provenance_derived(db: Session, business_id: str) -> str:
    return "demo_synthetic" if _business_is_demo(db, business_id) else "derived_from_uploaded_data"


def _decision(db: Session, business_id: str, decision_id: str) -> Decision:
    d = db.get(Decision, decision_id)
    if d is None or str(d.business_id) != str(business_id):
        raise NotFoundError(f"Decision {decision_id} not found.")
    return d


def _expectation(db: Session, business_id: str, expectation_id: str) -> TrackedExpectation:
    e = db.get(TrackedExpectation, expectation_id)
    if e is None or str(e.business_id) != str(business_id):
        raise NotFoundError(f"Expectation {expectation_id} not found.")
    return e


def _window_checks(start: date, end: date) -> int:
    if end < start:
        raise ValidationFailedError("window_end must not be before window_start.")
    days = (end - start).days + 1
    if days > MAX_WINDOW_DAYS:
        raise ValidationFailedError(f"A window may cover at most {MAX_WINDOW_DAYS} days.")
    return days


def _horizon_bucket(h: int) -> str:
    for hi, label in HORIZON_BUCKETS:
        if h <= hi:
            return label
    return HORIZON_BUCKETS[-1][1]


# ------------------------------------------------------------------------------------------------ expectations
def _snapshot_by_fingerprint(db: Session, business_id: str, fingerprint: str) -> TrackedExpectation | None:
    return (db.query(TrackedExpectation).filter(TrackedExpectation.business_id == business_id, TrackedExpectation.source_kind == "forecast",
                                                TrackedExpectation.fingerprint == fingerprint).first())


def save_forecast_snapshot(db: Session, business_id: str, horizon_days: int, question: str | None = None,
                           shown_fingerprint: str | None = None) -> tuple[TrackedExpectation, dict[str, Any]]:
    """Persist the forecast the owner chose to save.

    The forecast is recomputed ONLY to verify and to read its metadata; if ``shown_fingerprint`` (what the owner saw) differs from the
    freshly computed fingerprint - new data was uploaded, or the method changed - nothing is saved and a conflict is raised, so a saved
    snapshot is always identical to a forecast that was shown. An identical forecast already saved is returned, not duplicated; a changed
    forecast (new data) is a new snapshot. A forecast lacking the metadata needed for a later comparison is refused, never completed.
    """
    res = forecast_service.forecast_sales(db, business_id, horizon_days)         # raises InsufficientDataError / validation errors
    missing = [n for n, v in (("fingerprint", res.fingerprint), ("forecast dates", res.forecast_start), ("data cutoff", res.data_as_of),
                              ("dataset identity", res.dataset_sha256)) if not v]
    if missing or not res.points:
        raise ValidationFailedError("This forecast cannot be saved for later evaluation because its " + ", ".join(missing or ["points"])
                                    + " could not be established. Nothing was saved.")
    verified: bool | None = None
    if shown_fingerprint is not None:
        if shown_fingerprint != res.fingerprint:
            raise ConflictError(
                "The forecast has changed since it was shown (new sales data was uploaded or the forecasting method changed). Nothing was "
                "saved: refresh the forecast and save the one you see.", details={"shown": shown_fingerprint, "current": res.fingerprint})
        verified = True
    existing = _snapshot_by_fingerprint(db, business_id, res.fingerprint)
    if existing is not None:
        return existing, {"already_saved": True, "verified_against_shown": verified}
    h = len(res.points)
    pts = [{"date": p.forecast_date.isoformat(), "value": float(p.predicted_value), "lower": float(p.lower_bound), "upper": float(p.upper_bound),
            "baseline_naive_last": (res.references or {}).get("naive_last_daily"),
            "baseline_trailing_mean_28": (res.references or {}).get("trailing_mean_28_daily")} for p in res.points]
    refs = {"naive_last_total": float((res.references or {}).get("naive_last_daily") or 0.0) * h,
            "trailing_mean_28_total": float((res.references or {}).get("trailing_mean_28_daily") or 0.0) * h,
            "naive_last_daily": (res.references or {}).get("naive_last_daily"),
            "trailing_mean_28_daily": (res.references or {}).get("trailing_mean_28_daily"),
            "note": "constant per-day references computed at the same data cutoff"}
    comparable = res.forecast_basis in ("business_specific_validated", "business_specific_baseline", "limited_estimate")
    row = TrackedExpectation(
        business_id=business_id, source_kind="forecast", fingerprint=res.fingerprint, question=question, metric="units_sold", unit="units",
        scope=SCOPE_BUSINESS_TOTAL, window_start=res.forecast_start, window_end=res.forecast_end, horizon_days=h,
        data_cutoff=res.data_as_of, expected_value=round(sum(p["value"] for p in pts), 4), points_json=pts,
        interval_reliable=bool(res.interval_reliable), interval_method=res.interval_method, method=res.model_name,
        model_name=res.model_name, model_version=res.model_version, basis=res.forecast_basis,
        config_json={
            "fingerprint": res.fingerprint, "dataset_sha256": res.dataset_sha256, "generated_at": res.generated_at,
            "horizon_requested": res.horizon_requested, "horizon_returned": res.horizon_returned,
            "forecast_start": res.forecast_start.isoformat(), "forecast_end": res.forecast_end.isoformat(),
            "data_cutoff": res.data_as_of.isoformat(), "cutoff_provenance": "recorded", "horizon_provenance": "recorded",
            "metadata_quality": "known_persisted",
            "shown_fingerprint_verified": verified, "validation_status": (res.validation or {}).get("status"), "validation": res.validation,
            "target": res.target, "aggregation": res.aggregation, "granularity": "daily values; expected_value is their sum over the window",
            "interval": {"method": res.interval_method, "reliable": bool(res.interval_reliable), "nominal_coverage": 0.8},
            "calendar": "calendar dates without a time zone",
        },
        reference_json=refs, assumptions_json=["calendar days without sales rows are zero units", "no festival, promotion or supply change unless in the data"],
        limitations_json=list(res.warnings) + LIMITATIONS, comparable_to_actuals=comparable,
        comparability_reason=None if comparable else "the forecast did not come from the business's own history",
        input_sha256=res.dataset_sha256, provenance=_provenance_derived(db, business_id),
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()                       # a simultaneous save of the same forecast won the race: return that one, do not duplicate
        winner = _snapshot_by_fingerprint(db, business_id, res.fingerprint)
        if winner is not None:
            return winner, {"already_saved": True, "verified_against_shown": verified}
        raise
    except Exception:
        db.rollback()                       # no partial snapshot
        raise
    db.refresh(row)
    return row, {"already_saved": False, "verified_against_shown": verified}


def snapshot_forecast(db: Session, business_id: str, horizon_days: int, question: str | None = None) -> TrackedExpectation:
    """Store the business forecast as it would be shown now (see ``save_forecast_snapshot``)."""
    return save_forecast_snapshot(db, business_id, horizon_days, question)[0]


def _decision_model_comparable(db: Session, exp: dict) -> tuple[bool, str]:
    """Is the decision's figure on the business's own scale? Only if the model that produced it is recorded eligible for
    business-level forecasts. The registered synthetic-platform models are not, so their figures are stored but never compared."""
    from app.services import model_applicability_service as applic

    name, version = exp.get("model_name"), exp.get("model_version")
    row = (db.query(MLModel).filter(MLModel.model_name == name, MLModel.version == version).first() if name and version else None)
    if row is None:
        return False, "the model that produced this figure is not in the registry, so its scale and training population are unknown"
    a = applic.describe(row)
    if a["eligible_for"]["business_level_forecast"]:
        return True, "the model is recorded as eligible for this business's daily totals"
    return False, ("the figure comes from " + f"{name} {version}, which is not eligible for business-level figures: " + "; ".join(a["reasons"][:3])
                   + ". It is on a different scale and population from this business's actuals.")


# How a cutoff or horizon became known: persisted with the record, reconstructed from reliable evidence, inferred, or unknown. No record
# currently qualifies as "reconstructed"; an inferred value is never upgraded to a known one.
_METADATA_QUALITY = {"recorded": "known_persisted", "none_existed": "known_persisted", "inferred_from_upload_time": "inferred", "unknown": "unknown"}


def expectations_from_decision(db: Session, business_id: str, decision_id: str) -> list[TrackedExpectation]:
    """Materialise (once) the expected units and revenue of a stored decision as tracked expectations. A withheld price effect or an
    absent figure produces no expectation: nothing is invented to have something to compare."""
    d = _decision(db, business_id, decision_id)
    existing = db.query(TrackedExpectation).filter(TrackedExpectation.business_id == business_id, TrackedExpectation.decision_id == decision_id).all()
    if existing:
        return existing
    exp = d.expected_outcome_json or {}
    if (exp.get("price_response") or {}).get("withheld"):
        return []
    created = d.created_at
    po = (d.debate_json or {}).get("pipeline_options") or {}
    if "scenario_horizon_days" in po:        # recorded when the decision was made
        horizon = int(po["scenario_horizon_days"])
        rec = po.get("data_cutoff")
        cutoff = date.fromisoformat(rec) if rec else None
        cutoff_prov = "recorded" if rec else "none_existed"
        horizon_prov = "recorded"
        base_date = cutoff or (created.date() if created else clock.today())
    else:                                    # a decision made before these were stored: reconstructed and labelled as such
        horizon = DECISION_HORIZON_DAYS
        cutoff = db.query(func.max(Sale.sale_date)).filter(Sale.business_id == business_id, Sale.created_at <= created).scalar()
        cutoff_prov = "inferred_from_upload_time" if cutoff else "unknown"
        horizon_prov = "assumed_pipeline_default"
        base_date = cutoff or (created.date() if created else clock.today())
    start, end = base_date + timedelta(days=1), base_date + timedelta(days=horizon)
    comparable, reason = _decision_model_comparable(db, exp)
    if cutoff is None:
        comparable, reason = False, "no sales data existed when this decision was made, so there is no data cutoff to compare against"
    elif cutoff_prov == "inferred_from_upload_time":
        reason = (reason or "") + " (the data cutoff was reconstructed from upload times because this decision predates cutoff recording)"
    out: list[TrackedExpectation] = []
    for metric, key in (("units_sold", "expected_units_sold"), ("revenue", "expected_revenue")):
        val = _num(exp.get(key))
        if val is None:
            continue
        row = TrackedExpectation(
            business_id=business_id, source_kind="decision", decision_id=decision_id, metric=metric, unit=METRICS[metric],
            scope=SCOPE_BUSINESS_TOTAL, window_start=start, window_end=end, horizon_days=horizon, data_cutoff=cutoff,
            expected_value=val, method="digital_twin_scenario", model_name=exp.get("model_name"), model_version=exp.get("model_version"),
            basis="decision_scenario", config_json={
                "horizon_days": horizon, "horizon_provenance": horizon_prov, "cutoff_provenance": cutoff_prov,
                "metadata_quality": _METADATA_QUALITY.get(cutoff_prov, "unknown"),
                "data_cutoff": cutoff.isoformat() if cutoff else None, "calendar": "calendar dates without a time zone",
                "decision_created_at": created.isoformat() if created else None,
                "note": ("horizon and cutoff were recorded with the decision" if horizon_prov == "recorded" else
                         "this decision predates horizon and cutoff recording: the 14-day pipeline default and a cutoff reconstructed from "
                         "upload times are used, and are labelled as such")},
            assumptions_json=list(d.assumptions_json or exp.get("assumptions") or []),
            limitations_json=LIMITATIONS + ["A recommendation's expected figure assumes the action is carried out as recommended."],
            comparable_to_actuals=comparable, comparability_reason=reason, provenance=_provenance_derived(db, business_id),
        )
        db.add(row)
        out.append(row)
    _commit(db)
    for r in out:
        db.refresh(r)
    return out


def create_owner_plan(db: Session, business_id: str, metric: str, window_start: date, window_end: date, expected_value: float,
                      note: str | None, actor: str) -> TrackedExpectation:
    if metric not in METRICS:
        raise ValidationFailedError(f"metric must be one of {sorted(METRICS)}.")
    days = _window_checks(window_start, window_end)
    v = _num(expected_value)
    if v is None or v < 0:
        raise ValidationFailedError("expected_value must be a finite number that is not negative.")
    row = TrackedExpectation(
        business_id=business_id, source_kind="owner_plan", metric=metric, unit=METRICS[metric], scope=SCOPE_BUSINESS_TOTAL,
        window_start=window_start, window_end=window_end, horizon_days=days, data_cutoff=None, expected_value=v,
        method="owner_plan", basis="owner_plan", question=note, config_json={"entered_by": actor},
        assumptions_json=["a figure the owner stated; DecisionGPT did not calculate it"], limitations_json=LIMITATIONS,
        comparable_to_actuals=True, comparability_reason="an owner's own plan for the same metric, unit and window",
        provenance="demo_synthetic" if _business_is_demo(db, business_id) else "owner_entered",
    )
    db.add(row)
    _commit(db)
    db.refresh(row)
    return row


# ------------------------------------------------------------------------------------------------ responses (append-only)
def current_response(db: Session, business_id: str, decision_id: str) -> DecisionResponse | None:
    return (db.query(DecisionResponse).filter(DecisionResponse.business_id == business_id, DecisionResponse.decision_id == decision_id)
            .order_by(DecisionResponse.seq.desc()).first())


def record_response(db: Session, business_id: str, decision_id: str, *, response: str | None = None, action_status: str | None = None,
                    action_taken: dict | None = None, modified_action: dict | None = None, action_start: date | None = None,
                    action_end: date | None = None, known_changes: list[str] | None = None, evaluation_design: str | None = None,
                    follow_up_date: date | None = None, note: str | None = None, actor: str = "unknown") -> DecisionResponse:
    d = _decision(db, business_id, decision_id)
    prev = current_response(db, business_id, decision_id)

    def pick(new, attr, default):
        return new if new is not None else (getattr(prev, attr) if prev is not None else default)

    resp = pick(response, "response", "pending")
    status = pick(action_status, "action_status", "unknown")
    design = pick(evaluation_design, "evaluation_design", "none")
    taken = pick(action_taken, "action_taken_json", None)
    modified = pick(modified_action, "modified_action_json", None)
    a_start, a_end = pick(action_start, "action_start", None), pick(action_end, "action_end", None)
    changes = pick(known_changes, "known_changes_json", None)
    follow = pick(follow_up_date, "follow_up_date", None)
    text = pick(note, "note", None)
    if resp not in RESPONSES:
        raise ValidationFailedError(f"response must be one of {list(RESPONSES)}.")
    if status not in ACTION_STATUSES:
        raise ValidationFailedError(f"action_status must be one of {list(ACTION_STATUSES)}.")
    if design not in DESIGNS:
        raise ValidationFailedError(f"evaluation_design must be one of {list(DESIGNS)}.")
    # contradictions
    if status in ("executed", "partially_executed") and resp not in ("accepted", "modified"):
        raise ValidationFailedError(f"An action cannot be recorded as {status} while the response is '{resp}': accept or modify it first.")
    if resp == "rejected" and status not in ("unknown", "not_executed"):
        raise ValidationFailedError("A rejected recommendation cannot be executed.")
    if resp == "modified" and not modified:
        raise ValidationFailedError("A modified response needs modified_action: what was changed.")
    if resp != "modified":
        if modified_action is not None:
            raise ValidationFailedError("modified_action can only be recorded for a modified response.")
        modified = None                     # an earlier 'modified' description does not survive a change to another response
    created = d.created_at.date() if d.created_at else None
    today = clock.today()
    if status not in ("executed", "partially_executed"):
        # a start date or an action taken only belongs to an action that was carried out; a change to rejected / deferred / not executed
        # must not keep the dates of an earlier execution
        if action_start is not None or action_end is not None or action_taken is not None:
            raise ValidationFailedError("A start date or an action taken can only be recorded for an action that was carried out.")
        a_start = a_end = taken = None
    if status in ("executed", "partially_executed"):
        if a_start is None:
            raise ValidationFailedError("An executed action needs action_start (the date it began).")
        if a_start > today:
            raise ValidationFailedError("action_start cannot be in the future.")
        if created and a_start < created:
            raise ValidationFailedError("The action cannot have started before the recommendation was made.")
    if a_end is not None and a_start is not None and a_end < a_start:
        raise ValidationFailedError("action_end must not be before action_start.")
    if follow is not None and created and follow < created:
        raise ValidationFailedError("follow_up_date cannot be before the recommendation was made.")
    row = DecisionResponse(
        business_id=business_id, decision_id=decision_id, seq=(prev.seq + 1 if prev else 1), response=resp, action_status=status,
        action_taken_json=taken, modified_action_json=modified, action_start=a_start, action_end=a_end, known_changes_json=changes,
        evaluation_design=design, follow_up_date=follow, note=text, recorded_by=actor,
    )
    if prev is not None and all(getattr(prev, k) == getattr(row, k) for k in (
            "response", "action_status", "action_taken_json", "modified_action_json", "action_start", "action_end",
            "known_changes_json", "evaluation_design", "follow_up_date", "note")):
        raise ValidationFailedError("This response is already recorded; nothing changed.")
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()                      # a retry or double click raced with another write for the same revision
        latest = current_response(db, business_id, decision_id)
        if latest is not None and all(getattr(latest, k) == getattr(row, k) for k in (
                "response", "action_status", "action_taken_json", "modified_action_json", "action_start", "action_end",
                "known_changes_json", "evaluation_design", "follow_up_date", "note")):
            raise ValidationFailedError("This response is already recorded; nothing changed.")
        raise ConflictError("Another update to this recommendation was saved at the same moment. Refresh to see the latest response, "
                            "then change it if it is still wrong.")
    except Exception:
        db.rollback()
        raise
    db.refresh(row)
    return row


def action_executed(db: Session, business_id: str, decision_id: str) -> bool:
    """True only when the owner recorded that the recommended action was carried out (fully or partly). Never inferred."""
    r = current_response(db, business_id, decision_id)
    return r is not None and r.action_status in ("executed", "partially_executed")


def decision_comparable(db: Session, business_id: str, decision: Decision) -> bool:
    """Is the decision's expected figure on this business's own scale (a model recorded eligible for business-level figures)?"""
    ok, _ = _decision_model_comparable(db, decision.expected_outcome_json or {})
    return ok


# ------------------------------------------------------------------------------------------------ observations (append-only)
def _validated_fields(status: str, value: float | None, reason: str | None, covered_until: date | None, w_start: date, w_end: date,
                      today: date) -> tuple[float | None, str | None, date | None, int | None]:
    if status not in OBS_STATUSES:
        raise ValidationFailedError(f"status must be one of {list(OBS_STATUSES)}.")
    window_days = (w_end - w_start).days + 1
    if status in ("observed", "incomplete"):
        v = _num(value)
        if v is None or v < 0:
            raise ValidationFailedError(f"A {status} observation needs a value that is a finite number and not negative; if it is "
                                        "unknown, record it as pending or invalid instead of 0.")
        if status == "observed":
            if w_end > today:
                raise ValidationFailedError("A window that has not finished yet cannot be recorded as fully observed; record it as incomplete.")
            return v, reason, w_end, window_days
        if covered_until is None:
            raise ValidationFailedError("An incomplete observation needs covered_until: the last date the value covers.")
        if not (w_start <= covered_until < w_end):
            raise ValidationFailedError("covered_until must fall inside the window and before its end (otherwise it is observed).")
        if covered_until > today:
            raise ValidationFailedError("covered_until cannot be in the future.")
        return v, reason, covered_until, (covered_until - w_start).days + 1
    if value is not None:
        raise ValidationFailedError(f"A {status} observation has no value; do not enter 0 for an unknown.")
    if status == "invalid" and not (reason or "").strip():
        raise ValidationFailedError("An invalid observation needs unavailable_reason: why it cannot be used.")
    return None, (reason or "").strip() or ("the window has not finished or no data has been received yet" if status == "pending" else None), None, None


def _current_for_window(db: Session, business_id: str, expectation_id: str, metric: str, w_start: date, w_end: date) -> OutcomeObservation | None:
    return (db.query(OutcomeObservation).filter(
        OutcomeObservation.business_id == business_id, OutcomeObservation.expectation_id == expectation_id,
        OutcomeObservation.metric == metric, OutcomeObservation.window_start == w_start, OutcomeObservation.window_end == w_end,
        OutcomeObservation.is_current.is_(True)).first())


def record_observation(db: Session, business_id: str, expectation_id: str, *, metric: str, unit: str, status: str, value: float | None = None,
                       unavailable_reason: str | None = None, covered_until: date | None = None, window_start: date | None = None,
                       window_end: date | None = None, note: str | None = None, actor: str = "unknown") -> OutcomeObservation:
    e = _expectation(db, business_id, expectation_id)
    if metric != e.metric:
        raise ValidationFailedError(f"This expectation is about '{e.metric}'; an observation of '{metric}' cannot be compared with it. "
                                    "Record a separate expectation for that metric.")
    if unit != METRICS[metric]:
        raise ValidationFailedError(f"The unit for {metric} is '{METRICS[metric]}', not '{unit}'.")
    w_start, w_end = window_start or e.window_start, window_end or e.window_end
    _window_checks(w_start, w_end)
    v, reason, cov_until, cov_days = _validated_fields(status, value, unavailable_reason, covered_until, w_start, w_end, clock.today())
    cur = _current_for_window(db, business_id, expectation_id, metric, w_start, w_end)
    if cur is not None:
        same = (cur.status == status and _num(cur.value) == v and cur.covered_until == cov_until)
        if same:
            raise ValidationFailedError("This observation is already recorded; nothing changed.")
        raise ValidationFailedError("An observation for this window already exists. Submit a correction with a reason instead of a "
                                    "second observation, so the history stays auditable.")
    row = OutcomeObservation(
        business_id=business_id, expectation_id=expectation_id, metric=metric, unit=unit, scope=SCOPE_BUSINESS_TOTAL, window_start=w_start,
        window_end=w_end, value=v, status=status, unavailable_reason=reason, covered_until=cov_until, coverage_days=cov_days,
        window_days=(w_end - w_start).days + 1, source="owner_entered",
        provenance="demo_synthetic" if _business_is_demo(db, business_id) else "owner_entered", revision=1, is_current=True, note=note,
        recorded_by=actor,
    )
    _insert_observation(db, row)
    return row


def _supersede(db: Session, current: OutcomeObservation) -> None:
    """Make ``current`` no longer current - atomically. The UPDATE only matches while the row is STILL current, so of two requests that both
    loaded the same revision exactly one changes it; the other matches no row and gets a conflict. (A plain attribute assignment would have the
    loser rewrite an already-superseded row - on PostgreSQL, where the two really do run in parallel, the append-only trigger then refuses it
    with a raw integrity error instead of this answer.) The history guard still applies to every other change; this is the one permitted flip."""
    changed = db.execute(
        update(OutcomeObservation).where(OutcomeObservation.id == current.id, OutcomeObservation.is_current.is_(True))
        .values(is_current=False).execution_options(synchronize_session=False)
    ).rowcount
    if changed != 1:
        db.rollback()
        raise ConflictError("An observation for this window was saved at the same moment. Refresh to see it, then submit a correction if "
                            "it is wrong.")
    set_committed_value(current, "is_current", False)       # keep the in-memory row in step without scheduling another UPDATE


def _insert_observation(db: Session, row: OutcomeObservation) -> None:
    """Insert a revision. A lost race against the one-current-observation-per-window rule is a conflict, never a second current row; if
    the winner holds exactly what this request tried to save it was a retry, and the answer is the same as for any repeated submission."""
    db.add(row)
    key = (row.business_id, row.expectation_id, row.metric, row.window_start, row.window_end)
    sent = (row.status, _num(row.value), row.covered_until)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        winner = _current_for_window(db, key[0], key[1], key[2], key[3], key[4])
        if winner is not None and (winner.status, _num(winner.value), winner.covered_until) == sent:
            raise ValidationFailedError("This observation is already recorded; nothing changed.")
        raise ConflictError("An observation for this window was saved at the same moment. Refresh to see it, then submit a correction if "
                            "it is wrong.")
    except Exception:
        db.rollback()
        raise
    db.refresh(row)


def correct_observation(db: Session, business_id: str, observation_id: str, *, reason: str, status: str | None = None, value: float | None = None,
                        unavailable_reason: str | None = None, covered_until: date | None = None, actor: str = "unknown") -> OutcomeObservation:
    old = db.get(OutcomeObservation, observation_id)
    if old is None or str(old.business_id) != str(business_id):
        raise NotFoundError(f"Observation {observation_id} not found.")
    if not old.is_current:
        raise ValidationFailedError("Only the current revision of an observation can be corrected.")
    if not (reason or "").strip() or len(reason.strip()) < 3:
        raise ValidationFailedError("A correction needs a reason (it is kept with the history).")
    new_status = status or old.status
    new_value = value if value is not None else (_num(old.value) if new_status in ("observed", "incomplete") else None)
    new_cov = covered_until if covered_until is not None else old.covered_until
    new_reason = unavailable_reason if unavailable_reason is not None else old.unavailable_reason
    v, r, cov_until, cov_days = _validated_fields(new_status, new_value, new_reason, new_cov, old.window_start, old.window_end, clock.today())
    if new_status == old.status and v == _num(old.value) and cov_until == old.covered_until and (r or None) == (old.unavailable_reason or None):
        raise ValidationFailedError("The correction does not change anything.")
    _supersede(db, old)                     # the old revision stops being current before the new one is inserted
    row = OutcomeObservation(
        business_id=business_id, expectation_id=old.expectation_id, metric=old.metric, unit=old.unit, scope=old.scope,
        window_start=old.window_start, window_end=old.window_end, value=v, status=new_status, unavailable_reason=r, covered_until=cov_until,
        coverage_days=cov_days, window_days=old.window_days, source=old.source, provenance=old.provenance, revision=old.revision + 1,
        supersedes_id=old.id, revision_reason=reason.strip(), is_current=True, recorded_by=actor,
    )
    _insert_observation(db, row)
    return row


def derive_observation(db: Session, business_id: str, expectation_id: str, actor: str = "system:derive") -> OutcomeObservation:
    """Measure the window from the business's own uploaded data. A window with no data yet is ``pending``, never zero; a window the data
    only partly reaches is ``incomplete`` with the date it covers."""
    e = _expectation(db, business_id, expectation_id)
    w_start, w_end = e.window_start, e.window_end
    if e.metric in ("units_sold", "revenue"):
        frontier = db.query(func.max(Sale.sale_date)).filter(Sale.business_id == business_id).scalar()
        source = "derived_from_sales"
    elif e.metric == "marketing_spend":
        frontier = db.query(func.max(MarketingCampaign.campaign_date)).filter(MarketingCampaign.business_id == business_id).scalar()
        source = "derived_from_marketing"
    else:
        raise ValidationFailedError(f"'{e.metric}' cannot be derived from uploaded data (orders are not recorded as order ids); "
                                    "record the observation yourself.")
    status: str
    value: float | None = None
    reason: str | None = None
    covered: date | None = None
    if frontier is None or frontier < w_start:
        status, reason = "pending", "no uploaded data reaches the start of this window yet"
    else:
        upto = min(frontier, w_end)
        if e.metric == "marketing_spend":
            total = db.query(func.coalesce(func.sum(MarketingCampaign.spend), 0)).filter(
                MarketingCampaign.business_id == business_id, MarketingCampaign.campaign_date >= w_start, MarketingCampaign.campaign_date <= upto).scalar()
        elif e.metric == "units_sold":
            total = db.query(func.coalesce(func.sum(Sale.quantity), 0)).filter(
                Sale.business_id == business_id, Sale.sale_date >= w_start, Sale.sale_date <= upto).scalar()
        else:
            total = db.query(func.coalesce(func.sum(Sale.revenue), 0)).filter(
                Sale.business_id == business_id, Sale.sale_date >= w_start, Sale.sale_date <= upto).scalar()
        value = float(total or 0)
        if value < 0:
            status, value, reason = "invalid", None, "the net total over the window is negative (returns exceed sales)"
        elif frontier >= w_end:
            status, covered = "observed", w_end
        else:
            status, covered = "incomplete", upto
    cur = _current_for_window(db, business_id, expectation_id, e.metric, w_start, w_end)
    cov_days = ((covered - w_start).days + 1) if covered else None
    if cur is not None and cur.source == "owner_entered":
        raise ValidationFailedError("This window already has an observation entered by the owner. Correct that entry (with a reason) rather "
                                    "than replacing it with a figure measured from uploaded data.")
    if cur is not None:
        if cur.status == status and _num(cur.value) == value and cur.covered_until == covered:
            return cur                                         # idempotent: nothing new to record
        _supersede(db, cur)
        rev, sup, why = cur.revision + 1, cur.id, f"recomputed from uploaded data on {clock.today().isoformat()}"
    else:
        rev, sup, why = 1, None, None
    row = OutcomeObservation(
        business_id=business_id, expectation_id=expectation_id, metric=e.metric, unit=e.unit, scope=e.scope, window_start=w_start,
        window_end=w_end, value=value, status=status, unavailable_reason=reason, covered_until=covered, coverage_days=cov_days,
        window_days=(w_end - w_start).days + 1, source=source, provenance=_provenance_derived(db, business_id), revision=rev,
        supersedes_id=sup, revision_reason=why, is_current=True, recorded_by=actor,
    )
    _insert_observation(db, row)
    return row


def observations_of(db: Session, business_id: str, expectation_id: str, current_only: bool = False) -> list[OutcomeObservation]:
    q = db.query(OutcomeObservation).filter(OutcomeObservation.business_id == business_id, OutcomeObservation.expectation_id == expectation_id)
    if current_only:
        q = q.filter(OutcomeObservation.is_current.is_(True))
    return q.order_by(OutcomeObservation.created_at, OutcomeObservation.revision).all()


# ------------------------------------------------------------------------------------------------ comparison
def compare(db: Session, e: TrackedExpectation, obs: OutcomeObservation | None) -> dict[str, Any]:
    """Expected vs observed under the rules in BUSINESS_OUTCOME_TRACKING.md section 3. ``signed_error = expected - observed``."""
    base = {"expectation_id": str(e.id), "metric": e.metric, "unit": e.unit, "source_kind": e.source_kind, "horizon_days": e.horizon_days,
            "window": [e.window_start.isoformat(), e.window_end.isoformat()], "expected": _num(e.expected_value),
            "model": f"{e.model_name} {e.model_version}".strip() if e.model_name else None, "created_at": e.created_at.isoformat() if e.created_at else None,
            "data_cutoff": e.data_cutoff.isoformat() if e.data_cutoff else None,
            "data_cutoff_provenance": (e.config_json or {}).get("cutoff_provenance"),
            "horizon_provenance": (e.config_json or {}).get("horizon_provenance"),
            "calendar": "calendar dates without a time zone", "granularity": "business total over the window"}

    def out(status: str, reason: str, **kw: Any) -> dict[str, Any]:
        return {**base, "status": status, "reason": reason, **kw}

    if obs is None:
        return out("excluded", "missing_observation: nothing has been recorded for this window yet (it is not treated as zero)")
    if obs.status in ("pending", "invalid") or obs.value is None:
        return out("excluded", f"observation_{obs.status}: " + (obs.unavailable_reason or "no value"), observation_id=str(obs.id))
    if str(obs.business_id) != str(e.business_id):
        return out("excluded", "business_mismatch: the observation belongs to a different business", observation_id=str(obs.id))
    if (obs.metric, obs.unit, obs.scope) != (e.metric, e.unit, e.scope):
        return out("excluded", "metric_mismatch: the observation is not the same metric, unit and scope", observation_id=str(obs.id))
    if not e.comparable_to_actuals:
        return out("excluded", "not_comparable: " + (e.comparability_reason or "the expectation is not on the business's own scale"),
                   observation_id=str(obs.id), observed=_num(obs.value))
    if e.data_cutoff is None and e.source_kind != "owner_plan":
        return out("excluded", "cutoff_unknown: the data cutoff of this expectation is not known, so out-of-sample cannot be established",
                   observation_id=str(obs.id))
    if str((e.config_json or {}).get("cutoff_provenance", "")).startswith("inferred"):
        return out("excluded", "cutoff_inferred: the data cutoff was reconstructed, not recorded, so it cannot be shown that the observed "
                   "period lies after the data the expectation used", observation_id=str(obs.id), cutoff_inferred=True)
    if e.data_cutoff is not None and obs.window_start <= e.data_cutoff:
        return out("excluded", "in_sample: the observed window overlaps data the expectation could already see; it is not out-of-sample",
                   observation_id=str(obs.id))
    if (obs.window_start, obs.window_end) != (e.window_start, e.window_end):
        return out("excluded", "window_mismatch: the observation covers a different period from the expectation", observation_id=str(obs.id))
    observed = float(obs.value)
    expected = _num(e.expected_value)
    partial = obs.status == "incomplete"
    if partial:
        if not e.points_json:
            return out("excluded", "partial_period_without_daily_expectation: the expectation has no per-day values to compare a partial period",
                       observation_id=str(obs.id))
        cov = obs.covered_until
        expected = sum(float(p["value"]) for p in e.points_json if date.fromisoformat(p["date"]) <= cov)
    if expected is None:
        return out("excluded", "no_expected_value", observation_id=str(obs.id))
    err = expected - observed
    res = {
        "status": "partial" if partial else "evaluated",
        "reason": ("partial_period: compared over the first " + f"{obs.coverage_days} of {obs.window_days} days only") if partial else "same metric, unit, scope and window; after the data cutoff",
        "observation_id": str(obs.id), "observed": observed, "expected_compared": expected, "signed_error": err, "abs_error": abs(err),
        "abs_pct_error": (abs(err) / observed) if observed >= MIN_PCT_DENOMINATOR else None,
        "abs_pct_error_note": None if observed >= MIN_PCT_DENOMINATOR else
        f"unavailable: the observed value is below {MIN_PCT_DENOMINATOR:g} {e.unit}, so a percentage would be meaningless or infinite",
        "error_convention": "expected - observed (positive = over-forecast)",
        "coverage_fraction": (obs.coverage_days / obs.window_days) if partial else 1.0, "provenance": obs.provenance, "source": obs.source,
    }
    refs = e.reference_json or {}
    if not partial:
        res["references"] = {k: {"value": v, "abs_error": abs(float(v) - observed)} for k, v in refs.items() if k.endswith("_total") and _num(v) is not None}
        n = res["references"].get("naive_last_total")
        if n and n["abs_error"] > 0:
            res["abs_error_vs_naive_ratio"] = res["abs_error"] / n["abs_error"]
    if e.metric == "units_sold" and obs.source == "derived_from_sales" and e.points_json:
        cov_end = obs.covered_until or e.window_end
        rows = (db.query(Sale.sale_date, func.sum(Sale.quantity)).filter(Sale.business_id == e.business_id, Sale.sale_date >= e.window_start,
                                                                       Sale.sale_date <= cov_end).group_by(Sale.sale_date).all())
        actual = {d: float(q) for d, q in rows}
        hits = tot = 0
        for p in e.points_json:
            d = date.fromisoformat(p["date"])
            if d > cov_end:
                continue
            tot += 1
            hits += int(p["lower"] <= actual.get(d, 0.0) <= p["upper"])
        res["band_days"] = {"inside": hits, "days": tot, "interval_reliable_when_shown": e.interval_reliable}
    return {**base, **res}


def comparison_for(db: Session, business_id: str, expectation_id: str) -> dict[str, Any]:
    e = _expectation(db, business_id, expectation_id)
    obs = observations_of(db, business_id, expectation_id, current_only=True)
    cur = next((o for o in obs if (o.window_start, o.window_end) == (e.window_start, e.window_end)), obs[0] if obs else None)
    return compare(db, e, cur)


# ------------------------------------------------------------------------------------------------ report
def _impact_for_decision(resp: DecisionResponse | None, comparisons: list[dict[str, Any]]) -> dict[str, Any]:
    executed = resp is not None and resp.action_status in ("executed", "partially_executed")
    reasons = []
    if resp is None or resp.response == "pending":
        reasons.append("no response to the recommendation has been recorded")
    elif not executed:
        reasons.append(f"the action is recorded as '{resp.action_status}', not as carried out")
    if resp is None or resp.evaluation_design in (None, "none"):
        reasons.append("no evaluation design (control group or randomised holdout) has been declared")
    if not any(c["status"] in ("evaluated", "partial") for c in comparisons):
        reasons.append("no comparable observed outcome exists yet")
    reasons.append("a prediction that preceded an outcome is not attribution; other changes in the business are not controlled for")
    return {
        "causal_impact": "not_identified", "reasons": reasons,
        "action_recorded_as": resp.action_status if resp else "unknown", "response": resp.response if resp else "pending",
        "other_known_changes": (resp.known_changes_json if resp else None) or [],
        "declared_evaluation_design": resp.evaluation_design if resp else "none",
        "note": "DecisionGPT does not compute an effect in this module; a causal estimate needs a design and the causal module's classification",
    }


def report(db: Session, business_id: str) -> dict[str, Any]:
    """The outcome report, read from ONE consistent snapshot (see ``app.db.snapshot``): a snapshot saved or an observation corrected while the
    report is being built can never make its lists and counts disagree."""
    with read_snapshot(db):
        return _report(db, business_id)


def _report(db: Session, business_id: str) -> dict[str, Any]:
    decisions = db.query(Decision).filter(Decision.business_id == business_id).order_by(Decision.created_at).all()
    latest: dict[str, DecisionResponse] = {}
    for r in db.query(DecisionResponse).filter(DecisionResponse.business_id == business_id).order_by(DecisionResponse.seq).all():
        latest[str(r.decision_id)] = r
    exps = db.query(TrackedExpectation).filter(TrackedExpectation.business_id == business_id).order_by(TrackedExpectation.created_at).all()
    cur_obs: dict[str, list[OutcomeObservation]] = {}
    listed = {str(e.id) for e in exps}
    for o in db.query(OutcomeObservation).filter(OutcomeObservation.business_id == business_id, OutcomeObservation.is_current.is_(True)).all():
        if str(o.expectation_id) in listed:
            cur_obs.setdefault(str(o.expectation_id), []).append(o)

    comparisons: list[dict[str, Any]] = []
    for e in exps:
        obs = cur_obs.get(str(e.id), [])
        pick = next((o for o in obs if (o.window_start, o.window_end) == (e.window_start, e.window_end)), obs[0] if obs else None)
        comparisons.append(compare(db, e, pick))

    resp_counts = {k: 0 for k in RESPONSES}
    action_counts = {k: 0 for k in ACTION_STATUSES}
    for d in decisions:
        r = latest.get(str(d.id))
        resp_counts[r.response if r else "pending"] += 1
        action_counts[r.action_status if r else "unknown"] += 1
    obs_status = {k: 0 for k in OBS_STATUSES}
    for obs in cur_obs.values():
        for o in obs:
            obs_status[o.status] += 1
    missing = sum(1 for e in exps if str(e.id) not in cur_obs)

    by_status: dict[str, int] = {}
    reasons: dict[str, int] = {}
    for c in comparisons:
        by_status[c["status"]] = by_status.get(c["status"], 0) + 1
        if c["status"] == "excluded":
            key = c["reason"].split(":")[0]
            reasons[key] = reasons.get(key, 0) + 1
    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for c in comparisons:
        if c["status"] == "evaluated":                      # partial and excluded comparisons never contribute to an aggregate
            groups.setdefault((c["metric"], c["source_kind"], _horizon_bucket(c["horizon_days"])), []).append(c)
    accuracy = []
    for (metric, source_kind, bucket), rows in sorted(groups.items()):
        errs = np.array([r["signed_error"] for r in rows], dtype=float)
        obs_vals = np.array([r["observed"] for r in rows], dtype=float)
        pct = [r["abs_pct_error"] for r in rows if r["abs_pct_error"] is not None]
        item = {"metric": metric, "unit": METRICS[metric], "source_kind": source_kind, "horizon": bucket, "n": len(rows),
                "mean_abs_error": float(np.abs(errs).mean()), "mean_signed_error": float(errs.mean()),
                "wape": float(np.abs(errs).sum() / obs_vals.sum()) if obs_vals.sum() > 0 else None,
                "mean_abs_pct_error": float(np.mean(pct)) if pct else None, "pct_error_n": len(pct),
                "pct_error_unavailable_n": len(rows) - len(pct), "summarised": len(rows) >= MIN_COMPARABLE_FOR_SUMMARY}
        if not item["summarised"]:
            item.update(mean_abs_error=None, mean_signed_error=None, wape=None, mean_abs_pct_error=None,
                        note=f"fewer than {MIN_COMPARABLE_FOR_SUMMARY} comparable cases: listed individually, not summarised")
        accuracy.append(item)

    impact = []
    for d in decisions:
        r = latest.get(str(d.id))
        comps = [c for c, e in zip(comparisons, exps) if e.decision_id and str(e.decision_id) == str(d.id)]
        impact.append({"decision_id": str(d.id), "created_at": d.created_at.isoformat() if d.created_at else None, **_impact_for_decision(r, comps)})

    legacy = (db.query(func.count(DecisionOutcome.id)).join(Decision, Decision.id == DecisionOutcome.decision_id)
              .filter(Decision.business_id == business_id).scalar() or 0)
    prov: dict[str, int] = {}
    for e in exps:
        prov[e.provenance] = prov.get(e.provenance, 0) + 1
    for obs in cur_obs.values():
        for o in obs:
            prov[o.provenance] = prov.get(o.provenance, 0) + 1
    awaiting = []
    for e in exps:
        obs = cur_obs.get(str(e.id), [])
        done = any(o.status == "observed" and (o.window_start, o.window_end) == (e.window_start, e.window_end) for o in obs)
        if not done:
            state = "no observation yet" if not obs else "/".join(sorted({o.status for o in obs}))
            awaiting.append({"expectation_id": str(e.id), "source_kind": e.source_kind, "metric": e.metric, "unit": e.unit,
                             "window": [e.window_start.isoformat(), e.window_end.isoformat()], "window_finished": e.window_end < clock.today(),
                             "state": state, "comparable_to_actuals": e.comparable_to_actuals})
    with_obs = [c for c in comparisons if "observation_id" in c]
    cmp_ok = [c for c in with_obs if c["status"] in ("evaluated", "partial")]
    cmp_no = [c for c in with_obs if c["status"] == "excluded"]
    cover = [c.get("coverage_fraction", 1.0) for c in cmp_ok]
    dates = [c["window"] for c in comparisons if c["status"] in ("evaluated", "partial")]
    n_eval = by_status.get("evaluated", 0)
    return {
        "generated_at": utcnow().isoformat(), "business_scope": "this business only",
        "decisions": {"recorded": len(decisions), "latest_response": resp_counts, "action_status": action_counts,
                      "executed_confirmed": action_counts["executed"], "partially_executed": action_counts["partially_executed"]},
        "expectations": {"recorded": len(exps), "by_source": {k: sum(1 for e in exps if e.source_kind == k) for k in SOURCE_KINDS},
                         "comparable_to_actuals": sum(1 for e in exps if e.comparable_to_actuals),
                         "not_comparable": sum(1 for e in exps if not e.comparable_to_actuals)},
        "observations": {"by_status": obs_status, "expectations_without_any_observation": missing,
                         "comparable": len(cmp_ok), "not_comparable": len(cmp_no),
                         "mean_coverage_fraction": float(np.mean(cover)) if cover else None},
        "awaiting_actuals": awaiting,
        "comparisons": {"by_status": by_status, "excluded_reasons": reasons, "details": comparisons},
        "forecast_accuracy": {"groups": accuracy, "sample_size": n_eval, "aggregation_rule": AGGREGATION_RULE,
                              "coverage": {"compared_in_full": n_eval, "partial_not_aggregated": by_status.get("partial", 0),
                                           "withheld_not_aggregated": by_status.get("excluded", 0), "expectations": len(exps)},
                              "date_range": [min(w[0] for w in dates), max(w[1] for w in dates)] if dates else None,
                              "statement": (f"{n_eval} comparable forecast(s) with observed actuals; errors are listed by metric and horizon."
                                            if n_eval >= MIN_COMPARABLE_FOR_SUMMARY else
                                            f"Accuracy cannot yet be summarised: {n_eval} comparable case(s); at least {MIN_COMPARABLE_FOR_SUMMARY} are needed "
                                            "(provisional engineering policy).")},
        "business_impact": {"status": "not_evaluable",
                            "statement": ("Business impact cannot be evaluated from these records: a forecast being accurate does not show that a "
                                          "recommendation helped, and no recorded decision has a declared design with control observations."),
                            "per_decision": impact},
        "data_provenance": prov, "legacy_free_form_outcomes": {"recorded": int(legacy), "status": "unverified comparison: no window, units or scope; not used for accuracy or causal claims"},
        "limitations": LIMITATIONS + ["Observations entered by the owner cannot be verified by DecisionGPT.",
                                      "Demo or synthetic businesses are labelled demo_synthetic and are never evidence about real businesses."],
    }
