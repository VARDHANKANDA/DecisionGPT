"""Trivial baseline estimators with a scikit-learn-compatible fit/predict
interface, so they can be evaluated and saved through the same registry
code path as the real models (docs/AI_MODULE_SPECIFICATION.md §3: forecasting
must be compared against a naive baseline, not just XGBoost)."""
import numpy as np
import pandas as pd


class NaiveLagForecaster:
    """Predicts units_sold(t) = units_sold(t-1), i.e. the lag_1 feature.
    No fitting required — included for interface symmetry."""

    def fit(self, X: pd.DataFrame, y: pd.Series) -> "NaiveLagForecaster":
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        return X["lag_1"].to_numpy()
