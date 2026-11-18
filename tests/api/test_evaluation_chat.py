"""Evaluation results in chat: recognised by rules, answered from the evaluation service, scoped by who is asking.

Nothing here calls a language model; where a fake model is installed it is only there to prove it is never asked.
"""
import json
import re

import pytest

from app.core.config import get_settings
from app.models.ml_model import MLModel
from app.services import analytics_chat_service, evaluation_chat_service as chat
from app.services import evaluation_console_service as console
from app.services import ml_benchmark_service as bench
from tests.admin_support import admin_token
from tests.analytics_llm_support import FakeLLM
from tests.api.test_platform_api import P, _owner, auth_on  # noqa: F401  (auth_on is a fixture)
from tests.api.test_validation_api import _upload_sales, _weekly_rows
from tests.integration.test_analytics import _create_business


def _research():
    return {"X-Research-Token": get_settings().research_console_token}


def ask(client, bid, message, headers=None):
    r = client.post(f"/api/v1/businesses/{bid}/chat", json={"message": message}, headers=headers or {})
    assert r.status_code == 200, r.text
    return r.json()


def ev(body):
    return body["details"]["evaluation"]


def _model(db, name, mtype, metrics, version="v1", dataset="platform_v1"):
    m = MLModel(model_name=name, model_type=mtype, version=version, dataset_version=dataset, feature_version="f1", metrics_json=metrics,
                model_path=f"models/{name}", status="experimental", task="forecasting" if mtype.startswith("forecasting") else "churn",
                training_run_id=f"run-{name}")
    db.add(m)
    db.commit()
    return m


FORECAST = {"mae": 4.0, "rmse": 6.0, "mape": 22.0, "wape": 0.25, "bias": -0.5, "n_eval": 400, "n_zero_actual": 0, "n_invalid": 0, "baseline_mae": 5.0,
            "val_mae": 3.5, "val_rmse": 5.0, "val_wape": 0.2, "val_baseline_mae": 4.5}
OLD_FORECAST = {"mae": 4.0, "rmse": 6.0, "mape": 8.7e8}
CHURN = {"roc_auc": 0.8, "pr_auc": 0.7, "precision": 0.9, "recall": 0.1, "f1": 0.18, "brier": 0.2, "ece": 0.05, "val_roc_auc": 0.78, "val_pr_auc": 0.69,
         "val_threshold": 0.4, "threshold_from_validation": 0.4, "confusion_tp": 30, "confusion_fp": 10, "confusion_fn": 20, "confusion_tn": 140,
         "test_prevalence": 0.25, "train_prevalence": 0.24, "prevalence_shift": 0.01}


def _row(mae, **extra):
    return {"wape": 0.7, "mae": mae, "rmse": mae * 1.5, "bias": -0.05, "n_points": 9800, "n_series": 350, "zero_share": 0.4, **extra}


def _bench_run(root, name, results):
    d = root / name
    d.mkdir(parents=True)
    (d / "results.json").write_text(json.dumps(results), encoding="utf-8")
    (d / "metadata.json").write_text(json.dumps({"quick": False, "created_utc": "2026-10-15T00:00:00Z", "git_revision": "abc"}), encoding="utf-8")


F1 = {"evidence_class": "public_real_data", "test_window": ["2016-04-25", "2016-05-22"], "n_series": 350, "n_test_points": 9800, "validation_selected_method": "single:xgboost:depth6",
      "test": {"baseline:seasonal_naive_28": _row(1.45, rmsse_mean=1.10, rmsse_series_excluded_constant_history=0, aggregate_daily_wape=0.109, median_series_wape=1.149, series_with_defined_wape=344),
               "xgboost:depth6": _row(1.18, rmsse_mean=0.83, rmsse_series_excluded_constant_history=6, aggregate_daily_wape=0.07, median_series_wape=1.03, series_with_defined_wape=344)},
      "paired_test_comparisons": {}}
C1 = {"evidence_class": "real_data_proxy_label", "best_single_by_validation_auc": "random_forest", "rows": {"train": 1, "validation": 1, "test": 5256}, "prevalence": {"train": 0.5, "validation": 0.6, "test": 0.56},
      "models": {"random_forest": {"uncalibrated": {"test": {"roc_auc": 0.8, "pr_auc": 0.8, "brier": 0.19, "ece": 0.09, "log_loss": 0.56, "n": 5256, "prevalence": 0.56, "brier_prevalence_baseline": 0.2458}}}},
      "paired_vs_best_single_by_validation_auc": {}}


@pytest.fixture()
def world(client, db_session, monkeypatch, tmp_path):
    """A business (auth off), registered models, two stored benchmark runs, and the research token to see them."""
    _bench_run(tmp_path, "f1_20261015T010000Z_aaaa", F1)
    _bench_run(tmp_path, "c1_20261015T010000Z_cccc", C1)
    monkeypatch.setattr(bench, "RUNS_DIR", tmp_path)
    _model(db_session, "sales_forecast_xgboost", "forecasting_xgboost", FORECAST)
    _model(db_session, "sales_forecast_linear", "forecasting_linear", OLD_FORECAST)
    _model(db_session, "churn_logistic_regression", "churn_logistic_regression", CHURN)
    bid = _create_business(client)
    return client, db_session, bid


@pytest.fixture()
def validated(world):
    """The same world after the business's own forecast validation was run (through chat, as a person would)."""
    client, db, bid = world
    _upload_sales(client, bid, {}, _weekly_rows(150, seed=3))
    body = ask(client, bid, "Run a forecast validation for my business")
    assert body["intent"] == "evaluation_results" and body["sufficient_evidence"] is True, body["answer"]
    return client, db, bid


# ------------------------------------------------------------------ recognising the question
@pytest.mark.parametrize("question,mode,category", [
    ("Show me all evaluation metrics.", "all", None),
    ("Show all evaluation results.", "all", None),
    ("What metrics are used to evaluate the models?", "definitions", None),
    ("How accurate is this model?", "accuracy", None),
    ("Compare the model with its baseline.", "baseline", None),
    ("Show the forecasting evaluation results.", "all", "forecasting"),
    ("Show the classification metrics.", "all", "classification"),
    ("How reliable are the customer scores?", "reliability", "classification"),
    ("Show results for each forecast horizon.", "horizon", "forecasting"),
    ("Which metrics are unavailable and why?", "unavailable", None),
    ("Show the historical benchmark results.", "all", None),
    ("Show the validation results for my business.", "all", None),
    ("What is the WAPE?", "specific", "forecasting"),
])
def test_the_supported_questions_are_recognised(question, mode, category):
    q = chat.detect(question)
    assert q is not None, question
    assert q.mode == mode and q.category == category, (q.mode, q.category)


@pytest.mark.parametrize("question", [
    "Which products sold the most last month?", "What might my sales look like next month?", "Which customers are likely to stop buying?",
    "What should I focus on to improve my business?", "How many different products did I sell in January 2025?", "What are the KPI metrics on my dashboard?",
    "Why did my sales fall?", "What is improving and what is getting worse?", "How do you validate an upload?",
])
def test_everything_else_is_left_to_the_normal_assistant(question):
    assert chat.detect(question) is None, question


def test_the_scope_words_are_understood():
    assert chat.detect("Show the historical benchmark results").evidence == {"benchmark"}
    assert chat.detect("Show the validation results for my business").evidence == {"business"}
    assert chat.detect("show the 14-day horizon results").horizon == 14
    assert chat.detect("show all evaluation results, page 3").page == 3
    assert chat.detect("show mae and rmse").keys == ["mae", "rmse"]
    assert chat.detect("Run a forecast validation for my business").action == "run_forecast"
    assert chat.detect("Run the customer score check").action == "run_customer"
    assert chat.detect("How do you validate the model?").action is None          # a question about validation is not an instruction to run one


# ------------------------------------------------------------------ the whole inventory
def _expected_pairs(db, bid):
    """Every (result, metric) pair the evaluation service holds for this business and these models: the ground truth for 'all results'."""
    ov = console.overview(db)
    pairs = set()
    for m in ov["sections"]["training"]["forecasting"]:
        for c in m["baseline"]["test"] + m["test"] + m["validation"] + [m["interval_coverage"]]:
            pairs.add((f"{m['model_name']} {m['version']}", c["key"], c["context"].get("block")))
    for m in ov["sections"]["training"]["classification"]:
        cards = m["test"] + m["validation"] + ([m["class_balance"]["train_positive_rate"], m["class_balance"]["test_positive_rate"]] if m["class_balance"] else [])
        for c in cards:
            pairs.add((f"{m['model_name']} {m['version']}", c["key"], c["context"].get("block")))
    return pairs


def _collect_all_pages(client, bid, first_question, headers):
    pages, texts, results = [], [], []
    body = ask(client, bid, first_question, headers)
    while True:
        pages.append(body)
        texts.append(body["answer"])
        for sec in ev(body)["sections"]:
            results += [(sec["evidence"], r) for r in sec["results"]]
        nxt = ev(body)["pagination"]["next_prompt"]
        if not nxt:
            return pages, texts, results
        body = ask(client, bid, nxt, headers)


def test_all_results_returns_every_recorded_metric_for_every_result_with_none_dropped(validated):
    client, db, bid = validated
    pages, texts, results = _collect_all_pages(client, bid, "Show me all evaluation results.", _research())
    titles = [r["title"] for _, r in results]
    assert len(titles) == len(set(titles)), "a result appeared on two pages"
    got = {(r["title"], c["key"], c["context"].get("block")) for e, r in results if e == "training" for g in r["groups"] for c in g["cards"]}
    assert got == _expected_pairs(db, bid)
    # benchmark rows: every card of every stored row is present
    stored = {(f"{run['title']} - {s['name']}: {row['method']}" + (" (baseline)" if row["kind"] == "baseline" else ""), c["key"])
              for run in console.overview(db)["sections"]["benchmark"]["runs"] if run["kind"] == "forecast" for s in run["sections"] for row in s["rows"] for c in row["cards"]}
    shown = {(r["title"], c["key"]) for e, r in results if e == "benchmark" for g in r["groups"] for c in g["cards"]}
    assert stored <= shown
    # the business's own backtest is in the same answer, in its own section, with all three horizons accounted for
    biz = [r for e, r in results if e == "business"]
    assert [r["horizon"] for r in biz] == [7, 14, 28]                       # in horizon order, not alphabetical
    # totals in the pagination block match what was delivered
    pg = ev(pages[0])["pagination"]
    assert pg["metric_values_total"] == sum(len(g["cards"]) for _, r in results for g in r["groups"])
    assert pg["results_total"] == len(results)


def test_every_recorded_value_is_in_the_text_exactly_as_the_service_formats_it(validated):
    client, db, bid = validated
    pages, texts, results = _collect_all_pages(client, bid, "Show me all evaluation results.", _research())
    full = "\n".join(texts)
    for _, r in results:
        for g in r["groups"]:
            for c in g["cards"]:
                assert c["display"] in full, (r["title"], c["key"], c["display"])
    for bad in ("NaN", "nan ", "Infinity", "None%", "undefined units", "undefined%"):
        assert bad not in full, bad


def test_a_large_result_set_is_paginated_without_dropping_or_repeating_anything(world):
    client, db, bid = world
    pages, texts, results = _collect_all_pages(client, bid, "Show all evaluation results", _research())
    assert len(pages) > 1
    p0 = ev(pages[0])["pagination"]
    assert p0["page"] == 1 and p0["pages"] == len(pages) and p0["next_prompt"] and len(p0["page_prompts"]) == len(pages)
    assert all(ev(b)["pagination"]["metric_values_total"] == p0["metric_values_total"] for b in pages)       # every page knows the grand total
    assert sum(ev(b)["pagination"]["results_on_page"] for b in pages) == p0["results_total"]
    assert "Page 1 of" in pages[0]["answer"] and "Nothing is dropped" in pages[0]["answer"]
    for b in pages[:-1]:
        assert sum(len(g["cards"]) for sec in ev(b)["sections"] for r in sec["results"] for g in r["groups"]) <= chat.PAGE_METRIC_BUDGET + 20
    assert "Limitations and interpretation" in pages[-1]["answer"] and "Limitations and interpretation" not in pages[0]["answer"]
    last = ask(client, bid, f"Show all evaluation results, page {len(pages) + 1}", _research())
    assert last["sufficient_evidence"] is False and f"only {len(pages)} page" in last["answer"]


# ------------------------------------------------------------------ specific questions
def test_a_specific_metric_question_returns_only_that_metric_with_the_recorded_value(world):
    client, db, bid = world
    body = ask(client, bid, "What is the WAPE?", _research())
    cards = [c for sec in ev(body)["sections"] for r in sec["results"] for g in r["groups"] for c in g["cards"]]
    assert cards and {c["key"] for c in cards} == {"wape"}
    xgb = next(r for sec in ev(body)["sections"] for r in sec["results"] if r["title"].startswith("sales_forecast_xgboost"))
    wape = xgb["groups"][0]["cards"][0]
    assert wape["value"] == pytest.approx(25.0) and wape["display"] == "25.0%" and wape["direction_text"] == "Lower is better"
    assert "Weighted absolute percentage error (WAPE): 25.0%" in body["answer"]
    assert body["answer"].splitlines()[0].startswith("Here are the recorded values for WAPE")


def test_a_metric_that_no_result_reports_is_said_so_with_where_it_applies(world):
    client, db, bid = world
    body = ask(client, bid, "Show the forecasting RMSSE for the registered models", _research())
    assert "RMSSE" in body["answer"]
    body = ask(client, bid, "Show the ROC-AUC for the forecasting models", _research())
    assert "ROC-AUC) is not reported by forecasting results. It applies to classification and customer-scoring results" in body["answer"]
    only_cls = {c["key"] for sec in ev(body)["sections"] for r in sec["results"] for g in r["groups"] for c in g["cards"]}
    assert only_cls == {"roc_auc"}


def test_model_horizon_and_run_selection(validated):
    client, db, bid = validated
    body = ask(client, bid, "Show the 14-day horizon results for my business", _research())
    horizons = {r["horizon"] for sec in ev(body)["sections"] for r in sec["results"]}
    assert horizons == {14}
    miss = ask(client, bid, "Show the 90-day horizon results for my business", _research())
    assert "No 90-day horizon was evaluated for your business. Evaluated horizons: 7, 14, 28 days." in miss["answer"] and miss["sufficient_evidence"] is False
    named = ask(client, bid, "Show the evaluation results for the xgboost registered model", _research())
    titles = [r["title"] for sec in ev(named)["sections"] for r in sec["results"] if sec["evidence"] == "training"]
    assert titles == ["sales_forecast_xgboost v1"]


def test_units_directions_and_definitions_travel_with_every_value(validated):
    client, db, bid = validated
    _, _, results = _collect_all_pages(client, bid, "Show me all evaluation results.", _research())
    seen_units = set()
    for _, r in results:
        for g in r["groups"]:
            for c in g["cards"]:
                assert c["explanation"] and c["direction_text"] and c["name"] and c["abbr"] and c["kind"], c["key"]
                if c["status"] == "available":
                    assert c["display"] and c["value"] is not None
                else:
                    assert c["value"] is None and c["reason"] and c["display"] in ("Not available", "Not evaluated", "Not reliable", "Not applicable", "Insufficient data", "Failed")
                seen_units.add(c["unit"])
    assert {"units/day", "percent"} <= seen_units
    pct = next(c for _, r in results for g in r["groups"] for c in g["cards"] if c["key"] == "wape" and c["status"] == "available")
    assert pct["display"].endswith("%")
    n = next(c for _, r in results for g in r["groups"] for c in g["cards"] if c["key"] == "n_eval" and c["status"] == "available")
    assert re.fullmatch(r"[\d,]+", n["display"])                                         # counts are counts, not percentages or floats


# ------------------------------------------------------------------ missing, historical, unreliable, stale
def test_an_older_run_says_what_it_did_not_record_and_nothing_is_backfilled(world):
    client, db, bid = world
    body = ask(client, bid, "Show the evaluation results for the linear registered model", _research())
    r = next(r for sec in ev(body)["sections"] for r in sec["results"])
    cards = {c["key"]: c for g in r["groups"] for c in g["cards"]}
    assert cards["bias"]["kind"] == "not_recorded" and cards["bias"]["value"] is None and "Retrain" in cards["bias"]["reason"]
    assert cards["mape"]["kind"] == "unreliable" and cards["mape"]["value"] is None
    assert "Not recorded for this run" in body["answer"] and "Withheld as not reliable" in body["answer"]
    assert "870000000" not in body["answer"] and "8.7e" not in body["answer"]


def test_not_applicable_not_evaluated_and_insufficient_are_told_apart(validated):
    client, db, bid = validated
    body = ask(client, bid, "Which metrics are unavailable and why?", _research())
    cov = ev(body)["coverage"]
    kinds = {i["kind"] for i in cov["unavailable"]}
    assert {"not_recorded", "not_applicable", "unreliable"} <= kinds
    assert "Not applicable" in cov["counts_by_state"] or any(i["state"] == "Not applicable" for i in cov["unavailable"])
    for it in cov["unavailable"]:
        assert it["reason"] and it["state"] in chat.STATE_LABEL.values()
    assert "What is not available, and why" in body["answer"]
    inapplicable = [i for i in cov["unavailable"] if i["kind"] == "not_applicable"]
    assert any("point forecasts" in i["reason"] for i in inapplicable)


def test_non_finite_stored_values_never_reach_the_answer(world):
    client, db, bid = world
    _model(db, "broken", "forecasting_xgboost", {"mae": float("nan"), "rmse": float("inf"), "wape": float("-inf"), "n_eval": 5}, version="v9")
    body = ask(client, bid, "Show the evaluation results for the broken registered model", _research())
    json.dumps(body, allow_nan=False)
    assert not re.search(r"\bnan\b|infinity", body["answer"].lower())


def test_a_validation_that_is_a_week_old_is_flagged_as_possibly_out_of_date(validated, monkeypatch):
    client, db, bid = validated
    monkeypatch.setattr(chat, "_age_days", lambda iso: 10)
    body = ask(client, bid, "Show the validation results for my business")
    assert "run 10 days ago" in body["answer"] and "may be out of date" in body["answer"]


# ------------------------------------------------------------------ baseline comparison
def test_the_baseline_comparison_uses_recorded_pairs_on_the_same_rows_and_says_so(validated):
    client, db, bid = validated
    body = ask(client, bid, "Compare the model with its baseline.", _research())
    assert "same rows and period for both" in body["answer"]
    xgb = next(r for sec in ev(body)["sections"] for r in sec["results"] if r["title"].startswith("sales_forecast_xgboost"))
    cards = {c["key"]: c for g in xgb["groups"] if not g["title"].startswith("Validation block") for c in g["cards"]}
    assert cards["baseline_mae"]["value"] == 5.0 and cards["mae"]["value"] == 4.0 and cards["mae_vs_baseline"]["value"] == pytest.approx(20.0)
    assert xgb["extras"]["verdict"] == "better_than_baseline"
    bench_rows = [r for sec in ev(body)["sections"] if sec["evidence"] == "benchmark" for r in sec["results"]]
    assert bench_rows
    for r in bench_rows:        # a benchmark row is compared with the best baseline of ITS OWN section, and only the baseline-related metrics are shown
        assert {c["key"] for g in r["groups"] for c in g["cards"]} <= {"mae", "wape", "rmsse", "mae_vs_baseline", "brier", "brier_baseline", "brier_vs_baseline"}
    assert any(c["key"] == "mae_vs_baseline" and c["status"] == "available" and c["value"] == pytest.approx((1.45 - 1.18) / 1.45 * 100)
               for r in bench_rows for g in r["groups"] for c in g["cards"])
    biz = [r for sec in ev(body)["sections"] if sec["evidence"] == "business" for r in sec["results"]]
    assert biz and all({c["reference"] for c in r["extras"]["comparisons"]} == {"naive_last", "trailing_mean_28", "seasonal_naive_7"} for r in biz if not r["state"])


def test_the_naive_model_is_not_compared_with_itself(world):
    client, db, bid = world
    _model(db, "sales_forecast_naive", "forecasting_naive", {**FORECAST, "mae": 5.0})
    body = ask(client, bid, "Compare the models with their baselines", _research())
    naive = next(r for sec in ev(body)["sections"] for r in sec["results"] if r["title"].startswith("sales_forecast_naive"))
    c = next(c for g in naive["groups"] for c in g["cards"] if c["key"] == "mae_vs_baseline")
    assert c["kind"] == "not_applicable" and "baseline itself" in c["reason"]


# ------------------------------------------------------------------ classification
def test_precision_recall_f1_and_accuracy_share_one_threshold_and_the_confusion_matrix(world):
    client, db, bid = world
    body = ask(client, bid, "Show the classification metrics for the registered models", _research())
    m = next(r for sec in ev(body)["sections"] for r in sec["results"] if r["title"].startswith("churn_logistic_regression"))
    cm = m["extras"]["confusion_matrix"]
    cards = {c["key"]: c for g in m["groups"] for c in g["cards"]}
    tp, fp, fn, tn = cm["tp"], cm["fp"], cm["fn"], cm["tn"]
    assert cards["precision"]["value"] == pytest.approx(tp / (tp + fp)) and cards["recall"]["value"] == pytest.approx(tp / (tp + fn))
    assert cards["f1"]["value"] == pytest.approx(2 * tp / (2 * tp + fp + fn)) and cards["accuracy"]["value"] == pytest.approx((tp + tn) / (tp + fp + fn + tn))
    assert {cards[k]["context"]["threshold"] for k in ("precision", "recall", "f1", "accuracy")} == {cm["threshold"]}
    assert "Confusion matrix" in body["answer"] and "positive class churned = 1" in body["answer"] and "true positive 30" in body["answer"]
    assert "not a calibrated probability" in body["answer"]


def test_customer_scores_are_never_called_probabilities_and_calibration_is_stated(world):
    client, db, bid = world
    body = ask(client, bid, "How reliable are the customer scores?", _research())
    assert body["answer"].startswith("The customer scores are a ranking, not a calibrated probability")
    assert not re.search(r"probability of (leaving|churn)(?! of)", body["answer"].split("Evaluation summary")[0].replace("not a calibrated probability of leaving", ""))
    assert ev(body)["query"]["mode"] == "reliability"


def test_accuracy_never_becomes_an_invented_percentage(world):
    client, db, bid = world
    body = ask(client, bid, "How accurate is this model?", _research())
    assert body["answer"].startswith("There is no single 'accuracy percentage'")
    assert "will not turn an error score into one" in body["answer"]
    keys = {c["key"] for sec in ev(body)["sections"] for r in sec["results"] for g in r["groups"] for c in g["cards"]}
    assert {"mae", "wape"} <= keys and "rmse" not in keys                    # the metrics that answer the question for forecasts, not the whole inventory


def test_asking_for_live_accuracy_says_it_was_not_measured_and_keeps_evidence_apart(validated):
    client, db, bid = validated
    body = ask(client, bid, "What is the actual production accuracy of my forecast?")
    assert "not been measured" in body["answer"]
    assert {sec["evidence"] for sec in ev(body)["sections"]} == {"business"}


# ------------------------------------------------------------------ definitions
def test_what_metrics_are_used_lists_every_registered_metric_with_unit_direction_and_meaning(world):
    client, db, bid = world
    body = ask(client, bid, "What metrics are used to evaluate the models?")
    defs = ev(body)["definitions"]
    from app.services.metric_registry import REGISTRY
    assert {d["key"] for d in defs} == set(REGISTRY)
    for d in defs:
        assert d["definition"] and d["direction_text"] and d["unit"] and d["applies_to"]
        assert f"({d['abbr']}):" in body["answer"]
    mae = next(d for d in defs if d["key"] == "mae")
    assert mae["direction_text"] == "Lower is better" and mae["unit"] == "target_units" and "ignoring direction" in mae["definition"]
    assert "Forecasting and regression" in body["answer"] and "Classification and customer scoring" in body["answer"]
    assert "Closer to zero is better" in body["answer"] and "Positive = over-forecast" in body["answer"]


# ------------------------------------------------------------------ business validation
def test_business_results_are_separate_from_benchmarks_and_never_substituted(world):
    client, db, bid = world
    body = ask(client, bid, "Show the validation results for my business", _research())
    assert body["sufficient_evidence"] is False
    assert "Not evaluated" in body["answer"] and "I will not substitute a public benchmark" in body["answer"]
    assert ev(body)["sections"] == []                                      # no benchmark or model row stands in for the business


def test_running_a_validation_in_chat_stores_it_and_a_later_question_shows_the_same_numbers(validated):
    client, db, bid = validated
    first = ask(client, bid, "Show the validation results for my business")
    again = ask(client, bid, "Show the validation results for my business")
    pick = lambda b: [(r["title"], c["key"], c["value"]) for s in ev(b)["sections"] for r in s["results"] for g in r["groups"] for c in g["cards"]]  # noqa: E731
    assert pick(first) == pick(again) and pick(first)
    assert all(s["evidence"] == "business" for s in ev(first)["sections"])
    assert "Evaluated on:" in first["answer"] and "Validation run:" in first["answer"] and "Code revision:" in first["answer"]


def test_a_validation_that_cannot_run_is_reported_as_insufficient_data_not_a_failure_or_a_guess(world):
    client, db, bid = world
    body = ask(client, bid, "Run a forecast validation for my business")
    assert body["sufficient_evidence"] is False and body["answer"].startswith("Insufficient data")


def test_validation_history_lists_runs_and_a_run_can_be_opened_by_id(validated):
    client, db, bid = validated
    body = ask(client, bid, "Show the validation history for my business")
    runs = ev(body)["history"]
    assert runs and all(r["id"] in body["answer"] for r in runs)
    one = ask(client, bid, f"Show the validation results for run {runs[0]['id']}")
    assert ev(one)["sections"] and ev(one)["query"]["run_id"] == runs[0]["id"]
    ghost = ask(client, bid, "Show the validation results for run 00000000-0000-0000-0000-000000000000")
    assert ghost["sufficient_evidence"] is False and "could not find" in ghost["answer"]


# ------------------------------------------------------------------ nothing evaluated
def test_with_nothing_evaluated_the_answer_says_so(client, db_session, monkeypatch, tmp_path):
    monkeypatch.setattr(bench, "RUNS_DIR", tmp_path / "none")
    bid = _create_business(client)
    body = ask(client, bid, "Show me all evaluation results.", _research())
    assert body["sufficient_evidence"] is False and "Not evaluated" in body["answer"]
    assert body["intent"] == "evaluation_results" and body["path"] == "evaluation_service"


# ------------------------------------------------------------------ who may see what
def test_without_research_credentials_chat_shows_no_model_or_benchmark_result(world):
    client, db, bid = world
    body = ask(client, bid, "Show me all evaluation results.")                       # no research token
    text = json.dumps(body)
    for secret in ("sales_forecast_xgboost", "churn_logistic_regression", "xgboost:depth6", "random_forest", "platform_v1"):
        assert secret not in text, secret
    assert ev(body)["access"] == {"research": False, "scope": "business only"}
    assert "administrators in the Research Console" in body["answer"] or "not evaluated" in body["answer"].lower()
    asked = ask(client, bid, "Show the historical benchmark results")
    assert "xgboost:depth6" not in json.dumps(asked) and "administrators in the Research Console" in asked["answer"]


def test_a_wrong_research_token_is_the_same_as_none(world):
    client, db, bid = world
    body = ask(client, bid, "Show me all evaluation results.", {"X-Research-Token": "not-the-token"})
    assert "sales_forecast_xgboost" not in json.dumps(body) and ev(body)["access"]["research"] is False


def test_an_administrator_session_sees_research_results_and_a_business_owner_does_not(client, db_session, auth_on, monkeypatch, tmp_path):  # noqa: F811
    _bench_run(tmp_path, "f1_20261015T010000Z_aaaa", F1)
    monkeypatch.setattr(bench, "RUNS_DIR", tmp_path)
    _model(db_session, "sales_forecast_xgboost", "forecasting_xgboost", FORECAST)
    admin = {"Authorization": f"Bearer {admin_token(client, db_session)}"}
    admin_bid = client.post(P, json={"name": "Admin Shop", "industry": "retail", "business_type": "D2C", "business_size": "small"}, headers=admin).json()["id"]
    sme_bid, sme = _owner(client, "owner@example.com", "Owner Shop")
    a = ask(client, admin_bid, "Show the evaluation results for the registered models", admin)
    assert ev(a)["access"]["research"] is True and "sales_forecast_xgboost" in a["answer"]
    s = ask(client, sme_bid, "Show the evaluation results for the registered models", sme)
    assert ev(s)["access"]["research"] is False and "sales_forecast_xgboost" not in json.dumps(s)


def test_chat_still_requires_authentication_and_ownership(client, db_session, auth_on):  # noqa: F811
    a_bid, a = _owner(client, "a@example.com", "Alpha")
    b_bid, b = _owner(client, "b@example.com", "Beta")
    url = f"/api/v1/businesses/{a_bid}/chat"
    assert client.post(url, json={"message": "Show all evaluation results"}).status_code == 401
    assert client.post(url, json={"message": "Show all evaluation results"}, headers=b).status_code == 404


def test_one_business_never_sees_another_businesss_validation(client, db_session, auth_on, monkeypatch, tmp_path):  # noqa: F811
    monkeypatch.setattr(bench, "RUNS_DIR", tmp_path / "none")
    a_bid, a = _owner(client, "a@example.com", "Alpha")
    b_bid, b = _owner(client, "b@example.com", "Beta")
    _upload_sales(client, a_bid, a, _weekly_rows(150, seed=3))
    ran = ask(client, a_bid, "Run a forecast validation for my business", a)
    run_id = ev(ran)["sections"][0]["results"][0]["facts"][0]["value"]
    assert ask(client, a_bid, "Show the validation results for my business", a)["sufficient_evidence"] is True
    theirs = ask(client, b_bid, "Show the validation results for my business", b)
    assert theirs["sufficient_evidence"] is False and run_id not in json.dumps(theirs) and ev(theirs)["sections"] == []
    stolen = ask(client, b_bid, f"Show the validation results for run {run_id}", b)
    assert stolen["sufficient_evidence"] is False and "could not find" in stolen["answer"] and run_id.split("-")[0] not in stolen["answer"].replace(run_id, "")
    hist = ask(client, b_bid, "Show the validation history for my business", b)
    assert run_id not in json.dumps(hist)


# ------------------------------------------------------------------ no model can invent or change a number
def test_no_language_model_is_consulted_for_evaluation_questions(world, monkeypatch):
    client, db, bid = world
    fake = FakeLLM({})
    monkeypatch.setattr(analytics_chat_service, "get_llm", lambda: fake)
    for q in ("Show me all evaluation results.", "How accurate is this model?", "What is the WAPE?", "Which metrics are unavailable and why?"):
        body = ask(client, bid, q, _research())
        assert body["path"] == "evaluation_service" and body["intent"] == "evaluation_results"
    assert fake.calls == []


def test_every_number_in_the_answer_traces_to_a_service_value(world):
    """No number may appear in the answer that the evaluation service did not supply: metric values and units, facts, registry definitions and
    reasons, or a structural count (results, pages, metric totals). A model that wrote its own number would fail this."""
    client, db, bid = world
    body = ask(client, bid, "Show the forecasting evaluation results for the registered models", _research())
    e = ev(body)
    haystack = []
    for sec in e["sections"]:
        haystack.append(sec["title"])
        for r in sec["results"]:
            haystack.append(r["title"])
            haystack += [str(f["value"]) for f in r["facts"]]
            haystack += [str(n) for n in r["extras"].get("notes", [])]
            for g in r["groups"]:
                haystack.append(g["title"])
                for c in g["cards"]:
                    haystack += [str(c[k]) for k in ("display", "name", "abbr", "explanation", "caveat", "reason", "direction_text", "sign_note") if c.get(k)]
                    haystack += [str(v) for v in c["context"].values()]
    haystack += e["sources"] if "sources" in e else body["sources"]
    haystack += console.LIMITATIONS + [chat.NO_ACCURACY_PERCENT, e["coverage"]["counts_by_state"].__str__()]
    pg = e["pagination"]
    structural = {str(pg["page"]), str(pg["pages"]), str(pg["results_total"]), str(pg["metric_values_total"]), str(pg["results_on_page"]), str(chat.STALE_AFTER_DAYS),
                  str(e["coverage"]["available_values"]), *(str(v) for v in e["inventory"]["by_evidence"].values()), *(str(v) for v in e["coverage"]["counts_by_state"].values())}
    blob = " | ".join(haystack)
    strays = []
    for m in re.finditer(r"(?<![\w.])-?\d+(?:,\d{3})*(?:\.\d+)?%?", body["answer"]):
        token = m.group(0)
        if token in blob or token.rstrip("%") in structural:
            continue
        strays.append(token)
    assert not strays, strays


def test_ordinary_words_in_a_method_name_do_not_turn_a_broad_question_into_a_model_choice(world):
    """Found with the real stored benchmark files: 'ensemble:mean_all' contains the word 'all'."""
    client, db, bid = world
    res = json.loads(json.dumps(F1))
    res["test"]["ensemble:mean_all"] = _row(1.17)
    res["test"]["ensemble:nnls_weighted"] = _row(1.16)
    for d in list(bench.RUNS_DIR.iterdir()):
        if d.name.startswith("f1_"):
            (d / "results.json").write_text(json.dumps(res), encoding="utf-8")
    _, _, results = _collect_all_pages(client, bid, "Show me all evaluation results.", _research())
    titles = [r["title"] for _, r in results]
    assert any("xgboost:depth6" in t for t in titles) and any("mean_all" in t for t in titles) and any(t.startswith("sales_forecast_xgboost") for t in titles)
    # a distinctive name still selects, a word like 'all' or 'mean' does not
    named = ask(client, bid, "Show the evaluation results for xgboost:depth6", _research())
    assert [r["title"] for s in ev(named)["sections"] if s["evidence"] == "benchmark" for r in s["results"]] == [t for t in titles if "xgboost:depth6" in t]


def test_the_chat_research_rule_is_the_research_console_rule(client, db_session, auth_on):  # noqa: F811
    """``research_access_granted`` (chat) and ``require_research_access`` (the console's gate) must never disagree."""
    from app.api.deps import require_research_access, research_access_granted
    from app.core.errors import BusinessAccessDeniedError
    from app.models.user import User
    settings = get_settings()
    users = [None, User(email="a@x.io", password_hash="x", role="admin", is_active=True), User(email="b@x.io", password_hash="x", role="admin", is_active=False),
             User(email="c@x.io", password_hash="x", role="sme", is_active=True)]
    for user in users:
        for token in (None, "", "wrong", settings.research_console_token):
            try:
                require_research_access(token, user)
                gate = True
            except BusinessAccessDeniedError:
                gate = False
            assert research_access_granted(user, token) is gate, (getattr(user, "role", None), getattr(user, "is_active", None), token)


def test_a_business_owner_asking_about_accuracy_is_told_what_accuracy_means_and_where_research_results_are(world):
    client, db, bid = world
    body = ask(client, bid, "How accurate is this model?")                           # no research credentials
    assert body["answer"].startswith("Not evaluated") is False and "no single 'accuracy percentage'" in body["answer"]
    assert "Not evaluated: no validation has been run" in body["answer"]
    assert body["answer"].count("administrators in the Research Console") == 1       # said once, not repeated
    assert "sales_forecast_xgboost" not in json.dumps(body)


def test_the_restriction_notice_is_not_repeated(world):
    client, db, bid = world
    body = ask(client, bid, "Show the historical benchmark results")
    assert body["answer"].count("administrators in the Research Console") == 1


def test_timestamps_are_shown_in_one_readable_form(validated):
    client, db, bid = validated
    body = ask(client, bid, "Show the validation results for my business")
    assert re.search(r"Run date: \d{4}-\d{2}-\d{2} \d{2}:\d{2} UTC", body["answer"])
    assert not re.search(r"\d[T]\d", re.search(r"Run date: ([^;]+)", body["answer"]).group(1))      # no raw ISO "…T18:29:57.3+00:00"


def test_no_research_results_in_chat_when_the_research_console_is_switched_off(world, monkeypatch):
    client, db, bid = world
    monkeypatch.setattr(get_settings(), "research_console_enabled", False)
    body = ask(client, bid, "Show me all evaluation results.", _research())          # a valid token, but the console is off
    assert ev(body)["access"]["research"] is False and "sales_forecast_xgboost" not in json.dumps(body)


def test_the_unavailable_list_is_one_complete_answer_not_repeated_pages(validated):
    client, db, bid = validated
    body = ask(client, bid, "Which metrics are unavailable and why?", _research())
    e = ev(body)
    assert e["pagination"]["pages"] == 1 and e["pagination"]["next_prompt"] is None and e["sections"] == []
    listed = e["coverage"]["unavailable"]
    assert listed and all(it["reason"] for it in listed)
    assert body["answer"].count("\n- ") >= len(listed)                           # every item is in the text, once
    assert "page 1 of" not in body["answer"].lower()
