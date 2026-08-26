"""Research Console — Training Center (docs/PRD.md §17).

Trains one real model on a chosen dataset (an uploaded research dataset
version, or a bundled platform dataset), evaluates it with the task's
proper metrics, registers the artifact, and creates an MLModel row with
status EXPERIMENTAL. Nothing here is a stub — it calls the exact training
code (`ml.training.*`) the CLI uses, and every metric comes from a real
evaluation split.

The production DecisionGPT pipeline only ever selects models with status
ACTIVE (see model_registry_service.get_active_model), so a freshly trained
EXPERIMENTAL model has no effect on SME-facing behaviour until it is
explicitly promoted.
"""
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.errors import NotFoundError, ValidationFailedError
from app.models.ml_model import MLModel
from app.models.research import ResearchDatasetVersion, TrainingRun
from app.services import research_dataset_service
from ml.pipeline.loaders import load_platform_dataset
from ml.pipeline.registry import save_model_artifact
from ml.training import train_churn, train_forecasting

PROJECT_ROOT = Path(__file__).resolve().parents[3]

# What the current architecture can actually train. We do not advertise a
# task/model the codebase doesn't implement (AGENTS.md "no fabrication").
SUPPORTED = {
    "forecasting": {
        "model_types": list(train_forecasting.SUPPORTED_MODEL_TYPES),
        "platform": ("forecasting", "sales_timeseries.csv"),
        "metric_keys": ["mae", "rmse", "mape"],
        "primary_metric": ("mae", True),  # (key, minimize)
    },
    "churn": {
        "model_types": list(train_churn.SUPPORTED_MODEL_TYPES),
        "platform": ("churn", "customers.csv"),
        "metric_keys": ["precision", "recall", "f1", "roc_auc"],
        "primary_metric": ("roc_auc", False),
    },
}


def supported_tasks() -> dict:
    return {
        task: {"model_types": cfg["model_types"], "metrics": cfg["metric_keys"]}
        for task, cfg in SUPPORTED.items()
    }


def _resolve_dataframe(
    db: Session, task: str, dataset_version_id: str | None, platform_domain: str | None
):
    if dataset_version_id:
        version = db.get(ResearchDatasetVersion, dataset_version_id)
        if version is None:
            raise NotFoundError(f"Dataset version {dataset_version_id} not found.")
        df = research_dataset_service.load_version_dataframe(version)
        label = f"upload:{version.dataset_id}:v{version.version}"
        return df, version, None, label
    # Fall back to the bundled platform dataset for the task.
    domain, filename = SUPPORTED[task]["platform"]
    if platform_domain and platform_domain != domain:
        raise ValidationFailedError(
            f"Task '{task}' trains on the '{domain}' platform dataset, not '{platform_domain}'."
        )
    ds = load_platform_dataset(domain, filename)
    return ds.dataframe, None, domain, ds.metadata.get("dataset_id", f"platform-{domain}")


def start_training(
    db: Session,
    *,
    task: str,
    model_type: str,
    dataset_version_id: str | None = None,
    platform_domain: str | None = None,
    parameters: dict | None = None,
    random_seed: int = 42,
    created_by: str | None = None,
) -> TrainingRun:
    if task not in SUPPORTED:
        raise ValidationFailedError(
            f"Unsupported task '{task}'. Supported: {sorted(SUPPORTED)}."
        )
    if model_type not in SUPPORTED[task]["model_types"]:
        raise ValidationFailedError(
            f"Unsupported model_type '{model_type}' for task '{task}'. "
            f"Supported: {SUPPORTED[task]['model_types']}."
        )

    run = TrainingRun(
        dataset_version_id=dataset_version_id,
        platform_domain=platform_domain,
        task=task,
        model_type=model_type,
        parameters_json=parameters or {},
        random_seed=random_seed,
        created_by=created_by,
        status="pending",
        features_json=[],
        metrics_json={},
    )
    db.add(run)
    db.flush()
    run.mark_running()
    db.commit()

    try:
        df, version, domain, label = _resolve_dataframe(db, task, dataset_version_id, platform_domain)
        run.dataset_version_label = label

        trainer = train_forecasting.train_one if task == "forecasting" else train_churn.train_one
        result = trainer(df, model_type, random_seed=random_seed, params=parameters or {})

        model_name = f"{task}_{model_type}" if task == "churn" else f"sales_forecast_{model_type}"
        model_type_tag = f"{task}_{model_type}"

        # Next artifact version for this model_name.
        existing = (
            db.query(MLModel)
            .filter(MLModel.model_name == model_name)
            .order_by(MLModel.created_at.desc())
            .all()
        )
        used_versions = {m.version for m in existing}
        n = 1
        while f"v{n}" in used_versions:
            n += 1
        artifact_version = f"v{n}"

        manifest = save_model_artifact(
            model=result["model"],
            model_name=model_name,
            model_type=model_type_tag,
            version=artifact_version,
            dataset_version=label,
            feature_version=result["feature_version"],
            parameters=result["parameters"],
            metrics=result["metrics"],
            random_seed=random_seed,
            write_index=False,  # experimental models never auto-activate via a sync
        )

        model_row = MLModel(
            model_name=model_name,
            model_type=model_type_tag,
            version=artifact_version,
            dataset_version=label,
            feature_version=result["feature_version"],
            parameters_json=result["parameters"],
            metrics_json=result["metrics"],
            model_path=manifest.artifact_path,
            status="experimental",
            task=task,
            features_json=result["feature_columns"],
            training_run_id=run.id,
            source="training_center",
        )
        db.add(model_row)
        db.flush()

        run.features_json = result["feature_columns"]
        run.target = result["target"]
        run.metrics_json = {
            **result["metrics"],
            "train_rows": result["train_rows"],
            "test_rows": result["test_rows"],
        }
        run.model_id = model_row.id
        run.model_name = model_name
        run.model_version = artifact_version
        run.artifact_path = manifest.artifact_path
        run.mark_completed()
        db.commit()
        db.refresh(run)
        return run
    except Exception as exc:  # noqa: BLE001 - record + surface, never swallow
        db.rollback()
        run = db.get(TrainingRun, run.id)
        run.mark_failed(str(exc))
        db.commit()
        db.refresh(run)
        raise ValidationFailedError(f"Training failed: {exc}", details={"training_run_id": run.id})


def list_training_runs(db: Session, task: str | None = None) -> list[TrainingRun]:
    q = db.query(TrainingRun)
    if task:
        q = q.filter(TrainingRun.task == task)
    return q.order_by(TrainingRun.created_at.desc()).all()


def get_training_run(db: Session, run_id: str) -> TrainingRun:
    run = db.get(TrainingRun, run_id)
    if run is None:
        raise NotFoundError(f"Training run {run_id} not found.")
    return run
