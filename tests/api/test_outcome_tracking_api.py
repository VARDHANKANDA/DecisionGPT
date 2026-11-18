"""Outcome tracking through the API: authentication, tenant isolation, strict inputs, safe empty state and migration compatibility."""
import io
import os
import sqlite3
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from tests.api.test_platform_api import P, _owner, auth_on  # noqa: F401  (auth_on is a fixture)


def _upload(client, bid, headers, days=90):
    rng = np.random.default_rng(2)
    rows = []
    for i in range(days):
        d = date.today() - timedelta(days=days - 1 - i)
        for p in range(3):
            q = max(1, int(round(7 + rng.normal(0, 1)))) + 20 * p
            rows.append({"Order Date": d.isoformat(), "Product Name": f"I{p}", "Quantity": q, "Unit Price": 100, "Revenue": q * 100})
    buf = io.StringIO()
    pd.DataFrame(rows).to_csv(buf, index=False)
    r = client.post(f"{P}/{bid}/data/upload?data_type=sales", files={"file": ("sales.csv", buf.getvalue().encode(), "text/csv")}, headers=headers)
    assert r.json()["status"] == "completed", r.text


@pytest.fixture()
def world(client, db_session, auth_on):  # noqa: F811
    a, ha = _owner(client, "ta@example.com", "Alpha")
    b, hb = _owner(client, "tb@example.com", "Beta")
    return client, db_session, (a, ha), (b, hb)


def test_every_tracking_route_needs_a_token_and_the_right_business(world):
    client, _, (a, ha), (b, hb) = world
    _upload(client, a, ha)
    exp = client.post(f"{P}/{a}/tracking/forecasts", json={"horizon_days": 7}, headers=ha)
    assert exp.status_code == 200, exp.text
    eid = exp.json()["id"]
    paths = [("get", "/tracking/report"), ("get", "/tracking/expectations"), ("get", f"/tracking/expectations/{eid}"),
             ("post", "/tracking/forecasts"), ("post", f"/tracking/expectations/{eid}/observations/from-data")]
    for method, path in paths:
        kw = {"json": {"horizon_days": 7}} if path.endswith("/forecasts") else {}
        call = getattr(client, method)
        assert call(P + f"/{a}{path}", **kw).status_code == 401                              # no token
        assert call(P + f"/{a}{path}", headers=hb, **kw).status_code in (403, 404)            # another owner's token
    # an expectation id from another tenant is not reachable through one's own business route
    assert client.get(f"{P}/{b}/tracking/expectations/{eid}", headers=hb).status_code == 404
    assert client.post(f"{P}/{b}/tracking/expectations/{eid}/observations",
                       json={"metric": "units_sold", "unit": "units", "status": "invalid", "unavailable_reason": "x"}, headers=hb).status_code == 404
    assert client.get(f"{P}/{b}/tracking/expectations", headers=hb).json()["expectations"] == []
    assert client.get(f"{P}/{b}/tracking/report", headers=hb).json()["expectations"]["recorded"] == 0


def test_inputs_are_strict_and_units_are_required(world):
    client, _, (a, ha), _ = world
    _upload(client, a, ha)
    eid = client.post(f"{P}/{a}/tracking/forecasts", json={"horizon_days": 7}, headers=ha).json()["id"]
    obs = f"{P}/{a}/tracking/expectations/{eid}/observations"
    assert client.post(obs, json={"metric": "units_sold", "status": "observed", "value": 5}, headers=ha).status_code == 422       # unit missing
    assert client.post(obs, json={"metric": "units_sold", "unit": "units", "status": "observed", "value": 5, "extra": 1}, headers=ha).status_code == 422
    assert client.post(obs, json={"metric": "profit", "unit": "INR", "status": "observed", "value": 5}, headers=ha).status_code == 422
    assert client.post(obs, json={"metric": "units_sold", "unit": "units", "status": "observed", "value": "abc"}, headers=ha).status_code == 422
    assert client.post(obs, json={"metric": "units_sold", "unit": "units", "status": "observed"}, headers=ha).status_code == 422     # no value
    assert client.post(f"{P}/{a}/tracking/forecasts", json={"horizon_days": 400}, headers=ha).status_code == 422
    assert client.post(f"{P}/{a}/tracking/expectations", json={"metric": "marketing_spend", "unit": "kg", "window_start": "2026-01-01",
                                                                "window_end": "2026-01-07", "expected_value": 10}, headers=ha).status_code == 422


def test_the_full_owner_workflow_over_the_api(world):
    client, _, (a, ha), _ = world
    _upload(client, a, ha)
    eid = client.post(f"{P}/{a}/tracking/forecasts", json={"horizon_days": 7, "question": "next week?"}, headers=ha).json()["id"]
    # the window has not started: the derived observation is pending with no value, not zero
    d = client.post(f"{P}/{a}/tracking/expectations/{eid}/observations/from-data", headers=ha).json()
    assert d["status"] == "pending" and d["value"] is None
    full = client.get(f"{P}/{a}/tracking/expectations/{eid}", headers=ha).json()
    assert full["comparison"]["status"] == "excluded" and len(full["observations"]) == 1
    rep = client.get(f"{P}/{a}/tracking/report", headers=ha).json()
    assert rep["observations"]["by_status"]["pending"] == 1 and rep["business_impact"]["status"] == "not_evaluable"
    assert rep["forecast_accuracy"]["sample_size"] == 0


def test_empty_state_is_safe(world):
    client, _, (a, ha), _ = world
    rep = client.get(f"{P}/{a}/tracking/report", headers=ha)
    assert rep.status_code == 200
    j = rep.json()
    assert j["decisions"]["recorded"] == 0 and j["comparisons"]["details"] == [] and "cannot yet be summarised" in j["forecast_accuracy"]["statement"]
    assert client.get(f"{P}/{a}/tracking/expectations", headers=ha).json() == {"expectations": []}
    assert client.post(f"{P}/{a}/tracking/forecasts", json={"horizon_days": 7}, headers=ha).status_code == 422     # no sales: explained, not invented


def test_migration_0011_upgrades_a_0010_database_and_downgrades_cleanly(tmp_path):
    root = Path(__file__).resolve().parents[2]
    db = tmp_path / "m.db"
    env = {**os.environ, "DATABASE_URL": f"sqlite:///{db.as_posix()}", "PYTHONPATH": str(root)}

    def alembic(*args):
        return subprocess.run([sys.executable, "-m", "alembic", *args], cwd=root / "backend", env=env, capture_output=True, text=True, timeout=300)

    r = alembic("upgrade", "0010")
    assert r.returncode == 0, r.stderr[-800:]
    con = sqlite3.connect(db)
    tables = {t for (t,) in con.execute("select name from sqlite_master where type='table'")}
    assert "tracked_expectations" not in tables and "decisions" in tables
    con.close()
    r = alembic("upgrade", "head")
    assert r.returncode == 0, r.stderr[-800:]
    con = sqlite3.connect(db)
    tables = {t for (t,) in con.execute("select name from sqlite_master where type='table'")}
    assert {"tracked_expectations", "decision_responses", "outcome_observations"} <= tables
    cols = {c[1] for c in con.execute("pragma table_info(outcome_observations)")}
    assert {"value", "status", "revision", "supersedes_id", "is_current", "window_start", "window_end", "unit"} <= cols
    con.close()
    r = alembic("downgrade", "0010")
    assert r.returncode == 0, r.stderr[-800:]
    con = sqlite3.connect(db)
    assert "tracked_expectations" not in {t for (t,) in con.execute("select name from sqlite_master where type='table'")}
    con.close()
