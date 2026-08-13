"""Research Console — Experiment Runner (docs/PRD.md §12).

Dispatches to the real evaluation module for each experiment_type and
records a permanent ExperimentRun row — every number the Research Console
displays traces back to one of these rows (docs/RESEARCH_SPECIFICATION.md
§11 "no result is entered into the paper until produced by a recorded
experiment"). Nothing here computes or approximates a metric itself; it
only calls the real module and stores what came back.
"""
from dataclasses import asdict

from sqlalchemy.orm import Session

from app.core.errors import ValidationFailedError
from app.models.experiment import ExperimentRun
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


def run_experiment(db: Session, experiment_type: str, configuration: dict | None = None) -> ExperimentRun:
    if experiment_type not in SUPPORTED_EXPERIMENT_TYPES:
        raise ValidationFailedError(
            f"Unsupported experiment_type '{experiment_type}'.",
            details={"supported_types": sorted(SUPPORTED_EXPERIMENT_TYPES)},
        )

    configuration = configuration or {}
    seed = int(configuration.get("seed", 42))
    dataset_version: str | None = None

    if experiment_type == "forecasting":
        from ml.training.train_forecasting import run as train_forecasting

        result = train_forecasting(random_seed=seed)
        metrics = result["results"]
        dataset_version = result["dataset_version"]

    elif experiment_type == "churn":
        from ml.training.train_churn import run as train_churn

        result = train_churn(random_seed=seed)
        metrics = result["results"]
        dataset_version = result["dataset_version"]

    elif experiment_type == "digital_twin":
        evaluation = digital_twin_evaluation_service.run_digital_twin_evaluation(db)
        metrics = asdict(evaluation)
        dataset_version = "real_recorded_outcomes"

    elif experiment_type == "causal":
        evaluation = causal_evaluation_service.run_causal_evaluation(seed=seed)
        metrics = asdict(evaluation)
        dataset_version = "synthetic_causal_validation"

    elif experiment_type == "decision_architecture":
        run_result = decision_architecture_service.run_decision_architecture_experiment(db, seed=seed)
        metrics = asdict(run_result)
        dataset_version = "synthetic_scenario"

    elif experiment_type == "multi_agent":
        run_result = decision_architecture_service.run_decision_architecture_experiment(db, seed=seed)
        by_arch = {r.architecture: asdict(r) for r in run_result.results}
        metrics = {"single_agent": by_arch["C"], "multi_agent": by_arch["D"]}
        dataset_version = "synthetic_scenario"

    else:  # ablation
        ablation_result = ablation_service.run_ablation_study(db, seed=seed)
        metrics = asdict(ablation_result)
        dataset_version = "synthetic_scenario"

    run = ExperimentRun(
        experiment_name=configuration.get("name", experiment_type),
        experiment_type=experiment_type,
        dataset_version=dataset_version,
        model_version=None,
        configuration_json=configuration,
        metrics_json=metrics,
        random_seed=seed,
        status="completed",
    )
    db.add(run)
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
