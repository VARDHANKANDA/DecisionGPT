"""One-action, documented preprocessing for research datasets.

Principles
  * The source dataset version is never modified. Output is a NEW versioned artifact linked to the source version id and to the exact
    configuration (steps, parameters, input checksum), so a run is reproducible and auditable.
  * Steps are conditional on what the data contains; a step that does not apply is reported as not applicable, not silently run.
  * Nothing is silently deleted, imputed or clipped. Duplicates, missing values, outliers and invalid values are FLAGGED in new columns
    and counted. Learned transformations (imputation, scaling) are deliberately not performed here: they must be fitted on training
    rows only, inside the modelling pipeline.
  * Every step reports the rows and columns it touched and why.
"""
from __future__ import annotations

import hashlib
import json
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

STEP_ORDER = ["normalize_names", "trim_text", "parse_dates", "coerce_numeric", "sort_by_date", "flag_duplicates", "flag_invalid_values",
              "flag_outliers", "missing_summary", "feature_screen", "chronological_split"]

STEP_INFO = {
    "normalize_names": ("Normalise column names", "Lower-case snake_case names make later steps and models consistent."),
    "trim_text": ("Trim text and blank strings", "Leading/trailing spaces and empty strings are treated as missing so they are counted correctly."),
    "parse_dates": ("Parse date columns", "Dates stored as text cannot be ordered or split chronologically."),
    "coerce_numeric": ("Convert numeric text", "Numbers stored as text are converted; values that cannot be converted become missing and are counted."),
    "sort_by_date": ("Sort by date", "Chronological order is required for lag features and time-based splits."),
    "flag_duplicates": ("Flag duplicate rows", "Identical rows are flagged in a new column, not deleted: in transaction data they may be genuine repeats."),
    "flag_invalid_values": ("Flag impossible values", "Negative quantities, prices or amounts are flagged in a new column, not changed."),
    "flag_outliers": ("Flag extreme values", "Values beyond 3 x IQR are flagged per numeric column; none are clipped or removed."),
    "missing_summary": ("Summarise missing values", "Counts missing values per column. No imputation is performed here (it must be fitted on training data only)."),
    "feature_screen": ("Screen features", "Reports constant columns and identifier-like columns that should not be model features."),
    "chronological_split": ("Assign chronological split", "Labels each row train / validation / test (70/15/15 of unique dates) so no future row can enter training."),
}

_LOCKS: dict[str, threading.Lock] = {}
_REG = threading.Lock()


def _norm(name: str) -> str:
    s = re.sub(r"[^0-9a-zA-Z]+", "_", str(name).strip()).strip("_").lower()
    return s or "column"


def _date_like(df: pd.DataFrame) -> list[str]:
    out = []
    for c in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[c]):
            out.append(c)
            continue
        if df[c].dtype == object or str(df[c].dtype).startswith("str"):
            name_hint = re.search(r"date|time|day|period", str(c), re.I) is not None
            sample = df[c].dropna().astype(str).head(500)
            if len(sample) and name_hint:
                ok = pd.to_datetime(sample, errors="coerce").notna().mean()
                if ok >= 0.9:
                    out.append(c)
    return out


def _numeric_text(df: pd.DataFrame, skip: set[str]) -> list[str]:
    out = []
    for c in df.columns:
        if c in skip or pd.api.types.is_numeric_dtype(df[c]) or pd.api.types.is_datetime64_any_dtype(df[c]):
            continue
        s = df[c].dropna().astype(str).str.strip().str.replace(",", "", regex=False)
        s = s[s != ""]
        if len(s) >= 5 and pd.to_numeric(s, errors="coerce").notna().mean() >= 0.9:
            out.append(c)
    return out


_NONNEG = re.compile(r"qty|quantity|units|price|rate|amount|revenue|sales|spend|cost", re.I)


def plan(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Dry run: which steps apply to this dataset and what each would touch. Does not change anything."""
    steps: list[dict] = []

    def add(sid, applies, affected_rows=None, affected_cols=None, detail=""):
        title, why = STEP_INFO[sid]
        steps.append({"id": sid, "title": title, "rationale": why, "applies": bool(applies), "default_enabled": bool(applies),
                      "affected_rows": affected_rows, "affected_columns": affected_cols or [], "detail": detail,
                      "status": "proposed" if applies else "not_applicable"})

    renamed = [c for c in df.columns if _norm(c) != c]
    add("normalize_names", bool(renamed), None, renamed, f"{len(renamed)} column name(s) would change")
    obj_cols = [c for c in df.columns if df[c].dtype == object or str(df[c].dtype).startswith("str")]
    dirty = 0
    for c in obj_cols:
        s = df[c].dropna().astype(str)
        dirty += int(((s != s.str.strip()) | (s.str.strip() == "")).sum())
    add("trim_text", dirty > 0, dirty, obj_cols, f"{dirty} text cell(s) with extra spaces or empty strings")
    dcols = _date_like(df)
    needs_parse = [c for c in dcols if not pd.api.types.is_datetime64_any_dtype(df[c])]
    add("parse_dates", bool(needs_parse), len(df) if needs_parse else 0, needs_parse, "text columns recognised as dates: " + (", ".join(needs_parse) or "none"))
    ncols = _numeric_text(df, set(dcols))
    add("coerce_numeric", bool(ncols), len(df) if ncols else 0, ncols, "text columns that hold numbers: " + (", ".join(ncols) or "none"))
    add("sort_by_date", len(dcols) >= 1, len(df), dcols[:1], "sort by " + (dcols[0] if dcols else "n/a"))
    nd = int(df.duplicated().sum())
    add("flag_duplicates", True, nd, [], f"{nd} fully identical row(s) would be flagged (kept)")
    num = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    inv_cols = [c for c in num if _NONNEG.search(str(c))]
    ninv = int(sum((pd.to_numeric(df[c], errors="coerce") < 0).sum() for c in inv_cols))
    add("flag_invalid_values", bool(inv_cols), ninv, inv_cols, f"{ninv} negative value(s) in quantity/price/amount-like columns")
    out_cols = [c for c in num if df[c].notna().sum() >= 8 and df[c].nunique() > 5][:10]
    add("flag_outliers", bool(out_cols), None, out_cols, "numeric columns checked: " + (", ".join(out_cols) or "none"))
    mc = {c: int(v) for c, v in df.isna().sum().items() if v}
    add("missing_summary", True, int(sum(mc.values())), list(mc), f"{len(mc)} column(s) have missing values")
    add("feature_screen", True, None, [], "constant and identifier-like columns will be listed")
    ndates = int(pd.to_datetime(df[dcols[0]], errors="coerce").nunique()) if dcols else 0
    add("chronological_split", ndates >= 30, len(df) if ndates >= 30 else 0, dcols[:1], f"{ndates} distinct dates" + ("" if ndates >= 30 else " - fewer than 30, so no split is proposed"))
    return steps


def apply_pipeline(df: pd.DataFrame, enabled: list[str] | None = None) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Run the enabled steps (default: every applicable step). Returns the processed frame and a step-by-step report."""
    proposal = {s["id"]: s for s in plan(df)}
    chosen = [s for s in STEP_ORDER if (s in enabled if enabled is not None else proposal[s]["applies"])]
    out = df.copy()
    report: list[dict] = []
    notes: dict[str, Any] = {}

    def rec(sid, rows, cols, detail, status="applied"):
        report.append({"id": sid, "title": STEP_INFO[sid][0], "status": status, "rows_affected": rows, "columns_affected": cols, "detail": detail,
                       "rationale": STEP_INFO[sid][1]})

    for sid in STEP_ORDER:
        if sid not in chosen:
            rec(sid, 0, [], "Not run" + (": not applicable to this dataset" if not proposal[sid]["applies"] else ": not selected"), "skipped")
            continue
        if sid == "normalize_names":
            mapping, seen = {}, {}
            for c in out.columns:
                n = _norm(c)
                seen[n] = seen.get(n, 0) + 1
                mapping[c] = n if seen[n] == 1 else f"{n}_{seen[n]}"
            changed = {a: b for a, b in mapping.items() if a != b}
            out = out.rename(columns=mapping)
            notes["column_name_mapping"] = changed
            rec(sid, 0, list(changed.values()), f"{len(changed)} column(s) renamed")
        elif sid == "trim_text":
            n = 0
            cols = []
            for c in out.columns:
                if out[c].dtype == object or str(out[c].dtype).startswith("str"):
                    s = out[c]
                    ss = s.astype("string")
                    new = ss.str.strip().replace("", pd.NA)
                    changed = int((ss.notna() & ((ss != ss.str.strip()) | (ss.str.strip() == ""))).sum())
                    if changed:
                        out[c] = new.astype(object).where(new.notna(), np.nan)
                        n += changed
                        cols.append(c)
            rec(sid, n, cols, f"{n} cell(s) trimmed or blank strings set to missing")
        elif sid == "parse_dates":
            cols, bad = [], 0
            for c in _date_like(out):
                if not pd.api.types.is_datetime64_any_dtype(out[c]):
                    parsed = pd.to_datetime(out[c], errors="coerce")
                    bad += int(parsed.isna().sum() - out[c].isna().sum())
                    out[c] = parsed
                    cols.append(c)
            rec(sid, len(out), cols, f"{len(cols)} column(s) parsed; {bad} value(s) could not be parsed and are now missing")
        elif sid == "coerce_numeric":
            cols, bad = [], 0
            for c in _numeric_text(out, set(_date_like(out))):
                raw = out[c].astype("string").str.strip().str.replace(",", "", regex=False)
                conv = pd.to_numeric(raw, errors="coerce")
                bad += int(conv.isna().sum() - raw.isna().sum() - (raw == "").sum())
                out[c] = conv
                cols.append(c)
            rec(sid, len(out), cols, f"{len(cols)} column(s) converted; {max(bad, 0)} value(s) could not be converted and are now missing")
        elif sid == "sort_by_date":
            dc = [c for c in _date_like(out)][:1]
            if dc:
                out = out.sort_values(dc[0], kind="mergesort").reset_index(drop=True)
            rec(sid, len(out), dc, f"sorted by {dc[0]} (stable)" if dc else "no date column")
        elif sid == "flag_duplicates":
            flag = out.duplicated(keep="first")
            out["_flag_duplicate_row"] = flag
            rec(sid, int(flag.sum()), ["_flag_duplicate_row"], f"{int(flag.sum())} repeated row(s) flagged; none removed")
        elif sid == "flag_invalid_values":
            cols = [c for c in out.columns if pd.api.types.is_numeric_dtype(out[c]) and _NONNEG.search(str(c))]
            mask = pd.Series(False, index=out.index)
            for c in cols:
                mask |= pd.to_numeric(out[c], errors="coerce") < 0
            out["_flag_invalid_value"] = mask
            rec(sid, int(mask.sum()), ["_flag_invalid_value"], f"{int(mask.sum())} row(s) with a negative quantity/price/amount flagged; values unchanged")
        elif sid == "flag_outliers":
            cols = [c for c in out.columns if pd.api.types.is_numeric_dtype(out[c]) and not c.startswith("_flag") and out[c].notna().sum() >= 8 and out[c].nunique() > 5][:10]
            tot, added = 0, []
            for c in cols:
                s = pd.to_numeric(out[c], errors="coerce")
                q1, q3 = s.quantile([0.25, 0.75])
                iqr = q3 - q1
                if iqr > 0:
                    f = (s < q1 - 3 * iqr) | (s > q3 + 3 * iqr)
                    if f.any():
                        out[f"_flag_outlier_{c}"] = f
                        tot += int(f.sum())
                        added.append(f"_flag_outlier_{c}")
            rec(sid, tot, added, f"{tot} extreme value(s) flagged across {len(added)} column(s); none clipped or removed")
        elif sid == "missing_summary":
            miss = {c: int(v) for c, v in out.isna().sum().items() if v and not str(c).startswith("_flag")}
            notes["missing_by_column"] = miss
            rec(sid, int(sum(miss.values())), list(miss), "no imputation performed; handle inside the training pipeline")
        elif sid == "feature_screen":
            const = [c for c in out.columns if out[c].nunique(dropna=False) <= 1 and not str(c).startswith("_flag")]
            ident = [c for c in out.columns if not pd.api.types.is_numeric_dtype(out[c]) and not pd.api.types.is_datetime64_any_dtype(out[c])
                     and len(out) > 20 and out[c].nunique() / max(len(out), 1) > 0.9]
            notes["feature_screen"] = {"constant_columns": const, "identifier_like_columns": ident}
            rec(sid, 0, const + ident, f"{len(const)} constant and {len(ident)} identifier-like column(s) should not be used as features")
        elif sid == "chronological_split":
            dc = [c for c in _date_like(out)][:1]
            if dc:
                ud = sorted(pd.to_datetime(out[dc[0]], errors="coerce").dropna().unique())
                n = len(ud)
                if n >= 30:
                    a, b = ud[int(n * 0.70) - 1], ud[int(n * 0.85) - 1]
                    d = pd.to_datetime(out[dc[0]], errors="coerce")
                    out["_split"] = np.where(d <= a, "train", np.where(d <= b, "validation", "test"))
                    out.loc[d.isna(), "_split"] = "unassigned"
                    counts = out["_split"].value_counts().to_dict()
                    notes["split"] = {"train_last_date": str(a)[:10], "validation_last_date": str(b)[:10], "rows": {k: int(v) for k, v in counts.items()}}
                    rec(sid, len(out), ["_split"], f"train <= {str(a)[:10]}, validation <= {str(b)[:10]}, test after; rows {counts}")
                else:
                    rec(sid, 0, [], f"only {n} distinct dates; no split assigned", "skipped")
            else:
                rec(sid, 0, [], "no date column", "skipped")
    return out, {"steps": report, "notes": notes, "rows_in": int(len(df)), "rows_out": int(len(out)), "columns_in": int(len(df.columns)),
                 "columns_out": int(len(out.columns)),
                 "rows_removed": int(len(df) - len(out)), "business_totals_changed": False}


def _lock_for(key: str) -> threading.Lock:
    with _REG:
        return _LOCKS.setdefault(key, threading.Lock())


def frame_checksum(df: pd.DataFrame) -> str:
    return hashlib.sha256(pd.util.hash_pandas_object(df, index=True).values.tobytes() + "|".join(map(str, df.columns)).encode()).hexdigest()


def run_and_store(df: pd.DataFrame, source_version_id: str, root: Path, enabled: list[str] | None = None, created_by: str | None = None) -> dict[str, Any]:
    """Execute and persist: processed.csv + report.json under <root>/processed/<source_version_id>/<run_id>/. One run at a time per source."""
    lock = _lock_for(source_version_id)
    if not lock.acquire(blocking=False):
        return {"status": "busy", "reason": "A preprocessing run for this dataset version is already in progress."}
    created = datetime.now(timezone.utc)
    cfg = {"steps": enabled, "source_version_id": source_version_id, "input_sha256": frame_checksum(df)}
    run_id = f"pp_{created.strftime('%Y%m%dT%H%M%SZ')}_{hashlib.sha256(json.dumps(cfg, sort_keys=True).encode()).hexdigest()[:8]}"
    out_dir = root / "processed" / source_version_id / run_id
    try:
        out_dir.mkdir(parents=True, exist_ok=False)
        try:
            processed, rep = apply_pipeline(df, enabled)
            processed.to_csv(out_dir / "processed.csv", index=False)
            result = {"status": "completed", "run_id": run_id, "source_version_id": source_version_id, "created_utc": created.isoformat(timespec="seconds"),
                      "created_by": created_by, "config": cfg, "output_sha256": frame_checksum(processed), "output_file": "processed.csv",
                      "output_columns": list(map(str, processed.columns)), "raw_dataset_modified": False, **rep}
        except Exception as exc:  # noqa: BLE001 - failures are recorded, never hidden
            result = {"status": "failed", "run_id": run_id, "source_version_id": source_version_id, "created_utc": created.isoformat(timespec="seconds"),
                      "config": cfg, "error": f"{type(exc).__name__}: {exc}"[:400], "raw_dataset_modified": False}
        (out_dir / "report.json").write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
        return result
    finally:
        lock.release()


def list_runs(root: Path, source_version_id: str) -> list[dict]:
    d = root / "processed" / source_version_id
    out = []
    if d.exists():
        for p in sorted(d.glob("*/report.json"), reverse=True):
            try:
                r = json.loads(p.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            out.append({k: r.get(k) for k in ("run_id", "status", "created_utc", "rows_in", "rows_out", "columns_in", "columns_out", "error", "output_sha256")})
    return out


def get_run(root: Path, source_version_id: str, run_id: str) -> dict | None:
    if not re.fullmatch(r"pp_[0-9TZ]+_[0-9a-f]{8}", run_id) or not re.fullmatch(r"[0-9a-fA-F-]{8,64}", source_version_id):
        return None  # path-traversal guard
    p = root / "processed" / source_version_id / run_id / "report.json"
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
