"""Research Console — Paper-ready exports (docs/PRD.md §18).

Turns already-recorded data (ExperimentRun rows, the model registry) into
paper-ready tables — CSV, JSON, Markdown, and LaTeX. Every export reads
from what's already stored; nothing here computes a new number.
"""
import csv
import io
import json

from sqlalchemy.orm import Session

from app.core.errors import ValidationFailedError
from app.models.experiment import ExperimentRun
from app.models.ml_model import MLModel

SUPPORTED_FORMATS = {"csv", "json", "markdown", "latex"}


def _rows_to_csv(headers: list[str], rows: list[list]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(headers)
    writer.writerows(rows)
    return buf.getvalue()


def _rows_to_markdown(headers: list[str], rows: list[list]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    for row in rows:
        lines.append("| " + " | ".join(str(c) for c in row) + " |")
    return "\n".join(lines)


def _rows_to_latex(headers: list[str], rows: list[list], caption: str = "") -> str:
    col_spec = "l" * len(headers)
    lines = [
        "\\begin{table}[h]",
        "\\centering",
        f"\\begin{{tabular}}{{{col_spec}}}",
        "\\toprule",
        " & ".join(headers) + " \\\\",
        "\\midrule",
    ]
    for row in rows:
        lines.append(" & ".join(str(c) for c in row) + " \\\\")
    lines += ["\\bottomrule", "\\end{tabular}"]
    if caption:
        lines.append(f"\\caption{{{caption}}}")
    lines.append("\\end{table}")
    return "\n".join(lines)


def forecasting_performance_table(db: Session, experiment_id: str | None = None) -> tuple[list[str], list[list]]:
    models = db.query(MLModel).filter(MLModel.model_type.like("forecasting_%")).order_by(MLModel.model_name).all()
    headers = ["Model", "Version", "MAE", "RMSE", "MAPE", "Dataset version"]
    rows = [
        [
            m.model_name, m.version, m.metrics_json.get("mae"), m.metrics_json.get("rmse"),
            m.metrics_json.get("mape"), m.dataset_version,
        ]
        for m in models
    ]
    return headers, rows


def churn_performance_table(db: Session, experiment_id: str | None = None) -> tuple[list[str], list[list]]:
    models = db.query(MLModel).filter(MLModel.model_type.like("churn_%")).order_by(MLModel.model_name).all()
    headers = ["Model", "Version", "Precision", "Recall", "F1", "ROC-AUC", "Dataset version"]
    rows = [
        [
            m.model_name, m.version, m.metrics_json.get("precision"), m.metrics_json.get("recall"),
            m.metrics_json.get("f1"), m.metrics_json.get("roc_auc"), m.dataset_version,
        ]
        for m in models
    ]
    return headers, rows


def decision_architecture_table(db: Session, experiment_id: str | None) -> tuple[list[str], list[list]]:
    run = db.get(ExperimentRun, experiment_id) if experiment_id else None
    if run is None or run.experiment_type != "decision_architecture":
        return [], []
    headers = ["Architecture", "Selected strategy", "Expected benefit", "Risk-adjusted score", "Goal achievement", "Latency (s)"]
    rows = [
        [
            r["label"], r["selected_strategy_name"], r["expected_benefit"], r["risk_adjusted_score"],
            r["goal_achievement"], r["latency_seconds"],
        ]
        for r in run.metrics_json.get("results", [])
    ]
    return headers, rows


def ablation_table(db: Session, experiment_id: str | None) -> tuple[list[str], list[list]]:
    run = db.get(ExperimentRun, experiment_id) if experiment_id else None
    if run is None or run.experiment_type != "ablation":
        return [], []
    headers = [
        "Component removed", "Full goal achievement", "Ablated goal achievement", "Delta goal achievement",
        "Full risk-adj. score", "Ablated risk-adj. score", "Delta risk-adj. score",
    ]
    rows = [
        [
            c["component_removed"], c["full_goal_achievement"], c["ablated_goal_achievement"],
            c["delta_goal_achievement"], c["full_risk_adjusted_score"], c["ablated_risk_adjusted_score"],
            c["delta_risk_adjusted_score"],
        ]
        for c in run.metrics_json.get("comparisons", [])
    ]
    return headers, rows


def causal_evaluation_table(db: Session, experiment_id: str | None) -> tuple[list[str], list[list]]:
    run = db.get(ExperimentRun, experiment_id) if experiment_id else None
    if run is None or run.experiment_type != "causal":
        return [], []
    m = run.metrics_json
    headers = ["Metric", "Value"]
    rows = [
        ["Precision", m.get("precision")],
        ["Recall", m.get("recall")],
        ["Structural Hamming Distance", m.get("structural_hamming_distance")],
        ["True positives", m.get("true_positives")],
        ["False positives", m.get("false_positives")],
        ["False negatives", m.get("false_negatives")],
    ]
    return headers, rows


def digital_twin_evaluation_table(db: Session, experiment_id: str | None) -> tuple[list[str], list[list]]:
    run = db.get(ExperimentRun, experiment_id) if experiment_id else None
    if run is None or run.experiment_type != "digital_twin":
        return [], []
    headers = ["Decision ID", "Strategy", "Predicted change", "Actual change", "Error", "% error"]
    rows = [
        [r["decision_id"], r["strategy_name"], r["predicted_change"], r["actual_change"], r["error"], r["percentage_error"]]
        for r in run.metrics_json.get("rows", [])
    ]
    return headers, rows


TABLE_BUILDERS = {
    "forecasting_performance": forecasting_performance_table,
    "churn_performance": churn_performance_table,
    "decision_architecture": decision_architecture_table,
    "ablation": ablation_table,
    "causal_evaluation": causal_evaluation_table,
    "digital_twin_evaluation": digital_twin_evaluation_table,
}


def export_table(db: Session, table: str, fmt: str, experiment_id: str | None = None) -> str:
    if table not in TABLE_BUILDERS:
        raise ValidationFailedError(f"Unknown table '{table}'.", details={"supported_tables": sorted(TABLE_BUILDERS)})
    if fmt not in SUPPORTED_FORMATS:
        raise ValidationFailedError(
            f"Unknown export format '{fmt}'.", details={"supported_formats": sorted(SUPPORTED_FORMATS)}
        )

    headers, rows = TABLE_BUILDERS[table](db, experiment_id)

    if fmt == "csv":
        return _rows_to_csv(headers, rows)
    if fmt == "json":
        return json.dumps([dict(zip(headers, row)) for row in rows], indent=2, default=str)
    if fmt == "markdown":
        return _rows_to_markdown(headers, rows)
    return _rows_to_latex(headers, rows, caption=table.replace("_", " ").title())
