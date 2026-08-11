"""Business-upload validation — distinct from ml/pipeline/validation.py
(which validates offline platform/research datasets). This one checks a
single business's uploaded sheet against a canonical type after mapping.
"""
from dataclasses import dataclass, field

import pandas as pd

from app.services.canonical_schema import CanonicalType


@dataclass
class DataQualityReport:
    row_count: int
    missing_required_field_values: dict[str, int] = field(default_factory=dict)
    duplicate_row_count: int = 0
    invalid_date_rows: dict[str, int] = field(default_factory=dict)
    issues: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return not self.issues


def validate_mapped_dataframe(df: pd.DataFrame, canonical_type: CanonicalType) -> DataQualityReport:
    issues: list[str] = []
    missing_counts: dict[str, int] = {}
    invalid_date_rows: dict[str, int] = {}

    for field_name in canonical_type.required_fields:
        if field_name not in df.columns:
            issues.append(f"Required field '{field_name}' is missing after mapping.")
            continue
        n_missing = int(df[field_name].isna().sum())
        if n_missing:
            missing_counts[field_name] = n_missing

    for field_name, spec in canonical_type.fields.items():
        if spec.kind == "date" and field_name in df.columns:
            parsed = pd.to_datetime(df[field_name], errors="coerce")
            n_invalid = int(parsed.isna().sum() - df[field_name].isna().sum())
            if n_invalid > 0:
                invalid_date_rows[field_name] = n_invalid

    duplicate_row_count = int(df.duplicated().sum())

    if len(df) == 0:
        issues.append("No rows found in the uploaded sheet.")
    if duplicate_row_count:
        issues.append(f"{duplicate_row_count} duplicate rows detected.")
    for field_name, n_invalid in invalid_date_rows.items():
        issues.append(f"{n_invalid} rows have an unparseable date in '{field_name}'.")

    return DataQualityReport(
        row_count=len(df),
        missing_required_field_values=missing_counts,
        duplicate_row_count=duplicate_row_count,
        invalid_date_rows=invalid_date_rows,
        issues=issues,
    )
