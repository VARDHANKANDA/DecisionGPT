"""Research Console — Paper Results (docs Phase 8).

Collects the five paper tables from real recorded data and reports, per
table, whether it is ready or which experiment still needs to run. Rows
are previewed here; the full export goes through research_export_service
(CSV / JSON / Markdown / LaTeX), which every row already traces to an
experiment id / model version / decision id.
"""
from sqlalchemy.orm import Session

from app.models.evaluation import PredictionEvaluation
from app.models.experiment import ExperimentRun
from app.models.ml_model import MLModel
from app.services import digital_twin_evaluation_service, research_export_service

_PREVIEW = 25

TABLES = [
    {
        "key": "predictive_model_performance",
        "table": "forecasting_performance",  # + churn_performance
        "title": "Table 1 — Predictive Model Performance",
        "export_tables": ["forecasting_performance", "churn_performance"],
    },
    {
        "key": "digital_twin_evaluation",
        "table": "digital_twin_evaluation",
        "title": "Table 2 — Digital Twin Prediction Evaluation",
        "export_tables": ["digital_twin_evaluation"],
    },
    {
        "key": "causal_graph_evaluation",
        "table": "causal_evaluation",
        "title": "Table 3 — Causal Graph Evaluation (synthetic method validation)",
        "export_tables": ["causal_evaluation"],
    },
    {
        "key": "decision_architecture",
        "table": "decision_architecture",
        "title": "Table 4 — Decision Architecture Comparison",
        "export_tables": ["decision_architecture"],
    },
    {
        "key": "ablation_study",
        "table": "ablation",
        "title": "Table 5 — Ablation Study",
        "export_tables": ["ablation"],
    },
]


def _preview(headers: list[str], rows: list[list]) -> dict:
    return {"headers": headers, "rows": [list(r) for r in rows[:_PREVIEW]], "row_count": len(rows)}


def get_paper_results(db: Session) -> dict:
    digital_twin_evaluation_service.backfill(db)
    out = []

    for spec in TABLES:
        entry = {"key": spec["key"], "title": spec["title"], "export_tables": spec["export_tables"]}

        if spec["key"] == "predictive_model_performance":
            fh, fr = research_export_service.forecasting_performance_table(db)
            ch, cr = research_export_service.churn_performance_table(db)
            has = db.query(MLModel).count() > 0
            entry.update(
                available=has,
                missing_reason=None if has else "No models registered. Train models from the Training Center.",
                sections=[
                    {"name": "Forecasting", **_preview(fh, fr)},
                    {"name": "Classification (churn)", **_preview(ch, cr)},
                ],
                source_refs={"model_versions": [f"{r[0]} {r[1]}" for r in (fr + cr)]},
            )

        elif spec["key"] == "digital_twin_evaluation":
            headers, rows = research_export_service.digital_twin_evaluation_table(db, None)
            n_matched = (
                db.query(PredictionEvaluation)
                .filter(PredictionEvaluation.revenue_error.isnot(None))
                .count()
            )
            entry.update(
                available=n_matched > 0,
                missing_reason=None
                if n_matched > 0
                else "No matched predicted/actual outcomes. An SME must record an actual decision outcome.",
                sections=[{"name": "Prediction vs actual", **_preview(headers, rows)}],
                source_refs={"decision_ids": [r[0] for r in rows]},
            )

        else:  # experiment-backed
            exp_id = research_export_service.latest_experiment_id(db, spec["table"])
            run = db.get(ExperimentRun, exp_id) if exp_id else None
            builder = research_export_service.TABLE_BUILDERS[spec["table"]]
            headers, rows = builder(db, exp_id)
            entry.update(
                available=bool(rows),
                missing_reason=None
                if rows
                else f"No completed '{research_export_service.TABLE_EXPERIMENT_TYPE[spec['table']]}' experiment. Run it from Experiments.",
                sections=[{"name": spec["title"], **_preview(headers, rows)}],
                source_refs={
                    "experiment_id": exp_id,
                    "seed": run.random_seed if run else None,
                    "created_at": run.created_at.isoformat() if run and run.created_at else None,
                },
            )

        out.append(entry)

    ready = sum(1 for e in out if e["available"])
    return {
        "summary": {"tables_total": len(out), "tables_ready": ready, "tables_missing": len(out) - ready},
        "tables": out,
        "export_formats": sorted(research_export_service.SUPPORTED_FORMATS),
    }
