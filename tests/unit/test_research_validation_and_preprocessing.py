"""Validation checks (empty / malformed / missing columns / success) and the one-action preprocessing pipeline."""
import numpy as np
import pandas as pd
import pytest

from app.services import research_preprocessing_service as pp
from app.services import research_validation_service as val

SPEC = {"label": "t", "required": ["date", "units", "price"], "date": "date", "key": ["date"], "target": "units", "nonneg": ["units", "price"],
        "positive": ["price"], "numeric": ["units", "price"], "consistency": None, "min_dates": 30}


def good(n=60):
    return pd.DataFrame({"date": pd.date_range("2025-01-01", periods=n).strftime("%Y-%m-%d"), "units": np.arange(n) % 9 + 5, "price": 10.0})


def by_id(checks):
    return {c["id"]: c for c in checks}


# ------------------------------------------------------------------ validation
def test_unreadable_file_is_a_failure_not_a_pass():
    c = val.validate_frame(None, SPEC, "t")
    assert len(c) == 1 and c[0]["status"] == "failed" and c[0]["remedy"]


def test_empty_dataset_fails_and_stops():
    c = by_id(val.validate_frame(good().iloc[0:0], SPEC, "t"))
    assert c["non_empty"]["status"] == "failed" and "required_columns" not in c


def test_missing_columns_fail_with_a_named_remedy():
    c = by_id(val.validate_frame(good().drop(columns=["price"]), SPEC, "t"))
    assert c["required_columns"]["status"] == "failed" and c["required_columns"]["observed"] == {"missing": ["price"]}
    assert "price" in c["required_columns"]["explanation"] and c["required_columns"]["remedy"]


def test_malformed_values_are_detected():
    df = good().astype({"units": object})
    df.loc[3, "date"] = "not-a-date"
    df.loc[4, "units"] = "many"
    df.loc[5, "price"] = -2
    df.loc[6, "date"] = df.loc[7, "date"]  # duplicate key
    c = by_id(val.validate_frame(df, SPEC, "t"))
    assert c["date_parse"]["status"] == "failed" and c["date_parse"]["observed"]["unparseable"] == 1
    assert c["numeric_types"]["status"] == "failed" and "units" in c["numeric_types"]["observed"]["non_numeric_values_in"]
    assert c["non_negative_values"]["status"] == "failed"
    assert c["duplicate_keys"]["status"] == "failed"


def test_successful_validation_passes_every_applicable_check():
    c = val.validate_frame(good(), SPEC, "t")
    st = {x["id"]: x["status"] for x in c}
    assert st["required_columns"] == "passed" and st["date_continuity"] == "passed" and st["sample_size"] == "passed"
    assert not any(x["status"] == "failed" for x in c)


def test_a_date_gap_is_a_warning_with_the_missing_dates_listed():
    df = good().drop(index=[10])
    c = by_id(val.validate_frame(df, SPEC, "t"))
    assert c["date_continuity"]["status"] == "warning" and c["date_continuity"]["observed"]["missing_dates"] == ["2025-01-11"]


def test_missing_target_share_decides_between_warning_and_failure():
    df = good()
    df.loc[0, "units"] = np.nan
    assert by_id(val.validate_frame(df, SPEC, "t"))["missing_values"]["status"] == "warning"
    df.loc[:5, "units"] = np.nan
    assert by_id(val.validate_frame(df, SPEC, "t"))["missing_values"]["status"] == "failed"


def test_every_check_has_the_traceability_fields():
    for c in val.validate_frame(good(), SPEC, "t"):
        assert {"id", "group", "subject", "rule", "status", "observed", "explanation"} <= set(c)
        assert c["status"] in {"passed", "failed", "warning", "not_applicable"}


def test_overall_state_distinguishes_no_checks_from_passed(monkeypatch):
    monkeypatch.setattr(val, "FRAME_SPECS", {})
    monkeypatch.setattr(val.mc, "latest_results", lambda: {"datasets": {}, "available": [], "not_run": [], "dataset_catalogue": {}})
    monkeypatch.setattr(val, "evidence_integrity", lambda: [])
    r = val.run_validation()
    # the drift check is not_applicable, so zero checks actually ran: state must not read as 'passed'
    assert r["checks_run"] == 0 and r["state"] == "no_checks_run" and r["counts"]["passed"] == 0


def test_model_run_leakage_checks_fail_when_the_split_is_not_chronological():
    run = {"run_id": "r", "checks": {"train_before_val_before_test": False, "target_not_in_features": True},
           "split": {"test": {"dates": 12, "rows": 12}}, "models": {val.mc.BASELINE_KEY: {"test": {"mae": 1.0, "rmse": 1.0}}},
           "selection": {"rule": "lowest CV RMSE (test period not used)"}, "features": ["lag_1"]}
    c = by_id(val.validate_model_run(run))
    assert c["temporal_split_order"]["status"] == "failed"
    assert c["target_not_in_features"]["status"] == "passed" and c["small_test_period"]["status"] == "warning"


# ------------------------------------------------------------------ preprocessing
def messy():
    return pd.DataFrame({
        "Order Date": ["2025-01-0%d" % (i % 9 + 1) for i in range(40)] + ["2025-02-10"] * 5,
        "Product Name ": [" milk " if i % 3 == 0 else "EGG" for i in range(45)],
        "Qty": [str(i % 7 + 1) for i in range(45)],
        "Amount": [float(i * 10) for i in range(44)] + [-5.0],
    })


def test_plan_is_conditional_on_the_data():
    steps = {s["id"]: s for s in pp.plan(messy())}
    assert steps["normalize_names"]["applies"] and steps["parse_dates"]["applies"] and steps["coerce_numeric"]["applies"]
    clean = pd.DataFrame({"a": np.arange(10.0), "b": np.arange(10.0) * 2})
    c = {s["id"]: s for s in pp.plan(clean)}
    assert not c["parse_dates"]["applies"] and not c["normalize_names"]["applies"] and not c["chronological_split"]["applies"]


def test_pipeline_never_deletes_rows_or_changes_values_silently():
    df = messy()
    out, rep = pp.apply_pipeline(df)
    assert len(out) == len(df) and rep["rows_removed"] == 0 and rep["business_totals_changed"] is False
    assert out["amount"].sum() == pytest.approx(df["Amount"].sum())  # totals untouched
    assert pd.api.types.is_datetime64_any_dtype(out["order_date"]) and pd.api.types.is_numeric_dtype(out["qty"])
    assert int(out["_flag_invalid_value"].sum()) == 1  # the negative amount is flagged, not changed
    assert (out["amount"] == -5.0).sum() == 1
    assert out["product_name"].str.strip().tolist() == out["product_name"].tolist()


def test_source_dataframe_is_not_modified():
    df = messy()
    snap = df.copy(deep=True)
    pp.apply_pipeline(df)
    pd.testing.assert_frame_equal(df, snap)


def test_chronological_split_assignment_is_ordered_and_needs_enough_dates():
    n = 100
    df = pd.DataFrame({"date": pd.date_range("2025-01-01", periods=n).strftime("%Y-%m-%d"), "v": np.arange(n, dtype=float)})
    out, rep = pp.apply_pipeline(df)
    d = pd.to_datetime(out["date"])
    assert d[out["_split"] == "train"].max() < d[out["_split"] == "validation"].min() <= d[out["_split"] == "validation"].max() < d[out["_split"] == "test"].min()
    assert rep["notes"]["split"]["rows"] == {"train": 70, "validation": 15, "test": 15}
    short = pd.DataFrame({"date": pd.date_range("2025-01-01", periods=10).strftime("%Y-%m-%d"), "v": np.arange(10.0)})
    assert "_split" not in pp.apply_pipeline(short)[0].columns


def test_deterministic_checksums_and_versioned_output(tmp_path):
    df = messy()
    assert pp.frame_checksum(pp.apply_pipeline(df)[0]) == pp.frame_checksum(pp.apply_pipeline(df)[0])
    r = pp.run_and_store(df, "abcdef12-0000-0000-0000-000000000001", tmp_path)
    assert r["status"] == "completed" and r["raw_dataset_modified"] is False and r["source_version_id"].startswith("abcdef12")
    out = tmp_path / "processed" / r["source_version_id"] / r["run_id"]
    assert (out / "processed.csv").exists() and (out / "report.json").exists()
    assert r["config"]["input_sha256"] and r["output_sha256"]
    assert [x["run_id"] for x in pp.list_runs(tmp_path, r["source_version_id"])] == [r["run_id"]]


def test_a_concurrent_run_for_the_same_dataset_is_refused(tmp_path):
    lock = pp._lock_for("abcdef12-0000-0000-0000-000000000002")
    assert lock.acquire(blocking=False)
    try:
        r = pp.run_and_store(messy(), "abcdef12-0000-0000-0000-000000000002", tmp_path)
        assert r["status"] == "busy"
    finally:
        lock.release()


def test_failures_are_recorded_not_hidden(tmp_path, monkeypatch):
    def boom(df, enabled=None):
        raise RuntimeError("explode")

    monkeypatch.setattr(pp, "apply_pipeline", boom)
    r = pp.run_and_store(messy(), "abcdef12-0000-0000-0000-000000000003", tmp_path)
    assert r["status"] == "failed" and "explode" in r["error"]
    assert pp.get_run(tmp_path, "abcdef12-0000-0000-0000-000000000003", r["run_id"])["status"] == "failed"


def test_run_lookup_rejects_path_traversal(tmp_path):
    assert pp.get_run(tmp_path, "../../etc", "pp_20260101T000000Z_deadbeef") is None
    assert pp.get_run(tmp_path, "abcdef12-0000-0000-0000-000000000001", "../../x") is None
