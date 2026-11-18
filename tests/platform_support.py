"""Synthetic fixtures for the business-OS tests. SOFTWARE-TEST DATA ONLY - not business data and not research evidence."""
from __future__ import annotations

from datetime import date, timedelta

import numpy as np

from app.models.business import Business
from app.models.customer import Customer
from app.models.inventory import InventoryRecord
from app.models.marketing import MarketingCampaign
from app.models.product import Product
from app.models.sale import Sale


def business(db, name="Test Co") -> str:
    b = Business(name=name, industry="retail", business_type="retail", business_size="small")
    db.add(b)
    db.flush()
    return b.id


def products(db, bid, specs=(("Alpha", 10.0, 6.0), ("Beta", 20.0, 12.0), ("Gamma", 5.0, None))) -> dict[str, str]:
    out = {}
    for name, price, cost in specs:
        p = Product(business_id=bid, external_product_id=name[:3].upper(), name=name, category="General", selling_price=price, unit_cost=cost)
        db.add(p)
        db.flush()
        out[name] = p.id
    return out


def sale(db, bid, pid, day: date, qty: int, price: float, discount: float = 0.0, revenue: float | None = None, customer_id=None):
    s = Sale(business_id=bid, product_id=pid, customer_id=customer_id, sale_date=day, quantity=qty, unit_price=price, discount=discount,
             revenue=revenue if revenue is not None else qty * price - discount)
    db.add(s)
    return s


def two_period_sales(db, bid, pids, end: date, prev_daily: int, cur_daily: int, days: int = 30, price: float = 10.0):
    """prev_daily / cur_daily units per day in the previous / current ``days``-day windows (inclusive windows ending ``end``)."""
    pid = pids["Alpha"]
    for i in range(days + 1):
        sale(db, bid, pid, end - timedelta(days=i), cur_daily, price)
    for i in range(days + 1, 2 * days + 2):
        sale(db, bid, pid, end - timedelta(days=i), prev_daily, price)
    db.commit()


def daily_panel_data(db, bid, pids, start: date, n_days: int, effect: float = 0.0, seed: int = 7, with_marketing: bool = True):
    """Marketing spend varies day to day; revenue = 100 + effect*spend + weekday pattern + noise."""
    rng = np.random.default_rng(seed)
    pid = pids["Alpha"]
    for i in range(n_days):
        d = start + timedelta(days=i)
        spend = float(rng.integers(0, 200))
        rev = 100 + effect * spend + (d.weekday() >= 5) * 30 + rng.normal(0, 5)
        units = max(1, int(round(rev / 10)))
        sale(db, bid, pid, d, units, rev / units, revenue=round(rev, 2))
        if with_marketing:
            db.add(MarketingCampaign(business_id=bid, campaign_date=d, channel="Ads", campaign_name="c", spend=spend, attributed_revenue=None))
    db.commit()


def did_panel_data(db, bid, pids, t0: date, window: int = 28, effect: float = 0.0, pre_slope_gap: float = 0.0, seed: int = 3):
    """Alpha is 'changed' at t0; Beta is the comparison. ``effect`` is added to Alpha after t0; ``pre_slope_gap`` makes Alpha trend differently before."""
    rng = np.random.default_rng(seed)
    for i in range(-window, window):
        d = t0 + timedelta(days=i)
        post = i >= 0
        base_b = 50 + 0.0 * i + rng.normal(0, 1.5)
        base_a = 80 + pre_slope_gap * i + rng.normal(0, 1.5) + (effect if post else 0.0)
        sale(db, bid, pids["Beta"], d, 5, round(base_b / 5, 2), revenue=round(base_b, 2))
        sale(db, bid, pids["Alpha"], d, 8, round(base_a / 8, 2), revenue=round(base_a, 2))
    db.commit()


def customers(db, bid, n: int, last: date, recent_share: float = 0.7):
    for i in range(n):
        lp = last - timedelta(days=5) if i < n * recent_share else last - timedelta(days=200)
        db.add(Customer(business_id=bid, external_customer_id=f"C{i}", first_purchase_date=last - timedelta(days=400), last_purchase_date=lp, purchase_frequency=3, monetary_value=100))
    db.commit()


def stock(db, bid, pid, level: int, reorder: int | None, day: date):
    db.add(InventoryRecord(business_id=bid, product_id=pid, date=day, stock_level=level, reorder_level=reorder))
    db.commit()
