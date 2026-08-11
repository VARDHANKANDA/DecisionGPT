"""Feature engineering for the churn model.

Deliberately limited to fields derivable from the canonical business
customer schema (docs/DATA_SPECIFICATION.md §3: external_customer_id,
segment, first/last_purchase_date, purchase_frequency, monetary_value).
The platform training dataset also has support_tickets/discount_usage_rate,
but a business can never supply those through the normal upload flow, so a
model trained on them could never be run at inference time against real
business data — see AGENTS.md "no fabrication" and docs/DATA_SPECIFICATION
§4 "the application must calculate data sufficiency before enabling a
model." Those two columns are intentionally excluded from FEATURE_COLUMNS.
"""
import pandas as pd

FEATURE_COLUMNS = [
    "tenure_days",
    "recency_days",
    "frequency",
    "avg_order_value",
    "monetary_value",
    "purchase_rate_per_year",
    "recency_ratio",
]
TARGET_COLUMN = "churned"


def build_churn_features(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["purchase_rate_per_year"] = out["frequency"] / (out["tenure_days"] / 365.0).clip(lower=1 / 365)
    out["recency_ratio"] = out["recency_days"] / out["tenure_days"].clip(lower=1)
    return out
