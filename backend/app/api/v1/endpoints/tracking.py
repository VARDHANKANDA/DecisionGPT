"""Outcome tracking routes (docs/BUSINESS_OUTCOME_TRACKING.md). Mounted under ``/businesses/{business_id}`` behind
``verify_business_access``; every service call also filters by ``business_id``."""
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.tracking import DecisionResponse, OutcomeObservation, TrackedExpectation
from app.models.user import User
from app.services import outcome_tracking_service as svc

router = APIRouter()
B = "/businesses/{business_id}/tracking"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _actor(user: User | None) -> str:
    return getattr(user, "email", None) or "anonymous-local"


def _exp_out(e: TrackedExpectation) -> dict:
    return {
        "id": str(e.id), "source_kind": e.source_kind, "decision_id": str(e.decision_id) if e.decision_id else None, "question": e.question,
        "metric": e.metric, "unit": e.unit, "scope": e.scope, "window_start": e.window_start.isoformat(), "window_end": e.window_end.isoformat(),
        "horizon_days": e.horizon_days, "data_cutoff": e.data_cutoff.isoformat() if e.data_cutoff else None,
        "expected_value": float(e.expected_value) if e.expected_value is not None else None, "interval_reliable": e.interval_reliable,
        "interval_method": e.interval_method, "method": e.method, "model_name": e.model_name, "model_version": e.model_version, "basis": e.basis,
        "reference": e.reference_json, "assumptions": e.assumptions_json, "limitations": e.limitations_json,
        "comparable_to_actuals": e.comparable_to_actuals, "comparability_reason": e.comparability_reason, "input_sha256": e.input_sha256,
        "provenance": e.provenance, "created_at": e.created_at.isoformat() if e.created_at else None,
        "config": e.config_json, "points": e.points_json,
        "cutoff_provenance": (e.config_json or {}).get("cutoff_provenance"), "horizon_provenance": (e.config_json or {}).get("horizon_provenance"),
    }


def _obs_out(o: OutcomeObservation) -> dict:
    return {
        "id": str(o.id), "expectation_id": str(o.expectation_id), "metric": o.metric, "unit": o.unit, "scope": o.scope,
        "window_start": o.window_start.isoformat(), "window_end": o.window_end.isoformat(),
        "value": float(o.value) if o.value is not None else None, "status": o.status, "unavailable_reason": o.unavailable_reason,
        "covered_until": o.covered_until.isoformat() if o.covered_until else None, "coverage_days": o.coverage_days, "window_days": o.window_days,
        "source": o.source, "provenance": o.provenance, "revision": o.revision, "supersedes_id": str(o.supersedes_id) if o.supersedes_id else None,
        "revision_reason": o.revision_reason, "is_current": o.is_current, "note": o.note, "recorded_by": o.recorded_by,
        "calendar": "calendar dates without a time zone",
        "created_at": o.created_at.isoformat() if o.created_at else None,
    }


def _resp_out(r: DecisionResponse | None) -> dict:
    if r is None:
        return {"response": "pending", "action_status": "unknown", "seq": 0, "recorded": False}
    return {
        "recorded": True, "seq": r.seq, "response": r.response, "action_status": r.action_status, "action_taken": r.action_taken_json,
        "modified_action": r.modified_action_json, "action_start": r.action_start.isoformat() if r.action_start else None,
        "action_end": r.action_end.isoformat() if r.action_end else None, "known_changes": r.known_changes_json or [],
        "evaluation_design": r.evaluation_design, "follow_up_date": r.follow_up_date.isoformat() if r.follow_up_date else None,
        "note": r.note, "recorded_by": r.recorded_by, "created_at": r.created_at.isoformat() if r.created_at else None,
    }


# ------------------------------------------------------------------------------------------------ expectations
class ForecastSnapshotBody(_Strict):
    horizon_days: int = Field(default=14, ge=1, le=90)
    question: str | None = Field(default=None, max_length=500)
    # the fingerprint of the forecast the owner was shown (``fingerprint`` in the forecast response); when present the snapshot is saved
    # only if the forecast is still identical, so a saved snapshot is always one that was shown
    fingerprint: str | None = Field(default=None, min_length=64, max_length=64)


@router.post(B + "/forecasts")
def snapshot_forecast(business_id: str, body: ForecastSnapshotBody, db: Session = Depends(get_db)):
    """Save the forecast the owner chose to save, so it can be compared with actuals once the window has passed. 409 when it changed
    since it was shown; an identical forecast already saved is returned (``already_saved``), not duplicated."""
    row, info = svc.save_forecast_snapshot(db, business_id, body.horizon_days, body.question, body.fingerprint)
    return {**_exp_out(row), **info}


class OwnerPlanBody(_Strict):
    metric: Literal["units_sold", "revenue", "orders", "marketing_spend"]
    unit: str = Field(min_length=1, max_length=20)
    window_start: date
    window_end: date
    expected_value: float
    note: str | None = Field(default=None, max_length=500)


@router.post(B + "/expectations")
def create_plan(business_id: str, body: OwnerPlanBody, user: User | None = Depends(get_current_user), db: Session = Depends(get_db)):
    """An owner's own planned figure (for example planned marketing spend). Stated, not calculated by DecisionGPT."""
    from app.core.errors import ValidationFailedError
    from app.models.tracking import METRICS

    if body.unit != METRICS[body.metric]:
        raise ValidationFailedError(f"The unit for {body.metric} is '{METRICS[body.metric]}', not '{body.unit}'.")
    return _exp_out(svc.create_owner_plan(db, business_id, body.metric, body.window_start, body.window_end, body.expected_value, body.note, _actor(user)))


@router.get(B + "/expectations")
def list_expectations(business_id: str, db: Session = Depends(get_db)):
    rows = db.query(TrackedExpectation).filter(TrackedExpectation.business_id == business_id).order_by(TrackedExpectation.created_at.desc()).all()
    return {"expectations": [_exp_out(e) for e in rows]}


@router.get(B + "/expectations/{expectation_id}")
def get_expectation(business_id: str, expectation_id: str, db: Session = Depends(get_db)):
    from app.db.snapshot import read_snapshot

    with read_snapshot(db):               # the expectation, its history and the comparison come from the same moment
        e = svc._expectation(db, business_id, expectation_id)
        return {"expectation": _exp_out(e), "observations": [_obs_out(o) for o in svc.observations_of(db, business_id, expectation_id)],
                "comparison": svc.comparison_for(db, business_id, expectation_id)}


# ------------------------------------------------------------------------------------------------ observations
class ObservationBody(_Strict):
    metric: Literal["units_sold", "revenue", "orders", "marketing_spend"]
    unit: str = Field(min_length=1, max_length=20)
    status: Literal["pending", "incomplete", "observed", "invalid"]
    value: float | None = None
    unavailable_reason: str | None = Field(default=None, max_length=500)
    covered_until: date | None = None
    window_start: date | None = None
    window_end: date | None = None
    note: str | None = Field(default=None, max_length=500)


@router.post(B + "/expectations/{expectation_id}/observations")
def add_observation(business_id: str, expectation_id: str, body: ObservationBody, user: User | None = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    o = svc.record_observation(db, business_id, expectation_id, metric=body.metric, unit=body.unit, status=body.status, value=body.value,
                               unavailable_reason=body.unavailable_reason, covered_until=body.covered_until, window_start=body.window_start,
                               window_end=body.window_end, note=body.note, actor=_actor(user))
    return _obs_out(o)


class CorrectionBody(_Strict):
    reason: str = Field(min_length=3, max_length=500)
    status: Literal["pending", "incomplete", "observed", "invalid"] | None = None
    value: float | None = None
    unavailable_reason: str | None = Field(default=None, max_length=500)
    covered_until: date | None = None


@router.post(B + "/observations/{observation_id}/correction")
def correct(business_id: str, observation_id: str, body: CorrectionBody, user: User | None = Depends(get_current_user), db: Session = Depends(get_db)):
    """A correction is a new revision with a reason; the earlier value stays in the history."""
    return _obs_out(svc.correct_observation(db, business_id, observation_id, reason=body.reason, status=body.status, value=body.value,
                                            unavailable_reason=body.unavailable_reason, covered_until=body.covered_until, actor=_actor(user)))


@router.post(B + "/expectations/{expectation_id}/observations/from-data")
def derive(business_id: str, expectation_id: str, user: User | None = Depends(get_current_user), db: Session = Depends(get_db)):
    """Measure the window from this business's own uploaded data (pending when no data reaches it; never zero)."""
    return _obs_out(svc.derive_observation(db, business_id, expectation_id, _actor(user)))


# ------------------------------------------------------------------------------------------------ decisions
class ResponseBody(_Strict):
    response: Literal["pending", "accepted", "rejected", "modified", "deferred"] | None = None
    action_status: Literal["unknown", "not_executed", "partially_executed", "executed"] | None = None
    action_taken: dict | None = None
    modified_action: dict | None = None
    action_start: date | None = None
    action_end: date | None = None
    known_changes: list[str] | None = Field(default=None, max_length=20)
    evaluation_design: Literal["none", "before_after", "matched_control", "randomized"] | None = None
    follow_up_date: date | None = None
    note: str | None = Field(default=None, max_length=1000)


@router.post(B + "/decisions/{decision_id}/response")
def record_response(business_id: str, decision_id: str, body: ResponseBody, user: User | None = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    """What the owner did with a recommendation. Accepting is not executing: execution must be stated."""
    r = svc.record_response(db, business_id, decision_id, actor=_actor(user), **body.model_dump())
    exps = svc.expectations_from_decision(db, business_id, decision_id)
    return {**_resp_out(r), "expectations": [_exp_out(e) for e in exps]}


@router.get(B + "/decisions")
def list_decision_tracking(business_id: str, db: Session = Depends(get_db)):
    """The current response of every decision of this business in one call (decisions with no response are ``pending``)."""
    from app.models.decision import Decision
    from app.models.tracking import DecisionResponse as DR

    latest: dict[str, DR] = {}
    for r in db.query(DR).filter(DR.business_id == business_id).order_by(DR.seq).all():
        latest[str(r.decision_id)] = r
    ids = [str(i) for (i,) in db.query(Decision.id).filter(Decision.business_id == business_id).all()]
    return {"decisions": [{"decision_id": i, "current": _resp_out(latest.get(i))} for i in ids]}


@router.get(B + "/decisions/{decision_id}")
def get_decision_tracking(business_id: str, decision_id: str, db: Session = Depends(get_db)):
    from app.models.tracking import DecisionResponse as DR

    from app.db.snapshot import read_snapshot

    with read_snapshot(db):
        svc._decision(db, business_id, decision_id)
        history = db.query(DR).filter(DR.business_id == business_id, DR.decision_id == decision_id).order_by(DR.seq).all()
        exps = db.query(TrackedExpectation).filter(TrackedExpectation.business_id == business_id, TrackedExpectation.decision_id == decision_id).all()
        return {"current": _resp_out(history[-1] if history else None), "history": [_resp_out(h) for h in history],
                "expectations": [{"expectation": _exp_out(e), "comparison": svc.comparison_for(db, business_id, str(e.id))} for e in exps]}


@router.get(B + "/report")
def tracking_report(business_id: str, db: Session = Depends(get_db)):
    return svc.report(db, business_id)
