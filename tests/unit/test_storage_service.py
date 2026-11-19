import os
from unittest.mock import MagicMock, patch
import pytest

from app.core.config import get_settings
from app.services.storage_service import (
    LocalStorageBackend,
    SupabaseStorageBackend,
    get_storage,
)


def test_local_storage_backend_save_load_delete(tmp_path):
    storage = LocalStorageBackend(base_path=tmp_path)
    key = "business/123/original.csv"
    data = b"col1,col2\nval1,val2\n"

    # Save
    assert storage.save(key, data) is True
    assert storage.exists(key) is True

    # Load
    loaded = storage.load(key)
    assert loaded == data

    # Delete
    assert storage.delete(key) is True
    assert storage.exists(key) is False

    # Load deleted should raise FileNotFoundError
    with pytest.raises(FileNotFoundError):
        storage.load(key)


def test_local_storage_traversal_prevention(tmp_path):
    storage = LocalStorageBackend(base_path=tmp_path)
    # Attempt path traversal
    with pytest.raises(ValueError, match="Path traversal"):
        storage.load("../../../etc/passwd")


def test_get_storage_fallback():
    # Without supabase credentials configured, get_storage returns LocalStorageBackend
    backend = get_storage("business_uploads")
    assert isinstance(backend, LocalStorageBackend)


def test_supabase_storage_backend_operations():
    mock_client = MagicMock()
    mock_bucket = MagicMock()
    mock_client.storage.from_.return_value = mock_bucket

    mock_bucket.upload.return_value = {"Key": "business_uploads/test.csv"}
    mock_bucket.download.return_value = b"test,data\n1,2\n"
    mock_bucket.remove.return_value = [{"name": "test.csv"}]
    mock_bucket.list.return_value = [{"name": "test.csv"}]

    with patch("supabase.create_client", return_value=mock_client):
        backend = SupabaseStorageBackend(
            url="https://xyzcompany.supabase.co",
            service_role_key="mock-service-role-key-12345",
            bucket="decisiongpt-storage",
            prefix="business_uploads",
        )

        assert backend._available is True

        # Test save
        assert backend.save("test.csv", b"test,data\n1,2\n", content_type="text/csv") is True
        mock_bucket.upload.assert_called_once_with(
            path="business_uploads/test.csv",
            file=b"test,data\n1,2\n",
            file_options={"upsert": "true", "content-type": "text/csv"},
        )

        # Test load
        content = backend.load("test.csv")
        assert content == b"test,data\n1,2\n"
        mock_bucket.download.assert_called_once_with("business_uploads/test.csv")

        # Test exists
        assert backend.exists("test.csv") is True

        # Test delete
        assert backend.delete("test.csv") is True
        mock_bucket.remove.assert_called_once_with(["business_uploads/test.csv"])


def test_supabase_storage_load_missing_raises_filenotfound():
    mock_client = MagicMock()
    mock_bucket = MagicMock()
    mock_client.storage.from_.return_value = mock_bucket
    mock_bucket.download.side_effect = Exception("Object not found")
    mock_bucket.list.return_value = []

    with patch("supabase.create_client", return_value=mock_client):
        backend = SupabaseStorageBackend(
            url="https://xyzcompany.supabase.co",
            service_role_key="mock-service-role-key-12345",
            bucket="decisiongpt-storage",
            prefix="business_uploads",
        )

        with pytest.raises(FileNotFoundError):
            backend.load("nonexistent.csv")

        assert backend.exists("nonexistent.csv") is False
