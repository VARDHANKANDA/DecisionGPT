"""Shared preprocessing utilities for platform training pipelines.

Kept intentionally small — see docs/AI_MODULE_SPECIFICATION.md §1 "use the
simplest reliable model/pipeline that fits the dataset."
"""
import pandas as pd


def clean_dataframe(
    df: pd.DataFrame,
    date_columns: list[str] | None = None,
    dedupe_subset: list[str] | None = None,
) -> pd.DataFrame:
    """Parse date columns, drop exact/keyed duplicates, sort if a single
    date column is given. Does not impute — callers decide imputation
    per-column since the right strategy is domain-specific."""
    cleaned = df.copy()

    for col in date_columns or []:
        cleaned[col] = pd.to_datetime(cleaned[col])

    before = len(cleaned)
    cleaned = cleaned.drop_duplicates(subset=dedupe_subset)
    dropped = before - len(cleaned)
    if dropped:
        cleaned.attrs["duplicates_dropped"] = dropped

    if date_columns and len(date_columns) == 1:
        cleaned = cleaned.sort_values(date_columns[0]).reset_index(drop=True)

    return cleaned


def chronological_split(
    df: pd.DataFrame,
    date_column: str,
    train_frac: float = 0.7,
    val_frac: float = 0.15,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Chronological train/val/test split — never shuffled, so no future
    observation can leak into training (docs/DATA_SPECIFICATION.md §6).

    Splits on unique date boundaries rather than raw row count, so with
    multiple parallel series (e.g. one row per series per day) no single
    calendar date ever straddles two partitions.
    """
    ordered = df.sort_values(date_column).reset_index(drop=True)
    unique_dates = ordered[date_column].drop_duplicates().sort_values().reset_index(drop=True)
    n_dates = len(unique_dates)
    train_end_date = unique_dates.iloc[int(n_dates * train_frac) - 1]
    val_end_date = unique_dates.iloc[int(n_dates * (train_frac + val_frac)) - 1]

    train = ordered[ordered[date_column] <= train_end_date]
    val = ordered[(ordered[date_column] > train_end_date) & (ordered[date_column] <= val_end_date)]
    test = ordered[ordered[date_column] > val_end_date]
    return train, val, test
