"""Tenant boundaries of every tracking route (with real authorization), and the schema guarantees of migrations 0012 and 0013 on a
disposable database. Synthetic fixtures only."""
import io
import json
import os
import sqlite3
import subprocess
import sys
import uuid
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from app.models.tracking import OutcomeObservation, TrackedExpectation
from tests.api.test_platform_api import P, _owner, auth_on  # noqa: F401  (auth_on is a fixture)

PAST = {"window_start": "2026-01-08", "window_end": "2026-01-14"}


def _sales(client, bid, headers, days=80):
    rng = np.random.default_rng(3)
    rows = []
    for i in range(days):
        d = date.today() - timedelta(days=days - 1 - i)
        for p in range(3):
            q = max(1, int(round(7 + rng.normal(0, 1)))) + 20 * p
            rows.append({"Order Date": d.isoformat(), "Product Name": f"I{p}", "Quantity": q, "Unit Price": 100, "Revenue": q * 100})
    buf = io.StringIO()
    pd.DataFrame(rows).to_csv(buf, index=False)
    r = client.post(f"{P}/{bid}/data/upload?data_type=sales", files={"file": ("s.csv", buf.getvalue().encode(), "text/csv")}, headers=headers)
    assert r.json()["status"] == "completed", r.text


@pytest.fixture()
def world(client, db_session, auth_on):  # noqa: F811
    a, ha = _owner(client, "ta2@example.com", "Alpha")
    b, hb = _owner(client, "tb2@example.com", "Beta")
    # an expectation with a finished window and a distinctive observed value, created directly (no forecast needed)
    e = TrackedExpectation(business_id=a, source_kind="owner_plan", metric="units_sold", unit="units", scope="business_total",
                           window_start=date(2026, 1, 8), window_end=date(2026, 1, 14), horizon_days=7, expected_value=4242.0,
                           comparable_to_actuals=True, provenance="owner_entered", config_json={})
    db_session.add(e)
    db_session.commit()
    o = client.post(f"{P}/{a}/tracking/expectations/{e.id}/observations",
                    json={"metric": "units_sold", "unit": "units", "status": "observed", "value": 31337.0}, headers=ha)
    assert o.status_code == 200, o.text
    return client, db_session, (a, ha), (b, hb), str(e.id), o.json()["id"]


def _no_leak(resp, *secrets):
    text = resp.text
    for s in secrets:
        assert s not in text, f"{s} leaked in {text[:200]}"


def test_every_route_refuses_a_foreign_token_without_revealing_the_record(world):
    client, db, (a, ha), (b, hb), eid, oid = world
    calls = [
        ("get", f"/tracking/expectations/{eid}", None), ("get", "/tracking/expectations", None), ("get", "/tracking/report", None),
        ("get", "/tracking/decisions", None),
        ("post", f"/tracking/expectations/{eid}/observations", {"metric": "units_sold", "unit": "units", "status": "observed", "value": 1}),
        ("post", f"/tracking/observations/{oid}/correction", {"reason": "not mine", "value": 5}),
        ("post", f"/tracking/expectations/{eid}/observations/from-data", None),
        ("post", "/tracking/forecasts", {"horizon_days": 7}),
        ("post", "/tracking/expectations", {"metric": "units_sold", "unit": "units", "expected_value": 1, **PAST}),
    ]
    for method, path, body in calls:
        kw = {"json": body} if body is not None else {}
        r = getattr(client, method)(P + f"/{a}{path}", headers=hb, **kw)                      # b's token on a's business
        assert r.status_code in (403, 404), (path, r.status_code)
        _no_leak(r, "4242", "31337", eid, oid)
        assert getattr(client, method)(P + f"/{a}{path}", **kw).status_code == 401, path      # no token at all


def test_a_foreign_identifier_through_ones_own_business_route_is_not_found_and_changes_nothing(world):
    client, db, (a, ha), (b, hb), eid, oid = world
    for method, path, body in [
        ("get", f"/tracking/expectations/{eid}", None),
        ("post", f"/tracking/expectations/{eid}/observations", {"metric": "units_sold", "unit": "units", "status": "observed", "value": 7}),
        ("post", f"/tracking/observations/{oid}/correction", {"reason": "hijack", "value": 7}),
        ("post", f"/tracking/expectations/{eid}/observations/from-data", None),
    ]:
        kw = {"json": body} if body is not None else {}
        r = getattr(client, method)(P + f"/{b}{path}", headers=hb, **kw)                      # a's ids on b's own route
        assert r.status_code == 404, (path, r.status_code)
        assert r.json()["error"]["code"] == "NOT_FOUND"
        _no_leak(r, "4242", "31337")
    obs = db.query(OutcomeObservation).filter_by(expectation_id=eid).all()
    assert len(obs) == 1 and float(obs[0].value) == 31337.0 and obs[0].is_current and obs[0].revision == 1
    assert client.get(f"{P}/{b}/tracking/expectations", headers=hb).json() == {"expectations": []}


def test_the_client_cannot_name_a_tenant_in_the_body_or_headers(world):
    client, db, (a, ha), (b, hb), eid, oid = world
    body = {"metric": "units_sold", "unit": "units", "status": "observed", "value": 9, "business_id": a}
    assert client.post(f"{P}/{b}/tracking/expectations/{eid}/observations", json=body, headers=hb).status_code == 422       # extra field refused
    r = client.get(f"{P}/{b}/tracking/expectations/{eid}", headers={**hb, "X-Business-Id": a, "X-Tenant-Id": a})
    assert r.status_code == 404                                                                                              # headers are ignored
    r = client.post(f"{P}/{a}/tracking/forecasts?business_id={b}", json={"horizon_days": 7}, headers=hb)
    assert r.status_code in (403, 404)                                                                                       # path decides, not the query


def test_audit_history_is_as_private_as_the_current_record(world):
    client, db, (a, ha), (b, hb), eid, oid = world
    fixed = client.post(f"{P}/{a}/tracking/observations/{oid}/correction", json={"reason": "typo fix", "value": 31000.0}, headers=ha)
    assert fixed.status_code == 200 and fixed.json()["revision"] == 2
    mine = client.get(f"{P}/{a}/tracking/expectations/{eid}", headers=ha).json()
    assert [(x["revision"], x["value"], x["is_current"]) for x in mine["observations"]] == [(1, 31337.0, False), (2, 31000.0, True)]
    theirs = client.get(f"{P}/{a}/tracking/expectations/{eid}", headers=hb)
    assert theirs.status_code in (403, 404)
    _no_leak(theirs, "31337", "31000", "typo fix")
    report_b = client.get(f"{P}/{b}/tracking/report", headers=hb)
    _no_leak(report_b, "31337", "31000", "typo fix", eid)


def test_error_responses_never_echo_another_tenants_values(world):
    client, db, (a, ha), (b, hb), eid, oid = world
    r = client.post(f"{P}/{a}/tracking/expectations/{eid}/observations",
                    json={"metric": "units_sold", "unit": "units", "status": "observed", "value": 5}, headers=ha)
    assert r.status_code == 422 and "Submit a correction" in r.json()["error"]["message"]      # own record: a clear instruction
    r = client.post(f"{P}/{b}/tracking/observations/{oid}/correction", json={"reason": "x" * 5, "value": 1}, headers=hb)
    assert r.status_code == 404 and "31337" not in r.text and "4242" not in r.text


# ------------------------------------------------------------------ migrations
def _alembic(root: Path, env: dict, *args: str):
    return subprocess.run([sys.executable, "-m", "alembic", *args], cwd=root / "backend", env=env, capture_output=True, text=True, timeout=300)


def _insert_generic(con: sqlite3.Connection, table: str, **values):
    """Insert a row filling every NOT NULL column that has no default with a type-appropriate placeholder."""
    cols = con.execute(f"pragma table_info({table})").fetchall()
    row = dict(values)
    for _, name, ctype, notnull, default, _pk in cols:
        if name in row or not notnull or default is not None:
            continue
        t = (ctype or "").upper()
        row[name] = 0 if any(k in t for k in ("INT", "BOOL", "NUMERIC", "FLOAT")) else "2026-01-01" if "DATE" in t else "x"
    names = ", ".join(row)
    con.execute(f"insert into {table} ({names}) values ({', '.join('?' * len(row))})", list(row.values()))


def test_migrations_0012_and_0013_create_the_constraints_backfill_and_downgrade_cleanly(tmp_path):
    root = Path(__file__).resolve().parents[2]
    db = tmp_path / "m.db"
    env = {**os.environ, "DATABASE_URL": f"sqlite:///{db.as_posix()}", "MIGRATION_DATABASE_URL": f"sqlite:///{db.as_posix()}", "PYTHONPATH": str(root)}
    r = _alembic(root, env, "upgrade", "0012")
    assert r.returncode == 0, r.stderr[-800:]
    con = sqlite3.connect(db)
    idx = {n: u for (_s, n, u, *_r) in con.execute("pragma index_list(decision_responses)").fetchall()}
    assert idx.get("uq_decision_responses_decision_seq") == 1                                       # 0012: unique (decision, seq)
    oidx = {n: u for (_s, n, u, *_r) in con.execute("pragma index_list(outcome_observations)").fetchall()}
    assert oidx.get("uq_outcome_observations_current_window") == 1                                  # 0012: one current observation per window
    sql = con.execute("select sql from sqlite_master where name='uq_outcome_observations_current_window'").fetchone()[0]
    assert "WHERE" in sql.upper() and "is_current" in sql                                           # a partial index, not a blanket unique
    # data written at 0012: two forecast snapshots of one business sharing a fingerprint (the pre-0013 race), one with another fingerprint
    bid = str(uuid.uuid4())
    _insert_generic(con, "businesses", id=bid, created_at="2026-01-01", name="M", industry="i", business_type="t", business_size="s")
    fps = ["a" * 64, "a" * 64, "b" * 64]
    for k, fp in enumerate(fps):
        _insert_generic(con, "tracked_expectations", id=str(uuid.uuid4()), business_id=bid, created_at=f"2026-01-0{k + 1}T00:00:00", source_kind="forecast",
                        metric="units_sold", unit="units", scope="business_total", window_start="2026-02-01", window_end="2026-02-07",
                        horizon_days=7, comparable_to_actuals=1, provenance="x", config_json=json.dumps({"fingerprint": fp}))
    con.commit()
    con.close()
    r = _alembic(root, env, "upgrade", "head")
    assert r.returncode == 0, r.stderr[-800:]
    con = sqlite3.connect(db)
    rows = con.execute("select created_at, fingerprint from tracked_expectations order by created_at").fetchall()
    assert [fp for _, fp in rows] == ["a" * 64, None, "b" * 64]                                      # earliest keeps it; the duplicate stays readable
    assert len(rows) == 3                                                                           # nothing deleted or merged
    tidx = {n: u for (_s, n, u, *_r) in con.execute("pragma index_list(tracked_expectations)").fetchall()}
    assert tidx.get("uq_tracked_expectations_forecast_fingerprint") == 1
    # the database itself refuses a second snapshot with the same fingerprint for the business
    with pytest.raises(sqlite3.IntegrityError):
        _insert_generic(con, "tracked_expectations", id=str(uuid.uuid4()), business_id=bid, created_at="2026-02-01T00:00:00", source_kind="forecast",
                        metric="units_sold", unit="units", scope="business_total", window_start="2026-02-01", window_end="2026-02-07",
                        horizon_days=7, comparable_to_actuals=1, provenance="x", fingerprint="b" * 64)
    con.rollback()
    con.close()
    r = _alembic(root, env, "downgrade", "0011")
    assert r.returncode == 0, r.stderr[-800:]
    con = sqlite3.connect(db)
    cols = {c[1] for c in con.execute("pragma table_info(tracked_expectations)")}
    assert "fingerprint" not in cols and con.execute("select count(*) from tracked_expectations").fetchone()[0] == 3      # data kept
    con.close()


def test_migration_0014_makes_history_append_only_inside_the_database(tmp_path):
    """Raw SQL cannot edit a saved snapshot, a response, or anything of an observation except flipping a superseded revision's current flag;
    deletes (needed for ON DELETE CASCADE) and inserts still work. Exercised on SQLite; the PostgreSQL trigger code is not run here."""
    root = Path(__file__).resolve().parents[2]
    db = tmp_path / "t.db"
    env = {**os.environ, "DATABASE_URL": f"sqlite:///{db.as_posix()}", "MIGRATION_DATABASE_URL": f"sqlite:///{db.as_posix()}", "PYTHONPATH": str(root)}
    r = _alembic(root, env, "upgrade", "head")
    assert r.returncode == 0, r.stderr[-800:]
    con = sqlite3.connect(db)
    bid, eid, oid, did = (str(uuid.uuid4()) for _ in range(4))
    _insert_generic(con, "businesses", id=bid, created_at="2026-01-01", name="T", industry="i", business_type="t", business_size="s")
    _insert_generic(con, "tracked_expectations", id=eid, business_id=bid, created_at="2026-01-01T00:00:00", source_kind="owner_plan", metric="units_sold",
                    unit="units", scope="business_total", window_start="2026-02-01", window_end="2026-02-07", horizon_days=7,
                    expected_value=100, comparable_to_actuals=1, provenance="x", config_json="{}")
    _insert_generic(con, "outcome_observations", id=oid, business_id=bid, expectation_id=eid, created_at="2026-02-10T00:00:00", metric="units_sold",
                    unit="units", scope="business_total", window_start="2026-02-01", window_end="2026-02-07", value=90, status="observed",
                    window_days=7, source="owner_entered", provenance="owner_entered", revision=1, is_current=1)
    con.commit()
    for sql in ("update tracked_expectations set expected_value = 1",
                "update tracked_expectations set question = 'edited'",
                "update outcome_observations set value = 1",
                "update outcome_observations set status = 'invalid'",
                "update outcome_observations set is_current = 0, value = 1",       # a flip that also edits something else
                "update outcome_observations set revision_reason = 'x'"):
        with pytest.raises(sqlite3.DatabaseError, match="append-only"):
            con.execute(sql)
        con.rollback()
    # the one permitted change: a correction flips the current flag of the old revision (and only that)
    con.execute("update outcome_observations set is_current = 0 where id = ?", (oid,))
    con.commit()
    assert con.execute("select is_current, value from outcome_observations where id = ?", (oid,)).fetchone() == (0, 90)
    with pytest.raises(sqlite3.DatabaseError, match="append-only"):                 # and it cannot be flipped back
        con.execute("update outcome_observations set is_current = 1 where id = ?", (oid,))
    con.rollback()
    # inserts (new revisions) and deletes (business removal cascades) still work
    _insert_generic(con, "outcome_observations", id=str(uuid.uuid4()), business_id=bid, expectation_id=eid, created_at="2026-02-11T00:00:00",
                    metric="units_sold", unit="units", scope="business_total", window_start="2026-02-01", window_end="2026-02-07", value=95,
                    status="observed", window_days=7, source="owner_entered", provenance="owner_entered", revision=2, is_current=1, supersedes_id=oid)
    con.commit()
    con.execute("pragma foreign_keys = on")
    con.execute("delete from businesses where id = ?", (bid,))
    con.commit()
    assert con.execute("select count(*) from tracked_expectations").fetchone()[0] == 0
    con.close()
    r = _alembic(root, env, "downgrade", "0013")
    assert r.returncode == 0, r.stderr[-800:]
    con = sqlite3.connect(db)
    assert not con.execute("select name from sqlite_master where type='trigger'").fetchall()
    con.close()


def test_the_application_flows_still_work_on_a_database_with_the_triggers(tmp_path):
    """The legitimate paths (record, correct, respond, snapshot-style insert) must pass the database triggers, not only the ORM guard."""
    from datetime import date as _d

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.models.business import Business
    from app.models.decision import Decision
    from app.models.goal import Goal
    from app.models.tracking import TrackedExpectation as TE
    from app.services import outcome_tracking_service as svc

    root = Path(__file__).resolve().parents[2]
    db = tmp_path / "flows.db"
    env = {**os.environ, "DATABASE_URL": f"sqlite:///{db.as_posix()}", "MIGRATION_DATABASE_URL": f"sqlite:///{db.as_posix()}", "PYTHONPATH": str(root)}
    assert _alembic(root, env, "upgrade", "head").returncode == 0
    engine = create_engine(f"sqlite:///{db.as_posix()}", connect_args={"timeout": 30})
    with sessionmaker(bind=engine, autoflush=False)() as s:
        b = Business(name="Trg", industry="r", business_type="D2C", business_size="s")
        s.add(b)
        s.flush()
        g = Goal(business_id=b.id, objective="increase_revenue", target_value=1, target_unit="percent", primary_kpi="revenue")
        s.add(g)
        s.flush()
        dec = Decision(business_id=b.id, goal_id=g.id, risk_level="low", expected_outcome_json={})
        e = TE(business_id=b.id, source_kind="owner_plan", metric="units_sold", unit="units", scope="business_total", window_start=_d(2026, 1, 8),
               window_end=_d(2026, 1, 14), horizon_days=7, expected_value=100, comparable_to_actuals=True, provenance="owner_entered", config_json={})
        s.add_all([dec, e])
        s.commit()
        bid, eid, did = str(b.id), str(e.id), str(dec.id)
        o = svc.record_observation(s, bid, eid, metric="units_sold", unit="units", status="observed", value=90.0, actor="t")
        fixed = svc.correct_observation(s, bid, str(o.id), reason="till report", value=95.0, actor="t")
        assert fixed.revision == 2 and fixed.is_current
        r1 = svc.record_response(s, bid, did, response="accepted", actor="t")
        r2 = svc.record_response(s, bid, did, response="accepted", action_status="executed", action_start=_d.today(), actor="t")
        assert (r1.seq, r2.seq) == (1, 2)
        assert [x.is_current for x in svc.observations_of(s, bid, eid)] == [False, True]
    engine.dispose()
