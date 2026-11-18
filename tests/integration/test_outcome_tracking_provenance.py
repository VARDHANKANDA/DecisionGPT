"""Forecast provenance, snapshots of what was shown, recorded vs reconstructed horizon/cutoff, retries and the awaiting-actuals report.

Synthetic fixtures only (see test_outcome_tracking.py for the shared generators)."""
from datetime import timedelta

import pytest

from app.core import clock
from app.core.errors import ConflictError, ValidationFailedError
from app.models.tracking import DecisionResponse, OutcomeObservation, TrackedExpectation
from app.services import outcome_tracking_service as svc
from tests.integration.test_outcome_tracking import (  # noqa: F401  (fixtures and helpers)
    T0, _later_sales, _snapshot, biz, decision_world,
)


def _forecast_json(client, bid, h=7):
    r = client.post(f"/api/v1/businesses/{bid}/analytics/forecast?horizon_days={h}")
    assert r.status_code == 200, r.text
    return r.json()


def test_the_forecast_response_identifies_what_was_forecast_and_from_which_data(biz):
    client, _, bid = biz
    f = _forecast_json(client, bid, 7)
    assert len(f["fingerprint"]) == 64 and len(f["dataset_sha256"]) == 64 and f["generated_at"]
    assert f["horizon_requested"] == 7 and f["horizon_returned"] == 7
    assert f["forecast_start"] == f["points"][0]["forecast_date"] and f["forecast_end"] == f["points"][-1]["forecast_date"]
    assert f["data_cutoff"] == f["data_as_of"] and f["forecast_start"] > f["data_cutoff"]   # creation time and last data date are distinct
    assert set(f["references"]) >= {"naive_last_daily", "trailing_mean_28_daily"}
    assert _forecast_json(client, bid, 7)["fingerprint"] == f["fingerprint"]                  # deterministic for the same data and method
    assert _forecast_json(client, bid, 14)["fingerprint"] != f["fingerprint"]


def test_a_saved_snapshot_is_the_forecast_that_was_shown_with_all_its_provenance(biz):
    client, db, bid = biz
    shown = _forecast_json(client, bid, 7)
    r = client.post(f"/api/v1/businesses/{bid}/tracking/forecasts",
                    json={"horizon_days": 7, "fingerprint": shown["fingerprint"], "question": "next week?"})
    assert r.status_code == 200, r.text
    s = r.json()
    assert s["already_saved"] is False and s["verified_against_shown"] is True
    assert [p["date"] for p in s["points"]] == [p["forecast_date"] for p in shown["points"]]          # the saved values ARE the shown values
    assert [p["value"] for p in s["points"]] == [p["predicted_value"] for p in shown["points"]]
    assert [(p["lower"], p["upper"]) for p in s["points"]] == [(p["lower_bound"], p["upper_bound"]) for p in shown["points"]]
    assert (s["metric"], s["unit"], s["scope"]) == ("units_sold", "units", "business_total")
    assert s["window_start"] == shown["forecast_start"] and s["window_end"] == shown["forecast_end"] and s["data_cutoff"] == shown["data_cutoff"]
    assert s["input_sha256"] == shown["dataset_sha256"] and s["model_name"] == shown["model_name"] and s["basis"] == shown["forecast_basis"]
    assert s["interval_method"] == shown["interval_method"] and s["interval_reliable"] == shown["interval_reliable"]
    c = s["config"]
    assert c["fingerprint"] == shown["fingerprint"] and c["cutoff_provenance"] == "recorded" and c["horizon_provenance"] == "recorded"
    assert c["horizon_requested"] == 7 and c["horizon_returned"] == 7 and c["generated_at"] and c["validation_status"]
    assert c["calendar"].startswith("calendar dates") and "sum over the window" in c["granularity"]
    assert s["reference"]["naive_last_daily"] == shown["references"]["naive_last_daily"]
    assert s["points"][0]["baseline_naive_last"] == shown["references"]["naive_last_daily"]
    assert s["cutoff_provenance"] == "recorded" and s["created_at"]


def test_a_forecast_that_changed_since_it_was_shown_is_not_saved(biz):
    client, db, bid = biz
    shown = _forecast_json(client, bid, 7)
    _later_sales(client, bid, T0 + timedelta(days=1), T0 + timedelta(days=2))          # new data arrives after the owner saw the forecast
    r = client.post(f"/api/v1/businesses/{bid}/tracking/forecasts", json={"horizon_days": 7, "fingerprint": shown["fingerprint"]})
    assert r.status_code == 409 and r.json()["error"]["code"] == "CONFLICT" and "changed since it was shown" in r.json()["error"]["message"]
    assert db.query(TrackedExpectation).filter_by(business_id=bid).count() == 0              # nothing partially saved
    fresh = _forecast_json(client, bid, 7)
    assert fresh["fingerprint"] != shown["fingerprint"]
    ok = client.post(f"/api/v1/businesses/{bid}/tracking/forecasts", json={"horizon_days": 7, "fingerprint": fresh["fingerprint"]})
    assert ok.status_code == 200 and ok.json()["already_saved"] is False


def test_saving_the_same_forecast_twice_does_not_duplicate_it(biz):
    client, db, bid = biz
    shown = _forecast_json(client, bid, 7)
    body = {"horizon_days": 7, "fingerprint": shown["fingerprint"]}
    a = client.post(f"/api/v1/businesses/{bid}/tracking/forecasts", json=body).json()
    b = client.post(f"/api/v1/businesses/{bid}/tracking/forecasts", json=body).json()        # a double click or a retry
    assert a["id"] == b["id"] and b["already_saved"] is True
    assert db.query(TrackedExpectation).filter_by(business_id=bid, source_kind="forecast").count() == 1
    other = _forecast_json(client, bid, 14)                                                  # a different forecast is a different snapshot
    c = client.post(f"/api/v1/businesses/{bid}/tracking/forecasts", json={"horizon_days": 14, "fingerprint": other["fingerprint"]}).json()
    assert c["id"] != a["id"] and db.query(TrackedExpectation).filter_by(business_id=bid, source_kind="forecast").count() == 2


def test_a_forecast_whose_metadata_cannot_be_established_is_refused_not_completed(biz, monkeypatch):
    client, db, bid = biz
    from app.analytics import forecast_service

    real = forecast_service.forecast_sales

    def no_cutoff(*a, **k):
        r = real(*a, **k)
        r.data_as_of = None
        r.fingerprint = None
        return r

    monkeypatch.setattr(forecast_service, "forecast_sales", no_cutoff)
    r = client.post(f"/api/v1/businesses/{bid}/tracking/forecasts", json={"horizon_days": 7})
    assert r.status_code == 422 and "cannot be saved" in r.json()["error"]["message"] and "data cutoff" in r.json()["error"]["message"]
    assert db.query(TrackedExpectation).filter_by(business_id=bid).count() == 0


def test_a_snapshot_without_a_shown_fingerprint_is_labelled_unverified(biz):
    client, _, bid = biz
    s = client.post(f"/api/v1/businesses/{bid}/tracking/forecasts", json={"horizon_days": 7}).json()
    assert s["verified_against_shown"] is None and s["config"]["shown_fingerprint_verified"] is None


def test_a_new_decision_records_its_horizon_and_data_cutoff(decision_world):
    client, db, bid, did = decision_world
    from sqlalchemy import func

    from app.models.decision import Decision
    from app.models.sale import Sale

    po = db.get(Decision, did).debate_json["pipeline_options"]
    last = db.query(func.max(Sale.sale_date)).filter(Sale.business_id == bid).scalar()
    assert po["scenario_horizon_days"] == 14 and po["data_cutoff"] == last.isoformat() and "latest sale date" in po["data_cutoff_source"]
    e = svc.expectations_from_decision(db, bid, did)[0]
    assert e.config_json["cutoff_provenance"] == "recorded" and e.config_json["horizon_provenance"] == "recorded" and e.data_cutoff == last
    assert e.window_start == last + timedelta(days=1) and e.window_end == last + timedelta(days=14)


def test_a_legacy_decision_without_recorded_metadata_is_labelled_inferred_or_unknown(decision_world):
    client, db, bid, did = decision_world
    from app.models.decision import Decision

    d = db.get(Decision, did)
    d.debate_json = {k: v for k, v in d.debate_json.items() if k != "pipeline_options"}      # as a decision made before this was recorded
    db.commit()
    e = svc.expectations_from_decision(db, bid, did)[0]
    assert e.config_json["cutoff_provenance"] == "inferred_from_upload_time" and e.config_json["horizon_provenance"] == "assumed_pipeline_default"
    assert "reconstructed from upload times" in e.comparability_reason
    c = svc.comparison_for(db, bid, str(e.id))
    assert c["data_cutoff_provenance"] == "inferred_from_upload_time" and c["horizon_provenance"] == "assumed_pipeline_default"


def test_an_expectation_with_an_unknown_cutoff_is_never_compared(biz):
    _, db, bid = biz
    from tests.legacy_rows import as_legacy

    e = _snapshot(db, bid)
    # simulate a record from before cutoffs were kept: a saved snapshot cannot be UPDATEd (the ORM and, in production, the database refuse), so it is
    # replaced by a copy that has the legacy value - which is how such a row came to exist
    as_legacy(db, TrackedExpectation, TrackedExpectation.id == e.id, data_cutoff=None)
    with clock.reference_date(T0 + timedelta(days=10)):
        svc.record_observation(db, bid, str(e.id), metric="units_sold", unit="units", status="observed", value=100.0, actor="t")
    assert svc.comparison_for(db, bid, str(e.id))["reason"].startswith("cutoff_unknown")


def test_a_response_race_is_a_conflict_or_a_duplicate_never_two_current_revisions(decision_world, monkeypatch):
    _, db, bid, did = decision_world
    svc.record_response(db, bid, did, response="accepted", actor="o")
    real = svc.current_response
    calls = {"n": 0}

    def stale(db_, b_, d_):
        calls["n"] += 1
        return None if calls["n"] == 1 else real(db_, b_, d_)         # the first read misses the row another request just wrote

    monkeypatch.setattr(svc, "current_response", stale)
    with pytest.raises(ConflictError, match="same moment"):
        svc.record_response(db, bid, did, response="rejected", actor="o")
    calls["n"] = 0
    with pytest.raises(ValidationFailedError, match="already recorded"):
        svc.record_response(db, bid, did, response="accepted", actor="o")
    monkeypatch.setattr(svc, "current_response", real)
    assert db.query(DecisionResponse).filter_by(decision_id=did).count() == 1


def test_the_database_allows_only_one_current_observation_per_window(biz):
    from sqlalchemy.exc import IntegrityError

    _, db, bid = biz
    e = _snapshot(db, bid)
    with clock.reference_date(T0 + timedelta(days=10)):
        o = svc.record_observation(db, bid, str(e.id), metric="units_sold", unit="units", status="observed", value=10.0, actor="t")
    twin = OutcomeObservation(business_id=bid, expectation_id=e.id, metric=o.metric, unit=o.unit, scope=o.scope, window_start=o.window_start,
                              window_end=o.window_end, value=11.0, status="observed", window_days=o.window_days, source="owner_entered",
                              provenance="owner_entered", revision=1, is_current=True)
    db.add(twin)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_the_report_lists_snapshots_awaiting_actuals_and_comparable_counts(biz):
    client, db, bid = biz
    e1 = _snapshot(db, bid, 7)                                                      # will be observed completely
    with clock.reference_date(T0):
        e2 = svc.snapshot_forecast(db, bid, 14)                                     # no observation yet
    _later_sales(client, bid, T0 + timedelta(days=1), T0 + timedelta(days=7))
    with clock.reference_date(T0 + timedelta(days=9)):
        svc.derive_observation(db, bid, str(e1.id))
    rep = svc.report(db, bid)
    wait = {a["expectation_id"]: a for a in rep["awaiting_actuals"]}
    assert str(e1.id) not in wait and str(e2.id) in wait and wait[str(e2.id)]["state"] == "no observation yet"
    assert rep["observations"]["comparable"] == 1 and rep["observations"]["not_comparable"] == 0
    assert rep["observations"]["mean_coverage_fraction"] == 1.0
