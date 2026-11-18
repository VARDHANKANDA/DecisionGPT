"""Strict, closed vocabulary for LLM-interpreted analytics questions.

The LLM may only *fill in this schema*. It cannot add fields (``extra="forbid"``), choose tables, write SQL or code.
Every request is validated here, then resolved and executed by ``app.analytics.query_engine`` — which, not the LLM,
decides what the data says.
"""
from __future__ import annotations

from datetime import date
from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Metric = Literal["revenue", "units", "orders", "distinct_products", "customers", "profit"]
Operation = Literal["aggregate", "ranking", "compare_periods", "share_of_total"]
GroupBy = Literal["product", "category", "weekday", "day", "week", "month"]
Statistic = Literal["total", "mean_per_active_day", "mean_per_calendar_day"]
Direction = Literal["desc", "asc"]
Route = Literal["analytics_query", "clarification", "unsupported", "legacy"]
UnsupportedReason = Literal["causal_attribution", "missing_field", "out_of_scope"]
CalendarUnit = Literal["day", "week", "month", "quarter", "year"]

MAX_LIMIT = 50
MAX_TRAILING = 3650
MIN_DATE = date(1990, 1, 1)
MAX_DATE = date(2100, 12, 31)


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class AbsoluteRange(_Strict):
    kind: Literal["absolute"]
    start: date
    end: date

    @model_validator(mode="after")
    def _ordered(self):
        if self.start > self.end:
            raise ValueError("start must not be after end")
        if self.start < MIN_DATE or self.end > MAX_DATE:
            raise ValueError("date outside the supported range")
        return self


class CalendarPeriod(_Strict):
    """A named calendar period, resolved deterministically against the reference date.

    ``offset`` counts whole periods back from the one containing the reference date (0 = this, -1 = previous).
    For ``month``/``quarter``/``year`` an explicit ``year`` (and ``month``/``quarter``) pins the period instead.
    """

    kind: Literal["calendar"]
    unit: CalendarUnit
    offset: int | None = Field(default=None, ge=-1200, le=0)
    year: int | None = Field(default=None, ge=1990, le=2100)
    month: int | None = Field(default=None, ge=1, le=12)
    quarter: int | None = Field(default=None, ge=1, le=4)

    @model_validator(mode="after")
    def _coherent(self):
        pinned = any(v is not None for v in (self.year, self.month, self.quarter))
        if self.offset is not None and pinned:
            raise ValueError("give either offset or an explicit year/month/quarter, not both")
        if self.offset is None and not pinned:
            self.offset = 0
        if self.unit in ("day", "week") and pinned:
            raise ValueError("day/week periods are relative (offset) only")
        if self.unit == "month" and self.month is None and self.offset is None:
            raise ValueError("month period needs a month or an offset")
        if self.unit == "quarter" and self.quarter is None and self.offset is None:
            raise ValueError("quarter period needs a quarter or an offset")
        if self.unit == "year" and (self.month is not None or self.quarter is not None):
            raise ValueError("year period takes only a year")
        if self.unit == "month" and self.quarter is not None:
            raise ValueError("month period does not take a quarter")
        if self.unit == "quarter" and self.month is not None:
            raise ValueError("quarter period does not take a month")
        return self


class TrailingPeriod(_Strict):
    """The last ``count`` whole ``unit`` ending on the reference date (inclusive of it)."""

    kind: Literal["trailing"]
    count: int = Field(ge=1, le=MAX_TRAILING)
    unit: Literal["day", "week", "month"]


class AllTime(_Strict):
    """Every recorded sale (resolved to the first/last sale date in the business's own data)."""

    kind: Literal["all_time"]


DateSpec = Annotated[Union[AbsoluteRange, CalendarPeriod, TrailingPeriod, AllTime], Field(discriminator="kind")]


class AnalyticsQuery(_Strict):
    operation: Operation
    metric: Metric
    period: DateSpec
    comparison_period: DateSpec | None = None  # compare_periods only
    statistic: Statistic = "total"  # aggregate only; "total" unless the user asked for an average
    group_by: GroupBy | None = None  # ranking only
    direction: Direction = "desc"  # ranking only
    limit: int | None = Field(default=None, ge=1, le=MAX_LIMIT)  # ranking only
    products: list[Annotated[str, Field(min_length=1, max_length=200)]] = Field(default_factory=list, max_length=20)
    weekdays: list[int] = Field(default_factory=list, max_length=7)  # 0 = Monday ... 6 = Sunday
    only_days_with_sales: bool = True  # ranking by day/week/month: skip empty buckets (cannot be "lowest" otherwise)

    @field_validator("weekdays")
    @classmethod
    def _weekdays_valid(cls, v: list[int]) -> list[int]:
        if any(d < 0 or d > 6 for d in v):
            raise ValueError("weekday must be 0 (Monday) to 6 (Sunday)")
        return sorted(set(v))

    @model_validator(mode="after")
    def _coherent(self):
        op = self.operation
        if op == "compare_periods" and self.comparison_period is None:
            raise ValueError("compare_periods needs comparison_period")
        if op != "compare_periods" and self.comparison_period is not None:
            raise ValueError("comparison_period is only valid for compare_periods")
        if op == "ranking" and self.group_by is None:
            raise ValueError("ranking needs group_by")
        if op != "ranking" and (self.group_by is not None or self.limit is not None):
            raise ValueError("group_by/limit are only valid for ranking")
        if op == "share_of_total" and not self.products:
            raise ValueError("share_of_total needs at least one product")
        if self.statistic != "total" and op != "aggregate":
            raise ValueError("statistic other than total is only valid for aggregate")
        if self.statistic != "total" and self.metric in ("distinct_products", "customers"):
            raise ValueError("an average per day is not defined for a distinct count")
        if op == "ranking" and self.group_by == "category" and self.products:
            raise ValueError("product filter and category grouping cannot be combined")
        return self


class Interpretation(_Strict):
    """The complete, validated output the LLM interpreter is allowed to return."""

    route: Route
    query: AnalyticsQuery | None = None
    clarification_question: str | None = Field(default=None, max_length=300)
    unsupported_reason: UnsupportedReason | None = None
    unsupported_item: str | None = Field(default=None, max_length=120)  # e.g. "GST rate", names what was asked for

    @model_validator(mode="after")
    def _coherent(self):
        if self.route == "analytics_query":
            if self.query is None:
                raise ValueError("analytics_query needs a query")
        elif self.query is not None:
            raise ValueError("query is only valid with route analytics_query")
        if self.route == "clarification" and not self.clarification_question:
            raise ValueError("clarification needs clarification_question")
        if self.route == "unsupported" and self.unsupported_reason is None:
            raise ValueError("unsupported needs unsupported_reason")
        return self
