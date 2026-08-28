"""Dataset-specific raw -> canonical adapters for external benchmarks.

Each adapter is a set of pure functions that read an *unmodified* raw file
from ``data/external/<name>/raw/`` and return DataFrames matching a
DecisionGPT canonical schema:

- forecasting: ``series_id, date, units_sold, price, marketing_spend, promotion_flag``
  (the contract of ``ml/training/train_forecasting.train_one``)
- churn: ``tenure_days, recency_days, frequency, avg_order_value,
  monetary_value, churned`` (the contract of ``ml/training/train_churn.train_one``)

Adapters never touch the Digital Twin / Causal Graph / Multi-Agent code and
never write to the platform datasets. All randomness is seeded.
"""

FORECASTING_CANONICAL_COLUMNS = [
    "series_id",
    "date",
    "units_sold",
    "price",
    "marketing_spend",
    "promotion_flag",
]

CHURN_CANONICAL_COLUMNS = [
    "tenure_days",
    "recency_days",
    "frequency",
    "avg_order_value",
    "monetary_value",
    "churned",
]
