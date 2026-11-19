import os
import pytest
from app.services.storage_service import LocalStorageBackend, S3StorageBackend, get_storage


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
    # Without s3_bucket configured, get_storage returns LocalStorageBackend
    backend = get_storage("business_uploads")
    assert isinstance(backend, LocalStorageBackend)

