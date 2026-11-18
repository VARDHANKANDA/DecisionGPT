"""Research validation: real checks over the registered datasets, the stored model-comparison runs and the frozen evidence.

Every check is traceable (id, rule, observed value, explanation, remedy). Status is one of passed | failed | warning | not_applicable.
An overall state distinguishes ``no_checks_run`` from ``passed`` and ``failed``: an empty result is never rendered as a perfect score.
Frame-level checks are pure functions of a DataFrame, so they are unit-testable on small examples.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from app.services import model_comparison_service as mc

ROOT = Path(__file__).resolve().parents[3]
SPEC_PATH = ROOT / "research" / "llm_evaluation" / "tasks" / "tasks_v1.json"
MANIFEST_PATH = ROOT / "experiments" / "experiment_manifest.json"
RUNS_DIR = ROOT / "research" / "llm_evaluation" / "runs"
ECOM_CSV = ROOT / "data" / "external" / "india_ecommerce" / "processed" / "india_ecommerce_forecasting.csv"

FRAME_SPECS: dict[str, dict] = {
    "india_pos_register": {
        "label": "Indian POS register (processed)", "path": mc.POS_CSV,
        "required": ["date", "product", "qty", "rate_inr", "line_amount_inr"], "date": "date", "key": None, "target": "line_amount_inr",
        "nonneg": ["qty", "rate_inr", "line_amount_inr"], "positive": [], "numeric": ["qty", "rate_inr", "line_amount_inr"],
        "consistency": ("qty", "rate_inr", "line_amount_inr"), "min_dates": 30,
    },
    "platform_forecasting": {
        "label": "Synthetic platform forecasting series", "path": mc.PLATFORM_CSV,
        "required": ["series_id", "date", "units_sold", "price", "marketing_spend", "promotion_flag"], "date": "date",
        "key": ["series_id", "date"], "target": "units_sold", "nonneg": ["units_sold", "price", "marketing_spend"], "positive": ["price"],
        "numeric": ["units_sold", "price", "marketing_spend", "promotion_flag"], "consistency": None, "min_dates": 30,
    },
    "india_ecommerce_forecasting": {
        "label": "Indian e-commerce orders (daily units)", "path": ECOM_CSV,
        "required": ["series_id", "date", "units_sold", "price"], "date": "date", "key": ["series_id", "date"], "target": "units_sold",
        "nonneg": ["units_sold", "price"], "positive": [], "numeric": ["units_sold", "price"], "consistency": None, "min_dates": 30,
    },
}


def _check(cid: str, group: str, subject: str, rule: str, status: str, observed: Any, explanation: str, remedy: str | None = None) -> dict:
    return {"id": cid, "group": group, "subject": subject, "rule": rule, "status": status, "observed": observed,
            "explanation": explanation, "remedy": remedy if status in ("failed", "warning") else None}


def validate_frame(df: pd.DataFrame | None, spec: dict, subject: str) -> list[dict]:
    """Checks for one tabular dataset. ``df`` may be None (file unreadable) or empty; both are failures, not silent passes."""
    g = "data"
    out: list[dict] = []
    if df is None:
        return [_check("available", g, subject, "The data file can be read", "failed", None, "The dataset file could not be read.",
                       "Check that the file exists and is a valid CSV; re-register the dataset if needed.")]
    out.append(_check("available", g, subject, "The data file can be read", "passed", f"{len(df)} rows, {len(df.columns)} columns", "File read."))
    if len(df) == 0:
        out.append(_check("non_empty", g, subject, "The dataset has at least one row", "failed", 0, "The dataset has no rows, so no other check is meaningful.",
                          "Provide a non-empty dataset."))
        return out
    out.append(_check("non_empty", g, subject, "The dataset has at least one row", "passed", len(df), "Rows present."))

    missing = [c for c in spec["required"] if c not in df.columns]
    if missing:
        out.append(_check("required_columns", g, subject, "All required columns are present", "failed", {"missing": missing},
                          f"Required column(s) missing: {', '.join(missing)}.", "Add or map the missing columns before analysis."))
        return out  # later checks depend on these columns
    out.append(_check("required_columns", g, subject, "All required columns are present", "passed", spec["required"], "All required columns present."))

    # dtypes
    bad_num = [c for c in spec["numeric"] if c in df.columns and pd.to_numeric(df[c], errors="coerce").isna().sum() > df[c].isna().sum()]
    out.append(_check("numeric_types", g, subject, "Numeric columns hold numbers", "failed" if bad_num else "passed", {"non_numeric_values_in": bad_num},
                      "Some numeric columns contain text that cannot be read as numbers." if bad_num else "Numeric columns parse as numbers.",
                      "Clean or convert the offending values; do not coerce them silently."))
    # dates
    dcol = spec["date"]
    dates = pd.to_datetime(df[dcol], errors="coerce")
    n_bad_dates = int(dates.isna().sum() - df[dcol].isna().sum())
    out.append(_check("date_parse", g, subject, "Every date value can be parsed", "failed" if n_bad_dates else "passed", {"unparseable": n_bad_dates},
                      f"{n_bad_dates} date value(s) could not be parsed." if n_bad_dates else "All present dates parse.",
                      "Fix or remove the unparseable dates and document the change."))
    valid = dates.dropna()
    if len(valid):
        out.append(_check("date_range", g, subject, "A coherent date range exists", "passed",
                          {"first": str(valid.min().date()), "last": str(valid.max().date()), "distinct_dates": int(valid.nunique())},
                          "Date range recorded."))
        full = pd.date_range(valid.min(), valid.max(), freq="D")
        gaps = sorted(set(full) - set(valid.unique()))
        out.append(_check("date_continuity", g, subject, "No calendar dates are missing inside the range", "warning" if gaps else "passed",
                          {"missing_dates": [str(d.date()) for d in gaps[:10]], "n_missing": len(gaps)},
                          f"{len(gaps)} calendar date(s) have no records inside the range." if gaps else "Every calendar date has records.",
                          "Confirm whether the gap is a closed day or lost data; do not impute the target silently."))
        n_dates = int(valid.nunique())
        out.append(_check("sample_size", g, subject, f"At least {spec['min_dates']} distinct dates for time-based modelling",
                          "passed" if n_dates >= spec["min_dates"] else "failed", {"distinct_dates": n_dates},
                          "Enough dates for a chronological split." if n_dates >= spec["min_dates"] else "Too few dates for a defensible train/test split.",
                          "Collect a longer history before benchmarking."))
    else:
        out.append(_check("date_range", g, subject, "A coherent date range exists", "failed", None, "No valid dates at all.", "Provide a parseable date column."))

    # duplicates
    if spec.get("key"):
        dup = int(df.duplicated(spec["key"]).sum())
        out.append(_check("duplicate_keys", g, subject, f"No duplicate {'+'.join(spec['key'])} keys", "failed" if dup else "passed", {"duplicates": dup},
                          f"{dup} duplicated key(s): one entity-day appears more than once." if dup else "Keys are unique.",
                          "Aggregate or de-duplicate with a documented rule."))
    else:
        out.append(_check("duplicate_keys", g, subject, "Unique key", "not_applicable", None, "Line-level data has no natural unique key."))
    exact = int(df.duplicated().sum())
    out.append(_check("exact_duplicate_rows", g, subject, "No fully identical rows", "warning" if exact else "passed", {"identical_rows": exact},
                      f"{exact} fully identical row(s); in transaction data these can be genuine repeated sales." if exact else "No identical rows.",
                      "Decide per dataset whether they are repeats or entry errors; keep and flag rather than delete."))
    # missing values
    miss = df[spec["required"]].isna().sum()
    miss = {k: int(v) for k, v in miss.items() if v}
    tgt = spec.get("target")
    tgt_share = (int(df[tgt].isna().sum()) / len(df)) if tgt in df.columns else None
    status = "passed" if not miss else ("failed" if tgt_share is not None and tgt_share >= 0.05 else "warning")
    out.append(_check("missing_values", g, subject, "Required columns have no missing values", status, miss or {},
                      "Missing values in: " + ", ".join(f"{k} ({v})" for k, v in miss.items()) if miss else "No missing values in required columns.",
                      "Investigate the source; impute only with a documented, training-only rule."))
    # impossible values
    neg = {c: int((pd.to_numeric(df[c], errors="coerce") < 0).sum()) for c in spec["nonneg"] if c in df.columns}
    neg = {k: v for k, v in neg.items() if v}
    out.append(_check("non_negative_values", g, subject, "Quantities, prices and amounts are not negative", "failed" if neg else "passed", neg,
                      "Negative values: " + ", ".join(f"{k} ({v})" for k, v in neg.items()) if neg else "No negative values.",
                      "Check for returns or sign errors; model them separately or correct them."))
    zero = {c: int((pd.to_numeric(df[c], errors="coerce") == 0).sum()) for c in spec["positive"] if c in df.columns}
    zero = {k: v for k, v in zero.items() if v}
    out.append(_check("strictly_positive_values", g, subject, "Prices are strictly positive",
                      "warning" if zero else ("passed" if spec["positive"] else "not_applicable"), zero or None,
                      "Zero values where a positive value is expected: " + str(zero) if zero else ("Prices are positive." if spec["positive"] else "No such column."),
                      "Check whether zero means 'missing'."))
    # outliers (flag, never remove)
    if tgt and tgt in df.columns:
        s = pd.to_numeric(df[tgt], errors="coerce").dropna()
        if len(s) >= 8:
            q1, q3 = s.quantile([0.25, 0.75])
            iqr = q3 - q1
            n_out = int(((s < q1 - 3 * iqr) | (s > q3 + 3 * iqr)).sum()) if iqr > 0 else 0
            share = n_out / len(s)
            out.append(_check("target_outliers", g, subject, "Few extreme target values (beyond 3 IQR)", "warning" if share > 0.01 else "passed",
                              {"flagged": n_out, "share": round(share, 4)}, f"{n_out} extreme value(s) flagged; none were removed or clipped.",
                              "Review them with the business before any treatment."))
        zshare = float((pd.to_numeric(df[tgt], errors="coerce") == 0).mean())
        out.append(_check("target_zero_share", g, subject, "Zero values in the target are rare (percentage errors stay defined)",
                          "warning" if zshare > 0.05 else "passed", {"share_zero": round(zshare, 4)},
                          "Many zero targets make MAPE misleading." if zshare > 0.05 else "Few or no zero targets.",
                          "Prefer MAE/RMSE for this target."))
    # internal consistency
    if spec.get("consistency"):
        a, b, c = spec["consistency"]
        if all(x in df.columns for x in (a, b, c)):
            prod = pd.to_numeric(df[a], errors="coerce") * pd.to_numeric(df[b], errors="coerce")
            amt = pd.to_numeric(df[c], errors="coerce")
            mism = float((~np.isclose(prod, amt, atol=0.05, rtol=0.01)).mean())
            out.append(_check("amount_consistency", g, subject, f"{a} x {b} agrees with {c}", "warning" if mism > 0.001 else "passed",
                              {"share_mismatch": round(mism, 4)}, f"{mism:.1%} of rows disagree." if mism > 0.001 else "Amounts agree with quantity x rate.",
                              "Exclude or repair mismatching lines with a documented rule (the benchmark pipeline excludes them and reports the count)."))
    else:
        out.append(_check("amount_consistency", g, subject, "Quantity x rate agrees with the amount", "not_applicable", None, "No such columns in this dataset."))
    return out


def _read(path: Path) -> pd.DataFrame | None:
    try:
        return pd.read_csv(path)
    except (OSError, ValueError, pd.errors.EmptyDataError):
        return None


def validate_model_run(run: dict) -> list[dict]:
    g, s = "model", run.get("run_id", "model run")
    out: list[dict] = []
    ck = run.get("checks") or {}
    sp = run.get("split") or {}
    out.append(_check("temporal_split_order", g, s, "Training dates precede validation dates, which precede test dates",
                      "passed" if ck.get("train_before_val_before_test") else "failed", {"split": {k: (v.get("first"), v.get("last")) for k, v in sp.items()}},
                      "No future observation is in training." if ck.get("train_before_val_before_test") else "The split is not chronological.",
                      "Rebuild the split on unique dates in time order."))
    out.append(_check("target_not_in_features", g, s, "The target is not among the features", "passed" if ck.get("target_not_in_features") else "failed",
                      run.get("features"), "Features exclude the target itself." if ck.get("target_not_in_features") else "Target leakage.",
                      "Remove the target from the feature list."))
    n_test = (sp.get("test") or {}).get("dates", 0)
    out.append(_check("test_sample_size", g, s, f"At least {mc.MIN_TEST_DATES} test dates", "passed" if n_test >= mc.MIN_TEST_DATES else "failed",
                      {"test_dates": n_test, "test_rows": (sp.get("test") or {}).get("rows")}, "Test period large enough to report." if n_test >= mc.MIN_TEST_DATES
                      else "Test period too small.", "Extend the history."))
    out.append(_check("small_test_period", g, s, "Test period of at least 30 dates for stable estimates", "passed" if n_test >= 30 else "warning",
                      {"test_dates": n_test}, "Adequate." if n_test >= 30 else "Under 30 test dates: errors are indicative only.", "Treat as indicative; add more history."))
    finite = all(np.isfinite([m["test"]["mae"], m["test"]["rmse"]]).all() for m in (run.get("models") or {}).values() if "test" in m)
    out.append(_check("metric_validity", g, s, "All reported error metrics are finite", "passed" if finite else "failed", None,
                      "MAE and RMSE are finite for every model." if finite else "A metric is NaN or infinite.", "Inspect predictions for NaNs."))
    bad_mape = [k for k, m in (run.get("models") or {}).items() if m.get("test", {}).get("mape_pct") is not None and m["test"].get("mape_note")]
    out.append(_check("mape_validity", g, s, "MAPE is reported only when the target is safely non-zero", "failed" if bad_mape else "passed", None,
                      "MAPE reported where it should be suppressed." if bad_mape else "MAPE handling is consistent.", "Suppress MAPE for near-zero targets."))
    out.append(_check("baseline_present", g, s, "A simple baseline is included", "passed" if mc.BASELINE_KEY in (run.get("models") or {}) else "failed", None,
                      "Seasonal-naive baseline compared." if mc.BASELINE_KEY in (run.get("models") or {}) else "No baseline.", "Add the seasonal-naive baseline."))
    sel = (run.get("selection") or {}).get("rule", "")
    out.append(_check("selection_without_test", g, s, "Model selection did not use the test period",
                      "passed" if "test period not used" in sel else "warning", sel, "Selected on cross-validation only." if "test period not used" in sel
                      else "Selection rule unclear.", "State the rule explicitly."))
    return out


def evidence_integrity() -> list[dict]:
    g, s = "evidence", "frozen research artefacts"
    out: list[dict] = []
    runs = []
    if RUNS_DIR.exists():
        for d in sorted(RUNS_DIR.iterdir()):
            try:
                m = json.loads((d / "metadata.json").read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if m.get("research_result") and m.get("spec_sha256"):
                runs.append(m)
    if not runs:
        return [_check("frozen_hashes", g, s, "Frozen specification and manifest match the live runs", "not_applicable", None,
                       "No live evaluation run is stored, so there is nothing to compare against.")]
    try:
        spec = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
        spec_sha = hashlib.sha256(json.dumps(spec, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        man_sha = hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest()
    except OSError:
        return [_check("frozen_hashes", g, s, "Frozen specification and manifest can be read", "failed", None, "A frozen file is missing.", "Restore it from version control.")]
    ok_spec = all(m["spec_sha256"] == spec_sha for m in runs)
    ok_man = all(m.get("manifest_sha256") == man_sha for m in runs)
    out.append(_check("frozen_spec", g, s, "The task specification is unchanged since every live run", "passed" if ok_spec else "failed",
                      {"runs_checked": len(runs), "sha256": spec_sha[:16]}, "Hash equals the one recorded by each run." if ok_spec else "The spec changed after a run.",
                      "Restore the frozen specification; any change needs a new spec version and a logged deviation."))
    out.append(_check("frozen_manifest", g, s, "The experiment manifest is unchanged since every live run", "passed" if ok_man else "failed",
                      {"runs_checked": len(runs), "sha256": man_sha[:16]}, "Hash equals the one recorded by each run." if ok_man else "The manifest changed after a run.",
                      "Restore the manifest from version control."))
    partial = [m["run_id"] for m in runs if m.get("run_type") == "partial_pilot" or m.get("status") != "COMPLETED"]
    out.append(_check("run_completeness", g, s, "Live runs follow the full frozen protocol (27 tasks x 5 repeats)", "warning" if partial else "passed",
                      {"partial_runs": partial, "live_runs": len(runs)}, "Every live run so far is partial: the frozen five-repeat benchmark has not been completed."
                      if partial else "All live runs complete.", "Run the remaining frozen protocol when budget allows; keep results labelled partial until then."))
    return out


def run_validation() -> dict[str, Any]:
    checks: list[dict] = []
    datasets = []
    for key, spec in FRAME_SPECS.items():
        df = _read(spec["path"])
        res = validate_frame(df, spec, spec["label"])
        checks += res
        datasets.append({"key": key, "label": spec["label"], "rows": None if df is None else int(len(df))})
    latest = mc.latest_results()
    runs = [r for r in latest["datasets"].values() if r]
    for r in runs:
        checks += validate_model_run(r)
    if not runs:
        checks.append(_check("model_runs", "model", "model comparison", "A model comparison has been run", "not_applicable", None,
                             "No stored model-comparison run exists yet; model-level checks were not run."))
    checks.append(_check("drift", "data", "reference vs current", "Data drift between a reference and a current dataset", "not_applicable", None,
                         "No comparable reference/current dataset pair is registered, so drift cannot be assessed."))
    checks += evidence_integrity()
    counts = {s: sum(1 for c in checks if c["status"] == s) for s in ("passed", "failed", "warning", "not_applicable")}
    run_count = counts["passed"] + counts["failed"] + counts["warning"]
    state = "no_checks_run" if run_count == 0 else "failed" if counts["failed"] else "passed_with_warnings" if counts["warning"] else "passed"
    return {"state": state, "counts": counts, "checks_run": run_count, "total_checks": len(checks), "datasets": datasets,
            "checks": checks, "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds")}
