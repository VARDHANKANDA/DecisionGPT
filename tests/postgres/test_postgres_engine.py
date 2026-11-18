"""Behaviour that only a real PostgreSQL can show: the migration path, schema = models, indexes, append-only triggers under the
least-privilege role, privileges, transaction isolation, rollback, parallel writers, and the shared rate limiter. Every statement runs as the
least-privilege application role created by deploy/postgres/app-role.sql unless the test says it is using the owner."""
import threading
import uuid
from datetime import date

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError, IntegrityError, ProgrammingError
from sqlalchemy.orm import sessionmaker

from app.db.snapshot import read_snapshot
from app.models.business import Business
from app.models.decision import Decision
from app.models.goal import Goal
from app.models.tracking import DecisionResponse, OutcomeObservation, TrackedExpectation
from app.services import outcome_tracking_service as svc
from app.services import rate_limit_service as limiter
from tests.pg_support import run_alembic


def _seed(engine) -> dict:
    """A business with a goal, a decision, a saved snapshot, a response and a current observation."""
    Session = sessionmaker(bind=engine, autoflush=False)
    with Session() as s:
        b = Business(name="PG Co", industry="retail", business_type="D2C", business_size="small")
        s.add(b)
        s.flush()
        g = Goal(business_id=b.id, objective="increase_revenue", target_value=10, target_unit="percent", primary_kpi="revenue")
        s.add(g)
        s.flush()
        d = Decision(business_id=b.id, goal_id=g.id, risk_level="low", expected_outcome_json={})
        s.add(d)
        e = TrackedExpectation(business_id=b.id, source_kind="forecast", metric="units_sold", unit="units", scope="business_total",
                               window_start=date(2026, 1, 8), window_end=date(2026, 1, 14), horizon_days=7, data_cutoff=date(2026, 1, 7),
                               expected_value=100.0, comparable_to_actuals=True, config_json={}, provenance="owner_entered", fingerprint="fp-1")
        s.add(e)
        s.flush()
        s.add(DecisionResponse(business_id=b.id, decision_id=d.id, seq=1, response="accepted", action_status="unknown"))
        s.commit()
        ids = {"business": str(b.id), "decision": str(d.id), "expectation": str(e.id)}
        o = svc.record_observation(s, ids["business"], ids["expectation"], metric="units_sold", unit="units", status="observed", value=100.0, actor="o")
        ids["observation"] = str(o.id)
    return ids


# ------------------------------------------------------------------ migration path
def test_each_revision_applies_in_order_and_the_schema_equals_the_models(blank):
    out = run_alembic(blank.owner_url, "history").stdout.splitlines()
    steps = [ln.split("->")[1].split(",")[0].strip().split(" ")[0] for ln in out if "->" in ln][::-1]      # oldest first
    assert len(steps) >= 15
    for step in steps:                                                              # one revision at a time, from an empty database
        run_alembic(blank.owner_url, "upgrade", step)
    assert "(head)" in run_alembic(blank.owner_url, "current").stdout
    drift = run_alembic(blank.owner_url, "check", check=False)
    assert drift.returncode == 0, drift.stderr[-1200:]                              # no difference between migrations and the ORM models


def test_downgrade_and_upgrade_again_recreates_triggers_and_state(blank):
    run_alembic(blank.owner_url, "upgrade", "head")
    run_alembic(blank.owner_url, "downgrade", "0013")                               # removes the 0014 triggers and the 0015 tables
    eng = create_engine(blank.owner_url)
    with eng.connect() as c:
        assert c.execute(text("SELECT count(*) FROM pg_trigger WHERE tgname LIKE '%append_only%' AND NOT tgisinternal")).scalar() == 0
        assert c.execute(text("SELECT to_regclass('public.rate_limit_buckets')")).scalar() is None
    run_alembic(blank.owner_url, "upgrade", "head")
    with eng.connect() as c:
        assert c.execute(text("SELECT count(*) FROM pg_trigger WHERE tgname LIKE '%append_only%' AND NOT tgisinternal")).scalar() == 3
        assert c.execute(text("SELECT to_regclass('public.rate_limit_buckets')")).scalar() is not None
    eng.dispose()
    assert "(head)" in run_alembic(blank.owner_url, "current").stdout


def test_a_full_downgrade_to_the_first_revision_works_on_postgresql(blank):
    run_alembic(blank.owner_url, "upgrade", "head")
    r = run_alembic(blank.owner_url, "downgrade", "base", check=False)
    assert r.returncode == 0, "downgrade to base failed on PostgreSQL: " + r.stderr[-600:]
    eng = create_engine(blank.owner_url)
    with eng.connect() as c:
        left = c.execute(text("SELECT count(*) FROM pg_tables WHERE schemaname='public' AND tablename <> 'alembic_version'")).scalar()
    eng.dispose()
    assert left == 0
    run_alembic(blank.owner_url, "upgrade", "head")                                 # and the path back up still works


# ------------------------------------------------------------------ indexes and constraints
def test_partial_and_unique_indexes_exist_with_their_predicates(owner_engine):
    with owner_engine.connect() as c:
        defs = dict(c.execute(text("SELECT indexname, indexdef FROM pg_indexes WHERE schemaname='public'")).all())
    fp = defs["uq_tracked_expectations_forecast_fingerprint"]
    assert "UNIQUE" in fp and "WHERE" in fp
    cur = defs["uq_outcome_observations_current_window"]
    assert "UNIQUE" in cur and "WHERE" in cur and "is_current" in cur.split("WHERE")[1]
    assert "UNIQUE" in defs["uq_decision_responses_decision_seq"] and "UNIQUE" in defs["ix_prediction_evaluations_outcome_id"]


def test_the_unique_indexes_reject_duplicates_but_allow_superseded_history(app_engine):
    ids = _seed(app_engine)
    Session = sessionmaker(bind=app_engine, autoflush=False)
    obs = dict(business_id=ids["business"], expectation_id=ids["expectation"], metric="units_sold", unit="units", scope="business_total",
               window_start=date(2026, 1, 8), window_end=date(2026, 1, 14), window_days=7, value=5, status="observed", source="owner_entered",
               provenance="owner_entered", recorded_by="o")
    with Session() as s:                                                            # a second CURRENT observation for the window -> refused
        s.add(OutcomeObservation(revision=2, is_current=True, **obs))
        with pytest.raises(IntegrityError):
            s.flush()
    with Session() as s:                                                            # a superseded (not current) revision of the same window is fine
        s.add(OutcomeObservation(revision=2, is_current=False, **obs))
        s.commit()
    with Session() as s:                                                            # the same forecast fingerprint twice for one business -> refused
        s.add(TrackedExpectation(business_id=ids["business"], source_kind="forecast", metric="units_sold", unit="units", scope="business_total",
                                 window_start=date(2026, 1, 8), window_end=date(2026, 1, 14), horizon_days=7, comparable_to_actuals=True,
                                 provenance="owner_entered", fingerprint="fp-1"))
        with pytest.raises(IntegrityError):
            s.flush()
    with Session() as s:                                                            # the same revision number of one decision's response -> refused
        s.add(DecisionResponse(business_id=ids["business"], decision_id=ids["decision"], seq=1, response="rejected", action_status="unknown"))
        with pytest.raises(IntegrityError):
            s.flush()


# ------------------------------------------------------------------ append-only triggers under the application role
def test_the_application_role_cannot_edit_saved_snapshots_or_responses(app_engine):
    ids = _seed(app_engine)
    for sql in ("UPDATE tracked_expectations SET expected_value = 1 WHERE id = :i", "UPDATE decision_responses SET response = 'rejected'"):
        with pytest.raises(IntegrityError, match="append-only"):
            with app_engine.begin() as c:
                c.execute(text(sql), {"i": ids["expectation"]} if ":i" in sql else {})
    with app_engine.connect() as c:
        assert c.execute(text("SELECT expected_value FROM tracked_expectations")).scalar() == 100
        assert c.execute(text("SELECT response FROM decision_responses")).scalar() == "accepted"


def test_an_observation_may_only_be_superseded_never_rewritten(app_engine):
    ids = _seed(app_engine)
    bind = {"i": ids["observation"]}
    with pytest.raises(IntegrityError, match="append-only"):
        with app_engine.begin() as c:
            c.execute(text("UPDATE outcome_observations SET value = 999 WHERE id = :i"), bind)
    with pytest.raises(IntegrityError, match="append-only"):
        with app_engine.begin() as c:
            c.execute(text("UPDATE outcome_observations SET note = 'edited' WHERE id = :i"), bind)
    with app_engine.begin() as c:                                                    # the one legitimate change
        c.execute(text("UPDATE outcome_observations SET is_current = false WHERE id = :i"), bind)
    with pytest.raises(IntegrityError, match="append-only"):                       # and it cannot be flipped back, or applied twice
        with app_engine.begin() as c:
            c.execute(text("UPDATE outcome_observations SET is_current = true WHERE id = :i"), bind)
    with pytest.raises(IntegrityError, match="append-only"):
        with app_engine.begin() as c:
            c.execute(text("UPDATE outcome_observations SET is_current = false WHERE id = :i"), bind)


def test_the_real_correction_workflow_passes_the_triggers(app_engine):
    ids = _seed(app_engine)
    Session = sessionmaker(bind=app_engine, autoflush=False)
    with Session() as s:
        new = svc.correct_observation(s, ids["business"], ids["observation"], reason="typo in the entry", value=120.0, actor="o")
        assert new.revision == 2 and new.is_current
        svc.record_response(s, ids["business"], ids["decision"], response="rejected", actor="o")
    with Session() as s:
        cur = s.query(OutcomeObservation).filter_by(expectation_id=ids["expectation"], is_current=True).all()
        assert len(cur) == 1 and cur[0].revision == 2
        assert s.query(DecisionResponse).filter_by(decision_id=ids["decision"]).count() == 2


def test_deleting_a_business_still_cascades_through_the_protected_tables(app_engine):
    ids = _seed(app_engine)
    with app_engine.begin() as c:
        c.execute(text("DELETE FROM businesses WHERE id = :b"), {"b": ids["business"]})
    with app_engine.connect() as c:
        for t in ("tracked_expectations", "decision_responses", "outcome_observations"):
            assert c.execute(text(f"SELECT count(*) FROM {t}")).scalar() == 0


# ------------------------------------------------------------------ privileges: what the application role cannot do
@pytest.mark.parametrize("sql", [
    "TRUNCATE tracked_expectations",
    "DROP TRIGGER tracked_expectations_append_only ON tracked_expectations",
    "ALTER TABLE tracked_expectations DISABLE TRIGGER ALL",
    "ALTER TABLE tracked_expectations DISABLE TRIGGER tracked_expectations_append_only",
    "DROP TABLE tracked_expectations",
    "CREATE TABLE should_not_exist (id int)",
    "ALTER TABLE users ADD COLUMN sneaky int",
    "CREATE ROLE sneaky LOGIN",
    "CREATE OR REPLACE FUNCTION decisiongpt_block_update() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RETURN NEW; END $$",
    "SET session_replication_role = replica",
])
def test_the_application_role_cannot_remove_the_protection_or_change_the_schema(app_engine, sql):
    with pytest.raises((ProgrammingError, DBAPIError)) as err:
        with app_engine.begin() as c:
            c.execute(text(sql))
    msg = str(err.value).lower()
    assert "permission denied" in msg or "must be owner" in msg or "must be superuser" in msg, msg[:200]


def test_the_application_role_is_not_privileged_and_owns_nothing(app_engine):
    with app_engine.connect() as c:
        assert c.execute(text("SELECT rolsuper OR rolcreaterole OR rolcreatedb OR rolbypassrls FROM pg_roles WHERE rolname = current_user")).scalar() is False
        assert c.execute(text("SELECT count(*) FROM pg_tables WHERE schemaname='public' AND tableowner = current_user")).scalar() == 0


def test_the_owner_role_CAN_defeat_the_triggers_so_its_credentials_stay_out_of_the_application(owner_engine, app_engine):
    """The documented limit of the control: whoever holds the owner (or a superuser) can disable the protection. Recorded, not hidden."""
    _seed(app_engine)
    with owner_engine.begin() as c:
        c.execute(text("ALTER TABLE tracked_expectations DISABLE TRIGGER tracked_expectations_append_only"))
        c.execute(text("UPDATE tracked_expectations SET expected_value = 7"))
        c.execute(text("ALTER TABLE tracked_expectations ENABLE TRIGGER tracked_expectations_append_only"))
    with app_engine.connect() as c:
        assert c.execute(text("SELECT expected_value FROM tracked_expectations")).scalar() == 7


def test_tables_added_by_a_later_migration_are_usable_by_the_application_role(app_engine):
    with app_engine.begin() as c:                                                    # default privileges cover revoked_tokens / rate_limit_buckets (0015)
        c.execute(text("INSERT INTO revoked_tokens (jti, user_id, expires_at) VALUES ('j', :u, now())"), {"u": str(uuid.uuid4())})
        c.execute(text("DELETE FROM revoked_tokens"))


# ------------------------------------------------------------------ isolation, rollback, parallel writers
def test_a_read_snapshot_is_repeatable_read_and_read_only_and_ignores_concurrent_commits(app_engine):
    ids = _seed(app_engine)
    Session = sessionmaker(bind=app_engine, autoflush=False)
    with Session() as reader, Session() as writer:
        with read_snapshot(reader):
            assert reader.execute(text("SHOW transaction_isolation")).scalar() == "repeatable read"
            assert reader.execute(text("SHOW transaction_read_only")).scalar() == "on"
            assert reader.execute(text("SELECT count(*) FROM outcome_observations WHERE is_current")).scalar() == 1
            writer.execute(text("UPDATE outcome_observations SET is_current = false WHERE id = :i"), {"i": ids["observation"]})
            writer.commit()                                                          # committed while the snapshot is open
            assert reader.execute(text("SELECT count(*) FROM outcome_observations WHERE is_current")).scalar() == 1   # still the old state
            with pytest.raises(DBAPIError, match="read-only"):
                reader.execute(text("DELETE FROM decision_responses"))
            reader.rollback()
        assert reader.execute(text("SELECT count(*) FROM outcome_observations WHERE is_current")).scalar() == 0     # a new snapshot sees the commit


def test_a_failed_write_rolls_back_everything_in_its_transaction(app_engine):
    ids = _seed(app_engine)
    Session = sessionmaker(bind=app_engine, autoflush=False)
    with Session() as s:
        s.add(DecisionResponse(business_id=ids["business"], decision_id=ids["decision"], seq=2, response="modified", action_status="unknown"))
        s.add(DecisionResponse(business_id=ids["business"], decision_id=ids["decision"], seq=2, response="rejected", action_status="unknown"))
        with pytest.raises(IntegrityError):
            s.commit()
    with app_engine.connect() as c:
        assert c.execute(text("SELECT count(*) FROM decision_responses")).scalar() == 1                # the first insert was undone as well


def test_simultaneous_inserts_of_the_same_unique_key_admit_exactly_one(app_engine):
    ids = _seed(app_engine)
    Session = sessionmaker(bind=app_engine, autoflush=False)
    wins, losses, barrier = [], [], threading.Barrier(12)

    def worker():
        with Session() as s:
            try:
                barrier.wait(timeout=30)
                s.add(DecisionResponse(business_id=ids["business"], decision_id=ids["decision"], seq=2, response="modified", action_status="unknown"))
                s.commit()
                wins.append(1)
            except IntegrityError:
                losses.append(1)

    ts = [threading.Thread(target=worker) for _ in range(12)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert len(wins) == 1 and len(losses) == 11


# ------------------------------------------------------------------ the shared rate limiter on PostgreSQL
def test_the_atomic_counter_loses_no_increment_under_parallel_workers(app_engine):
    rule = limiter.Rule("login_ip", 10_000, 900)
    Session = sessionmaker(bind=app_engine, autoflush=False)
    errors = []

    def worker():
        db = Session()
        try:
            for _ in range(25):
                limiter.record(db, rule, "203.0.113.9")
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)
        finally:
            db.close()

    ts = [threading.Thread(target=worker) for _ in range(8)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert not errors, errors
    with Session() as db:
        assert limiter.current(db, rule, "203.0.113.9")[0] == 200


def test_concurrent_sign_ups_never_exceed_the_limit_on_postgresql(app_engine, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "rate_limit_enabled", True)
    monkeypatch.setattr(get_settings(), "rate_limit_register_per_ip", 4)
    Session = sessionmaker(bind=app_engine, autoflush=False)
    admitted, refused, barrier = [], [], threading.Barrier(20)

    def worker():
        db = Session()
        try:
            barrier.wait(timeout=30)
            limiter.enforce_register(db, "203.0.113.9")
            admitted.append(1)
        except limiter.RateLimitedError:
            refused.append(1)
        finally:
            db.close()

    ts = [threading.Thread(target=worker) for _ in range(20)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert len(admitted) == 4 and len(refused) == 16
