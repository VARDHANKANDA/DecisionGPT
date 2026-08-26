"""Research Console — Model Performance (docs Phase 1/2).

Aggregates the real MLModel registry and TrainingRun history. No metric is
computed here — every number is read from a recorded training/evaluation
run. Forecasting and classification metrics are kept in separate sections
so incompatible metrics are never compared.
"""
from sqlalchemy.orm import Session

from app.models.ml_model import MLModel
from app.models.research import ResearchDatasetVersion, TrainingRun

_FORECAST_METRICS = ["mae", "rmse", "mape"]
_CLASS_METRICS = ["precision", "recall", "f1", "roc_auc"]


def _num(v):
    return v if isinstance(v, (int, float)) else None


def _model_row(m: MLModel) -> dict:
    return {
        "id": m.id,
        "model_name": m.model_name,
        "model_type": m.model_type,
        "version": m.version,
        "status": m.status,
        "source": m.source or "cli",
        "task": m.task,
        "dataset_version": m.dataset_version,
        "training_run_id": m.training_run_id,
        "created_at": m.created_at.isoformat() if m.created_at else None,
        "metrics": {k: _num(m.metrics_json.get(k)) for k in (_FORECAST_METRICS + _CLASS_METRICS)},
    }


def _best(models: list[MLModel], metric: str, minimize: bool):
    scored = [(m, m.metrics_json.get(metric)) for m in models]
    scored = [(m, v) for (m, v) in scored if isinstance(v, (int, float))]
    if not scored:
        return None
    m, v = (min if minimize else max)(scored, key=lambda t: t[1])
    return {"metric": metric, "value": round(v, 4), "model": f"{m.model_name} {m.version}", "model_id": m.id}


def get_model_performance(
    db: Session,
    task: str | None = None,
    dataset_version: str | None = None,
    model_name: str | None = None,
    training_run_id: str | None = None,
) -> dict:
    q = db.query(MLModel)
    if dataset_version:
        q = q.filter(MLModel.dataset_version == dataset_version)
    if model_name:
        q = q.filter(MLModel.model_name == model_name)
    if training_run_id:
        q = q.filter(MLModel.training_run_id == training_run_id)
    all_models = q.order_by(MLModel.model_name, MLModel.created_at.desc()).all()

    forecasting = [m for m in all_models if m.model_type.startswith("forecasting_")]
    churn = [m for m in all_models if m.model_type.startswith("churn_")]
    if task == "forecasting":
        churn = []
    elif task == "churn":
        forecasting = []

    tr_q = db.query(TrainingRun)
    if task:
        tr_q = tr_q.filter(TrainingRun.task == task)
    training_runs = tr_q.order_by(TrainingRun.created_at.desc()).all()

    dataset_versions = sorted(
        {m.dataset_version for m in db.query(MLModel).all() if m.dataset_version}
    )
    model_names = sorted({m.model_name for m in db.query(MLModel).all()})

    empty_state = None
    if not all_models and not training_runs:
        empty_state = (
            "No evaluated models yet. Train a model from the Training Center to view performance results."
        )

    return {
        "summary": {
            "registered_models": len(all_models),
            "active_models": sum(1 for m in all_models if m.status == "active"),
            "experimental_models": sum(1 for m in all_models if m.status == "experimental"),
            "completed_training_runs": sum(1 for r in training_runs if r.status == "completed"),
            "failed_training_runs": sum(1 for r in training_runs if r.status == "failed"),
            "best_forecasting": _best(forecasting, "mae", minimize=True),
            "best_churn": _best(churn, "roc_auc", minimize=False),
        },
        "forecasting": {
            "metrics": _FORECAST_METRICS,
            "models": [_model_row(m) for m in forecasting],
            "chart": [
                {"name": f"{m.model_name} {m.version}", **{k: _num(m.metrics_json.get(k)) for k in _FORECAST_METRICS}}
                for m in forecasting
            ],
        },
        "classification": {
            "metrics": _CLASS_METRICS,
            "models": [_model_row(m) for m in churn],
            "chart": [
                {"name": f"{m.model_name} {m.version}", **{k: _num(m.metrics_json.get(k)) for k in _CLASS_METRICS}}
                for m in churn
            ],
        },
        "training_history": [
            {
                "id": r.id,
                "task": r.task,
                "model_type": r.model_type,
                "status": r.status,
                "dataset_version_label": r.dataset_version_label,
                "model_name": r.model_name,
                "model_version": r.model_version,
                "metrics": r.metrics_json,
                "started_at": r.started_at.isoformat() if r.started_at else None,
                "completed_at": r.completed_at.isoformat() if r.completed_at else None,
                "error_message": r.error_message,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in training_runs
        ],
        "filters": {
            "tasks": ["forecasting", "churn"],
            "dataset_versions": dataset_versions,
            "model_names": model_names,
        },
        "empty_state": empty_state,
    }
