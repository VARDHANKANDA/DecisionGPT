"""The evaluation data view: exactly the POS lines the production system can ingest unchanged.

Why a view at all (all measured in this repository, see README):
  * sales.quantity is an INTEGER column  -> weighed/fractional lines cannot be stored as-is
  * validate_mapped_dataframe() REJECTS an upload that contains duplicate rows, and a POS register
    legitimately repeats identical lines (e.g. milk x1 at the same price many times a day) -> those
    lines cannot be uploaded as-is. They are MERGED (quantities summed), not dropped, so total sales
    and total units are preserved exactly; only the "one row per bill line" grain is lost.
  * the canonical sales schema has no GST column

Both systems under test (DecisionGPT and the LLM baseline) and the ground truth use THIS view, so
nobody is scored on data another system never received. Selection rules are fixed here, before any
model is run, and every stage's counts are recorded in the run metadata.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
PROCESSED_CSV = ROOT / "data" / "external" / "india_pos_register" / "processed" / "india_pos_register_clean.csv"
RAW_ZIP = ROOT / "data" / "external" / "india_pos_register" / "raw" / "retail-sales-register-data.zip"
EXPECTED_RAW_SHA256 = "2ee177e85839ba6a235b6a92cf667bbb51d7b2364e6e79fdaf513e57b810bd59"
EXPECTED_PROCESSED_ROWS = 94_290

VIEW_RULES = (
    "1) keep lines whose quantity is a whole number > 0 (sales.quantity is an integer column); "
    "2) keep lines whose recomputed amount (qty*rate) agrees with a printed amount column; "
    "3) merge lines that share (date, product, unit price) by summing quantity (the production upload validator rejects duplicate rows; "
    "merging preserves total sales and total units exactly; when a merged group mixed GST slabs, the slab with the largest revenue in the group is kept). "
    "Consequence: 'one row' no longer means 'one bill line', so no task asks about individual sale entries."
)


@dataclass(frozen=True)
class ViewInfo:
    raw_zip_sha256: str | None
    processed_rows: int
    after_whole_quantity: int
    after_amount_agreement: int
    after_merge: int
    lines_merged_away: int
    gst_mixed_groups: int
    revenue_processed: float
    revenue_view: float
    date_min: str
    date_max: str
    days_with_sales: int
    distinct_products: int
    view_sha256: str
    rules: str = VIEW_RULES

    def as_dict(self) -> dict:
        return self.__dict__.copy()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_processed() -> pd.DataFrame:
    df = pd.read_csv(PROCESSED_CSV, parse_dates=["date"])
    if len(df) != EXPECTED_PROCESSED_ROWS:
        raise RuntimeError(f"processed POS file has {len(df)} rows, expected {EXPECTED_PROCESSED_ROWS}")
    return df


def build_view(processed: pd.DataFrame | None = None) -> tuple[pd.DataFrame, ViewInfo]:
    """Return (view, info). The view has: date, product, quantity(int), unit_price, revenue, gst_pct."""
    df = load_processed() if processed is None else processed
    s1 = df[(df["qty"] > 0) & ((df["qty"] % 1) == 0)]
    s2 = s1[s1["amount_matches_printed"]]
    s2 = s2.assign(_rev=s2["qty"] * s2["rate_inr"])
    grp = s2.groupby(["date", "product", "rate_inr"], sort=True)
    qty = grp["qty"].sum()
    # slab with the largest revenue inside each merged group
    gst_best = (
        s2.groupby(["date", "product", "rate_inr", "gst_pct"])["_rev"].sum().reset_index()
        .sort_values(["date", "product", "rate_inr", "_rev", "gst_pct"], ascending=[True, True, True, False, True])
        .drop_duplicates(["date", "product", "rate_inr"], keep="first")
        .set_index(["date", "product", "rate_inr"])["gst_pct"]
    )
    gst_mixed = int((grp["gst_pct"].nunique() > 1).sum())
    merged = qty.to_frame("quantity").join(gst_best).reset_index()
    view = pd.DataFrame(
        {
            "date": merged["date"].dt.normalize(),
            "product": merged["product"].astype(str),
            "quantity": merged["quantity"].astype(int),
            "unit_price": merged["rate_inr"].astype(float),
            "gst_pct": merged["gst_pct"].astype(float),
        }
    ).reset_index(drop=True)
    view["revenue"] = (view["quantity"] * view["unit_price"]).round(2)
    if view.duplicated(["date", "product", "quantity", "unit_price"]).any():  # would be rejected by the upload validator
        raise RuntimeError("evaluation view still contains duplicate rows")

    canonical = view.assign(date=view["date"].dt.strftime("%Y-%m-%d")).to_csv(index=False).encode()
    info = ViewInfo(
        raw_zip_sha256=sha256_file(RAW_ZIP) if RAW_ZIP.exists() else None,
        processed_rows=len(df),
        after_whole_quantity=len(s1),
        after_amount_agreement=len(s2),
        after_merge=len(view),
        lines_merged_away=len(s2) - len(view),
        gst_mixed_groups=gst_mixed,
        revenue_processed=round(float(df["line_amount_inr"].sum()), 2),
        revenue_view=round(float(view["revenue"].sum()), 2),
        date_min=str(view["date"].min().date()),
        date_max=str(view["date"].max().date()),
        days_with_sales=int(view["date"].nunique()),
        distinct_products=int(view["product"].nunique()),
        view_sha256=hashlib.sha256(canonical).hexdigest(),
    )
    return view, info


def verify_raw_provenance() -> dict:
    """Raw file must be the audited one (hash) — never silently evaluate a different file."""
    got = sha256_file(RAW_ZIP) if RAW_ZIP.exists() else None
    return {"expected_sha256": EXPECTED_RAW_SHA256, "found_sha256": got, "ok": got == EXPECTED_RAW_SHA256}
