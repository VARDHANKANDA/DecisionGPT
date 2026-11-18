"""Row-level management of a business's own uploaded / entered data.

Powers the "My Data" screens: list what is stored, view and edit rows, add
rows by hand, and delete rows or a whole table. Everything is scoped by
`business_id` (AGENTS.md "Data isolation") and acts on the same canonical
tables the analytics read — nothing here is a copy or a mock.

Manual rows go through the *same* validation and ingestion code as uploaded
files (`validate_mapped_dataframe` + the `_INGESTORS` table), so entered data
is checked exactly like uploaded data.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

import pandas as pd
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError, ValidationFailedError
from app.models.customer import Customer
from app.models.finance import FinanceRecord
from app.models.ingestion_job import DataIngestionJob
from app.models.inventory import InventoryRecord
from app.models.marketing import MarketingCampaign
from app.models.product import Product
from app.models.sale import Sale
from app.services.canonical_schema import CANONICAL_TYPES
from app.services.data_ingestion_service import _INGESTORS
from app.services.data_validation import validate_mapped_dataframe


@dataclass(frozen=True)
class Col:
    key: str
    label: str
    kind: str  # text | number | integer | date
    editable: bool = True


@dataclass(frozen=True)
class TableSpec:
    type: str
    model: Any
    title: str
    description: str
    columns: tuple[Col, ...]
    canonical: str  # key into CANONICAL_TYPES used for validating manual rows


TABLES: dict[str, TableSpec] = {
    "sales": TableSpec(
        "sales", Sale, "Sales",
        "Each sale: the date, what was sold, how many, and the amount.",
        (
            Col("sale_date", "Date", "date"),
            Col("product", "Product", "text", editable=False),
            Col("customer", "Customer", "text", editable=False),
            Col("quantity", "Quantity", "integer"),
            Col("unit_price", "Price each (₹)", "number"),
            Col("discount", "Discount (₹)", "number"),
            Col("revenue", "Total (₹)", "number"),
        ),
        "sales",
    ),
    "customers": TableSpec(
        "customers", Customer, "Customers",
        "Your customers: when they first and last bought, how often, and how much they spent.",
        (
            Col("external_customer_id", "Customer ID", "text"),
            Col("segment", "Group", "text"),
            Col("first_purchase_date", "First purchase", "date"),
            Col("last_purchase_date", "Last purchase", "date"),
            Col("purchase_frequency", "Times bought", "number"),
            Col("monetary_value", "Total spent (₹)", "number"),
        ),
        "customers",
    ),
    "products": TableSpec(
        "products", Product, "Products",
        "The things you sell, with their price, cost and stock.",
        (
            Col("external_product_id", "Product ID", "text"),
            Col("name", "Name", "text"),
            Col("category", "Category", "text"),
            Col("unit_cost", "Cost each (₹)", "number"),
            Col("selling_price", "Selling price (₹)", "number"),
            Col("stock_quantity", "In stock", "integer"),
        ),
        "products",
    ),
    "inventory": TableSpec(
        "inventory", InventoryRecord, "Stock levels",
        "How much stock you had of each product on a given day.",
        (
            Col("date", "Date", "date"),
            Col("product", "Product", "text", editable=False),
            Col("stock_level", "In stock", "integer"),
            Col("reorder_level", "Reorder at", "integer"),
        ),
        "inventory",
    ),
    "marketing_campaigns": TableSpec(
        "marketing_campaigns", MarketingCampaign, "Marketing",
        "Money spent on advertising and what it brought in.",
        (
            Col("campaign_date", "Date", "date"),
            Col("channel", "Where", "text"),
            Col("campaign_name", "Campaign", "text"),
            Col("spend", "Spent (₹)", "number"),
            Col("impressions", "Times shown", "integer"),
            Col("clicks", "Clicks", "integer"),
            Col("conversions", "Orders", "integer"),
            Col("attributed_revenue", "Sales from it (₹)", "number"),
        ),
        "marketing_campaigns",
    ),
    "finance": TableSpec(
        "finance", FinanceRecord, "Money & accounts",
        "Monthly money figures such as income, costs and profit.",
        (
            Col("period_date", "Month", "date"),
            Col("revenue", "Income (₹)", "number"),
            Col("cogs", "Cost of goods (₹)", "number"),
            Col("operating_expenses", "Running costs (₹)", "number"),
            Col("net_profit", "Profit (₹)", "number"),
            Col("cash_balance", "Cash in hand (₹)", "number"),
        ),
        "finance",
    ),
}


def _spec(table_type: str) -> TableSpec:
    spec = TABLES.get(table_type)
    if spec is None:
        raise NotFoundError(f"Unknown data type '{table_type}'.")
    return spec


def _base_query(db: Session, spec: TableSpec, business_id: str):
    return db.query(spec.model).filter(spec.model.business_id == business_id)


def _iso(v: Any) -> Any:
    if isinstance(v, (date, datetime)):
        return v.isoformat()[:10] if isinstance(v, date) and not isinstance(v, datetime) else v.date().isoformat()
    if v is None:
        return None
    if hasattr(v, "__float__") and not isinstance(v, (int, float, str)):
        return float(v)
    return v


def _row_values(db: Session, spec: TableSpec, obj: Any, names: dict[str, dict[str, str]]) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for col in spec.columns:
        if col.key == "product":
            pid = getattr(obj, "product_id", None)
            values[col.key] = names["products"].get(pid) if pid else None
        elif col.key == "customer":
            cid = getattr(obj, "customer_id", None)
            values[col.key] = names["customers"].get(cid) if cid else None
        else:
            values[col.key] = _iso(getattr(obj, col.key, None))
    return values


def _name_maps(db: Session, business_id: str) -> dict[str, dict[str, str]]:
    return {
        "products": {p.id: p.name for p in db.query(Product.id, Product.name).filter(Product.business_id == business_id)},
        "customers": {
            c.id: (c.external_customer_id or "—")
            for c in db.query(Customer.id, Customer.external_customer_id).filter(Customer.business_id == business_id)
        },
    }


def _last_updated(db: Session, spec: TableSpec, business_id: str) -> datetime | None:
    model = spec.model
    col = getattr(model, "updated_at", None) or getattr(model, "created_at", None)
    if col is None:
        return None
    return db.query(col).filter(model.business_id == business_id).order_by(col.desc()).limit(1).scalar()


def library(db: Session, business_id: str) -> list[dict]:
    """One entry per kind of data. Every kind is listed (so the user can see
    what they could add); `rows == 0` means nothing stored yet."""
    jobs = (
        db.query(DataIngestionJob)
        .filter(DataIngestionJob.business_id == business_id, DataIngestionJob.status == "completed")
        .order_by(DataIngestionJob.created_at.desc())
        .all()
    )
    out = []
    for spec in TABLES.values():
        rows = _base_query(db, spec, business_id).count()
        files = []
        for j in jobs:
            ingested = (j.summary_json or {}).get("rows_ingested", {})
            if spec.canonical in ingested or spec.type in ingested:
                files.append({"filename": j.filename, "uploaded_at": j.created_at, "rows": ingested.get(spec.canonical, ingested.get(spec.type))})
        out.append(
            {
                "type": spec.type,
                "title": spec.title,
                "description": spec.description,
                "rows": rows,
                "columns": len(spec.columns),
                "last_updated": _last_updated(db, spec, business_id) if rows else None,
                "source_files": files[:5],
            }
        )
    return out


def upload_history(db: Session, business_id: str) -> list[DataIngestionJob]:
    return (
        db.query(DataIngestionJob)
        .filter(DataIngestionJob.business_id == business_id)
        .order_by(DataIngestionJob.created_at.desc())
        .limit(50)
        .all()
    )


def list_rows(db: Session, business_id: str, table_type: str, offset: int = 0, limit: int = 25) -> dict:
    spec = _spec(table_type)
    limit = max(1, min(limit, 200))
    q = _base_query(db, spec, business_id)
    total = q.count()
    order_col = (
        getattr(spec.model, "sale_date", None)
        or getattr(spec.model, "campaign_date", None)
        or getattr(spec.model, "period_date", None)
        or getattr(spec.model, "date", None)
        or spec.model.created_at
    )
    rows = q.order_by(order_col.desc(), spec.model.id).offset(max(0, offset)).limit(limit).all()
    names = _name_maps(db, business_id)
    return {
        "type": spec.type,
        "title": spec.title,
        "description": spec.description,
        "columns": [{"key": c.key, "label": c.label, "kind": c.kind, "editable": c.editable} for c in spec.columns],
        "rows": [{"id": r.id, "values": _row_values(db, spec, r, names)} for r in rows],
        "total": total,
        "offset": offset,
        "limit": limit,
    }


def _coerce(col: Col, raw: Any) -> Any:
    if raw is None or (isinstance(raw, str) and raw.strip() == ""):
        return None
    try:
        if col.kind == "integer":
            return int(float(raw))
        if col.kind == "number":
            return float(raw)
        if col.kind == "date":
            return pd.to_datetime(raw).date()
    except (ValueError, TypeError):
        raise ValidationFailedError(f"'{raw}' is not a valid value for {col.label}.") from None
    return str(raw).strip()


def update_row(db: Session, business_id: str, table_type: str, row_id: str, changes: dict[str, Any]) -> dict:
    spec = _spec(table_type)
    obj = _base_query(db, spec, business_id).filter(spec.model.id == row_id).one_or_none()
    if obj is None:
        raise NotFoundError("That row was not found.")
    cols = {c.key: c for c in spec.columns}
    for key, raw in changes.items():
        col = cols.get(key)
        if col is None or not col.editable:
            raise ValidationFailedError(f"'{key}' can't be changed here.")
        value = _coerce(col, raw)
        if value is None and key in {"sale_date", "quantity", "unit_price", "revenue", "date", "stock_level",
                                      "campaign_date", "channel", "spend", "period_date", "name"}:
            raise ValidationFailedError(f"{col.label} can't be left empty.")
        setattr(obj, key, value)
    if spec.type == "sales" and "revenue" not in changes and {"quantity", "unit_price", "discount"} & set(changes):
        # Total is derived when it wasn't edited directly — keep rows self-consistent.
        obj.revenue = round(float(obj.quantity) * float(obj.unit_price) - float(obj.discount or 0), 2)
    db.commit()
    db.refresh(obj)
    names = _name_maps(db, business_id)
    return {"id": obj.id, "values": _row_values(db, spec, obj, names)}


def _detach_references(db: Session, business_id: str, table_type: str, ids: list[str] | None) -> None:
    """Deleting products/customers must not leave dangling references."""
    if table_type == "products":
        sales = db.query(Sale).filter(Sale.business_id == business_id, Sale.product_id.isnot(None))
        inv = db.query(InventoryRecord).filter(InventoryRecord.business_id == business_id)
        if ids is not None:
            sales, inv = sales.filter(Sale.product_id.in_(ids)), inv.filter(InventoryRecord.product_id.in_(ids))
        sales.update({Sale.product_id: None}, synchronize_session=False)
        inv.delete(synchronize_session=False)
    elif table_type == "customers":
        sales = db.query(Sale).filter(Sale.business_id == business_id, Sale.customer_id.isnot(None))
        if ids is not None:
            sales = sales.filter(Sale.customer_id.in_(ids))
        sales.update({Sale.customer_id: None}, synchronize_session=False)


def delete_row(db: Session, business_id: str, table_type: str, row_id: str) -> None:
    spec = _spec(table_type)
    obj = _base_query(db, spec, business_id).filter(spec.model.id == row_id).one_or_none()
    if obj is None:
        raise NotFoundError("That row was not found.")
    _detach_references(db, business_id, table_type, [row_id])
    db.delete(obj)
    db.commit()


def clear_table(db: Session, business_id: str, table_type: str) -> int:
    spec = _spec(table_type)
    _detach_references(db, business_id, table_type, None)
    n = _base_query(db, spec, business_id).delete(synchronize_session=False)
    db.commit()
    return n


# Manual-entry field names the UI sends -> the canonical field names the
# ingestors expect (sales/inventory refer to products & customers by their own ID).
_MANUAL_ALIASES = {
    "sales": {"product": "external_product_id", "customer": "external_customer_id"},
    "inventory": {"product": "external_product_id"},
}


def add_rows(db: Session, business_id: str, table_type: str, rows: list[dict[str, Any]]) -> dict:
    """Validate then store hand-entered rows with the same pipeline as uploads."""
    spec = _spec(table_type)
    if table_type not in _INGESTORS and spec.canonical not in _INGESTORS:
        raise ValidationFailedError("This kind of data can't be entered by hand.")
    if not rows:
        raise ValidationFailedError("Add at least one row.")
    aliases = _MANUAL_ALIASES.get(table_type, {})
    cleaned = []
    for r in rows:
        item = {}
        for k, v in r.items():
            if v is None or (isinstance(v, str) and v.strip() == ""):
                continue
            item[aliases.get(k, k)] = v
        cleaned.append(item)
    df = pd.DataFrame(cleaned)
    canonical = CANONICAL_TYPES[spec.canonical]
    report = validate_mapped_dataframe(df, canonical)
    labels = {c.key: c.label for c in spec.columns}
    labels.update({"external_product_id": "Product", "external_customer_id": "Customer"})
    problems: list[str] = []
    for f in canonical.required_fields:
        if f not in df.columns:
            problems.append(f"Please fill in “{labels.get(f, f.replace('_', ' '))}”.")
        elif f in report.missing_required_field_values:
            n = report.missing_required_field_values[f]
            problems.append(f"{n} row(s) are missing “{labels.get(f, f.replace('_', ' '))}”.")
    for f, n in report.invalid_date_rows.items():
        problems.append(f"{n} row(s) have a date we couldn't read in “{labels.get(f, f)}”.")
    if len(df) == 0:
        problems.append("Add at least one row.")
    # Two identical rows are legitimate when typing by hand (e.g. two equal sales), so
    # the upload-only "duplicate rows" warning is deliberately not enforced here.
    if problems:
        raise ValidationFailedError(" ".join(problems), {"issues": problems})
    count = _INGESTORS[spec.canonical](db, business_id, df)
    db.commit()
    return {"added": count}
