"""Infrastructure tests for the POS LLM evaluation: data view, spec, ground truth, sandbox, metrics, runner refusal.

Mocks appear ONLY here (to test plumbing); they never produce research results.
"""
import json
from pathlib import Path

import pandas as pd
import pytest

import research.llm_evaluation.run_evaluation as runner
from research.llm_evaluation import report as report_mod
from research.llm_evaluation.data_view import build_view, load_processed, verify_raw_provenance
from research.llm_evaluation.ground_truth import compute, spec_sha256
from research.llm_evaluation.llm_instrument import LLMRecorder, cost_usd, summarize_calls
from research.llm_evaluation.metrics import efficiency, quality, summarize
from research.llm_evaluation.sandbox import SandboxViolation, check_code, run_code
from research.llm_evaluation.scoring import score_answer

SPEC = json.loads((Path(runner.SPEC_PATH)).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def view():
    v, _ = build_view()
    return v


# --------------------------------------------------------------------------- data view
def test_raw_file_is_the_audited_one():
    assert verify_raw_provenance()["ok"]


def test_view_is_ingestible_and_preserves_totals(view):
    processed = load_processed()
    ok = processed[(processed["qty"] > 0) & ((processed["qty"] % 1) == 0) & processed["amount_matches_printed"]]
    assert not view.duplicated(["date", "product", "quantity", "unit_price"]).any()  # would be rejected by the upload validator
    assert (view["quantity"] % 1 == 0).all() and (view["quantity"] > 0).all()
    assert view["revenue"].sum() == pytest.approx((ok["qty"] * ok["rate_inr"]).sum(), abs=0.5)  # merging preserves sales
    assert view["quantity"].sum() == int(ok["qty"].sum())


# --------------------------------------------------------------------------- spec
def test_spec_is_complete_and_preregistered():
    ids = [t["task_id"] for t in SPEC["tasks"]]
    assert len(ids) == len(set(ids)) and 20 <= len(ids) <= 30
    required = {"task_id", "category", "natural_language_question", "expected_answer_type", "required_fields", "date_range",
                "aggregation_definition", "ground_truth_definition", "tolerance", "source_dataset", "notes"}
    for t in SPEC["tasks"]:
        assert required <= set(t), t["task_id"]
        assert t["track"] in ("primary", "supplementary")
        assert t["tolerance"]
    assert SPEC["repeats_per_task"] >= 5
    # no ground-truth value may be written into the spec (it would leak into prompts and cannot be hand-typed)
    assert "answer" not in json.dumps([t["ground_truth_definition"] for t in SPEC["tasks"]])


def test_questions_are_business_owner_language():
    banned = ("group by", "sum(", "select ", "dataframe")
    for t in SPEC["tasks"]:
        q = t["natural_language_question"].lower()
        assert not any(b in q for b in banned), t["task_id"]


# --------------------------------------------------------------------------- ground truth
def test_ground_truth_matches_an_independent_computation_from_the_processed_file():
    """Different code path: straight from processed lines (no merge), plain pandas."""
    gt = json.loads(next(runner.GT_DIR.glob(f"ground_truth_{spec_sha256(SPEC)[:12]}.json")).read_text(encoding="utf-8"))["answers"]
    d = load_processed()
    d = d[(d["qty"] > 0) & ((d["qty"] % 1) == 0) & d["amount_matches_printed"]].copy()
    d["rev"] = d["qty"] * d["rate_inr"]
    d["date"] = pd.to_datetime(d["date"])
    jan, feb, mar = (d[d["date"].dt.month == m] for m in (1, 2, 3))
    assert gt["A01"]["answer"] == pytest.approx(jan["rev"].sum(), abs=0.05)
    assert gt["A02"]["answer"] == pytest.approx(feb["rev"].sum(), abs=0.05)
    assert gt["A03"]["answer"] == pytest.approx(d["rev"].sum(), abs=0.05)
    assert gt["A04"]["answer"] == int(mar["qty"].sum())
    assert gt["A05"]["answer"] == int(feb["qty"].sum())
    assert gt["B01"]["answer"] == pytest.approx((feb["rev"].sum() - jan["rev"].sum()) / jan["rev"].sum() * 100, abs=1e-3)
    assert gt["B03"]["answer"] == str(d.groupby("date")["rev"].sum().idxmax().date())
    assert gt["C01"]["answer"] == [feb.groupby("product")["qty"].sum().idxmax()]
    assert gt["D03"]["answer"] == pytest.approx(d[d["date"].dt.day_name() == "Sunday"]["rev"].sum(), abs=0.05)
    assert gt["D01"]["answer"] == d.assign(wd=d["date"].dt.day_name()).groupby("wd")["rev"].sum().idxmax()
    assert gt["F01"]["answer"] == jan["product"].nunique()
    assert gt["E02"]["answer"] == pytest.approx(d[d["gst_pct"] == 18]["rev"].sum() / d["rev"].sum() * 100, abs=0.05)


def test_ambiguous_ties_are_refused(view):
    v = pd.DataFrame({"date": pd.to_datetime(["2025-01-01", "2025-01-02"]), "product": ["A", "B"], "quantity": [1, 1],
                      "unit_price": [10.0, 10.0], "gst_pct": [0.0, 0.0]})
    v["revenue"] = v["quantity"] * v["unit_price"]
    with pytest.raises(ValueError):
        compute({"op": "argmax_day_revenue", "params": {"start": "2025-01-01", "end": "2025-01-02"}}, v)


def test_unknown_op_fails_loudly(view):
    with pytest.raises(ValueError):
        compute({"op": "nope", "params": {}}, view)


# --------------------------------------------------------------------------- sandbox
def test_sandbox_runs_a_valid_snippet(view):
    out = run_code("result = float(df['revenue'].sum())", view)
    assert out["ok"] and float(out["result"]) == pytest.approx(view["revenue"].sum(), abs=0.01)


@pytest.mark.parametrize("code", ["import os\nresult = 1", "result = open('x').read()", "result = df.to_csv('x.csv')",
                                  "result = df.__class__", "import subprocess", "result = eval('1+1')", "from os import path"])
def test_sandbox_rejects_unsafe_code(code):
    with pytest.raises(SandboxViolation):
        check_code(code)


def test_sandbox_reports_errors_without_raising(view):
    assert not run_code("result = df['nope'].sum()", view)["ok"]
    assert not run_code("x = 1", view)["ok"]  # no `result`
    assert not run_code("import os", view)["ok"]


# --------------------------------------------------------------------------- baseline with a scripted client (plumbing only)
class _ScriptedClient:
    def __init__(self, replies):
        self.replies, self.calls = list(replies), 0

    def complete(self, system, user, **kw):
        self.calls += 1
        return self.replies.pop(0)


def _baseline(view, replies):
    from research.llm_evaluation.systems.llm_code_baseline import LLMCodeBaseline

    b = LLMCodeBaseline(LLMRecorder())
    b._view, b._client = view, _ScriptedClient(replies)
    return b


def test_baseline_handles_malformed_model_output(view):
    b = _baseline(view, ["I think the answer is 42", "Sorry, I could not compute that."])
    out = b.ask(SPEC["tasks"][0])
    assert out["tool_ok"] is False and "answer" in out  # failure recorded, nothing invented


def test_baseline_repairs_once_then_answers(view):
    b = _baseline(view, ["```python\nresult = df['nope'].sum()\n```", "```python\nresult = round(float(df['revenue'].sum()), 2)\n```", "Your sales were that amount."])
    out = b.ask(SPEC["tasks"][0])
    assert out["tool_ok"] and len(out["code_attempts"]) == 2 and out["executed_result"] == str(round(float(view['revenue'].sum()), 2))


def test_baseline_never_sees_gst_on_primary_tasks(view):
    b = _baseline(view, [])
    primary = next(t for t in SPEC["tasks"] if t["track"] == "primary")
    supp = next(t for t in SPEC["tasks"] if t["track"] == "supplementary")
    assert "gst_pct" not in b._frame_for(primary)[1] and "gst_pct" in b._frame_for(supp)[1]


def test_baseline_provider_error_is_recorded_not_hidden(view):
    class Boom(_ScriptedClient):
        def complete(self, *a, **k):
            raise RuntimeError("provider down")

    b = _baseline(view, [])
    b._client = Boom([])
    out = b.ask(SPEC["tasks"][0])
    assert "provider down" in out["error"]
    assert score_answer(SPEC["tasks"][0], 1.0, out.get("answer"), system_error=out["error"])["outcome"] == "tool_data_access_failure"


# --------------------------------------------------------------------------- instrumentation & metrics
def test_token_and_cost_are_none_when_not_returned():
    calls = [{"ok": True, "latency_s": 0.5, "input_tokens": None, "output_tokens": None, "model_requested": "m"}]
    s = summarize_calls(calls)
    assert s["input_tokens"] is None and s["output_tokens"] is None
    assert cost_usd(calls, {"m": {"input_per_million_usd": 1, "output_per_million_usd": 2}}) is None  # never estimated


def test_cost_needs_complete_usage_and_a_supplied_price():
    calls = [{"ok": True, "input_tokens": 1000, "output_tokens": 500, "model_requested": "m", "model_returned": "m"}]
    assert cost_usd(calls, None) is None
    assert cost_usd(calls, {"m": {"input_per_million_usd": 2.0, "output_per_million_usd": 4.0}}) == pytest.approx(0.004)


def _row(system, task_id, category, correct, outcome="correct", **extra):
    return {"system": system, "condition": "asof", "task_id": task_id, "repeat": 1, "latency_s": 1.0, "llm_summary": {"n_calls": 0, "input_tokens": None, "output_tokens": None},
            "task": {"task_id": task_id, "track": "primary", "category": category, "expected_answer_type": "currency"},
            "score": {"correct": correct, "outcome": outcome, **extra}}


def test_metrics_partial_run_and_no_fake_zeros():
    rows = [_row("decisiongpt", "A01", "aggregation", True), _row("decisiongpt", "A02", "aggregation", False, "unable_to_answer")]
    m = summarize(rows)["decisiongpt|asof"]["primary"]
    assert m["quality"]["n_attempts"] == 2 and m["quality"]["accuracy_primary_pct"] == 50.0
    assert m["quality"]["failure_rates_pct"]["unable_to_answer"] == 50.0
    assert m["efficiency"]["tokens"]["input_total"] is None and m["efficiency"]["cost_usd_total"] is None  # not 0


def test_empty_quality_is_not_a_number():
    assert quality([]) == {"n_attempts": 0}
    assert efficiency([])["latency_end_to_end_s"]["median"] is None


# --------------------------------------------------------------------------- runner refuses without a real LLM
def test_run_is_blocked_without_a_real_llm_and_creates_no_results(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "RUNS_DIR", tmp_path)
    monkeypatch.setattr(runner, "llm_status", lambda: {"enabled": False, "provider": None, "model_configured": None, "api_key_present": False})
    code = runner.main(["run"])
    assert code == runner.EXIT_BLOCKED
    dirs = list(tmp_path.iterdir())
    assert len(dirs) == 1
    meta = json.loads((dirs[0] / "metadata.json").read_text(encoding="utf-8"))
    assert meta["status"] == "BLOCKED" and meta["research_result"] is False
    assert not (dirs[0] / "task_results.jsonl").exists() and not (dirs[0] / "metrics.json").exists()
    page = report_mod.write_report(dirs[0]).read_text(encoding="utf-8")
    assert "no results exist" in page and "accuracy" not in page.lower()
    Path(report_mod.REPORTS_DIR / f"{meta['run_id']}.md").unlink(missing_ok=True)


def test_smoke_never_becomes_a_research_report(tmp_path):
    meta = {"run_id": "smoke_x", "status": "COMPLETED", "research_result": False, "note": "plumbing"}
    (tmp_path / "metadata.json").write_text(json.dumps(meta), encoding="utf-8")
    p = report_mod.write_report(tmp_path)
    try:
        assert "No metrics are reported" in p.read_text(encoding="utf-8")
    finally:
        p.unlink(missing_ok=True)
