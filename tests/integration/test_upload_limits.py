"""Upload resource limits: oversized files and files with too many rows are rejected with a clear, user-facing message; nothing is stored."""
import pandas as pd
import pytest

from app.core.config import get_settings
from tests.integration.test_analytics import _create_business


def _upload(client, bid, df, name="sales.csv"):
    return client.post(f"/api/v1/businesses/{bid}/data/upload?data_type=sales",
                       files={"file": (name, df.to_csv(index=False).encode(), "text/csv")})


def _sales(n):
    days = pd.date_range("2025-01-01", periods=n).strftime("%Y-%m-%d")
    return pd.DataFrame({"Order Date": days, "Product Name": [f"P{i % 7}" for i in range(n)], "Quantity": [1 + i % 3 for i in range(n)],
                         "Unit Price": [10 + i % 5 for i in range(n)], "Revenue": [(1 + i % 3) * (10 + i % 5) for i in range(n)]})


def test_a_file_over_the_size_limit_is_rejected_with_a_clear_message(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "max_upload_bytes", 2000)
    bid = _create_business(client)
    r = _upload(client, bid, _sales(500))
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "failed" and "larger than" in body["error_message"] and "Split it" in body["error_message"]
    lib = client.get(f"/api/v1/businesses/{bid}/data/library").json()
    assert all((t["rows"] or 0) == 0 for t in lib)  # nothing was stored


def test_a_file_over_the_row_limit_is_rejected_and_stores_nothing(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "max_upload_rows", 50)
    bid = _create_business(client)
    body = _upload(client, bid, _sales(120)).json()
    assert body["status"] == "failed" and "more rows than the limit of 50" in body["error_message"]
    lib = client.get(f"/api/v1/businesses/{bid}/data/library").json()
    assert all((t["rows"] or 0) == 0 for t in lib)


def test_a_file_within_the_limits_still_ingests(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "max_upload_rows", 50)
    bid = _create_business(client)
    body = _upload(client, bid, _sales(30)).json()
    assert body["status"] == "completed", body
