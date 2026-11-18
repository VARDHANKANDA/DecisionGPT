"""Outcome tracking: expectations, responses, observations, comparison rules and the report.

Synthetic fixtures only (generated weekly-pattern sales with fixed past dates); nothing here is evidence about a real business. The
clock is pinned with ``clock.reference_date`` so forecasts are made 'in the past' and their windows can then be observed.
"""
from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from app.core import clock
from app.core.errors import NotFoundError, ValidationFailedError
from app.models.decision import DecisionOutcome
from app.models.ml_model import MLModel
from app.models.tracking import OutcomeObservation, TrackedExpectation
from app.services import model_registry_service
from app.services import outcome_tracking_service as svc
from tests.integration.test_analytics import _create_business, _seed_rich_business, _upload_csv
from tests.integration.test_decisions import _create_goal

T0 = date(2026, 6, 30)   # the day the forecasts are made (data through T0)


def _rows(start: date, end: date, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    out = []
    d = start
    while d <= end:
        mult = 1.6 if d.weekday() >= 5 else 1.0
        for p in range(3):
            q = max(1, int(round(7 * mult + rng.normal(0, 1.0)))) + 20 * p         # distinct per product per day (no duplicate rows)
            out.append({"Order Date": d.isoformat(), "Product Name": f"Item {p}", "Quantity": q, "Unit Price": 100, "Revenue": q * 100})
        d += timedelta(days=1)
    return pd.DataFrame(out)


@pytest.fixture()
def biz(client, db_session):
    bid = _create_business(client)
    _upload_csv(client, bid, "sales", _rows(T0 - timedelta(days=119), T0))
    return client, db_session, bid


def _snapshot(db, bid, horizon=7):
    with clock.reference_date(T0):
        return svc.snapshot_forecast(db, bid, horizon, question="How many units next week?")


def _later_sales(client, bid, start, end, seed=5):
    _upload_csv(client, bid, "sales", _rows(start, end, seed))


# ------------------------------------------------------------------ expectations
def test_a_forecast_snapshot_keeps_what_it_would_have_shown(biz):
    client, db, bid = biz
    e = _snapshot(db, bid, 7)
    assert (e.metric, e.unit, e.scope) == ("units_sold", "units", "business_total")
    assert e.data_cutoff == T0 and e.window_start == T0 + timedelta(days=1) and e.window_end == T0 + timedelta(days=7) and e.horizon_days == 7
    assert e.model_name.startswith("business_baseline:") and e.basis in ("business_specific_validated", "business_specific_baseline")
    assert len(e.points_json) == 7 and abs(sum(p["value"] for p in e.points_json) - float(e.expected_value)) < 0.05
    assert {"naive_last_total", "trailing_mean_28_total"} <= set(e.reference_json) and len(e.input_sha256) == 64
    assert e.comparable_to_actuals is True and e.provenance == "derived_from_uploaded_data" and e.question.startswith("How many")
    assert any("zero units" in a for a in e.assumptions_json)


def test_a_missing_observation_is_excluded_not_treated_as_zero(biz):
    _, db, bid = biz
    e = _snapshot(db, bid)
    c = svc.comparison_for(db, bid, str(e.id))
    assert c["status"] == "excluded" and c["reason"].startswith("missing_observation") and "observed" not in c


# ------------------------------------------------------------------ derived observations and comparison
def test_a_window_with_no_data_yet_is_pending_with_no_value(biz):
    _, db, bid = biz
    e = _snapshot(db, bid)
    with clock.reference_date(T0 + timedelta(days=3)):
        o = svc.derive_observation(db, bid, str(e.id))
    assert o.status == "pending" and o.value is None and "no uploaded data reaches" in o.unavailable_reason
    assert svc.comparison_for(db, bid, str(e.id))["status"] == "excluded"


def test_a_complete_window_is_compared_out_of_sample_with_signed_error_and_references(biz):
    client, db, bid = biz
    e = _snapshot(db, bid)
    _later_sales(client, bid, T0 + timedelta(days=1), T0 + timedelta(days=7))
    with clock.reference_date(T0 + timedelta(days=10)):
        o = svc.derive_observation(db, bid, str(e.id))
    assert o.status == "observed" and o.coverage_days == 7 and o.source == "derived_from_sales" and o.value is not None
    c = svc.comparison_for(db, bid, str(e.id))
    assert c["status"] == "evaluated" and c["error_convention"] == "expected - observed (positive = over-forecast)"
    assert c["signed_error"] == pytest.approx(c["expected"] - c["observed"]) and c["abs_error"] == pytest.approx(abs(c["signed_error"]))
    assert c["abs_pct_error"] == pytest.approx(c["abs_error"] / c["observed"])
    assert set(c["references"]) >= {"naive_last_total", "trailing_mean_28_total"}
    assert c["band_days"]["days"] == 7 and 0 <= c["band_days"]["inside"] <= 7
    assert c["data_cutoff"] == T0.isoformat() and c["horizon_days"] == 7           # the original cutoff and horizon are preserved


def test_a_partial_period_is_labelled_and_compared_over_the_covered_days_only(biz):
    client, db, bid = biz
    e = _snapshot(db, bid)
    _later_sales(client, bid, T0 + timedelta(days=1), T0 + timedelta(days=3))
    with clock.reference_date(T0 + timedelta(days=5)):
        o = svc.derive_observation(db, bid, str(e.id))
    assert o.status == "incomplete" and o.coverage_days == 3 and o.covered_until == T0 + timedelta(days=3)
    c = svc.comparison_for(db, bid, str(e.id))
    assert c["status"] == "partial" and c["coverage_fraction"] == pytest.approx(3 / 7) and "partial_period" in c["reason"]
    assert c["expected_compared"] == pytest.approx(sum(p["value"] for p in e.points_json[:3]))


def test_later_data_creates_a_new_revision_and_keeps_the_history(biz):
    client, db, bid = biz
    e = _snapshot(db, bid)
    _later_sales(client, bid, T0 + timedelta(days=1), T0 + timedelta(days=3))
    with clock.reference_date(T0 + timedelta(days=5)):
        first = svc.derive_observation(db, bid, str(e.id))
        again = svc.derive_observation(db, bid, str(e.id))
    assert again.id == first.id                                                      # idempotent: nothing new, no duplicate row
    _later_sales(client, bid, T0 + timedelta(days=4), T0 + timedelta(days=7), seed=6)
    with clock.reference_date(T0 + timedelta(days=9)):
        second = svc.derive_observation(db, bid, str(e.id))
    assert second.status == "observed" and second.revision == 2 and second.supersedes_id == first.id
    assert "recomputed from uploaded data" in second.revision_reason
    hist = svc.observations_of(db, bid, str(e.id))
    assert [o.revision for o in hist] == [1, 2] and [o.is_current for o in hist] == [False, True]


def test_an_observation_that_overlaps_the_data_cutoff_is_in_sample_and_excluded(biz):
    _, db, bid = biz
    e = _snapshot(db, bid)
    with clock.reference_date(T0 + timedelta(days=10)):
        svc.record_observation(db, bid, str(e.id), metric="units_sold", unit="units", status="observed", value=200.0,
                               window_start=T0 - timedelta(days=2), window_end=T0 + timedelta(days=4), actor="t")
    c = svc.comparison_for(db, bid, str(e.id))
    assert c["status"] == "excluded" and c["reason"].startswith("in_sample")


def test_a_different_window_is_excluded_not_forced(biz):
    _, db, bid = biz
    e = _snapshot(db, bid)
    with clock.reference_date(T0 + timedelta(days=20)):
        svc.record_observation(db, bid, str(e.id), metric="units_sold", unit="units", status="observed", value=210.0,
                               window_start=T0 + timedelta(days=1), window_end=T0 + timedelta(days=14), actor="t")
    assert svc.comparison_for(db, bid, str(e.id))["reason"].startswith("window_mismatch")


# ------------------------------------------------------------------ validation of what can be recorded
def test_metric_and_unit_must_match_the_expectation(biz):
    _, db, bid = biz
    e = _snapshot(db, bid)
    with clock.reference_date(T0 + timedelta(days=10)):
        with pytest.raises(ValidationFailedError, match="cannot be compared"):
            svc.record_observation(db, bid, str(e.id), metric="revenue", unit="INR", status="observed", value=1.0, actor="t")
        with pytest.raises(ValidationFailedError, match="unit for units_sold is 'units'"):
            svc.record_observation(db, bid, str(e.id), metric="units_sold", unit="kg", status="observed", value=1.0, actor="t")


@pytest.mark.parametrize("kw,match", [
    (dict(status="observed", value=None), "finite number"),
    (dict(status="observed", value=-3.0), "not negative"),
    (dict(status="observed", value=float("nan")), "finite number"),
    (dict(status="pending", value=0.0), "do not enter 0"),
    (dict(status="invalid", value=None), "needs unavailable_reason"),
    (dict(status="incomplete", value=10.0), "needs covered_until"),
    (dict(status="incomplete", value=10.0, covered_until=T0 + timedelta(days=7)), "before its end"),
    (dict(status="nonsense", value=1.0), "status must be one of"),
])
def test_unknown_values_are_never_stored_as_zero_and_bad_input_is_refused(biz, kw, match):
    _, db, bid = biz
    e = _snapshot(db, bid)
    with clock.reference_date(T0 + timedelta(days=10)):
        with pytest.raises(ValidationFailedError, match=match):
            svc.record_observation(db, bid, str(e.id), metric="units_sold", unit="units", actor="t", **kw)
    assert svc.observations_of(db, bid, str(e.id)) == []


def test_a_window_that_has_not_finished_cannot_be_recorded_as_observed(biz):
    _, db, bid = biz
    e = _snapshot(db, bid)
    with clock.reference_date(T0 + timedelta(days=2)):
        with pytest.raises(ValidationFailedError, match="has not finished yet"):
            svc.record_observation(db, bid, str(e.id), metric="units_sold", unit="units", status="observed", value=50.0, actor="t")
        o = svc.record_observation(db, bid, str(e.id), metric="units_sold", unit="units", status="incomplete", value=20.0,
                                   covered_until=T0 + timedelta(days=2), actor="t")
    assert o.status == "incomplete" and o.coverage_days == 2


def test_duplicate_and_contradictory_submissions_are_refused_and_corrections_are_auditable(biz):
    _, db, bid = biz
    e = _snapshot(db, bid)
    with clock.reference_date(T0 + timedelta(days=10)):
        o = svc.record_observation(db, bid, str(e.id), metric="units_sold", unit="units", status="observed", value=180.0, actor="owner@x")
        with pytest.raises(ValidationFailedError, match="already recorded"):
            svc.record_observation(db, bid, str(e.id), metric="units_sold", unit="units", status="observed", value=180.0, actor="owner@x")
        with pytest.raises(ValidationFailedError, match="Submit a correction"):
            svc.record_observation(db, bid, str(e.id), metric="units_sold", unit="units", status="observed", value=190.0, actor="owner@x")
        with pytest.raises(ValidationFailedError, match="needs a reason"):
            svc.correct_observation(db, bid, str(o.id), reason="", value=190.0, actor="owner@x")
        with pytest.raises(ValidationFailedError, match="does not change anything"):
            svc.correct_observation(db, bid, str(o.id), reason="typo", value=180.0, actor="owner@x")
        fixed = svc.correct_observation(db, bid, str(o.id), reason="typed 180, the till report says 190", value=190.0, actor="owner@x")
    assert fixed.revision == 2 and float(fixed.value) == 190.0 and fixed.supersedes_id == o.id and "till report" in fixed.revision_reason
    db.refresh(o)
    assert o.is_current is False and float(o.value) == 180.0                       # the earlier value is still on record
    with pytest.raises(ValidationFailedError, match="Only the current revision"):
        svc.correct_observation(db, bid, str(o.id), reason="again", value=200.0, actor="x")
    assert svc.comparison_for(db, bid, str(e.id))["observed"] == 190.0               # the comparison uses the corrected value


def test_an_invalid_observation_carries_its_reason_and_is_never_compared(biz):
    _, db, bid = biz
    e = _snapshot(db, bid)
    with clock.reference_date(T0 + timedelta(days=10)):
        svc.record_observation(db, bid, str(e.id), metric="units_sold", unit="units", status="invalid",
                               unavailable_reason="the till was offline for three days", actor="t")
    c = svc.comparison_for(db, bid, str(e.id))
    assert c["status"] == "excluded" and "till was offline" in c["reason"]


# ------------------------------------------------------------------ owner plans (planned vs observed)
def test_planned_marketing_spend_is_compared_with_observed_spend_from_uploaded_campaigns(client, db_session):
    bid = _create_business(client)
    _upload_csv(client, bid, "marketing_campaigns", pd.DataFrame([
        {"Date": (T0 + timedelta(days=i)).isoformat(), "Channel": "Instagram", "Spend": 1000, "Impressions": 5000, "Clicks": 100, "Conversions": 5,
         "Attributed Revenue": 3000} for i in range(1, 8)]))
    plan = svc.create_owner_plan(db_session, bid, "marketing_spend", T0 + timedelta(days=1), T0 + timedelta(days=7), 8000.0, "Diwali push", "owner@x")
    assert plan.source_kind == "owner_plan" and plan.unit == "INR" and plan.comparable_to_actuals and plan.data_cutoff is None
    with clock.reference_date(T0 + timedelta(days=10)):
        o = svc.derive_observation(db_session, bid, str(plan.id))
    assert o.status == "observed" and float(o.value) == 7000.0 and o.source == "derived_from_marketing"
    c = svc.comparison_for(db_session, bid, str(plan.id))
    assert c["status"] == "evaluated" and c["signed_error"] == pytest.approx(1000.0)      # planned 8000, observed 7000
    with pytest.raises(ValidationFailedError, match="cannot be derived"):
        svc.derive_observation(db_session, bid, str(svc.create_owner_plan(db_session, bid, "orders", T0, T0 + timedelta(days=6), 10, None, "o").id))


# ------------------------------------------------------------------ decisions: responses, comparability, causal policy
@pytest.fixture()
def decision_world(client, db_session):
    model_registry_service.sync_from_file_registry(db_session)
    bid = _create_business(client)
    _seed_rich_business(client, bid)
    gid = _create_goal(client, bid, "Increase revenue by 10% in 2 months")
    d = client.post(f"/api/v1/businesses/{bid}/decisions/analyze", json={"goal_id": gid})
    assert d.status_code == 200, d.text
    return client, db_session, bid, d.json()["id"]


def test_accepting_a_recommendation_is_not_executing_it(decision_world):
    _, db, bid, did = decision_world
    assert svc.current_response(db, bid, did) is None and not svc.action_executed(db, bid, did)
    r = svc.record_response(db, bid, did, response="accepted", actor="owner@x")
    assert (r.response, r.action_status, r.seq) == ("accepted", "unknown", 1) and not svc.action_executed(db, bid, did)
    r2 = svc.record_response(db, bid, did, action_status="executed", action_start=date.today(), actor="owner@x")
    assert r2.seq == 2 and r2.response == "accepted" and svc.action_executed(db, bid, did)       # earlier fields carried forward
    assert [x.seq for x in db.query(type(r)).filter_by(decision_id=did).order_by(type(r).seq)] == [1, 2]   # append-only


@pytest.mark.parametrize("first,second,match", [
    (dict(response="rejected"), dict(action_status="executed", action_start=date.today()), "cannot be recorded as executed"),
    (dict(response="deferred"), dict(action_status="partially_executed", action_start=date.today()), "accept or modify"),
    (dict(response="accepted"), dict(action_status="executed"), "needs action_start"),
    (dict(response="accepted"), dict(action_status="executed", action_start=date.today() + timedelta(days=3)), "in the future"),
    (dict(response="accepted"), dict(action_status="executed", action_start=date.today() - timedelta(days=30)), "before the recommendation"),
    (dict(response="accepted"), dict(response="modified"), "needs modified_action"),
    (dict(response="accepted", note="same"), dict(note="same"), "already recorded"),
])
def test_contradictory_or_duplicate_responses_are_refused(decision_world, first, second, match):
    _, db, bid, did = decision_world
    svc.record_response(db, bid, did, actor="o", **first)
    with pytest.raises(ValidationFailedError, match=match):
        svc.record_response(db, bid, did, actor="o", **second)


def test_a_decision_figure_from_a_synthetic_model_is_stored_but_never_compared(decision_world):
    client, db, bid, did = decision_world
    exps = svc.expectations_from_decision(db, bid, did)
    assert exps and {e.metric for e in exps} <= {"units_sold", "revenue"}
    for e in exps:
        assert e.comparable_to_actuals is False and "not eligible for business-level figures" in e.comparability_reason
        assert e.source_kind == "decision" and e.horizon_days == svc.DECISION_HORIZON_DAYS and e.model_name
    assert [e.id for e in svc.expectations_from_decision(db, bid, did)] == [e.id for e in exps]     # materialised once
    e = exps[0]
    with clock.reference_date(e.window_end + timedelta(days=1)):
        svc.record_observation(db, bid, str(e.id), metric=e.metric, unit=e.unit, status="observed", value=100.0, actor="o")
    c = svc.comparison_for(db, bid, str(e.id))
    assert c["status"] == "excluded" and c["reason"].startswith("not_comparable") and "observed" in c   # observation kept, no error computed
    assert "signed_error" not in c


def test_a_decision_with_a_withheld_price_effect_creates_no_expectation(decision_world):
    _, db, bid, did = decision_world
    from app.models.decision import Decision

    d = db.get(Decision, did)
    d.expected_outcome_json = {**d.expected_outcome_json, "price_response": {"withheld": True}, "expected_units_sold": None, "expected_revenue": None}
    db.commit()
    assert svc.expectations_from_decision(db, bid, did) == []


def test_the_report_separates_accuracy_from_impact_and_never_claims_a_success_rate(decision_world):
    client, db, bid, did = decision_world
    svc.record_response(db, bid, did, response="accepted", actor="o")
    svc.record_response(db, bid, did, action_status="executed", action_start=date.today(), known_changes=["a festival week"],
                        evaluation_design="before_after", actor="o")
    e = svc.expectations_from_decision(db, bid, did)[0]
    with clock.reference_date(e.window_end + timedelta(days=1)):
        svc.record_observation(db, bid, str(e.id), metric=e.metric, unit=e.unit, status="observed", value=123.0, actor="o")
    rep = svc.report(db, bid)
    assert rep["decisions"]["recorded"] == 1 and rep["decisions"]["executed_confirmed"] == 1
    assert rep["decisions"]["latest_response"]["accepted"] == 1
    assert rep["expectations"]["not_comparable"] == rep["expectations"]["recorded"] > 0
    assert rep["comparisons"]["excluded_reasons"].get("not_comparable", 0) >= 1
    assert rep["forecast_accuracy"]["sample_size"] == 0 and "cannot yet be summarised" in rep["forecast_accuracy"]["statement"]
    imp = rep["business_impact"]
    assert imp["status"] == "not_evaluable" and "does not show that a recommendation helped" in imp["statement"] or "not show" in imp["statement"]
    one = imp["per_decision"][0]
    assert one["causal_impact"] == "not_identified" and one["action_recorded_as"] == "executed" and one["other_known_changes"] == ["a festival week"]
    assert one["declared_evaluation_design"] == "before_after"       # declared, and still not identified: no control observations
    flat = repr(rep)
    assert "success_rate" not in flat and "percent_successful" not in flat
    assert rep["legacy_free_form_outcomes"]["recorded"] == 0


def test_the_report_with_no_records_is_safe_and_says_so(client, db_session):
    bid = _create_business(client)
    rep = svc.report(db_session, bid)
    assert rep["decisions"]["recorded"] == 0 and rep["expectations"]["recorded"] == 0 and rep["comparisons"]["details"] == []
    assert rep["forecast_accuracy"]["groups"] == [] and rep["forecast_accuracy"]["date_range"] is None
    assert rep["business_impact"]["status"] == "not_evaluable" and rep["business_impact"]["per_decision"] == []


def test_accuracy_is_summarised_only_with_enough_comparable_cases_and_grouped_by_horizon(biz):
    client, db, bid = biz
    exps = []
    for k in range(6):                                  # forecast, then the week it forecast arrives, then forecast again
        cutoff = T0 + timedelta(days=7 * k)
        with clock.reference_date(cutoff):
            exps.append(svc.snapshot_forecast(db, bid, 7))
        assert exps[-1].data_cutoff == cutoff
        _later_sales(client, bid, cutoff + timedelta(days=1), cutoff + timedelta(days=7), seed=20 + k)
    with clock.reference_date(T0 + timedelta(days=60)):
        for e in exps:
            assert svc.derive_observation(db, bid, str(e.id)).status == "observed"
    rep = svc.report(db, bid)
    assert rep["comparisons"]["by_status"]["evaluated"] == 6
    grp = rep["forecast_accuracy"]["groups"][0]
    assert (grp["metric"], grp["horizon"], grp["n"]) == ("units_sold", "1-7 days", 6)
    assert grp["summarised"] is True and grp["mean_abs_error"] >= 0 and grp["mean_abs_pct_error"] is not None
    assert rep["forecast_accuracy"]["date_range"][0] == (T0 + timedelta(days=1)).isoformat()
    assert "6 comparable forecast(s)" in rep["forecast_accuracy"]["statement"]
    assert rep["forecast_accuracy"]["sample_size"] == 6


def test_fewer_than_the_minimum_comparable_cases_are_not_summarised(biz):
    client, db, bid = biz
    e = _snapshot(db, bid)
    _later_sales(client, bid, T0 + timedelta(days=1), T0 + timedelta(days=7))
    with clock.reference_date(T0 + timedelta(days=10)):
        svc.derive_observation(db, bid, str(e.id))
    g = svc.report(db, bid)["forecast_accuracy"]
    assert g["sample_size"] == 1 and "cannot yet be summarised" in g["statement"]
    assert g["groups"][0]["summarised"] is False and g["groups"][0]["mean_abs_error"] is None and "not summarised" in g["groups"][0]["note"]


def test_recording_an_outcome_does_not_change_any_model(decision_world):
    client, db, bid, did = decision_world
    before = sorted((m.model_name, m.version, m.status) for m in db.query(MLModel).all())
    svc.record_response(db, bid, did, response="accepted", actor="o")
    svc.record_response(db, bid, did, action_status="executed", action_start=date.today(), actor="o")
    e = svc.expectations_from_decision(db, bid, did)[0]
    with clock.reference_date(e.window_end + timedelta(days=1)):
        svc.record_observation(db, bid, str(e.id), metric=e.metric, unit=e.unit, status="observed", value=50.0, actor="o")
    assert sorted((m.model_name, m.version, m.status) for m in db.query(MLModel).all()) == before


def test_legacy_free_form_outcomes_are_counted_as_unverified(decision_world):
    client, db, bid, did = decision_world
    r = client.post(f"/api/v1/businesses/{bid}/decisions/{did}/outcome", json={"actual_outcome": {"revenue": 12345.0}})
    assert r.status_code == 200, r.text
    rep = svc.report(db, bid)
    assert rep["legacy_free_form_outcomes"]["recorded"] == 1 and "unverified" in rep["legacy_free_form_outcomes"]["status"]
    assert db.query(DecisionOutcome).count() == 1
    assert db.query(OutcomeObservation).count() == 0        # the legacy path never creates a verified observation


def test_unknown_ids_are_not_found(biz):
    _, db, bid = biz
    for fn, args in ((svc.comparison_for, (db, bid, "00000000-0000-0000-0000-000000000000")),
                     (svc.expectations_from_decision, (db, bid, "00000000-0000-0000-0000-000000000000"))):
        with pytest.raises(NotFoundError):
            fn(*args)


def test_a_demo_business_is_labelled_synthetic_everywhere_it_appears(client, db_session):
    from app.models.business import Business

    bid = _create_business(client)
    _upload_csv(client, bid, "sales", _rows(T0 - timedelta(days=119), T0))
    b = db_session.get(Business, bid)
    b.description = "Synthetic demonstration data generated for a walkthrough"
    db_session.commit()
    with clock.reference_date(T0):
        e = svc.snapshot_forecast(db_session, bid, 7)
    _upload_csv(client, bid, "sales", _rows(T0 + timedelta(days=1), T0 + timedelta(days=7), seed=3))
    with clock.reference_date(T0 + timedelta(days=9)):
        o = svc.derive_observation(db_session, bid, str(e.id))
    assert e.provenance == "demo_synthetic" and o.provenance == "demo_synthetic"
    rep = svc.report(db_session, bid)
    assert rep["data_provenance"] == {"demo_synthetic": 2}
    assert any("demo_synthetic" in x and "never evidence about real businesses" in x for x in rep["limitations"])


def test_an_observation_id_from_another_business_cannot_be_corrected(client, db_session):
    a, b = _create_business(client), _create_business(client)
    _upload_csv(client, a, "sales", _rows(T0 - timedelta(days=60), T0))
    with clock.reference_date(T0):
        e = svc.snapshot_forecast(db_session, a, 7)
    with clock.reference_date(T0 + timedelta(days=9)):
        o = svc.record_observation(db_session, a, str(e.id), metric="units_sold", unit="units", status="observed", value=100.0, actor="t")
        with pytest.raises(NotFoundError):
            svc.correct_observation(db_session, b, str(o.id), reason="not mine", value=1.0, actor="t")
        with pytest.raises(NotFoundError):
            svc.record_observation(db_session, b, str(e.id), metric="units_sold", unit="units", status="observed", value=1.0, actor="t")
        with pytest.raises(NotFoundError):
            svc.comparison_for(db_session, b, str(e.id))
