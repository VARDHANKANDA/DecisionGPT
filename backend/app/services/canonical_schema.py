"""Canonical business data schemas — the target shape every upload gets
mapped to, per docs/DATA_SPECIFICATION.md §3.

Each canonical type declares required/optional fields, which are dates vs
numeric, and a list of common column-name aliases used to auto-suggest a
mapping from whatever headers the SME's spreadsheet actually has.
"""
from dataclasses import dataclass, field


@dataclass
class FieldSpec:
    aliases: list[str]
    required: bool = False
    kind: str = "string"  # string | number | date | integer


@dataclass
class CanonicalType:
    name: str
    fields: dict[str, FieldSpec]
    sheet_name_aliases: list[str] = field(default_factory=list)

    @property
    def required_fields(self) -> list[str]:
        return [k for k, v in self.fields.items() if v.required]


PRODUCTS = CanonicalType(
    name="products",
    sheet_name_aliases=["products", "product", "items", "catalog"],
    fields={
        "external_product_id": FieldSpec(["product id", "sku", "item id", "product_id", "item_id"], required=True),
        "name": FieldSpec(["product name", "name", "item name", "title"], required=True),
        "category": FieldSpec(["category", "product category", "type"]),
        "unit_cost": FieldSpec(["cost", "unit cost", "cost price", "cogs"], kind="number"),
        "selling_price": FieldSpec(["price", "selling price", "mrp", "unit price"], kind="number", required=True),
        "stock_quantity": FieldSpec(["stock", "quantity", "stock quantity", "qty", "inventory"], kind="integer"),
    },
)

CUSTOMERS = CanonicalType(
    name="customers",
    sheet_name_aliases=["customers", "customer", "clients"],
    fields={
        "external_customer_id": FieldSpec(
            ["customer id", "customer_id", "client id", "cust id"], required=True
        ),
        "segment": FieldSpec(["segment", "customer segment", "tier"]),
        "first_purchase_date": FieldSpec(["first purchase date", "first order date", "joined date"], kind="date"),
        "last_purchase_date": FieldSpec(["last purchase date", "last order date"], kind="date"),
        "purchase_frequency": FieldSpec(["purchase frequency", "order frequency", "frequency"], kind="number"),
        "monetary_value": FieldSpec(["monetary value", "total spent", "lifetime value", "ltv"], kind="number"),
    },
)

SALES = CanonicalType(
    name="sales",
    sheet_name_aliases=["sales", "sale", "orders", "transactions"],
    fields={
        "external_customer_id": FieldSpec(["customer id", "customer_id", "client id"]),
        "external_product_id": FieldSpec(["product id", "sku", "item id", "product_id"]),
        "sale_date": FieldSpec(["date", "sale date", "order date"], kind="date", required=True),
        "quantity": FieldSpec(["quantity", "qty", "units"], kind="number", required=True),
        "unit_price": FieldSpec(["unit price", "price", "selling price"], kind="number", required=True),
        "discount": FieldSpec(["discount", "discount amount"], kind="number"),
        "revenue": FieldSpec(["revenue", "total", "total amount", "sales amount", "amount"], kind="number"),
    },
)

MARKETING = CanonicalType(
    name="marketing_campaigns",
    sheet_name_aliases=["marketing", "campaigns", "ads", "advertising"],
    fields={
        "campaign_date": FieldSpec(["date", "campaign date"], kind="date", required=True),
        "channel": FieldSpec(["channel", "platform", "source"], required=True),
        "campaign_name": FieldSpec(["campaign name", "campaign", "name"]),
        "spend": FieldSpec(["spend", "cost", "amount spent", "budget"], kind="number", required=True),
        "impressions": FieldSpec(["impressions", "views"], kind="integer"),
        "clicks": FieldSpec(["clicks"], kind="integer"),
        "conversions": FieldSpec(["conversions", "orders"], kind="integer"),
        "attributed_revenue": FieldSpec(["attributed revenue", "revenue"], kind="number"),
    },
)

INVENTORY = CanonicalType(
    name="inventory",
    sheet_name_aliases=["inventory", "stock"],
    fields={
        "external_product_id": FieldSpec(["product id", "sku", "item id"], required=True),
        "date": FieldSpec(["date", "stock date"], kind="date", required=True),
        "stock_level": FieldSpec(["stock level", "stock", "quantity", "qty"], kind="integer", required=True),
        "reorder_level": FieldSpec(["reorder level", "reorder point", "minimum stock"], kind="integer"),
    },
)

# --- Tier-1 SME layers: finance + business profile ---------------------
# Optional uploads (docs/INDIAN_SME_DATA_ARCHITECTURE.md). Only the period
# date is required; every metric is optional and a derived ratio is only
# computed when its source fields are present (no fabricated values).

FINANCE = CanonicalType(
    name="finance",
    sheet_name_aliases=["finance", "financials", "financial", "pnl", "p&l", "profit and loss", "accounts"],
    fields={
        "period_date": FieldSpec(
            ["date", "period", "month", "period date", "as of date"], kind="date", required=True
        ),
        "revenue": FieldSpec(["revenue", "sales", "turnover", "total revenue", "income"], kind="number"),
        "cogs": FieldSpec(["cogs", "cost of goods sold", "cost of sales", "direct cost"], kind="number"),
        "gross_profit": FieldSpec(["gross profit", "gross margin value"], kind="number"),
        "operating_expenses": FieldSpec(
            ["operating expenses", "opex", "overheads", "expenses"], kind="number"
        ),
        "net_profit": FieldSpec(["net profit", "profit", "pat", "net income", "bottom line"], kind="number"),
        "cash_balance": FieldSpec(["cash balance", "cash", "bank balance", "closing cash"], kind="number"),
        "accounts_receivable": FieldSpec(
            ["accounts receivable", "receivables", "debtors", "ar"], kind="number"
        ),
        "accounts_payable": FieldSpec(
            ["accounts payable", "payables", "creditors", "ap"], kind="number"
        ),
        "inventory_value": FieldSpec(
            ["inventory value", "stock value", "closing stock value"], kind="number"
        ),
        "loan_amount": FieldSpec(["loan amount", "loan", "borrowings", "debt"], kind="number"),
        "interest_rate": FieldSpec(["interest rate", "rate of interest", "roi"], kind="number"),
        "emi": FieldSpec(["emi", "monthly instalment", "loan repayment"], kind="number"),
    },
)

BUSINESS_PROFILE = CanonicalType(
    name="business_profile",
    sheet_name_aliases=["business profile", "profile", "business details", "company", "about"],
    fields={
        "state": FieldSpec(["state", "province", "region"]),
        "district": FieldSpec(["district", "zila"]),
        "city": FieldSpec(["city", "town", "location"]),
        "enterprise_type": FieldSpec(
            ["enterprise type", "msme category", "udyam category", "size category"]
        ),
        "organisation_type": FieldSpec(
            ["organisation type", "organization type", "legal form", "constitution"]
        ),
        "major_activity": FieldSpec(["major activity", "activity", "nature of business"]),
        "nic_code": FieldSpec(["nic code", "nic", "industry code"]),
        "registration_date": FieldSpec(
            ["registration date", "udyam registration date", "incorporation date", "date of registration"],
            kind="date",
        ),
    },
)

CANONICAL_TYPES: dict[str, CanonicalType] = {
    t.name: t for t in [PRODUCTS, CUSTOMERS, SALES, MARKETING, INVENTORY, FINANCE, BUSINESS_PROFILE]
}


def normalize(text: str) -> str:
    return text.strip().lower().replace("_", " ").replace("-", " ")


def detect_canonical_type(sheet_or_file_name: str) -> str | None:
    normalized = normalize(sheet_or_file_name)
    for canonical_type in CANONICAL_TYPES.values():
        for alias in canonical_type.sheet_name_aliases:
            if alias in normalized:
                return canonical_type.name
    return None
