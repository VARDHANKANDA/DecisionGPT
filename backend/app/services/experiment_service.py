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


def _dispatch(db: Session, experiment_type: str, configuration: dict) -> tuple[dict, str | None, dict]:
    """Returns (metrics, dataset_version, model_versions)."""
    seed = int(configuration.get("seed", 42))

    if experiment_type == "forecasting":
        from ml.training.train_forecasting import run as train_forecasting

        result = train_forecasting(random_seed=seed)
        return result["results"], result["dataset_version"], {}

    if experiment_type == "churn":
        from ml.training.train_churn import run as train_churn

        result = train_churn(random_seed=seed)
        return result["results"], result["dataset_version"], {}

    if experiment_type == "digital_twin":
        evaluation = digital_twin_evaluation_service.run_digital_twin_evaluation(db)
        return asdict(evaluation), "real_recorded_outcomes", {}

    if experiment_type == "causal":
        evaluation = causal_evaluation_service.run_causal_evaluation(seed=seed)
        return asdict(evaluation), "synthetic_causal_validation", {}

    if experiment_type == "decision_architecture":
        run_result = decision_architecture_service.run_decision_architecture_experiment(db, seed=seed)
        return asdict(run_result), "synthetic_scenario", {}

    if experiment_type == "multi_agent":
        run_result = decision_architecture_service.run_decision_architecture_experiment(db, seed=seed)
        by_arch = {r.architecture: asdict(r) for r in run_result.results}
        return {"single_agent": by_arch["C"], "multi_agent": by_arch["D"]}, "synthetic_scenario", {}

    # ablation
    ablation_result = ablation_service.run_ablation_study(db, seed=seed)
    return asdict(ablation_result), "synthetic_scenario", ablation_result.model_versions


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
