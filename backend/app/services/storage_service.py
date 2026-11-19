"""Storage service abstraction supporting both local filesystem and Supabase Object Storage.

For local development or environments without cloud storage credentials, all operations fall back cleanly
to local filesystem paths. In cloud deployments (Render, Railway, etc.), setting SUPABASE_URL and
SUPABASE_SERVICE_ROLE_KEY routes uploads and persistent artifacts to Supabase Storage so that ephemeral
container restarts never lose data.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional, Protocol

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class StorageBackend(Protocol):
    def save(self, key: str, data: bytes, content_type: Optional[str] = None) -> bool:
        """Save bytes under the given key. Returns True on success, False on failure."""
        ...

    def load(self, key: str) -> bytes:
        """Load bytes for the given key. Raises FileNotFoundError if missing."""
        ...

    def delete(self, key: str) -> bool:
        """Delete object at key. Returns True if deleted or did not exist."""
        ...

    def exists(self, key: str) -> bool:
        """Check if object exists at key."""
        ...


class LocalStorageBackend:
    """Stores files on the local filesystem with path traversal protection."""

    def __init__(self, base_path: str | Path):
        root = Path(base_path)
        if not root.is_absolute():
            root = Path(__file__).resolve().parents[3] / root
        self.root = root.resolve()

    def _resolve_safe(self, key: str) -> Path:
        p = (self.root / key).resolve()
        if self.root not in p.parents and p != self.root:
            raise ValueError(f"Path traversal detected: {key}")
        return p

    def save(self, key: str, data: bytes, content_type: Optional[str] = None) -> bool:
        try:
            target = self._resolve_safe(key)
            target.parent.mkdir(parents=True, exist_ok=True)
            tmp = target.with_suffix(target.suffix + ".part")
            tmp.write_bytes(data)
            os.replace(tmp, target)
            return True
        except (OSError, ValueError) as exc:
            logger.warning("Local storage save failed for %s: %s", key, exc)
            return False

    def load(self, key: str) -> bytes:
        target = self._resolve_safe(key)
        if not target.is_file():
            raise FileNotFoundError(f"Key not found in local storage: {key}")
        return target.read_bytes()

    def delete(self, key: str) -> bool:
        try:
            target = self._resolve_safe(key)
            if target.is_file():
                target.unlink(missing_ok=True)
                for parent in (target.parent, target.parent.parent):
                    if parent != self.root:
                        try:
                            parent.rmdir()
                        except OSError:
                            break
            return True
        except (OSError, ValueError):
            return False

    def exists(self, key: str) -> bool:
        try:
            target = self._resolve_safe(key)
            return target.is_file()
        except ValueError:
            return False


class SupabaseStorageBackend:
    """Stores files in a private Supabase Storage bucket."""

    def __init__(
        self,
        url: str,
        service_role_key: str,
        bucket: str = "decisiongpt-storage",
        prefix: str = "",
    ):
        self.bucket = bucket
        self.prefix = prefix.strip("/")
        self._url = url.rstrip("/")
        self._key = service_role_key

        try:
            from supabase import Client, create_client

            self.client: Client = create_client(self._url, self._key)
            self._available = True
        except Exception as exc:
            logger.warning("Supabase client initialization failed: %s; storage will be unavailable", exc)
            self.client = None
            self._available = False

    def _full_key(self, key: str) -> str:
        clean_key = key.lstrip("/\\").replace("\\", "/")
        return f"{self.prefix}/{clean_key}" if self.prefix else clean_key

    def save(self, key: str, data: bytes, content_type: Optional[str] = None) -> bool:
        if not self._available or not self.client:
            return False
        full_key = self._full_key(key)
        file_options: dict[str, str] = {"upsert": "true"}
        if content_type:
            file_options["content-type"] = content_type
        try:
            self.client.storage.from_(self.bucket).upload(
                path=full_key,
                file=data,
                file_options=file_options,
            )
            return True
        except Exception as exc:
            logger.warning("Supabase storage upload failed for %s: %s", full_key, exc)
            return False

    def load(self, key: str) -> bytes:
        if not self._available or not self.client:
            raise FileNotFoundError("Supabase client not available")
        full_key = self._full_key(key)
        try:
            data = self.client.storage.from_(self.bucket).download(full_key)
            if data is None:
                raise FileNotFoundError(f"Supabase key returned empty or not found: {full_key}")
            return data
        except Exception as exc:
            if isinstance(exc, FileNotFoundError):
                raise
            raise FileNotFoundError(f"Supabase key not found {full_key}: {exc}") from exc

    def delete(self, key: str) -> bool:
        if not self._available or not self.client:
            return False
        full_key = self._full_key(key)
        try:
            self.client.storage.from_(self.bucket).remove([full_key])
            return True
        except Exception as exc:
            logger.warning("Supabase storage delete failed for %s: %s", full_key, exc)
            return False

    def exists(self, key: str) -> bool:
        if not self._available or not self.client:
            return False
        full_key = self._full_key(key)
        try:
            parts = full_key.rsplit("/", 1)
            parent = parts[0] if len(parts) > 1 else ""
            filename = parts[-1]
            files = self.client.storage.from_(self.bucket).list(path=parent or None, options={"search": filename})
            if any(isinstance(f, dict) and f.get("name") == filename for f in files):
                return True
        except Exception:
            pass
        try:
            self.load(key)
            return True
        except Exception:
            return False


# Backward compatibility alias
S3StorageBackend = SupabaseStorageBackend


def get_storage(namespace: str = "business_uploads") -> StorageBackend:
    """Return configured storage backend. Uses SupabaseStorageBackend if configured.
    Falls back to LocalStorageBackend for local dev/testing."""
    settings = get_settings()
    supabase_url = getattr(settings, "supabase_url", None)
    supabase_key = getattr(settings, "supabase_service_role_key", None)
    bucket = getattr(settings, "supabase_storage_bucket", "decisiongpt-storage")

    if supabase_url and supabase_key:
        try:
            backend = SupabaseStorageBackend(
                url=supabase_url,
                service_role_key=supabase_key,
                bucket=bucket,
                prefix=namespace,
            )
            if backend._available:
                return backend
        except Exception as exc:
            logger.error("Failed to initialize Supabase storage for namespace '%s': %s.", namespace, exc)
            if settings.is_production:
                raise RuntimeError(
                    f"Production environment requires persistent cloud storage, but Supabase initialization failed for namespace '{namespace}': {exc}"
                ) from exc

    if settings.is_production:
        logger.error(
            "CRITICAL: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are unset in production. "
            "Render has an ephemeral filesystem; uploaded data will be lost on container restart."
        )

    # Local fallback for dev/testing
    if namespace == "research_uploads":
        base_path = getattr(settings, "research_data_path", "./data/research_uploads")
    else:
        base_path = getattr(settings, "business_upload_path", "./data/business_uploads")

    return LocalStorageBackend(base_path=base_path)
