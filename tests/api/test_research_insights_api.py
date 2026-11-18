"""Research Console read models and the preprocessing endpoints: access control, shapes, empty states, and the full one-action flow."""
import io

import numpy as np
import pandas as pd
import pytest

from app.core.config import get_settings

READ_PATHS = [
    "/api/v1/research/summary",
    "/api/v1/research/model-comparison",
    "/api/v1/research/validation",
    "/api/v1/research/architecture-evaluation",
    "/api/v1/research/causal-assessment",
    "/api/v1/research/risk-assessment",
]


def _h():
    return {"X-Research-Token": get_settings().research_console_token}


@pytest.fixture()
def auth_on(monkeypatch):
    monkeypatch.setattr(get_settings(), "auth_enabled", True)


def test_anonymous_requests_are_refused(client):
    for p in READ_PATHS + ["/api/v1/research/llm-evaluation/runs/anything"]:
        assert client.get(p).status_code == 403, p


def test_business_user_cannot_read_or_preprocess_but_admin_can(client, auth_on, db_session):
    from tests.admin_support import admin_token

    sme = client.post("/api/v1/auth/register", json={"email": "s@x.com", "password": "orange-river-4271", "role": "sme"}).json()["access_token"]
    admin = admin_token(client, db_session, "a@x.com")
    for p in READ_PATHS:
        assert client.get(p, headers={"Authorization": f"Bearer {sme}"}).status_code == 403, p
        assert client.get(p, headers={"Authorization": f"Bearer {admin}"}).status_code == 200, p
    vid = "00000000-0000-0000-0000-000000000000"
    assert client.get(f"/api/v1/research/preprocessing/{vid}/plan", headers={"Authorization": f"Bearer {sme}"}).status_code == 403
    assert client.post(f"/api/v1/research/preprocessing/{vid}/run", json={}, headers={"Authorization": f"Bearer {sme}"}).status_code == 403


def test_validation_never_reports_an_empty_pass(client):
    body = client.get("/api/v1/research/validation", headers=_h()).json()
    assert body["state"] in {"no_checks_run", "failed", "passed_with_warnings", "passed"}
    assert set(body["counts"]) == {"passed", "failed", "warning", "not_applicable"}
    assert body["total_checks"] == len(body["checks"]) == sum(body["counts"].values())
    if body["checks_run"] == 0:
        assert body["state"] == "no_checks_run"
    for c in body["checks"]:
        if c["status"] in ("failed", "warning"):
            assert c["explanation"] and c["remedy"], c["id"]


def test_summary_findings_are_labelled_with_an_evidence_type(client):
    s = client.get("/api/v1/research/summary", headers=_h()).json()
    assert {e["key"] for e in s["evidence_legend"]} == {"measured", "estimated", "simulated", "not_evaluated"}
    for f in s["key_findings"]:
        assert f["evidence"] in {"measured", "measured_on_synthetic_data", "simulated", "estimated", "not_evaluated"}
        assert f["text"]
    assert s["status"]["validation_state"]


def test_model_comparison_lists_runs_or_says_not_run(client):
    r = client.get("/api/v1/research/model-comparison", headers=_h()).json()
    assert set(r["datasets"]) == set(r["dataset_catalogue"])
    for k, v in r["datasets"].items():
        assert (v is None) == (k in r["not_run"])  # no placeholder object for an unrun dataset


def test_risk_assessment_declares_the_decision_risk_score_unevaluated(client):
    r = client.get("/api/v1/research/risk-assessment", headers=_h()).json()
    assert r["decision_risk_score"]["status"] == "not_evaluated"
    assert r["definitions"][0]["calibration"] == "not_applicable"


def test_llm_run_detail_rejects_unknown_and_malformed_ids(client):
    assert client.get("/api/v1/research/llm-evaluation/runs/does_not_exist_run", headers=_h()).status_code == 404
    assert client.get("/api/v1/research/llm-evaluation/runs/..%2F..%2Fsecret", headers=_h()).status_code in (404, 422)


# ------------------------------------------------------------------ one-action preprocessing
def _csv(df):
    b = io.BytesIO()
    df.to_csv(b, index=False)
    return b.getvalue()


def test_preprocessing_flow_plan_run_history_download(client, tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "research_data_path", str(tmp_path / "research_uploads"))
    rng = np.random.default_rng(0)
    df = pd.DataFrame({"Order Date": pd.date_range("2025-01-01", periods=60).strftime("%Y-%m-%d"), "Units Sold": rng.integers(1, 20, 60).astype(str),
                       "Revenue": rng.uniform(100, 500, 60).round(2)})
    up = client.post("/api/v1/research/datasets/upload", files={"file": ("sales.csv", _csv(df), "text/csv")},
                     data={"name": "PP test", "domain": "forecasting"}, headers=_h())
    assert up.status_code == 201, up.text
    vid = up.json()["id"]

    plan = client.get(f"/api/v1/research/preprocessing/{vid}/plan", headers=_h()).json()
    ids = {s["id"]: s for s in plan["steps"]}
    assert plan["rows"] == 60 and ids["normalize_names"]["applies"] and ids["chronological_split"]["applies"]
    assert plan["runs"] == []

    assert client.post(f"/api/v1/research/preprocessing/{vid}/run", json={"steps": ["nope"]}, headers=_h()).status_code == 422
    assert client.post(f"/api/v1/research/preprocessing/{vid}/run", json={"unexpected": 1}, headers=_h()).status_code == 422

    run = client.post(f"/api/v1/research/preprocessing/{vid}/run", json={}, headers=_h())
    assert run.status_code == 200, run.text
    r = run.json()
    assert r["status"] == "completed" and r["rows_in"] == r["rows_out"] == 60 and r["raw_dataset_modified"] is False
    assert "order_date" in r["output_columns"] and "_split" in r["output_columns"]

    hist = client.get(f"/api/v1/research/preprocessing/{vid}/runs", headers=_h()).json()
    assert [h["run_id"] for h in hist] == [r["run_id"]]
    dl = client.get(f"/api/v1/research/preprocessing/{vid}/runs/{r['run_id']}/download", headers=_h())
    assert dl.status_code == 200 and dl.headers["content-type"].startswith("text/csv")
    out = pd.read_csv(io.BytesIO(dl.content))
    assert len(out) == 60 and out["revenue"].sum() == pytest.approx(df["Revenue"].sum())

    assert client.get(f"/api/v1/research/preprocessing/{vid}/runs/pp_20200101T000000Z_00000000", headers=_h()).status_code == 404


def test_preprocessing_unknown_dataset_version_is_404(client):
    assert client.get("/api/v1/research/preprocessing/00000000-0000-0000-0000-00000000dead/plan", headers=_h()).status_code == 404
