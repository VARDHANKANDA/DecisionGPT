"""Where the original uploaded file is kept, unchanged, so the cleaned tables can always be traced back to it.

The path is built only from validated UUIDs and a fixed file name; the uploaded file's own name is never part of a path. Writes are atomic
(temporary file, then rename). Nothing here logs file contents.
"""
from __future__ import annotations

import os
import uuid
from pathlib import Path

from app.core.config import get_settings
from app.services.storage_service import get_storage

_ALLOWED_EXT = (".csv", ".xlsx")


def _root() -> Path:
    root = Path(get_settings().business_upload_path)
    if not root.is_absolute():
        root = Path(__file__).resolve().parents[3] / root
    return root


def _key(business_id: str, job_id: str, ext: str) -> str:
    if ext not in _ALLOWED_EXT:
        raise ValueError("unsupported extension")
    return f"{uuid.UUID(str(business_id))}/{uuid.UUID(str(job_id))}/original{ext}"


def extension_of(filename: str) -> str | None:
    lower = (filename or "").lower()
    return next((e for e in _ALLOWED_EXT if lower.endswith(e)), None)


def save_original(business_id: str, job_id: str, filename: str, content: bytes) -> str | None:
    """Store the original bytes; return the storage key (None if the type is not storable). Never raises for a full disk: the import can still
    proceed and the report says the original was not kept."""
    ext = extension_of(filename)
    if ext is None:
        return None
    key = _key(business_id, job_id, ext)
    storage = get_storage("business_uploads")
    if storage.save(key, content):
        return key
    return None


def load_original(key: str) -> bytes:
    storage = get_storage("business_uploads")
    return storage.load(key)


def delete_original(key: str | None) -> None:
    if not key:
        return
    storage = get_storage("business_uploads")
    storage.delete(key)
