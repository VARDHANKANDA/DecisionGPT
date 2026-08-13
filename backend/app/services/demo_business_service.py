"""Demo Business — docs/PRD.md §38.

A synthetic Indian D2C clothing brand with a full 180-day history across
products, customers, sales, marketing, and inventory, so the entire
product workflow (analytics, forecasting, goals, Digital Twin, causal
graph, multi-agent decisions) can be demonstrated without the user's own
data. Every row is generated here, deterministically from `seed` — it is
never presented as real; the business name and `description` both mark it
as synthetic (docs/PRD.md §38 "Clearly mark it: Synthetic demonstration
data"), and the frontend surfaces that label wherever the business name is shown.
"""
import random
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.models.business import Business
from app.models.customer import Customer
from app.models.inventory import InventoryRecord
from app.models.marketing import MarketingCampaign
from app.models.product import Product
from app.models.sale import Sale

DEMO_BUSINESS_NAME = "Saanjh Handloom Co. (Demo)"
DEMO_DESCRIPTION = (
    "Synthetic demonstration data — an illustrative Indian D2C clothing brand, not a real business."
)

PRODUCT_CATALOG = [
    ("Cotton Kurta - Indigo", 799, 380),
    ("Linen Shirt - White", 1299, 620),
    ("Handloom Saree - Maroon", 2999, 1450),
    ("Denim Jacket", 2199, 1050),
    ("Block-Print Dress", 1599, 740),
]
CHANNELS = ["Instagram", "Google Ads", "Facebook"]
HISTORY_DAYS = 180
CUSTOMER_COUNT = 120


def create_demo_business(db: Session, seed: int = 7) -> str:
    rng = random.Random(seed)

    business = Business(
        name=DEMO_BUSINESS_NAME,
        industry="Apparel / D2C",
        business_type="D2C",
        business_size="Small (6-25)",
        country="IN",
        currency="INR",
        description=DEMO_DESCRIPTION,
    )
    db.add(business)
    db.flush()

    products = []
    for i, (name, price, cost) in enumerate(PRODUCT_CATALOG):
        product = Product(
            business_id=business.id,
            external_product_id=f"DEMO-P{i:03d}",
            name=name,
            category="Apparel",
            unit_cost=cost,
            selling_price=price,
            stock_quantity=rng.randint(40, 120),
        )
        db.add(product)
        products.append(product)
    db.flush()

    today = date.today()
    customers = []
    for i in range(CUSTOMER_COUNT):
        first_purchase = today - timedelta(days=rng.randint(30, HISTORY_DAYS))
        last_purchase = first_purchase + timedelta(days=rng.randint(0, (today - first_purchase).days))
        customer = Customer(
            business_id=business.id,
            external_customer_id=f"DEMO-C{i:04d}",
            first_purchase_date=first_purchase,
            last_purchase_date=last_purchase,
            purchase_frequency=rng.randint(1, 8),
            monetary_value=round(rng.uniform(800, 6000), 2),
        )
        db.add(customer)
        customers.append(customer)
    db.flush()

    start = today - timedelta(days=HISTORY_DAYS)
    for day_offset in range(HISTORY_DAYS):
        sale_date = start + timedelta(days=day_offset)
        is_festive_season = sale_date.month in (10, 11)  # illustrative festive-season demand bump
        daily_orders = rng.randint(3, 8) + (3 if is_festive_season else 0)

        for _ in range(daily_orders):
            product = rng.choice(products)
            customer = rng.choice(customers)
            quantity = rng.randint(1, 3)
            discount = round(float(product.selling_price) * 0.1, 2) if rng.random() < 0.15 else 0.0
            revenue = round(float(product.selling_price) * quantity - discount, 2)
            db.add(
                Sale(
                    business_id=business.id,
                    customer_id=customer.id,
                    product_id=product.id,
                    sale_date=sale_date,
                    quantity=quantity,
                    unit_price=product.selling_price,
                    discount=discount,
                    revenue=revenue,
                )
            )

        if day_offset % 4 == 0:
            spend = round(rng.uniform(1500, 4500), 2)
            clicks = rng.randint(300, 900)
            db.add(
                MarketingCampaign(
                    business_id=business.id,
                    campaign_date=sale_date,
                    channel=rng.choice(CHANNELS),
                    campaign_name="Demo campaign",
                    spend=spend,
                    impressions=clicks * 15,
                    clicks=clicks,
                    conversions=rng.randint(10, 40),
                    attributed_revenue=round(spend * rng.uniform(1.5, 4.0), 2),
                )
            )

        if day_offset % 14 == 0:
            for product in products:
                db.add(
                    InventoryRecord(
                        business_id=business.id,
                        product_id=product.id,
                        date=sale_date,
                        stock_level=rng.randint(15, 150),
                        reorder_level=20,
                    )
                )

    db.commit()
    return business.id
