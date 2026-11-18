"""Deterministic query engine: expected values are computed here with plain Python from the seeded rows, independently of the engine."""
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.analytics import query_engine, query_presenter
from app.core import clock
from app.schemas.analytics_query import AnalyticsQuery
from tests.analytics_llm_support import make_business, ref_sum, seed_sales

FEB = {"kind": "calendar", "unit": "month", "year": 2025, "month": 2}
JAN = {"kind": "calendar", "unit": "month", "year": 2025, "month": 1}
MAR = {"kind": "calendar", "unit": "month", "year": 2025, "month": 3}
ALL = {"kind": "all_time"}
D = lambda y, m, d: date(y, m, d)  # noqa: E731


@pytest.fixture()
def world(db_session):
    a = make_business(db_session, "A")
    b = make_business(db_session, "B")
    ref_a = seed_sales(db_session, a, with_customers=True)
    seed_sales(db_session, b, scale=1000)  # another tenant with 1000x the volume
    return db_session, a, b, ref_a


def run(db, bid, **kw):
    base = {"operation": "aggregate", "metric": "revenue", "period": FEB}
    base.update(kw)
    return query_engine.run_query(db, bid, AnalyticsQuery.model_validate(base))


# ------------------------------------------------------------------------------------------ C. totals
def test_total_revenue_and_units(world):
    db, a, _b, ref = world
    r = run(db, a)
    assert r.value == ref_sum(ref, "revenue", start=D(2025, 2, 1), end=D(2025, 2, 28))
    assert r.period.start == D(2025, 2, 1) and r.period.end == D(2025, 2, 28)
    u = run(db, a, metric="units", period=ALL)
    assert u.value == ref_sum(ref, "qty")
    assert query_presenter.facts(r)[0].startswith("Your total sales for February 2025 were ₹")


def test_orders_distinct_products_and_customers(world):
    db, a, _b, ref = world
    r = run(db, a, metric="orders", period=JAN)
    assert r.value == len([x for x in ref if x["date"].month == 1])
    r = run(db, a, metric="distinct_products", period=JAN)
    assert r.value == len({x["product"] for x in ref if x["date"].month == 1})
    r = run(db, a, metric="customers", period=ALL)
    assert r.value == len({x["customer"] for x in ref})


def test_product_and_weekday_filters(world):
    db, a, _b, ref = world
    r = run(db, a, metric="units", period=ALL, products=["BIG ONION"])
    assert r.value == ref_sum(ref, "qty", product="BIG ONION")
    r = run(db, a, period=ALL, weekdays=[6])
    assert r.value == ref_sum(ref, "revenue", weekday=6)
    assert "Sundays" in query_presenter.facts(r)[0]
    r = run(db, a, period=ALL, weekdays=[5, 6])
    assert r.value == ref_sum(ref, "revenue", weekday=5) + ref_sum(ref, "revenue", weekday=6)


def test_averages_active_vs_calendar_days(world):
    db, a, _b, ref = world
    daily = defaultdict(Decimal)
    for x in ref:
        if x["date"].month == 3:
            daily[x["date"]] += x["revenue"]
    r = run(db, a, period=MAR, statistic="mean_per_active_day")
    assert r.basis_days == len(daily)
    assert r.value == (sum(daily.values()) / len(daily)).quantize(Decimal("0.01"))
    r2 = run(db, a, period=MAR, statistic="mean_per_calendar_day")
    # the seeded data's last sale is on 30 March (31 March is a no-sales day at the very end), so the engine
    # averages over the part of March the data covers and says so
    assert r2.basis_days == 30
    assert any("part of that period your data covers" in a for a in r2.assumptions)
    assert r2.value == (sum(daily.values()) / 30).quantize(Decimal("0.01"))
    assert r.value > r2.value  # days with no sales are excluded from the first average only


# ---------------------------------------------------------------------------------------- C. rankings
def test_ranking_products_by_units_and_revenue(world):
    db, a, _b, ref = world
    totals = defaultdict(int)
    rev = defaultdict(Decimal)
    for x in ref:
        if x["date"].month == 2:
            totals[x["product"]] += x["qty"]
            rev[x["product"]] += x["revenue"]
    exp_units = sorted(totals.items(), key=lambda kv: (-kv[1], kv[0]))
    r = run(db, a, operation="ranking", metric="units", group_by="product", limit=3)
    assert [(row["key"], int(row["value"])) for row in r.rows] == exp_units[:3]
    exp_rev = sorted(rev.items(), key=lambda kv: (-kv[1], kv[0]))
    r = run(db, a, operation="ranking", group_by="product", limit=2, period=ALL if False else FEB)
    assert [row["key"] for row in r.rows] == [k for k, _ in exp_rev[:2]]
    asc = run(db, a, operation="ranking", metric="units", group_by="product", limit=1, direction="asc")
    assert asc.rows[0]["key"] == exp_units[-1][0]


def test_ranking_days_and_weekdays(world):
    db, a, _b, ref = world
    daily = defaultdict(Decimal)
    for x in ref:
        daily[x["date"]] += x["revenue"]
    best = max(daily.items(), key=lambda kv: (kv[1], -kv[0].toordinal()))
    r = run(db, a, operation="ranking", group_by="day", limit=1, period=ALL)
    assert r.rows[0]["value"] == best[1]
    assert best[0].isoformat() in query_presenter.facts(r)[0]
    worst = min(daily.items(), key=lambda kv: (kv[1], kv[0]))
    r = run(db, a, operation="ranking", group_by="day", limit=1, direction="asc", period=ALL)
    assert r.rows[0]["value"] == worst[1] and r.rows[0]["value"] > 0  # only days with sales by default
    r = run(db, a, operation="ranking", group_by="day", limit=1, direction="asc", period=ALL, only_days_with_sales=False)
    assert r.rows[0]["value"] == 0  # a no-sales day counted as zero, when asked
    wk = defaultdict(Decimal)
    for x in ref:
        wk[x["date"].weekday()] += x["revenue"]
    r = run(db, a, operation="ranking", group_by="weekday", limit=7, period=ALL)
    assert [row["key"] for row in r.rows][0] == query_engine.WEEKDAYS[max(wk, key=lambda k: (wk[k], -k))]
    assert len(r.rows) == 7
    assert any("per weekday" in c for c in r.caveats)


def test_ranking_by_category_and_month(world):
    db, a, _b, ref = world
    cat = defaultdict(Decimal)
    for x in ref:
        cat[x["category"]] += x["revenue"]
    r = run(db, a, operation="ranking", group_by="category", period=ALL, limit=2)
    assert [row["key"] for row in r.rows] == [k for k, _ in sorted(cat.items(), key=lambda kv: (-kv[1], kv[0]))]
    r = run(db, a, operation="ranking", group_by="month", period=ALL, limit=3)
    assert {row["key"] for row in r.rows} == {"2025-01", "2025-02", "2025-03"}


# ------------------------------------------------------------------------- C. comparison & percentage
def test_comparison_percentage_change(world):
    db, a, _b, ref = world
    feb = ref_sum(ref, "revenue", start=D(2025, 2, 1), end=D(2025, 2, 28))
    jan = ref_sum(ref, "revenue", start=D(2025, 1, 1), end=D(2025, 1, 31))
    r = run(db, a, operation="compare_periods", period=FEB, comparison_period=JAN)
    c = r.comparison
    assert c["current"] == feb and c["previous"] == jan
    assert c["change_pct"] == ((feb - jan) / jan * 100).quantize(Decimal("0.01"))
    text = query_presenter.facts(r)[0]
    assert ("higher" in text) == (feb > jan) and f"{abs(c['change_pct'])}%" in text


def test_comparison_with_zero_baseline_has_no_percentage(world):
    db, a, _b, _ref = world
    r = run(db, a, operation="compare_periods", period=FEB, comparison_period={"kind": "calendar", "unit": "month", "year": 2024, "month": 12})
    assert r.comparison["change_pct"] is None
    assert any("can't be calculated" in c for c in r.caveats)


def test_share_of_total(world):
    db, a, _b, ref = world
    part = ref_sum(ref, "revenue", product="EGG")
    total = ref_sum(ref, "revenue")
    r = run(db, a, operation="share_of_total", period=ALL, products=["EGG"])
    assert r.share["part"] == part and r.share["total"] == total
    assert r.share["share_pct"] == (part / total * 100).quantize(Decimal("0.01"))


# ------------------------------------------------------------------------- products, no data, profit
def test_product_matching_exact_partial_ambiguous_missing(world):
    db, a, _b, ref = world
    r = run(db, a, metric="units", period=ALL, products=["big onion"])
    assert r.value == ref_sum(ref, "qty", product="BIG ONION") and not r.assumptions
    r = run(db, a, metric="units", period=ALL, products=["Milk"])
    assert r.value == ref_sum(ref, "qty", product="MILK")
    with pytest.raises(query_engine.QueryError) as amb:
        run(db, a, products=["ONION"])
    assert amb.value.code == "product_ambiguous" and set(amb.value.candidates) == {"BIG ONION", "RED ONION"}
    with pytest.raises(query_engine.QueryError) as nf:
        run(db, a, products=["TOOTHPASTE"])
    assert nf.value.code == "product_not_found"
    with pytest.raises(query_engine.QueryError):
        run(db, a, products=["x' OR 1=1; --"])  # matched as a plain string, never as SQL


def test_period_without_sales_is_no_data_not_zero(world):
    db, a, _b, _ref = world
    r = run(db, a, period={"kind": "calendar", "unit": "month", "year": 2024, "month": 6})
    assert r.no_data and r.value is None
    assert "couldn't find any recorded sales" in query_presenter.facts(r)[0]
    assert r.coverage_status == "none"


def test_partial_coverage_is_flagged(world):
    db, a, _b, _ref = world
    r = run(db, a, period={"kind": "calendar", "unit": "month", "year": 2025, "month": 4}, metric="units")
    assert r.no_data
    r = run(db, a, period={"kind": "absolute", "start": "2025-03-15", "end": "2025-04-15"})
    assert r.coverage_status == "partial" and any("only covers" in c for c in r.caveats)


def test_profit_requires_costs(db_session):
    no_cost = make_business(db_session, "NC")
    seed_sales(db_session, no_cost)
    with pytest.raises(query_engine.QueryError) as e:
        run(db_session, no_cost, metric="profit", period=ALL)
    assert e.value.code == "no_cost_data"

    with_cost = make_business(db_session, "WC")
    ref = seed_sales(db_session, with_cost, with_costs=True)
    r = run(db_session, with_cost, metric="profit", period=ALL)
    exp = sum((x["revenue"] - Decimal(x["qty"]) * x["cost"] for x in ref if x["cost"] is not None), Decimal(0))
    assert r.value == exp.quantize(Decimal("0.01"))
    assert any("recorded cost" in c for c in r.caveats)  # EGG has no cost -> partial coverage disclosed


def test_unsupported_combinations_are_refused(world):
    db, a, _b, _ref = world
    for kw in (
        {"operation": "ranking", "group_by": "day", "metric": "customers"},
        {"operation": "ranking", "group_by": "product", "metric": "distinct_products"},
        {"operation": "share_of_total", "metric": "distinct_products", "products": ["EGG"]},
        {"operation": "compare_periods", "metric": "customers", "comparison_period": JAN},
    ):
        with pytest.raises(query_engine.QueryError) as e:
            run(db, a, **kw)
        assert e.value.code == "unsupported_combination"


# ----------------------------------------------------------------- relative dates + the evaluation clock
def test_relative_period_follows_the_evaluation_clock(world):
    db, a, _b, ref = world
    this_month = {"kind": "calendar", "unit": "month", "offset": 0}
    with clock.reference_date(D(2025, 3, 31)):
        r = run(db, a, period=this_month)
        assert r.value == ref_sum(ref, "revenue", start=D(2025, 3, 1), end=D(2025, 3, 31))
        assert r.period.label == "March 2025"
        last30 = run(db, a, period={"kind": "trailing", "count": 30, "unit": "day"})
        assert last30.period.start == D(2025, 3, 2) and last30.value == ref_sum(ref, "revenue", start=D(2025, 3, 2), end=D(2025, 3, 31))
    real = run(db, a, period=this_month)  # production clock: this month is long after the data
    assert real.no_data


# --------------------------------------------------------------------------------- tenant isolation
def test_engine_never_reads_another_business(world):
    db, a, b, ref = world
    ra, rb = run(db, a, period=ALL), run(db, b, period=ALL)
    assert ra.value == ref_sum(ref, "revenue") and rb.value == ra.value * 1000
    # B has a product also called BIG ONION; asking A for it must only ever see A's own sales
    assert run(db, a, metric="units", period=ALL, products=["BIG ONION"]).value == ref_sum(ref, "qty", product="BIG ONION")
    # a business id that owns nothing sees nothing, whatever the request says
    ghost = make_business(db, "ghost")
    assert run(db, ghost, period=FEB).no_data
    with pytest.raises(query_engine.QueryError) as e:
        run(db, ghost, period=ALL)  # "all time" for a business with no sales: there is nothing to resolve
    assert e.value.code == "no_data"
    c = run(db, a, metric="customers", period=ALL)
    assert c.value == len({x["customer"] for x in ref})
