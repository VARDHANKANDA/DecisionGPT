"""Research Console — Overview aggregates (docs/PRD.md §12 dashboard).

Every number is a live count/aggregate over real rows — no hard-coded
dashboard figures (AGENTS.md "no fabrication").
"""
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.experiment import ExperimentRun
from app.models.ml_model import MLModel
from app.models.research import ResearchDataset, ResearchDatasetVersion, TrainingRun
from app.services import dataset_registry_service


def build_overview(db: Session) -> dict:
    uploaded_datasets = db.query(ResearchDataset).count()
    uploaded_versions = db.query(ResearchDatasetVersion).count()
    platform_datasets = len(dataset_registry_service.list_datasets())

    models = db.query(MLModel).all()
    active_models = [m for m in models if m.status == "active"]
    experimental_models = [m for m in models if m.status == "experimental"]

    training_runs = db.query(TrainingRun).all()
    training_failed = [r for r in training_runs if r.status == "failed"]

    experiments = db.query(ExperimentRun).order_by(ExperimentRun.created_at.desc()).all()
    completed = [e for e in experiments if e.status == "completed"]
    failed = [e for e in experiments if e.status == "failed"]
    latest = experiments[0] if experiments else None

    # Best recorded metrics where meaningful, straight from active models.
    best_metrics: dict = {}
    for m in active_models:
        for key in ("mae", "rmse", "mape", "roc_auc", "f1", "precision", "recall"):
            val = m.metrics_json.get(key)
            if isinstance(val, (int, float)):
                minimise = key in ("mae", "rmse", "mape")
                cur = best_metrics.get(key)
                if cur is None or (val < cur["value"] if minimise else val > cur["value"]):
                    best_metrics[key] = {"value": val, "model": f"{m.model_name} {m.version}"}

    return {
        "uploaded_dataset_count": uploaded_datasets,
        "uploaded_dataset_version_count": uploaded_versions,
        "platform_dataset_count": platform_datasets,
        "model_count": len(models),
        "active_model_count": len(active_models),
        "experimental_model_count": len(experimental_models),
        "training_run_count": len(training_runs),
        "training_runs_failed": len(training_failed),
        "experiment_count": len(experiments),
        "experiments_completed": len(completed),
        "experiments_failed": len(failed),
        "latest_experiment": (
            {
                "id": latest.id,
                "experiment_type": latest.experiment_type,
                "status": latest.status,
                "created_at": latest.created_at.isoformat() if latest.created_at else None,
            }
            if latest
            else None
        ),
        "best_metrics": best_metrics,
    }
