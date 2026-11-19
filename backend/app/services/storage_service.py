"""Storage service abstraction supporting both local filesystem and cloud object storage (S3 / Cloudflare R2 / MinIO).

For local development or environments without cloud object storage credentials, all operations fall back cleanly
to local filesystem paths. In cloud deployments (Render, Railway, AWS, etc.), setting S3_BUCKET and AWS credentials
routes uploads and persistent artifacts to object storage so that ephemeral container restarts never lose data.
"""
from __future__ import annotations

import io
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


class S3StorageBackend:
    """Stores files in an S3-compatible bucket (AWS S3, Cloudflare R2, MinIO, Wasabi)."""

    def __init__(
        self,
        bucket: str,
        region: str = "us-east-1",
        endpoint_url: Optional[str] = None,
        access_key_id: Optional[str] = None,
        secret_access_key: Optional[str] = None,
        prefix: str = "",
    ):
        self.bucket = bucket
        self.prefix = prefix.strip("/")
        self._endpoint_url = endpoint_url

        try:
            import boto3
            from botocore.config import Config

            session_kwargs = {}
            if access_key_id and secret_access_key:
                session_kwargs["aws_access_key_id"] = access_key_id
                session_kwargs["aws_secret_access_key"] = secret_access_key

            session = boto3.Session(region_name=region, **session_kwargs)
            client_kwargs = {
                "config": Config(signature_version="s3v4", retries={"max_attempts": 3, "mode": "standard"})
            }
            if endpoint_url:
                client_kwargs["endpoint_url"] = endpoint_url

            self.client = session.client("s3", **client_kwargs)
            self._available = True
        except Exception as exc:
            logger.warning("S3 client initialization failed: %s; S3 storage will be unavailable", exc)
            self.client = None
            self._available = False

    def _full_key(self, key: str) -> str:
        clean_key = key.lstrip("/")
        return f"{self.prefix}/{clean_key}" if self.prefix else clean_key

    def save(self, key: str, data: bytes, content_type: Optional[str] = None) -> bool:
        if not self._available or not self.client:
            return False
        full_key = self._full_key(key)
        kwargs = {"Bucket": self.bucket, "Key": full_key, "Body": io.BytesIO(data)}
        if content_type:
            kwargs["ContentType"] = content_type
        try:
            self.client.put_object(**kwargs)
            return True
        except Exception as exc:
            logger.warning("S3 put_object failed for %s: %s", full_key, exc)
            return False

    def load(self, key: str) -> bytes:
        if not self._available or not self.client:
            raise FileNotFoundError("S3 client not available")
        full_key = self._full_key(key)
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=full_key)
            return response["Body"].read()
        except Exception as exc:
            raise FileNotFoundError(f"S3 key not found {full_key}: {exc}") from exc

    def delete(self, key: str) -> bool:
        if not self._available or not self.client:
            return False
        full_key = self._full_key(key)
        try:
            self.client.delete_object(Bucket=self.bucket, Key=full_key)
            return True
        except Exception as exc:
            logger.warning("S3 delete_object failed for %s: %s", full_key, exc)
            return False

    def exists(self, key: str) -> bool:
        if not self._available or not self.client:
            return False
        full_key = self._full_key(key)
        try:
            self.client.head_object(Bucket=self.bucket, Key=full_key)
            return True
        except Exception:
            return False


def get_storage(namespace: str = "business_uploads") -> StorageBackend:
    """Return configured storage backend. Falls back to LocalStorageBackend if S3 is unconfigured."""
    settings = get_settings()
    s3_bucket = getattr(settings, "s3_bucket", None)

    if s3_bucket:
        try:
            backend = S3StorageBackend(
                bucket=s3_bucket,
                region=getattr(settings, "s3_region", "us-east-1"),
                endpoint_url=getattr(settings, "s3_endpoint_url", None),
                access_key_id=getattr(settings, "s3_access_key_id", None),
                secret_access_key=getattr(settings, "s3_secret_access_key", None),
                prefix=namespace,
            )
            if backend._available:
                return backend
        except Exception as exc:
            logger.warning("Failed to initialize S3 storage for namespace '%s': %s. Falling back to local disk.", namespace, exc)

    # Local fallback
    if namespace == "research_uploads":
        base_path = getattr(settings, "research_data_path", "./data/research_uploads")
    else:
        base_path = getattr(settings, "business_upload_path", "./data/business_uploads")

    return LocalStorageBackend(base_path=base_path)

