"""Turns a ``VerifiedResult`` into the deterministic FACT text and the table behind it.

Every figure the user sees in the direct answer is formatted here from the computed result. The same text is what the
numeric guard (``app.services.analytics_answer_service``) compares an LLM's explanation against: the LLM may only repeat
numbers that appear here (or an exact lakh/crore rendering of them).
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from app.analytics.query_engine import VerifiedResult

_METRIC_NOUN = {
    "revenue": "sales",
    "profit": "profit",
    "units": "units sold",
    "orders": "sales records",
    "distinct_products": "different products sold",
    "customers": "different customers",
}


def indian_group(digits: str) -> str:
    if len(digits) <= 3:
        return digits
    head, tail = digits[:-3], digits[-3:]
    parts: list[str] = []
    while len(head) > 2:
        parts.insert(0, head[-2:])
        head = head[:-2]
    if head:
        parts.insert(0, head)
    return ",".join(parts + [tail])


def fmt_inr(value: Decimal | float) -> str:
    v = Decimal(str(value))
    sign = "-" if v < 0 else ""
    a = abs(v)
    if a < 100:
        return f"{sign}₹{a:.2f}"
    whole = int(a.to_integral_value(rounding="ROUND_HALF_UP"))
    return f"{sign}₹{indian_group(str(whole))}"


def fmt_num(value: Decimal | float) -> str:
    v = Decimal(str(value))
    sign = "-" if v < 0 else ""
    a = abs(v)
    if a == a.to_integral_value():
        return f"{sign}{indian_group(str(int(a)))}"
    q = a.quantize(Decimal("0.01"))
    whole, frac = f"{q:.2f}".split(".")
    return f"{sign}{indian_group(whole)}.{frac}"


def fmt_pct(value: Decimal | float) -> str:
    return f"{abs(Decimal(str(value))):.2f}%"


def fmt_value(res: VerifiedResult, value: Decimal | float) -> str:
    return fmt_inr(value) if res.unit == "INR" else fmt_num(value)


def _scope(res: VerifiedResult) -> str:
    bits = []
    if res.filters["products"]:
        bits.append("for " + " and ".join(res.filters["products"]))
    if res.filters["weekdays"]:
        days = res.filters["weekdays"]
        bits.append("on " + (days[0] + "s" if len(days) == 1 else ", ".join(d + "s" for d in days)))
    return (" " + " ".join(bits)) if bits else ""


def _label(key: Any, group_by: str | None) -> str:
    if group_by == "day":
        try:
            d = date.fromisoformat(str(key))
            return f"{d.strftime('%A')} {d.day} {d.strftime('%B %Y')} ({d.isoformat()})"
        except ValueError:
            return str(key)
    return str(key)


def facts(res: VerifiedResult) -> list[str]:
    """Deterministic sentences, headline first. Never mentions a cause."""
    p = res.period.label
    noun = _METRIC_NOUN[res.metric]
    scope = _scope(res)

    if res.no_data:
        cov = f" Your sales data covers {res.coverage[0].isoformat()} to {res.coverage[1].isoformat()}." if res.coverage else ""
        return [f"I couldn't find any recorded sales{scope} for {p}.{cov}"]

    if res.operation == "aggregate":
        assert res.value is not None or res.statistic != "total"
        if res.value is None:
            return [f"I couldn't work out {noun} for {p}{scope} from the recorded data."]
        v = fmt_value(res, res.value)
        if res.statistic == "total":
            if res.metric == "revenue":
                head = f"Your total sales{scope} for {p} were {v}."
            elif res.metric == "units":
                head = f"You sold {v} units{scope} in {p}."
            elif res.metric == "orders":
                head = f"There were {v} recorded sales records{scope} in {p}."
            elif res.metric == "distinct_products":
                head = f"You sold {v} different products{scope} in {p}."
            elif res.metric == "customers":
                head = f"{v} different customers made purchases{scope} in {p}."
            else:
                head = f"Your profit{scope} for {p} was {v}."
        else:
            word = "on an average day that had sales" if res.statistic == "mean_per_active_day" else "per calendar day"
            what = {"revenue": "your sales were", "units": "you sold", "orders": "there were", "profit": "your profit was"}[res.metric]
            suffix = {"units": " units", "orders": " sales records"}.get(res.metric, "")
            head = f"{p[0].upper() + p[1:]}{scope}: {word}, {what} {v}{suffix} (averaged over {res.basis_days} days)."
        return [head]

    if res.operation == "ranking":
        word = "highest" if res.direction == "desc" else "lowest"
        gb = res.group_by or "product"
        if gb == "product":
            scope = ""  # the listed products ARE the (filtered) scope; naming them before the answer would blur which one leads
        first = res.rows[0]
        v = fmt_value(res, first["value"])
        label = _label(first["key"], gb)
        if len(res.rows) == 1:
            return [f"For {p}{scope}, {label} had the {word} {noun}: {v}."]
        lines = ", ".join(f"{r['rank']}. {_label(r['key'], gb)} ({fmt_value(res, r['value'])})" for r in res.rows)
        return [f"For {p}{scope}, ranked by {noun} ({word} first): {lines}."]

    if res.operation == "compare_periods":
        c = res.comparison or {}
        cur, prev = fmt_value(res, c["current"]), fmt_value(res, c["previous"])
        if c["change_pct"] is None:
            return [f"{c['current_label']}: {cur}; {c['previous_label']}: {prev}. A percentage change can't be worked out because {c['previous_label']} had none."]
        direction = "higher" if c["change"] > 0 else ("lower" if c["change"] < 0 else "the same")
        if direction == "the same":
            return [f"{noun.capitalize()} in {c['current_label']} ({cur}) were the same as in {c['previous_label']} ({prev}); the change is 0.00%."]
        diff = fmt_value(res, abs(c["change"]))
        return [
            f"{noun.capitalize()} in {c['current_label']} were {cur}, compared with {prev} in {c['previous_label']} — "
            f"{fmt_pct(c['change_pct'])} {direction} (a difference of {diff})."
        ]

    s = res.share or {}
    if s.get("share_pct") is None:
        return [f"I couldn't work out a share because total {noun} for {p} was zero."]
    names = " and ".join(res.filters["products"])
    return [
        f"{names} accounted for {fmt_pct(s['share_pct'])} of your total {noun} for {p} "
        f"({fmt_value(res, s['part'])} out of {fmt_value(res, s['total'])})."
    ]


def table(res: VerifiedResult) -> list[dict[str, Any]]:
    """Exact figures behind the answer (for the 'Show the numbers' view)."""
    if res.no_data:
        return []
    if res.operation == "ranking":
        return [
            {"rank": r["rank"], res.group_by or "item": str(r["key"]), res.metric: float(r["value"]), "days_with_sales": r["active_days"]}
            for r in res.rows
        ]
    if res.operation == "compare_periods" and res.comparison:
        c = res.comparison
        return [
            {"period": c["current_label"], res.metric: float(c["current"])},
            {"period": c["previous_label"], res.metric: float(c["previous"])},
        ]
    if res.operation == "share_of_total" and res.share:
        s = res.share
        return [
            {"selected_products": ", ".join(res.filters["products"]), res.metric: float(s["part"])},
            {"selected_products": "all products", res.metric: float(s["total"])},
        ]
    return []


def scalar_details(res: VerifiedResult) -> dict[str, Any]:
    out: dict[str, Any] = {"period_start": res.period.start.isoformat(), "period_end": res.period.end.isoformat()}
    if res.value is not None:
        out[f"{res.metric}_{res.statistic}"] = float(res.value)
    if res.comparison and res.comparison.get("change_pct") is not None:
        out["change_percent"] = float(res.comparison["change_pct"])
    if res.share and res.share.get("share_pct") is not None:
        out["share_percent"] = float(res.share["share_pct"])
    out["sales_records_used"] = res.n_records
    return out


def notes(res: VerifiedResult) -> list[str]:
    """Assumptions and caveats, deterministic."""
    out = list(res.assumptions) + list(res.caveats)
    if not res.no_data and res.coverage_status != "none":
        out.append("This is based on the sales recorded in your uploaded data.")
    return out
