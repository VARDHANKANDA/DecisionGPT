"""Orchestrates the business data upload pipeline:

    Upload -> Read & clean (app/services/upload_preprocessing.py) -> Detect the kind of data -> Schema mapping -> Typed conversion
    -> Validation -> Confirmation (only when something is genuinely ambiguous) -> Store -> Report

(docs/PRD.md §5). Runs synchronously within the request per docs/BACKEND_SPECIFICATION.md §6. The DataIngestionJob row exists so the result can be
read back and so an ambiguous mapping or date order can be confirmed and resumed from the ORIGINAL file, which is kept unchanged.

Guarantees: all or nothing (every table of one upload is stored in a single transaction); the original is never altered; rows that cannot be
read are reported, not repaired; nothing is imputed; a failure is a clear message on the job, never a server error with half the data saved.
"""
from dataclasses import asdict
from datetime import datetime, timezone
import math
import logging

import pandas as pd
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import NotFoundError, ValidationFailedError
from app.models.business import Business
from app.models.customer import Customer
from app.models.finance import FinanceRecord
from app.models.ingestion_job import DataIngestionJob
from app.models.inventory import InventoryRecord
from app.models.marketing import MarketingCampaign
from app.models.product import Product
from app.models.sale import Sale
from app.services import upload_preprocessing as prep
from app.services import upload_storage
from app.services.canonical_schema import CANONICAL_TYPES, detect_canonical_type
from app.services.column_mapping import suggest_mapping
from app.services.data_validation import validate_mapped_dataframe

log = logging.getLogger("decisiongpt.ingestion")
STATUS_PENDING = "needs_mapping_confirmation"
_CHUNK = 400                                                          # ids per IN (...) query: stays under SQLite's variable limit


# ------------------------------------------------------------------------------------------------ small value helpers (used by every ingestor)
def _present(v) -> bool:
    return v is not None and not (isinstance(v, float) and math.isnan(v)) and not (v is pd.NaT) and not (isinstance(v, str) and v.strip() == "")


def _as_int(v, field: str) -> int:
    """An integer column holds whole numbers: 2.0 is 2, 2.5 is refused (never silently cut to 2)."""
    f = float(v)
    if not math.isfinite(f) or f != int(f):
        raise ValidationFailedError(f"'{field}' must be a whole number; {v} is not. Quantities with decimals (for example 2.5 kg) are not supported yet.")
    return int(f)


def _text_id(v) -> str:
    """An identifier as text. Excel stores 1001 as the number 1001.0; it must not become '1001.0'."""
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v).strip()


# ------------------------------------------------------------------------------------------------ ingestors (the canonical tables)
def _bulk_ids(db: Session, model, business_id: str, column: str, wanted: set[str], make) -> dict[str, str]:
    """external id -> row id for every wanted id: existing rows are found in a few queries, missing ones are created in one batch."""
    attr = getattr(model, column)
    found: dict[str, str] = {}
    ids = sorted(wanted)
    for i in range(0, len(ids), _CHUNK):
        for ext, pk in db.query(attr, model.id).filter(model.business_id == business_id, attr.in_(ids[i:i + _CHUNK])).all():
            found[ext] = pk
    missing = [x for x in ids if x not in found]
    if missing:
        new = [make(x) for x in missing]
        db.add_all(new)
        db.flush()
        for obj, ext in zip(new, missing):
            found[ext] = obj.id
    return found


def _get_or_create_product(db: Session, business_id: str, external_product_id: str) -> Product:
    product = (
        db.query(Product)
        .filter(Product.business_id == business_id, Product.external_product_id == external_product_id)
        .one_or_none()
    )
    if product is None:
        product = Product(business_id=business_id, external_product_id=external_product_id, name=external_product_id)
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
        product = _get_or_create_product(db, business_id, _text_id(row["external_product_id"]))
        if _present(row.get("name")):
            product.name = str(row["name"])
        if "category" in df.columns and _present(row.get("category")):
            product.category = str(row["category"])
        if "unit_cost" in df.columns and _present(row.get("unit_cost")):
            product.unit_cost = float(row["unit_cost"])
        if "selling_price" in df.columns and _present(row.get("selling_price")):
            product.selling_price = float(row["selling_price"])
        if "stock_quantity" in df.columns and _present(row.get("stock_quantity")):
            product.stock_quantity = _as_int(row["stock_quantity"], "stock_quantity")
        count += 1
    return count


def _ingest_customers(db: Session, business_id: str, df: pd.DataFrame) -> int:
    count = 0
    for _, row in df.iterrows():
        customer = _get_or_create_customer(db, business_id, _text_id(row["external_customer_id"]))
        for field_name in ["segment", "first_purchase_date", "last_purchase_date", "purchase_frequency", "monetary_value"]:
            if field_name in df.columns and _present(row.get(field_name)):
                value = row[field_name]
                if field_name.endswith("_date"):
                    value = pd.to_datetime(value).date()
                setattr(customer, field_name, value)
        count += 1
    return count


def _ingest_sales(db: Session, business_id: str, df: pd.DataFrame) -> int:
    has_cust = "external_customer_id" in df.columns
    has_prod = "external_product_id" in df.columns
    cust_ids = {}
    prod_ids = {}
    if has_cust:
        wanted = {_text_id(v) for v in df["external_customer_id"] if _present(v)}
        cust_ids = _bulk_ids(db, Customer, business_id, "external_customer_id", wanted,
                             lambda x: Customer(business_id=business_id, external_customer_id=x))
    if has_prod:
        wanted = {_text_id(v) for v in df["external_product_id"] if _present(v)}
        prod_ids = _bulk_ids(db, Product, business_id, "external_product_id", wanted,
                             lambda x: Product(business_id=business_id, external_product_id=x, name=x))
    rows = []
    for _, row in df.iterrows():
        quantity = _as_int(row["quantity"], "quantity")
        unit_price = float(row["unit_price"])
        discount = float(row["discount"]) if "discount" in df.columns and _present(row.get("discount")) else 0.0
        revenue = float(row["revenue"]) if "revenue" in df.columns and _present(row.get("revenue")) else round(quantity * unit_price - discount, 2)
        rows.append(dict(
            business_id=business_id,
            customer_id=cust_ids.get(_text_id(row["external_customer_id"])) if has_cust and _present(row.get("external_customer_id")) else None,
            product_id=prod_ids.get(_text_id(row["external_product_id"])) if has_prod and _present(row.get("external_product_id")) else None,
            sale_date=pd.to_datetime(row["sale_date"]).date(), quantity=quantity, unit_price=unit_price, discount=discount, revenue=revenue,
        ))
    for i in range(0, len(rows), 2000):
        db.bulk_insert_mappings(Sale, rows[i:i + 2000])
    return len(rows)


def _ingest_marketing(db: Session, business_id: str, df: pd.DataFrame) -> int:
    def opt_int(row, name):
        return _as_int(row[name], name) if name in df.columns and _present(row.get(name)) else None

    count = 0
    for _, row in df.iterrows():
        db.add(
            MarketingCampaign(
                business_id=business_id,
                campaign_date=pd.to_datetime(row["campaign_date"]).date(),
                channel=str(row["channel"]),
                campaign_name=str(row["campaign_name"]) if _present(row.get("campaign_name")) else None,
                spend=float(row["spend"]),
                impressions=opt_int(row, "impressions"),
                clicks=opt_int(row, "clicks"),
                conversions=opt_int(row, "conversions"),
                attributed_revenue=float(row["attributed_revenue"]) if "attributed_revenue" in df.columns and _present(row.get("attributed_revenue")) else None,
            )
        )
        count += 1
    return count


def _ingest_inventory(db: Session, business_id: str, df: pd.DataFrame) -> int:
    count = 0
    for _, row in df.iterrows():
        product_id = _get_or_create_product(db, business_id, _text_id(row["external_product_id"])).id
        db.add(
            InventoryRecord(
                business_id=business_id,
                product_id=product_id,
                date=pd.to_datetime(row["date"]).date(),
                stock_level=_as_int(row["stock_level"], "stock_level"),
                reorder_level=_as_int(row["reorder_level"], "reorder_level") if "reorder_level" in df.columns and _present(row.get("reorder_level")) else None,
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
            if field_name in df.columns and _present(row.get(field_name)):
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
        if field_name in df.columns and _present(row.get(field_name)):
            setattr(business, field_name, str(row[field_name]))
    if "registration_date" in df.columns and _present(row.get("registration_date")):
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

# stored as whole numbers: a value with decimals is refused rather than cut
_WHOLE_NUMBER_FIELDS = {("sales", "quantity")}


# ------------------------------------------------------------------------------------------------ typed conversion of one mapped table
def coerce_for_import(df: pd.DataFrame, type_name: str, date_orders: dict[str, str] | None = None):
    """Turn a mapped text table into typed values. Returns (clean frame, skipped rows, blocking issues, notes, date questions).

    A row is skipped (and reported with its reason) when a REQUIRED value is missing or cannot be read unambiguously. An optional value that
    cannot be read is left empty and counted. A whole-number field holding decimals is a blocking issue: it is never truncated."""
    canonical = CANONICAL_TYPES[type_name]
    date_orders = date_orders or {}
    out = df.copy()
    skip: dict[int, str] = {}
    issues: list[str] = []
    notes: list[str] = []
    questions: list[dict] = []
    for fname, spec in canonical.fields.items():
        if fname not in out.columns:
            continue
        col = out[fname]
        required = fname in canonical.required_fields
        kind = spec.kind
        if kind == "date":
            res = prep.coerce_dates(col, date_orders.get(fname), column=fname)
            if res.question is not None:
                questions.append({"field": fname, "examples": res.question.examples})
                continue
            out[fname] = res.values
            notes += [f"{fname}: {n}" for n in res.notes]
            bad = res.invalid
            label = "unreadable date"
            examples = res.examples
        elif kind in ("number", "integer"):
            res = prep.coerce_numeric(col)
            out[fname] = res.values
            notes += [f"{fname}: {n}" for n in res.notes]
            bad = res.invalid
            label = "unreadable number"
            examples = res.examples
            whole = kind == "integer" or (type_name, fname) in _WHOLE_NUMBER_FIELDS
            if whole:
                vals = res.values.dropna()
                frac = vals[(vals - vals.round()).abs() > 1e-9]
                if len(frac):
                    issues.append(f"'{fname}' has {len(frac)} value(s) with decimals (for example {frac.iloc[0]:g}). This field holds whole numbers only, "
                                  "and the file was NOT imported so that nothing is rounded without your knowledge.")
        else:
            out[fname] = col.map(lambda v: None if not _present(v) else (_text_id(v) if isinstance(v, (float, int)) and not isinstance(v, bool) else str(v).strip()))
            continue
        for i in out.index[bad.values]:
            if required:
                skip.setdefault(int(i), f"{label} in '{fname}'" + (f" ({examples[0]})" if examples else ""))
            else:
                notes.append(f"'{fname}': {int(bad.sum())} value(s) could not be read and were left empty.")
                break
        if required:
            for i in out.index[col.map(lambda v: not _present(v)).values]:
                skip.setdefault(int(i), f"missing '{fname}'")
    skipped = [{"row": int(i) + 1, "reason": r} for i, r in sorted(skip.items())]
    clean = out.drop(index=list(skip)) if skip else out
    return clean.reset_index(drop=True), skipped, issues, notes, questions


# ------------------------------------------------------------------------------------------------ assigning a kind of data to each table
def _infer_type_from_columns(columns: list[str]) -> str | None:
    """The one kind whose REQUIRED columns can all be matched; the best fit if several qualify; None when nothing or a tie."""
    fits = []
    for name, ctype in CANONICAL_TYPES.items():
        m = suggest_mapping(columns, ctype)
        # all REQUIRED columns matched, and enough columns matched for that to mean something: a kind with no required columns (the business
        # profile) must not "fit" every sheet just because nothing was required of it
        if not m.needs_confirmation and len(m.column_to_field) >= max(len(ctype.required_fields), 2):
            fits.append((len(m.column_to_field), name))
    fits.sort(reverse=True)
    if not fits or (len(fits) > 1 and fits[0][0] == fits[1][0]):
        return None
    return fits[0][1]


def assign_types(read: prep.ReadResult, filename: str, hint: str | None) -> tuple[dict[str, str], list[dict[str, str]]]:
    """table name -> canonical type, plus the tables that were NOT used (with the reason; never dropped silently)."""
    if hint is not None and hint not in CANONICAL_TYPES:
        raise ValidationFailedError(f"Unknown data type '{hint}'. Supported: " + "|".join(sorted(CANONICAL_TYPES)))
    assigned: dict[str, str] = {}
    unused: list[dict[str, str]] = list(read.ignored_sheets)
    is_csv = filename.lower().endswith(".csv")
    names = list(read.frames)
    for name in names:
        cols = list(read.frames[name].columns)
        t = hint if (is_csv or len(names) == 1) and hint else None
        t = t or (detect_canonical_type(filename) if is_csv else detect_canonical_type(name))
        t = t or _infer_type_from_columns(cols)
        if t is None:
            unused.append({"sheet": name, "reason": "could not tell what kind of data this is from its name or columns"})
        elif t in assigned.values():
            unused.append({"sheet": name, "reason": f"another sheet already provides the {t.replace('_', ' ')} data (one table per kind of data per upload)"})
        else:
            assigned[name] = t
    if not assigned:
        raise ValidationFailedError(
            "We could not tell what kind of data this file holds. Choose it under 'What is in this file?' "
            "(Sales, Customers, Products, Stock levels, Marketing, Money & accounts) and upload again. "
            + (f"Sheets found: {', '.join(names)}." if not is_csv else "")
        )
    return assigned, unused


# ------------------------------------------------------------------------------------------------ the pipeline
def _fail(db: Session, job: DataIngestionJob, message: str, summary: dict | None = None) -> DataIngestionJob:
    db.rollback()
    job = db.get(DataIngestionJob, job.id)
    upload_storage.delete_original(job.storage_key)
    job.status = "failed"
    job.error_message = message
    job.storage_key = None
    if summary is not None:
        job.summary_json = summary
    job.mapping_json = {}
    db.commit()
    db.refresh(job)
    return job


def _mapping_for(read: prep.ReadResult, assigned: dict[str, str]) -> dict:
    out = {}
    for name, tname in assigned.items():
        df = read.frames[name]
        m = suggest_mapping(list(df.columns), CANONICAL_TYPES[tname])
        out[name] = (tname, m)
    return out


def process_upload(
    db: Session,
    business_id: str,
    filename: str,
    content: bytes,
    data_type_hint: str | None = None,
    allow_duplicate_file: bool = False,
) -> DataIngestionJob:
    settings = get_settings()
    shown = prep.safe_display_name(filename)
    digest = prep.sha256_hex(content)
    job = DataIngestionJob(business_id=business_id, filename=shown, status="processing", file_sha256=digest, file_size=len(content))
    db.add(job)
    db.commit()                                                            # the job exists even if everything after this fails
    db.refresh(job)

    if len(content) > settings.max_upload_bytes:
        return _fail(db, job, f"This file is larger than the {settings.max_upload_bytes // (1024 * 1024)} MB limit. Split it into smaller "
                              "files (for example by month) and upload them one at a time.")
    previous = (db.query(DataIngestionJob)
                .filter(DataIngestionJob.business_id == business_id, DataIngestionJob.file_sha256 == digest, DataIngestionJob.status == "completed",
                        DataIngestionJob.id != job.id).order_by(DataIngestionJob.created_at.desc()).first())
    if previous is not None and not allow_duplicate_file:
        when = previous.created_at.strftime("%d %b %Y") if previous.created_at else "earlier"
        return _fail(db, job, f"This exact file was already imported on {when}. Nothing was added. Importing it again would add the same rows a second time; "
                              "if that is what you want, choose 'Import it again anyway'.",
                     {"duplicate_of": {"job_id": str(previous.id), "imported_on": when}})
    try:
        read = prep.read_upload(shown, content, settings.max_upload_rows)
        assigned, unused = assign_types(read, shown, data_type_hint)
    except ValidationFailedError as exc:
        return _fail(db, job, exc.message)
    except Exception:                                                      # noqa: BLE001 - a parser failure must be a message, never a 500
        log.exception("upload_read_failed")                                # exception type and location only: no file content is ever logged
        return _fail(db, job, "This file could not be read. Check that it is a normal CSV or .xlsx file and try again.")

    job.detected_types_json = sorted(set(assigned.values()))
    mappings = _mapping_for(read, assigned)
    pending, questions = {}, {}
    for name, (tname, m) in mappings.items():
        canonical = CANONICAL_TYPES[tname]
        mapped_cols = {f: c for c, f in m.column_to_field.items()}
        qs = []
        if not m.needs_confirmation:
            for fname, spec in canonical.fields.items():
                if spec.kind == "date" and fname in mapped_cols:
                    q = prep.coerce_dates(read.frames[name][mapped_cols[fname]], None, column=fname).question
                    if q is not None:
                        qs.append({"field": fname, "column": mapped_cols[fname], "examples": q.examples})
        if m.needs_confirmation or qs:
            pending[tname] = {
                "sheet": name, "type": tname, "suggested_mapping": m.column_to_field, "unmapped_required_fields": m.unmapped_required_fields,
                "available_columns": [str(c) for c in read.frames[name].columns], "date_questions": qs,
            }
    reports = {n: r.as_dict() for n, r in read.reports.items()}
    if pending:
        job.storage_key = upload_storage.save_original(business_id, job.id, shown, content)
        job.status = STATUS_PENDING
        job.mapping_json = pending
        job.summary_json = {"preprocessing": reports, "sheets_not_used": unused, "assigned": assigned,
                            "auto_mapping": {n: dict(mappings[n][1].column_to_field) for n in assigned}}
        db.commit()
        db.refresh(job)
        return job
    return _finish(db, job, read, assigned, unused, {n: dict(mappings[n][1].column_to_field) for n in assigned}, {}, content)


def _finish(db: Session, job: DataIngestionJob, read: prep.ReadResult, assigned: dict[str, str], unused: list[dict[str, str]],
            confirmed: dict[str, dict[str, str]], orders: dict[str, dict[str, str]], content: bytes) -> DataIngestionJob:
    """Convert, validate and store every table of the upload in ONE transaction, then report what was done."""
    settings = get_settings()
    quality: dict[str, dict] = {}
    prepared: dict[str, pd.DataFrame] = {}
    datasets: list[dict] = []
    blocking: list[str] = []
    questions_left: dict[str, list] = {}
    for name, tname in assigned.items():
        df = read.frames[name]
        mapping = confirmed[name]
        mapped = df.rename(columns=mapping)[[c for c in mapping.values() if c in df.rename(columns=mapping).columns]]
        clean, skipped, issues, notes, questions = coerce_for_import(mapped, tname, orders.get(name, {}))
        rep = read.reports[name]
        if questions:
            inverse = {f: c for c, f in mapping.items()}
            questions_left[name] = [{"field": q["field"], "column": inverse.get(q["field"], q["field"]), "examples": q["examples"]} for q in questions]
            continue
        vr = validate_mapped_dataframe(clean, CANONICAL_TYPES[tname])
        quality[name] = asdict(vr)
        blocking += [f"{name}: {i}" for i in issues + vr.issues]
        total = len(mapped)
        if total and len(skipped) / total > settings.max_skipped_row_share:
            reasons = {}
            for s in skipped:
                reasons[s["reason"].split(" (")[0]] = reasons.get(s["reason"].split(" (")[0], 0) + 1
            top = ", ".join(f"{r}: {n}" for r, n in sorted(reasons.items(), key=lambda t: -t[1])[:3])
            blocking.append(f"{name}: most rows ({len(skipped):,} of {total:,}) could not be imported ({top}). This usually means a column was matched "
                            "to the wrong field or the dates or numbers are written in a way we cannot read. Nothing was imported.")
        elif len(clean) == 0:
            blocking.append(f"{name}: no row had all the required values, so nothing could be imported.")
        prepared[name] = clean
        used = {c: f for c, f in mapping.items() if c in df.columns}
        examples = [s for s in skipped[:10]]
        reasons_count: dict[str, int] = {}
        for s in skipped:
            key = s["reason"].split(" (")[0]
            reasons_count[key] = reasons_count.get(key, 0) + 1
        datasets.append({
            "type": tname, "source": name, "rows_read": rep.rows_read, "rows_after_cleaning": total, "rows_imported": len(clean), "rows_skipped": len(skipped),
            "skipped_reasons": reasons_count, "skipped_examples": examples,
            "columns_in_file": rep.columns_kept, "columns_used": [{"column": c, "as": f} for c, f in used.items()],
            "columns_not_used": [c for c in rep.columns_kept if c not in used],
            "columns_removed_empty": rep.empty_columns_removed, "renamed_columns": rep.renamed_columns, "duplicate_rows": rep.duplicate_rows,
            "actions": [a.as_dict() for a in rep.actions] + [{"code": "note", "message": n, "count": None} for n in notes],
            "warnings": rep.warnings, "encoding": rep.encoding, "delimiter": rep.delimiter,
        })
    summary_base = {
        "preprocessing": {n: r.as_dict() for n, r in read.reports.items()}, "sheets_not_used": unused,
        "file": {"name": job.filename, "size_bytes": job.file_size, "sha256": job.file_sha256},
    }
    if questions_left:
        job.status = STATUS_PENDING
        summary_base = {**summary_base, "assigned": assigned, "auto_mapping": confirmed}
        job.mapping_json = {assigned[n]: {"sheet": n, "type": assigned[n], "suggested_mapping": confirmed[n], "unmapped_required_fields": [],
                                          "available_columns": [str(c) for c in read.frames[n].columns], "date_questions": q} for n, q in questions_left.items()}
        job.summary_json = summary_base
        db.commit()
        db.refresh(job)
        return job
    if blocking:
        return _fail(db, job, " ".join(blocking), {**summary_base, "quality": quality, "datasets": datasets})
    try:
        counts = {}
        for name, clean in prepared.items():
            counts[assigned[name]] = counts.get(assigned[name], 0) + _INGESTORS[assigned[name]](db, job.business_id, clean)
        key = job.storage_key or upload_storage.save_original(job.business_id, job.id, job.filename, content)
        job.storage_key = key
        job.status = "completed"
        job.error_message = None
        job.mapping_json = {}
        job.summary_json = {**summary_base, "quality": quality, "rows_ingested": counts, "datasets": datasets,
                            "original_kept": bool(key), "completed_at": datetime.now(timezone.utc).isoformat()}
        db.commit()                                                        # every table together, or none of them
        db.refresh(job)
        return job
    except ValidationFailedError as exc:
        return _fail(db, job, exc.message, {**summary_base, "quality": quality, "datasets": datasets})
    except Exception:                                                      # noqa: BLE001
        log.exception("upload_store_failed")                               # type and location only
        return _fail(db, job, "The data could not be saved, so nothing was imported and your existing data is unchanged. Please try again.",
                     {**summary_base, "quality": quality, "datasets": datasets})


def confirm_mapping(db: Session, business_id: str, job_id: str, mappings: dict[str, dict[str, str]],
                    date_orders: dict[str, dict[str, str]] | None = None) -> DataIngestionJob:
    """mappings: {table: {uploaded_column: canonical_field}}; date_orders: {table: {field: 'day_first' | 'month_first'}}. Resumes from the ORIGINAL file."""
    job = db.get(DataIngestionJob, job_id)
    if job is None or job.business_id != business_id:
        raise NotFoundError(f"Ingestion job {job_id} not found.")
    if job.status != STATUS_PENDING:
        raise ValidationFailedError(f"Job {job_id} is not awaiting confirmation (status={job.status}).")
    pending = job.mapping_json or {}
    for tname, p in pending.items():
        confirmed = mappings.get(tname) or p["suggested_mapping"]
        canonical = CANONICAL_TYPES[tname]
        missing = [f for f in canonical.required_fields if f not in confirmed.values()]
        if missing:
            raise ValidationFailedError(f"Mapping for '{tname}' is still missing required fields: {missing}")
        for q in p.get("date_questions", []):
            if (date_orders or {}).get(tname, {}).get(q["field"]) not in ("day_first", "month_first"):
                raise ValidationFailedError(f"Please say whether the dates in '{q['column']}' are day/month/year or month/day/year.")
    # claim the job atomically so a double click cannot import twice
    claimed = db.execute(update(DataIngestionJob).where(DataIngestionJob.id == job_id, DataIngestionJob.status == STATUS_PENDING).values(status="processing"))
    db.commit()
    if claimed.rowcount != 1:
        raise ValidationFailedError("This file is already being imported.")
    job = db.get(DataIngestionJob, job_id)
    try:
        content = upload_storage.load_original(job.storage_key)
    except (OSError, TypeError):
        return _fail(db, job, "The original upload is no longer available. Please upload the file again.")
    settings = get_settings()
    try:
        read = prep.read_upload(job.filename, content, settings.max_upload_rows)
    except ValidationFailedError as exc:
        return _fail(db, job, exc.message)
    summary = job.summary_json or {}
    assigned = dict(summary.get("assigned") or {p["sheet"]: t for t, p in pending.items()})
    unused = summary.get("sheets_not_used", [])
    auto = summary.get("auto_mapping", {})
    conf = {name: (mappings.get(t) or pending.get(t, {}).get("suggested_mapping") or auto.get(name) or {}) for name, t in assigned.items()}
    assigned = {n: t for n, t in assigned.items() if n in read.frames}
    orders = {name: (date_orders or {}).get(t, {}) for name, t in assigned.items()}
    return _finish(db, job, read, assigned, unused, conf, orders, content)


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
