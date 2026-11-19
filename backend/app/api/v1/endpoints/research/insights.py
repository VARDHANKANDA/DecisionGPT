"""Research Console - evaluation read models and the one-action preprocessing pipeline (admin/research only).

Read endpoints serve stored records; nothing here calls an AI provider. The two POST endpoints are deterministic local computations
(model comparison, preprocessing) that persist versioned records and never touch the frozen benchmark.
"""
import re

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.api.deps import require_research_access
from app.services.export_safety import safe_csv_stream
from app.db.session import get_db
from app.models.agent import AgentEvaluation
from app.models.decision import DecisionOutcome
from app.services import (
    agent_evaluation_service,
    architecture_evaluation_service,
    causal_graph_evaluation_service,
    causal_identification_service,
    external_benchmark_service,
    llm_evaluation_status_service,
    ml_benchmark_service,
    model_comparison_service,
    research_dataset_service,
    research_preprocessing_service,
    research_summary_service,
    research_validation_service,
    risk_assessment_service,
)

router = APIRouter(dependencies=[Depends(require_research_access)])


@router.get("/summary")
def summary(db: Session = Depends(get_db)):
    return research_summary_service.get_summary(db)


@router.get("/model-comparison")
def model_comparison():
    return model_comparison_service.latest_results()


@router.get("/ml-benchmark")
def ml_benchmark():
    """Stored ML benchmark runs (public / real-transaction / proxy-label / synthetic), grouped by evidence class. Read-only."""
    return ml_benchmark_service.latest_results()


@router.get("/external-benchmark")
def external_benchmark():
    """External system benchmark comparing DecisionGPT against Traditional Rule-Based DSS, ERP statistical forecasting, and single-agent raw GPT-5 mini."""
    return external_benchmark_service.get_external_benchmark_report()


@router.post("/model-comparison/run")
def model_comparison_run():
    """Deterministic (seed 42), local, no provider call. Writes new versioned records; earlier records are kept."""
    res = model_comparison_service.run_all(save=True)
    return {k: {"status": v.get("status"), "run_id": v.get("run_id"), "reason": v.get("reason")} for k, v in res.items()}


@router.get("/validation")
def validation():
    return research_validation_service.run_validation()


@router.get("/architecture-evaluation")
def architecture_evaluation(db: Session = Depends(get_db)):
    return architecture_evaluation_service.get_architecture_evaluation(agent_evaluation_service.get_agent_evaluation(db))


@router.get("/causal-assessment")
def causal_assessment(db: Session = Depends(get_db)):
    out = causal_identification_service.get_report()
    out["graph_evidence"] = causal_graph_evaluation_service.get_causal_graph_evaluation(db)
    return out


@router.get("/risk-assessment")
def risk_assessment(db: Session = Depends(get_db)):
    n = db.query(DecisionOutcome).count()
    n_eval = db.query(AgentEvaluation).count()
    total_evaluated = n + n_eval
    return risk_assessment_service.get_risk_assessment(agent_evaluation_service.get_agent_evaluation(db), total_evaluated)


@router.get("/llm-evaluation/runs/{run_id}")
def llm_run_detail(run_id: str):
    d = llm_evaluation_status_service.run_detail(run_id)
    if d is None:
        raise HTTPException(status_code=404, detail="Unknown run")
    return d


# ------------------------------------------------------------------------------------------------ preprocessing
class PreprocessRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    steps: list[str] | None = Field(default=None, description="step ids to run; omitted = every applicable step")


def _frame(db: Session, version_id: str):
    v = research_dataset_service.get_version(db, version_id)  # raises 404 for an unknown id
    return v, research_dataset_service.load_version_dataframe(v)


@router.get("/preprocessing/{version_id}/plan")
def preprocessing_plan(version_id: str, db: Session = Depends(get_db)):
    v, df = _frame(db, version_id)
    return {"version_id": version_id, "rows": int(len(df)), "columns": int(len(df.columns)),
            "schema": [{"name": str(c), "dtype": str(df[c].dtype), "missing": int(df[c].isna().sum())} for c in df.columns],
            "duplicate_rows": int(df.duplicated().sum()),
            "steps": research_preprocessing_service.plan(df),
            "runs": research_preprocessing_service.list_runs(research_dataset_service._storage_root(), version_id)}


@router.post("/preprocessing/{version_id}/run")
def preprocessing_run(version_id: str, body: PreprocessRequest, db: Session = Depends(get_db)):
    if body.steps is not None:
        unknown = [s for s in body.steps if s not in research_preprocessing_service.STEP_ORDER]
        if unknown:
            raise HTTPException(status_code=422, detail=f"unknown step(s): {unknown}")
    v, df = _frame(db, version_id)
    res = research_preprocessing_service.run_and_store(df, version_id, research_dataset_service._storage_root(), body.steps)
    if res.get("status") == "busy":
        raise HTTPException(status_code=409, detail=res["reason"])
    return res


@router.get("/preprocessing/{version_id}/runs")
def preprocessing_runs(version_id: str, db: Session = Depends(get_db)):
    research_dataset_service.get_version(db, version_id)
    return research_preprocessing_service.list_runs(research_dataset_service._storage_root(), version_id)


@router.get("/preprocessing/{version_id}/runs/{run_id}")
def preprocessing_run_detail(version_id: str, run_id: str, db: Session = Depends(get_db)):
    research_dataset_service.get_version(db, version_id)
    r = research_preprocessing_service.get_run(research_dataset_service._storage_root(), version_id, run_id)
    if r is None:
        raise HTTPException(status_code=404, detail="Unknown preprocessing run")
    return r


@router.get("/preprocessing/{version_id}/runs/{run_id}/download")
def preprocessing_download(version_id: str, run_id: str, db: Session = Depends(get_db)):
    research_dataset_service.get_version(db, version_id)
    r = research_preprocessing_service.get_run(research_dataset_service._storage_root(), version_id, run_id)
    if r is None or r.get("status") != "completed":
        raise HTTPException(status_code=404, detail="No processed output for this run")
    path = research_dataset_service._storage_root() / "processed" / version_id / run_id / "processed.csv"
    # streamed through the export filter: a text cell that a spreadsheet would run as a formula is neutralised (the stored file is untouched)
    return StreamingResponse(safe_csv_stream(path), media_type="text/csv",
                             headers={"Content-Disposition": f'attachment; filename="{re.sub(r"[^A-Za-z0-9._-]", "_", str(run_id))}.csv"'})
