"""Structured-request validation, the analytics clock, and deterministic date resolution (no LLM involved)."""
from datetime import date

import pytest
from pydantic import ValidationError

from app.analytics.query_engine import QueryError, label_for, resolve_period
from app.core import clock
from app.schemas.analytics_query import AnalyticsQuery, Interpretation

PERIOD = {"kind": "calendar", "unit": "month", "year": 2025, "month": 2}


def q(**kw):
    base = {"operation": "aggregate", "metric": "revenue", "period": PERIOD}
    base.update(kw)
    return AnalyticsQuery.model_validate(base)


# ----------------------------------------------------------------------------------------- A. validation
def test_valid_requests_parse():
    assert q().metric == "revenue"
    r = q(operation="ranking", metric="units", group_by="product", limit=10, direction="desc")
    assert r.limit == 10
    c = q(operation="compare_periods", comparison_period={"kind": "calendar", "unit": "month", "year": 2025, "month": 1})
    assert c.comparison_period is not None
    s = q(operation="share_of_total", products=["EGG"])
    assert s.products == ["EGG"]
    assert q(weekdays=[6, 6, 0]).weekdays == [0, 6]


@pytest.mark.parametrize(
    "patch",
    [
        {"operation": "run_sql"},
        {"metric": "margin_percent"},
        {"metric": "revenue; DROP TABLE sales"},
        {"operation": "ranking", "group_by": "product", "limit": 0},
        {"operation": "ranking", "group_by": "product", "limit": 51},
        {"operation": "ranking", "group_by": "product", "limit": 10**9},
        {"operation": "ranking"},  # no group_by
        {"operation": "compare_periods"},  # no comparison period
        {"operation": "share_of_total"},  # no product
        {"group_by": "product"},  # group_by outside ranking
        {"comparison_period": PERIOD},  # comparison outside compare
        {"statistic": "mean_per_active_day", "metric": "customers"},
        {"weekdays": [7]},
        {"weekdays": [-1]},
        {"sql": "SELECT * FROM sales"},  # unexpected field
        {"table": "users"},
        {"products": [""]},
        {"direction": "sideways"},
        {"period": {"kind": "absolute", "start": "2025-03-01", "end": "2025-02-01"}},  # reversed
        {"period": {"kind": "absolute", "start": "2025-13-01", "end": "2025-13-02"}},  # impossible date
        {"period": {"kind": "absolute", "start": "1500-01-01", "end": "1500-02-01"}},
        {"period": {"kind": "calendar", "unit": "month", "year": 2025, "month": 13}},
        {"period": {"kind": "calendar", "unit": "month", "offset": 1}},  # future offset
        {"period": {"kind": "calendar", "unit": "month", "offset": -1, "month": 2}},  # both
        {"period": {"kind": "calendar", "unit": "week", "year": 2025}},
        {"period": {"kind": "trailing", "count": 0, "unit": "day"}},
        {"period": {"kind": "trailing", "count": 10**7, "unit": "day"}},
        {"period": {"kind": "relative", "text": "last tuesday"}},
        {"period": "yesterday"},
    ],
)
def test_invalid_requests_are_rejected(patch):
    with pytest.raises(ValidationError):
        q(**patch)


def test_interpretation_envelope_rules():
    assert Interpretation.model_validate({"route": "legacy"}).route == "legacy"
    with pytest.raises(ValidationError):
        Interpretation.model_validate({"route": "analytics_query"})  # no query
    with pytest.raises(ValidationError):
        Interpretation.model_validate({"route": "legacy", "query": {"operation": "aggregate", "metric": "revenue", "period": PERIOD}})
    with pytest.raises(ValidationError):
        Interpretation.model_validate({"route": "clarification"})
    with pytest.raises(ValidationError):
        Interpretation.model_validate({"route": "unsupported"})
    with pytest.raises(ValidationError):
        Interpretation.model_validate({"route": "legacy", "answer": "Sales were 100"})  # an LLM-supplied answer field does not exist


# ------------------------------------------------------------------------------------------ B. the clock
def test_clock_is_real_by_default_and_pin_is_scoped():
    assert clock.today() == date.today()
    assert not clock.is_pinned()
    with clock.reference_date(date(2025, 3, 31)):
        assert clock.today() == date(2025, 3, 31)
        assert clock.is_pinned()
    assert clock.today() == date.today()


def test_clock_pin_is_released_after_an_exception():
    with pytest.raises(RuntimeError):
        with clock.reference_date(date(2025, 3, 31)):
            raise RuntimeError("boom")
    assert not clock.is_pinned()


def test_clock_rejects_non_dates():
    with pytest.raises(TypeError):
        with clock.reference_date("2025-03-31"):  # type: ignore[arg-type]
            pass


def test_chat_reachable_modules_use_the_clock_not_date_today():
    import app.analytics.breakdown_service as b
    import app.analytics.churn_service as c
    import app.analytics.kpi_service as k
    import app.services.assistant_service as a
    import inspect

    for mod in (a, b, c, k):
        assert "date.today()" not in inspect.getsource(mod), mod.__name__
    for mod in (a, b, c, k):
        assert "clock.today()" in inspect.getsource(mod), mod.__name__


def test_legacy_windows_follow_the_pinned_clock(db_session):
    from app.analytics import kpi_service
    from tests.analytics_llm_support import make_business, seed_sales

    bid = make_business(db_session)
    seed_sales(db_session, bid)
    with clock.reference_date(date(2025, 3, 31)):
        k = kpi_service.compute_kpis(db_session, bid, period_days=30)
        assert k.period_end == date(2025, 3, 31) and k.revenue > 0
    assert kpi_service.compute_kpis(db_session, bid, period_days=30).revenue == 0  # real clock: nothing in the last 30 days


# --------------------------------------------------------------------------------- B. date resolution
def rp(spec: dict, today: date, coverage=None):
    from pydantic import TypeAdapter

    from app.schemas.analytics_query import DateSpec

    return resolve_period(TypeAdapter(DateSpec).validate_python(spec), today, coverage)


T = date(2025, 3, 31)


def test_explicit_dates_and_month_names():
    p, a = rp({"kind": "absolute", "start": "2025-03-01", "end": "2025-03-15"}, T)
    assert (p.start, p.end) == (date(2025, 3, 1), date(2025, 3, 15)) and a == []
    p, _ = rp({"kind": "calendar", "unit": "month", "year": 2025, "month": 2}, T)
    assert (p.start, p.end, p.label) == (date(2025, 2, 1), date(2025, 2, 28), "February 2025")
    p, _ = rp({"kind": "calendar", "unit": "month", "year": 2024, "month": 2}, T)
    assert p.end == date(2024, 2, 29)  # leap year


def test_relative_months_use_the_reference_date():
    p, _ = rp({"kind": "calendar", "unit": "month", "offset": 0}, T)
    assert (p.start, p.end) == (date(2025, 3, 1), date(2025, 3, 31))
    p, _ = rp({"kind": "calendar", "unit": "month", "offset": -1}, T)
    assert (p.start, p.end) == (date(2025, 2, 1), date(2025, 2, 28))
    p, _ = rp({"kind": "calendar", "unit": "month", "offset": 0}, date(2025, 4, 10))
    assert (p.start, p.end) == (date(2025, 4, 1), date(2025, 4, 30))


def test_year_boundary():
    p, _ = rp({"kind": "calendar", "unit": "month", "offset": -1}, date(2025, 1, 15))
    assert (p.start, p.end) == (date(2024, 12, 1), date(2024, 12, 31))
    p, _ = rp({"kind": "calendar", "unit": "month", "offset": -13}, date(2025, 1, 15))
    assert (p.start, p.end) == (date(2023, 12, 1), date(2023, 12, 31))
    p, _ = rp({"kind": "calendar", "unit": "quarter", "offset": -1}, date(2025, 2, 1))
    assert (p.start, p.end) == (date(2024, 10, 1), date(2024, 12, 31))
    p, _ = rp({"kind": "calendar", "unit": "year", "offset": -1}, date(2025, 2, 1))
    assert (p.start, p.end) == (date(2024, 1, 1), date(2024, 12, 31))
    p, _ = rp({"kind": "trailing", "count": 3, "unit": "month"}, date(2025, 2, 15))
    assert (p.start, p.end) == (date(2024, 11, 16), date(2025, 2, 15))
    p, _ = rp({"kind": "trailing", "count": 30, "unit": "day"}, date(2025, 1, 10))
    assert (p.start, p.end) == (date(2024, 12, 12), date(2025, 1, 10))  # exactly 30 days, both ends included


def test_month_without_year_picks_most_recent_and_says_so():
    p, a = rp({"kind": "calendar", "unit": "month", "month": 2}, T)
    assert p.start == date(2025, 2, 1) and any("didn't name a year" in x for x in a)
    p, a = rp({"kind": "calendar", "unit": "month", "month": 11}, T)
    assert p.start == date(2024, 11, 1) and a  # November has not happened yet in 2025
    p, _ = rp({"kind": "calendar", "unit": "month", "month": 3}, T)
    assert p.start == date(2025, 3, 1)


def test_week_and_day_periods():
    p, _ = rp({"kind": "calendar", "unit": "week", "offset": 0}, date(2025, 3, 31))  # a Monday
    assert (p.start, p.end) == (date(2025, 3, 31), date(2025, 4, 6))
    p, _ = rp({"kind": "calendar", "unit": "day", "offset": -1}, date(2025, 3, 1))
    assert p.start == p.end == date(2025, 2, 28)


def test_all_time_uses_the_data_span_and_needs_data():
    p, _ = rp({"kind": "all_time"}, T, (date(2025, 1, 1), date(2025, 3, 31)))
    assert (p.start, p.end) == (date(2025, 1, 1), date(2025, 3, 31))
    with pytest.raises(QueryError):
        rp({"kind": "all_time"}, T, None)


def test_labels_name_whole_months():
    assert label_for(date(2025, 1, 1), date(2025, 3, 31)) == "Q1 2025"
    assert label_for(date(2025, 1, 1), date(2025, 2, 28)).startswith("1 January 2025 to")
    assert label_for(date(2025, 3, 1), date(2025, 3, 15)) == "1 March 2025 to 15 March 2025"
