"""Integrity of the decision-tracking records and of the outcome report, against deterministic fixtures whose metrics are computed
independently in the test (not by the service). Synthetic fixtures only; nothing here is evidence about a real business."""
from datetime import date, timedelta

import pytest
from sqlalchemy.exc import OperationalError

from app.core import clock
from app.core.errors import NotFoundError, ValidationFailedError
from app.models.tracking import ImmutableRecordError, OutcomeObservation, TrackedExpectation
from app.services import outcome_tracking_service as svc
from tests.integration.test_analytics import _create_business, _upload_csv
from tests.integration.test_outcome_tracking import T0, _later_sales, _rows, decision_world  # noqa: F401  (fixture)

CUTOFF = date(2026, 6, 30)
NOW = date(2027, 3, 1)                      # every window below is over by then


def window(k: int) -> tuple[date, date]:
    start = CUTOFF + timedelta(days=1 + 7 * k)
    return start, start + timedelta(days=6)


def exp(db, bid, k, expected, *, source="forecast", metric="units_sold", unit="units", cutoff=CUTOFF, comparable=True, cfg=None, points=None):
    start, end = window(k)
    cfg = {"cutoff_provenance": "recorded", "horizon_provenance": "recorded", **(cfg or {})}
    e = TrackedExpectation(business_id=bid, source_kind=source, metric=metric, unit=unit, scope="business_total", window_start=start,
                           window_end=end, horizon_days=7, data_cutoff=cutoff, expected_value=expected, points_json=points,
                           comparable_to_actuals=comparable, comparability_reason=None if comparable else "model not on this scale",
                           config_json=cfg, provenance="derived_from_uploaded_data", method="fixture")
    db.add(e)
    db.commit()
    return e


def observe(db, bid, e, value, status="observed", **kw):
    with clock.reference_date(NOW):
        return svc.record_observation(db, bid, str(e.id), metric=e.metric, unit=e.unit, status=status, value=value, actor="fixture", **kw)


def raw_obs(db, bid, e, *, metric, unit, value):
    o = OutcomeObservation(business_id=bid, expectation_id=e.id, metric=metric, unit=unit, scope="business_total", window_start=e.window_start,
                           window_end=e.window_end, value=value, status="observed", window_days=7, source="owner_entered",
                           provenance="owner_entered", revision=1, is_current=True)
    db.add(o)
    db.commit()


@pytest.fixture()
def fixtures(client, db_session):
    a, b = _create_business(client), _create_business(client)
    db = db_session
    cases = {}
    cases["perfect"] = exp(db, a, 0, 100.0); observe(db, a, cases["perfect"], 100.0)
    cases["over"] = exp(db, a, 1, 120.0); observe(db, a, cases["over"], 100.0)
    cases["under"] = exp(db, a, 2, 80.0); observe(db, a, cases["under"], 100.0)
    cases["zero"] = exp(db, a, 3, 30.0); observe(db, a, cases["zero"], 0.0)                 # a genuine zero, not a missing value
    cases["small"] = exp(db, a, 4, 5.0); observe(db, a, cases["small"], 0.5)                # near zero: percentage must be unavailable
    cases["missing"] = exp(db, a, 5, 60.0)                                                  # no observation at all
    pts = [{"date": (window(6)[0] + timedelta(days=i)).isoformat(), "value": 10.0, "lower": 5.0, "upper": 15.0} for i in range(7)]
    cases["partial"] = exp(db, a, 6, 70.0, points=pts)
    with clock.reference_date(window(6)[0] + timedelta(days=3)):
        svc.record_observation(db, a, str(cases["partial"].id), metric="units_sold", unit="units", status="incomplete", value=28.0,
                               covered_until=window(6)[0] + timedelta(days=2), actor="fixture")
    cases["metric_mismatch"] = exp(db, a, 7, 90.0); raw_obs(db, a, cases["metric_mismatch"], metric="revenue", unit="INR", value=90000.0)
    cases["unit_mismatch"] = exp(db, a, 8, 90.0); raw_obs(db, a, cases["unit_mismatch"], metric="units_sold", unit="kg", value=90.0)
    cases["in_sample"] = exp(db, a, 9, 90.0, cutoff=window(9)[0]); observe(db, a, cases["in_sample"], 90.0)   # window starts at the cutoff
    cases["unknown_cutoff"] = exp(db, a, 10, 90.0, cutoff=None); observe(db, a, cases["unknown_cutoff"], 90.0)
    cases["inferred_cutoff"] = exp(db, a, 11, 90.0, cfg={"cutoff_provenance": "inferred_from_upload_time"}); observe(db, a, cases["inferred_cutoff"], 90.0)
    cases["revised"] = exp(db, a, 12, 100.0)
    first = observe(db, a, cases["revised"], 150.0)
    with clock.reference_date(NOW):
        svc.correct_observation(db, a, str(first.id), reason="till report says 110", value=110.0, actor="fixture")
    cases["invalid"] = exp(db, a, 13, 90.0); observe(db, a, cases["invalid"], None, status="invalid", unavailable_reason="till offline")
    cases["not_comparable"] = exp(db, a, 14, 90.0, comparable=False); observe(db, a, cases["not_comparable"], 90.0)
    cases["plan"] = exp(db, a, 15, 50.0, source="owner_plan", cutoff=None); observe(db, a, cases["plan"], 40.0)
    # another business with its own comparable cases: must never appear in a's report
    for k, (ex, ob) in enumerate([(10.0, 10.0), (200.0, 100.0)]):
        other = exp(db, b, k, ex)
        observe(db, b, other, ob)
    return client, db, a, b, cases


def test_the_report_matches_metrics_computed_independently_from_the_fixtures(fixtures):
    client, db, a, b, cases = fixtures
    rep = client.get(f"/api/v1/businesses/{a}/tracking/report").json()
    # independent arithmetic (expected - observed): perfect 0, over +20, under -20, zero +30, small +4.5, revised -10
    errs = [0.0, 20.0, -20.0, 30.0, 4.5, -10.0]
    observed = [100.0, 100.0, 100.0, 0.0, 0.5, 110.0]
    pcts = [0 / 100, 20 / 100, 20 / 100, 10 / 110]                       # zero and 0.5 observed: unavailable
    g = {(x["metric"], x["source_kind"], x["horizon"]): x for x in rep["forecast_accuracy"]["groups"]}
    fc = g[("units_sold", "forecast", "1-7 days")]
    assert fc["n"] == 6 and fc["summarised"] is True
    assert fc["mean_signed_error"] == pytest.approx(sum(errs) / 6)
    assert fc["mean_abs_error"] == pytest.approx(sum(abs(x) for x in errs) / 6)
    assert fc["wape"] == pytest.approx(sum(abs(x) for x in errs) / sum(observed))
    assert fc["mean_abs_pct_error"] == pytest.approx(sum(pcts) / 4) and fc["pct_error_n"] == 4 and fc["pct_error_unavailable_n"] == 2
    plan = g[("units_sold", "owner_plan", "1-7 days")]                   # a plan is never mixed with forecasts
    assert plan["n"] == 1 and plan["summarised"] is False and plan["mean_abs_error"] is None and "not summarised" in plan["note"]
    assert len(g) == 2
    # statuses: 7 compared in full (6 forecasts + the plan), 1 partial, 8 withheld
    assert rep["comparisons"]["by_status"] == {"evaluated": 7, "partial": 1, "excluded": 8}
    assert rep["comparisons"]["excluded_reasons"] == {"missing_observation": 1, "metric_mismatch": 2, "in_sample": 1, "cutoff_unknown": 1,
                                                      "cutoff_inferred": 1, "observation_invalid": 1, "not_comparable": 1}
    cov = rep["forecast_accuracy"]["coverage"]
    assert cov == {"compared_in_full": 7, "partial_not_aggregated": 1, "withheld_not_aggregated": 8, "expectations": 16}
    assert rep["forecast_accuracy"]["sample_size"] == 7 and "never combined" in rep["forecast_accuracy"]["aggregation_rule"]
    assert rep["observations"]["comparable"] == 8 and rep["observations"]["not_comparable"] == 7        # missing has no observation at all


def test_each_case_reports_exactly_the_error_and_reason_expected(fixtures):
    client, db, a, _, cases = fixtures
    cmp = {k: svc.comparison_for(db, a, str(e.id)) for k, e in cases.items()}
    assert cmp["perfect"]["signed_error"] == 0.0 and cmp["perfect"]["abs_pct_error"] == 0.0
    assert cmp["over"]["signed_error"] == 20.0 and cmp["under"]["signed_error"] == -20.0
    assert cmp["zero"]["observed"] == 0.0 and cmp["zero"]["abs_pct_error"] is None and "unavailable" in cmp["zero"]["abs_pct_error_note"]
    assert cmp["small"]["abs_pct_error"] is None and cmp["small"]["signed_error"] == 4.5          # explicit, never an inflated percentage
    assert cmp["revised"]["observed"] == 110.0 and cmp["revised"]["signed_error"] == -10.0          # the corrected value, not the first entry
    p = cmp["partial"]
    assert p["status"] == "partial" and p["expected_compared"] == 30.0 and p["observed"] == 28.0 and p["coverage_fraction"] == pytest.approx(3 / 7)
    for k, reason in (("missing", "missing_observation"), ("metric_mismatch", "metric_mismatch"), ("unit_mismatch", "metric_mismatch"),
                      ("in_sample", "in_sample"), ("unknown_cutoff", "cutoff_unknown"), ("inferred_cutoff", "cutoff_inferred"),
                      ("invalid", "observation_invalid"), ("not_comparable", "not_comparable")):
        assert cmp[k]["status"] == "excluded" and cmp[k]["reason"].startswith(reason), k
        assert "signed_error" not in cmp[k], k                                                   # a withheld comparison has no error figure
    assert cmp["inferred_cutoff"]["cutoff_inferred"] is True and cmp["inferred_cutoff"]["data_cutoff_provenance"] == "inferred_from_upload_time"
    assert cmp["missing"].get("observed") is None                                                # missing is not zero


def test_withheld_comparisons_cannot_move_an_aggregate(fixtures):
    client, db, a, _, cases = fixtures
    before = client.get(f"/api/v1/businesses/{a}/tracking/report").json()["forecast_accuracy"]["groups"]
    wild = exp(db, a, 20, 1.0, cutoff=None)                      # would be a huge error if it were compared
    observe(db, a, wild, 100000.0)
    wild2 = exp(db, a, 21, 1.0, cfg={"cutoff_provenance": "inferred_from_upload_time"})
    observe(db, a, wild2, 100000.0)
    after = client.get(f"/api/v1/businesses/{a}/tracking/report").json()["forecast_accuracy"]["groups"]
    assert after == before


def test_another_business_never_appears_in_the_report_or_the_aggregates(fixtures):
    client, db, a, b, cases = fixtures
    rb = client.get(f"/api/v1/businesses/{b}/tracking/report").json()
    assert rb["expectations"]["recorded"] == 2 and rb["comparisons"]["by_status"] == {"evaluated": 2}
    assert rb["forecast_accuracy"]["sample_size"] == 2 and rb["forecast_accuracy"]["groups"][0]["summarised"] is False
    ids_a = {str(e.id) for e in cases.values()}
    assert not ids_a & {c["expectation_id"] for c in rb["comparisons"]["details"]}
    with clock.reference_date(NOW):                                  # b cannot attach an observation to a's expectation
        with pytest.raises(NotFoundError):
            svc.record_observation(db, b, str(cases["perfect"].id), metric="units_sold", unit="units", status="observed", value=1.0, actor="x")


# ------------------------------------------------------------------ immutability
def test_saved_snapshots_and_history_cannot_be_changed_only_superseded(fixtures):
    client, db, a, _, cases = fixtures
    e = cases["perfect"]
    e.expected_value = 999.0
    with pytest.raises(ImmutableRecordError, match="append-only"):
        db.commit()
    db.rollback()
    o = db.query(OutcomeObservation).filter_by(expectation_id=e.id).first()
    o.value = 1.0
    with pytest.raises(ImmutableRecordError):
        db.commit()
    db.rollback()
    db.delete(e)
    with pytest.raises(ImmutableRecordError, match="cannot be deleted"):
        db.commit()
    db.rollback()
    o = db.query(OutcomeObservation).filter_by(expectation_id=e.id).first()
    o.is_current = False                                              # the one allowed change (a correction flips it on the old revision)
    db.commit()
    db.expire_all()
    assert db.get(TrackedExpectation, e.id).expected_value is not None and float(db.get(TrackedExpectation, e.id).expected_value) == 100.0


def test_a_correction_changes_nothing_but_the_current_flag_of_the_old_revision(fixtures):
    client, db, a, _, cases = fixtures
    revs = svc.observations_of(db, a, str(cases["revised"].id))
    assert [(r.revision, float(r.value), r.is_current) for r in revs] == [(1, 150.0, False), (2, 110.0, True)]
    assert revs[1].supersedes_id == revs[0].id and "till report" in revs[1].revision_reason


def test_saved_snapshots_survive_later_data_code_and_configuration_changes(client, db_session, monkeypatch):
    bid = _create_business(client)
    _upload_csv(client, bid, "sales", _rows(T0 - timedelta(days=119), T0))
    shown = client.post(f"/api/v1/businesses/{bid}/analytics/forecast?horizon_days=7").json()
    saved = client.post(f"/api/v1/businesses/{bid}/tracking/forecasts", json={"horizon_days": 7, "fingerprint": shown["fingerprint"]}).json()
    frozen = {k: saved[k] for k in ("id", "expected_value", "window_start", "window_end", "data_cutoff", "input_sha256", "points", "model_name",
                                    "horizon_days")}
    # the business uploads more sales, and the forecasting code / default configuration change
    _later_sales(client, bid, T0 + timedelta(days=1), T0 + timedelta(days=20))
    from app.analytics import business_forecast_service as bfs

    monkeypatch.setattr(bfs, "STALE_AFTER_DAYS", 1)
    monkeypatch.setattr(bfs, "ORIGIN_STEP_DAYS", 3)
    newer = client.post(f"/api/v1/businesses/{bid}/analytics/forecast?horizon_days=7").json()
    assert newer["fingerprint"] != shown["fingerprint"]
    again = client.get(f"/api/v1/businesses/{bid}/tracking/expectations/{saved['id']}").json()["expectation"]
    assert {k: again[k] for k in frozen} == frozen                                  # unchanged and still readable
    second = client.post(f"/api/v1/businesses/{bid}/tracking/forecasts", json={"horizon_days": 7, "fingerprint": newer["fingerprint"]}).json()
    assert second["id"] != saved["id"] and second["already_saved"] is False        # an intentionally new snapshot is allowed
    assert {e["id"] for e in client.get(f"/api/v1/businesses/{bid}/tracking/expectations").json()["expectations"]} == {saved["id"], second["id"]}


# ------------------------------------------------------------------ transitions
def test_derived_measurement_never_replaces_an_owner_entered_observation(biz_for_derive):
    client, db, bid, e = biz_for_derive
    with clock.reference_date(T0 + timedelta(days=10)):
        svc.record_observation(db, bid, str(e.id), metric="units_sold", unit="units", status="observed", value=123.0, actor="owner")
        with pytest.raises(ValidationFailedError, match="entered by the owner"):
            svc.derive_observation(db, bid, str(e.id))
    cur = [o for o in svc.observations_of(db, bid, str(e.id)) if o.is_current]
    assert len(cur) == 1 and cur[0].source == "owner_entered" and float(cur[0].value) == 123.0


@pytest.fixture()
def biz_for_derive(client, db_session):
    bid = _create_business(client)
    _upload_csv(client, bid, "sales", _rows(T0 - timedelta(days=119), T0))
    with clock.reference_date(T0):
        e = svc.snapshot_forecast(db_session, bid, 7)
    _later_sales(client, bid, T0 + timedelta(days=1), T0 + timedelta(days=7))
    return client, db_session, bid, e


def test_switching_from_modified_to_accepted_drops_the_modified_description(decision_world):
    _, db, bid, did = decision_world
    svc.record_response(db, bid, did, response="modified", modified_action={"description": "price +3%"}, actor="o")
    r = svc.record_response(db, bid, did, response="accepted", actor="o")
    assert r.response == "accepted" and r.modified_action_json is None
    with pytest.raises(ValidationFailedError, match="only be recorded for a modified response"):
        svc.record_response(db, bid, did, response="rejected", modified_action={"description": "x"}, actor="o")


def test_rejection_and_deferral_do_not_keep_an_earlier_execution(decision_world):
    _, db, bid, did = decision_world
    svc.record_response(db, bid, did, response="accepted", action_status="executed", action_start=date.today(), action_taken={"d": 1}, actor="o")
    for resp in ("rejected", "deferred"):
        svc.record_response(db, bid, did, response="accepted", action_status="executed", action_start=date.today(), action_taken={"d": 1}, actor="o") \
            if resp == "deferred" else None
        r = svc.record_response(db, bid, did, response=resp, action_status="not_executed", actor="o")
        assert (r.action_start, r.action_end, r.action_taken_json, r.action_status) == (None, None, None, "not_executed")
        assert not svc.action_executed(db, bid, did)


# ------------------------------------------------------------------ failure between validation and persistence
def test_a_failure_while_saving_leaves_no_partial_record_and_a_retry_works(biz_for_derive, monkeypatch):
    client, db, bid, e = biz_for_derive
    real_commit = db.commit
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] == 1:
            raise OperationalError("COMMIT", {}, Exception("disk I/O error"))
        return real_commit()

    monkeypatch.setattr(db, "commit", flaky)
    with clock.reference_date(T0 + timedelta(days=10)):
        with pytest.raises(OperationalError):
            svc.record_observation(db, bid, str(e.id), metric="units_sold", unit="units", status="observed", value=77.0, actor="o")
        assert svc.observations_of(db, bid, str(e.id)) == []          # nothing partially persisted, and the session is usable
        ok = svc.record_observation(db, bid, str(e.id), metric="units_sold", unit="units", status="observed", value=77.0, actor="o")
    assert ok.revision == 1 and len(svc.observations_of(db, bid, str(e.id))) == 1


def test_a_failure_while_saving_a_snapshot_leaves_nothing_behind(client, db_session, monkeypatch):
    bid = _create_business(client)
    _upload_csv(client, bid, "sales", _rows(T0 - timedelta(days=119), T0))
    real_commit = db_session.commit
    state = {"fail": True}

    def flaky():
        if state["fail"]:
            state["fail"] = False
            raise OperationalError("COMMIT", {}, Exception("disk I/O error"))
        return real_commit()

    monkeypatch.setattr(db_session, "commit", flaky)
    with pytest.raises(OperationalError):
        svc.save_forecast_snapshot(db_session, bid, 7)
    assert db_session.query(TrackedExpectation).filter_by(business_id=bid).count() == 0
    row, info = svc.save_forecast_snapshot(db_session, bid, 7)
    assert info["already_saved"] is False and db_session.query(TrackedExpectation).filter_by(business_id=bid).count() == 1


# ------------------------------------------------------------------ no external calls; legacy metadata is never silently upgraded
def test_tracking_never_opens_a_network_connection(client, db_session, monkeypatch):
    import socket

    def refuse(*a, **k):
        raise AssertionError("tracking attempted a network connection")

    bid = _create_business(client)
    _upload_csv(client, bid, "sales", _rows(T0 - timedelta(days=119), T0))
    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    with clock.reference_date(T0):
        e, _ = svc.save_forecast_snapshot(db_session, bid, 7)
    with clock.reference_date(T0 + timedelta(days=10)):
        svc.record_observation(db_session, bid, str(e.id), metric="units_sold", unit="units", status="observed", value=50.0, actor="t")
    assert svc.report(db_session, bid)["expectations"]["recorded"] == 1


def test_an_inferred_cutoff_is_not_upgraded_when_the_decision_later_gains_recorded_metadata(decision_world):
    from app.models.decision import Decision

    _, db, bid, did = decision_world
    d = db.get(Decision, did)
    po = d.debate_json["pipeline_options"]
    d.debate_json = {k: v for k, v in d.debate_json.items() if k != "pipeline_options"}        # a legacy decision
    db.commit()
    first = svc.expectations_from_decision(db, bid, did)[0]
    assert first.config_json["cutoff_provenance"] == "inferred_from_upload_time" and first.config_json["metadata_quality"] == "inferred"
    d.debate_json = {**d.debate_json, "pipeline_options": po}                                    # recorded metadata appears afterwards
    db.commit()
    again = svc.expectations_from_decision(db, bid, did)[0]
    assert again.id == first.id and again.config_json["cutoff_provenance"] == "inferred_from_upload_time"     # still inferred
    assert again.config_json["metadata_quality"] == "inferred"


def test_metadata_quality_distinguishes_known_inferred_and_unknown(decision_world):
    from app.models.decision import Decision

    _, db, bid, did = decision_world
    recorded = svc.expectations_from_decision(db, bid, did)[0]
    assert recorded.config_json["metadata_quality"] == "known_persisted"
    d = db.get(Decision, did)
    d.debate_json = {k: v for k, v in d.debate_json.items() if k != "pipeline_options"}
    db.commit()
    from sqlalchemy import update

    from tests.legacy_rows import as_legacy

    as_legacy(db, TrackedExpectation, TrackedExpectation.decision_id == did, decision_id=None)   # detach to re-materialise (a saved row cannot be UPDATEd, so it is replaced)
    from sqlalchemy import func

    from app.models.sale import Sale

    db.execute(update(Sale).where(Sale.business_id == bid).values(created_at=d.created_at + timedelta(days=1)))   # no sales existed at decision time
    db.commit()
    unknown = svc.expectations_from_decision(db, bid, did)[0]
    assert unknown.config_json["cutoff_provenance"] == "unknown" and unknown.config_json["metadata_quality"] == "unknown"
    assert unknown.comparable_to_actuals is False and unknown.data_cutoff is None
