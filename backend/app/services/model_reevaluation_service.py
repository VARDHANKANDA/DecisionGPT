"""Research Console - re-evaluation of a REGISTERED FORECASTING MODEL on the held-out test block of its own dataset.

Why this exists: models registered before WAPE, the evaluated-row count and the baseline's errors were recorded at training time (they stored only MAE, RMSE
and MAPE), so the console could not show WAPE or an improvement over the baseline for them. This service re-scores the *stored artifact* - it never trains,
never calls an external service and never changes the model or its recorded training metrics - and stores the result next to them
(``models.lifecycle_json['reevaluation']``).

Safeguards (each one is a stated status, never a silent default):
  * the data and the split are rebuilt with the SAME functions the training code uses (clean -> features -> chronological 70/15/15 split by date), and only the
    final TEST block is scored; training or validation rows are never scored here;
  * the recomputed MAE, RMSE and MAPE must reproduce the values the training run recorded (relative tolerance 1e-6). If they do not, the artifact or dataset is not
    the one that was evaluated: the status is ``verification_failed`` and NO metric from this run is shown as that model's result;
  * a model whose artifact or dataset cannot be found is ``unavailable`` with the reason; nothing is invented;
  * undefined results (zero actual volume, no valid pairs, empty test block) are ``None`` with a reason, never 0.
"""
from __future__ import annotations

import importlib.util
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.core.errors import NotFoundError, ValidationFailedError
from app.models.ml_model import MLModel
from app.models.research import ResearchDatasetVersion
from app.services import research_dataset_service

PROJECT_ROOT = Path(__file__).resolve().parents[3]
MODELS_ROOT = PROJECT_ROOT / "models"
BASELINE_NAME = "Yesterday's value (1-day lag)"
HORIZON = "1 day ahead"
SPLIT_SCHEME = "chronological 70% train / 15% validation / 15% test by date (never shuffled); only the final test block is scored here"
REL_TOL = 1e-6
METHOD = (
    "The stored model artifact was re-scored on the held-out test block of its own dataset, rebuilt with the same cleaning, features and chronological split as "
    "training. Each forecast is one step ahead (the previous day's value is an input). The baseline (yesterday's value) is scored on exactly the same rows. No model was trained and nothing was fitted."
)

STATUS_EVALUATED, STATUS_UNAVAILABLE, STATUS_FAILED = "evaluated", "unavailable", "failed"
_UPLOAD = re.compile(r"^upload:([0-9a-fA-F-]{36}):v(\d+)$")


class Unavailable(Exception):
    """The evaluation cannot be run (missing artifact or dataset); carries the plain-language reason."""


# ------------------------------------------------------------------------------------------------ pure arithmetic (unit-tested)
def relative_improvement_pct(baseline: float | None, model: float | None) -> float | None:
    """100 x (baseline - model) / baseline. None - never 0 - when either value is missing/non-finite or the baseline is not positive."""
    if baseline is None or model is None:
        return None
    try:
        b, m = float(baseline), float(model)
    except (TypeError, ValueError):
        return None
    if not (math.isfinite(b) and math.isfinite(m)) or b <= 0:
        return None
    return 100.0 * (b - m) / b


def score_pairs(actual: Any, predicted: Any) -> dict[str, Any]:
    """Forecast metrics from actual-vs-predicted pairs using the project's authoritative functions (``ml.evaluation.metrics``).

    Non-finite pairs are left out and counted. With no valid pair nothing is computed (all None). WAPE is None when the actual volume is zero; MAPE is returned
    as a raw percentage and is flagged unreliable by the caller when actuals contain zeros."""
    from ml.evaluation import metrics as M

    y = np.asarray(actual, dtype=float).ravel()
    p = np.asarray(predicted, dtype=float).ravel()
    if y.shape != p.shape:
        raise ValueError("actual and predicted must have the same length")
    ok = np.isfinite(y) & np.isfinite(p)
    n_invalid = int(ok.size - ok.sum())
    y, p = y[ok], p[ok]
    out: dict[str, Any] = {"n_eval": int(y.size), "n_invalid": n_invalid, "n_zero_actual": int((np.abs(y) <= 1e-9).sum()) if y.size else 0,
                           "mae": None, "rmse": None, "mape": None, "wape": None, "bias": None, "actual_total": float(np.abs(y).sum()) if y.size else 0.0}
    if y.size == 0:
        return out
    out.update(mae=M.mae(y, p), rmse=M.rmse(y, p), mape=M.mape(y, p), wape=M.wape(y, p), bias=float(np.mean(p - y)))
    return out


def verify_against_stored(recomputed: dict[str, Any], stored: dict[str, Any]) -> dict[str, Any]:
    """Does the re-score reproduce what the training run recorded? Compared on MAE, RMSE and MAPE (the values every registered run has)."""
    compared, ok = {}, True
    for k in ("mae", "rmse", "mape"):
        s, r = stored.get(k), recomputed.get(k)
        if not isinstance(s, (int, float)) or isinstance(s, bool) or r is None:
            continue
        match = math.isclose(float(s), float(r), rel_tol=REL_TOL, abs_tol=1e-9)
        compared[k] = {"stored": float(s), "recomputed": float(r), "match": bool(match)}
        ok = ok and match
    return {"stored_metrics_matched": bool(ok and compared), "compared": compared, "tolerance_rel": REL_TOL, "reason": None if (ok and compared) else
            ("no recorded metric to compare with" if not compared else "the recomputed MAE/RMSE/MAPE do not reproduce the values recorded at training")}


# ------------------------------------------------------------------------------------------------ rebuilding the evaluation inputs
def _dataframe(db: Session, m: MLModel) -> tuple[pd.DataFrame, str]:
    dv = m.dataset_version or ""
    hit = _UPLOAD.match(dv)
    if hit:
        v = db.query(ResearchDatasetVersion).filter(ResearchDatasetVersion.dataset_id == hit.group(1), ResearchDatasetVersion.version == int(hit.group(2))).first()
        if v is None:
            raise Unavailable(f"The research dataset version {dv} is no longer registered.")
        try:
            return research_dataset_service.load_version_dataframe(v), f"stored research upload ({dv})"
        except NotFoundError as exc:
            raise Unavailable(str(exc)) from exc
    if dv.startswith("platform-forecasting"):
        from ml.pipeline.loaders import load_platform_dataset

        try:
            return load_platform_dataset("forecasting", "sales_timeseries.csv").dataframe, f"platform dataset file ({dv})"
        except FileNotFoundError:
            pass
        gen = PROJECT_ROOT / "scripts" / "generate_platform_data.py"
        if not gen.exists():
            raise Unavailable("The platform forecasting file is absent and its generator script is not available.")
        spec = importlib.util.spec_from_file_location("_platform_generator", gen)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        df = mod.generate_forecasting_dataset(np.random.default_rng(mod.RANDOM_SEED))
        return df, (f"platform dataset {dv} regenerated in memory with its documented seed ({mod.RANDOM_SEED}) because the stored file is absent; "
                    "accepted only if the recomputed metrics reproduce the recorded ones")
    raise Unavailable(f"The dataset '{dv}' cannot be rebuilt from this registry entry.")


def _predictor(m: MLModel):
    if m.model_type.endswith("naive"):
        return None                                           # the naive model is the lag-1 baseline itself; no artifact is needed
    path = (PROJECT_ROOT / m.model_path).resolve()
    try:
        path.relative_to(MODELS_ROOT.resolve())
    except ValueError as exc:                                  # never load anything outside the model registry folder
        raise Unavailable("The registered artifact path is outside the model registry folder.") from exc
    if not path.exists():
        raise Unavailable(f"The stored artifact file for {m.model_name} {m.version} is missing ({m.model_path}).")
    import joblib

    return joblib.load(path)


# ------------------------------------------------------------------------------------------------ public API
def is_forecasting(m: MLModel) -> bool:
    return (m.model_type or "").startswith("forecasting_")


def has_recorded_wape(m: MLModel) -> bool:
    return isinstance((m.metrics_json or {}).get("wape"), (int, float))


def trusted_reevaluation(m: MLModel) -> dict[str, Any] | None:
    rev = (m.lifecycle_json or {}).get("reevaluation")
    if isinstance(rev, dict) and rev.get("status") == STATUS_EVALUATED and rev.get("trusted") is True:
        return rev
    return None


def _store(db: Session, m: MLModel, record: dict[str, Any]) -> dict[str, Any]:
    life = dict(m.lifecycle_json or {})
    life["reevaluation"] = record
    m.lifecycle_json = life
    flag_modified(m, "lifecycle_json")
    db.commit()
    return record


def reevaluate_model(db: Session, model_id: str) -> dict[str, Any]:
    """Re-score one registered forecasting model on its held-out test block and store the outcome. Read-only with respect to the model and the data."""
    m = db.get(MLModel, model_id)
    if m is None:
        raise NotFoundError(f"Model {model_id} not found.")
    if not is_forecasting(m):
        raise ValidationFailedError("Only forecasting models can be re-evaluated here; classification models record their own confusion matrix at training.")
    now = datetime.now(timezone.utc).isoformat()
    base = {"evaluated_at": now, "method": METHOD, "horizon": HORIZON, "baseline": {"name": BASELINE_NAME}, "split": {"scheme": SPLIT_SCHEME}, "trusted": False}
    try:
        from ml.features.forecasting_features import FEATURE_COLUMNS, TARGET_COLUMN, build_forecasting_features
        from ml.pipeline.preprocessing import chronological_split, clean_dataframe

        df, provenance = _dataframe(db, m)
        predictor = _predictor(m)
        feat = build_forecasting_features(clean_dataframe(df, date_columns=["date"]))
        _train, _val, test = chronological_split(feat, "date")
        if len(test) == 0:
            raise Unavailable("The chronological split left no test rows, so nothing can be evaluated.")
        y = test[TARGET_COLUMN].to_numpy(dtype=float)
        base_pred = test["lag_1"].to_numpy(dtype=float)
        pred = base_pred if predictor is None else np.asarray(predictor.predict(test[list(FEATURE_COLUMNS)]), dtype=float)
        model_scores, base_scores = score_pairs(y, pred), score_pairs(y, base_pred)
    except Unavailable as exc:
        return _store(db, m, {**base, "status": STATUS_UNAVAILABLE, "reason": str(exc)})
    except Exception as exc:                                     # a scoring failure is reported, never swallowed into a number
        return _store(db, m, {**base, "status": STATUS_FAILED, "reason": f"The evaluation failed ({type(exc).__name__}). Nothing was stored as a metric."})

    verification = verify_against_stored(model_scores, m.metrics_json or {})
    dates = pd.to_datetime(test["date"])
    split = {"scheme": SPLIT_SCHEME, "test_start": str(dates.min().date()), "test_end": str(dates.max().date()), "n_test_rows": int(len(test)),
             "n_series": int(test["series_id"].nunique()) if "series_id" in test.columns else None}
    is_baseline = m.model_type.endswith("naive")
    record = {**base, "split": split, "dataset": {"version": m.dataset_version, "provenance": provenance}, "verification": verification,
              "metrics": {k: v for k, v in model_scores.items()}, "baseline": {"name": BASELINE_NAME, "mae": base_scores["mae"], "rmse": base_scores["rmse"], "wape": base_scores["wape"]},
              "improvement": {"wape_pct": None if is_baseline else relative_improvement_pct(base_scores["wape"], model_scores["wape"]),
                              "mae_pct": None if is_baseline else relative_improvement_pct(base_scores["mae"], model_scores["mae"])}}
    if not verification["stored_metrics_matched"]:
        record.update(status=STATUS_FAILED, trusted=False, reason=(
            "Verification failed: " + verification["reason"] + ". The stored artifact or the rebuilt dataset is not the one that was evaluated at training time, "
            "so no figure from this re-scoring (WAPE, bias, baseline) is shown for it. Any MAE and RMSE displayed are the values recorded at training."))
        record["metrics"], record["baseline"], record["improvement"] = {}, {"name": BASELINE_NAME}, {}   # nothing untrusted is kept as a number
        return _store(db, m, record)
    record.update(status=STATUS_EVALUATED, trusted=True, reason=None)
    return _store(db, m, record)


def pending_models(db: Session) -> list[MLModel]:
    """Forecasting models with no recorded WAPE for which the re-evaluation has never been attempted (a failed or unavailable attempt is not silently retried)."""
    ms = db.query(MLModel).order_by(MLModel.model_name, MLModel.created_at.desc()).all()
    return [m for m in ms if is_forecasting(m) and not has_recorded_wape(m) and not isinstance((m.lifecycle_json or {}).get("reevaluation"), dict)]


def reevaluate_pending(db: Session) -> dict[str, Any]:
    results = []
    for m in pending_models(db):
        rec = reevaluate_model(db, m.id)
        results.append({"model_id": m.id, "model": f"{m.model_name} {m.version}", "status": rec["status"], "reason": rec.get("reason")})
    return {"attempted": len(results), "evaluated": sum(r["status"] == STATUS_EVALUATED for r in results), "results": results}
