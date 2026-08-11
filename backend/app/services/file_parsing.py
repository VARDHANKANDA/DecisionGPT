"""Parse an uploaded CSV or XLSX file into one or more (canonical_type, df)
pairs, per docs/PRD.md §5 "Business Data Pipeline" — a single Excel workbook
with Sales/Customers/Products/Marketing/Inventory sheets is the preferred
demo experience; separate CSVs (one canonical type per file) are also
supported.
"""
import io

import pandas as pd

from app.core.errors import ValidationFailedError
from app.services.canonical_schema import detect_canonical_type


def parse_upload(filename: str, content: bytes, data_type_hint: str | None = None) -> dict[str, pd.DataFrame]:
    lower = filename.lower()

    if lower.endswith(".xlsx") or lower.endswith(".xls"):
        try:
            sheets = pd.read_excel(io.BytesIO(content), sheet_name=None)
        except Exception as exc:
            raise ValidationFailedError(f"Could not read Excel file: {exc}") from exc

        result: dict[str, pd.DataFrame] = {}
        unrecognized: list[str] = []
        for sheet_name, df in sheets.items():
            canonical_type = detect_canonical_type(sheet_name)
            if canonical_type is None:
                unrecognized.append(sheet_name)
                continue
            result[canonical_type] = df
        if not result:
            raise ValidationFailedError(
                "None of the sheet names could be matched to a known data "
                f"type (Sales/Customers/Products/Marketing/Inventory). Sheets found: {list(sheets.keys())}"
            )
        return result

    if lower.endswith(".csv"):
        try:
            df = pd.read_csv(io.BytesIO(content))
        except Exception as exc:
            raise ValidationFailedError(f"Could not read CSV file: {exc}") from exc

        canonical_type = data_type_hint or detect_canonical_type(filename)
        if canonical_type is None:
            raise ValidationFailedError(
                "Could not determine the data type for this CSV from its filename. "
                "Pass data_type explicitly (products|customers|sales|marketing_campaigns|inventory)."
            )
        return {canonical_type: df}

    raise ValidationFailedError(f"Unsupported file type: {filename}. Upload a .csv or .xlsx file.")
