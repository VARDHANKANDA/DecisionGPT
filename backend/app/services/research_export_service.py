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
from app.models.evaluation import PredictionEvaluation
from app.models.experiment import ExperimentRun
from app.models.ml_model import MLModel

SUPPORTED_FORMATS = {"csv", "json", "markdown", "latex"}

# Which experiment_type backs each experiment-derived table.
TABLE_EXPERIMENT_TYPE = {
    "decision_architecture": "decision_architecture",
    "decision_architecture_detail": "multi_scenario_architecture",
    "ablation": "ablation",
    "ablation_detail": "multi_scenario_ablation",
    "causal_evaluation": "causal",
    "digital_twin_evaluation": "digital_twin",
}


# tables that should prefer an aggregated multi-scenario run when one exists
_MULTI_PREFERENCE = {
    "decision_architecture": ["multi_scenario_architecture", "decision_architecture"],
    "ablation": ["multi_scenario_ablation", "ablation"],
    "decision_architecture_detail": ["multi_scenario_architecture"],
    "ablation_detail": ["multi_scenario_ablation"],
}


def latest_experiment_id(db: Session, table: str) -> str | None:
    types = _MULTI_PREFERENCE.get(table)
    if types is None:
        exp_type = TABLE_EXPERIMENT_TYPE.get(table)
        if exp_type is None:
            return None
        types = [exp_type]
    for exp_type in types:
        run = (
            db.query(ExperimentRun)
            .filter(ExperimentRun.experiment_type == exp_type, ExperimentRun.status == "completed")
            .order_by(ExperimentRun.created_at.desc())
            .first()
        )
        if run is not None:
            return run.id
    return None


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


def _model_data_category(db: Session, dataset_version: str | None) -> str:
    """Category label for a model row so Table 1 keeps real / synthetic /
    Indian-agri results visibly separate (docs/RESEARCH_EXPERIMENT_REPORT.md)."""
    from app.models.research import ResearchDataset, ResearchDatasetVersion
    from app.services import dataset_category

    dv = dataset_version or ""
    if dv.lower().startswith("platform-"):
        return dataset_category.SYNTHETIC_CONTROLLED
    # Training Center models carry `upload:<dataset_uuid>:v<n>` — resolve the
    # human dataset id so the category classifier can see it.
    if dv.startswith("upload:"):
        ref = dv.split(":", 2)[1]
        ds = db.query(ResearchDataset).filter(ResearchDataset.id == ref).one_or_none()
        if ds is None:
            v = db.query(ResearchDatasetVersion).filter(ResearchDatasetVersion.id == ref).one_or_none()
            if v is not None:
                ds = db.query(ResearchDataset).filter(ResearchDataset.id == v.dataset_id).one_or_none()
        if ds is not None:
            return dataset_category.classify(source=ds.source, dataset_id=ds.dataset_id)
    return dataset_category.classify(source=dv, dataset_id=dv)


def forecasting_performance_table(db: Session, experiment_id: str | None = None) -> tuple[list[str], list[list]]:
    models = db.query(MLModel).filter(MLModel.model_type.like("forecasting_%")).order_by(MLModel.model_name).all()
    headers = ["Model", "Version", "Status", "Data category", "MAE", "RMSE", "MAPE", "Dataset version"]
    rows = [
        [
            m.model_name, m.version, m.status, _model_data_category(db, m.dataset_version),
            m.metrics_json.get("mae"), m.metrics_json.get("rmse"),
            m.metrics_json.get("mape"), m.dataset_version,
        ]
        for m in models
    ]
    return headers, rows


def churn_performance_table(db: Session, experiment_id: str | None = None) -> tuple[list[str], list[list]]:
    models = db.query(MLModel).filter(MLModel.model_type.like("churn_%")).order_by(MLModel.model_name).all()
    headers = ["Model", "Version", "Status", "Data category", "Precision", "Recall", "F1", "ROC-AUC", "Dataset version"]
    rows = [
        [
            m.model_name, m.version, m.status, _model_data_category(db, m.dataset_version),
            m.metrics_json.get("precision"), m.metrics_json.get("recall"),
            m.metrics_json.get("f1"), m.metrics_json.get("roc_auc"), m.dataset_version,
        ]
        for m in models
    ]
    return headers, rows


def _latest_completed(db: Session, *types: str) -> ExperimentRun | None:
    return (
        db.query(ExperimentRun)
        .filter(ExperimentRun.experiment_type.in_(types), ExperimentRun.status == "completed")
        .order_by(ExperimentRun.created_at.desc())
        .first()
    )


def _fmt(cell: dict | None, k: str = "mean") -> object:
    return None if not cell else cell.get(k)


def decision_architecture_table(db: Session, experiment_id: str | None) -> tuple[list[str], list[list]]:
    """Paper Table 4. Prefers a completed multi-scenario run (aggregated across
    scenarios x seeds); falls back to the legacy single-scenario run."""
    run = db.get(ExperimentRun, experiment_id) if experiment_id else _latest_completed(
        db, "multi_scenario_architecture", "decision_architecture"
    )
    if run is None:
        return [], []

    if run.experiment_type == "multi_scenario_architecture":
        m = run.metrics_json or {}
        agg = m.get("aggregates", {})
        headers = ["Architecture", "Mean goal achievement", "Std", "95% CI",
                   "Mean risk-adjusted score", "Std", "Mean confidence", "Mean latency (s)", "N"]
        rows = []
        for a in "ABCD":
            ga = agg.get(a, {}).get("goal_achievement") or {}
            ra = agg.get(a, {}).get("risk_adjusted_score") or {}
            cf = agg.get(a, {}).get("confidence") or {}
            la = agg.get(a, {}).get("latency_seconds") or {}
            rows.append([
                f"{a} — {da_LABEL.get(a, a)}", _fmt(ga), _fmt(ga, 'std'),
                str(ga.get('ci95')) if ga.get('ci95') else "n/a",
                _fmt(ra), _fmt(ra, 'std'), _fmt(cf) if cf else "n/a", _fmt(la),
                ga.get('n', 0),
            ])
        return headers, rows

    headers = ["Architecture", "Selected strategy", "Expected benefit", "Risk-adjusted score",
               "Goal achievement", "Latency (s)"]
    rows = [
        [r["label"], r["selected_strategy_name"], r["expected_benefit"], r["risk_adjusted_score"],
         r["goal_achievement"], r["latency_seconds"]]
        for r in (run.metrics_json or {}).get("results", [])
    ]
    return headers, rows


def decision_architecture_detail_table(db: Session, experiment_id: str | None) -> tuple[list[str], list[list]]:
    """Traceable per-(architecture x scenario x seed) observations behind Table 4."""
    run = db.get(ExperimentRun, experiment_id) if experiment_id else _latest_completed(
        db, "multi_scenario_architecture"
    )
    if run is None:
        return [], []
    headers = ["Architecture", "Scenario", "Goal objective", "Seed", "Selected strategy",
               "Goal achievement", "Risk-adjusted score", "Confidence", "Latency (s)"]
    rows = [
        [o["architecture"], o["scenario_id"], o["goal_objective"], o["seed"], o["selected_strategy"],
         o["goal_achievement"], o["risk_adjusted_score"], o["confidence"], o["latency_seconds"]]
        for o in (run.metrics_json or {}).get("observations", [])
    ]
    return headers, rows


def ablation_table(db: Session, experiment_id: str | None) -> tuple[list[str], list[list]]:
    """Paper Table 5. Prefers a completed multi-scenario run; else legacy."""
    run = db.get(ExperimentRun, experiment_id) if experiment_id else _latest_completed(
        db, "multi_scenario_ablation", "ablation"
    )
    if run is None:
        return [], []

    if run.experiment_type == "multi_scenario_ablation":
        agg = (run.metrics_json or {}).get("aggregates", {})
        headers = ["Configuration", "Component removed", "Mean goal achievement", "Δ vs Full (mean)",
                   "95% CI of Δ", "Mean risk-adjusted score", "Δ vs Full (mean)", "Mean confidence", "N"]
        rows = []
        for c in ("A", "B", "C", "D", "E", "F"):
            e = agg.get(c, {})
            ga = e.get("goal_achievement") or {}
            dg = e.get("delta_goal_achievement_vs_full") or {}
            ra = e.get("risk_adjusted_score") or {}
            dr = e.get("delta_risk_adjusted_vs_full") or {}
            cf = e.get("confidence") or {}
            rows.append([
                f"{c} — {e.get('config_label', c)}", e.get("component_removed", ""),
                _fmt(ga), _fmt(dg), str(dg.get("ci95")) if dg.get("ci95") else "n/a",
                _fmt(ra), _fmt(dr), _fmt(cf) if cf else "n/a", ga.get("n", 0),
            ])
        return headers, rows

    headers = [
        "Component removed", "Full goal achievement", "Ablated goal achievement", "Delta goal achievement",
        "Full risk-adj. score", "Ablated risk-adj. score", "Delta risk-adj. score",
    ]
    rows = [
        [c["component_removed"], c["full_goal_achievement"], c["ablated_goal_achievement"],
         c["delta_goal_achievement"], c["full_risk_adjusted_score"], c["ablated_risk_adjusted_score"],
         c["delta_risk_adjusted_score"]]
        for c in (run.metrics_json or {}).get("comparisons", [])
    ]
    return headers, rows


def ablation_detail_table(db: Session, experiment_id: str | None) -> tuple[list[str], list[list]]:
    run = db.get(ExperimentRun, experiment_id) if experiment_id else _latest_completed(
        db, "multi_scenario_ablation"
    )
    if run is None:
        return [], []
    headers = ["Configuration", "Scenario", "Seed", "Selected strategy", "Goal achievement",
               "Δ goal achievement vs Full", "Risk-adjusted score", "Confidence"]
    rows = [
        [o["config"], o["scenario_id"], o["seed"], o["selected_strategy"], o["goal_achievement"],
         o["delta_goal_achievement_vs_full"], o["risk_adjusted_score"], o["confidence"]]
        for o in (run.metrics_json or {}).get("observations", [])
    ]
    return headers, rows


da_LABEL = {
    "A": "Prediction only", "B": "Prediction + Digital Twin",
    "C": "Prediction + Digital Twin + Single Agent", "D": "Full DecisionGPT",
}


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
    headers = ["Decision ID", "Strategy", "Predicted change", "Actual change", "Error", "% error"]
    run = db.get(ExperimentRun, experiment_id) if experiment_id else None
    if run is not None and run.experiment_type == "digital_twin" and run.metrics_json.get("rows"):
        rows = [
            [r["decision_id"], r["strategy_name"], r["predicted_change"], r["actual_change"], r["error"], r["percentage_error"]]
            for r in run.metrics_json.get("rows", [])
        ]
        return headers, rows
    # Fallback: read persisted PredictionEvaluation rows directly, so this
    # table works from real recorded outcomes even without a run.
    evals = (
        db.query(PredictionEvaluation)
        .filter(PredictionEvaluation.revenue_error.isnot(None))
        .order_by(PredictionEvaluation.recorded_at)
        .all()
    )
    rows = [
        [
            e.decision_id,
            e.strategy_name or "unknown",
            float(e.predicted_revenue_change) if e.predicted_revenue_change is not None else None,
            float(e.actual_revenue_change) if e.actual_revenue_change is not None else None,
            float(e.revenue_error) if e.revenue_error is not None else None,
            float(e.revenue_abs_pct_error) if e.revenue_abs_pct_error is not None else None,
        ]
        for e in evals
    ]
    return headers, rows


TABLE_BUILDERS = {
    "forecasting_performance": forecasting_performance_table,
    "churn_performance": churn_performance_table,
    "decision_architecture": decision_architecture_table,
    "decision_architecture_detail": decision_architecture_detail_table,
    "ablation": ablation_table,
    "ablation_detail": ablation_detail_table,
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

    # Auto-resolve the most recent completed experiment for experiment-backed
    # tables (except digital_twin_evaluation, which also reads persisted evals).
    if experiment_id is None and table in TABLE_EXPERIMENT_TYPE and table != "digital_twin_evaluation":
        experiment_id = latest_experiment_id(db, table)

    headers, rows = TABLE_BUILDERS[table](db, experiment_id)

    if fmt == "csv":
        return _rows_to_csv(headers, rows)
    if fmt == "json":
        return json.dumps([dict(zip(headers, row)) for row in rows], indent=2, default=str)
    if fmt == "markdown":
        return _rows_to_markdown(headers, rows)
    return _rows_to_latex(headers, rows, caption=table.replace("_", " ").title())
