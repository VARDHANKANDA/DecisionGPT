"""Metric functions used across every training/evaluation script and by the
Research Console's Model Performance page. Kept in one place so a metric
name always means the same computation everywhere it's displayed.
"""
import numpy as np
from sklearn.metrics import (
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)


def mae(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.mean(np.abs(np.asarray(y_true) - np.asarray(y_pred))))


def rmse(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.sqrt(np.mean((np.asarray(y_true) - np.asarray(y_pred)) ** 2)))


def mape(y_true: np.ndarray, y_pred: np.ndarray, epsilon: float = 1e-6) -> float:
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    denom = np.maximum(np.abs(y_true), epsilon)
    return float(np.mean(np.abs((y_true - y_pred) / denom)) * 100)


def wape(y_true: np.ndarray, y_pred: np.ndarray) -> float | None:
    """Weighted absolute percentage error = sum|e| / sum|y|. Scale-aware and stable for intermittent demand, unlike MAPE. Returns None
    (never 0) when the actuals sum to zero."""
    y_true = np.asarray(y_true, dtype=float)
    denom = float(np.sum(np.abs(y_true)))
    return float(np.sum(np.abs(y_true - np.asarray(y_pred, dtype=float))) / denom) if denom > 0 else None


def regression_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    out = {
        "mae": mae(y_true, y_pred),
        "rmse": rmse(y_true, y_pred),
        "mape": mape(y_true, y_pred),
    }
    w = wape(y_true, y_pred)
    if w is not None:  # omitted (not 0) when undefined, so consumers never display a fake perfect score
        out["wape"] = w
    return out


def regression_diagnostics(y_true: np.ndarray, y_pred: np.ndarray, zero_tol: float = 1e-9) -> dict:
    """Facts needed to read the regression metrics honestly, recorded next to them: the number of evaluated points, how many actual values
    were zero (percentage errors are undefined there), how many pairs were non-finite and left out, and the signed bias (mean of
    prediction - actual: positive = the model over-forecasts, negative = it under-forecasts). Additive: it never changes the values of
    ``regression_metrics``."""
    y = np.asarray(y_true, dtype=float)
    p = np.asarray(y_pred, dtype=float)
    ok = np.isfinite(y) & np.isfinite(p)
    y, p = y[ok], p[ok]
    out = {"n_eval": int(y.size), "n_invalid": int(ok.size - ok.sum()), "n_zero_actual": int((np.abs(y) <= zero_tol).sum())}
    if y.size:
        out["bias"] = float(np.mean(p - y))
    return out


def classification_metrics(y_true: np.ndarray, y_pred: np.ndarray, y_proba: np.ndarray) -> dict:
    return {
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
        "roc_auc": float(roc_auc_score(y_true, y_proba)),
    }
