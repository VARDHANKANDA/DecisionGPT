"""``/research/evaluation``: admin-only, read-only. Every number is one that a run recorded; derived values are checked against hand arithmetic,
the evidence kinds stay apart, and nothing is shown as a probability, a metric or a result that was not computed."""
import json

import pytest

from app.core.config import get_settings
from app.models.ml_model import MLModel
from app.services import evaluation_console_service as svc
from app.services import ml_benchmark_service as bench
from tests.admin_support import admin_token
from tests.api.test_platform_api import P, _owner, auth_on  # noqa: F401  (auth_on is a fixture)
from tests.api.test_validation_api import _upload_sales, _weekly_rows

URL = "/api/v1/research/evaluation"


def _h():
    return {"X-Research-Token": get_settings().research_console_token}


def _model(db, name, mtype, metrics, version="v1", dataset="platform_v1"):
    m = MLModel(model_name=name, model_type=mtype, version=version, dataset_version=dataset, feature_version="f1", metrics_json=metrics,
                model_path=f"models/{name}", status="experimental", task="forecasting" if mtype.startswith("forecasting") else "churn")
    db.add(m)
    db.commit()
    return m


NEW_FORECAST = {"mae": 4.0, "rmse": 6.0, "mape": 22.0, "wape": 0.25, "bias": -0.5, "n_eval": 400, "n_zero_actual": 0, "n_invalid": 0,
                "baseline_mae": 5.0, "val_mae": 3.5, "val_rmse": 5.0, "val_wape": 0.2, "val_baseline_mae": 4.5}
OLD_FORECAST = {"mae": 4.0, "rmse": 6.0, "mape": 8.7e8}
CHURN = {"roc_auc": 0.8, "pr_auc": 0.7, "precision": 0.9, "recall": 0.1, "f1": 0.18, "brier": 0.2, "ece": 0.05, "val_roc_auc": 0.78, "val_pr_auc": 0.69,
         "val_threshold": 0.4, "threshold_from_validation": 0.4, "confusion_tp": 30, "confusion_fp": 10, "confusion_fn": 20, "confusion_tn": 140,
         "test_prevalence": 0.25, "train_prevalence": 0.24, "prevalence_shift": 0.01}


def _by_key(cards):
    return {c["key"]: c for c in cards}


@pytest.fixture()
def no_benchmark(monkeypatch, tmp_path):
    monkeypatch.setattr(bench, "RUNS_DIR", tmp_path / "none")


# ------------------------------------------------------------------ access
def test_the_evaluation_endpoints_need_research_credentials(client):
    assert client.get(URL).status_code == 403
    assert client.get(f"{URL}/business/00000000-0000-0000-0000-000000000000").status_code in (403, 404)


def test_an_sme_account_cannot_read_the_console(client, db_session, auth_on):  # noqa: F811
    _, h = _owner(client, "sme@example.com", "Shop")
    assert client.get(URL, headers=h).status_code == 403


# ------------------------------------------------------------------ empty state
def test_with_nothing_recorded_the_page_says_so_and_invents_nothing(client, db_session, no_benchmark):
    body = client.get(URL, headers=_h()).json()
    tr = body["sections"]["training"]
    assert tr["forecasting"] == [] and tr["classification"] == [] and "No models are registered" in tr["empty"]
    assert body["sections"]["benchmark"]["available"] is False and body["sections"]["benchmark"]["runs"] == []
    assert body["sections"]["production"]["status"] == "not_evaluated" and body["sections"]["production"]["reason"]
    assert body["glossary"] and body["limitations"]


# ------------------------------------------------------------------ forecasting model cards
def test_forecasting_cards_show_recorded_values_baseline_and_honest_unavailables(client, db_session, no_benchmark):
    _model(db_session, "sales_forecast_xgboost", "forecasting_xgboost", NEW_FORECAST)
    body = client.get(URL, headers=_h()).json()
    m = body["sections"]["training"]["forecasting"][0]
    t = _by_key(m["test"])
    assert t["mae"]["value"] == 4.0 and t["mae"]["unit"] == "units/day" and t["mae"]["direction"] == "lower_is_better"
    assert t["rmse"]["value"] == 6.0
    assert t["wape"]["value"] == pytest.approx(25.0) and t["wape"]["display"] == "25.0%"      # stored fraction 0.25 shown as a percentage
    assert t["bias"]["value"] == -0.5 and "Negative" in t["bias"]["sign_note"]
    assert t["mape"]["status"] == "available" and t["n_eval"]["value"] == 400
    # validation is a separate block, never mixed into the test cards
    assert {c["context"]["block"] for c in m["validation"]} == {"validation"} and {c["context"]["block"] for c in m["test"]} == {"test"}
    # baseline comparison: derived from two recorded MAEs on the same rows
    b = _by_key(m["baseline"]["test"])
    assert b["baseline_mae"]["value"] == 5.0 and b["mae_vs_baseline"]["value"] == pytest.approx(20.0)
    assert m["baseline"]["verdict"] == "better_than_baseline" and "same rows" in m["baseline"]["same_rows"]
    assert _by_key(m["baseline"]["validation"])["mae_vs_baseline"]["value"] == pytest.approx((4.5 - 3.5) / 4.5 * 100)
    # no intervals and no horizons exist for registered models: stated, not faked
    assert m["interval_coverage"]["status"] == "not_evaluated" and m["interval_coverage"]["value"] is None
    assert m["by_horizon"]["status"] == "not_evaluated"


def test_an_older_run_marks_what_it_did_not_record_and_never_shows_its_meaningless_mape(client, db_session, no_benchmark):
    _model(db_session, "old_model", "forecasting_linear", OLD_FORECAST)
    m = client.get(URL, headers=_h()).json()["sections"]["training"]["forecasting"][0]
    t = _by_key(m["test"])
    assert t["mape"]["status"] == "unreliable" and t["mape"]["value"] is None
    assert t["n_eval"]["status"] == "not_available" and "Retrain" in t["n_eval"]["reason"]
    assert t["bias"]["status"] == "not_available" and t["wape"]["status"] == "not_available"
    b = _by_key(m["baseline"]["test"])
    assert b["baseline_mae"]["status"] == "not_available" and b["mae_vs_baseline"]["value"] is None
    assert m["baseline"]["verdict"] is None and m["validation"] == []


def test_the_naive_model_is_not_compared_with_itself(client, db_session, no_benchmark):
    _model(db_session, "naive", "forecasting_naive", {**NEW_FORECAST, "mae": 5.0})
    m = client.get(URL, headers=_h()).json()["sections"]["training"]["forecasting"][0]
    c = _by_key(m["baseline"]["test"])["mae_vs_baseline"]
    assert c["value"] is None and "baseline itself" in c["reason"] and m["baseline"]["verdict"] is None


def test_a_zero_actual_makes_mape_unreliable_even_for_a_new_run(client, db_session, no_benchmark):
    _model(db_session, "sparse", "forecasting_xgboost", {**NEW_FORECAST, "n_zero_actual": 120, "mape": 40.0})
    t = _by_key(client.get(URL, headers=_h()).json()["sections"]["training"]["forecasting"][0]["test"])
    assert t["mape"]["status"] == "unreliable" and "120" in t["mape"]["reason"]


# ------------------------------------------------------------------ classification model cards
def test_classification_cards_are_consistent_with_the_confusion_matrix_and_never_a_probability(client, db_session, no_benchmark):
    _model(db_session, "churn_logistic_regression", "churn_logistic_regression", CHURN)
    m = client.get(URL, headers=_h()).json()["sections"]["training"]["classification"][0]
    t = _by_key(m["test"])
    assert m["confusion_matrix"] == {"tp": 30, "fp": 10, "fn": 20, "tn": 140, "n": 200, "positive_class": "churned = 1", "threshold": 0.4,
                                     "rows_are": "actual", "columns_are": "predicted at the threshold"}
    assert t["precision"]["value"] == pytest.approx(30 / 40) and t["recall"]["value"] == pytest.approx(30 / 50)
    assert t["f1"]["value"] == pytest.approx(60 / 90) and t["accuracy"]["value"] == pytest.approx(170 / 200)
    assert t["precision"]["context"]["threshold"] == 0.4                            # NOT the stored precision measured at 0.5
    assert t["roc_auc"]["value"] == 0.8 and t["pr_auc"]["value"] == 0.7 and t["roc_auc"]["context"]["positive_class"] == "churned = 1"
    assert m["calibrated"] is False and "not a calibrated probability" in m["score_meaning"]
    assert m["class_balance"]["test_positive_rate"]["value"] == 0.25 and m["class_balance"]["shift"] == 0.01
    assert "stratified random" in m["setup"]["split_scheme"]


def test_a_large_prevalence_shift_warns_that_calibration_is_not_comparable(client, db_session, no_benchmark):
    _model(db_session, "shifted", "churn_logistic_regression", {**CHURN, "prevalence_shift": 0.2})
    t = _by_key(client.get(URL, headers=_h()).json()["sections"]["training"]["classification"][0]["test"])
    assert "not comparable" in t["ece"]["caveat"]


def test_an_older_classifier_without_a_confusion_matrix_does_not_invent_accuracy(client, db_session, no_benchmark):
    _model(db_session, "oldchurn", "churn_random_forest", {"roc_auc": 0.7, "precision": 0.6, "recall": 0.5, "f1": 0.55})
    m = client.get(URL, headers=_h()).json()["sections"]["training"]["classification"][0]
    t = _by_key(m["test"])
    assert m["confusion_matrix"] is None and t["accuracy"]["status"] == "not_available" and "confusion matrix" in t["accuracy"]["reason"]
    assert t["precision"]["context"]["threshold"] == 0.5 and t["pr_auc"]["status"] == "not_available" and t["brier"]["status"] == "not_available"


def test_degenerate_confusion_counts_give_undefined_not_zero(client, db_session, no_benchmark):
    _model(db_session, "nothing_flagged", "churn_logistic_regression", {**CHURN, "confusion_tp": 0, "confusion_fp": 0, "confusion_fn": 0, "confusion_tn": 50})
    t = _by_key(client.get(URL, headers=_h()).json()["sections"]["training"]["classification"][0]["test"])
    assert t["precision"]["status"] == "not_available" and "undefined" in t["precision"]["reason"]
    assert t["recall"]["status"] == "not_available" and t["f1"]["status"] == "not_available"
    assert t["accuracy"]["value"] == 1.0


# ------------------------------------------------------------------ never NaN / Infinity
def test_a_non_finite_stored_value_becomes_not_available_and_the_payload_stays_valid_json():
    m = MLModel(model_name="x", model_type="forecasting_xgboost", version="v1", dataset_version="d", feature_version="f", model_path="p", status="experimental",
                metrics_json={"mae": float("nan"), "rmse": float("inf"), "wape": float("-inf"), "bias": float("nan"), "mape": float("nan"), "n_eval": 3})
    out = svc._forecast_model(m)
    text = json.dumps(out, allow_nan=False)                                              # allow_nan=False raises on any NaN/Infinity
    assert "NaN" not in text and "Infinity" not in text
    assert all(c["value"] is None for c in out["test"] if c["key"] in ("mae", "rmse", "wape", "bias", "mape"))


# ------------------------------------------------------------------ benchmark section
F2 = {"evidence_class": "real_single_business_transactions", "test_window": ["2011-11-12", "2011-12-09"],
      "total_daily_revenue": {"n_series": 1, "n_test_points": 28, "validation_selected_method": "single:xgboost:depth6",
                              "test": {"baseline:seasonal_naive": {"wape": 0.33, "mae": 10.0, "rmse": 12.0, "bias": -0.2, "n_points": 28},
                                       "xgboost:depth6": {"wape": 0.24, "mae": 8.0, "rmse": 11.0, "bias": -0.1, "n_points": 28}},
                              "paired_test_comparisons": {}}}


def test_benchmark_rows_compare_with_the_best_baseline_on_the_same_run_and_stay_separate(client, db_session, monkeypatch, tmp_path):
    d = tmp_path / "f2_20261015T010000Z_aaaa"
    d.mkdir()
    (d / "results.json").write_text(json.dumps(F2), encoding="utf-8")
    (d / "metadata.json").write_text(json.dumps({"quick": False, "created_utc": "2026-10-15T00:00:00Z", "git_revision": "abc"}), encoding="utf-8")
    monkeypatch.setattr(bench, "RUNS_DIR", tmp_path)
    _model(db_session, "sales_forecast_xgboost", "forecasting_xgboost", NEW_FORECAST)
    body = client.get(URL, headers=_h()).json()
    run = body["sections"]["benchmark"]["runs"][0]
    sec = run["sections"][0]
    assert sec["baseline_used_for_comparison"] == "baseline:seasonal_naive" and run["evidence_class"] == "real_single_business_transactions"
    rows = {r["method"]: _by_key(r["cards"]) for r in sec["rows"]}
    assert rows["xgboost:depth6"]["mae_vs_baseline"]["value"] == pytest.approx(20.0)
    assert rows["xgboost:depth6"]["mae"]["context"]["n"] == 28
    assert rows["baseline:seasonal_naive"]["mae_vs_baseline"]["value"] is None
    # the registered model and the benchmark are different sections: nothing from one appears in the other
    assert body["sections"]["training"]["forecasting"][0]["model_name"] == "sales_forecast_xgboost"
    assert "sales_forecast_xgboost" not in json.dumps(body["sections"]["benchmark"])


# ------------------------------------------------------------------ one business's own validation
@pytest.fixture()
def admin_world(client, db_session, auth_on):  # noqa: F811
    token = admin_token(client, db_session)
    h = {"Authorization": f"Bearer {token}"}
    bid = client.post(P, json={"name": "Admin Shop", "industry": "retail", "business_type": "D2C", "business_size": "small"}, headers=h).json()["id"]
    other, _ = _owner(client, "owner@example.com", "Other Shop")
    return client, h, bid, other


def test_a_business_that_has_not_been_validated_says_so(admin_world):
    client, h, bid, _ = admin_world
    body = client.get(f"{URL}/business/{bid}", headers=h).json()
    assert body["forecast"] is None and body["customer"] is None and body["evidence"] == "business"


def test_running_the_forecast_validation_presents_registry_cards_with_horizons_and_coverage(admin_world):
    client, h, bid, _ = admin_world
    _upload_sales(client, bid, h, _weekly_rows(150, seed=3))
    r = client.post(f"{URL}/business/{bid}/run?kind=forecast", headers=h)
    assert r.status_code == 200, r.text
    run = r.json()
    assert run["kind"] == "forecast" and run["horizons"]
    evaluated = [x for x in run["horizons"] if x["status"] == "evaluated"]
    assert evaluated, [x["status"] for x in run["horizons"]]
    h0 = evaluated[0]
    keys = _by_key(h0["cards"])
    assert {"mae", "rmse", "wape", "bias", "relative_bias", "n_eval"} <= set(keys)
    assert keys["mae"]["unit"] == "units/day" and keys["bias"]["sign_note"]
    assert h0["interval_coverage"]["key"] == "coverage" and h0["interval_coverage"]["context"]["promised"]
    assert {c["reference"] for c in h0["baseline_comparison"]} == {"naive_last", "trailing_mean_28", "seasonal_naive_7"}
    # the page reads the same stored report back; the numbers are identical (no recomputation, no drift)
    again = client.get(f"{URL}/business/{bid}", headers=h).json()["forecast"]
    first = next(x for x in again["horizons"] if x["horizon_days"] == h0["horizon_days"])
    assert _by_key(first["cards"])["mae"]["value"] == keys["mae"]["value"]
    json.dumps(run, allow_nan=False)


def test_a_business_cannot_be_read_by_someone_who_does_not_own_it(admin_world):
    client, h, _, other = admin_world
    assert client.get(f"{URL}/business/{other}", headers=h).status_code == 404
    assert client.post(f"{URL}/business/{other}/run?kind=forecast", headers=h).status_code == 404
    assert client.get(f"{URL}/business/not-a-uuid", headers=h).status_code == 404


def test_the_evaluation_run_changes_no_registered_model(admin_world, db_session):
    client, h, bid, _ = admin_world
    _model(db_session, "keepme", "forecasting_xgboost", NEW_FORECAST)

    def state():
        return sorted((m.model_name, m.version, m.status, json.dumps(m.metrics_json, sort_keys=True)) for m in db_session.query(MLModel).all())

    before = state()
    _upload_sales(client, bid, h, _weekly_rows(120, seed=5))
    client.post(f"{URL}/business/{bid}/run?kind=forecast", headers=h)
    db_session.expire_all()
    assert state() == before
