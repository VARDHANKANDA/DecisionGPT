"""Forecast ensembles that use ONLY validation-origin predictions for any fitted quantity.

* ``mean``: unweighted average of the given models (no fitting).
* ``nnls``: non-negative least-squares weights fitted on pooled validation predictions (each produced by a model trained strictly
  before its validation window), normalised to sum to one. The weights never see the test window.
A learned meta-model with more capacity is deliberately not offered: three overlapping-series validation origins are not enough
independent data (see docs/ML_BENCHMARK_REPORT.md); the report records it as "not run".
"""
from __future__ import annotations

import numpy as np
from scipy.optimize import nnls


def mean_ensemble(preds: list[np.ndarray]) -> np.ndarray:
    return np.mean(np.stack(preds, axis=0), axis=0)


def nnls_weights(val_preds: np.ndarray, val_y: np.ndarray) -> np.ndarray:
    """``val_preds`` [n_points, n_models]. Returns weights >= 0 summing to 1 (equal weights if the fit is degenerate)."""
    w, _ = nnls(val_preds, val_y)
    s = w.sum()
    return w / s if s > 1e-12 else np.full(val_preds.shape[1], 1.0 / val_preds.shape[1])


def weighted(preds: np.ndarray, w: np.ndarray) -> np.ndarray:
    return preds @ w
