"""KPI monitoring, business health and smart alerts. Synthetic software-test data only."""
from datetime import date, datetime, timedelta, timezone

import pytest

from app.core import clock
from app.core.errors import NotFoundError
from app.services import alert_service as al
from app.services import health_service as hs
from app.services import kpi_monitor_service as kms
from tests import platform_support as ps

END = date(2025, 3, 31)


@pytest.fixture()
def world(db_session):
    bid = ps.business(db_session)
    pids = ps.products(db_session, bid)
    return db_session, bid, pids


# ------------------------------------------------------------------------------------------------ KPI monitoring
def test_kpi_values_are_exact_and_follow_the_selected_window(world):
    db, bid, pids = world
    ps.two_period_sales(db, bid, pids, END, prev_daily=2, cur_daily=3)  # 31 days x 3 units x 10 = 930 now; 31 x 2 x 10 = 620 before
    out = kms.list_kpis(db, bid, 30, anchor="latest")
    k = {x["key"]: x for x in out["kpis"]}
    assert out["period"]["end"] == "2025-03-31" and out["period"]["anchor"] == "latest"
    assert k["revenue"]["value"] == 930.0 and k["revenue"]["previous_value"] == 620.0
    assert k["revenue"]["change_pct"] == pytest.approx(0.5, abs=1e-4)
    assert k["orders"]["value"] == 31.0
    assert k["profit"]["value"] == pytest.approx(930 - 3 * 31 * 6)  # Alpha cost 6
    assert k["marketing_roi"]["value"] is None and k["marketing_roi"]["data_quality"]["status"] == "unavailable"
    for key in ("revenue", "orders", "profit"):
        assert k[key]["definition"] and k[key]["source"] and k[key]["unit"]


def test_status_comes_only_from_a_configured_target_and_a_disclosed_rule(world):
    db, bid, pids = world
    ps.two_period_sales(db, bid, pids, END, 2, 3)
    out = {k["key"]: k for k in kms.list_kpis(db, bid, 30, "latest")["kpis"]}
    assert out["revenue"]["status"] == "no_target" and "No target" in out["revenue"]["status_rule"]  # never green/red without a target
    kms.set_target(db, bid, "revenue", 900, "higher", 30)
    kms.set_target(db, bid, "marketing_spend", 100, "lower", 30)
    kms.set_target(db, bid, "orders", 1000, "higher", 30)
    out = {k["key"]: k for k in kms.list_kpis(db, bid, 30, "latest")["kpis"]}
    assert out["revenue"]["status"] == "met" and "at least" in out["revenue"]["status_rule"]
    assert out["orders"]["status"] == "not_met"
    assert out["marketing_spend"]["status"] == "no_data"  # no spend recorded: neither met nor missed
    kms.set_target(db, bid, "revenue", 5000, "higher", 30)  # update, not duplicate
    assert len(kms.get_targets(db, bid)) == 3
    assert {k["key"]: k for k in kms.list_kpis(db, bid, 30, "latest")["kpis"]}["revenue"]["status"] == "not_met"
    kms.delete_target(db, bid, "revenue")
    assert "revenue" not in kms.get_targets(db, bid)


def test_target_on_a_different_period_is_judged_on_its_own_period(world):
    db, bid, pids = world
    ps.two_period_sales(db, bid, pids, END, 2, 3)
    kms.set_target(db, bid, "revenue", 500, "higher", 7)  # 8 inclusive days x 30 = 240 < 500
    r = {k["key"]: k for k in kms.list_kpis(db, bid, 30, "latest")["kpis"]}["revenue"]
    assert r["target_period_value"] == 240.0 and r["status"] == "not_met"


@pytest.mark.parametrize("bad", [{"value": float("nan")}, {"value": 1e15}, {"value": 1, "period_days": 5}, {"value": 1, "direction": "up"}])
def test_invalid_targets_are_rejected(world, bad):
    db, bid, _ = world
    with pytest.raises(kms.KpiValidationError):
        kms.set_target(db, bid, "revenue", bad["value"], bad.get("direction"), bad.get("period_days", 30))


def test_unknown_kpi_and_bad_period_are_errors(world):
    db, bid, _ = world
    with pytest.raises(NotFoundError):
        kms.set_target(db, bid, "nonsense", 1, None, 30)
    with pytest.raises(kms.KpiValidationError):
        kms.list_kpis(db, bid, 45)
    with pytest.raises(kms.KpiValidationError):
        kms.list_kpis(db, bid, 30, "yesterday")


def test_stale_data_is_flagged_against_today_and_empty_periods_are_no_data(world):
    db, bid, pids = world
    ps.two_period_sales(db, bid, pids, END, 2, 3)
    stale = kms.list_kpis(db, bid, 30, "latest")  # real clock is long after the 2025 data
    assert stale["stale_days"] > kms.STALE_AFTER_DAYS
    assert {k["key"]: k for k in stale["kpis"]}["revenue"]["data_quality"]["status"] == "stale"
    empty = {k["key"]: k for k in kms.list_kpis(db, bid, 30, "today")["kpis"]}  # window ends today: no sales in it
    assert empty["revenue"]["value"] is None and empty["revenue"]["data_quality"]["status"] == "no_data"


def test_trend_has_only_days_with_records_and_rejects_unsupported_kpis(world):
    db, bid, pids = world
    pid = pids["Alpha"]
    for d in (END, END - timedelta(days=3)):
        ps.sale(db, bid, pid, d, 2, 10)
    db.commit()
    t = kms.trend(db, bid, "revenue", 30, "latest")
    assert [p["date"] for p in t["points"]] == ["2025-03-28", "2025-03-31"] and t["n_points"] == 2  # the gap is not zero-filled
    with pytest.raises(kms.KpiValidationError):
        kms.trend(db, bid, "profit", 30, "latest")


# ------------------------------------------------------------------------------------------------ business health
def test_health_without_enough_inputs_gives_an_assessment_not_a_score(world):
    db, bid, pids = world
    ps.two_period_sales(db, bid, pids, END, 2, 3)
    pids_alpha_only = None  # noqa: F841
    # remove costs so profit margin is unavailable; no stock, no customers
    from app.models.product import Product

    db.query(Product).filter(Product.business_id == bid).update({"unit_cost": None})
    db.commit()
    h = hs.assess(db, bid, 30, "latest", save=False)
    avail = {c["key"]: c["available"] for c in h["components"]}
    assert avail == {"sales_trend": True, "data_freshness": True, "profit_margin": False, "stock_health": False, "customer_activity": False}
    assert h["composite_score"] is None and "at least 3" in h["composite_unavailable_reason"]
    assert all(c["unavailable_reason"] for c in h["components"] if not c["available"])  # missing is explained, never scored as poor
    assert h["version"] == "health-v1" and h["limitations"]


def test_health_composite_is_a_weighted_average_of_available_components_and_renormalises(world):
    db, bid, pids = world
    ps.two_period_sales(db, bid, pids, END, 2, 3)
    ps.customers(db, bid, 20, END)
    ps.stock(db, bid, pids["Alpha"], 50, 10, END)
    h = hs.assess(db, bid, 30, "latest", save=False)
    c = {x["key"]: x for x in h["components"]}
    assert all(c[k]["available"] for k in ("sales_trend", "data_freshness", "profit_margin", "stock_health", "customer_activity"))
    assert c["sales_trend"]["score"] == pytest.approx(60 + 40 * min(0.5 / 0.2, 1))  # +50% -> capped at 100
    assert c["stock_health"]["score"] == 100.0 and c["customer_activity"]["score"] == pytest.approx(70.0)
    expected = sum(x["weight"] * x["score"] for x in h["components"]) / sum(x["weight"] for x in h["components"])
    assert h["composite_score"] == pytest.approx(round(expected, 1))
    assert sum(x["effective_weight"] for x in h["components"]) == pytest.approx(1.0, abs=0.01)
    # dropping a component does not lower the score just because it is missing: weights renormalise over what remains
    from app.models.inventory import InventoryRecord

    db.query(InventoryRecord).delete()
    db.commit()
    h2 = hs.assess(db, bid, 30, "latest", save=False)
    assert {x["key"]: x for x in h2["components"]}["stock_health"]["available"] is False
    assert h2["composite_score"] is not None and h2["available_weight_share"] < h["available_weight_share"]


def test_health_snapshot_is_saved_with_version_and_history(world):
    db, bid, pids = world
    ps.two_period_sales(db, bid, pids, END, 2, 3)
    ps.customers(db, bid, 20, END)
    hs.assess(db, bid, 30, "latest", save=True)
    hist = hs.history(db, bid)
    assert len(hist) == 1 and hist[0]["version"] == "health-v1" and hist[0]["period_days"] == 30


def test_health_declines_map_to_low_scores_and_levels_use_disclosed_thresholds(world):
    db, bid, pids = world
    ps.two_period_sales(db, bid, pids, END, 3, 2)  # -33%
    ps.customers(db, bid, 20, END)
    h = hs.assess(db, bid, 30, "latest", save=False)
    st = {c["key"]: c for c in h["components"]}["sales_trend"]
    assert st["score"] == 0.0  # -20% or worse = 0
    assert h["level"] in ("Good", "Fair", "Needs attention") and h["level_thresholds"][0] == {"min": 75.0, "label": "Good"}


# ------------------------------------------------------------------------------------------------ alerts
NOW = datetime(2025, 4, 1, 12, 0, tzinfo=timezone.utc)


def _titles(db, bid, status="active"):
    return sorted(a["rule_key"] for a in al.list_alerts(db, bid, status))


def test_sales_drop_alert_has_evidence_rule_and_severity(world):
    db, bid, pids = world
    ps.two_period_sales(db, bid, pids, END, 4, 2)  # -50%: more than 2x the 15% threshold -> high
    al.evaluate(db, bid, "latest", now=NOW)
    a = next(x for x in al.list_alerts(db, bid) if x["rule_key"] == "sales_drop")
    assert a["severity"] == "high" and a["metric_value"] == pytest.approx(-0.5, abs=1e-3) and a["threshold"] == -0.15
    assert a["evidence"]["previous_sales"] > a["evidence"]["current_sales"] and a["period_end"] == "2025-03-31"
    assert a["severity_rule"] and a["suggested_action"] and a["first_seen"]
    assert "stale_data" in _titles(db, bid)  # real clock is long after the data


def test_no_alert_is_invented_when_nothing_is_wrong(world):
    db, bid, pids = world
    ps.two_period_sales(db, bid, pids, END, 2, 3)
    with clock.reference_date(END):  # data is fresh relative to the (pinned) clock
        res = al.evaluate(db, bid, "latest", now=NOW)
    assert res["created"] == 0 and al.list_alerts(db, bid, "active") == []


def test_repeated_evaluation_does_not_flood_duplicates_and_conditions_clear(world):
    db, bid, pids = world
    ps.two_period_sales(db, bid, pids, END, 4, 2)
    with clock.reference_date(END):
        first = al.evaluate(db, bid, "latest", now=NOW)
        second = al.evaluate(db, bid, "latest", now=NOW + timedelta(hours=1))
    assert first["created"] == 2 and second["created"] == 0 and second["refreshed"] == 2  # total sales drop + the one product that fell
    assert len([a for a in al.list_alerts(db, bid, "active") if a["rule_key"] == "sales_drop"]) == 1
    # the condition goes away: add many sales in the current window
    for i in range(31):
        ps.sale(db, bid, pids["Alpha"], END - timedelta(days=i), 20, 10)
    db.commit()
    with clock.reference_date(END):
        third = al.evaluate(db, bid, "latest", now=NOW + timedelta(hours=2))
    assert third["cleared"] == 2 and _titles(db, bid) == [] and "sales_drop" in _titles(db, bid, "cleared")


def test_resolved_alert_is_not_raised_again_during_the_cooldown_but_is_afterwards(world):
    db, bid, pids = world
    ps.two_period_sales(db, bid, pids, END, 4, 2)
    with clock.reference_date(END):
        al.evaluate(db, bid, "latest", now=NOW)
        a = al.list_alerts(db, bid)[0]
        al.set_status(db, bid, a["id"], "resolved", now=NOW)
        again = al.evaluate(db, bid, "latest", now=NOW + timedelta(hours=2))
        assert again["created"] == 0 and again["suppressed_by_cooldown"] == 1
        later = al.evaluate(db, bid, "latest", now=NOW + timedelta(hours=al.COOLDOWN_HOURS + 1))
    assert later["created"] == 1


def test_read_state_and_tenant_isolation(world):
    db, bid, pids = world
    ps.two_period_sales(db, bid, pids, END, 4, 2)
    al.evaluate(db, bid, "latest", now=NOW)
    a = al.list_alerts(db, bid)[0]
    assert al.set_status(db, bid, a["id"], "read")["status"] == "read"
    other = ps.business(db, "Other")
    with pytest.raises(NotFoundError):
        al.set_status(db, other, a["id"], "read")  # another business cannot touch it
    assert al.list_alerts(db, other) == []
    with pytest.raises(al.AlertValidationError):
        al.set_status(db, bid, a["id"], "deleted")


def test_thresholds_are_configurable_and_validated_and_disabled_rules_do_not_fire(world):
    db, bid, pids = world
    ps.two_period_sales(db, bid, pids, END, 10, 9)  # -10%
    with clock.reference_date(END):
        assert al.evaluate(db, bid, "latest", now=NOW)["created"] == 0  # below the 15% default
        al.set_rule(db, bid, "sales_drop", True, 0.05)
        assert al.evaluate(db, bid, "latest", now=NOW)["created"] == 1
        al.set_rule(db, bid, "sales_drop", False, 0.05)
        out = al.evaluate(db, bid, "latest", now=NOW + timedelta(hours=1))
    assert out["created"] == 0 and out["cleared"] == 0  # disabling leaves existing alerts alone (rule not evaluated)
    for bad in (0, -1, 1.5):
        with pytest.raises(al.AlertValidationError):
            al.set_rule(db, bid, "sales_drop", True, bad)
    with pytest.raises(NotFoundError):
        al.set_rule(db, bid, "made_up", True, 1)
    with pytest.raises(al.AlertValidationError):
        al.set_rule(db, bid, "low_stock", True, 3)  # no threshold to configure


def test_kpi_target_low_stock_and_validation_alerts(world):
    db, bid, pids = world
    ps.two_period_sales(db, bid, pids, END, 2, 3)
    kms.set_target(db, bid, "revenue", 5000, "higher", 30)
    ps.stock(db, bid, pids["Alpha"], 0, 10, END)
    ps.sale(db, bid, pids["Alpha"], END, -2, 10)  # invalid quantity -> validation failure
    db.commit()
    from app.services import data_platform_service as dps

    dps.run_validation(db, bid)
    with clock.reference_date(END):
        al.evaluate(db, bid, "latest", now=NOW)
    got = {a["rule_key"]: a for a in al.list_alerts(db, bid)}
    assert got["kpi_target_missed"]["severity"] == "high"  # >25% away from target
    assert got["low_stock"]["severity"] == "high"  # zero stock
    assert got["validation_failed"]["severity"] == "high" and got["validation_failed"]["evidence"]["fail"] >= 1


def test_product_decline_ignores_small_products(world):
    db, bid, pids = world
    for i in range(31):
        ps.sale(db, bid, pids["Beta"], END - timedelta(days=i), 1, 20)  # steady
    for i in range(32, 63):
        ps.sale(db, bid, pids["Beta"], END - timedelta(days=i), 1, 20)
        ps.sale(db, bid, pids["Alpha"], END - timedelta(days=i), 10, 10)  # big before, nothing now
    ps.sale(db, bid, pids["Gamma"], END - timedelta(days=40), 1, 5)  # tiny share before, gone now
    db.commit()
    with clock.reference_date(END):
        al.evaluate(db, bid, "latest", now=NOW)
    prods = [a["evidence"]["product"] for a in al.list_alerts(db, bid) if a["rule_key"] == "product_decline"]
    assert prods == ["Alpha"]


def test_database_refuses_two_active_alerts_for_one_condition(db_session):
    """A concurrent double check (two tabs, or a page effect firing twice) can never leave two active copies of one alert."""
    from sqlalchemy.exc import IntegrityError

    from app.models.platform import Alert

    bid = ps.business(db_session)
    now = datetime.now(timezone.utc)

    def alert(status):
        return Alert(business_id=bid, rule_key="stale_data", dedupe_key="stale", severity="low", status=status, title="t", message="m", first_seen=now, last_seen=now)

    db_session.add(alert("open"))
    db_session.commit()
    db_session.add(alert("read"))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
    db_session.add(alert("resolved"))  # past occurrences do not block a later one
    db_session.add(alert("cleared"))
    db_session.commit()
    assert db_session.query(Alert).filter(Alert.business_id == bid).count() == 3
