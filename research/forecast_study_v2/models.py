"""Candidate models of forecast_study_v2 and the mathematical target of each objective.

All boosted models share the original study's base hyper-parameters (500 trees (XGBoost 400), learning rate 0.05, 31 leaves, subsample 0.8, column sample 0.8) so that candidates differ in the
OBJECTIVE (and, for two of them, one regularisation setting), not in capacity. Predictions are clipped at zero (demand is non-negative).

Target functional of each objective (population-risk interpretation; trees only approximate it):
  l2 / squared error  : conditional mean                         -> optimal for squared error, and (as a total) for aggregated totals
  l1 / absolute error : conditional median                       -> optimal for absolute error, hence for pooled item-day WAPE (the denominator does not depend on the forecast)
  quantile alpha=0.5  : conditional median (pinball loss at 0.5 = half the absolute error); in LightGBM it differs from 'l1' only in how leaf values are refreshed
  tweedie p           : conditional mean under a Tweedie variance function Var ~ mean^p and a log link (p in (1, 2): compound Poisson-gamma; zero-inflated non-negative data)
A mean-targeting objective is NOT optimal for an absolute-error metric on skewed or sparse data; a median-targeting objective is NOT optimal for totals. Nothing here assumes that an objective is
good for a metric because of its name.
"""
from __future__ import annotations

import numpy as np

from ml.benchmark import models as zoo

LGBM_BASE = dict(n_estimators=500, learning_rate=0.05, num_leaves=31, min_child_samples=40, subsample=0.8, subsample_freq=1, colsample_bytree=0.8, verbose=-1, deterministic=True, force_row_wise=True)
XGB_BASE = dict(n_estimators=400, max_depth=6, learning_rate=0.05, subsample=0.8, colsample_bytree=0.8, min_child_weight=5, tree_method="hist", verbosity=0)

CANDIDATES: dict[str, dict] = {
    "lgbm_tweedie_p11": {"kind": "lgbm", "params": {"objective": "tweedie", "tweedie_variance_power": 1.1}, "target": "conditional mean (Tweedie p=1.1, log link)"},
    "lgbm_tweedie_p15": {"kind": "lgbm", "params": {"objective": "tweedie", "tweedie_variance_power": 1.5}, "target": "conditional mean (Tweedie p=1.5, log link)"},
    "lgbm_l2": {"kind": "lgbm", "params": {"objective": "regression"}, "target": "conditional mean (squared error)"},
    "lgbm_l1": {"kind": "lgbm", "params": {"objective": "l1"}, "target": "conditional median (absolute error)"},
    "lgbm_l1_small": {"kind": "lgbm", "params": {"objective": "l1", "num_leaves": 15, "min_child_samples": 100}, "target": "conditional median (absolute error), smoother trees"},
    "lgbm_quantile50": {"kind": "lgbm", "params": {"objective": "quantile", "alpha": 0.5}, "target": "conditional median (pinball loss at 0.5)"},
    "xgb_l1": {"kind": "xgb", "params": {"objective": "reg:absoluteerror"}, "target": "conditional median (absolute error)"},
    "ridge_a100": {"kind": "ridge", "params": {"alpha": 100.0}, "target": "conditional mean (squared error, linear)"},
}
REFERENCE_MODEL = "lgbm_tweedie_p11"      # the configuration selected in all six cells of forecast_study_v1
MEDIAN_TARGETING = ("lgbm_l1", "lgbm_l1_small", "lgbm_quantile50", "xgb_l1")


class Model:
    def __init__(self, cid: str, names: list[str], seed: int, n_jobs: int = 4):
        spec = CANDIDATES[cid]
        self.cid, self.kind = cid, spec["kind"]
        if self.kind == "lgbm":
            from lightgbm import LGBMRegressor

            self.m = LGBMRegressor(**{**LGBM_BASE, **spec["params"]}, n_jobs=n_jobs, random_state=seed)
        elif self.kind == "xgb":
            from xgboost import XGBRegressor

            self.m = XGBRegressor(**{**XGB_BASE, **spec["params"]}, n_jobs=n_jobs, random_state=seed)
        else:
            self.m = zoo.build("ridge", "alpha100", names, seed)

    def fit(self, X, y):
        self.m.fit(X, y)
        return self

    def predict(self, X) -> np.ndarray:
        return np.maximum(np.asarray(self.m.predict(X), dtype=np.float64), 0.0).astype(np.float32)

    def objective_string(self) -> str:
        if self.kind == "lgbm":
            return str(self.m.get_params().get("objective"))
        if self.kind == "xgb":
            return str(self.m.get_params().get("objective"))
        return "ridge"
