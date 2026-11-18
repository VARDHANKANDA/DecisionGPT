"""Feature engineering for the sales forecasting model.

Lag/rolling features are computed per series_id (groupby) so no series ever
sees another series' history, and rolling windows only look backward — no
future leakage (docs/DATA_SPECIFICATION.md §6).
"""
import pandas as pd

FEATURE_COLUMNS = [
    "lag_1",
    "lag_7",
    "rolling_mean_7",
    "rolling_mean_28",
    "day_of_week",
    "is_weekend",
    "month",
    "price",
    "marketing_spend",
    "promotion_flag",
]
TARGET_COLUMN = "units_sold"


def build_forecasting_features(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["date"] = pd.to_datetime(out["date"])
    out = out.sort_values(["series_id", "date"])

    grouped = out.groupby("series_id")[TARGET_COLUMN]
    out["lag_1"] = grouped.shift(1)
    out["lag_7"] = grouped.shift(7)
    out["rolling_mean_7"] = grouped.transform(lambda s: s.shift(1).rolling(7).mean())
    out["rolling_mean_28"] = grouped.transform(lambda s: s.shift(1).rolling(28).mean())

    out["day_of_week"] = out["date"].dt.dayofweek
    out["is_weekend"] = (out["day_of_week"] >= 5).astype(int)
    out["month"] = out["date"].dt.month

    # First 28 rows of each series can't have a full rolling_mean_28 window.
    out = out.dropna(subset=FEATURE_COLUMNS + [TARGET_COLUMN]).reset_index(drop=True)
    return out
