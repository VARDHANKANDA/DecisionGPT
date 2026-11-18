"""Data Platform: inspection & profiling, cleaning, validation, transformation and the preparation pipeline.

Operates on the owner's STORED canonical tables (the same rows every analysis reads) — not on fixed samples. Original uploaded files are
not retained, so "original data" here means the rows as stored before a cleaning/transformation step; every consequential step records
an undo snapshot in ``data_prep_runs`` so it can be reviewed and reverted. This is a row-level audit trail, not full lineage.

Safety rules: nothing is deleted or changed without an explicit ``confirm``; rows are never auto-deleted as "duplicates" (identical rows
can be separate genuine transactions); only fixed, safe operations exist — no user-supplied code, SQL or expressions.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Callable

import numpy as np
import pandas as pd
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.orm import Session

from app.core import clock
from app.core.errors import AppError, NotFoundError, ValidationFailedError
from app.models.platform import DataPrepRun
from app.services import data_management_service as dms

STAGES = ("profile", "clean", "validate", "transform")
DESTRUCTIVE_TABLES = ("sales", "marketing_campaigns", "inventory", "finance")  # rows nothing else points at; safe to exclude
TEXT_STYLE_COLUMNS: dict[str, tuple[str, ...]] = {
    "products": ("category",), "customers": ("segment",), "marketing_campaigns": ("channel", "campaign_name"),
}
NUMERIC_KINDS = ("number", "integer")


class DataPlatformError(AppError):
    code = "DATA_PLATFORM"
    http_status = 422


# ------------------------------------------------------------------------------------------------ loading
def frame(db: Session, business_id: str, table_type: str) -> pd.DataFrame:
    """All rows of one table as a DataFrame (columns in the table spec, plus ``_id``). Dates stay ISO strings; numbers become floats."""
    spec = dms._spec(table_type)  # noqa: SLF001 - same package family
    names = dms._name_maps(db, business_id)  # noqa: SLF001
    rows = dms._base_query(db, spec, business_id).all()  # noqa: SLF001
    data = []
    for r in rows:
        v = dms._row_values(db, spec, r, names)  # noqa: SLF001
        v["_id"] = r.id
        data.append(v)
    df = pd.DataFrame(data, columns=[c.key for c in spec.columns] + ["_id"])
    for c in spec.columns:
        if c.kind in NUMERIC_KINDS:
            df[c.key] = pd.to_numeric(df[c.key], errors="coerce")
    return df


def _cols(table_type: str):
    return dms._spec(table_type).columns  # noqa: SLF001


def _text_cols(table_type: str) -> list[str]:
    return [c.key for c in _cols(table_type) if c.kind == "text"]


def _vis_cols(table_type: str) -> list[str]:
    return [c.key for c in _cols(table_type)]


def _jsonable(v: Any) -> Any:
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return None
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating,)):
        return float(v)
    if isinstance(v, (date, datetime)):
        return v.isoformat()
    if isinstance(v, Decimal):
        return float(v)
    return v


def _records(df: pd.DataFrame, cols: list[str], limit: int = 8) -> list[dict[str, Any]]:
    return [{"id": r["_id"], **{c: _jsonable(r[c]) for c in cols}} for _, r in df.head(limit).iterrows()]


# ------------------------------------------------------------------------------------------------ rules (shared by profiling & validation)
@dataclass(frozen=True)
class Rule:
    id: str
    table: str
    title: str
    severity: str  # fail | warn
    mask: Callable[[pd.DataFrame], pd.Series]
    explanation: str
    next_step: str
    required_cols: tuple[str, ...] = ()


def _num(df: pd.DataFrame, c: str) -> pd.Series:
    return pd.to_numeric(df[c], errors="coerce")


def _date(df: pd.DataFrame, c: str) -> pd.Series:
    return pd.to_datetime(df[c], errors="coerce")


def _future(df: pd.DataFrame, c: str) -> pd.Series:
    return _date(df, c) > pd.Timestamp(clock.today() + timedelta(days=1))


def _dup(df: pd.DataFrame, cols: list[str]) -> pd.Series:
    return df.duplicated(subset=cols, keep="first")


def _rules() -> list[Rule]:
    R = Rule
    return [
        R("sales.date_present", "sales", "Every sale has a date", "fail", lambda d: _date(d, "sale_date").isna(), "A sale without a readable date cannot be placed in any period.", "Correct or add the date in My Data."),
        R("sales.date_not_future", "sales", "No sale is dated in the future", "fail", lambda d: _future(d, "sale_date"), "Future-dated sales distort recent periods.", "Check the date of the listed sales."),
        R("sales.date_plausible", "sales", "Sale dates are after 1 Jan 2000", "warn", lambda d: _date(d, "sale_date") < pd.Timestamp("2000-01-01"), "Very old dates are usually typing or format mistakes.", "Check the date format of the listed sales."),
        R("sales.quantity_positive", "sales", "Quantity is a positive number", "fail", lambda d: _num(d, "quantity").isna() | (_num(d, "quantity") <= 0), "A sale of zero or fewer units, or without a quantity, is not a valid sale.", "Correct the quantity or exclude the row."),
        R("sales.price_valid", "sales", "Price each is present and not negative", "fail", lambda d: _num(d, "unit_price").isna() | (_num(d, "unit_price") < 0), "A missing or negative price makes the total unreliable.", "Correct the price in My Data."),
        R("sales.total_present", "sales", "Total amount is present and not negative", "fail", lambda d: _num(d, "revenue").isna() | (_num(d, "revenue") < 0), "Sales totals feed every revenue figure.", "Correct the total or exclude the row."),
        R("sales.total_consistent", "sales", "Total equals quantity × price − discount (within 1%)", "warn",
          lambda d: ((_num(d, "revenue") - (_num(d, "quantity") * _num(d, "unit_price") - _num(d, "discount").fillna(0))).abs()
                     > np.maximum(1.0, 0.01 * _num(d, "revenue").abs())).fillna(False),
          "The stored total disagrees with quantity × price − discount. It may include tax or rounding, or be a typing error.", "Review the listed rows; use the 'recalculate totals' transformation only if the totals should follow the formula."),
        R("sales.product_linked", "sales", "Every sale is linked to a product", "warn", lambda d: d["product"].isna(), "Sales without a product cannot appear in product rankings.", "Add the product or re-upload with a product column."),
        R("sales.no_exact_duplicates", "sales", "No identical repeated rows", "warn", lambda d: _dup(d, [c for c in d.columns if c != "_id"]),
          "Identical rows may be repeats of one entry or genuine separate sales; DecisionGPT will not guess.", "Review in Data Cleaning and remove only the ones you know are repeats."),
        R("customers.id_present", "customers", "Every customer has an ID", "fail", lambda d: d["external_customer_id"].isna() | (d["external_customer_id"].astype(str).str.strip() == ""), "Customers without an ID cannot be matched to sales.", "Add an ID in My Data."),
        R("customers.id_unique", "customers", "Customer IDs are unique", "fail", lambda d: d["external_customer_id"].notna() & d["external_customer_id"].duplicated(keep="first"), "Two rows with one ID are ambiguous.", "Merge or correct the repeated IDs."),
        R("customers.dates_ordered", "customers", "First purchase is not after last purchase", "warn", lambda d: (_date(d, "first_purchase_date") > _date(d, "last_purchase_date")).fillna(False), "The dates contradict each other.", "Correct the dates."),
        R("customers.non_negative", "customers", "Times bought and total spent are not negative", "fail", lambda d: ((_num(d, "purchase_frequency") < 0) | (_num(d, "monetary_value") < 0)).fillna(False), "Negative counts or spend are invalid.", "Correct the values."),
        R("products.name_present", "products", "Every product has a name", "fail", lambda d: d["name"].isna() | (d["name"].astype(str).str.strip() == ""), "Unnamed products cannot be shown or matched.", "Add a name."),
        R("products.name_unique", "products", "Product names are unique (ignoring case)", "warn", lambda d: d["name"].astype(str).str.strip().str.casefold().duplicated(keep="first") & d["name"].notna(), "Two products with one name make rankings ambiguous.", "Merge or rename."),
        R("products.price_positive", "products", "Selling price is above zero", "warn", lambda d: (_num(d, "selling_price") <= 0).fillna(False), "A zero price is usually missing data.", "Correct the price."),
        R("products.cost_not_above_price", "products", "Cost each is not above selling price", "warn", lambda d: (_num(d, "unit_cost") > _num(d, "selling_price")).fillna(False), "A product sold below cost is possible but worth checking.", "Check the cost and price."),
        R("products.stock_non_negative", "products", "Stock is not negative", "fail", lambda d: (_num(d, "stock_quantity") < 0).fillna(False), "Negative stock is not valid.", "Correct the stock figure."),
        R("inventory.levels_valid", "inventory", "Stock and reorder levels are not negative", "fail", lambda d: ((_num(d, "stock_level") < 0) | (_num(d, "reorder_level") < 0)).fillna(False), "Negative levels are not valid.", "Correct the figures."),
        R("inventory.one_row_per_day", "inventory", "One stock row per product per day", "warn", lambda d: _dup(d, ["date", "product"]), "Two rows for one product and day conflict.", "Keep the correct one."),
        R("marketing.spend_valid", "marketing_campaigns", "Spend is not negative", "fail", lambda d: (_num(d, "spend") < 0).fillna(False), "Negative spend is invalid.", "Correct the spend."),
        R("marketing.results_valid", "marketing_campaigns", "Recorded results are not negative", "fail", lambda d: ((_num(d, "attributed_revenue") < 0) | (_num(d, "clicks") < 0) | (_num(d, "conversions") < 0)).fillna(False), "Negative results are invalid.", "Correct the values."),
        R("marketing.funnel_ordered", "marketing_campaigns", "Clicks ≤ times shown, orders ≤ clicks", "warn", lambda d: ((_num(d, "clicks") > _num(d, "impressions")) | (_num(d, "conversions") > _num(d, "clicks"))).fillna(False), "The funnel numbers contradict each other.", "Check the campaign figures."),
        R("finance.month_present", "finance", "Every row has a month", "fail", lambda d: _date(d, "period_date").isna(), "Money figures need a period.", "Add the month."),
        R("finance.profit_consistent", "finance", "Profit equals income − costs (within 1%)", "warn",
          lambda d: ((_num(d, "net_profit") - (_num(d, "revenue") - _num(d, "cogs").fillna(0) - _num(d, "operating_expenses").fillna(0))).abs()
                     > np.maximum(1.0, 0.01 * _num(d, "revenue").abs())).fillna(False),
          "Profit does not match income − cost of goods − running costs (taxes or other items could explain it).", "Check the figures."),
    ]


# ------------------------------------------------------------------------------------------------ profiling
def profile(db: Session, business_id: str, table_type: str, record: bool = False) -> dict[str, Any]:
    spec = dms._spec(table_type)  # noqa: SLF001
    df = frame(db, business_id, table_type)
    n = len(df)
    cols: list[dict[str, Any]] = []
    outliers: list[dict[str, Any]] = []
    for c in spec.columns:
        s = df[c.key]
        missing = int(s.isna().sum())
        info: dict[str, Any] = {"key": c.key, "label": c.label, "declared_type": c.kind, "missing": missing,
                                "missing_pct": round(100 * missing / n, 2) if n else 0.0, "unique": int(s.nunique(dropna=True))}
        nn = s.dropna()
        if c.kind in NUMERIC_KINDS and len(nn):
            q1, q3 = float(nn.quantile(0.25)), float(nn.quantile(0.75))
            info.update(inferred_type="number", min=float(nn.min()), max=float(nn.max()), mean=round(float(nn.mean()), 4), median=float(nn.median()),
                        std=round(float(nn.std(ddof=1)), 4) if len(nn) > 1 else 0.0)
            if len(nn) >= 20 and q3 > q1:
                lo, hi = q1 - 1.5 * (q3 - q1), q3 + 1.5 * (q3 - q1)
                mask = (s < lo) | (s > hi)
                if mask.any():
                    outliers.append({"column": c.key, "label": c.label, "candidates": int(mask.sum()), "lower_bound": round(lo, 4), "upper_bound": round(hi, 4),
                                     "sample": _records(df[mask].assign(_v=s[mask]).sort_values("_v", ascending=False), [c.key], 5),
                                     "note": "Candidates only (outside 1.5 × the interquartile range). Large values can be genuine; nothing is changed automatically."})
        elif c.kind == "date" and len(nn):
            d = pd.to_datetime(nn, errors="coerce")
            info.update(inferred_type="date", date_min=str(d.min().date()) if d.notna().any() else None, date_max=str(d.max().date()) if d.notna().any() else None,
                        unparseable=int(d.isna().sum()))
        elif len(nn):
            vc = nn.astype(str).value_counts().head(8)
            info.update(inferred_type="text", top_values=[{"value": k, "count": int(v)} for k, v in vc.items()])
        else:
            info["inferred_type"] = {"integer": "number"}.get(c.kind, c.kind)
        if c.kind == "text" and len(nn):
            st = nn.astype(str)
            info["whitespace_issues"] = int((st != st.str.strip().str.replace(r"\s+", " ", regex=True)).sum())
        cols.append(info)

    dup_cols = [c for c in _vis_cols(table_type)]
    duplicates = int(df.duplicated(subset=dup_cols, keep="first").sum()) if n else 0
    invalid = []
    if n:
        for r in _rules():
            if r.table != table_type:
                continue
            try:
                m = r.mask(df).fillna(False)
            except Exception:  # noqa: BLE001 - a rule that cannot run on this data is skipped, not guessed
                continue
            if int(m.sum()):
                invalid.append({"rule": r.id, "title": r.title, "severity": r.severity, "count": int(m.sum()), "explanation": r.explanation,
                                "sample_ids": [str(x) for x in df.loc[m, "_id"].head(5)]})
    result = {
        "table": table_type, "title": spec.title, "rows": n, "columns": len(spec.columns), "column_profiles": cols,
        "duplicate_rows": duplicates, "invalid_or_inconsistent": invalid, "outlier_candidates": outliers,
        "limitations": ["Profiling describes the rows currently stored. Source files are not retained.", "Outliers are candidates for review, not errors."],
        "profiled_at": clock.today().isoformat(),
    }
    if record:
        _record(db, business_id, "profile", table_type, "profile", "completed", {"rows": n, "duplicates": duplicates, "invalid_rules_hit": len(invalid), "outlier_columns": len(outliers)})
    return result


def table_preview(db: Session, business_id: str, table_type: str, offset: int = 0, limit: int = 25, search: str | None = None) -> dict[str, Any]:
    """Searchable, paginated rows. The search is a plain case-insensitive substring match over the visible text/number columns."""
    spec = dms._spec(table_type)  # noqa: SLF001
    if not search:
        out = dms.list_rows(db, business_id, table_type, offset, limit)
        out["search"] = None
        return out
    df = frame(db, business_id, table_type)
    needle = search.strip().casefold()
    if needle:
        mask = df[[c.key for c in spec.columns]].astype(str).apply(lambda col: col.str.casefold().str.contains(needle, regex=False)).any(axis=1)
        df = df[mask]
    limit = max(1, min(limit, 200))
    page = df.iloc[max(0, offset): max(0, offset) + limit]
    return {"type": table_type, "title": spec.title, "columns": [{"key": c.key, "label": c.label, "kind": c.kind, "editable": c.editable} for c in spec.columns],
            "rows": [{"id": r["_id"], "values": {c.key: _jsonable(r[c.key]) for c in spec.columns}} for _, r in page.iterrows()],
            "total": int(len(df)), "offset": offset, "limit": limit, "search": search}


# ------------------------------------------------------------------------------------------------ run records
def _record(db: Session, business_id: str, stage: str, table: str | None, op: str | None, status: str, summary: dict[str, Any],
            undo: dict[str, Any] | None = None, error: str | None = None) -> DataPrepRun:
    run = DataPrepRun(business_id=business_id, stage=stage, table_type=table, operation=op, status=status, summary_json=summary, undo_json=undo, error_message=error)
    db.add(run)
    db.commit()
    return run


def _run_meta(r: DataPrepRun) -> dict[str, Any]:
    return {"id": r.id, "stage": r.stage, "table": r.table_type, "operation": r.operation, "status": r.status, "summary": r.summary_json or {},
            "reversible": bool(r.undo_json) and r.status == "applied", "error": r.error_message, "created_at": r.created_at.isoformat() if r.created_at else None}


def history(db: Session, business_id: str, limit: int = 100, stage: str | None = None) -> list[dict[str, Any]]:
    q = db.query(DataPrepRun).filter(DataPrepRun.business_id == business_id)
    if stage:
        q = q.filter(DataPrepRun.stage == stage)
    return [_run_meta(r) for r in q.order_by(DataPrepRun.created_at.desc()).limit(max(1, min(limit, 500))).all()]


def get_run(db: Session, business_id: str, run_id: str) -> dict[str, Any]:
    r = db.query(DataPrepRun).filter(DataPrepRun.id == run_id, DataPrepRun.business_id == business_id).first()
    if r is None:
        raise NotFoundError("Run not found.")
    return {**_run_meta(r), "detail": (r.summary_json or {})}


# ------------------------------------------------------------------------------------------------ cleaning
def _applied_ids(db: Session, business_id: str, stage: str) -> set[str]:
    return {(r.summary_json or {}).get("proposal_id") for r in
            db.query(DataPrepRun).filter(DataPrepRun.business_id == business_id, DataPrepRun.stage == stage, DataPrepRun.status == "applied").all()}


def _collapse(s: pd.Series) -> pd.Series:
    return s.astype(str).str.strip().str.replace(r"\s+", " ", regex=True)


def cleaning_proposals(db: Session, business_id: str, table_type: str) -> list[dict[str, Any]]:
    spec = dms._spec(table_type)  # noqa: SLF001
    df = frame(db, business_id, table_type)
    n = len(df)
    applied = _applied_ids(db, business_id, "clean")
    out: list[dict[str, Any]] = []
    if n == 0:
        return out
    vis = _vis_cols(table_type)

    for col in _text_cols(table_type):
        s = df[col]
        nn = s.dropna()
        if not len(nn):
            continue
        fixed = _collapse(nn)
        bad = nn.index[(nn.astype(str) != fixed)]
        if len(bad):
            pid = f"trim:{table_type}.{col}"
            out.append({"id": pid, "table": table_type, "kind": "trim_whitespace", "column": col, "issue": f"{len(bad)} value(s) in '{col}' have extra spaces at the ends or between words.",
                        "action": "Remove leading/trailing spaces and collapse repeated spaces.", "affected_rows": int(len(bad)), "affected_cells": int(len(bad)),
                        "preview": [{"id": df.at[i, "_id"], "before": str(s[i]), "after": str(fixed[i])} for i in list(bad)[:8]],
                        "risk": "Low. Only spacing changes; the words are untouched.", "can_apply": table_type != "customers" or col != "external_customer_id", "applied": pid in applied})

    for col in TEXT_STYLE_COLUMNS.get(table_type, ()):
        if col not in df.columns:
            continue
        nn = df[col].dropna()
        if not len(nn):
            continue
        key = _collapse(nn).str.casefold()
        groups: dict[str, list[str]] = {}
        for raw, k in zip(nn.astype(str), key):
            groups.setdefault(k, [])
            if raw not in groups[k]:
                groups[k].append(raw)
        variants = {k: v for k, v in groups.items() if len(v) > 1}
        if variants:
            counts = nn.astype(str).value_counts()
            mapping = {}
            for k, vs in variants.items():
                canon = max(vs, key=lambda v: (counts[v], v))
                for v in vs:
                    if v != canon:
                        mapping[v] = canon
            affected = int(df[col].isin(list(mapping)).sum())
            pid = f"case:{table_type}.{col}"
            out.append({"id": pid, "table": table_type, "kind": "standardise_categories", "column": col,
                        "issue": f"'{col}' has {len(variants)} value(s) written in more than one way (for example {', '.join(next(iter(variants.values())))}).",
                        "action": "Use the most common spelling for each.", "affected_rows": affected, "affected_cells": affected, "mapping": mapping,
                        "preview": [{"before": a, "after": b} for a, b in list(mapping.items())[:8]],
                        "risk": "Low to medium. Values that only differ by capitalisation are treated as the same thing; check the list.", "can_apply": True, "applied": pid in applied})

    dup_mask = df.duplicated(subset=vis, keep="first")
    if dup_mask.any():
        pid = f"dedupe:{table_type}"
        out.append({"id": pid, "table": table_type, "kind": "exact_duplicates", "column": None, "issue": f"{int(dup_mask.sum())} row(s) are identical to an earlier row in every visible column.",
                    "action": "Exclude the later copies and keep the first of each.", "affected_rows": int(dup_mask.sum()), "affected_cells": int(dup_mask.sum()) * len(vis),
                    "preview": _records(df[dup_mask], vis, 6),
                    "risk": "Medium. Identical rows can be separate genuine transactions (for example two identical purchases). Remove them only if you know they are repeats. You can undo this.",
                    "can_apply": table_type in DESTRUCTIVE_TABLES, "applied": pid in applied,
                    **({} if table_type in DESTRUCTIVE_TABLES else {"blocked_reason": "Other records point at these rows, so DecisionGPT will not exclude them automatically. Edit them in My Data."})})

    invalid = {"sales": [("sales.quantity_positive", "quantity is zero, negative or missing"), ("sales.price_valid", "price is missing or negative"),
                         ("sales.total_present", "total is missing or negative"), ("sales.date_present", "date is missing")],
               "marketing_campaigns": [("marketing.spend_valid", "spend is negative")], "inventory": [("inventory.levels_valid", "stock level is negative")],
               "finance": [("finance.month_present", "month is missing")]}.get(table_type, [])
    rules = {r.id: r for r in _rules()}
    for rid, what in invalid:
        m = rules[rid].mask(df).fillna(False)
        if m.any():
            pid = f"invalid:{rid}"
            out.append({"id": pid, "table": table_type, "kind": "invalid_rows", "column": None, "issue": f"{int(m.sum())} row(s) where {what}.",
                        "action": "Exclude these rows from analysis (they are removed from the stored table; you can undo).", "affected_rows": int(m.sum()), "affected_cells": int(m.sum()),
                        "preview": _records(df[m], vis, 6), "rule": rid,
                        "risk": "Medium. These rows cannot be used as they are, but fixing the value in My Data keeps the sale instead of dropping it.",
                        "can_apply": table_type in DESTRUCTIVE_TABLES, "applied": pid in applied})

    miss = {c: int(df[c].isna().sum()) for c in vis if int(df[c].isna().sum())}
    if miss:
        out.append({"id": f"missing:{table_type}", "table": table_type, "kind": "missing_values", "column": None,
                    "issue": "Missing values: " + ", ".join(f"{k} ({v})" for k, v in miss.items()) + ".",
                    "action": "Review and fill in My Data. DecisionGPT does not fill missing values for you.", "affected_rows": int(df[list(miss)].isna().any(axis=1).sum()),
                    "affected_cells": int(sum(miss.values())), "preview": [], "risk": "Guessing a missing value can change your results, so no automatic fill is offered.",
                    "can_apply": False, "applied": False})
    return out


def _model_columns(obj: Any) -> dict[str, Any]:
    return {c.key: _jsonable(getattr(obj, c.key)) for c in sa_inspect(type(obj)).columns}


def apply_cleaning(db: Session, business_id: str, proposal_id: str, confirm: bool) -> dict[str, Any]:
    if confirm is not True:
        raise ValidationFailedError("Please confirm before changing your data.")
    kind_key, _, rest = proposal_id.partition(":")
    if kind_key == "missing":
        raise DataPlatformError("Missing values have to be fixed by hand in My Data; DecisionGPT does not fill them in.")
    if kind_key == "dedupe":
        table_type = rest
    elif kind_key in ("trim", "case"):
        table_type = rest.split(".", 1)[0]
    elif kind_key == "invalid":
        rule = next((r for r in _rules() if r.id == rest), None)
        if rule is None:
            raise NotFoundError("Unknown cleaning proposal.")
        table_type = rule.table
    else:
        raise NotFoundError("Unknown cleaning proposal.")
    if table_type not in dms.TABLES:
        raise NotFoundError("Unknown cleaning proposal.")
    props = {p["id"]: p for p in cleaning_proposals(db, business_id, table_type)}
    p = props.get(proposal_id)
    if p is None:
        raise NotFoundError("That issue is no longer present.")
    if not p["can_apply"]:
        raise DataPlatformError(p.get("blocked_reason") or "This issue has to be fixed by hand in My Data.")
    spec = dms._spec(table_type)  # noqa: SLF001
    model = spec.model
    df = frame(db, business_id, table_type)
    kind = p["kind"]
    undo: dict[str, Any]
    if kind in ("exact_duplicates", "invalid_rows"):
        vis = _vis_cols(table_type)
        mask = df.duplicated(subset=vis, keep="first") if kind == "exact_duplicates" else _rules_mask(df, p["rule"])
        ids = list(df.loc[mask, "_id"])
        objs = db.query(model).filter(model.business_id == business_id, model.id.in_(ids)).all()
        undo = {"type": "reinsert", "model": table_type, "rows": [_model_columns(o) for o in objs]}
        for o in objs:
            db.delete(o)
        affected = len(objs)
    else:
        col = p["column"]
        if kind == "trim_whitespace":
            objs = db.query(model).filter(model.business_id == business_id).all()
            old: dict[str, Any] = {}
            for o in objs:
                v = getattr(o, col)
                if isinstance(v, str):
                    nv = re.sub(r"\s+", " ", v.strip())
                    if nv != v:
                        old[o.id] = v
                        setattr(o, col, nv)
            undo = {"type": "restore_values", "model": table_type, "column": col, "old": old}
            affected = len(old)
        else:  # standardise_categories
            mapping = p["mapping"]
            objs = db.query(model).filter(model.business_id == business_id).all()
            old = {}
            for o in objs:
                v = getattr(o, col)
                if v in mapping:
                    old[o.id] = v
                    setattr(o, col, mapping[v])
            undo = {"type": "restore_values", "model": table_type, "column": col, "old": old}
            affected = len(old)
    db.commit()
    run = _record(db, business_id, "clean", table_type, kind, "applied", {"proposal_id": proposal_id, "issue": p["issue"], "action": p["action"], "affected_rows": affected, "preview": p["preview"][:5]}, undo)
    return {**_run_meta(run), "affected_rows": affected}


def _rules_mask(df: pd.DataFrame, rule_id: str) -> pd.Series:
    return next(r for r in _rules() if r.id == rule_id).mask(df).fillna(False)


def revert_run(db: Session, business_id: str, run_id: str) -> dict[str, Any]:
    r = db.query(DataPrepRun).filter(DataPrepRun.id == run_id, DataPrepRun.business_id == business_id).first()
    if r is None:
        raise NotFoundError("Run not found.")
    if r.status != "applied" or not r.undo_json:
        raise DataPlatformError("Only an applied change that recorded an undo snapshot can be reverted.")
    u = r.undo_json
    spec = dms._spec(u["model"])  # noqa: SLF001
    model = spec.model
    restored = 0
    if u["type"] == "reinsert":
        import sqlalchemy as sa

        cols = {c.key: c for c in sa_inspect(model).columns}
        for row in u["rows"]:
            vals = {}
            for k, v in row.items():
                if isinstance(v, str) and k in cols and isinstance(cols[k].type, sa.Date):
                    v = date.fromisoformat(v[:10])
                elif isinstance(v, str) and k in cols and isinstance(cols[k].type, sa.DateTime):
                    v = datetime.fromisoformat(v)
                vals[k] = v
            if vals.get("business_id") != business_id or db.get(model, vals["id"]) is not None:
                continue
            db.add(model(**vals))
            restored += 1
    else:
        for rid, old in u["old"].items():
            o = db.query(model).filter(model.id == rid, model.business_id == business_id).first()
            if o is not None:
                setattr(o, u["column"], old)
                restored += 1
    r.status = "reverted"
    r.summary_json = {**(r.summary_json or {}), "reverted_rows": restored, "reverted_at": datetime.now(timezone.utc).isoformat()}
    db.commit()
    return {**_run_meta(r), "restored_rows": restored}


# ------------------------------------------------------------------------------------------------ validation
def run_validation(db: Session, business_id: str, tables: list[str] | None = None, record: bool = True) -> dict[str, Any]:
    tables = tables or list(dms.TABLES)
    results: list[dict[str, Any]] = []
    skipped: list[str] = []
    for t in tables:
        dms._spec(t)  # noqa: SLF001  validates the table name
        df = frame(db, business_id, t)
        if len(df) == 0:
            skipped.append(t)
            continue
        for r in _rules():
            if r.table != t:
                continue
            try:
                m = r.mask(df).fillna(False)
            except Exception as exc:  # noqa: BLE001
                results.append({"id": r.id, "table": t, "title": r.title, "severity": r.severity, "status": "error", "affected": 0, "explanation": f"The check could not run: {exc}", "next_step": "", "sample": []})
                continue
            n = int(m.sum())
            status = "pass" if n == 0 else ("fail" if r.severity == "fail" else "warn")
            results.append({"id": r.id, "table": t, "title": r.title, "severity": r.severity, "status": status, "affected": n,
                            "explanation": r.explanation if n else "All rows passed this check.", "next_step": r.next_step if n else "",
                            "sample": _records(df[m], _vis_cols(t), 5) if n else []})
    counts = {k: sum(1 for x in results if x["status"] == k) for k in ("pass", "warn", "fail", "error")}
    overall = ("not_run" if not results else "fail" if counts["fail"] or counts["error"] else "warn" if counts["warn"] else "pass")
    out = {"overall": overall, **counts, "tables_checked": [t for t in tables if t not in skipped], "tables_skipped_empty": skipped, "results": results,
           "rule": "Pass only when every check on every non-empty table passed. Empty tables are skipped, not passed.", "validated_at": clock.today().isoformat()}
    if record:
        run = _record(db, business_id, "validate", None, "validate", "completed", {"pass": counts["pass"], "warn": counts["warn"], "fail": counts["fail"], "error": counts["error"],
                                                                                     "overall": overall, "tables": out["tables_checked"], "results": [{k: v for k, v in x.items() if k != "sample"} for x in results]})
        out["run_id"] = run.id
    return out


# ------------------------------------------------------------------------------------------------ transformation
TRANSFORM_STYLES = ("title", "upper", "lower")


def _style(s: str, style: str) -> str:
    return {"title": s.title(), "upper": s.upper(), "lower": s.lower()}[style]


def transform_options(db: Session, business_id: str) -> list[dict[str, Any]]:
    opts: list[dict[str, Any]] = []
    for t, cols in TEXT_STYLE_COLUMNS.items():
        for c in cols:
            opts.append({"id": f"style:{t}.{c}", "kind": "standardise_style", "table": t, "column": c, "title": f"Standardise capitalisation of {c}", "styles": list(TRANSFORM_STYLES),
                         "needs": "style"})
            opts.append({"id": f"map:{t}.{c}", "kind": "map_values", "table": t, "column": c, "title": f"Rename values in {c}", "needs": "mapping"})
    opts.append({"id": "recalc:sales.revenue", "kind": "recalculate_totals", "table": "sales", "column": "revenue", "title": "Recalculate sale totals (quantity × price − discount)", "needs": None})
    opts.append({"id": "aggregate:sales", "kind": "aggregate_preview", "table": "sales", "column": None, "title": "Preview sales totals by day, week or month (read-only)", "needs": "by"})
    return opts


def _transform_plan(db: Session, business_id: str, op: dict[str, Any]) -> dict[str, Any]:
    kind, table, col = op.get("kind"), op.get("table"), op.get("column")
    valid = {o["id"]: o for o in transform_options(db, business_id)}
    opt = valid.get(op.get("id", ""))
    if opt is None or opt["kind"] != kind:
        raise DataPlatformError("Unsupported transformation. Only the listed operations are available.")
    df = frame(db, business_id, table)
    if kind in ("standardise_style", "map_values"):
        s = df[col].dropna().astype(str)
        if kind == "standardise_style":
            style = op.get("style")
            if style not in TRANSFORM_STYLES:
                raise DataPlatformError(f"style must be one of {list(TRANSFORM_STYLES)}.")
            new = s.map(lambda v: _style(_collapse(pd.Series([v])).iloc[0], style))
        else:
            mapping = op.get("mapping")
            if not isinstance(mapping, dict) or not mapping or len(mapping) > 200:
                raise DataPlatformError("Give a non-empty mapping of existing values to new values (up to 200).")
            existing = set(s.unique())
            bad = [k for k in mapping if k not in existing]
            if bad:
                raise DataPlatformError(f"These values do not exist in the column: {', '.join(map(str, bad[:5]))}.")
            if any(not isinstance(v, str) or not v.strip() or len(v) > 200 for v in mapping.values()):
                raise DataPlatformError("New values must be non-empty text (up to 200 characters).")
            new = s.map(lambda v: mapping.get(v, v))
        changed = s[new != s].index
        return {"df": df, "col": col, "new": new, "changed": list(changed), "preview": [{"id": df.at[i, "_id"], "before": s[i], "after": new[i]} for i in list(changed)[:8]]}
    if kind == "recalculate_totals":
        calc = (_num(df, "quantity") * _num(df, "unit_price") - _num(df, "discount").fillna(0)).round(2)
        cur = _num(df, "revenue")
        changed = df.index[((calc - cur).abs() > 0.005) & calc.notna()]
        return {"df": df, "col": "revenue", "new": calc, "changed": list(changed),
                "preview": [{"id": df.at[i, "_id"], "before": _jsonable(cur[i]), "after": _jsonable(calc[i])} for i in list(changed)[:8]]}
    raise DataPlatformError("Unsupported transformation.")


def aggregate_preview(db: Session, business_id: str, by: str = "month") -> dict[str, Any]:
    if by not in ("day", "week", "month"):
        raise DataPlatformError("by must be day, week or month.")
    df = frame(db, business_id, "sales")
    if df.empty:
        return {"by": by, "rows": [], "note": "No sales."}
    d = pd.to_datetime(df["sale_date"], errors="coerce")
    key = d.dt.to_period({"day": "D", "week": "W", "month": "M"}[by]).astype(str)
    g = df.assign(_k=key).dropna(subset=["_k"]).groupby("_k").agg(sales=("revenue", "sum"), units=("quantity", "sum"), rows=("_id", "count")).reset_index()
    return {"by": by, "rows": [{"period": r["_k"], "sales": round(float(r["sales"]), 2), "units": float(r["units"]), "records": int(r["rows"])} for _, r in g.iterrows()][:400],
            "note": "Read-only preview of what analyses read. Nothing is stored or changed.", "limit_note": "Shows up to 400 periods."}


def transform_preview(db: Session, business_id: str, op: dict[str, Any]) -> dict[str, Any]:
    if op.get("kind") == "aggregate_preview":
        return aggregate_preview(db, business_id, op.get("by", "month"))
    plan = _transform_plan(db, business_id, op)
    return {"id": op["id"], "affected_rows": len(plan["changed"]), "preview": plan["preview"], "risk": "Values change in the stored table. A validation runs afterwards and the change is undone automatically if it introduces new failed checks; you can also undo it later.",
            "can_apply": len(plan["changed"]) > 0}


def apply_transform(db: Session, business_id: str, op: dict[str, Any], confirm: bool) -> dict[str, Any]:
    if confirm is not True:
        raise ValidationFailedError("Please confirm before changing your data.")
    if op.get("kind") == "aggregate_preview":
        raise DataPlatformError("The aggregation is a read-only preview; there is nothing to apply.")
    plan = _transform_plan(db, business_id, op)
    if not plan["changed"]:
        raise DataPlatformError("Nothing would change.")
    table, col = op["table"], plan["col"]
    model = dms._spec(table).model  # noqa: SLF001
    before = run_validation(db, business_id, [table], record=False)
    old: dict[str, Any] = {}
    for i in plan["changed"]:
        rid = plan["df"].at[i, "_id"]
        obj = db.get(model, rid)
        if obj is None or obj.business_id != business_id:
            continue
        old[rid] = _jsonable(getattr(obj, col))
        new = plan["new"][i]
        setattr(obj, col, float(new) if op["kind"] == "recalculate_totals" else str(new))
    db.commit()
    after = run_validation(db, business_id, [table], record=False)
    undo = {"type": "restore_values", "model": table, "column": col, "old": old}
    if after["fail"] > before["fail"]:
        # the transformation introduced new failed checks: put the data back and keep the record of the attempt
        for rid, v in old.items():
            obj = db.get(model, rid)
            setattr(obj, col, v)
        db.commit()
        run = _record(db, business_id, "transform", table, op["kind"], "failed", {"id": op["id"], "affected_rows": len(old), "validation_before": before["fail"], "validation_after": after["fail"]},
                      None, "Validation after the change found new failed checks, so it was undone.")
        raise DataPlatformError(f"The change was undone: it would have introduced {after['fail'] - before['fail']} new failed check(s). (run {run.id})")
    run = _record(db, business_id, "transform", table, op["kind"], "applied", {"id": op["id"], "proposal_id": op["id"], "affected_rows": len(old), "preview": plan["preview"][:5],
                                                                                "validation_before": before["fail"], "validation_after": after["fail"]}, undo)
    return {**_run_meta(run), "affected_rows": len(old)}


# ------------------------------------------------------------------------------------------------ pipeline
def _data_changed_at(db: Session, business_id: str) -> datetime | None:
    stamps = [dms._last_updated(db, spec, business_id) for spec in dms.TABLES.values()]  # noqa: SLF001
    stamps = [s for s in stamps if s is not None]
    return max(stamps) if stamps else None


def _naive(dt: datetime | None) -> datetime | None:
    return dt.replace(tzinfo=None) if dt is not None and dt.tzinfo else dt


def pipeline(db: Session, business_id: str) -> dict[str, Any]:
    """Stage states derived from the stored data and the recorded runs: not_started | in_progress | needs_attention | ready | failed."""
    lib = dms.library(db, business_id)
    total_rows = sum(x["rows"] for x in lib)
    tables_with_data = [x["type"] for x in lib if x["rows"] > 0]
    uploads = dms.upload_history(db, business_id)
    last_upload = next((u for u in uploads if u.status == "completed"), None)
    failed_upload = uploads[0] if uploads and uploads[0].status == "failed" else None
    runs = db.query(DataPrepRun).filter(DataPrepRun.business_id == business_id).order_by(DataPrepRun.created_at.desc()).all()
    last = lambda stage: next((r for r in runs if r.stage == stage and r.status in ("completed", "applied")), None)  # noqa: E731
    changed = _naive(_data_changed_at(db, business_id))

    stages: list[dict[str, Any]] = []

    def add(key, name, state, detail, **extra):
        stages.append({"key": key, "name": name, "state": state, "detail": detail, **extra})

    # 1 source
    if total_rows == 0:
        add("source", "Source data", "failed" if failed_upload else "not_started", failed_upload.error_message if failed_upload else "No data has been added yet.", link="/data")
    else:
        add("source", "Source data", "ready", f"{total_rows:,} rows across {len(tables_with_data)} kind(s) of data" + (f"; last upload {last_upload.filename}" if last_upload else "."), link="/data")

    # 2 profiling
    prof = last("profile")
    add("profiling", "Inspection & profiling", "not_started" if total_rows == 0 else ("ready" if prof else "in_progress"),
        "Nothing to inspect yet." if total_rows == 0 else (f"Last profiled {prof.created_at.isoformat()[:10]}." if prof else "Open Profiling to inspect your data (nothing is required to continue)."), link="/data/profile")

    # 3 cleaning
    pending = 0
    for t in tables_with_data:
        pending += sum(1 for p in cleaning_proposals(db, business_id, t) if not p["applied"] and p["kind"] != "missing_values")
    if total_rows == 0:
        add("cleaning", "Cleaning", "not_started", "Nothing to clean yet.", link="/data/clean")
    else:
        add("cleaning", "Cleaning", "needs_attention" if pending else "ready", f"{pending} issue(s) found that you can review." if pending else "No cleaning issues found in the current rows.", pending=pending, link="/data/clean")

    # 4 validation
    val = last("validate")
    if total_rows == 0:
        add("validation", "Validation", "not_started", "Nothing to validate yet.", link="/data/validate")
    elif val is None:
        add("validation", "Validation", "not_started", "Checks have not been run on your data.", link="/data/validate")
    else:
        s = val.summary_json or {}
        stale = changed is not None and changed > _naive(val.created_at)
        if s.get("fail") or s.get("error"):
            add("validation", "Validation", "needs_attention", f"{s.get('fail', 0)} failed and {s.get('warn', 0)} warning check(s) at the last run.", link="/data/validate", validated_at=val.created_at.isoformat())
        elif stale:
            add("validation", "Validation", "needs_attention", "Your data changed after the last validation run; run the checks again.", link="/data/validate", validated_at=val.created_at.isoformat())
        elif s.get("warn"):
            add("validation", "Validation", "needs_attention", f"{s['warn']} warning check(s) at the last run (no failures).", link="/data/validate", validated_at=val.created_at.isoformat())
        else:
            add("validation", "Validation", "ready", "All checks passed at the last run.", link="/data/validate", validated_at=val.created_at.isoformat())

    # 5 transformation (optional)
    tr = last("transform")
    add("transformation", "Transformation", "not_started" if total_rows == 0 else ("ready" if tr else "in_progress"),
        "Optional: standardise values or recalculate totals." if not tr else f"Last transformation {tr.created_at.isoformat()[:10]}.", link="/data/transform", optional=True)

    # 6 prepared dataset
    v = next(s for s in stages if s["key"] == "validation")
    if total_rows == 0:
        add("prepared", "Prepared dataset", "not_started", "No data yet.", link="/data")
        prepared_ready = False
    elif v["state"] == "ready":
        add("prepared", "Prepared dataset", "ready", "Validated and ready for analysis.", prepared_at=v.get("validated_at"), link="/data/validate")
        prepared_ready = True
    elif v["state"] == "needs_attention" and "failed" in v["detail"] and "0 failed" not in v["detail"]:
        add("prepared", "Prepared dataset", "needs_attention", "Failed checks mean some analyses may use rows that did not pass.", link="/data/validate")
        prepared_ready = False
    else:
        add("prepared", "Prepared dataset", "in_progress", "Run validation (and resolve anything it finds) to mark your data prepared.", link="/data/validate")
        prepared_ready = False

    # 7 downstream
    from app.services import capability_service

    caps = capability_service.get_capabilities(db, business_id)["capabilities"]
    add("analytics", "Business Analytics & AI", "ready" if prepared_ready else ("not_started" if total_rows == 0 else "in_progress"),
        "Analyses read your stored rows. They work on un-validated data too, but results can be affected by unresolved issues." if total_rows else "Add data first.", capabilities=caps, link="/analytics")

    from app.models.platform import HealthSnapshot, SavedReport

    latest_report = db.query(SavedReport.created_at).filter(SavedReport.business_id == business_id).order_by(SavedReport.created_at.desc()).first()
    latest_health = db.query(HealthSnapshot.created_at).filter(HealthSnapshot.business_id == business_id).order_by(HealthSnapshot.created_at.desc()).first()
    stale_outputs = []
    if changed is not None:
        if latest_report and _naive(latest_report[0]) < changed:
            stale_outputs.append("saved reports")
        if latest_health and _naive(latest_health[0]) < changed:
            stale_outputs.append("business health snapshots")
    cur = next((s for s in stages if s["state"] in ("failed", "needs_attention", "in_progress", "not_started")), None)
    return {"stages": stages, "current_stage": cur["key"] if cur else "analytics", "ready_for_analysis": prepared_ready,
            "last_data_change": changed.isoformat() if changed else None, "last_prepared": (v.get("validated_at") if prepared_ready else None),
            "downstream_may_need_refresh": stale_outputs,
            "limitations": ["Source files are not retained: 'original data' means the stored rows before a step, which each applied step snapshots so it can be undone.",
                            "This is a row-level record of preparation, not complete data lineage."]}
