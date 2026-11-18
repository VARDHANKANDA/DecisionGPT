"""Compatibility wrapper. Reading and cleaning an upload now lives in ``app/services/upload_preprocessing.py`` (and the kind-of-data assignment in
``data_ingestion_service.assign_types``); this keeps the old entry point for callers that only want the cleaned tables.
"""
import pandas as pd

from app.core.config import get_settings
from app.services import upload_preprocessing as prep


def parse_upload(filename: str, content: bytes, data_type_hint: str | None = None) -> dict[str, pd.DataFrame]:
    """{canonical type: cleaned table (text/native values, headers cleaned, blank rows and empty columns removed)}."""
    from app.services.data_ingestion_service import assign_types

    read = prep.read_upload(filename, content, get_settings().max_upload_rows)
    assigned, _ = assign_types(read, filename, data_type_hint)
    return {t: read.frames[name] for name, t in assigned.items()}
