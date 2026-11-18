"""``GET /research/ml-benchmark``: admin-only, read-only, never presents smoke or superseded runs as results."""
import json

import pytest

from app.core.config import get_settings
from app.services import ml_benchmark_service as svc


def _run(root, name, results, meta=None, superseded=False):
    d = root / name
    d.mkdir(parents=True)
    (d / "results.json").write_text(json.dumps(results), encoding="utf-8")
    (d / "metadata.json").write_text(json.dumps({"quick": False, "created_utc": "2026-10-15T00:00:00Z", "git_revision": "abc", **(meta or {})}), encoding="utf-8")
    if superseded:
        (d / "SUPERSEDED.md").write_text("superseded", encoding="utf-8")


F2 = {"evidence_class": "real_single_business_transactions", "test_window": ["2011-11-12", "2011-12-09"],
      "total_daily_revenue": {"n_series": 1, "n_test_points": 28, "validation_selected_method": "single:xgboost:depth6",
                              "test": {"baseline:seasonal_naive": {"wape": 0.33, "mae": 1, "rmse": 2, "bias": -0.2, "aggregate_daily_wape": 0.33},
                                       "xgboost:depth6": {"wape": 0.24, "mae": 1, "rmse": 2, "bias": -0.1, "aggregate_daily_wape": 0.24}},
                              "paired_test_comparisons": {}}}
C = {"evidence_class": "real_data_proxy_label", "best_single_by_validation_auc": "random_forest", "rows": {"train": 1, "validation": 1, "test": 1},
     "models": {"random_forest": {"uncalibrated": {"test": {"roc_auc": 0.8, "pr_auc": 0.8, "brier": 0.19, "ece": 0.09}},
                                  "isotonic": {"test": {"ece": 0.12}}, "sigmoid": {"test": {"ece": 0.12}}}},
     "paired_vs_best_single_by_validation_auc": {}}


def test_service_groups_runs_and_hides_smoke_and_superseded(tmp_path, monkeypatch):
    monkeypatch.setattr(svc, "RUNS_DIR", tmp_path)
    _run(tmp_path, "f2_20261015T010000Z_aaaa", F2)
    _run(tmp_path, "f2_20261016T010000Z_bbbb", {**F2, "evidence_class": "SMOKE"}, meta={"quick": True})   # smoke: never shown
    _run(tmp_path, "c1_20261015T010000Z_cccc", C)
    _run(tmp_path, "c2_20261015T010000Z_dddd", C, superseded=True)                                       # superseded: never shown
    out = svc.latest_results()
    assert [r["task"] for r in out["runs"]] == ["f2", "c1"]
    f2 = out["runs"][0]
    assert f2["run_id"] == "f2_20261015T010000Z_aaaa" and f2["evidence_class"] == "real_single_business_transactions"
    rows = f2["sections"][0]["rows"]
    assert rows[0]["method"] == "xgboost:depth6" and rows[0]["selected_by_validation"] is True and rows[1]["kind"] == "baseline"
    assert out["runs"][1]["rows"][0]["selected_by_validation"] is True and out["runs"][1]["evidence_class"] == "real_data_proxy_label"


def test_selected_method_and_best_single_are_distinguished_when_an_ensemble_wins_validation(tmp_path, monkeypatch):
    monkeypatch.setattr(svc, "RUNS_DIR", tmp_path)
    res = {**F2}
    res["total_daily_revenue"] = {**F2["total_daily_revenue"], "validation_selected_method": "ensemble:nnls_weighted(LOO)", "best_single_by_validation": "xgboost:depth6",
                                  "test": {**F2["total_daily_revenue"]["test"], "ensemble:nnls_weighted": {"wape": 0.25, "mae": 1, "rmse": 2, "bias": 0, "aggregate_daily_wape": 0.25}}}
    _run(tmp_path, "f2_20261015T010000Z_aaaa", res)
    rows = {r["method"]: r for r in svc.latest_results()["runs"][0]["sections"][0]["rows"]}
    assert rows["ensemble:nnls_weighted"]["selected_by_validation"] is True and rows["ensemble:nnls_weighted"]["best_single_by_validation"] is False
    assert rows["xgboost:depth6"]["selected_by_validation"] is False and rows["xgboost:depth6"]["best_single_by_validation"] is True


def test_service_with_no_runs_is_an_explicit_empty_state(tmp_path, monkeypatch):
    monkeypatch.setattr(svc, "RUNS_DIR", tmp_path / "missing")
    out = svc.latest_results()
    assert out["available"] is False and out["runs"] == []


def test_the_real_stored_runs_are_summarised_without_error():
    out = svc.latest_results()
    if not out["available"]:
        pytest.skip("no benchmark runs stored")
    tasks = {r["task"] for r in out["runs"]}
    assert {"f1", "f2", "c1", "c2", "p1"} <= tasks
    c2 = next(r for r in out["runs"] if r["task"] == "c2")
    assert "SUPERSEDED" not in c2["run_id"] and c2["evidence_class"].lower().startswith("synthetic")
    assert all(r["run_id"].split("_")[0] == r["task"] for r in out["runs"])


def test_endpoint_is_admin_only(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "auth_enabled", True)
    assert client.get("/api/v1/research/ml-benchmark").status_code in (401, 403)
    sme = client.post("/api/v1/auth/register", json={"email": "m@x.com", "password": "orange-river-4271", "role": "sme"}).json()["access_token"]
    assert client.get("/api/v1/research/ml-benchmark", headers={"Authorization": f"Bearer {sme}"}).status_code == 403
