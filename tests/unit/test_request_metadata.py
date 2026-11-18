"""Request-ID sanitising and timing header (no secrets, no request body in logs)."""
import logging


def test_a_safe_request_id_is_echoed_and_timing_is_reported(client):
    r = client.get("/api/v1/health", headers={"X-Request-ID": "trace-abc12345"})
    assert r.headers["X-Request-ID"] == "trace-abc12345"
    assert float(r.headers["X-Process-Time-Ms"]) >= 0


def test_an_unsafe_request_id_is_replaced(client):
    for bad in ("short", "x" * 200, "has space and \"quotes\" ; DROP", "with/slash/and:colon"):
        r = client.get("/api/v1/health", headers={"X-Request-ID": bad})
        rid = r.headers["X-Request-ID"]
        assert rid != bad and len(rid) == 36  # a fresh UUID


def test_the_access_log_carries_no_query_string_or_body(client, caplog):
    with caplog.at_level(logging.INFO, logger="decisiongpt.request"):
        client.get("/api/v1/health?secret=hunter2")
    rec = [r for r in caplog.records if r.name == "decisiongpt.request"]  # (the HTTP client's own log line is not ours)
    assert rec and rec[-1].path == "/api/v1/health"
    assert "hunter2" not in " ".join(f"{r.getMessage()} {r.__dict__}" for r in rec)
