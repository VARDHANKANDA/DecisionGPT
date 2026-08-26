"""Throwaway end-to-end audit: drives the full 18-step SME flow + the
research pipeline against a fresh in-memory DB and prints what actually got
persisted at each step. Not a test — a manual verification aid.

    python scripts/audit_e2e.py
"""
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

import pandas as pd  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

import app.models  # noqa: E402,F401
from app.core.config import get_settings  # noqa: E402
from app.db.session import Base, get_db  # noqa: E402
from app.main import app as fastapi_app  # noqa: E402
from app.services import model_registry_service  # noqa: E402

OK, BAD = "  [OK]", "  [!!]"


def line(msg):
    print(msg, flush=True)


engine = create_engine(
    "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
)
Base.metadata.create_all(engine)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
db = SessionLocal()
fastapi_app.dependency_overrides[get_db] = lambda: (yield db)  # type: ignore
client = TestClient(fastapi_app)
model_registry_service.sync_from_file_registry(db)  # production would already have models

RTOKEN = {"X-Research-Token": get_settings().research_console_token}


def rich_csv(kind: str) -> bytes:
    today = date.today()
    start = today - timedelta(days=120)
    if kind == "products":
        df = pd.DataFrame([{"Product ID": f"P{i}", "Product Name": f"Item {i}", "Selling Price": 500 + i * 40,
                            "Unit Cost": 250 + i * 20} for i in range(5)])
    elif kind == "customers":
        df = pd.DataFrame([{"Customer ID": f"C{i:03d}",
                            "First Purchase Date": (start + timedelta(days=i % 90)).isoformat(),
                            "Last Purchase Date": (today - timedelta(days=i % 25)).isoformat(),
                            "Purchase Frequency": 2 + (i % 6), "Monetary Value": 1200 + i * 33} for i in range(45)])
    elif kind == "sales":
        rows = []
        for d in range(120):
            sd = start + timedelta(days=d)
            for j in range(3):
                rows.append({"Order Date": sd.isoformat(), "Customer ID": f"C{(d * 3 + j) % 45:03d}",
                             "Product ID": f"P{(d + j) % 5}", "Quantity": 1 + (j % 3),
                             "Unit Price": 500 + ((d + j) % 5) * 40, "Discount": 0})
        df = pd.DataFrame(rows)
    elif kind == "marketing_campaigns":
        df = pd.DataFrame([{"Date": (start + timedelta(days=i)).isoformat(), "Channel": "Instagram",
                            "Spend": 1500 + (i % 12) * 40, "Impressions": 6000, "Clicks": 240,
                            "Conversions": 12, "Attributed Revenue": 5200} for i in range(0, 120, 3)])
    else:
        raise ValueError(kind)
    return df.to_csv(index=False).encode()


def main():
    line("=" * 70)
    line("SME END-TO-END FLOW")
    line("=" * 70)

    # 1. register / login
    reg = client.post("/api/v1/auth/register",
                      json={"email": "audit@x.com", "password": "password123", "role": "sme"})
    assert reg.status_code == 201, reg.text
    token = reg.json()["access_token"]
    auth = {"Authorization": f"Bearer {token}"}
    me = client.get("/api/v1/auth/me", headers=auth)
    line(f"{OK} 1. auth: registered + /me -> {me.json()['email']} role={me.json()['role']}")

    # 2. business creation
    biz = client.post("/api/v1/businesses", headers=auth,
                      json={"name": "Audit Co", "industry": "Apparel", "business_type": "D2C",
                            "business_size": "Small (6-25)"})
    bid = biz.json()["id"]
    from app.models.business import Business
    owner = db.get(Business, bid).owner_user_id
    line(f"{OK} 2. business created id={bid[:8]} owner_user_id set={owner is not None}")

    # 3. data upload
    for kind in ("products", "customers", "sales", "marketing_campaigns"):
        r = client.post(f"/api/v1/businesses/{bid}/data/upload?data_type={kind}", headers=auth,
                        files={"file": (f"{kind}.csv", rich_csv(kind), "text/csv")})
        assert r.status_code == 200 and r.json()["status"] == "completed", (kind, r.text)
    from app.models.sale import Sale
    line(f"{OK} 3. data uploaded: {db.query(Sale).filter(Sale.business_id == bid).count()} sales rows")

    # 4. analytics
    kpis = client.get(f"/api/v1/businesses/{bid}/analytics/kpis", headers=auth).json()
    fc = client.post(f"/api/v1/businesses/{bid}/analytics/forecast?horizon_days=7", headers=auth)
    line(f"{OK} 4. analytics: revenue=Rs {kpis['revenue']:.0f} profit={kpis['profit']} "
         f"forecast={fc.status_code} model={fc.json().get('model_name') if fc.status_code == 200 else '—'}")

    # 5. goal
    goal = client.post(f"/api/v1/businesses/{bid}/goals", headers=auth,
                       json={"text": "Increase profit by 15% in 3 months without raising prices"})
    assert goal.status_code == 201, goal.text
    gid = goal.json()["id"]
    line(f"{OK} 5. goal: objective={goal.json()['objective']} constraints={goal.json()['constraints_json']}")

    # 6-13. decision analyze (goal-aware strategies -> DT sim -> causal -> agents r1 -> debate -> optimize -> explain -> persist)
    dec = client.post(f"/api/v1/businesses/{bid}/decisions/analyze", headers=auth, json={"goal_id": gid})
    assert dec.status_code == 200, dec.text
    d = dec.json()
    did = d["id"]
    sg = d["strategy_generation"]
    line(f"{OK} 6. goal-aware strategies: objective={sg['objective']} candidates={sg['candidate_count']} "
         f"constraints_applied={sg['constraints_applied']} excluded={len(sg['excluded'])}")
    line(f"{OK} 7. digital twin: selected='{d['selected_strategy_name']}' "
         f"expected_rev=Rs {d['expected_outcome']['expected_revenue']:.0f} risk={d['risk_level']}")
    cc = d["causal_context"]
    line(f"{OK} 8. causal context: built={cc['built']} graph_version={cc['graph_version']} "
         f"strongest={cc['strongest_pathway_evidence']} pathways={len(cc['pathways'])}")
    deb = d["debate"]
    line(f"{OK} 9. multi-agent round1: {list(deb['round1'].keys())}")
    line(f"{OK} 10. peer review: reviews={len(deb['round2_reviews'])} conflicts={len(deb['resolution']['conflicts'])}")
    line(f"{OK} 11. optimizer: final_score={deb['resolution']['final_score']} "
         f"confidence={deb['resolution']['confidence']} basis_keys={list(deb['resolution']['confidence_basis'])}")
    expl = client.get(f"/api/v1/businesses/{bid}/decisions/{did}/explanation", headers=auth).json()
    line(f"{OK} 12. explanation: shap_available={expl['explanation']['shap_available']} "
         f"local_factors={len(expl['explanation']['local_factors'])} reasoning_len={len(expl['reasoning'])}")
    from app.models.decision import Decision
    from app.models.agent import AgentRun
    from app.models.strategy import Strategy
    row = db.get(Decision, did)
    line(f"{OK} 13. persistence: Decision row exists, strategies={db.query(Strategy).filter(Strategy.business_id == bid).count()} "
         f"agent_runs={db.query(AgentRun).filter(AgentRun.decision_id == did).count()}")

    # 14. traceability
    tr = client.get(f"/api/v1/businesses/{bid}/decisions/{did}/trace", headers=auth).json()
    need = ["business_state_version", "candidate_strategy_ids", "simulation_ids", "agent_run_ids",
            "model_versions", "causal_graph_version", "debate", "strategy_generation", "assumptions",
            "uncertainty", "prompt_version"]
    missing = [k for k in need if not tr.get(k)]
    line(f"{OK if not missing else BAD} 14. traceability: reproducible={tr['reproducible']['ok']} "
         f"missing_fields={missing or 'none'}")

    # 15. actual outcome recording
    exp = d["expected_outcome"]
    actual_rev = exp["baseline_revenue"] + (exp["expected_revenue"] - exp["baseline_revenue"]) * 0.6
    payload = {"revenue": actual_rev}
    if exp.get("expected_profit") is not None:
        payload["profit"] = exp["baseline_profit"] + (exp["expected_profit"] - exp["baseline_profit"]) * 0.5
    oc = client.post(f"/api/v1/businesses/{bid}/decisions/{did}/outcome", headers=auth,
                     json={"actual_outcome": payload})
    assert oc.status_code == 200, oc.text
    line(f"{OK} 15. outcome recorded: goal_achieved={oc.json()['goal_achieved']} "
         f"score={oc.json()['goal_achievement_score']}")

    # 16. DT prediction evaluation (feedback loop)
    from app.models.evaluation import PredictionEvaluation
    pe = db.query(PredictionEvaluation).filter(PredictionEvaluation.decision_id == did).first()
    line(f"{OK if pe else BAD} 16. DT prediction eval persisted: "
         f"{'sim=' + (pe.simulation_id or 'NULL')[:8] + ' rev_err=' + str(pe.revenue_error) + ' metrics=' + str(list(pe.metrics_json)) if pe else 'MISSING'}")

    # 17. memory update
    from app.models.memory import BusinessMemory
    mem_types = [m[0] for m in db.query(BusinessMemory.memory_type).filter(BusinessMemory.business_id == bid).distinct()]
    line(f"{OK} 17. memory: types={sorted(mem_types)}")

    # 18. conservative causal evidence feedback
    from app.models.evaluation import CausalEvidenceUpdate
    from app.models.causal import CausalEdge
    upd = db.query(CausalEvidenceUpdate).count()
    cv = db.query(CausalEdge).filter(CausalEdge.evidence_type == "causally_validated").count()
    line(f"{OK} 18. causal feedback: evidence_updates={upd} (expected 0 after 1 outcome) "
         f"causally_validated_edges={cv} (must be 0)")
    assert cv == 0, "causally_validated must never be auto-assigned"

    line("")
    line("=" * 70)
    line("RESEARCH PIPELINE")
    line("=" * 70)

    # sync models
    model_registry_service.sync_from_file_registry(db)
    ov = client.get("/api/v1/research/overview", headers=RTOKEN).json()
    line(f"{OK} research overview: models={ov['model_count']} active={ov['active_model_count']} "
         f"platform_datasets={ov['platform_dataset_count']}")

    # dataset upload -> version -> train
    fc_df = pd.DataFrame({
        "series_id": "s1",
        "date": pd.date_range("2025-01-01", periods=160).strftime("%Y-%m-%d"),
        "units_sold": [30 + (i % 11) for i in range(160)],
        "price": 500.0, "marketing_spend": [1000.0 + (i % 7) * 50 for i in range(160)], "promotion_flag": 0,
    })
    up = client.post("/api/v1/research/datasets/upload", headers=RTOKEN,
                     files={"file": ("fc.csv", fc_df.to_csv(index=False).encode(), "text/csv")},
                     data={"name": "Audit FC", "domain": "forecasting"})
    assert up.status_code == 201, up.text
    vid = up.json()["id"]
    line(f"{OK} dataset upload: v{up.json()['version']} rows={up.json()['row_count']} valid={up.json()['validation_ok']}")

    tr_run = client.post("/api/v1/research/training/run", headers=RTOKEN,
                         json={"task": "forecasting", "model_type": "xgboost", "dataset_version_id": vid, "seed": 7})
    assert tr_run.status_code == 200, tr_run.text
    trj = tr_run.json()
    line(f"{OK} training run: status={trj['status']} model={trj['model_name']} {trj['model_version']} "
         f"metrics={list(trj['metrics_json'])} model_id={trj['model_id'][:8] if trj['model_id'] else None}")

    mp = client.get("/api/v1/research/model-performance", headers=RTOKEN).json()
    line(f"{OK} model performance: registered={mp['summary']['registered_models']} "
         f"best_forecasting={mp['summary']['best_forecasting']['value'] if mp['summary']['best_forecasting'] else None}")

    for et in ("causal", "decision_architecture", "ablation"):
        r = client.post("/api/v1/research/experiments/run", headers=RTOKEN,
                        json={"experiment_type": et, "configuration": {"seed": 42}})
        assert r.status_code == 200, (et, r.text)
        rj = r.json()
        line(f"{OK} experiment '{et}': status={rj['status']} started={bool(rj['started_at'])} "
             f"completed={bool(rj['completed_at'])} seed={rj['random_seed']} ds={rj['dataset_version']}")

    dte = client.get("/api/v1/research/digital-twin-evaluation", headers=RTOKEN).json()
    line(f"{OK} DT evaluation page: evaluated={dte['summary']['evaluated_predictions']} "
         f"rev_mae={dte['summary']['revenue_mae']} empty_state={bool(dte['empty_state'])}")

    ce = client.get("/api/v1/research/causal-evaluation", headers=RTOKEN).json()
    line(f"{OK} causal evaluation page: graphs={len(ce['graphs'])} method_validation={ce['method_validation'] is not None} "
         f"ground_truth_available={ce['ground_truth_comparison']['available']}")

    ae = client.get("/api/v1/research/agent-evaluation", headers=RTOKEN).json()
    line(f"{OK} agent evaluation page: arch_rows={len(ae['architecture_comparison']['rows'])} "
         f"debate_decisions={ae['debate_analysis']['decisions_with_debate']}")

    pr = client.get("/api/v1/research/paper-results", headers=RTOKEN).json()
    for t in pr["tables"]:
        line(f"     paper table '{t['key']}': available={t['available']} "
             f"reason={t['missing_reason'] or '—'}")

    for tbl in ("forecasting_performance", "digital_twin_evaluation", "decision_architecture", "ablation", "causal_evaluation"):
        for fmt in ("csv", "markdown"):
            ex = client.post("/api/v1/research/export", headers=RTOKEN, json={"table": tbl, "format": fmt})
            assert ex.status_code == 200, (tbl, fmt, ex.text)
        line(f"{OK} export '{tbl}': csv+markdown ok ({len(ex.text)} chars md)")

    line("")
    line("=" * 70)
    line("ACCESS CONTROL (auth_enabled=True)")
    line("=" * 70)
    get_settings().auth_enabled = True
    try:
        sme2 = client.post("/api/v1/auth/register",
                           json={"email": "intruder@x.com", "password": "password123", "role": "sme"}).json()["access_token"]
        r = client.get(f"/api/v1/businesses/{bid}/analytics/kpis", headers={"Authorization": f"Bearer {sme2}"})
        line(f"{OK if r.status_code == 403 else BAD} cross-business access blocked: {r.status_code}")
        r = client.get("/api/v1/research/overview", headers={"Authorization": f"Bearer {sme2}"})
        line(f"{OK if r.status_code == 403 else BAD} SME blocked from research: {r.status_code}")
        r = client.get("/api/v1/research/overview")
        line(f"{OK if r.status_code == 403 else BAD} unauthenticated blocked from research: {r.status_code}")
        admin = client.post("/api/v1/auth/register",
                            json={"email": "admin@x.com", "password": "password123", "role": "admin"}).json()["access_token"]
        r = client.get("/api/v1/research/overview", headers={"Authorization": f"Bearer {admin}"})
        line(f"{OK if r.status_code == 200 else BAD} admin allowed into research: {r.status_code}")
    finally:
        get_settings().auth_enabled = False

    line("")
    line("AUDIT COMPLETE — no assertion failures.")


if __name__ == "__main__":
    main()
