"""Research Console — Experiment Runner (docs/PRD.md §12).

Every experiment runs through an explicit lifecycle
(PENDING -> RUNNING -> COMPLETED | FAILED) and records a permanent
ExperimentRun row with its dataset version, model versions, random seed,
timings and full metrics. Nothing here computes or approximates a metric
itself — it calls the real evaluation module and stores what came back
(docs/RESEARCH_SPECIFICATION.md §11).
"""
from dataclasses import asdict

from sqlalchemy.orm import Session

from app.core.errors import ValidationFailedError
from app.models.evaluation import PredictionEvaluation
from app.models.experiment import (
    STATUS_COMPLETED,
    STATUS_FAILED,
    STATUS_PENDING,
    STATUS_RUNNING,
    ExperimentRun,
)
from app.services import (
    ablation_service,
    causal_evaluation_service,
    decision_architecture_service,
    digital_twin_evaluation_service,
)

SUPPORTED_EXPERIMENT_TYPES = {
    "forecasting",
    "churn",
    "digital_twin",
    "causal",
    "decision_architecture",
    "multi_agent",
    "ablation",
}


def _active_forecasting_versions(db: Session) -> dict:
    """The forecasting model versions the decision pipeline actually used at
    run time — recorded so a decision-architecture / digital-twin experiment
    is reproducible against the same registry state."""
    from app.analytics.forecast_service import FORECAST_MODEL_CANDIDATES
    from app.services import model_registry_service

    out = {}
    for name in FORECAST_MODEL_CANDIDATES:
        m = model_registry_service.get_active_model(db, name)
        if m is not None:
            out[name] = m.version
    return out


def _dispatch(db: Session, experiment_type: str, configuration: dict) -> tuple[dict, str | None, dict]:
    """Returns (metrics, dataset_version, model_versions)."""
    seed = int(configuration.get("seed", 42))

    if experiment_type == "forecasting":
        from ml.training.train_forecasting import run as train_forecasting

        result = train_forecasting(random_seed=seed)
        return (
            result["results"],
            result["dataset_version"],
            {f"sales_forecast_{k}": "v1" for k in result["results"]},
        )

    if experiment_type == "churn":
        from ml.training.train_churn import run as train_churn

        result = train_churn(random_seed=seed)
        return (
            result["results"],
            result["dataset_version"],
            {f"churn_{k}": "v1" for k in result["results"]},
        )

    if experiment_type == "digital_twin":
        evaluation = digital_twin_evaluation_service.run_digital_twin_evaluation(db)
        model_versions: dict = {}
        for row in db.query(PredictionEvaluation).all():
            model_versions.update(row.model_versions_json or {})
        return asdict(evaluation), "real_recorded_outcomes", model_versions

    if experiment_type == "causal":
        evaluation = causal_evaluation_service.run_causal_evaluation(seed=seed)
        return asdict(evaluation), "synthetic_causal_validation", {"method": "granger_causality"}

    if experiment_type == "decision_architecture":
        run_result = decision_architecture_service.run_decision_architecture_experiment(db, seed=seed)
        return asdict(run_result), "synthetic_scenario", _active_forecasting_versions(db)

    if experiment_type == "multi_agent":
        run_result = decision_architecture_service.run_decision_architecture_experiment(db, seed=seed)
        by_arch = {r.architecture: asdict(r) for r in run_result.results}
        return (
            {"single_agent": by_arch["C"], "multi_agent": by_arch["D"]},
            "synthetic_scenario",
            _active_forecasting_versions(db),
        )

    # ablation
    ablation_result = ablation_service.run_ablation_study(db, seed=seed)
    model_versions = dict(ablation_result.model_versions or {})
    model_versions.update(_active_forecasting_versions(db))
    return asdict(ablation_result), "synthetic_scenario", model_versions


def run_experiment(db: Session, experiment_type: str, configuration: dict | None = None) -> ExperimentRun:
    if experiment_type not in SUPPORTED_EXPERIMENT_TYPES:
        raise ValidationFailedError(
            f"Unsupported experiment_type '{experiment_type}'.",
            details={"supported_types": sorted(SUPPORTED_EXPERIMENT_TYPES)},
        )

    configuration = configuration or {}
    seed = int(configuration.get("seed", 42))

    run = ExperimentRun(
        experiment_name=configuration.get("name", experiment_type),
        experiment_type=experiment_type,
        configuration_json=configuration,
        metrics_json={},
        random_seed=seed,
        status=STATUS_PENDING,
    )
    db.add(run)
    db.flush()
    run.mark_running()
    db.commit()

    try:
        metrics, dataset_version, model_versions = _dispatch(db, experiment_type, configuration)
    except Exception as exc:  # noqa: BLE001 - record + surface, never swallow
        db.rollback()
        run = db.get(ExperimentRun, run.id)
        run.mark_failed(str(exc))
        db.commit()
        db.refresh(run)
        raise ValidationFailedError(
            f"Experiment '{experiment_type}' failed: {exc}",
            details={"experiment_id": run.id, "status": STATUS_FAILED},
        )

    run.dataset_version = dataset_version
    run.metrics_json = metrics
    run.model_versions_json = model_versions or {}
    run.mark_completed()
    db.commit()
    db.refresh(run)
    return run


def list_experiments(db: Session, experiment_type: str | None = None) -> list[ExperimentRun]:
    query = db.query(ExperimentRun)
    if experiment_type:
        query = query.filter(ExperimentRun.experiment_type == experiment_type)
    return query.order_by(ExperimentRun.created_at.desc()).all()


def get_experiment(db: Session, experiment_id: str) -> ExperimentRun | None:
    return db.get(ExperimentRun, experiment_id)


def _metric_summary(run: ExperimentRun) -> dict:
    """A small, type-appropriate headline metric set for the manifest —
    read straight from what was stored, nothing recomputed."""
    m = run.metrics_json or {}
    t = run.experiment_type
    if t in ("forecasting",):
        return {k: {"mae": v.get("mae"), "rmse": v.get("rmse"), "mape": v.get("mape")} for k, v in m.items() if isinstance(v, dict)}
    if t in ("churn",):
        return {k: {"f1": v.get("f1"), "roc_auc": v.get("roc_auc")} for k, v in m.items() if isinstance(v, dict)}
    if t == "causal":
        return {"precision": m.get("precision"), "recall": m.get("recall"), "shd": m.get("structural_hamming_distance")}
    if t == "digital_twin":
        return {"sample_size": m.get("sample_size"), "mae": m.get("mae"), "rmse": m.get("rmse"), "mape": m.get("mean_percentage_error")}
    if t == "decision_architecture":
        return {r.get("architecture"): {"goal_achievement": r.get("goal_achievement"), "risk_adjusted": r.get("risk_adjusted_score")} for r in m.get("results", [])}
    if t == "ablation":
        return {c.get("component_removed"): {"delta_goal_achievement": c.get("delta_goal_achievement")} for c in m.get("comparisons", [])}
    if t == "multi_agent":
        return {k: {"goal_achievement": (v or {}).get("goal_achievement")} for k, v in m.items() if isinstance(v, dict)}
    return {}


def build_manifest(db: Session) -> dict:
    """Reproducibility manifest for every recorded experiment
    (docs/RESEARCH_TRACEABILITY.md, docs/EXPERIMENT_GUIDE.md). Everything an
    external reader needs to reproduce a result: id, type, seed, dataset
    version, model versions, configuration, timings, status, headline
    metrics. Recomputes nothing."""
    runs = db.query(ExperimentRun).order_by(ExperimentRun.created_at.desc()).all()
    return {
        "generated_at": None,  # filled by the endpoint (kept pure here)
        "experiment_count": len(runs),
        "experiments": [
            {
                "experiment_id": r.id,
                "experiment_name": r.experiment_name,
                "experiment_type": r.experiment_type,
                "status": r.status,
                "random_seed": r.random_seed,
                "dataset_version": r.dataset_version,
                "model_versions": r.model_versions_json or {},
                "configuration": r.configuration_json or {},
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "started_at": r.started_at.isoformat() if r.started_at else None,
                "completed_at": r.completed_at.isoformat() if r.completed_at else None,
                "error_message": r.error_message,
                "metric_summary": _metric_summary(r),
            }
            for r in runs
        ],
    }
