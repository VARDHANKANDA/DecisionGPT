"""Research Console - Evaluation (admin only, read-only).

Turns metrics that were ALREADY recorded - by training runs (``models.metrics_json``), by the stored benchmark files, and by a business's own
validation reports - into the cards defined in ``metric_registry``. Nothing here fits a model or computes a new model metric; the only
arithmetic is derived from recorded counts (accuracy from a confusion matrix) or from two recorded values (MAE vs baseline), and each such
card says so.

Four kinds of evidence are kept apart and never merged into one table:
  training    the held-out part of the dataset a registered model was trained on (a research dataset, not a business)
  benchmark   stored public-data benchmark runs (experiments/ml_benchmark_v1), shown as stored
  business    a backtest on ONE business's own history (a stored validation report)
  production  not evaluated here: live forecast-vs-outcome accuracy is not aggregated into the console
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.ml_model import MLModel
from app.services import analysis_run_service, ml_benchmark_service
from app.services import model_reevaluation_service as reeval
from app.services.metric_registry import (
    NOT_EVALUATED,
    card,
    improvement_vs_baseline,
    mape_card,
    metric_definitions,
)

TARGET_UNIT = "units/day"
_TRAIN_FORECAST_TARGET = "units_sold per series per day"
_OLD_RUN = "This model was trained before this value was recorded. Retrain it to record it."

LIMITATIONS = [
    "Registered platform models are scored on the held-out part of their own research dataset. That measures how well they learned that dataset, "
    "not how they would do for a particular business.",
    "Benchmark results describe the public datasets they were run on (retail data), not Indian SMEs.",
    "A customer-inactivity or churn score here ranks customers. It is not a probability that a customer will leave, and its label may be a proxy "
    "or synthetic.",
    "Business validation uses one business's own history with a handful of overlapping test periods; small samples make every figure unstable.",
    "A good evaluation figure is not evidence of business impact, and nothing on this page changes a model or approves it for use.",
]


def _isnum(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _ctx(**kw: Any) -> dict[str, Any]:
    return {k: v for k, v in kw.items() if v is not None}


def _run_meta(m: MLModel) -> dict[str, Any]:
    life = m.lifecycle_json or {}
    return life.get("run_metadata") or {}


def _setup(m: MLModel, split_scheme: str) -> dict[str, Any]:
    meta = _run_meta(m)
    return {
        "dataset_version": m.dataset_version, "feature_version": m.feature_version, "features": list(m.features_json or meta.get("feature_columns") or []),
        "dataset_sha256": meta.get("dataset_sha256"), "random_seed": meta.get("random_seed"), "splits": meta.get("splits"),
        "split_scheme": (meta.get("splits") or {}).get("scheme") or split_scheme, "code_revision": meta.get("git_revision"),
        "training_run_id": m.training_run_id, "source": m.source or "cli", "trained_at": m.created_at.isoformat() if m.created_at else None,
        "selection_rule": meta.get("selection_rule"),
    }


def _identity(m: MLModel) -> dict[str, Any]:
    return {"id": m.id, "model_name": m.model_name, "model_type": m.model_type, "version": m.version, "status": m.status,
            "validation_status": m.validation_status}


# ------------------------------------------------------------------------------------------------ registered models: forecasting
def evaluation_meta(m: MLModel) -> dict[str, Any]:
    """Where a forecasting model's test figures come from and whether they exist: ``evaluated`` (recorded at training, or a verified re-evaluation of the stored
    artifact), ``pending`` (WAPE was never recorded and the re-evaluation has not been run), ``unavailable`` (it was run but the artifact or dataset is missing) or
    ``failed`` (verification or scoring failed, so no figure is shown). Training and validation figures never count as a test evaluation."""
    mj = m.metrics_json or {}
    rev_any = (m.lifecycle_json or {}).get("reevaluation")
    rev = reeval.trusted_reevaluation(m)
    meta: dict[str, Any] = {"status": "pending", "kind": None, "reason": None, "evaluated_at": None, "test_window": None, "n_eval": mj.get("n_eval") if _isnum(mj.get("n_eval")) else None,
                            "horizon": reeval.HORIZON, "baseline_name": reeval.BASELINE_NAME, "method": None, "dataset": m.dataset_version, "verification": None,
                            "can_run": False, "is_baseline_model": (m.model_type or "").endswith("naive")}
    if _isnum(mj.get("wape")):
        meta.update(status="evaluated", kind="recorded_at_training", method="Recorded by the training run on the held-out test block of its dataset (chronological split by date).")
        splits = _run_meta(m).get("splits")
        test_split = splits.get("test") if isinstance(splits, dict) else None
        if isinstance(test_split, dict) and test_split.get("start") and test_split.get("end"):
            meta["test_window"] = [test_split["start"], test_split["end"]]
    elif rev:
        sp = rev.get("split") or {}
        meta.update(status="evaluated", kind="re_evaluated", method=rev.get("method"), evaluated_at=rev.get("evaluated_at"), verification=rev.get("verification"),
                    test_window=[sp.get("test_start"), sp.get("test_end")] if sp.get("test_start") else None, n_eval=(rev.get("metrics") or {}).get("n_eval"))
    elif isinstance(rev_any, dict):
        meta.update(status="failed" if rev_any.get("status") == reeval.STATUS_FAILED else "unavailable", kind="re_evaluation_attempted", reason=rev_any.get("reason"),
                    evaluated_at=rev_any.get("evaluated_at"), method=rev_any.get("method"), verification=rev_any.get("verification"), can_run=True)
    else:
        meta.update(reason="WAPE and the evaluated-row count were not recorded when this model was trained (older run). Run the evaluation to score the stored model "
                           "on its held-out test block; this trains nothing and calls no external service.", can_run=True)
    return meta


def _forecast_model(m: MLModel) -> dict[str, Any]:
    mj_recorded = dict(m.metrics_json or {})
    mj = dict(mj_recorded)
    rev = reeval.trusted_reevaluation(m)
    rev_base = (rev or {}).get("baseline") or {}
    if rev:                                    # a verified re-evaluation fills ONLY what training did not record; recorded values always win
        rm = rev.get("metrics") or {}
        for k in ("wape", "bias", "n_eval", "n_zero_actual"):
            if not _isnum(mj.get(k)) and _isnum(rm.get(k)):
                mj[k] = rm[k]
        if not _isnum(mj.get("baseline_mae")) and _isnum(rev_base.get("mae")):
            mj["baseline_mae"] = rev_base["mae"]
    meta = evaluation_meta(m)
    n_eval, n_zero = mj.get("n_eval"), mj.get("n_zero_actual")
    known = _isnum(n_eval)
    old = None if known else _OLD_RUN
    window = meta["test_window"]
    c_test = _ctx(block="test", target=_TRAIN_FORECAST_TARGET, n=int(n_eval) if known else None, dataset=m.dataset_version, test_window=window,
                  source="re-evaluated from the stored artifact" if meta["kind"] == "re_evaluated" else None)
    c_val = _ctx(block="validation", target=_TRAIN_FORECAST_TARGET, dataset=m.dataset_version)
    is_baseline = meta["is_baseline_model"]
    wape_val = mj.get("wape")
    wape_reason = None
    if "mae" in mj and "wape" not in mj:
        wape_reason = ("WAPE is not defined: the actual volume in the test block is zero." if meta["status"] == "evaluated" else
                       "WAPE was not recorded for this run (older run) and the re-evaluation has not produced a verified result.")
    fc_acc = (1.0 - wape_val) if _isnum(wape_val) else None
    test_cards = [
        card("mae", mj.get("mae"), target_unit=TARGET_UNIT, context=c_test),
        card("rmse", mj.get("rmse"), target_unit=TARGET_UNIT, context=c_test),
        card("wape", wape_val, as_percent_of_fraction=True, context=c_test, reason=wape_reason),
        card("forecast_accuracy", fc_acc, as_percent_of_fraction=True, context=c_test, reason=wape_reason),
        card("bias", mj.get("bias"), target_unit=TARGET_UNIT, context=c_test, reason=old),
        mape_card(mj.get("mape"), n_zero_actual=int(n_zero) if _isnum(n_zero) else None, n_eval=int(n_eval) if known else None, context=c_test),
        card("n_eval", n_eval, context=c_test, reason=old),
        card("n_zero_actual", n_zero, context=c_test, reason=old),
    ]
    val_cards = [
        card("mae", mj.get("val_mae"), target_unit=TARGET_UNIT, context=c_val),
        card("rmse", mj.get("val_rmse"), target_unit=TARGET_UNIT, context=c_val),
        card("wape", mj.get("val_wape"), as_percent_of_fraction=True, context=c_val),
    ] if any(k.startswith("val_") for k in mj) else []
    base_t, base_v = mj.get("baseline_mae"), mj.get("val_baseline_mae")
    base_w = rev_base.get("wape") if rev else None
    base_acc = (1.0 - base_w) if _isnum(base_w) else None
    imp_t = None if is_baseline else improvement_vs_baseline(mj.get("mae"), base_t)
    imp_w = None if is_baseline else reeval.relative_improvement_pct(base_w, mj.get("wape"))
    imp_v = None if is_baseline else improvement_vs_baseline(mj.get("val_mae"), base_v)
    why_none = "This model is the baseline itself." if is_baseline else (
        "A baseline MAE was not recorded for this model." if base_t is None else "The baseline's error was zero, so no relative change is defined.")
    if is_baseline:
        why_w = "This model is the baseline itself."
    elif base_w is None:
        why_w = "The baseline's WAPE is recorded only by the re-evaluation, which has not produced a verified result for this model."
    else:
        why_w = "A relative WAPE change needs a positive baseline WAPE and a model WAPE."
    baseline = {
        "baseline": reeval.BASELINE_NAME, "same_rows": "The baseline is scored on exactly the same rows and period as the model.",
        "test": [card("baseline_mae", base_t, target_unit=TARGET_UNIT, context=c_test, reason=None if base_t is not None else "A baseline MAE was not recorded for this model."),
                 card("mae_vs_baseline", imp_t, context=c_test, reason=why_none if imp_t is None else None,
                      kind="not_applicable" if is_baseline else None),
                 card("baseline_wape", base_w, as_percent_of_fraction=True, context=c_test, reason=None if base_w is not None else why_w),
                 card("baseline_forecast_accuracy", base_acc, as_percent_of_fraction=True, context=c_test, reason=None if base_w is not None else why_w),
                 card("wape_vs_baseline", imp_w, context=c_test, reason=why_w if imp_w is None else None, kind="not_applicable" if is_baseline else None)],
        "validation": [card("baseline_mae", base_v, target_unit=TARGET_UNIT, context=c_val),
                       card("mae_vs_baseline", imp_v, context=c_val)] if base_v is not None else [],
        "verdict": None if imp_t is None else ("better_than_baseline" if imp_t > 0 else "not_better_than_baseline"),
        "verdict_wape": None if imp_w is None else ("better_than_baseline" if imp_w > 0 else "not_better_than_baseline"),
    }
    return {
        **_identity(m), "task": "forecasting", "target": _TRAIN_FORECAST_TARGET,
        "setup": _setup(m, "chronological split of the dataset by date"), "evaluation": meta,
        "test": test_cards, "validation": val_cards, "baseline": baseline,
        "interval_coverage": card("coverage", None, status=NOT_EVALUATED, kind="not_applicable",
                                  reason="Registered platform models produce point forecasts only. Interval coverage is checked per business under Business validation."),
        "by_horizon": {"status": NOT_EVALUATED, "reason": "Registered platform models predict one day ahead, so there is no horizon breakdown. "
                                                           "Per-horizon figures exist under Business validation."},
    }


# ------------------------------------------------------------------------------------------------ registered models: classification
def _confusion(mj: dict) -> dict[str, int] | None:
    keys = ("confusion_tp", "confusion_fp", "confusion_fn", "confusion_tn")
    if not all(_isnum(mj.get(k)) for k in keys):
        return None
    return {"tp": int(mj["confusion_tp"]), "fp": int(mj["confusion_fp"]), "fn": int(mj["confusion_fn"]), "tn": int(mj["confusion_tn"])}


def _rate(num: int, den: int) -> float | None:
    return num / den if den > 0 else None


def _classification_model(m: MLModel) -> dict[str, Any]:
    mj = m.metrics_json or {}
    conf = _confusion(mj)
    thr = mj.get("threshold_from_validation")
    c_test = _ctx(block="test", target="churned (1 = customer left)", positive_class="churned = 1", dataset=m.dataset_version)
    out: dict[str, Any] = {**_identity(m), "task": "classification", "target": "churned (1 = customer left)", "positive_class": "churned = 1",
                           "setup": _setup(m, "stratified random 80/20 split of customers; the threshold is chosen on the training part (5-fold)")}
    test_cards = []
    if conf is not None:
        n = sum(conf.values())
        c_thr = {**c_test, "n": n, "threshold": round(float(thr), 4) if _isnum(thr) else None, "threshold_source": "chosen on validation, never on test"}
        test_cards += [
            card("accuracy", _rate(conf["tp"] + conf["tn"], n), context=c_thr,
                 extra_caveat="Computed from the confusion matrix below."),
            card("roc_auc", mj.get("roc_auc"), context=c_test),
            card("pr_auc", mj.get("pr_auc"), context=c_test),
            card("precision", _rate(conf["tp"], conf["tp"] + conf["fp"]), context=c_thr, kind="not_applicable",
                 reason="No customer was flagged, so precision is undefined." if conf["tp"] + conf["fp"] == 0 else None),
            card("recall", _rate(conf["tp"], conf["tp"] + conf["fn"]), context=c_thr, kind="not_applicable",
                 reason="There were no positive customers, so recall is undefined." if conf["tp"] + conf["fn"] == 0 else None),
            card("f1", _rate(2 * conf["tp"], 2 * conf["tp"] + conf["fp"] + conf["fn"]), context=c_thr, kind="not_applicable",
                 reason="Undefined: nothing was flagged and there were no positives." if 2 * conf["tp"] + conf["fp"] + conf["fn"] == 0 else None),
        ]
        out["confusion_matrix"] = {**conf, "n": n, "positive_class": "churned = 1", "threshold": c_thr["threshold"],
                                   "rows_are": "actual", "columns_are": "predicted at the threshold"}
        out["threshold_note"] = "Precision, recall, F1 and accuracy are all computed at one threshold chosen on validation data, so they agree with the confusion matrix."
    else:
        c_default = {**c_test, "threshold": 0.5, "threshold_source": "the model's default cut-off (0.5); this run did not record a validation-chosen threshold"}
        test_cards += [
            card("accuracy", mj.get("accuracy"), context=c_default,
                 reason="Accuracy needs a confusion matrix, which this older run did not record." if mj.get("accuracy") is None else None),
            card("roc_auc", mj.get("roc_auc"), context=c_test),
            card("pr_auc", mj.get("pr_auc"), context=c_test),
            card("precision", mj.get("precision"), context=c_default),
            card("recall", mj.get("recall"), context=c_default),
            card("f1", mj.get("f1"), context=c_default),
        ]
        out["confusion_matrix"] = None
        out["threshold_note"] = "This run did not record a confusion matrix; precision, recall and F1 are at the default cut-off."
    shift = mj.get("prevalence_shift")
    comparable = _isnum(shift) and float(shift) < 0.05
    test_cards += [
        card("brier", mj.get("brier"), context=c_test),
        card("ece", mj.get("ece"), context=c_test,
             extra_caveat=None if comparable or not _isnum(shift) else
             f"The positive rate differs by {float(shift) * 100:.1f} points between training and test, so calibration is not comparable here."),
    ]
    out["test"] = test_cards
    out["validation"] = [card("roc_auc", mj.get("val_roc_auc"), context={"block": "validation (5-fold on the training part)"}),
                         card("pr_auc", mj.get("val_pr_auc"), context={"block": "validation (5-fold on the training part)"})] if "val_roc_auc" in mj else []
    out["class_balance"] = {
        "test_positive_rate": card("prevalence", mj.get("test_prevalence"), context=c_test),
        "train_positive_rate": card("prevalence", mj.get("train_prevalence"), context={"block": "train"}),
        "shift": float(shift) if _isnum(shift) else None,
    } if _isnum(mj.get("test_prevalence")) else None
    out["score_meaning"] = ("A ranking score. It orders customers from least to most likely to leave; it is not a calibrated probability, "
                            "and Brier/ECE are diagnostics of how far it is from one.")
    out["calibrated"] = False
    out["baseline"] = {"status": NOT_EVALUATED, "reason": "No baseline classifier is recorded for registered customer models. The positive rate above is the "
                                                           "reference for PR-AUC and accuracy."}
    return out


def _mini(c: dict[str, Any]) -> dict[str, Any]:
    return {"value": c.get("value"), "display": c.get("display"), "status": c.get("status"), "kind": c.get("kind"), "reason": c.get("reason")}


def forecast_summary_row(entry: dict[str, Any]) -> dict[str, Any]:
    """One flat row per registered forecasting model: identity, evaluation status and provenance, and the held-out TEST figures only (never validation or training)."""
    by = {c["key"]: c for c in entry["test"]}
    bl = {c["key"]: c for c in entry["baseline"]["test"]}
    ev = entry["evaluation"]
    return {
        "model_id": entry["id"], "model_name": entry["model_name"], "version": entry["version"], "model_status": entry["status"], "dataset_version": entry["setup"]["dataset_version"],
        "evaluation_status": ev["status"], "evaluation_kind": ev["kind"], "evaluation_reason": ev["reason"], "evaluated_at": ev["evaluated_at"], "can_run": ev["can_run"],
        "test_window": ev["test_window"], "n_eval": ev["n_eval"], "horizon": ev["horizon"], "baseline_name": ev["baseline_name"], "method": ev["method"],
        "is_baseline_model": ev["is_baseline_model"],
        "wape": _mini(by["wape"]), "forecast_accuracy": _mini(by["forecast_accuracy"]), "mae": _mini(by["mae"]), "rmse": _mini(by["rmse"]), "mape": _mini(by["mape"]),
        "baseline_wape": _mini(bl["baseline_wape"]), "baseline_forecast_accuracy": _mini(bl["baseline_forecast_accuracy"]), "wape_vs_baseline": _mini(bl["wape_vs_baseline"]), "mae_vs_baseline": _mini(bl["mae_vs_baseline"]),
        "verdict_wape": entry["baseline"]["verdict_wape"],
    }


def forecast_summary(models: list[MLModel]) -> list[dict[str, Any]]:
    return [forecast_summary_row(_forecast_model(m)) for m in models if (m.model_type or "").startswith("forecasting_")]


def _models_section(db: Session) -> dict[str, Any]:
    rows = db.query(MLModel).order_by(MLModel.model_name, MLModel.created_at.desc()).all()
    fc = [_forecast_model(m) for m in rows if m.model_type.startswith("forecasting_")]
    cl = [_classification_model(m) for m in rows if m.model_type.startswith("churn_")]
    return {
        "evidence": "training",
        "label": "Registered models on their own research dataset",
        "note": "Scored on the held-out part of the dataset each model was trained on. Not business data.",
        "forecasting": fc, "classification": cl,
        "empty": None if rows else "No models are registered yet. Train one in the Training Center to see its metrics here.",
    }


def _benchmark_unit(section_name: str) -> str:
    """What a benchmark forecast error is measured in. The stored files do not carry a unit field, so it follows from what the section forecasts."""
    return "revenue/day" if "revenue" in section_name.lower() else "units/day"


# ------------------------------------------------------------------------------------------------ benchmark files
def _benchmark_section() -> dict[str, Any]:
    data = ml_benchmark_service.latest_results()
    if not data.get("available"):
        return {"evidence": "benchmark", "available": False, "label": "Public-data benchmarks", "runs": [], "reason": data.get("message")}
    runs = []
    for r in data["runs"]:
        base = {"run_id": r["run_id"], "task": r["task"], "title": r["title"], "kind": r["kind"], "evidence_class": r.get("evidence_class"),
                "created_utc": r.get("created_utc"), "git_revision": r.get("git_revision")}
        if r["kind"] == "forecast":
            secs = []
            for s in r["sections"]:
                best_base = min((x for x in s["rows"] if x["kind"] == "baseline" and _isnum(x.get("mae"))), key=lambda x: x["mae"], default=None)
                rows = []
                unit = _benchmark_unit(s["name"])
                single = s.get("n_series") == 1
                for x in s["rows"]:
                    c = _ctx(block="test", n=x.get("n_points"), test_window=s.get("test_window"), series=s.get("n_series"))
                    imp = improvement_vs_baseline(x.get("mae"), best_base["mae"]) if best_base and x["kind"] != "baseline" else None
                    n_def, n_all = x.get("series_with_defined_wape"), x.get("n_series")
                    c_med = {**c, "series_with_a_defined_wape": f"{n_def} of {n_all}"} if _isnum(n_def) and _isnum(n_all) else c
                    excl = x.get("rmsse_excluded")
                    rows.append({
                        "method": x["method"], "kind": x["kind"], "selected_by_validation": x["selected_by_validation"],
                        "cards": [card("mae", x.get("mae"), target_unit=unit, context=c), card("rmse", x.get("rmse"), target_unit=unit, context=c),
                                  card("wape", x.get("wape"), as_percent_of_fraction=True, context=c),
                                  # the stored benchmark "bias" is sum(error)/sum(actual): a RELATIVE bias, not an error in units
                                  card("relative_bias", x.get("bias"), as_percent_of_fraction=True, context=c),
                                  card("mae_vs_baseline", imp, context=c, reason=("This row is a baseline." if x["kind"] == "baseline" else None) if imp is None else None,
                                       kind="not_applicable" if x["kind"] == "baseline" else None),
                                  card("rmsse", x.get("rmsse_mean"), context=c,
                                       extra_caveat=(f"{int(excl)} series with a constant training history could not be scaled and are not in this average." if _isnum(excl) and excl > 0 else None),
                                       reason="This run did not record a scale-based error for these series."),
                                  card("aggregate_daily_wape", x.get("aggregate_daily_wape"), as_percent_of_fraction=True, context=c,
                                       **({"status": NOT_EVALUATED, "kind": "not_applicable", "reason": "This is a single series, so adding series together changes nothing: see WAPE."} if single else {})),
                                  card("median_series_wape", x.get("median_series_wape"), as_percent_of_fraction=True, context=c_med,
                                       **({"status": NOT_EVALUATED, "kind": "not_applicable", "reason": "This is a single series, so there is no typical series to take the middle of: see WAPE."} if single else {}))],
                    })
                secs.append({"name": s["name"], "n_series": s.get("n_series"), "n_test_points": s.get("n_test_points"), "test_window": s.get("test_window"),
                             "baseline_used_for_comparison": best_base["method"] if best_base else None, "rows": rows,
                             "paired_comparisons": s.get("paired")})
            runs.append({**base, "sections": secs})
        elif r["kind"] == "classification":
            rows = []
            for x in r["rows"]:
                c = _ctx(block="test", n=x.get("n_test"), positive_rate=x.get("test_prevalence"))
                rows.append({"method": x["method"], "selected_by_validation": x["selected_by_validation"],
                             "cards": [card("roc_auc", x.get("roc_auc"), context=c), card("pr_auc", x.get("pr_auc"), context=c),
                                       card("brier", x.get("brier"), context=c),
                                       card("brier_baseline", x.get("brier_prevalence_baseline"), context=c),
                                       card("brier_vs_baseline", improvement_vs_baseline(x.get("brier"), x.get("brier_prevalence_baseline")), context=c,
                                            reason="Needs both this model's Brier score and the constant-forecast Brier score; one was not recorded."),
                                       card("log_loss", x.get("log_loss"), context=c), card("ece", x.get("ece"), context=c)],
                             "brier_if_always_predicting_the_positive_rate": x.get("brier_prevalence_baseline")})
            runs.append({**base, "rows": rows, "rows_per_split": r.get("rows_per_split"), "prevalence": r.get("prevalence"),
                         "temporal_integrity": r.get("temporal_integrity"), "paired": r.get("paired")})
        else:
            runs.append({**base, "note": "This run is not a prediction-accuracy benchmark; see the Research Console benchmark page for it."})
    return {"evidence": "benchmark", "available": True, "label": "Public-data benchmarks (shown as stored)", "runs": runs, "reading_notes": data.get("reading_notes", [])}


# ------------------------------------------------------------------------------------------------ one business's own validation
def _method_cards(mm: dict[str, Any] | None, context: dict[str, Any]) -> list[dict[str, Any]]:
    if not mm:
        return []
    return [card("mae", mm.get("mae"), target_unit=TARGET_UNIT, context=context), card("rmse", mm.get("rmse"), target_unit=TARGET_UNIT, context=context),
            card("wape", mm.get("wape"), as_percent_of_fraction=True, context=context, reason=mm.get("wape_note"), kind="not_applicable"),
            card("bias", mm.get("bias_units_per_day"), target_unit=TARGET_UNIT, context=context),
            card("relative_bias", mm.get("relative_bias"), as_percent_of_fraction=True, context=context, reason=mm.get("wape_note"), kind="not_applicable"),
            card("n_eval", mm.get("n_points"), context=context)]


def _present_forecast_run(report: dict[str, Any]) -> dict[str, Any]:
    horizons = []
    for h in report.get("horizons", []):
        entry: dict[str, Any] = {"horizon_days": h.get("horizon_days"), "status": h.get("status"), "statement": h.get("statement"), "origins": h.get("origins"),
                                 "holdout_origins": h.get("holdout_origins"), "selection_origins": h.get("selection_origins")}
        st = h.get("status")
        if st == "evaluated":
            chosen = (h.get("production") or {}).get("selected_method")
            hold = h.get("holdout") or {}
            sel = hold.get(chosen) if chosen in hold else None
            c = _ctx(block="untouched holdout origins", horizon_days=h.get("horizon_days"), method=chosen, origins=h.get("holdout_origins"))
            entry["method"] = chosen
            entry["cards"] = _method_cards(sel, c)
            ref = {k: hold.get(k) for k in ("naive_last", "seasonal_naive_7", "trailing_mean_28") if hold.get(k)}
            entry["references"] = [{"method": k, "cards": _method_cards(v, _ctx(block="untouched holdout origins", horizon_days=h.get("horizon_days"), method=k))[:2]}
                                   for k, v in ref.items()]
            comp = h.get("comparison_on_holdout") or {}
            entry["baseline_comparison"] = [
                {"reference": name, "mae_ratio": comp.get(key), "reading": "ratio below 1 means the selected method had the lower holdout MAE"}
                for name, key in (("naive_last", "selected_vs_naive_last_mae_ratio"), ("trailing_mean_28", "selected_vs_trailing_mean_mae_ratio"),
                                  ("seasonal_naive_7", "selected_vs_seasonal_naive_mae_ratio"))]
            entry["verdict"] = h.get("verdict")
            iv = h.get("interval") or {}
            entry["interval_coverage"] = card("coverage", iv.get("observed_holdout_coverage"), as_percent_of_fraction=True,
                                              context=_ctx(promised=f"{round((iv.get('nominal_coverage') or 0) * 100)}%", points=iv.get("holdout_points")),
                                              extra_caveat=iv.get("limitation"))
            entry["interval_reliable_by_policy"] = iv.get("reliable_by_policy")
        elif st == "descriptive_only":
            allm = h.get("all_origins") or {}
            entry["cards"] = []
            entry["references"] = [{"method": k, "cards": _method_cards(v, _ctx(block="all backtest origins (descriptive only)", horizon_days=h.get("horizon_days"), method=k))[:3]}
                                   for k, v in allm.items()]
            entry["interval_coverage"] = card("coverage", None, status=NOT_EVALUATED, kind="insufficient_data",
                                              reason="Too few backtest origins to keep an untouched holdout, so coverage was not checked.")
        else:
            entry["cards"] = []
            entry["interval_coverage"] = card("coverage", None, status=NOT_EVALUATED, kind="failed" if st == "refused" else "insufficient_data",
                                              reason=h.get("statement") or "This horizon could not be evaluated.")
        horizons.append(entry)
    series = report.get("series") or {}
    return {
        "kind": "forecast", "run_id": report.get("id"), "generated_at": report.get("generated_at"), "code_revision": report.get("code_revision"),
        "dataset": report.get("dataset"), "series": {k: series.get(k) for k in ("series_class", "pattern", "zero_share", "mean_units_per_day", "metric_guidance")},
        "data_quality": report.get("data_quality"), "config": report.get("config"), "horizons": horizons, "headline": report.get("headline"),
        "not_evidence_of": (report.get("evidence") or {}).get("not_evidence_of", []),
    }


def _present_customer_run(report: dict[str, Any]) -> dict[str, Any]:
    cuts = []
    for c in report.get("cutoffs", []):
        e: dict[str, Any] = {"cutoff": c.get("cutoff"), "label_window": c.get("label_window"), "status": c.get("status"), "reason": c.get("reason"),
                             "customers": c.get("customers"), "inactive": c.get("inactive")}
        if c.get("status") == "evaluated":
            ctx = _ctx(block="customers at this cutoff", n=c.get("customers"), positive_class="inactive (no purchase in the window)")
            n_c = c.get("customers")
            top_n = -(-int(n_c) // 10) if _isnum(n_c) else None                 # the validation takes ceil(10% of customers)
            ctx_top = {**ctx, "top_group": f"{top_n:,} highest-scored customers (10%, rounded up)" if top_n else None}
            e["cards"] = [card("roc_auc", c.get("roc_auc"), context=ctx),
                          card("prevalence", c.get("prevalence"), context=ctx),
                          card("roc_auc", c.get("roc_auc_recency_only"), context={**ctx, "reference": "ranking by days since last purchase only"}),
                          card("top_decile_lift", c.get("top_decile_lift"), context=ctx_top,
                               reason="This report did not record the top-decile result (it was run before it was added)."),
                          card("top_decile_inactive_rate", c.get("top_decile_inactive_rate"), context=ctx_top,
                               reason="This report did not record the top-decile result (it was run before it was added).")]
        cuts.append(e)
    return {"kind": "customer", "run_id": report.get("id"), "generated_at": report.get("generated_at"), "model": report.get("model"), "target": report.get("target"),
            "cutoffs": cuts, "stable_across_cutoffs": report.get("stable_across_cutoffs"), "headline": report.get("headline"),
            "calibration": card("brier", None, status=NOT_EVALUATED, kind="not_applicable", reason=(report.get("calibration") or {}).get("reason")),
            "not_evidence_of": (report.get("evidence") or {}).get("not_evidence_of", [])}


def business_validation(db: Session, business_id: str) -> dict[str, Any]:
    """The newest stored validation reports of ONE business (the caller has already been checked as its owner)."""
    out: dict[str, Any] = {"evidence": "business", "label": "This business's own history (backtest)", "forecast": None, "customer": None}
    for kind, key, present in (("forecast_eval", "forecast", _present_forecast_run), ("customer_eval", "customer", _present_customer_run)):
        runs = analysis_run_service.list_runs(db, business_id, kind, limit=1)
        if runs:
            full = analysis_run_service.get(db, business_id, runs[0]["id"], kind)
            out[key] = present({**(full.get("result") or {}), "id": full["id"]})
    return out


def present_run(report: dict[str, Any], kind: str) -> dict[str, Any]:
    return _present_forecast_run(report) if kind == "forecast" else _present_customer_run(report)


# ------------------------------------------------------------------------------------------------ whole page
def overview(db: Session) -> dict[str, Any]:
    models = _models_section(db)
    bench = _benchmark_section()
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sections": {
            "training": models,
            "benchmark": bench,
            "production": {"evidence": "production", "label": "Live use", "status": NOT_EVALUATED,
                           "reason": "Accuracy of live forecasts against what actually happened is tracked per business (Outcome tracking) and is not aggregated "
                                     "here, so no production metric is shown. Training and benchmark figures must not be read as production accuracy."},
        },
        "availability": {
            "forecasting_models": len(models["forecasting"]), "classification_models": len(models["classification"]),
            "benchmark_runs": len(bench.get("runs", [])),
        },
        "glossary": metric_definitions(),
        "limitations": LIMITATIONS,
    }
