"""Concurrency and idempotency of the tracking records, against a FILE-backed SQLite database with a separate session per request or
thread (the shared in-memory test database cannot race). The assertions are database invariants that must hold for every interleaving,
plus deterministic forced interleavings through barriers. Synthetic fixtures only."""
import threading
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.errors import ConflictError, ValidationFailedError
from app.db.session import Base, get_db
from app.main import app as fastapi_app
from app.models.business import Business
from app.models.decision import Decision
from app.models.goal import Goal
from app.models.sale import Sale
from app.models.tracking import DecisionResponse, OutcomeObservation, TrackedExpectation
from app.services import outcome_tracking_service as svc
from tests import pg_support

PAST_START = date(2026, 1, 8)          # a window that is already over relative to any real run date
PAST_END = date(2026, 1, 14)
CUTOFF = date(2026, 1, 7)


@pytest.fixture()
def race(tmp_path):
    urls = pg_support.shared_urls()
    if urls:        # the same scenarios against real PostgreSQL (migrated schema, least-privilege role, genuinely parallel writers)
        pg_support.reset_data(urls[1])
        engine = create_engine(urls[0], pool_size=24, max_overflow=24)
    else:
        engine = create_engine(f"sqlite:///{(tmp_path / 'race.db').as_posix()}", connect_args={"check_same_thread": False, "timeout": 60})
        Base.metadata.create_all(engine)
        with engine.connect() as c0:                   # WAL: readers keep their snapshot while a writer commits (the production-like read behaviour)
            c0.exec_driver_sql("PRAGMA journal_mode=WAL")
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    with Session() as s:
        b = Business(name="Race Co", industry="retail", business_type="D2C", business_size="small")
        s.add(b)
        s.flush()
        bid = str(b.id)
        for i in range(120):
            d = date(2026, 1, 7) - timedelta(days=119 - i)
            for p in range(3):
                q = 7 + (3 if d.weekday() >= 5 else 0) + 20 * p + (i % 3)
                s.add(Sale(business_id=bid, sale_date=d, quantity=q, unit_price=100, discount=0, revenue=q * 100))
        g = Goal(business_id=bid, objective="increase_revenue", target_value=10, target_unit="percent", primary_kpi="revenue")
        s.add(g)
        s.flush()
        dec = Decision(business_id=bid, goal_id=g.id, risk_level="low", expected_outcome_json={})
        s.add(dec)
        exp = TrackedExpectation(business_id=bid, source_kind="forecast", metric="units_sold", unit="units", scope="business_total",
                                 window_start=PAST_START, window_end=PAST_END, horizon_days=7, data_cutoff=CUTOFF, expected_value=100.0,
                                 comparable_to_actuals=True, config_json={"cutoff_provenance": "recorded"}, provenance="owner_entered")
        s.add(exp)
        s.commit()
        ids = {"business": bid, "decision": str(dec.id), "expectation": str(exp.id)}

    def override():
        s = Session()
        try:
            yield s
        finally:
            s.close()

    fastapi_app.dependency_overrides[get_db] = override
    yield {"Session": Session, **ids}
    fastapi_app.dependency_overrides.clear()
    engine.dispose()


def run_threads(n, fn):
    """Start ``n`` threads released together; return their results (exceptions are returned, not raised)."""
    barrier = threading.Barrier(n, timeout=30)
    out: list = [None] * n

    def work(i):
        try:
            barrier.wait()
            out[i] = fn(i)
        except BaseException as exc:  # noqa: BLE001 - the test inspects every outcome
            out[i] = exc

    ts = [threading.Thread(target=work, args=(i,)) for i in range(n)]
    for t in ts:
        t.start()
    for t in ts:
        t.join(timeout=120)
    return out


# ------------------------------------------------------------------ 1. simultaneous snapshot saves of the same forecast
def test_simultaneous_saves_of_the_same_forecast_create_exactly_one_snapshot(race):
    bid = race["business"]
    c0 = TestClient(fastapi_app)
    shown = c0.post(f"/api/v1/businesses/{bid}/analytics/forecast?horizon_days=7").json()

    def save(i):
        return TestClient(fastapi_app).post(f"/api/v1/businesses/{bid}/tracking/forecasts",
                                            json={"horizon_days": 7, "fingerprint": shown["fingerprint"]})

    results = run_threads(6, save)
    assert all(not isinstance(r, BaseException) for r in results), results
    assert [r.status_code for r in results] == [200] * 6, [r.text for r in results if r.status_code != 200]
    created = [r.json()["already_saved"] for r in results]
    assert created.count(False) == 1 and created.count(True) == 5
    assert len({r.json()["id"] for r in results}) == 1
    with race["Session"]() as s:
        assert s.query(TrackedExpectation).filter_by(business_id=bid, fingerprint=shown["fingerprint"]).count() == 1


def test_a_lost_insert_race_returns_the_winner_not_an_error(race, monkeypatch):
    bid = race["business"]
    with race["Session"]() as s1:
        first, _ = svc.save_forecast_snapshot(s1, bid, 7)
    real = svc._snapshot_by_fingerprint
    calls = {"n": 0}

    def blind_once(db, b, fp):                      # the second request looked before the first had committed
        calls["n"] += 1
        return None if calls["n"] == 1 else real(db, b, fp)

    monkeypatch.setattr(svc, "_snapshot_by_fingerprint", blind_once)
    with race["Session"]() as s2:
        second, info = svc.save_forecast_snapshot(s2, bid, 7)
    assert info["already_saved"] is True and second.id == first.id
    with race["Session"]() as s3:
        assert s3.query(TrackedExpectation).filter_by(business_id=bid, fingerprint=first.fingerprint).count() == 1


# ------------------------------------------------------------------ 2. concurrent responses to one decision
def test_forced_interleaving_of_two_responses_yields_one_revision_and_a_conflict(race, monkeypatch):
    bid, did = race["business"], race["decision"]
    barrier = threading.Barrier(2, timeout=30)
    real = svc.current_response
    seen = threading.local()

    def read_then_wait(db, b, d):
        r = real(db, b, d)
        if not getattr(seen, "waited", False):      # only the first read of each request: both have read the same state before either writes
            seen.waited = True
            barrier.wait()
        return r

    monkeypatch.setattr(svc, "current_response", read_then_wait)

    def respond(i):
        with race["Session"]() as s:
            return svc.record_response(s, bid, did, response=("accepted", "rejected")[i], actor=f"user{i}")

    out = run_threads(2, respond)
    wins = [o for o in out if isinstance(o, DecisionResponse)]
    losses = [o for o in out if isinstance(o, ConflictError)]
    assert len(wins) == 1 and len(losses) == 1, out
    assert "same moment" in losses[0].message
    monkeypatch.setattr(svc, "current_response", real)
    with race["Session"]() as s:
        rows = s.query(DecisionResponse).filter_by(decision_id=did).all()
        assert [r.seq for r in rows] == [1] and rows[0].response == wins[0].response


def test_many_simultaneous_responses_never_corrupt_the_history(race):
    bid, did = race["business"], race["decision"]
    choices = [dict(response="accepted"), dict(response="rejected", action_status="not_executed"), dict(response="deferred", action_status="not_executed"),
               dict(response="accepted", note="a"), dict(response="rejected", action_status="not_executed", note="b"), dict(response="deferred", action_status="not_executed", note="c")]

    def respond(i):
        c = TestClient(fastapi_app)
        return c.post(f"/api/v1/businesses/{bid}/tracking/decisions/{did}/response", json=choices[i])

    out = run_threads(6, respond)
    assert all(not isinstance(o, BaseException) for o in out), out
    assert {o.status_code for o in out} <= {200, 409, 422}, [(o.status_code, o.text[:80]) for o in out]
    assert any(o.status_code == 200 for o in out)
    with race["Session"]() as s:
        rows = s.query(DecisionResponse).filter_by(decision_id=did).order_by(DecisionResponse.seq).all()
        assert [r.seq for r in rows] == list(range(1, len(rows) + 1))            # unique and contiguous
        assert len(rows) == sum(o.status_code == 200 for o in out)
        for r in rows:                                                           # no row contradicts itself
            assert not (r.action_status in ("executed", "partially_executed") and r.response not in ("accepted", "modified"))
            assert r.response != "rejected" or r.action_status in ("unknown", "not_executed")


# ------------------------------------------------------------------ 3/4. observations: repeated, concurrent corrections
def test_the_same_observation_submitted_simultaneously_is_recorded_once(race):
    bid, eid = race["business"], race["expectation"]

    def submit(i):
        with race["Session"]() as s:
            return svc.record_observation(s, bid, eid, metric="units_sold", unit="units", status="observed", value=111.0, actor="retry")

    out = run_threads(5, submit)
    ok = [o for o in out if isinstance(o, OutcomeObservation)]
    rest = [o for o in out if not isinstance(o, OutcomeObservation)]
    assert len(ok) == 1, out
    assert all(isinstance(o, ValidationFailedError) and "already recorded" in o.message for o in rest), rest
    with race["Session"]() as s:
        assert s.query(OutcomeObservation).filter_by(expectation_id=eid).count() == 1


def test_a_different_value_submitted_after_the_first_is_a_conflict_that_asks_for_a_correction(race):
    bid, eid = race["business"], race["expectation"]
    with race["Session"]() as s:
        svc.record_observation(s, bid, eid, metric="units_sold", unit="units", status="observed", value=111.0, actor="o")
    with race["Session"]() as s:
        with pytest.raises(ValidationFailedError, match="Submit a correction"):
            svc.record_observation(s, bid, eid, metric="units_sold", unit="units", status="observed", value=222.0, actor="o")


def test_simultaneous_corrections_of_one_observation_yield_one_new_revision(race):
    bid, eid = race["business"], race["expectation"]
    with race["Session"]() as s:
        first = svc.record_observation(s, bid, eid, metric="units_sold", unit="units", status="observed", value=100.0, actor="o")
        first_id = str(first.id)

    def correct(i):
        with race["Session"]() as s:
            return svc.correct_observation(s, bid, first_id, reason=f"correction {i}", value=200.0 + i, actor=f"user{i}")

    out = run_threads(4, correct)
    ok = [o for o in out if isinstance(o, OutcomeObservation)]
    refused = [o for o in out if isinstance(o, (ConflictError, ValidationFailedError))]
    assert len(ok) == 1 and len(ok) + len(refused) == 4, out
    with race["Session"]() as s:
        revs = s.query(OutcomeObservation).filter_by(expectation_id=eid).order_by(OutcomeObservation.revision).all()
        assert [(r.revision, r.is_current) for r in revs] == [(1, False), (2, True)]     # one current revision, history intact
        assert float(revs[0].value) == 100.0 and revs[1].supersedes_id == revs[0].id


def test_forced_interleaving_of_two_corrections_is_a_conflict_not_two_current_rows(race, monkeypatch):
    bid, eid = race["business"], race["expectation"]
    with race["Session"]() as s:
        first_id = str(svc.record_observation(s, bid, eid, metric="units_sold", unit="units", status="observed", value=100.0, actor="o").id)
    barrier = threading.Barrier(2, timeout=30)
    real = svc._validated_fields
    seen = threading.local()

    def meet_after_reading(*a, **k):
        if not getattr(seen, "waited", False):
            seen.waited = True
            barrier.wait()                          # both requests have loaded the same CURRENT revision before either writes
        return real(*a, **k)

    monkeypatch.setattr(svc, "_validated_fields", meet_after_reading)

    def correct(i):
        with race["Session"]() as s:
            return svc.correct_observation(s, bid, first_id, reason=f"fix {i}", value=300.0 + i, actor=f"u{i}")

    out = run_threads(2, correct)
    monkeypatch.setattr(svc, "_validated_fields", real)
    ok = [o for o in out if isinstance(o, OutcomeObservation)]
    bad = [o for o in out if isinstance(o, BaseException)]
    assert len(ok) == 1 and len(bad) == 1, out
    assert isinstance(bad[0], ConflictError) and "same moment" in bad[0].message, bad
    with race["Session"]() as s:
        cur = s.query(OutcomeObservation).filter_by(expectation_id=eid, is_current=True).all()
        assert len(cur) == 1 and cur[0].revision == 2
        assert s.query(OutcomeObservation).filter_by(expectation_id=eid).count() == 2          # the loser left nothing behind


# ------------------------------------------------------------------ 5. reads during corrections
def test_report_reads_during_corrections_are_always_internally_consistent(race):
    bid, eid = race["business"], race["expectation"]
    with race["Session"]() as s:
        first_id = str(svc.record_observation(s, bid, eid, metric="units_sold", unit="units", status="observed", value=100.0, actor="o").id)
    values = [100.0]
    stop = threading.Event()
    errors: list = []

    def writer():
        current = first_id
        for k in range(1, 9):
            v = 100.0 + 10 * k
            try:
                with race["Session"]() as s:
                    new = svc.correct_observation(s, bid, current, reason=f"revision {k}", value=v, actor="w")
                    current = str(new.id)
                    values.append(v)
            except BaseException as exc:  # noqa: BLE001
                errors.append(exc)
        stop.set()

    seen: list = []

    def reader():
        c = TestClient(fastapi_app)
        while not stop.is_set():
            r = c.get(f"/api/v1/businesses/{bid}/tracking/report")
            seen.append((r.status_code, r.json() if r.status_code == 200 else None))

    w = threading.Thread(target=writer)
    rs = [threading.Thread(target=reader) for _ in range(2)]
    for t in rs + [w]:
        t.start()
    for t in [w] + rs:
        t.join(timeout=180)
    assert not errors, errors
    assert seen and all(code == 200 for code, _ in seen)
    allowed = set(values)
    for _, rep in seen:
        details = rep["comparisons"]["details"]
        assert len(details) == 1                                              # the one expectation, never zero or two rows for it
        d = details[0]
        assert d["status"] == "evaluated" and d["observed"] in allowed        # a real revision, never a half-written one, never missing
        assert rep["observations"]["by_status"]["observed"] == 1             # exactly one current observation at every instant


# ------------------------------------------------------------------ 6. one consistent snapshot for reports
def test_a_read_snapshot_does_not_see_commits_made_while_it_is_open(race):
    from app.db.snapshot import read_snapshot

    with race["Session"]() as reader:
        outside_before = reader.query(TrackedExpectation).count()
        with read_snapshot(reader):
            before = reader.query(TrackedExpectation).count()
            with race["Session"]() as writer:                                   # another connection commits in the middle
                writer.add(TrackedExpectation(business_id=race["business"], source_kind="owner_plan", metric="units_sold", unit="units", scope="business_total",
                                              window_start=PAST_START, window_end=PAST_END, horizon_days=7, expected_value=1, comparable_to_actuals=True,
                                              config_json={}, provenance="owner_entered"))
                writer.commit()
            during = reader.query(TrackedExpectation).count()
        after = reader.query(TrackedExpectation).count()
    assert outside_before == before == during == 1                              # one moment for every statement inside the snapshot
    assert after == 2                                                           # outside it, the commit is visible as usual


def test_the_report_describes_the_state_at_its_start_even_if_a_correction_commits_midway(race):
    from sqlalchemy import event

    bid, eid = race["business"], race["expectation"]
    with race["Session"]() as s:
        first = svc.record_observation(s, bid, eid, metric="units_sold", unit="units", status="observed", value=100.0, actor="o")
        first_id = str(first.id)
    engine = race["Session"].kw["bind"]
    state = {"armed": True, "busy": False}

    def correct_midway(conn, cursor, statement, params, context, executemany):
        if state["armed"] and not state["busy"] and "FROM outcome_observations" in statement and statement.lstrip().upper().startswith("SELECT"):
            state["busy"] = True                                               # the writer's own statements must not re-trigger the hook
            with race["Session"]() as w:
                svc.correct_observation(w, bid, first_id, reason="changed while the report runs", value=200.0, actor="w")
            state["armed"] = False
            state["busy"] = False

    event.listen(engine, "before_cursor_execute", correct_midway)
    try:
        with race["Session"]() as s:
            rep = svc.report(s, bid)
    finally:
        event.remove(engine, "before_cursor_execute", correct_midway)
    (d,) = rep["comparisons"]["details"]
    assert d["observed"] == 100.0 and rep["observations"]["by_status"]["observed"] == 1       # the state when the report began, internally consistent
    with race["Session"]() as s:
        assert svc.report(s, bid)["comparisons"]["details"][0]["observed"] == 200.0          # a report started afterwards sees the correction


def test_the_report_never_counts_an_observation_whose_expectation_it_does_not_list(race):
    """Defence for engines without snapshot isolation: orphaned current observations are ignored, so counts always reconcile."""
    bid = race["business"]
    with race["Session"]() as s:
        rep = svc._report(s, bid)
    assert sum(rep["observations"]["by_status"].values()) <= rep["expectations"]["recorded"]


def test_control_without_the_snapshot_the_report_reads_a_later_moment_midway(race):
    """Negative control for the test above: the unwrapped report body, with the same mid-report correction, shows the corrected value, so
    the snapshot (not luck) is what makes the report describe a single moment."""
    from sqlalchemy import event

    bid, eid = race["business"], race["expectation"]
    with race["Session"]() as s:
        first_id = str(svc.record_observation(s, bid, eid, metric="units_sold", unit="units", status="observed", value=100.0, actor="o").id)
    engine = race["Session"].kw["bind"]
    state = {"armed": True, "busy": False}

    def correct_midway(conn, cursor, statement, params, context, executemany):
        if state["armed"] and not state["busy"] and "FROM outcome_observations" in statement and statement.lstrip().upper().startswith("SELECT"):
            state["busy"] = True
            with race["Session"]() as w:
                svc.correct_observation(w, bid, first_id, reason="midway", value=200.0, actor="w")
            state["armed"], state["busy"] = False, False

    event.listen(engine, "before_cursor_execute", correct_midway)
    try:
        with race["Session"]() as s:
            rep = svc._report(s, bid)
    finally:
        event.remove(engine, "before_cursor_execute", correct_midway)
    assert rep["comparisons"]["details"][0]["observed"] == 200.0

