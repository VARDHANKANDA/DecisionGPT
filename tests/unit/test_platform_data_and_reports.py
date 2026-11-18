"""Data platform (profiling, cleaning, validation, transformation, pipeline) and saved reports. Synthetic software-test data only."""
from datetime import date, timedelta

import pytest

from app.core.errors import NotFoundError, ValidationFailedError
from app.models.platform import DataPrepRun
from app.models.product import Product
from app.models.sale import Sale
from app.services import data_platform_service as dps
from app.services import report_service as rs
from tests import platform_support as ps

D = date(2025, 3, 1)


@pytest.fixture()
def world(db_session):
    bid = ps.business(db_session)
    pids = ps.products(db_session, bid)
    return db_session, bid, pids


def _sales_sum(db, bid):
    return round(sum(float(s.revenue) for s in db.query(Sale).filter(Sale.business_id == bid)), 2), db.query(Sale).filter(Sale.business_id == bid).count()


# ------------------------------------------------------------------------------------------------ profiling
def test_profile_reports_actual_statistics_missing_duplicates_and_outlier_candidates(world):
    db, bid, pids = world
    for i in range(30):
        ps.sale(db, bid, pids["Alpha"], D + timedelta(days=i), 1 + i % 4, 10)
    ps.sale(db, bid, pids["Alpha"], D, 1, 10)  # exact duplicate of the first row
    ps.sale(db, bid, pids["Beta"], D, 500, 20)  # an outlier candidate
    ps.sale(db, bid, pids["Gamma"], D + timedelta(days=2), 1, 5, discount=0)
    db.commit()
    p = dps.profile(db, bid, "sales")
    assert p["rows"] == 33 and p["columns"] == 7
    q = next(c for c in p["column_profiles"] if c["key"] == "quantity")
    assert q["inferred_type"] == "number" and q["max"] == 500 and q["min"] == 1 and q["missing"] == 0
    assert round(q["mean"], 2) == round((sum(1 + i % 4 for i in range(30)) + 1 + 500 + 1) / 33, 2)
    d = next(c for c in p["column_profiles"] if c["key"] == "sale_date")
    assert d["date_min"] == "2025-03-01" and d["date_max"] == "2025-03-30"
    assert p["duplicate_rows"] == 1
    out = next(o for o in p["outlier_candidates"] if o["column"] == "quantity")
    assert out["candidates"] >= 1 and "Candidates only" in out["note"]
    prod = next(c for c in p["column_profiles"] if c["key"] == "product")
    assert prod["inferred_type"] == "text" and {v["value"] for v in prod["top_values"]} >= {"Alpha", "Beta"}


def test_profiling_empty_table_is_honest(world):
    db, bid, _ = world
    p = dps.profile(db, bid, "sales")
    assert p["rows"] == 0 and p["duplicate_rows"] == 0 and p["invalid_or_inconsistent"] == []


def test_preview_search_and_pagination(world):
    db, bid, pids = world
    for i in range(30):
        ps.sale(db, bid, pids["Alpha" if i % 2 else "Beta"], D + timedelta(days=i), 1, 10)
    db.commit()
    page = dps.table_preview(db, bid, "sales", 0, 10)
    assert page["total"] == 30 and len(page["rows"]) == 10
    hit = dps.table_preview(db, bid, "sales", 0, 100, "beta")
    assert hit["total"] == 15 and all("Beta" == r["values"]["product"] for r in hit["rows"])
    assert dps.table_preview(db, bid, "sales", 0, 10, "zzz-no-match")["total"] == 0
    with pytest.raises(NotFoundError):
        dps.table_preview(db, bid, "not_a_table")


# ------------------------------------------------------------------------------------------------ cleaning
def _dupes_world(db, bid, pids):
    ps.sale(db, bid, pids["Alpha"], D, 2, 10)
    ps.sale(db, bid, pids["Alpha"], D, 2, 10)  # identical to the previous
    ps.sale(db, bid, pids["Alpha"], D, 2, 10)  # identical again
    ps.sale(db, bid, pids["Beta"], D, 1, 20)
    db.commit()


def test_duplicates_are_proposed_never_applied_silently_and_need_confirmation(world):
    db, bid, pids = world
    _dupes_world(db, bid, pids)
    before = _sales_sum(db, bid)
    props = {p["id"]: p for p in dps.cleaning_proposals(db, bid, "sales")}
    p = props["dedupe:sales"]
    assert p["affected_rows"] == 2 and p["can_apply"] and "separate genuine transactions" in p["risk"] and p["preview"]
    assert _sales_sum(db, bid) == before  # proposing changes nothing
    with pytest.raises(ValidationFailedError):
        dps.apply_cleaning(db, bid, "dedupe:sales", confirm=False)
    assert _sales_sum(db, bid) == before


def test_applied_duplicate_removal_is_recorded_and_exactly_reversible(world):
    db, bid, pids = world
    _dupes_world(db, bid, pids)
    before = _sales_sum(db, bid)
    ids_before = {s.id for s in db.query(Sale).filter(Sale.business_id == bid)}
    run = dps.apply_cleaning(db, bid, "dedupe:sales", confirm=True)
    assert run["affected_rows"] == 2 and run["status"] == "applied" and run["reversible"]
    assert _sales_sum(db, bid)[1] == 2
    assert not any(p["id"] == "dedupe:sales" for p in dps.cleaning_proposals(db, bid, "sales"))  # the issue is gone after applying
    hist = dps.history(db, bid, stage="clean")
    assert hist[0]["id"] == run["id"] and hist[0]["summary"]["affected_rows"] == 2
    rev = dps.revert_run(db, bid, run["id"])
    assert rev["restored_rows"] == 2 and rev["status"] == "reverted"
    assert _sales_sum(db, bid) == before and {s.id for s in db.query(Sale).filter(Sale.business_id == bid)} == ids_before  # same rows, same ids
    with pytest.raises(dps.DataPlatformError):
        dps.revert_run(db, bid, run["id"])  # cannot revert twice


def test_whitespace_and_category_variants_are_proposed_applied_and_reverted(world):
    db, bid, pids = world
    db.add(Product(business_id=bid, external_product_id="X1", name="Delta  Widget ", category="Home", selling_price=5))
    db.add(Product(business_id=bid, external_product_id="X2", name="Epsilon", category="home", selling_price=5))
    db.add(Product(business_id=bid, external_product_id="X3", name="Zeta", category="Home", selling_price=5))
    db.commit()
    ids = {p["id"]: p for p in dps.cleaning_proposals(db, bid, "products")}
    assert ids["trim:products.name"]["affected_cells"] == 1 and ids["trim:products.name"]["preview"][0]["after"] == "Delta Widget"
    cat = ids["case:products.category"]
    assert cat["mapping"] == {"home": "Home"} and cat["affected_rows"] == 1
    run = dps.apply_cleaning(db, bid, "case:products.category", True)
    assert {p.category for p in db.query(Product).filter(Product.business_id == bid, Product.external_product_id.in_(["X1", "X2", "X3"]))} == {"Home"}
    dps.revert_run(db, bid, run["id"])
    assert db.query(Product).filter(Product.business_id == bid, Product.category == "home").count() == 1
    dps.apply_cleaning(db, bid, "trim:products.name", True)
    assert db.query(Product).filter(Product.business_id == bid, Product.name == "Delta Widget").count() == 1


def test_records_that_others_depend_on_are_not_deleted_automatically(world):
    db, bid, _ = world
    ps.customers(db, bid, 3, D)
    from app.models.customer import Customer

    dup = db.query(Customer).filter(Customer.business_id == bid).first()
    db.add(Customer(business_id=bid, external_customer_id=dup.external_customer_id, first_purchase_date=dup.first_purchase_date, last_purchase_date=dup.last_purchase_date,
                    purchase_frequency=dup.purchase_frequency, monetary_value=dup.monetary_value))
    db.commit()
    p = next(x for x in dps.cleaning_proposals(db, bid, "customers") if x["id"] == "dedupe:customers")
    assert p["can_apply"] is False and "blocked_reason" in p
    with pytest.raises(dps.DataPlatformError):
        dps.apply_cleaning(db, bid, "dedupe:customers", True)


def test_invalid_rows_proposal_excludes_only_the_invalid_rows_and_can_be_undone(world):
    db, bid, pids = world
    ps.sale(db, bid, pids["Alpha"], D, 2, 10)
    ps.sale(db, bid, pids["Alpha"], D + timedelta(days=1), 0, 10, revenue=0)  # zero quantity
    ps.sale(db, bid, pids["Alpha"], D + timedelta(days=2), -3, 10, revenue=-30)  # negative
    db.commit()
    p = next(x for x in dps.cleaning_proposals(db, bid, "sales") if x["id"] == "invalid:sales.quantity_positive")
    assert p["affected_rows"] == 2
    run = dps.apply_cleaning(db, bid, p["id"], True)
    assert _sales_sum(db, bid) == (20.0, 1)
    dps.revert_run(db, bid, run["id"])
    assert _sales_sum(db, bid)[1] == 3


def test_missing_values_are_reported_but_never_filled(world):
    db, bid, pids = world
    from app.models.product import Product as P

    db.add(P(business_id=bid, external_product_id="M1", name="Missing", category=None, selling_price=5))
    db.commit()
    m = next(x for x in dps.cleaning_proposals(db, bid, "products") if x["id"] == "missing:products")
    assert m["can_apply"] is False and "does not fill missing values" in m["action"]
    with pytest.raises(dps.DataPlatformError):
        dps.apply_cleaning(db, bid, "missing:products", True)


def test_cleaning_is_scoped_to_the_business(world):
    db, bid, pids = world
    _dupes_world(db, bid, pids)
    other = ps.business(db, "Other")
    assert dps.cleaning_proposals(db, other, "sales") == []
    run = dps.apply_cleaning(db, bid, "dedupe:sales", True)
    with pytest.raises(NotFoundError):
        dps.revert_run(db, other, run["id"])
    with pytest.raises(NotFoundError):
        dps.apply_cleaning(db, bid, "dedupe:../etc/passwd", True)


# ------------------------------------------------------------------------------------------------ validation
def test_validation_pass_warn_fail_and_empty_tables_are_not_passes(db_session):
    db = db_session
    bid = ps.business(db)
    empty = dps.run_validation(db, bid)
    assert empty["overall"] == "not_run" and empty["results"] == [] and "sales" in empty["tables_skipped_empty"]  # nothing checked -> not a pass
    pids = ps.products(db, bid)
    for i in range(3):
        ps.sale(db, bid, pids["Alpha"], D + timedelta(days=i), 2, 10)
    db.commit()
    ok = dps.run_validation(db, bid, ["sales"])
    assert ok["overall"] == "pass" and ok["fail"] == 0 and ok["warn"] == 0 and ok["pass"] > 5
    assert all(r["status"] == "pass" and r["sample"] == [] for r in ok["results"])
    ps.sale(db, bid, pids["Alpha"], D, 2, 10)  # exact duplicate -> warning
    ps.sale(db, bid, pids["Alpha"], date.today() + timedelta(days=30), 1, 10)  # future date -> failure
    ps.sale(db, bid, pids["Alpha"], D, 5, 10, revenue=999)  # total disagrees with qty x price -> warning
    db.commit()
    res = dps.run_validation(db, bid, ["sales"])
    by = {r["id"]: r for r in res["results"]}
    assert res["overall"] == "fail" and by["sales.date_not_future"]["status"] == "fail" and by["sales.date_not_future"]["affected"] == 1
    assert by["sales.no_exact_duplicates"]["status"] == "warn" and by["sales.total_consistent"]["status"] == "warn"
    assert by["sales.total_consistent"]["sample"] and by["sales.total_consistent"]["next_step"]
    assert db.query(DataPrepRun).filter(DataPrepRun.business_id == bid, DataPrepRun.stage == "validate").count() == 3  # every run is recorded


def test_validation_rules_cover_other_tables(world):
    db, bid, pids = world
    ps.customers(db, bid, 3, D)
    from app.models.customer import Customer
    from app.models.marketing import MarketingCampaign

    db.add(Customer(business_id=bid, external_customer_id="C0", first_purchase_date=D, last_purchase_date=D - timedelta(days=5), purchase_frequency=1, monetary_value=1))  # id repeated, dates reversed
    db.add(MarketingCampaign(business_id=bid, campaign_date=D, channel="A", campaign_name="x", spend=-5, impressions=10, clicks=20, conversions=30))
    db.commit()
    res = {r["id"]: r for r in dps.run_validation(db, bid, ["customers", "marketing_campaigns", "products"])["results"]}
    assert res["customers.id_unique"]["status"] == "fail" and res["customers.dates_ordered"]["status"] == "warn"
    assert res["marketing.spend_valid"]["status"] == "fail" and res["marketing.funnel_ordered"]["status"] == "warn"
    assert res["products.name_present"]["status"] == "pass"


# ------------------------------------------------------------------------------------------------ transformation
def test_transform_preview_apply_and_undo_with_validation(world):
    db, bid, pids = world
    for name, cat in (("P1", "snacks"), ("P2", "Snacks"), ("P3", "SNACKS")):
        db.add(Product(business_id=bid, external_product_id=name, name=name, category=cat, selling_price=5))
    db.commit()
    op = {"id": "style:products.category", "kind": "standardise_style", "table": "products", "column": "category", "style": "title"}
    pre = dps.transform_preview(db, bid, op)
    assert pre["affected_rows"] == 2 and {x["after"] for x in pre["preview"]} == {"Snacks"} and pre["can_apply"]
    with pytest.raises(ValidationFailedError):
        dps.apply_transform(db, bid, op, confirm=False)
    run = dps.apply_transform(db, bid, op, confirm=True)
    assert run["status"] == "applied" and run["affected_rows"] == 2 and run["summary"]["validation_after"] == run["summary"]["validation_before"]
    assert {p.category for p in db.query(Product).filter(Product.business_id == bid, Product.external_product_id.in_(["P1", "P2", "P3"]))} == {"Snacks"}
    dps.revert_run(db, bid, run["id"])
    assert {p.category for p in db.query(Product).filter(Product.business_id == bid, Product.external_product_id.in_(["P1", "P2", "P3"]))} == {"snacks", "Snacks", "SNACKS"}


def test_map_values_recalculate_and_unsupported_operations(world):
    db, bid, pids = world
    ps.sale(db, bid, pids["Alpha"], D, 2, 10, revenue=25)  # stored total disagrees with 2 x 10
    ps.sale(db, bid, pids["Alpha"], D + timedelta(days=1), 3, 10)
    db.commit()
    rec = {"id": "recalc:sales.revenue", "kind": "recalculate_totals", "table": "sales", "column": "revenue"}
    pre = dps.transform_preview(db, bid, rec)
    assert pre["affected_rows"] == 1 and pre["preview"][0] == {"id": pre["preview"][0]["id"], "before": 25.0, "after": 20.0}
    dps.apply_transform(db, bid, rec, True)
    assert _sales_sum(db, bid) == (50.0, 2)
    mp = {"id": "map:products.category", "kind": "map_values", "table": "products", "column": "category", "mapping": {"General": "Misc"}}
    assert dps.transform_preview(db, bid, mp)["affected_rows"] == 3
    with pytest.raises(dps.DataPlatformError):
        dps.transform_preview(db, bid, {**mp, "mapping": {"Nope": "X"}})  # value does not exist
    with pytest.raises(dps.DataPlatformError):
        dps.transform_preview(db, bid, {**mp, "mapping": {"General": ""}})
    with pytest.raises(dps.DataPlatformError):
        dps.transform_preview(db, bid, {"id": "exec:os.system", "kind": "map_values", "table": "products", "column": "name", "mapping": {"a": "b"}})  # not an offered operation
    with pytest.raises(dps.DataPlatformError):
        dps.apply_transform(db, bid, {"id": "aggregate:sales", "kind": "aggregate_preview", "table": "sales"}, True)  # read-only


def test_transform_that_introduces_new_failures_is_undone_automatically(world, monkeypatch):
    db, bid, pids = world
    ps.sale(db, bid, pids["Alpha"], D, 2, 10, revenue=25)
    db.commit()
    real = dps.run_validation
    calls = {"n": 0}

    def fake(db_, bid_, tables=None, record=True):
        out = real(db_, bid_, tables, record)
        calls["n"] += 1
        if calls["n"] == 2:  # the validation after the change
            out["fail"] += 1
        return out

    monkeypatch.setattr(dps, "run_validation", fake)
    rec = {"id": "recalc:sales.revenue", "kind": "recalculate_totals", "table": "sales", "column": "revenue"}
    with pytest.raises(dps.DataPlatformError, match="undone"):
        dps.apply_transform(db, bid, rec, True)
    assert _sales_sum(db, bid) == (25.0, 1)  # data restored
    assert dps.history(db, bid, stage="transform")[0]["status"] == "failed"


def test_aggregate_preview_is_read_only(world):
    db, bid, pids = world
    for i in range(40):
        ps.sale(db, bid, pids["Alpha"], D + timedelta(days=i), 1, 10)
    db.commit()
    before = _sales_sum(db, bid)
    agg = dps.aggregate_preview(db, bid, "month")
    assert [r["period"] for r in agg["rows"]] == ["2025-03", "2025-04"] and agg["rows"][0]["sales"] == 310.0
    assert _sales_sum(db, bid) == before and "Nothing is stored" in agg["note"]
    with pytest.raises(dps.DataPlatformError):
        dps.aggregate_preview(db, bid, "decade")


# ------------------------------------------------------------------------------------------------ pipeline
def test_pipeline_states_follow_real_state(db_session):
    db = db_session
    bid = ps.business(db)
    p0 = dps.pipeline(db, bid)
    assert [s["state"] for s in p0["stages"]][:2] == ["not_started", "not_started"] and not p0["ready_for_analysis"]
    pids = ps.products(db, bid)
    for i in range(3):
        ps.sale(db, bid, pids["Alpha"], D + timedelta(days=i), 2, 10)
    ps.sale(db, bid, pids["Alpha"], D, 2, 10)  # duplicate -> a cleaning issue
    db.commit()
    st = {s["key"]: s for s in dps.pipeline(db, bid)["stages"]}
    assert st["source"]["state"] == "ready" and st["cleaning"]["state"] == "needs_attention" and st["cleaning"]["pending"] >= 1
    assert st["validation"]["state"] == "not_started" and st["prepared"]["state"] == "in_progress"
    dps.run_validation(db, bid)
    p2 = dps.pipeline(db, bid)
    v = {s["key"]: s for s in p2["stages"]}["validation"]
    assert v["state"] == "needs_attention" and "warning" in v["detail"] and not p2["ready_for_analysis"]  # a warning is not a pass
    dps.apply_cleaning(db, bid, "dedupe:sales", True)
    dps.run_validation(db, bid)
    p3 = dps.pipeline(db, bid)
    assert p3["ready_for_analysis"] and {s["key"]: s for s in p3["stages"]}["prepared"]["state"] == "ready"
    assert p3["current_stage"] in ("profiling", "transformation", "analytics")  # first non-ready stage; profiling/transformation are optional
    assert any("provenance" in x or "lineage" in x for x in p3["limitations"])


def test_pipeline_flags_stale_validation_and_outdated_outputs(world):
    db, bid, pids = world
    for i in range(3):
        ps.sale(db, bid, pids["Alpha"], D + timedelta(days=i), 2, 10)
    db.commit()
    dps.run_validation(db, bid)
    rep = rs.create(db.get(__import__("app.models.business", fromlist=["Business"]).Business, bid), db, "performance") if False else None  # noqa: F841
    from app.models.business import Business

    rs.create(db, db.get(Business, bid), "performance", 30, "latest")
    # new data arrives after the validation run and the report
    import time

    time.sleep(0.01)
    db.add(Product(business_id=bid, external_product_id="NEW", name="New", category="x", selling_price=1))
    db.commit()
    p = dps.pipeline(db, bid)
    assert {s["key"]: s for s in p["stages"]}["validation"]["state"] == "needs_attention"
    assert "saved reports" in p["downstream_may_need_refresh"]


# ------------------------------------------------------------------------------------------------ reports
def _seeded(db):
    bid = ps.business(db, "Report Co")
    pids = ps.products(db, bid)
    ps.two_period_sales(db, bid, pids, date(2025, 3, 31), 2, 3)
    from app.models.business import Business

    return bid, db.get(Business, bid)


@pytest.mark.parametrize("rtype", list(rs.REPORT_TYPES))
def test_every_report_type_is_saved_reopened_and_scoped(db_session, rtype):
    bid, biz = _seeded(db_session)
    saved = rs.create(db_session, biz, rtype, 30, "latest")
    assert saved["report_type"] == rtype and saved["id"]
    payload = saved["payload"]
    assert payload["title"] == rs.REPORT_TYPES[rtype] and payload["period"]["end"] == "2025-03-31" and payload["scope"]["business_id"] == bid
    assert payload["assumptions"] and payload["limitations"] and isinstance(payload["sections"], list)
    again = rs.get(db_session, bid, saved["id"])
    assert again["payload"] == payload  # a snapshot: reopening returns exactly what was saved
    assert [r["id"] for r in rs.list_reports(db_session, bid)] == [saved["id"]]
    other = ps.business(db_session, "Other")
    with pytest.raises(NotFoundError):
        rs.get(db_session, other, saved["id"])
    assert rs.list_reports(db_session, other) == []


def test_report_contents_match_the_data_and_do_not_recalculate(db_session):
    bid, biz = _seeded(db_session)
    saved = rs.create(db_session, biz, "kpi", 30, "latest")
    table = next(s for s in saved["payload"]["sections"] if s["kind"] == "table")
    rev = next(r for r in table["rows"] if r[0] == "Sales")
    assert rev[1] == "₹930" and rev[2] == "+50.0%"
    ps.sale(db_session, bid, ps.products(db_session, bid)["Alpha"] if False else db_session.query(Product).filter(Product.business_id == bid).first().id, date(2025, 3, 30), 100, 10)
    db_session.commit()
    assert rs.get(db_session, bid, saved["id"])["payload"] == saved["payload"]  # later data does not rewrite a saved report
    assert saved["payload"]["summary"].startswith("Sales were ₹930")


def test_unknown_report_type_period_and_delete(db_session):
    bid, biz = _seeded(db_session)
    with pytest.raises(rs.ReportValidationError):
        rs.create(db_session, biz, "astrology", 30)
    with pytest.raises(rs.ReportValidationError):
        rs.create(db_session, biz, "kpi", 45)
    r = rs.create(db_session, biz, "kpi", 30, "latest")
    other = ps.business(db_session, "Other")
    with pytest.raises(NotFoundError):
        rs.delete(db_session, other, r["id"])
    rs.delete(db_session, bid, r["id"])
    assert rs.list_reports(db_session, bid) == []


def test_forecast_report_without_a_usable_model_says_so_instead_of_inventing_one(db_session):
    bid, biz = _seeded(db_session)
    saved = rs.create(db_session, biz, "forecast", 30, "latest")
    text = str(saved["payload"]["sections"])
    assert ("could not be produced" in text) or ("Expected units" in text)  # either a real forecast or an explicit refusal
    assert saved["payload"]["limitations"]
