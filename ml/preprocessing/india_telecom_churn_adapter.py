"""India Telecom Customer Churn Preprocessing Adapter.

Converts raw telecom_churn.csv into cleaned, leak-free feature matrices
for customer retention, risk assessment, and classification benchmarks.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RAW_FILE = ROOT / "data" / "external" / "india_telecom_churn" / "raw" / "telecom_churn.csv"
PROCESSED_FILE = ROOT / "data" / "external" / "india_telecom_churn" / "processed" / "india_telecom_churn_clean.csv"

FEATURE_COLUMNS = [
    "age",
    "num_dependents",
    "salary_lakhs",
    "calls_made",
    "sms_sent",
    "data_used_gb",
    "tenure_months",
    "partner_airtel",
    "partner_jio",
    "partner_vodafone",
    "partner_bsnl",
    "gender_female",
]

TARGET_COLUMN = "churn"


def preprocess_telecom_churn(sample_size: int | None = None, random_seed: int = 42) -> pd.DataFrame:
    if not RAW_FILE.exists():
        raise FileNotFoundError(f"Raw dataset not found at {RAW_FILE}")

    df = pd.read_csv(RAW_FILE)
    
    # 1. Clean outliers and negative anomalies in usage
    df["data_used_gb"] = np.maximum(0, df["data_used"].fillna(0)) / 1024.0
    df["calls_made"] = np.maximum(0, df["calls_made"].fillna(0))
    df["sms_sent"] = np.maximum(0, df["sms_sent"].fillna(0))
    df["salary_lakhs"] = np.maximum(0, df["estimated_salary"].fillna(df["estimated_salary"].median())) / 100000.0
    df["age"] = df["age"].clip(18, 90)
    df["num_dependents"] = df["num_dependents"].fillna(0).clip(0, 10)

    # 2. Tenure from registration date
    reg_date = pd.to_datetime(df["date_of_registration"], errors="coerce")
    ref_date = reg_date.max() if not reg_date.isna().all() else pd.Timestamp("2024-12-31")
    tenure_days = (ref_date - reg_date).dt.days.fillna(365)
    df["tenure_months"] = (tenure_days / 30.4).clip(1, 120)

    # 3. Categoricals
    df["partner_airtel"] = (df["telecom_partner"] == "Airtel").astype(int)
    df["partner_jio"] = (df["telecom_partner"] == "Reliance Jio").astype(int)
    df["partner_vodafone"] = (df["telecom_partner"] == "Vodafone").astype(int)
    df["partner_bsnl"] = (df["telecom_partner"] == "BSNL").astype(int)
    df["gender_female"] = (df["gender"].str.upper() == "F").astype(int)

    # 4. Target
    df["churn"] = df["churn"].astype(int)

    cols = ["customer_id", "telecom_partner", "state", "city"] + FEATURE_COLUMNS + [TARGET_COLUMN]
    clean_df = df[cols].copy()

    if sample_size and sample_size < len(clean_df):
        clean_df = clean_df.sample(n=sample_size, random_state=random_seed).reset_index(drop=True)

    PROCESSED_FILE.parent.mkdir(parents=True, exist_ok=True)
    clean_df.to_csv(PROCESSED_FILE, index=False)
    print(f"Preprocessed {len(clean_df):,} rows -> {PROCESSED_FILE}")
    return clean_df


if __name__ == "__main__":
    preprocess_telecom_churn()

