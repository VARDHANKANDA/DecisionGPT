"""Shared test support for the Jev analytics path. MOCKED JEV ONLY — nothing here is a research result.

``FakeLLM`` stands in for ``LLMService``: for a question it returns the *typed decisions* a test supplies (choice / noul answers
with a confidence; it is never given, and never produces, a numerical answer), and records every request so tests can assert what
the provider is — and is not — shown. The periods, product names and limits come from the deterministic extractor under test.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Callable

from app.models.business import Business
from app.models.customer import Customer
from app.models.product import Product
from app.models.sale import Sale
from app.services.openai_client import Answer, DecisionResult

# name, category, unit price, unit cost (None = unknown)
CATALOGUE = [
    ("BIG ONION", "Vegetables", Decimal("40.00"), None),
    ("RED ONION", "Vegetables", Decimal("60.00"), None),
    ("MILK", "Dairy", Decimal("50.00"), None),
    ("EGG", "Dairy", Decimal("6.00"), None),
]
START, END = date(2025, 1, 1), date(2025, 3, 31)


def make_business(db, name: str = "Test Store") -> str:
    b = Business(name=name, industry="retail", business_type="retail", business_size="small")
    db.add(b)
    db.flush()
    return b.id


def seed_sales(db, business_id: str, *, scale: int = 1, with_costs: bool = False, with_customers: bool = False) -> list[dict]:
    """Deterministic sales over 2025-01-01..2025-03-31 (some days have no sales). Returns the plain-Python reference rows
    the tests compute expected values from — independent of the engine under test."""
    prods = {}
    for i, (name, cat, price, cost) in enumerate(CATALOGUE):
        p = Product(
            business_id=business_id,
            external_product_id=f"P{i}",
            name=name,
            category=cat,
            selling_price=price,
            unit_cost=(price * Decimal("0.7")).quantize(Decimal("0.01")) if with_costs and name != "EGG" else cost,
        )
        db.add(p)
        prods[name] = p
    db.flush()
    cust = []
    if with_customers:
        for k in range(3):
            c = Customer(business_id=business_id, external_customer_id=f"C{k}")
            db.add(c)
            cust.append(c)
        db.flush()
    ref: list[dict] = []
    d, i = START, 0
    while d <= END:
        if i % 10 != 9:  # every 10th day has no sales
            for j, (name, cat, price, _c) in enumerate(CATALOGUE):
                if (i + j) % 3 == 0:
                    continue
                qty = (1 + (i * (j + 2)) % 5) * scale
                rev = Decimal(qty) * price
                s = Sale(
                    business_id=business_id,
                    product_id=prods[name].id,
                    customer_id=cust[(i + j) % 3].id if cust else None,
                    sale_date=d,
                    quantity=qty,
                    unit_price=price,
                    revenue=rev,
                )
                db.add(s)
                ref.append({"date": d, "product": name, "category": cat, "qty": qty, "revenue": rev, "cost": prods[name].unit_cost,
                            "customer": (i + j) % 3 if cust else None})
        d += timedelta(days=1)
        i += 1
    db.commit()
    return ref


def ref_sum(rows: list[dict], key: str, *, start: date | None = None, end: date | None = None, product: str | None = None, weekday: int | None = None):
    total = Decimal(0)
    for r in rows:
        if start and r["date"] < start:
            continue
        if end and r["date"] > end:
            continue
        if product and r["product"] != product:
            continue
        if weekday is not None and r["date"].weekday() != weekday:
            continue
        total += Decimal(r[key])
    return total


# ----------------------------------------------------------------------------------------------- mocked Jev
def decision(route="calculate", operation="aggregate", metric="revenue", statistic="total", group_by="none", direction="desc",
             named_products=0.0, include_empty_days=0.0, clarify_about="other", missing_item="other", conf=0.9, **conf_override) -> DecisionResult:
    """The typed answers Jev would return (same keys as ``analytics_interpreter_service.QUESTIONS``)."""
    def ch(name, value):
        return Answer("choice", value, {value: conf}, conf_override.get(name, conf))

    answers = {
        "route": ch("route", route), "operation": ch("operation", operation), "metric": ch("metric", metric),
        "statistic": ch("statistic", statistic), "group_by": ch("group_by", group_by), "direction": ch("direction", direction),
        "clarify_about": ch("clarify_about", clarify_about), "missing_item": ch("missing_item", missing_item),
        "named_products": Answer("noul", named_products), "include_empty_days": Answer("noul", include_empty_days),
    }
    return DecisionResult(True, answers, None, 0.001, "openai", "gpt-4.1-mini", "gpt-4.1-mini-2025-04-14", {"input_tokens": 900, "output_tokens": 0}, 1)


def failure(kind: str) -> DecisionResult:
    return DecisionResult(False, {}, kind, 0.001, "openai", "gpt-4.1-mini", None, None, 1)


class FakeLLM:
    """Scripted stand-in for LLMService. ``script`` maps the question text to a DecisionResult (or a callable returning one)."""

    enabled = True

    def __init__(self, script: dict[str, Any] | None = None):
        self.script = script or {}
        self.calls: list[dict[str, Any]] = []

    def decide(self, state, questions) -> DecisionResult:
        self.calls.append({"state": state, "questions": questions})
        out = self.script.get(state)
        if out is None:
            return failure("provider_error")
        return out() if callable(out) else out
