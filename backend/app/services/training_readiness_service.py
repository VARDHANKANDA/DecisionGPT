"""Is this business's stored data fit to forecast from, and to train or evaluate a model on later?

Read-only and tenant-scoped (every query filters on ``business_id``). It reports facts about the stored sales and the ingestion record; it
does not fix anything and it never claims a dataset is real SME data: provenance is what the uploader said, not something DecisionGPT can
verify (a file of retail transactions is not thereby a real SME's).
"""
from __future__ import annotations

from typing import Any

import pandas as pd
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.analytics import business_forecast_service as bfs
from app.core import clock
from app.models.ingestion_job import DataIngestionJob
from app.models.customer import Customer
from app.models.inventory import InventoryRecord
from app.models.product import Product
from app.models.sale import Sale

MIN_DAYS_TO_TRAIN = 180        # a business-specific model needs at least ~6 months and two full weekly cycles per month of data
MIN_SALE_DAYS_TO_TRAIN = 100
MAX_ZERO_RUN_FOR_TRAINING = 14
PRICE_TOLERANCE = 0.02         # unit_price x quantity x (1 - discount%)... see _price_inconsistency


def _price_inconsistency(rows: pd.DataFrame) -> int:
    """Rows whose recorded revenue differs from quantity x unit_price (net of the recorded discount) by more than 2%."""
    if rows.empty:
        return 0
    expected = rows["quantity"] * rows["unit_price"] - rows["discount"].fillna(0)
    denom = expected.abs().clip(lower=1e-9)
    return int((((rows["revenue"] - expected).abs() / denom) > PRICE_TOLERANCE).sum())


EXAMPLE_NOTE = ("Some rows in this business are DecisionGPT example data (products named \"Example:\" or customer ids starting \"EX-\"), "
                "not records of a real business. Results that include them describe the example, not a real business.")


def example_data_note(db: Session, business_id: str) -> str | None:
    """A sentence when the business holds the app's built-in example rows (they are recognisable by construction), else None."""
    n = (db.query(func.count(Product.id)).filter(Product.business_id == business_id, Product.name.like("Example:%")).scalar() or 0) +         (db.query(func.count(Customer.id)).filter(Customer.business_id == business_id, Customer.external_customer_id.like("EX-%")).scalar() or 0)
    return EXAMPLE_NOTE if n else None


def readiness(db: Session, business_id: str) -> dict[str, Any]:
    sales = pd.DataFrame(
        [{"sale_date": s.sale_date, "product_id": s.product_id, "customer_id": s.customer_id, "quantity": int(s.quantity),
          "unit_price": float(s.unit_price), "discount": float(s.discount or 0), "revenue": float(s.revenue)}
         for s in db.query(Sale).filter(Sale.business_id == business_id).all()]
    )
    jobs = db.query(DataIngestionJob).filter(DataIngestionJob.business_id == business_id).order_by(DataIngestionJob.created_at).all()
    sources = [{"filename": j.filename, "status": j.status, "uploaded_at": j.created_at.isoformat() if j.created_at else None,
                "types": list(j.detected_types_json or [])} for j in jobs]
    example_note = example_data_note(db, business_id)
    out: dict[str, Any] = {
        "business_scope": "this business only; data of different businesses is never pooled into one training population",
        "provenance": {
            "sources": sources, "uploads": len(sources), "currency": "INR (assumed; the upload does not record a currency)",
            "timezone": "none: dates are calendar dates without a time zone, interpreted as the business's local day",
            "statement": "provenance is the uploader's statement; DecisionGPT cannot verify that a file is real small-business data",
        },
        "example_data": example_note,
        "original_uploads": "file contents are parsed into the business tables; the preprocessing run record (data_prep_runs) keeps what each "
                            "cleaning step changed, with undo information for consequential changes",
    }
    if sales.empty:
        blockers = ["No sales are stored for this business."]
        waiting = [j for j in jobs if j.status == "needs_mapping_confirmation"]
        failed = [j for j in jobs if j.status == "failed"]
        if waiting:
            blockers.append(f"{len(waiting)} uploaded file(s) are waiting for you to confirm which column is which "
                            f"({', '.join(sorted({j.filename for j in waiting}))}); nothing from them is stored until you do.")
        if failed:
            last = failed[-1]
            blockers.append(f"{len(failed)} upload(s) failed; the latest ({last.filename}): {last.error_message or 'see the upload summary'}")
        out.update(sales={"rows": 0}, ready_for_forecast=False, ready_for_training=False, blockers=blockers, issues=[])
        return out

    sales["sale_date"] = pd.to_datetime(sales["sale_date"])
    daily = sales.groupby("sale_date")["quantity"].sum()
    full = pd.date_range(daily.index.min(), daily.index.max(), freq="D")
    series = daily.reindex(full, fill_value=0).rename_axis("date").reset_index().rename(columns={"quantity": "units_sold"})
    prof = bfs.profile_series(series)

    key = ["sale_date", "product_id", "customer_id", "quantity", "unit_price"]
    dup = int(sales.duplicated(key).sum())
    returns = int((sales["quantity"] < 0).sum())
    bad_price = int((sales["unit_price"] <= 0).sum())
    price_incon = _price_inconsistency(sales[sales["quantity"] > 0])
    issues: list[dict[str, Any]] = []

    def add(kind: str, n: int, detail: str, severity: str = "warning"):
        if n:
            issues.append({"kind": kind, "rows": n, "severity": severity, "detail": detail})

    add("duplicate_rows", dup, "Identical date / product / customer / quantity / price rows. They may be genuine repeat sales; they are kept, not removed.")
    add("returns_or_negative_quantity", returns, "Negative quantities (returns). The daily units target counts them as written; confirm they are returns.")
    add("non_positive_price", bad_price, "Rows with a zero or negative unit price.", "error")
    add("revenue_not_quantity_times_price", price_incon, "Recorded revenue differs from quantity x unit price (net of discount) by more than 2%.")
    if prof["longest_zero_run_days"] >= MAX_ZERO_RUN_FOR_TRAINING:
        add("long_zero_run", 1, f"{prof['longest_zero_run_days']} consecutive days with no sales: a closure, a stockout or a gap in the upload. "
                                "The data cannot tell which; zeros are treated as real.")
    inv_zero = (db.query(func.count(InventoryRecord.id)).filter(InventoryRecord.business_id == business_id, InventoryRecord.stock_level <= 0).scalar() or 0)
    if inv_zero:
        add("possible_stockouts", int(inv_zero), "Inventory records with zero stock: zero sales on those days may reflect no stock rather than no demand.", "info")

    last = full[-1].date()
    blockers: list[str] = []
    if prof["days"] < bfs.MIN_DAYS_ANY or prof["sale_days"] < bfs.MIN_SALE_DAYS_ANY:
        blockers.append(f"A forecast needs at least {bfs.MIN_DAYS_ANY} days with sales on {bfs.MIN_SALE_DAYS_ANY} of them "
                        f"(you have {prof['days']} days of history and {prof['sale_days']} days with sales).")
    train_blockers: list[str] = []
    if prof["days"] < MIN_DAYS_TO_TRAIN:
        train_blockers.append(f"A business-specific model needs at least {MIN_DAYS_TO_TRAIN} days of history (you have {prof['days']}).")
    if prof["sale_days"] < MIN_SALE_DAYS_TO_TRAIN:
        train_blockers.append(f"It needs at least {MIN_SALE_DAYS_TO_TRAIN} days with sales (you have {prof['sale_days']}).")
    if prof["longest_zero_run_days"] >= MAX_ZERO_RUN_FOR_TRAINING:
        train_blockers.append("A long run of zero-sale days must be explained (closure vs gap) before it is used for training.")
    if any(i["kind"] == "non_positive_price" for i in issues):
        train_blockers.append("Rows with non-positive prices must be corrected.")
    out.update(
        sales={**prof, "rows": int(len(sales)), "products": int(sales["product_id"].nunique()), "date_range": [prof["first_date"], prof["last_date"]],
               "days_since_last_sale": (clock.today() - last).days},
        target={"name": "units_sold", "unit": prof["target_unit"], "aggregation": prof["aggregation"],
                "required_columns_present": True, "note": "target = quantity summed over all products per calendar day"},
        issues=issues, blockers=blockers, ready_for_forecast=not blockers, ready_for_training=not blockers and not train_blockers,
        training_blockers=train_blockers,
        evidence_note="Even a ready business has no outcome labels recorded here: a model trained on this data is validated only on its own "
                      "chronological holdout, never on other businesses.",
    )
    return out
