"""Model zoo for the benchmark: existing algorithms are kept, XGBoost / LightGBM / CatBoost are added.

Hyper-parameters come from a small FIXED grid declared here (never tuned on the test window). Each config id is
``<family>:<variant>``; selection picks one variant per family on the validation origins.
"""
from __future__ import annotations

from typing import Any, Callable

import numpy as np
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

CATEGORICAL = ("dept_code", "cat_code", "item_code")


class Predictor:
    """Thin uniform wrapper: ``fit(X, y)`` / ``predict(X)`` on a numpy matrix whose columns follow ``feature_names``."""

    def __init__(self, family: str, variant: str, factory: Callable[[list[str], int], Any], feature_names: list[str], seed: int):
        self.family, self.variant, self.feature_names, self.seed = family, variant, feature_names, seed
        self.model = factory(feature_names, seed)

    @property
    def config_id(self) -> str:
        return f"{self.family}:{self.variant}"

    def fit(self, X: np.ndarray, y: np.ndarray) -> "Predictor":
        self.model.fit(self._x(X), y)
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        return np.clip(np.asarray(self.model.predict(self._x(X)), dtype=np.float64), 0.0, None)

    def _x(self, X: np.ndarray):
        if self.family == "catboost":
            import pandas as pd

            df = pd.DataFrame(X, columns=self.feature_names)
            for c in CATEGORICAL:
                if c in df.columns:
                    df[c] = df[c].fillna(-1).astype(int)
            return df
        if self.family in ("linear", "ridge", "random_forest"):
            import pandas as pd

            return pd.DataFrame(X, columns=self.feature_names)
        return X


def _linear_preprocessor(names: list[str]):
    cat_idx = [n for n in names if n == "dept_code"]
    num = [n for n in names if n not in CATEGORICAL]
    return ColumnTransformer([
        ("num", make_pipeline(SimpleImputer(strategy="median"), StandardScaler()), num),
        ("dept", make_pipeline(SimpleImputer(strategy="most_frequent"), OneHotEncoder(handle_unknown="ignore")), cat_idx),
    ])


def _make_linear(alpha: float | None):
    def f(names: list[str], seed: int):
        est = LinearRegression() if alpha is None else Ridge(alpha=alpha, random_state=seed)
        return make_pipeline(_linear_preprocessor(names), est)
    return f


def _make_rf(min_leaf: int):
    def f(names: list[str], seed: int):
        return make_pipeline(
            SimpleImputer(strategy="median"),
            RandomForestRegressor(n_estimators=100, min_samples_leaf=min_leaf, max_features=0.5, max_samples=0.3, n_jobs=2, random_state=seed),
        )
    return f


def _make_hgb(max_depth: int, max_iter: int):
    def f(names: list[str], seed: int):
        cat = [names.index(c) for c in CATEGORICAL if c in names]
        return HistGradientBoostingRegressor(max_iter=max_iter, learning_rate=0.05, max_depth=max_depth, random_state=seed)
    return f


def _make_xgb(max_depth: int):
    def f(names: list[str], seed: int):
        from xgboost import XGBRegressor

        return XGBRegressor(n_estimators=400, max_depth=max_depth, learning_rate=0.05, subsample=0.8, colsample_bytree=0.8,
                            min_child_weight=5, tree_method="hist", n_jobs=2, random_state=seed, verbosity=0)
    return f


def _make_lgbm(objective: str):
    def f(names: list[str], seed: int):
        from lightgbm import LGBMRegressor

        kw = {"objective": "tweedie", "tweedie_variance_power": 1.1} if objective == "tweedie" else {"objective": "regression"}
        return LGBMRegressor(n_estimators=500, learning_rate=0.05, num_leaves=31, min_child_samples=40, subsample=0.8, subsample_freq=1,
                             colsample_bytree=0.8, n_jobs=2, random_state=seed, verbose=-1, **kw)
    return f


def _make_cat(depth: int):
    def f(names: list[str], seed: int):
        from catboost import CatBoostRegressor

        return CatBoostRegressor(iterations=500, depth=depth, learning_rate=0.08, loss_function="RMSE", random_seed=seed, thread_count=2,
                                 verbose=0, allow_writing_files=False, cat_features=[n for n in names if n in CATEGORICAL])
    return f


GRID: dict[str, dict[str, Callable]] = {
    "linear": {"ols": _make_linear(None)},
    "ridge": {"alpha1": _make_linear(1.0), "alpha100": _make_linear(100.0)},
    "random_forest": {"leaf5": _make_rf(5), "leaf20": _make_rf(20)},
    "hist_gradient_boosting": {"depth4": _make_hgb(4, 200), "depth6": _make_hgb(6, 300)},
    "xgboost": {"depth4": _make_xgb(4), "depth6": _make_xgb(6)},
    "lightgbm": {"l2": _make_lgbm("l2"), "tweedie": _make_lgbm("tweedie")},
    "catboost": {"depth6": _make_cat(6), "depth8": _make_cat(8)},
}
ORIGINAL_FAMILIES = ("linear", "ridge", "random_forest", "hist_gradient_boosting")  # kept from the existing comparison
ADDED_FAMILIES = ("xgboost", "lightgbm", "catboost")


def build(family: str, variant: str, feature_names: list[str], seed: int) -> Predictor:
    return Predictor(family, variant, GRID[family][variant], feature_names, seed)
