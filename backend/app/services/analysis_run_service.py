"""Persistence helpers for saved causal / counterfactual / debate runs (``analysis_runs``)."""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.core.errors import NotFoundError, uuid_or_not_found
from app.models.platform import AnalysisRun

KINDS = ("causal", "counterfactual", "debate", "forecast_eval", "customer_eval")


def save(db: Session, business_id: str, kind: str, mode: str | None, question: str | None, params: dict[str, Any], result: dict[str, Any],
         status: str = "completed", error: str | None = None) -> AnalysisRun:
    if kind not in KINDS:
        raise ValueError(f"unknown analysis kind {kind}")
    run = AnalysisRun(business_id=business_id, kind=kind, status=status, mode=mode, question=question, params_json=params, result_json=result, error_message=error)
    db.add(run)
    db.commit()
    return run


def meta(r: AnalysisRun) -> dict[str, Any]:
    res = r.result_json or {}
    return {"id": r.id, "kind": r.kind, "status": r.status, "mode": r.mode, "question": r.question, "created_at": r.created_at.isoformat() if r.created_at else None,
            "classification": res.get("classification"), "headline": res.get("headline") or res.get("summary")}


def list_runs(db: Session, business_id: str, kind: str, limit: int = 50) -> list[dict[str, Any]]:
    rows = (db.query(AnalysisRun).filter(AnalysisRun.business_id == business_id, AnalysisRun.kind == kind)
            .order_by(AnalysisRun.created_at.desc()).limit(max(1, min(limit, 200))).all())
    return [meta(r) for r in rows]


def get(db: Session, business_id: str, run_id: str, kind: str | None = None) -> dict[str, Any]:
    run_id = uuid_or_not_found(run_id, "Analysis run not found.")
    q = db.query(AnalysisRun).filter(AnalysisRun.id == run_id, AnalysisRun.business_id == business_id)
    if kind:
        q = q.filter(AnalysisRun.kind == kind)
    r = q.first()
    if r is None:
        raise NotFoundError("Analysis run not found.")
    return {**meta(r), "params": r.params_json or {}, "result": r.result_json or {}, "error": r.error_message}
