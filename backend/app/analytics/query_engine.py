"""Deterministic execution of a validated ``AnalyticsQuery`` — the part that decides what the data says.

Nothing here talks to an LLM, and nothing here trusts one: dates are resolved from the (possibly pinned) clock, product
names are matched only against *this business's* products, every query is an ORM query filtered by ``business_id``,
and the numbers returned are computed from the business's own ``sales`` rows. The LLM never supplies a value.
"""
from __future__ import annotations

import calendar
import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core import clock
from app.models.product import Product
from app.models.sale import Sale
from app.schemas.analytics_query import (
    AbsoluteRange,
    AllTime,
    AnalyticsQuery,
    CalendarPeriod,
    TrailingPeriod,
)

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
_CENT = Decimal("0.01")


class QueryError(Exception):
    """A request that is valid in shape but cannot be answered correctly from this business's data."""

    def __init__(self, code: str, message: str, candidates: list[str] | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.candidates = candidates or []


# --------------------------------------------------------------------------------------------- dates
@dataclass(frozen=True)
class ResolvedPeriod:
    start: date
    end: date
    label: str
    kind: str


def _month_shift(year: int, month: int, delta: int) -> tuple[int, int]:
    idx = year * 12 + (month - 1) + delta
    return idx // 12, idx % 12 + 1


def _month_bounds(year: int, month: int) -> tuple[date, date]:
    return date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1])


def _fmt_day(d: date) -> str:
    return f"{d.day} {d.strftime('%B %Y')}"


def label_for(start: date, end: date) -> str:
    """Human label for a range; names whole calendar months / quarters / years, otherwise 'D Month YYYY to D Month YYYY'."""
    if start == end:
        return _fmt_day(start)
    if start.day == 1 and end == _month_bounds(end.year, end.month)[1]:
        if (start.year, start.month) == (end.year, end.month):
            return start.strftime("%B %Y")
        months = (end.year - start.year) * 12 + end.month - start.month + 1
        if start.month == 1 and end.month == 12 and start.year == end.year:
            return str(start.year)
        if months == 3 and (start.month - 1) % 3 == 0:
            return f"Q{(start.month - 1) // 3 + 1} {start.year}"
    return f"{_fmt_day(start)} to {_fmt_day(end)}"


def resolve_period(spec: Any, today: date, coverage: tuple[date, date] | None) -> tuple[ResolvedPeriod, list[str]]:
    """Resolve a validated DateSpec to explicit dates. Returns the period and any assumptions made (shown to the user)."""
    assumptions: list[str] = []
    if isinstance(spec, AbsoluteRange):
        return ResolvedPeriod(spec.start, spec.end, label_for(spec.start, spec.end), "absolute"), assumptions

    if isinstance(spec, AllTime):
        if coverage is None:
            raise QueryError("no_data", "There are no sales recorded yet.")
        s, e = coverage
        return ResolvedPeriod(s, e, f"all your recorded sales ({_fmt_day(s)} to {_fmt_day(e)})", "all_time"), assumptions

    if isinstance(spec, TrailingPeriod):
        if spec.unit == "day":
            start = today - timedelta(days=spec.count - 1)
        elif spec.unit == "week":
            start = today - timedelta(days=spec.count * 7 - 1)
        else:
            y, m = _month_shift(today.year, today.month, -spec.count)
            last = calendar.monthrange(y, m)[1]
            start = date(y, m, min(today.day, last)) + timedelta(days=1)
        unit = spec.unit + ("s" if spec.count != 1 else "")
        return ResolvedPeriod(start, today, f"the last {spec.count} {unit} ({_fmt_day(start)} to {_fmt_day(today)})", "trailing"), assumptions

    assert isinstance(spec, CalendarPeriod)
    u = spec.unit
    if u == "day":
        d = today + timedelta(days=spec.offset or 0)
        return ResolvedPeriod(d, d, _fmt_day(d), "calendar"), assumptions
    if u == "week":
        monday = today - timedelta(days=today.weekday()) + timedelta(weeks=spec.offset or 0)
        sunday = monday + timedelta(days=6)
        return ResolvedPeriod(monday, sunday, f"the week of {_fmt_day(monday)} to {_fmt_day(sunday)}", "calendar"), assumptions
    if u == "month":
        if spec.offset is not None:
            y, m = _month_shift(today.year, today.month, spec.offset)
        elif spec.year is not None:
            y, m = spec.year, spec.month  # type: ignore[assignment]
        else:  # month named, year not given: the most recent such month that has started by the reference date
            y = today.year if date(today.year, spec.month, 1) <= today else today.year - 1  # type: ignore[arg-type]
            m = spec.month  # type: ignore[assignment]
            assumptions.append(f"You didn't name a year, so I used {date(y, m, 1).strftime('%B %Y')}.")
        s, e = _month_bounds(y, m)
        return ResolvedPeriod(s, e, s.strftime("%B %Y"), "calendar"), assumptions
    if u == "quarter":
        if spec.offset is not None:
            cur_q = (today.month - 1) // 3
            idx = today.year * 4 + cur_q + spec.offset
            y, q = idx // 4, idx % 4 + 1
        elif spec.year is not None:
            y, q = spec.year, spec.quarter  # type: ignore[assignment]
        else:
            q = spec.quarter  # type: ignore[assignment]
            y = today.year if date(today.year, (q - 1) * 3 + 1, 1) <= today else today.year - 1
            assumptions.append(f"You didn't name a year, so I used Q{q} {y}.")
        s = date(y, (q - 1) * 3 + 1, 1)
        e = _month_bounds(y, (q - 1) * 3 + 3)[1]
        return ResolvedPeriod(s, e, f"Q{q} {y}", "calendar"), assumptions
    # year
    y = today.year + (spec.offset or 0) if spec.year is None else spec.year
    return ResolvedPeriod(date(y, 1, 1), date(y, 12, 31), str(y), "calendar"), assumptions


# ----------------------------------------------------------------------------------------- products
def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.casefold()).strip()


def resolve_products(db: Session, business_id: str, names: list[str]) -> list[Product]:
    """Match requested names to THIS business's products only. Exact (case/punctuation-insensitive) first; otherwise a
    unique whole-word containment match; several matches -> clarification; none -> not found."""
    if not names:
        return []
    catalogue = db.query(Product).filter(Product.business_id == business_id).all()
    by_norm: dict[str, list[Product]] = {}
    for p in catalogue:
        by_norm.setdefault(_norm(p.name), []).append(p)
    resolved: list[Product] = []
    for requested in names:
        n = _norm(requested)
        if not n:
            raise QueryError("product_not_found", "I couldn't tell which product you meant.")
        exact = by_norm.get(n)
        if exact:
            resolved.extend(exact)
            continue
        ext = [p for p in catalogue if p.external_product_id and _norm(p.external_product_id) == n]
        if ext:
            resolved.extend(ext)
            continue
        pat = re.compile(rf"(?:^| ){re.escape(n)}(?: |$)")
        partial = [p for p in catalogue if pat.search(_norm(p.name))]
        if len(partial) == 1:
            resolved.append(partial[0])
        elif len(partial) > 1:
            raise QueryError(
                "product_ambiguous",
                f"More than one of your products matches “{requested}”.",
                candidates=sorted({p.name for p in partial})[:8],
            )
        else:
            raise QueryError("product_not_found", f"I couldn't find a product called “{requested}” in your data.")
    seen: set[str] = set()
    unique = []
    for p in resolved:
        if p.id not in seen:
            seen.add(p.id)
            unique.append(p)
    return unique


# ------------------------------------------------------------------------------------------ results
@dataclass
class VerifiedResult:
    """Everything the answer is allowed to say. Numbers are computed, never supplied by an LLM."""

    operation: str
    metric: str
    unit: str  # "INR" | "units" | "count"
    period: ResolvedPeriod
    filters: dict[str, Any]
    no_data: bool = False
    value: Decimal | None = None  # aggregate
    statistic: str = "total"
    rows: list[dict[str, Any]] = field(default_factory=list)  # ranking
    group_by: str | None = None
    direction: str = "desc"
    limit: int | None = None
    tie_at_boundary: bool = False
    comparison: dict[str, Any] | None = None  # compare_periods
    share: dict[str, Any] | None = None  # share_of_total
    basis_days: int | None = None  # days averaged over (mean_*), or days in the filtered set
    coverage: tuple[date, date] | None = None
    coverage_status: str = "full"  # full | partial | none
    assumptions: list[str] = field(default_factory=list)
    caveats: list[str] = field(default_factory=list)
    calculation: str = ""
    n_records: int = 0


@dataclass
class _Bucket:
    day: date
    product_id: str | None
    name: str
    category: str | None
    qty: Decimal
    revenue: Decimal
    n: int
    unit_cost: Decimal | None


def _d(x: Any) -> Decimal:
    return Decimal(str(x if x is not None else 0))


def _money(x: Decimal) -> Decimal:
    return x.quantize(_CENT, rounding=ROUND_HALF_UP)


def data_coverage(db: Session, business_id: str) -> tuple[date, date] | None:
    lo, hi = db.query(func.min(Sale.sale_date), func.max(Sale.sale_date)).filter(Sale.business_id == business_id).one()
    return (lo, hi) if lo is not None and hi is not None else None


def _buckets(
    db: Session, business_id: str, period: ResolvedPeriod, product_ids: list[str] | None, weekdays: list[int]
) -> list[_Bucket]:
    q = (
        db.query(
            Sale.sale_date,
            Sale.product_id,
            func.sum(Sale.quantity),
            func.sum(Sale.revenue),
            func.count(Sale.id),
        )
        .filter(Sale.business_id == business_id, Sale.sale_date >= period.start, Sale.sale_date <= period.end)
    )
    if product_ids:
        q = q.filter(Sale.product_id.in_(product_ids))
    rows = q.group_by(Sale.sale_date, Sale.product_id).all()
    products = {p.id: p for p in db.query(Product).filter(Product.business_id == business_id).all()}
    out: list[_Bucket] = []
    for day, pid, qty, rev, n in rows:
        if weekdays and day.weekday() not in weekdays:
            continue
        p = products.get(pid)
        out.append(
            _Bucket(
                day,
                pid,
                p.name if p else "(no product recorded)",
                p.category if p else None,
                _d(qty),
                _d(rev),
                int(n),
                _d(p.unit_cost) if p is not None and p.unit_cost is not None else None,
            )
        )
    return out


def _customers(db: Session, business_id: str, period: ResolvedPeriod, product_ids: list[str] | None, weekdays: list[int]) -> int:
    q = db.query(Sale.sale_date, Sale.customer_id).filter(
        Sale.business_id == business_id, Sale.sale_date >= period.start, Sale.sale_date <= period.end, Sale.customer_id.isnot(None)
    )
    if product_ids:
        q = q.filter(Sale.product_id.in_(product_ids))
    return len({cid for day, cid in q.distinct().all() if not weekdays or day.weekday() in weekdays})


def _profit(buckets: list[_Bucket]) -> tuple[Decimal | None, Decimal, Decimal]:
    """Profit over sales whose product has a recorded unit cost (same rule as kpi_service). Returns (profit, revenue_covered, revenue_total)."""
    total_rev = sum((b.revenue for b in buckets), Decimal(0))
    costed = [b for b in buckets if b.unit_cost is not None]
    if not costed:
        return None, Decimal(0), total_rev
    rev = sum((b.revenue for b in costed), Decimal(0))
    cost = sum((b.unit_cost * b.qty for b in costed), Decimal(0))  # type: ignore[operator]
    return rev - cost, rev, total_rev


def _metric_value(metric: str, buckets: list[_Bucket]) -> Decimal | None:
    if metric == "revenue":
        return sum((b.revenue for b in buckets), Decimal(0))
    if metric == "units":
        return sum((b.qty for b in buckets), Decimal(0))
    if metric == "orders":
        return Decimal(sum(b.n for b in buckets))
    if metric == "distinct_products":
        return Decimal(len({b.product_id for b in buckets if b.product_id is not None}))
    if metric == "profit":
        return _profit(buckets)[0]
    raise QueryError("unsupported_metric", f"Metric {metric} cannot be computed here.")


def _unit_for(metric: str) -> str:
    return {"revenue": "INR", "profit": "INR", "units": "units"}.get(metric, "count")


_BASE_DESC = {
    "revenue": "sum of recorded sales value (quantity × unit price, as stored)",
    "units": "sum of recorded quantity",
    "orders": "number of recorded sales records",
    "distinct_products": "number of different products with at least one recorded sale",
    "customers": "number of different customers with at least one recorded sale",
    "profit": "recorded sales value minus recorded unit cost × quantity, for products that have a unit cost",
}


def _check_profit_available(db: Session, business_id: str, buckets: list[_Bucket], res: VerifiedResult) -> None:
    profit, rev_cov, rev_tot = _profit(buckets)
    if profit is None:
        has_any_cost = db.query(Product.id).filter(Product.business_id == business_id, Product.unit_cost.isnot(None)).first()
        if not has_any_cost:
            raise QueryError("no_cost_data", "Your data has no product costs, so profit can't be calculated.")
    elif rev_tot > 0 and rev_cov < rev_tot:
        pct = (rev_cov / rev_tot * 100).quantize(Decimal("1"))
        res.caveats.append(f"Profit is calculated only for products with a recorded cost (about {pct}% of the sales value).")


def _bucket_key(group_by: str, b: _Bucket) -> tuple[Any, str]:
    if group_by == "product":
        return (b.product_id or "", b.name)
    if group_by == "category":
        return (b.category or "", b.category or "(no category)")
    if group_by == "weekday":
        return (b.day.weekday(), WEEKDAYS[b.day.weekday()])
    if group_by == "day":
        return (b.day, b.day.isoformat())
    if group_by == "week":
        monday = b.day - timedelta(days=b.day.weekday())
        return (monday, f"week of {monday.isoformat()}")
    return ((b.day.year, b.day.month), f"{b.day.year}-{b.day.month:02d}")


def run_query(db: Session, business_id: str, q: AnalyticsQuery) -> VerifiedResult:
    """Resolve and run a validated query. Raises ``QueryError`` for questions this data cannot answer correctly."""
    today = clock.today()
    cov = data_coverage(db, business_id)
    period, assumptions = resolve_period(q.period, today, cov)

    products = resolve_products(db, business_id, q.products)
    pids = [p.id for p in products] or None
    filters: dict[str, Any] = {"products": [p.name for p in products], "weekdays": [WEEKDAYS[d] for d in q.weekdays]}
    for requested, p in zip(q.products, products):
        if _norm(requested) != _norm(p.name):
            assumptions.append(f"I took “{requested}” to mean “{p.name}”.")

    res = VerifiedResult(
        operation=q.operation,
        metric=q.metric,
        unit=_unit_for(q.metric),
        period=period,
        filters=filters,
        statistic=q.statistic,
        group_by=q.group_by,
        direction=q.direction,
        limit=q.limit,
        coverage=cov,
        assumptions=assumptions,
    )
    _coverage_status(res)

    if q.operation == "aggregate":
        _run_aggregate(db, business_id, q, res, pids)
    elif q.operation == "ranking":
        _run_ranking(db, business_id, q, res, pids)
    elif q.operation == "compare_periods":
        _run_compare(db, business_id, q, res, pids, today, cov)
    else:
        _run_share(db, business_id, q, res, pids)
    return res


def _coverage_status(res: VerifiedResult) -> None:
    cov = res.coverage
    if cov is None:
        res.coverage_status = "none"
    elif res.period.end < cov[0] or res.period.start > cov[1]:
        res.coverage_status = "none"
    elif res.period.start < cov[0] or res.period.end > cov[1]:
        res.coverage_status = "partial"
    else:
        res.coverage_status = "full"
    if res.coverage_status == "partial" and cov is not None:
        res.caveats.append(
            f"Your sales data only covers {_fmt_day(cov[0])} to {_fmt_day(cov[1])}, so this period is only partly covered."
        )


def _active_days(buckets: list[_Bucket]) -> dict[date, list[_Bucket]]:
    by_day: dict[date, list[_Bucket]] = {}
    for b in buckets:
        by_day.setdefault(b.day, []).append(b)
    return by_day


def _run_aggregate(db: Session, business_id: str, q: AnalyticsQuery, res: VerifiedResult, pids: list[str] | None) -> None:
    buckets = _buckets(db, business_id, res.period, pids, q.weekdays)
    res.n_records = sum(b.n for b in buckets)
    if q.metric == "customers":
        n = _customers(db, business_id, res.period, pids, q.weekdays)
        res.value = Decimal(n)
        res.no_data = res.n_records == 0
        res.calculation = _BASE_DESC["customers"]
        return
    if not buckets:
        res.no_data = True
        return
    if q.metric == "profit":
        _check_profit_available(db, business_id, buckets, res)
    if q.statistic == "total":
        res.value = _metric_value(q.metric, buckets)
        res.calculation = _BASE_DESC[q.metric]
        res.basis_days = len(_active_days(buckets))
    elif q.statistic == "mean_per_active_day":
        by_day = _active_days(buckets)
        vals = [_metric_value(q.metric, bs) for bs in by_day.values()]
        vals = [v for v in vals if v is not None]
        res.value = sum(vals, Decimal(0)) / len(vals) if vals else None
        res.basis_days = len(by_day)
        res.calculation = f"mean of the daily totals over the {len(by_day)} days that have at least one sale; daily total = {_BASE_DESC[q.metric]}"
    else:  # mean_per_calendar_day
        lo, hi = res.period.start, res.period.end
        if res.coverage is not None:
            clipped_lo, clipped_hi = max(lo, res.coverage[0]), min(hi, res.coverage[1])
            if (clipped_lo, clipped_hi) != (lo, hi):
                res.assumptions.append(
                    f"I averaged over {_fmt_day(clipped_lo)} to {_fmt_day(clipped_hi)}, the part of that period your data covers."
                )
            lo, hi = clipped_lo, clipped_hi
        days = [lo + timedelta(days=i) for i in range((hi - lo).days + 1)]
        if q.weekdays:
            days = [d for d in days if d.weekday() in q.weekdays]
        total = _metric_value(q.metric, buckets)
        res.value = (total / len(days)) if total is not None and days else None
        res.basis_days = len(days)
        res.calculation = f"total divided by the {len(days)} calendar days in the period; total = {_BASE_DESC[q.metric]}"
    if res.metric in ("revenue", "profit") and res.value is not None:
        res.value = _money(res.value)


def _run_ranking(db: Session, business_id: str, q: AnalyticsQuery, res: VerifiedResult, pids: list[str] | None) -> None:
    gb = q.group_by or "product"
    if q.metric == "customers":
        raise QueryError("unsupported_combination", "Ranking by number of customers isn't supported.")
    if q.metric == "distinct_products" and gb == "product":
        raise QueryError("unsupported_combination", "Counting different products per product doesn't make sense.")
    buckets = _buckets(db, business_id, res.period, pids, q.weekdays)
    res.n_records = sum(b.n for b in buckets)
    if not buckets:
        res.no_data = True
        return
    if q.metric == "profit":
        _check_profit_available(db, business_id, buckets, res)

    groups: dict[Any, tuple[str, list[_Bucket]]] = {}
    for b in buckets:
        key, label = _bucket_key(gb, b)
        groups.setdefault(key, (label, []))[1].append(b)

    if gb == "day" and not q.only_days_with_sales and res.coverage is not None:
        lo, hi = max(res.period.start, res.coverage[0]), min(res.period.end, res.coverage[1])
        for i in range((hi - lo).days + 1):
            d = lo + timedelta(days=i)
            if (not q.weekdays or d.weekday() in q.weekdays) and d not in groups:
                groups[d] = (d.isoformat(), [])
        res.assumptions.append("Days with no sales are counted as zero.")
    elif gb in ("day", "week", "month") and q.only_days_with_sales:
        res.assumptions.append("Only days that have at least one recorded sale are considered." if gb == "day" else "Only periods with recorded sales are considered.")

    scored: list[tuple[Any, str, Decimal]] = []
    for key, (label, bs) in groups.items():
        v = _metric_value(q.metric, bs) if bs else Decimal(0)
        if v is None:
            continue
        scored.append((key, label, v))
    sign = -1 if q.direction == "desc" else 1
    scored.sort(key=lambda t: (sign * t[2], str(t[0])))
    limit = q.limit or 1
    top = scored[:limit]
    res.tie_at_boundary = len(scored) > limit and scored[limit][2] == scored[limit - 1][2]
    res.rows = [
        {
            "rank": i + 1,
            "key": label,
            "value": _money(v) if res.unit == "INR" else v,
            "active_days": len(_active_days(groups[key][1])) if groups[key][1] else 0,
        }
        for i, (key, label, v) in enumerate(top)
    ]
    res.basis_days = len(_active_days(buckets))
    res.calculation = f"{_BASE_DESC[q.metric]}, totalled per {gb}"
    if gb == "weekday":
        res.caveats.append("These are totals per weekday across the whole period, so a weekday that occurs more often has more days adding up.")
    if res.tie_at_boundary:
        res.caveats.append("There is a tie at the cut-off, so another entry has the same value as the last one shown.")


def _run_compare(
    db: Session, business_id: str, q: AnalyticsQuery, res: VerifiedResult, pids: list[str] | None, today: date, cov: tuple[date, date] | None
) -> None:
    if q.metric == "customers":
        raise QueryError("unsupported_combination", "Comparing customer counts isn't supported.")
    other, other_assumptions = resolve_period(q.comparison_period, today, cov)
    res.assumptions.extend(other_assumptions)
    cur_b = _buckets(db, business_id, res.period, pids, q.weekdays)
    prev_b = _buckets(db, business_id, other, pids, q.weekdays)
    res.n_records = sum(b.n for b in cur_b) + sum(b.n for b in prev_b)
    if q.metric == "profit":
        _check_profit_available(db, business_id, cur_b + prev_b, res)
    cur = _metric_value(q.metric, cur_b) if cur_b else Decimal(0)
    prev = _metric_value(q.metric, prev_b) if prev_b else Decimal(0)
    if cur is None or prev is None:
        res.no_data = True
        return
    change = cur - prev
    pct = (change / prev * 100) if prev != 0 else None
    prev_status = "none"
    if cov is not None and not (other.end < cov[0] or other.start > cov[1]):
        prev_status = "partial" if (other.start < cov[0] or other.end > cov[1]) else "full"
    if prev_status == "partial" and cov is not None:
        res.caveats.append(
            f"Your data only partly covers {other.label} (it covers {_fmt_day(cov[0])} to {_fmt_day(cov[1])}), so the comparison may not be like-for-like."
        )
    res.comparison = {
        "current_label": res.period.label,
        "previous_label": other.label,
        "current_start": res.period.start,
        "current_end": res.period.end,
        "previous_start": other.start,
        "previous_end": other.end,
        "current": _money(cur) if res.unit == "INR" else cur,
        "previous": _money(prev) if res.unit == "INR" else prev,
        "change": _money(change) if res.unit == "INR" else change,
        "change_pct": pct.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) if pct is not None else None,
        "previous_status": prev_status,
    }
    res.no_data = not cur_b and not prev_b
    res.calculation = f"(this period − comparison period) ÷ comparison period × 100; each period = {_BASE_DESC[q.metric]}"
    if pct is None and prev == 0:
        res.caveats.append(f"There were no sales in {other.label}, so a percentage change can't be calculated.")


def _run_share(db: Session, business_id: str, q: AnalyticsQuery, res: VerifiedResult, pids: list[str] | None) -> None:
    if q.metric not in ("revenue", "units", "orders"):
        raise QueryError("unsupported_combination", "A share of the total can be worked out for sales, units or orders.")
    part_b = _buckets(db, business_id, res.period, pids, q.weekdays)
    all_b = _buckets(db, business_id, res.period, None, q.weekdays)
    res.n_records = sum(b.n for b in all_b)
    if not all_b:
        res.no_data = True
        return
    part = _metric_value(q.metric, part_b) if part_b else Decimal(0)
    total = _metric_value(q.metric, all_b)
    pct = (part / total * 100) if total else None
    res.share = {
        "part": _money(part) if res.unit == "INR" else part,
        "total": _money(total) if res.unit == "INR" else total,
        "share_pct": pct.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) if pct is not None else None,
    }
    res.calculation = f"selected products' {q.metric} ÷ all products' {q.metric} × 100; {_BASE_DESC[q.metric]}"
