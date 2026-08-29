"""Research Console — Real Indian SME decision-outcome capture & validation
(docs/REAL_INDIAN_SME_OUTCOME_VALIDATION.md).

Evidence-generation, NOT optimization. This module lets a genuine Indian SME
contribute an **anonymised, aggregate** decision-outcome record and then
evaluates DecisionGPT's prediction against that real outcome. It reuses the
existing `DecisionOutcome` / `PredictionEvaluation` / Digital-Twin-evaluation
pipeline unchanged — it only adds:
  * a documented import schema (docs/templates/real_indian_sme_outcome_template.*),
  * `validate_record` — schema + anonymisation + horizon-consistency + PII rejection,
  * `import_outcome_record` — creates an anonymised Business + Decision +
    DecisionOutcome (source_type = real_indian_sme) and the PredictionEvaluation,
  * `get_real_sme_outcome_report` — Table-2 material restricted to real SME
    outcomes, per target (revenue / profit / units), with an honest empty state.

HARD RULES (docs task §3, §23):
  * NEVER fabricate a `DecisionOutcome`. Synthetic scenarios stay labelled
    SYNTHETIC_* and never enter this table.
  * If no real records exist: n = 0, Table 2 = NOT READY. That is a valid result.
  * Production defaults are unchanged (risk_model=None, risk_penalty_lambda=1.0).
"""
from __future__ import annotations

import math
import re
from datetime import date, datetime, timezone

from sqlalchemy.orm import Session

from app.core.errors import ValidationFailedError
from app.models.business import Business
from app.models.decision import (
    OUTCOME_SOURCE_REAL_INDIAN_SME,
    REAL_SME_OUTCOME_CATEGORY,
    Decision,
    DecisionOutcome,
)
from app.models.evaluation import PredictionEvaluation
from app.models.goal import Goal
from app.models.strategy import Strategy
from app.services import digital_twin_evaluation_service as dte

# --- import schema (kept minimal; mirrors docs/templates/*) --------------

SUPPORTED_DECISION_TYPES = {
    "price_increase", "price_decrease", "marketing_increase",
    "marketing_decrease", "inventory_decision",
}
SUPPORTED_HORIZON_DAYS = {7, 14, 30, 60, 90}
SUPPORTED_OUTCOME_STATUS = {"achieved", "partially_achieved", "not_achieved", "inconclusive"}

REQUIRED_FIELDS = [
    "business_id", "industry", "state", "district",
    "decision_date", "decision_type", "goal", "strategy", "prediction_horizon_days",
    "baseline_revenue", "predicted_revenue", "actual_revenue",
    "predicted_confidence", "predicted_risk",
    "outcome_recorded_date", "outcome_status",
    # provenance (task §15)
    "source_type", "business_country", "data_consent_status",
    "anonymization_status", "collection_method",
]
OPTIONAL_NUMERIC = [
    "baseline_profit", "predicted_profit", "actual_profit",
    "baseline_units", "predicted_units", "actual_units",
    "historical_price_min", "historical_price_max", "historical_price_median",
]

# field names that must NOT appear — this record is business-level & anonymised
_FORBIDDEN_KEYS = re.compile(
    r"(aadhaar|aadhar|\bpan\b|gstin?|phone|mobile|email|bank|account_no|"
    r"account_number|ifsc|customer_name|customer_id|owner|contact|address|pincode)",
    re.I,
)
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(r"(?<!\d)(?:\+?91[\-\s]?)?[6-9]\d{9}(?!\d)")
_LONGNUM_RE = re.compile(r"(?<!\d)\d{11,}(?!\d)")   # Aadhaar (12) / account numbers
_ANON_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_\-]{1,63}$")


def _num(v):
    try:
        f = float(v)
        return f if math.isfinite(f) else None
    except (TypeError, ValueError):
        return None


def _reject_pii(record: dict) -> list[str]:
    errs: list[str] = []
    for k, v in record.items():
        if _FORBIDDEN_KEYS.search(str(k)):
            errs.append(f"field '{k}' is not allowed — records must be business-level and anonymised")
        s = str(v)
        if _EMAIL_RE.search(s):
            errs.append(f"field '{k}' looks like an email address — remove personal contact info")
        if _PHONE_RE.search(s):
            errs.append(f"field '{k}' looks like an Indian phone number — remove personal contact info")
        if _LONGNUM_RE.search(s):
            errs.append(f"field '{k}' contains an 11+ digit number — possible Aadhaar / account number")
    return errs


def validate_record(record: dict) -> list[str]:
    """Return a list of validation errors ([] == valid). Never raises."""
    errs: list[str] = []
    if not isinstance(record, dict):
        return ["record must be a JSON object"]

    for f in REQUIRED_FIELDS:
        if record.get(f) in (None, ""):
            errs.append(f"missing required field: {f}")

    errs += _reject_pii(record)

    # anonymisation / provenance (task §3, §15)
    if str(record.get("source_type", "")).strip().lower() != OUTCOME_SOURCE_REAL_INDIAN_SME:
        errs.append(
            f"source_type must be '{OUTCOME_SOURCE_REAL_INDIAN_SME}' — synthetic / demo / unknown "
            "records must NEVER enter the real-outcome table")
    if str(record.get("business_country", "")).strip().upper() not in ("IN", "IND", "INDIA"):
        errs.append("business_country must be India (IN)")
    if str(record.get("anonymization_status", "")).strip().lower() not in ("anonymized", "anonymised"):
        errs.append("anonymization_status must be 'anonymized'")
    if str(record.get("data_consent_status", "")).strip().lower() not in (
        "consented", "consent_given", "granted"):
        errs.append("data_consent_status must record explicit consent (e.g. 'consented')")
    bid = str(record.get("business_id", ""))
    if bid and (not _ANON_ID_RE.match(bid) or _EMAIL_RE.search(bid) or _PHONE_RE.search(bid)):
        errs.append("business_id must be an anonymised token (letters/digits/_/-), not a name or contact")

    # decision type + capability (task §7 — capability system unchanged)
    dtp = str(record.get("decision_type", "")).strip().lower()
    if dtp and dtp not in SUPPORTED_DECISION_TYPES:
        errs.append(f"decision_type '{dtp}' is not one the Digital Twin can simulate "
                    f"({sorted(SUPPORTED_DECISION_TYPES)})")
    if dtp in ("marketing_increase", "marketing_decrease") and _num(record.get("baseline_units")) is None:
        errs.append("a marketing decision needs baseline_units so the outcome can be evaluated")

    # horizon (task §8)
    h = record.get("prediction_horizon_days")
    try:
        h = int(h)
    except (TypeError, ValueError):
        h = None
    if h not in SUPPORTED_HORIZON_DAYS:
        errs.append(f"prediction_horizon_days must be one of {sorted(SUPPORTED_HORIZON_DAYS)}")

    st = str(record.get("outcome_status", "")).strip().lower()
    if st and st not in SUPPORTED_OUTCOME_STATUS:
        errs.append(f"outcome_status must be one of {sorted(SUPPORTED_OUTCOME_STATUS)}")

    # dates + horizon-consistency / no-leakage (task §8, §22)
    d0 = _parse_date(record.get("decision_date"))
    d1 = _parse_date(record.get("outcome_recorded_date"))
    if record.get("decision_date") and d0 is None:
        errs.append("decision_date is not a valid YYYY-MM-DD date")
    if record.get("outcome_recorded_date") and d1 is None:
        errs.append("outcome_recorded_date is not a valid YYYY-MM-DD date")
    if d0 and d1:
        if d1 < d0:
            errs.append("outcome_recorded_date is before decision_date")
        elif h is not None:
            gap = (d1 - d0).days
            if not (h * 0.5 <= gap <= h * 2.0 + 7):
                errs.append(
                    f"outcome window ({gap} days) does not match the stated "
                    f"{h}-day horizon — a {h}-day prediction cannot be compared with a {gap}-day actual")

    # numerics
    for f in ("baseline_revenue", "predicted_revenue", "actual_revenue",
              "predicted_confidence", "predicted_risk", *OPTIONAL_NUMERIC):
        if record.get(f) not in (None, "") and _num(record.get(f)) is None:
            errs.append(f"field '{f}' must be numeric")
    for f in ("predicted_confidence", "predicted_risk"):
        v = _num(record.get(f))
        if v is not None and not (0.0 <= v <= 1.0):
            errs.append(f"{f} must be in [0, 1]")
    return errs


def _parse_date(v) -> date | None:
    if isinstance(v, date):
        return v
    try:
        return datetime.strptime(str(v).strip(), "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def _get_or_make_business(db: Session, record: dict) -> str:
    token = str(record["business_id"]).strip()
    name = f"Anonymised Indian SME [{token}]"
    biz = db.query(Business).filter(Business.name == name).first()
    if biz is not None:
        return biz.id
    biz = Business(
        name=name, industry=str(record.get("industry", "unspecified"))[:100],
        business_type="Real (anonymised, research outcome only)", business_size="SME",
        country="IN", currency="INR",
        description=f"Anonymised aggregate record — {REAL_SME_OUTCOME_CATEGORY}. "
                    f"State {record.get('state')}, district {record.get('district')}. "
                    "No transaction-level or personal data.",
    )
    db.add(biz)
    db.flush()
    return biz.id


def _natural_key(record: dict) -> str:
    """Stable identity of one SME decision record — used only for duplicate
    detection (task §10). Anonymised token + date + intervention; no PII."""
    return "|".join(str(record.get(k, "")).strip().lower() for k in
                    ("business_id", "decision_date", "decision_type", "strategy",
                     "prediction_horizon_days"))


def import_outcome_record(db: Session, record: dict) -> dict:
    """Validate and persist ONE anonymised real Indian SME decision outcome.
    Raises ValidationFailedError with the full error list on any problem, or a
    'duplicate' error if this exact decision record was already imported."""
    errs = validate_record(record)
    if errs:
        raise ValidationFailedError("real SME outcome record failed validation", details={"errors": errs})

    nkey = _natural_key(record)
    dup = (db.query(Decision)
           .join(DecisionOutcome, DecisionOutcome.decision_id == Decision.id)
           .filter(DecisionOutcome.source_type == OUTCOME_SOURCE_REAL_INDIAN_SME)
           .all())
    for d in dup:
        if (d.expected_outcome_json or {}).get("_sme_natural_key") == nkey:
            raise ValidationFailedError(
                "duplicate: this real SME decision record was already imported",
                details={"errors": [f"a decision outcome for '{nkey}' already exists "
                                    f"(decision {d.id})"]})

    business_id = _get_or_make_business(db, record)
    horizon = int(record["prediction_horizon_days"])

    goal = Goal(
        business_id=business_id, objective=str(record.get("goal", "increase_revenue"))[:100],
        target_value=0.0, target_unit="percent", primary_kpi="revenue",
        time_horizon=max(1, round(horizon / 30)), status="closed",
    )
    db.add(goal)
    db.flush()

    strat = Strategy(
        business_id=business_id, goal_id=goal.id,
        strategy_name=str(record.get("strategy", record.get("decision_type")))[:120],
        description="Recorded real SME intervention (anonymised).", actions_json=[],
    )
    db.add(strat)
    db.flush()

    # expected_outcome_json is built ONLY from the SME's reported predicted /
    # baseline figures — never from the actual outcome. This is the no-leakage
    # guarantee at the record level (see test_no_leakage_*).
    expected = {
        "baseline_revenue": _num(record.get("baseline_revenue")),
        "expected_revenue": _num(record.get("predicted_revenue")),
        "baseline_profit": _num(record.get("baseline_profit")),
        "expected_profit": _num(record.get("predicted_profit")),
        "baseline_units_sold": _num(record.get("baseline_units")),
        "expected_units_sold": _num(record.get("predicted_units")),
        "risk_score": _num(record.get("predicted_risk")),
        "_sme_natural_key": _natural_key(record),   # dedup only; anonymised, ignored by evaluators
    }
    decision = Decision(
        business_id=business_id, goal_id=goal.id, selected_strategy_id=strat.id,
        expected_outcome_json={k: v for k, v in expected.items() if v is not None},
        risk_level="medium", confidence=_num(record.get("predicted_confidence")),
        reasoning="Imported anonymised real Indian SME decision (research outcome validation).",
        prompt_version="real_sme_import_v1",
        model_versions_json={"note": "prediction as reported by the SME's own DecisionGPT run "
                                     "(production config R0); not recomputed here"},
    )
    db.add(decision)
    db.flush()

    actual = {
        "revenue": _num(record.get("actual_revenue")),
        "profit": _num(record.get("actual_profit")),
        "units": _num(record.get("actual_units")),
    }
    actual = {k: v for k, v in actual.items() if v is not None}
    goal_achieved = str(record.get("outcome_status", "")).lower() == "achieved"

    outcome = DecisionOutcome(
        decision_id=decision.id, actual_outcome_json=actual,
        goal_achieved=goal_achieved, goal_achievement_score=None,
        recorded_at=(datetime.combine(_parse_date(record["outcome_recorded_date"]),
                                      datetime.min.time(), tzinfo=timezone.utc)),
        outcome_horizon_days=horizon,
        outcome_status=str(record["outcome_status"]).lower(),
        notes=str(record.get("notes", ""))[:2000] or None,
        source_type=OUTCOME_SOURCE_REAL_INDIAN_SME,
        business_country="IN",
        business_industry=str(record.get("industry", ""))[:80] or None,
        data_consent_status=str(record["data_consent_status"]).lower(),
        anonymization_status="anonymized",
        collection_method=str(record["collection_method"])[:60],
        collection_date=_parse_date(record.get("collection_date")) or _parse_date(record["outcome_recorded_date"]),
    )
    db.add(outcome)
    db.flush()

    dte.evaluate_decision_outcome(db, decision, outcome)
    db.commit()
    return {
        "imported": True, "business_id": business_id, "decision_id": decision.id,
        "outcome_id": outcome.id, "source_type": OUTCOME_SOURCE_REAL_INDIAN_SME,
        "data_category": REAL_SME_OUTCOME_CATEGORY,
    }


# --- reporting (Table 2 material; honest empty state) -------------------

def _real_sme_outcomes(db: Session):
    return (db.query(DecisionOutcome)
            .filter(DecisionOutcome.source_type == OUTCOME_SOURCE_REAL_INDIAN_SME)
            .order_by(DecisionOutcome.recorded_at).all())


def _target_errors(evals: list[PredictionEvaluation], target: str) -> dict:
    errs, pcts = [], []
    for e in evals:
        m = (e.metrics_json or {}).get(target)
        if not m or m.get("error") is None:
            continue
        errs.append(float(m["error"]))
        if m.get("abs_pct_error") is not None:
            pcts.append(float(m["abs_pct_error"]))
    if not errs:
        return {"n": 0, "mae": None, "rmse": None, "mape": None}
    return {
        "n": len(errs),
        "mae": round(sum(abs(x) for x in errs) / len(errs), 2),
        "rmse": round((sum(x * x for x in errs) / len(errs)) ** 0.5, 2),
        "mape": round(sum(pcts) / len(pcts), 2) if pcts else None,
    }


def get_real_sme_outcome_report(db: Session) -> dict:
    outcomes = _real_sme_outcomes(db)
    n = len(outcomes)
    empty = {
        "data_category": REAL_SME_OUTCOME_CATEGORY,
        "collection_status": "PENDING",
        "table_2": "NOT READY",
        "n_businesses": 0, "n_decisions": 0, "n_outcomes": 0,
        "empty_state": ("No real Indian SME outcomes available. "
                        "Table 2 remains NOT READY. Synthetic outcomes are never shown here."),
        "message": ("Contribute an anonymised aggregate record via "
                    "docs/templates/real_indian_sme_outcome_template.csv and import it with "
                    "scripts/import_real_sme_outcomes.py — see "
                    "docs/REAL_INDIAN_SME_OUTCOME_VALIDATION.md."),
        "r0_vs_r3": "NOT APPLICABLE — 0 real outcomes",
        "causal_evidence": "NOT READY — 0 real outcomes "
                           f"(needs >= {_min_outcomes()} consistent per-edge interventions)",
        "statistical_inference": "DESCRIPTIVE ONLY (planned n = 5-10)",
    }
    if n == 0:
        return empty

    dte.backfill(db)
    dec_ids = [o.decision_id for o in outcomes]
    decisions = {d.id: d for d in db.query(Decision).filter(Decision.id.in_(dec_ids)).all()}
    evals = (db.query(PredictionEvaluation)
             .filter(PredictionEvaluation.outcome_id.in_([o.id for o in outcomes])).all())

    businesses = {decisions[o.decision_id].business_id for o in outcomes if o.decision_id in decisions}
    horizons = sorted({o.outcome_horizon_days for o in outcomes if o.outcome_horizon_days})
    by_type: dict[str, int] = {}
    for o in outcomes:
        d = decisions.get(o.decision_id)
        s = db.get(Strategy, d.selected_strategy_id) if d and d.selected_strategy_id else None
        key = (s.strategy_name if s else "unknown")
        by_type[key] = by_type.get(key, 0) + 1

    achieved = sum(1 for o in outcomes if o.outcome_status == "achieved")
    small = n < 5

    rows = []
    for o in outcomes:
        e = next((x for x in evals if x.outcome_id == o.id), None)
        rows.append({
            "outcome_id": o.id, "decision_id": o.decision_id,
            "business_industry": o.business_industry, "horizon_days": o.outcome_horizon_days,
            "outcome_status": o.outcome_status,
            "metrics": (e.metrics_json if e else {}),
            "source_type": o.source_type, "anonymization_status": o.anonymization_status,
        })

    return {
        "data_category": REAL_SME_OUTCOME_CATEGORY,
        "collection_status": "IN PROGRESS",
        "table_2": "READY" if n >= 5 else "NOT READY",
        "table_2_reason": None if n >= 5 else f"only {n} real outcome(s); need >= 5 for Table 2",
        "n_businesses": len(businesses), "n_decisions": len(set(dec_ids)), "n_outcomes": n,
        "decision_types": by_type, "outcome_horizons": horizons,
        "digital_twin": {
            "revenue": _target_errors(evals, "revenue"),
            "profit": _target_errors(evals, "profit"),
            "units": _target_errors(evals, "units"),
        },
        "goal_achievement": {"achieved": achieved, "n": n,
                             "rate": round(achieved / n, 4) if n else None},
        "r0_vs_r3": ("NO MEASURABLE DIFFERENCE — aggregate outcome records do not carry the price "
                     "history needed to recompute R0/R3 risk; production stays R0"),
        "confidence_calibration": "DESCRIPTIVE ONLY" if small else "assessable",
        "causal_evidence": "INSUFFICIENT — real intervention feedback is applied through the existing "
                           f"causal_feedback_service rules (>= {_min_outcomes()} consistent per-edge "
                           "outcomes); not overridden here",
        "statistical_inference": "DESCRIPTIVE ONLY" if small else "assess clustering by business first",
        "provenance": {
            "all_anonymized": all(o.anonymization_status == "anonymized" for o in outcomes),
            "all_real_source": all(o.source_type == OUTCOME_SOURCE_REAL_INDIAN_SME for o in outcomes),
            "all_india": all(o.business_country == "IN" for o in outcomes),
            "consent_recorded": all(o.data_consent_status for o in outcomes),
        },
        "rows": rows,
        "clustering_note": ("Repeated decisions from one business are clustered — do not treat every "
                            "row as an independent business."),
    }


def _min_outcomes() -> int:
    from app.services import causal_feedback_service
    return causal_feedback_service.MIN_OUTCOMES_FOR_OBSERVATIONAL
