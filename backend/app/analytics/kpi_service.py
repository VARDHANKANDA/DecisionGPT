"""Business KPI calculations — docs/PRD.md §22 "Data & Analytics".

Every number here is computed directly from the business's own uploaded
rows. Where a KPI can't be honestly computed (e.g. profit needs
Product.unit_cost, which the SME may not have provided), the field is
returned as None with a note explaining why — never a fabricated or
assumed value (see AGENTS.md "no fabrication").
"""
from dataclasses import dataclass, field
from datetime import date, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.marketing import MarketingCampaign
from app.models.product import Product
from app.models.sale import Sale


@dataclass
class KPISnapshot:
    period_start: date | None
    period_end: date | None
    revenue: float
    orders: int
    customers: int
    average_order_value: float | None
    profit: float | None
    marketing_spend: float
    marketing_roi: float | None
    conversion_rate: float | None
    notes: list[str] = field(default_factory=list)


def compute_kpis(db: Session, business_id: str, period_days: int | None = None) -> KPISnapshot:
    notes: list[str] = []

    sales_query = db.query(Sale).filter(Sale.business_id == business_id)
    period_start = period_end = None
    if period_days is not None:
        period_end = date.today()
        period_start = period_end - timedelta(days=period_days)
        sales_query = sales_query.filter(Sale.sale_date >= period_start, Sale.sale_date <= period_end)

    sales = sales_query.all()
    revenue = float(sum(s.revenue for s in sales))
    orders = len(sales)
    customers = len({s.customer_id for s in sales if s.customer_id is not None})
    average_order_value = round(revenue / orders, 2) if orders else None
    if orders == 0:
        notes.append("No sales in this period — revenue-derived KPIs are unavailable.")

    # Profit requires unit_cost on the sold product; only computed over
    # sales whose product has a known cost, and flagged if any are missing.
    profit = None
    if sales:
        product_costs = {
            p.id: p.unit_cost
            for p in db.query(Product).filter(Product.business_id == business_id).all()
            if p.unit_cost is not None
        }
        sales_with_cost = [s for s in sales if s.product_id in product_costs]
        if sales_with_cost:
            total_cost = sum(float(product_costs[s.product_id]) * s.quantity for s in sales_with_cost)
            revenue_with_cost = sum(float(s.revenue) for s in sales_with_cost)
            profit = round(revenue_with_cost - total_cost, 2)
            if len(sales_with_cost) < len(sales):
                notes.append(
                    f"Profit computed from {len(sales_with_cost)}/{len(sales)} sales — "
                    "the rest reference products with no unit_cost on file."
                )
        else:
            notes.append("Profit is unavailable — no products have a unit_cost on file.")

    marketing_query = db.query(MarketingCampaign).filter(MarketingCampaign.business_id == business_id)
    if period_days is not None:
        marketing_query = marketing_query.filter(
            MarketingCampaign.campaign_date >= period_start, MarketingCampaign.campaign_date <= period_end
        )
    campaigns = marketing_query.all()
    marketing_spend = float(sum(c.spend for c in campaigns))

    marketing_roi = None
    attributed = [c for c in campaigns if c.attributed_revenue is not None]
    if attributed and marketing_spend > 0:
        total_attributed = sum(float(c.attributed_revenue) for c in attributed)
        total_spend_with_attribution = sum(float(c.spend) for c in attributed)
        if total_spend_with_attribution > 0:
            marketing_roi = round(
                (total_attributed - total_spend_with_attribution) / total_spend_with_attribution, 4
            )
    elif campaigns:
        notes.append("Marketing ROI is unavailable — no campaigns have attributed_revenue on file.")

    conversion_rate = None
    campaigns_with_funnel = [c for c in campaigns if c.clicks and c.clicks > 0 and c.conversions is not None]
    if campaigns_with_funnel:
        total_clicks = sum(c.clicks for c in campaigns_with_funnel)
        total_conversions = sum(c.conversions for c in campaigns_with_funnel)
        conversion_rate = round(total_conversions / total_clicks, 4) if total_clicks else None

    return KPISnapshot(
        period_start=period_start,
        period_end=period_end,
        revenue=round(revenue, 2),
        orders=orders,
        customers=customers,
        average_order_value=average_order_value,
        profit=profit,
        marketing_spend=round(marketing_spend, 2),
        marketing_roi=marketing_roi,
        conversion_rate=conversion_rate,
        notes=notes,
    )


def revenue_trend(db: Session, business_id: str, days: int = 90) -> list[dict]:
    """Daily revenue series for the trailing `days` — used by the dashboard
    trend chart. Returns only dates that actually have sales; the frontend
    is responsible for deciding how to render gaps."""
    period_end = date.today()
    period_start = period_end - timedelta(days=days)
    rows = (
        db.query(Sale.sale_date, func.sum(Sale.revenue).label("revenue"))
        .filter(Sale.business_id == business_id, Sale.sale_date >= period_start, Sale.sale_date <= period_end)
        .group_by(Sale.sale_date)
        .order_by(Sale.sale_date)
        .all()
    )
    return [{"date": r.sale_date.isoformat(), "revenue": float(r.revenue)} for r in rows]
