"""Dataset validation — run before any preprocessing/training step.

Returns a structured report rather than raising on the first problem, so
callers (training scripts, the future Research Console) can show the full
picture instead of one error at a time.
"""
from dataclasses import dataclass, field

import pandas as pd


@dataclass
class ValidationReport:
    is_valid: bool
    row_count: int
    missing_columns: list[str] = field(default_factory=list)
    missing_value_counts: dict[str, int] = field(default_factory=dict)
    duplicate_row_count: int = 0
    issues: list[str] = field(default_factory=list)


def validate_dataframe(
    df: pd.DataFrame,
    required_columns: list[str],
    key_columns: list[str] | None = None,
) -> ValidationReport:
    missing_columns = [c for c in required_columns if c not in df.columns]

    missing_value_counts = {}
    if not missing_columns:
        for col in required_columns:
            n_missing = int(df[col].isna().sum())
            if n_missing:
                missing_value_counts[col] = n_missing

    duplicate_row_count = int(df.duplicated(subset=key_columns).sum()) if key_columns else int(
        df.duplicated().sum()
    )

    issues = []
    if missing_columns:
        issues.append(f"Missing required columns: {missing_columns}")
    if duplicate_row_count:
        issues.append(f"{duplicate_row_count} duplicate rows detected")
    if len(df) == 0:
        issues.append("Dataset is empty")

    return ValidationReport(
        is_valid=len(issues) == 0,
        row_count=len(df),
        missing_columns=missing_columns,
        missing_value_counts=missing_value_counts,
        duplicate_row_count=duplicate_row_count,
        issues=issues,
    )
