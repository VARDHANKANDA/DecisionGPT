"""Sales/Customer/Marketing/Inventory analytics breakdowns —
docs/PRD.md §22 "Data & Analytics". Every number here is computed directly
from this business's own uploaded rows (same honesty rule as kpi_service):
no products/campaigns/inventory on file means an empty list, never a
placeholder row.
"""
from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.customer import Customer
from app.models.inventory import InventoryRecord
from app.models.marketing import MarketingCampaign
from app.models.product import Product
from app.models.sale import Sale


@dataclass
class ProductPerformance:
    product_id: str
    name: str
    units_sold: int
    revenue: float


def top_products(db: Session, business_id: str, limit: int = 10) -> list[ProductPerformance]:
    rows = (
        db.query(
            Product.id,
            Product.name,
            func.coalesce(func.sum(Sale.quantity), 0),
            func.coalesce(func.sum(Sale.revenue), 0.0),
        )
        .outerjoin(Sale, Sale.product_id == Product.id)
        .filter(Product.business_id == business_id)
        .group_by(Product.id, Product.name)
        .order_by(func.coalesce(func.sum(Sale.revenue), 0.0).desc())
        .limit(limit)
        .all()
    )
    return [
        ProductPerformance(product_id=r[0], name=r[1], units_sold=int(r[2]), revenue=round(float(r[3]), 2))
        for r in rows
    ]


@dataclass
class ChannelPerformance:
    channel: str
    spend: float
    attributed_revenue: float | None
    roi: float | None
    campaigns: int


def marketing_by_channel(db: Session, business_id: str) -> list[ChannelPerformance]:
    campaigns = db.query(MarketingCampaign).filter(MarketingCampaign.business_id == business_id).all()
    by_channel: dict[str, list[MarketingCampaign]] = {}
    for c in campaigns:
        by_channel.setdefault(c.channel, []).append(c)

    results = []
    for channel, items in by_channel.items():
        spend = float(sum(c.spend for c in items))
        attributed = [c for c in items if c.attributed_revenue is not None]
        attributed_revenue = round(float(sum(c.attributed_revenue for c in attributed)), 2) if attributed else None
        roi = round((attributed_revenue - spend) / spend, 4) if attributed_revenue is not None and spend > 0 else None
        results.append(
            ChannelPerformance(
                channel=channel, spend=round(spend, 2), attributed_revenue=attributed_revenue, roi=roi,
                campaigns=len(items),
            )
        )
    results.sort(key=lambda c: c.spend, reverse=True)
    return results


@dataclass
class CustomerSummary:
    total_customers: int
    customers_with_purchase_history: int
    avg_monetary_value: float | None
    avg_purchase_frequency: float | None
    new_customers_last_30_days: int


def customer_summary(db: Session, business_id: str) -> CustomerSummary:
    customers = db.query(Customer).filter(Customer.business_id == business_id).all()
    with_history = [c for c in customers if c.monetary_value is not None and c.purchase_frequency is not None]
    avg_monetary = (
        round(sum(float(c.monetary_value) for c in with_history) / len(with_history), 2) if with_history else None
    )
    avg_frequency = (
        round(sum(float(c.purchase_frequency) for c in with_history) / len(with_history), 2)
        if with_history
        else None
    )

    cutoff = date.today() - timedelta(days=30)
    new_customers = sum(1 for c in customers if c.first_purchase_date is not None and c.first_purchase_date >= cutoff)

    return CustomerSummary(
        total_customers=len(customers),
        customers_with_purchase_history=len(with_history),
        avg_monetary_value=avg_monetary,
        avg_purchase_frequency=avg_frequency,
        new_customers_last_30_days=new_customers,
    )


@dataclass
class InventoryStatus:
    product_id: str
    product_name: str
    current_stock: int
    reorder_level: int | None
    low_stock: bool


def inventory_status(db: Session, business_id: str) -> list[InventoryStatus]:
    products = {p.id: p for p in db.query(Product).filter(Product.business_id == business_id).all()}

    latest_by_product: dict[str, InventoryRecord] = {}
    for record in (
        db.query(InventoryRecord)
        .filter(InventoryRecord.business_id == business_id)
        .order_by(InventoryRecord.product_id, InventoryRecord.date)
        .all()
    ):
        latest_by_product[record.product_id] = record  # ascending date -> last write wins

    results = []
    for product_id, record in latest_by_product.items():
        product = products.get(product_id)
        name = product.name if product else "Unknown product"
        low_stock = record.reorder_level is not None and record.stock_level <= record.reorder_level
        results.append(
            InventoryStatus(
                product_id=product_id,
                product_name=name,
                current_stock=record.stock_level,
                reorder_level=record.reorder_level,
                low_stock=low_stock,
            )
        )
    results.sort(key=lambda r: r.current_stock)
    return results
