"""Orchestrates the business data upload pipeline:

    Upload -> Parse -> Detect columns/sheets -> Schema mapping -> Validation
    -> Data quality -> Confirmation -> Store -> Generate business state

(docs/PRD.md §5). Runs synchronously within the request per
docs/BACKEND_SPECIFICATION.md §6 ("keep the initial queue implementation
simple") — the DataIngestionJob row exists so status/results can still be
polled afterward and so an ambiguous mapping can be confirmed and resumed.
"""
from dataclasses import asdict

import pandas as pd
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError, ValidationFailedError
from app.models.business import Business
from app.models.customer import Customer
from app.models.finance import FinanceRecord
from app.models.ingestion_job import DataIngestionJob
from app.models.inventory import InventoryRecord
from app.models.marketing import MarketingCampaign
from app.models.product import Product
from app.models.sale import Sale
from app.services.canonical_schema import CANONICAL_TYPES
from app.services.column_mapping import apply_mapping, suggest_mapping
from app.services.data_validation import validate_mapped_dataframe
from app.services.file_parsing import parse_upload


def _get_or_create_product(db: Session, business_id: str, external_product_id: str) -> Product:
    product = (
        db.query(Product)
        .filter(Product.business_id == business_id, Product.external_product_id == external_product_id)
        .one_or_none()
    )
    if product is None:
        product = Product(
            business_id=business_id, external_product_id=external_product_id, name=external_product_id
        )
        db.add(product)
        db.flush()
    return product


def _get_or_create_customer(db: Session, business_id: str, external_customer_id: str) -> Customer:
    customer = (
        db.query(Customer)
        .filter(Customer.business_id == business_id, Customer.external_customer_id == external_customer_id)
        .one_or_none()
    )
    if customer is None:
        customer = Customer(business_id=business_id, external_customer_id=external_customer_id)
        db.add(customer)
        db.flush()
    return customer


def _ingest_products(db: Session, business_id: str, df: pd.DataFrame) -> int:
    count = 0
    for _, row in df.iterrows():
        product = _get_or_create_product(db, business_id, str(row["external_product_id"]))
        product.name = row.get("name") or product.name
        if "category" in df.columns:
            product.category = row.get("category")
        if "unit_cost" in df.columns and pd.notna(row.get("unit_cost")):
            product.unit_cost = float(row["unit_cost"])
        if "selling_price" in df.columns and pd.notna(row.get("selling_price")):
            product.selling_price = float(row["selling_price"])
        if "stock_quantity" in df.columns and pd.notna(row.get("stock_quantity")):
            product.stock_quantity = int(row["stock_quantity"])
        count += 1
    return count


def _ingest_customers(db: Session, business_id: str, df: pd.DataFrame) -> int:
    count = 0
    for _, row in df.iterrows():
        customer = _get_or_create_customer(db, business_id, str(row["external_customer_id"]))
        for field_name in ["segment", "first_purchase_date", "last_purchase_date", "purchase_frequency", "monetary_value"]:
            if field_name in df.columns and pd.notna(row.get(field_name)):
                value = row[field_name]
                if field_name.endswith("_date"):
                    value = pd.to_datetime(value).date()
                setattr(customer, field_name, value)
        count += 1
    return count


def _ingest_sales(db: Session, business_id: str, df: pd.DataFrame) -> int:
    count = 0
    for _, row in df.iterrows():
        customer_id = None
        product_id = None
        if "external_customer_id" in df.columns and pd.notna(row.get("external_customer_id")):
            customer_id = _get_or_create_customer(db, business_id, str(row["external_customer_id"])).id
        if "external_product_id" in df.columns and pd.notna(row.get("external_product_id")):
            product_id = _get_or_create_product(db, business_id, str(row["external_product_id"])).id

        quantity = int(row["quantity"])
        unit_price = float(row["unit_price"])
        discount = float(row["discount"]) if "discount" in df.columns and pd.notna(row.get("discount")) else 0.0
        revenue = (
            float(row["revenue"])
            if "revenue" in df.columns and pd.notna(row.get("revenue"))
            else round(quantity * unit_price - discount, 2)
        )

        db.add(
            Sale(
                business_id=business_id,
                customer_id=customer_id,
                product_id=product_id,
                sale_date=pd.to_datetime(row["sale_date"]).date(),
                quantity=quantity,
                unit_price=unit_price,
                discount=discount,
                revenue=revenue,
            )
        )
        count += 1
    return count


def _ingest_marketing(db: Session, business_id: str, df: pd.DataFrame) -> int:
    count = 0
    for _, row in df.iterrows():
        db.add(
            MarketingCampaign(
                business_id=business_id,
                campaign_date=pd.to_datetime(row["campaign_date"]).date(),
                channel=str(row["channel"]),
                campaign_name=row.get("campaign_name"),
                spend=float(row["spend"]),
                impressions=int(row["impressions"]) if pd.notna(row.get("impressions")) else None,
                clicks=int(row["clicks"]) if pd.notna(row.get("clicks")) else None,
                conversions=int(row["conversions"]) if pd.notna(row.get("conversions")) else None,
                attributed_revenue=float(row["attributed_revenue"]) if pd.notna(row.get("attributed_revenue")) else None,
            )
        )
        count += 1
    return count


def _ingest_inventory(db: Session, business_id: str, df: pd.DataFrame) -> int:
    count = 0
    for _, row in df.iterrows():
        product_id = _get_or_create_product(db, business_id, str(row["external_product_id"])).id
        db.add(
            InventoryRecord(
                business_id=business_id,
                product_id=product_id,
                date=pd.to_datetime(row["date"]).date(),
                stock_level=int(row["stock_level"]),
                reorder_level=int(row["reorder_level"]) if pd.notna(row.get("reorder_level")) else None,
            )
        )
        count += 1
    return count


_FINANCE_NUMERIC_FIELDS = [
    "revenue", "cogs", "gross_profit", "operating_expenses", "net_profit",
    "cash_balance", "accounts_receivable", "accounts_payable", "inventory_value",
    "loan_amount", "interest_rate", "emi",
]


def _ingest_finance(db: Session, business_id: str, df: pd.DataFrame) -> int:
    count = 0
    for _, row in df.iterrows():
        record = FinanceRecord(
            business_id=business_id,
            period_date=pd.to_datetime(row["period_date"]).date(),
        )
        for field_name in _FINANCE_NUMERIC_FIELDS:
            if field_name in df.columns and pd.notna(row.get(field_name)):
                setattr(record, field_name, float(row[field_name]))
        db.add(record)
        count += 1
    return count


_BUSINESS_PROFILE_FIELDS = [
    "state", "district", "city", "enterprise_type", "organisation_type",
    "major_activity", "nic_code",
]


def _ingest_business_profile(db: Session, business_id: str, df: pd.DataFrame) -> int:
    """Business profile is one row describing the SME itself — it updates the
    Business record rather than creating child rows."""
    business = db.get(Business, business_id)
    if business is None:
        raise NotFoundError(f"Business {business_id} not found.")
    row = df.iloc[0]
    for field_name in _BUSINESS_PROFILE_FIELDS:
        if field_name in df.columns and pd.notna(row.get(field_name)):
            setattr(business, field_name, str(row[field_name]))
    if "registration_date" in df.columns and pd.notna(row.get("registration_date")):
        reg = pd.to_datetime(row["registration_date"])
        business.registration_date = reg.date()
        business.business_age_years = max(0, int((pd.Timestamp.utcnow().tz_localize(None) - reg).days // 365))
    return 1


_INGESTORS = {
    "products": _ingest_products,
    "customers": _ingest_customers,
    "sales": _ingest_sales,
    "marketing_campaigns": _ingest_marketing,
    "inventory": _ingest_inventory,
    "finance": _ingest_finance,
    "business_profile": _ingest_business_profile,
}


def process_upload(
    db: Session,
    business_id: str,
    filename: str,
    content: bytes,
    data_type_hint: str | None = None,
) -> DataIngestionJob:
    job = DataIngestionJob(business_id=business_id, filename=filename, status="processing")
    db.add(job)
    db.flush()

    try:
        parsed = parse_upload(filename, content, data_type_hint)
    except ValidationFailedError as exc:
        job.status = "failed"
        job.error_message = exc.message
        db.commit()
        db.refresh(job)
        return job

    job.detected_types_json = list(parsed.keys())

    pending_mappings = {}
    quality_summary = {}
    ready_to_ingest: dict[str, tuple[pd.DataFrame, dict]] = {}

    for canonical_type_name, df in parsed.items():
        canonical_type = CANONICAL_TYPES[canonical_type_name]
        mapping_result = suggest_mapping(list(df.columns), canonical_type)

        if mapping_result.needs_confirmation:
            pending_mappings[canonical_type_name] = {
                "suggested_mapping": mapping_result.column_to_field,
                "unmapped_required_fields": mapping_result.unmapped_required_fields,
                "available_columns": list(df.columns),
                "raw_records": df.to_dict(orient="records"),
            }
            continue

        ready_to_ingest[canonical_type_name] = (df, mapping_result.column_to_field)

    if pending_mappings:
        job.status = "needs_mapping_confirmation"
        job.mapping_json = pending_mappings
        db.commit()
        db.refresh(job)
        return job

    return _validate_and_ingest(db, job, ready_to_ingest)


def _validate_and_ingest(
    db: Session, job: DataIngestionJob, ready: dict[str, tuple[pd.DataFrame, dict]]
) -> DataIngestionJob:
    quality_summary = {}
    issues_found = False

    mapped_frames: dict[str, pd.DataFrame] = {}
    for canonical_type_name, (df, mapping) in ready.items():
        canonical_type = CANONICAL_TYPES[canonical_type_name]
        mapped_df = apply_mapping(df, mapping)
        report = validate_mapped_dataframe(mapped_df, canonical_type)
        quality_summary[canonical_type_name] = asdict(report)
        if not report.is_valid:
            issues_found = True
        else:
            mapped_frames[canonical_type_name] = mapped_df

    if issues_found:
        job.status = "failed"
        job.summary_json = quality_summary
        job.error_message = "One or more sheets failed data quality validation. See summary_json for details."
        db.commit()
        db.refresh(job)
        return job

    row_counts = {}
    for canonical_type_name, mapped_df in mapped_frames.items():
        ingestor = _INGESTORS[canonical_type_name]
        row_counts[canonical_type_name] = ingestor(db, job.business_id, mapped_df)

    job.status = "completed"
    job.summary_json = {"quality": quality_summary, "rows_ingested": row_counts}
    job.mapping_json = {}
    db.commit()
    db.refresh(job)
    return job


def confirm_mapping(db: Session, business_id: str, job_id: str, mappings: dict[str, dict[str, str]]) -> DataIngestionJob:
    """mappings: {canonical_type: {uploaded_column: canonical_field}}"""
    job = db.get(DataIngestionJob, job_id)
    if job is None or job.business_id != business_id:
        raise NotFoundError(f"Ingestion job {job_id} not found.")
    if job.status != "needs_mapping_confirmation":
        raise ValidationFailedError(f"Job {job_id} is not awaiting mapping confirmation (status={job.status}).")

    ready: dict[str, tuple[pd.DataFrame, dict]] = {}
    for canonical_type_name, pending in job.mapping_json.items():
        confirmed_mapping = mappings.get(canonical_type_name, pending["suggested_mapping"])
        canonical_type = CANONICAL_TYPES[canonical_type_name]
        still_unmapped = [f for f in canonical_type.required_fields if f not in confirmed_mapping.values()]
        if still_unmapped:
            raise ValidationFailedError(
                f"Mapping for '{canonical_type_name}' is still missing required fields: {still_unmapped}"
            )
        df = pd.DataFrame.from_records(pending["raw_records"])
        ready[canonical_type_name] = (df, confirmed_mapping)

    return _validate_and_ingest(db, job, ready)


def get_job(db: Session, business_id: str, job_id: str) -> DataIngestionJob:
    job = db.get(DataIngestionJob, job_id)
    if job is None or job.business_id != business_id:
        raise NotFoundError(f"Ingestion job {job_id} not found.")
    return job


def get_data_summary(db: Session, business_id: str) -> dict:
    business = db.get(Business, business_id)
    profile_set = bool(
        business is not None
        and any(getattr(business, f, None) for f in ("state", "district", "city", "enterprise_type", "nic_code"))
    )
    return {
        "products": db.query(Product).filter(Product.business_id == business_id).count(),
        "customers": db.query(Customer).filter(Customer.business_id == business_id).count(),
        "sales": db.query(Sale).filter(Sale.business_id == business_id).count(),
        "marketing_campaigns": db.query(MarketingCampaign).filter(MarketingCampaign.business_id == business_id).count(),
        "inventory_records": db.query(InventoryRecord).filter(InventoryRecord.business_id == business_id).count(),
        "finance_records": db.query(FinanceRecord).filter(FinanceRecord.business_id == business_id).count(),
        "business_profile_set": profile_set,
    }
