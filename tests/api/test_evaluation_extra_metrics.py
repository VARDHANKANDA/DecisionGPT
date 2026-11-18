"""RMSSE, aggregate-day and median-series WAPE, log loss, the constant-forecast Brier reference and top-decile lift on the evaluation console:
each card must be a value a run recorded (or a clearly labelled state), with its provenance, and must equal the stored number."""
import json

import pytest

from app.core.config import get_settings
from app.services import evaluation_console_service as svc
from app.services import ml_benchmark_service as bench

URL = "/api/v1/research/evaluation"


def _h():
    return {"X-Research-Token": get_settings().research_console_token}


def _by_key(cards):
    return {c["key"]: c for c in cards}


def _bench_run(root, name, results):
    d = root / name
    d.mkdir(parents=True)
    (d / "results.json").write_text(json.dumps(results), encoding="utf-8")
    (d / "metadata.json").write_text(json.dumps({"quick": False, "created_utc": "2026-10-15T00:00:00Z", "git_revision": "abc"}), encoding="utf-8")


def _row(mae, **extra):
    return {"wape": 0.7, "mae": mae, "rmse": mae * 1.5, "bias": -0.05, "n_points": 9800, "n_series": 350, "zero_share": 0.4, **extra}


F1 = {"evidence_class": "public_real_data", "test_window": ["2016-04-25", "2016-05-22"], "n_series": 350, "n_test_points": 9800,
      "validation_selected_method": "single:xgboost:depth6",
      "test": {"baseline:seasonal_naive_28": _row(1.45, rmsse_mean=1.10, rmsse_series_excluded_constant_history=0, aggregate_daily_wape=0.109,
                                                 median_series_wape=1.149, series_with_defined_wape=344),
               "xgboost:depth6": _row(1.18, rmsse_mean=0.83, rmsse_series_excluded_constant_history=6, aggregate_daily_wape=0.07,
                                      median_series_wape=1.03, series_with_defined_wape=344)},
      "paired_test_comparisons": {}}


def _xgb_cards(client):
    rows = client.get(URL, headers=_h()).json()["sections"]["benchmark"]["runs"][0]["sections"][0]["rows"]
    return _by_key(next(r for r in rows if r["method"] == "xgboost:depth6")["cards"])


def test_scale_free_and_aggregate_benchmark_metrics_are_shown_with_their_provenance(client, db_session, monkeypatch, tmp_path):
    _bench_run(tmp_path, "f1_20261015T010000Z_aaaa", F1)
    monkeypatch.setattr(bench, "RUNS_DIR", tmp_path)
    x = _xgb_cards(client)
    assert x["rmsse"]["value"] == 0.83 and x["rmsse"]["direction"] == "lower_is_better" and "6 series" in x["rmsse"]["caveat"]
    assert x["aggregate_daily_wape"]["value"] == pytest.approx(7.0) and "must not be compared" in x["aggregate_daily_wape"]["caveat"]
    assert x["median_series_wape"]["value"] == pytest.approx(103.0) and x["median_series_wape"]["context"]["series_with_a_defined_wape"] == "344 of 350"
    assert x["median_series_wape"]["context"]["test_window"] == ["2016-04-25", "2016-05-22"]
    # the stored "bias" is relative (sum error / sum actual): it is shown as a percentage, never as units
    assert "bias" not in x and x["relative_bias"]["value"] == pytest.approx(-5.0) and x["relative_bias"]["unit"] == "percent"
    assert x["mae"]["unit"] == "units/day"


def test_a_value_the_run_did_not_record_is_not_available_not_zero(client, db_session, monkeypatch, tmp_path):
    res = json.loads(json.dumps(F1))
    for k in ("rmsse_mean", "median_series_wape", "aggregate_daily_wape"):
        del res["test"]["xgboost:depth6"][k]
    _bench_run(tmp_path, "f1_20261015T010000Z_aaaa", res)
    monkeypatch.setattr(bench, "RUNS_DIR", tmp_path)
    x = _xgb_cards(client)
    for k in ("rmsse", "aggregate_daily_wape", "median_series_wape"):
        assert x[k]["status"] == "not_available" and x[k]["value"] is None and x[k]["reason"]


def test_a_single_series_run_does_not_pretend_aggregate_and_median_wape_are_new_information(client, db_session, monkeypatch, tmp_path):
    res = {"evidence_class": "real_single_business_transactions", "test_window": ["2011-11-12", "2011-12-09"],
           "total_daily_revenue": {"n_series": 1, "n_test_points": 28, "validation_selected_method": "single:xgboost:depth6",
                                   "test": {"baseline:seasonal_naive": _row(10.0, n_series=1, n_points=28, aggregate_daily_wape=0.7, median_series_wape=0.7, series_with_defined_wape=1),
                                            "xgboost:depth6": _row(8.0, n_series=1, n_points=28, aggregate_daily_wape=0.6, median_series_wape=0.6, series_with_defined_wape=1)},
                                   "paired_test_comparisons": {}}}
    _bench_run(tmp_path, "f2_20261015T010000Z_aaaa", res)
    monkeypatch.setattr(bench, "RUNS_DIR", tmp_path)
    x = _xgb_cards(client)
    assert x["aggregate_daily_wape"]["status"] == "not_evaluated" and x["median_series_wape"]["status"] == "not_evaluated"
    assert x["mae"]["unit"] == "revenue/day"                                          # a revenue series is not measured in units


C1 = {"evidence_class": "real_data_proxy_label", "best_single_by_validation_auc": "random_forest", "rows": {"train": 1, "validation": 1, "test": 5256},
      "models": {"random_forest": {"uncalibrated": {"test": {"roc_auc": 0.8, "pr_auc": 0.8, "brier": 0.19, "ece": 0.09, "log_loss": 0.56, "n": 5256,
                                                              "prevalence": 0.56, "brier_prevalence_baseline": 0.2458}}}},
      "paired_vs_best_single_by_validation_auc": {}}


def _c1_cards(client):
    return _by_key(client.get(URL, headers=_h()).json()["sections"]["benchmark"]["runs"][0]["rows"][0]["cards"])


def test_classification_benchmark_shows_log_loss_and_the_constant_forecast_reference(client, db_session, monkeypatch, tmp_path):
    _bench_run(tmp_path, "c1_20261015T010000Z_cccc", C1)
    monkeypatch.setattr(bench, "RUNS_DIR", tmp_path)
    x = _c1_cards(client)
    assert x["log_loss"]["value"] == 0.56 and x["log_loss"]["direction"] == "lower_is_better" and "baseline" in x["log_loss"]["caveat"]
    assert x["brier_baseline"]["value"] == 0.2458
    assert x["brier_vs_baseline"]["value"] == pytest.approx((0.2458 - 0.19) / 0.2458 * 100)
    assert x["brier"]["context"]["n"] == 5256


def test_no_brier_comparison_without_both_recorded_values(client, db_session, monkeypatch, tmp_path):
    res = json.loads(json.dumps(C1))
    del res["models"]["random_forest"]["uncalibrated"]["test"]["brier_prevalence_baseline"]
    _bench_run(tmp_path, "c1_20261015T010000Z_cccc", res)
    monkeypatch.setattr(bench, "RUNS_DIR", tmp_path)
    x = _c1_cards(client)
    assert x["brier_baseline"]["status"] == "not_available" and x["brier_vs_baseline"]["status"] == "not_available" and x["brier_vs_baseline"]["value"] is None


def test_the_console_shows_exactly_the_values_in_the_real_stored_benchmark_files(client, db_session):
    """Read-only comparison with the frozen results on disk: every number on a card equals the stored number (no recomputation; cards round to 6 decimals)."""
    real = bench.latest_results()
    if not real.get("available"):
        pytest.skip("no stored benchmark runs on this machine")
    shown = {r["run_id"]: r for r in client.get(URL, headers=_h()).json()["sections"]["benchmark"]["runs"]}
    checked = 0
    for r in real["runs"]:
        if r["kind"] == "forecast":
            for sec_in, sec_out in zip(r["sections"], shown[r["run_id"]]["sections"]):
                for x, y in zip(sec_in["rows"], sec_out["rows"]):
                    cards = _by_key(y["cards"])
                    for key, src, scale in (("mae", "mae", 1), ("rmse", "rmse", 1), ("wape", "wape", 100), ("rmsse", "rmsse_mean", 1),
                                            ("median_series_wape", "median_series_wape", 100), ("relative_bias", "bias", 100)):
                        single_series_skip = key == "median_series_wape" and sec_in["n_series"] == 1
                        if x.get(src) is not None and not single_series_skip:
                            assert cards[key]["value"] == pytest.approx(x[src] * scale, abs=1e-6), (r["run_id"], x["method"], key)
                            checked += 1
        elif r["kind"] == "classification":
            for x, y in zip(r["rows"], shown[r["run_id"]]["rows"]):
                cards = _by_key(y["cards"])
                for key in ("roc_auc", "pr_auc", "brier", "ece", "log_loss"):
                    if x.get(key) is not None:
                        assert cards[key]["value"] == pytest.approx(x[key], abs=1e-6), (r["run_id"], x["method"], key)
                        checked += 1
    assert checked > 50


def _customer_report(**top):
    c = {"cutoff": "2026-05-01", "status": "evaluated", "customers": 123, "inactive": 40, "prevalence": 40 / 123, "roc_auc": 0.7, "roc_auc_recency_only": 0.65, **top}
    return {"id": "c1", "generated_at": "2026-10-21T00:00:00Z", "model": {"name": "churn", "version": "v1"}, "headline": "h", "target": {"definition": "d", "limits": "l"},
            "calibration": {"evaluated": False, "reason": "proxy"}, "cutoffs": [c]}


def test_customer_top_decile_cards_state_the_group_and_the_proxy_label():
    out = svc.present_run(_customer_report(top_decile_lift=1.8, top_decile_inactive_rate=0.6), "customer")
    lift = next(c for c in out["cutoffs"][0]["cards"] if c["key"] == "top_decile_lift")
    assert lift["value"] == 1.8 and lift["display"].startswith("1.80") and lift["direction"] == "higher_is_better"
    assert lift["context"]["top_group"].startswith("13 highest-scored customers")           # ceil(10% of 123)
    assert "proxy" in lift["caveat"].lower() and "1.0 is no better than" in lift["explanation"]


def test_an_older_customer_report_without_the_top_decile_says_so():
    out = svc.present_run(_customer_report(), "customer")
    c = next(c for c in out["cutoffs"][0]["cards"] if c["key"] == "top_decile_lift")
    assert c["status"] == "not_available" and c["value"] is None and "did not record" in c["reason"]
