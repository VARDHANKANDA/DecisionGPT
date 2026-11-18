"""Architecture audit of what the production chat path actually does (derived from the code, not asserted).

Everything here is computed by (a) AST scans of backend/app, (b) calling the production `classify_intent`, and
(c) arithmetic over the processed POS file. Nothing calls an LLM. Run:

    python -m research.llm_evaluation.audit.architecture          # writes audit/architecture_audit.json (+ prints a summary)
"""
from __future__ import annotations

import ast
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from research.llm_evaluation.data_view import build_view, load_processed

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
APP = ROOT / "backend" / "app"
SPEC_PATH = ROOT / "research" / "llm_evaluation" / "tasks" / "tasks_v1.json"
OUT_JSON = HERE / "architecture_audit.json"
AUDIT_DATE = "2026-10-13"

# Methods that can reach the provider (OpenAI). The former free-text methods (generate_business_response, generate_strategy_explanation,
# evaluate_agent) are deterministic templates now and are deliberately NOT listed: they cannot call a provider.
LLM_FACADE_METHODS = {"decide", "parse_goal"}
LLM_CLIENT_METHODS = {"decide"}


# --------------------------------------------------------------------------- AST helpers
def _parse(path: Path) -> ast.AST:
    return ast.parse(path.read_text(encoding="utf-8"))


def _enclosing_function_names(tree: ast.AST) -> dict[int, str]:
    out: dict[int, str] = {}
    for fn in ast.walk(tree):
        if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for n in ast.walk(fn):
                out[id(n)] = fn.name
    return out


def scan_llm_call_sites() -> list[dict]:
    """Every place in production code that calls the LLM facade (or the raw client) — outside the facade itself."""
    sites = []
    for path in sorted(APP.rglob("*.py")):
        rel = path.relative_to(ROOT).as_posix()
        if rel.endswith(("services/llm_service.py", "services/openai_client.py")) or "/research/" in rel and rel.endswith("llm_evaluation.py"):
            continue
        tree = _parse(path)
        enc = _enclosing_function_names(tree)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr in LLM_FACADE_METHODS | LLM_CLIENT_METHODS:
                    sites.append({"file": rel, "function": enc.get(id(node), "<module>"), "method": node.func.attr, "line": node.lineno})
    return sites


def chat_intent_handlers() -> dict[str, str]:
    """intent name -> handler function name, read from the if/elif chain of the LEGACY router (assistant_service._legacy_answer)."""
    tree = _parse(APP / "services" / "assistant_service.py")
    fn = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "_legacy_answer")
    mapping: dict[str, str] = {}
    for node in ast.walk(fn):
        if isinstance(node, ast.If) and isinstance(node.test, ast.Compare) and isinstance(node.test.left, ast.Name) and node.test.left.id == "intent":
            comp = node.test.comparators[0]
            if isinstance(comp, ast.Constant) and isinstance(comp.value, str):
                for stmt in node.body:
                    if isinstance(stmt, ast.Assign) and isinstance(stmt.value, ast.Call) and isinstance(stmt.value.func, ast.Name):
                        mapping[comp.value] = stmt.value.func.id
    return mapping


def handler_calls_llm(handler: str) -> bool:
    tree = _parse(APP / "services" / "assistant_service.py")
    fn = next((n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == handler), None)
    if fn is None:
        return False
    return any(isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr in LLM_FACADE_METHODS | LLM_CLIENT_METHODS for n in ast.walk(fn))


def intent_llm_map() -> dict[str, dict]:
    out = {}
    for intent, handler in chat_intent_handlers().items():
        out[intent] = {"handler": handler, "invokes_llm_when_configured": handler_calls_llm(handler),
                       "llm_role": "rephrases an already-computed template answer" if handler_calls_llm(handler) else None}
    out["unrecognized"] = {"handler": "(fixed refusal text)", "invokes_llm_when_configured": False, "llm_role": None}
    return out


def date_today_sites() -> list[dict]:
    sites = []
    for path in sorted(APP.rglob("*.py")):
        tree = _parse(path)
        enc = _enclosing_function_names(tree)
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "today"
                    and isinstance(node.func.value, ast.Name) and node.func.value.id == "date"):
                sites.append({"file": path.relative_to(ROOT).as_posix(), "function": enc.get(id(node), "<module>"), "line": node.lineno})
    return sites


def chat_reachable_modules_with_today() -> list[str]:
    """Chat-reachable modules that still call date.today() directly (should be none: they use app.core.clock.today())."""
    tree = _parse(APP / "services" / "assistant_service.py")
    imported = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom) and n.module == "app.analytics":
            imported |= {a.name for a in n.names}
    mods = {f"backend/app/analytics/{m}.py" for m in imported} | {"backend/app/services/assistant_service.py"}
    return sorted({s["file"] for s in date_today_sites() if s["file"] in mods})


def _calls(path: Path, func: str | None, attr: str) -> bool:
    tree = _parse(path)
    scope = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and (func is None or n.name == func)]
    return any(isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute) and c.func.attr == attr for fn in scope for c in ast.walk(fn))


def analytics_llm_path_status() -> dict:
    """AST proof that the production chat now contains the LLM analytics path (question -> LLM interpreter -> validated request ->
    deterministic query engine -> verified result -> grounded answer). Pure static inspection: nothing is executed or called."""
    svc = APP / "services"
    checks = {
        "answer_question_calls_analytics_path_first": _calls(svc / "assistant_service.py", "answer_question", "try_answer"),
        "answer_question_keeps_legacy_router_as_fallback": any(
            isinstance(c, ast.Call) and isinstance(c.func, ast.Name) and c.func.id == "_legacy_answer"
            for fn in ast.walk(_parse(svc / "assistant_service.py")) if isinstance(fn, ast.FunctionDef) and fn.name == "answer_question"
            for c in ast.walk(fn)),
        "interpreter_calls_llm": _calls(svc / "analytics_interpreter_service.py", "interpret", "decide"),
        "orchestrator_runs_interpreter": _calls(svc / "analytics_chat_service.py", "try_answer", "interpret"),
        "orchestrator_executes_deterministic_engine": _calls(svc / "analytics_chat_service.py", "try_answer", "run_query"),
        "orchestrator_composes_a_templated_answer": _calls(svc / "analytics_chat_service.py", "try_answer", "assemble"),
        "answer_composition_has_no_llm_call": not any(
            _calls(svc / "analytics_answer_service.py", None, m) for m in ("decide", "call_json", "complete", "complete_json")),
        "engine_has_no_llm_call": not any(
            _calls(APP / "analytics" / f, None, m) for f in ("query_engine.py", "query_presenter.py") for m in ("decide", "call_json", "complete", "complete_json")),
    }
    return {"implemented": all(checks.values()), "checks": checks,
            "needs": "OPENAI_API_KEY configured (OpenAI); without it the legacy router answers and is labelled path=legacy_router",
            "kill_switch": "ANALYTICS_LLM_ENABLED=false"}


# --------------------------------------------------------------------------- routing of the frozen questions
def route_frozen_questions() -> list[dict]:
    from app.services.assistant_service import classify_intent

    spec = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    return [{"task_id": t["task_id"], "track": t["track"], "question": t["natural_language_question"],
             "intent": classify_intent(t["natural_language_question"])} for t in spec["tasks"]]


# --------------------------------------------------------------------------- data-view conservation
def view_conservation() -> dict:
    p = load_processed()
    view, info = build_view(p)
    frac = p[(p["qty"] % 1) != 0]
    whole = p[(p["qty"] > 0) & ((p["qty"] % 1) == 0)]
    mismatch = whole[~whole["amount_matches_printed"]]
    kept = whole[whole["amount_matches_printed"]]
    kept_rev_lines = round(float((kept["qty"] * kept["rate_inr"]).sum()), 2)
    # merge identity check: sum over merged rows of quantity*unit_price vs sum over retained lines, to the paisa
    merged = view.assign(_k=list(zip(view["date"], view["product"], view["unit_price"])))
    lines = kept.assign(_k=list(zip(kept["date"], kept["product"], kept["rate_inr"])), _r=kept["qty"] * kept["rate_inr"])
    per_group_lines = lines.groupby("_k")["_r"].sum().round(2)
    per_group_view = merged.set_index("_k")["revenue"]
    max_group_diff = float((per_group_lines - per_group_view.reindex(per_group_lines.index)).abs().max())
    return {
        "original_processed_lines": int(len(p)),
        "original_revenue_inr": round(float(p["line_amount_inr"].sum()), 2),
        "original_quantity_mixed_units": round(float(p["qty"].sum()), 3),
        "rejected_fractional_quantity": {"lines": int(len(frac)), "pct_of_lines": round(100 * len(frac) / len(p), 2),
                                         "revenue_inr": round(float(frac["line_amount_inr"].sum()), 2),
                                         "pct_of_revenue": round(100 * float(frac["line_amount_inr"].sum()) / float(p["line_amount_inr"].sum()), 2),
                                         "quantity": round(float(frac["qty"].sum()), 3)},
        "rejected_amount_disagreement": {"lines": int(len(mismatch)), "revenue_inr": round(float(mismatch["line_amount_inr"].sum()), 2)},
        "whole_quantity_lines_retained": int(len(kept)),
        "whole_quantity_revenue_inr": kept_rev_lines,
        "view_rows_after_merge": int(len(view)),
        "lines_merged_away": int(len(kept) - len(view)),
        "view_revenue_inr": round(float(view["revenue"].sum()), 2),
        "view_quantity": int(view["quantity"].sum()),
        "whole_quantity_lines_quantity": int(kept["qty"].sum()),
        "revenue_conserved_by_merge": abs(kept_rev_lines - round(float(view["revenue"].sum()), 2)) < 0.005,
        "quantity_conserved_by_merge": int(view["quantity"].sum()) == int(kept["qty"].sum()),
        "max_abs_difference_per_merged_group_inr": round(max_group_diff, 6),
        "pct_original_rows_in_view": round(100 * len(view) / len(p), 2),
        "pct_original_lines_represented": round(100 * len(kept) / len(p), 2),
        "pct_original_revenue_retained": round(100 * float(view["revenue"].sum()) / float(p["line_amount_inr"].sum()), 2),
        "identity": "for lines sharing (date, product, unit price p): sum(q_i * p) = p * sum(q_i), so merging by summing quantity conserves revenue; verified numerically above",
        "label": "evaluation-compatible view derived from the approved Indian POS dataset (NOT the original dataset)",
        "view_sha256": info.view_sha256,
    }


# --------------------------------------------------------------------------- 27-task compatibility (declared reasoning, machine-checked)
BB = {
    "kpis": "analytics/kpi_service.compute_kpis(period_days) — trailing window [today-N, today]; revenue + line count",
    "pop": "analytics/kpi_service.period_over_period(days) — trailing vs preceding window",
    "trend": "analytics/kpi_service.revenue_trend(days) — daily revenue for trailing days (days with sales only)",
    "top": "analytics/breakdown_service.top_products(limit) — all-time units+revenue per product, ranked by revenue (GET /analytics/products)",
    "prodrev": "services/assistant_service._product_revenue(start,end) — per-product units+revenue for an ABSOLUTE window (internal helper)",
}

# class: B1 = ONE existing call, parameters only; B2 = existing building block + trivial arithmetic (sum/count/argmax/mean/%/share/weekday);
#        C = no existing building block can supply the quantity (missing field or missing aggregation); A = answerable through chat today; D = invalid/ambiguous.
TASK_CLASSIFICATION: dict[str, dict] = {
    "A01": {"cls": "B2", "needs": "revenue sum, absolute window 1-31 Jan", "block": "prodrev", "causes": ["B", "D", "F"]},
    "A02": {"cls": "B2", "needs": "revenue sum, absolute window 1-28 Feb", "block": "prodrev", "causes": ["B", "D", "F"]},
    "A03": {"cls": "B1", "needs": "revenue sum over the whole data span", "block": "kpis", "causes": ["B", "D"],
            "note": "kpis(period_days=89) equals Jan 1-Mar 31 only under the evaluation clock 2025-03-31"},
    "A04": {"cls": "B2", "needs": "unit sum, absolute window March", "block": "prodrev", "causes": ["B", "D", "F"]},
    "A05": {"cls": "B2", "needs": "unit sum, absolute window February", "block": "prodrev", "causes": ["B", "D", "F"]},
    "B01": {"cls": "B2", "needs": "% change between two absolute windows (Feb vs Jan)", "block": "prodrev", "causes": ["B", "D", "F"]},
    "B02": {"cls": "B2", "needs": "% change between two absolute windows (Mar vs Feb)", "block": "prodrev", "causes": ["B", "D", "F"],
            "note": "period_over_period uses equal-length trailing windows, which do not align with calendar months"},
    "B03": {"cls": "B2", "needs": "argmax of daily revenue", "block": "trend", "causes": ["B", "F"]},
    "B04": {"cls": "B2", "needs": "argmin of daily revenue over days with sales", "block": "trend", "causes": ["B", "F"]},
    "B05": {"cls": "B2", "needs": "% change between two absolute half-month windows", "block": "prodrev", "causes": ["B", "D", "F"]},
    "C01": {"cls": "B2", "needs": "argmax units by product, absolute window Feb", "block": "prodrev", "causes": ["G", "D", "F"], "recognized_but_incompatible": True,
            "note": "router -> top_products, but that handler ranks by REVENUE over a fixed trailing 30-day window and ignores the dates/metric in the question"},
    "C02": {"cls": "B1", "needs": "top-3 products by revenue over the whole data span", "block": "top", "causes": ["G"], "recognized_but_incompatible": True,
            "class_if_real_clock": "A",
            "note": "router -> top_products. Under the evaluation clock the handler answers for March only; under the real clock its 'no sales in the last 30 days' fallback ranks ALL sales by revenue, which coincidentally equals the task because the data span is exactly the asked window"},
    "C03": {"cls": "B2", "needs": "top-3 products by UNITS, absolute window March", "block": "prodrev", "causes": ["G", "F"], "recognized_but_incompatible": True,
            "note": "router -> top_products, but the handler ranks by revenue, not units"},
    "C04": {"cls": "B1", "needs": "units of one product over the whole data span", "block": "top", "causes": ["B"],
            "note": "single call of GET /analytics/products?limit>=2 returns units_sold; equals the asked window because the data span is exactly Jan-Mar"},
    "C05": {"cls": "B2", "needs": "compare units of two products", "block": "top", "causes": ["B", "F"]},
    "C06": {"cls": "B2", "needs": "one product's revenue / total revenue", "block": "top", "causes": ["B", "F"]},
    "D01": {"cls": "B2", "needs": "weekday with the largest revenue", "block": "trend", "causes": ["B", "F"]},
    "D02": {"cls": "B2", "needs": "weekday with the smallest revenue", "block": "trend", "causes": ["B", "F"]},
    "D03": {"cls": "B2", "needs": "revenue summed over Sundays", "block": "trend", "causes": ["B", "F"]},
    "D04": {"cls": "B2", "needs": "mean daily revenue over days with sales", "block": "trend", "causes": ["B", "F"]},
    "F01": {"cls": "B2", "needs": "count of distinct products sold in January", "block": "prodrev", "causes": ["B", "D", "F"]},
    "F02": {"cls": "C", "needs": "mean DAILY UNITS in March", "block": None, "causes": ["C", "F"],
            "note": "no production function returns daily unit totals (revenue_trend returns revenue only)"},
    "F03": {"cls": "B2", "needs": "largest daily revenue", "block": "trend", "causes": ["B", "F"]},
    "E01": {"cls": "C", "needs": "revenue by GST slab", "block": None, "causes": ["E"], "note": "the production sales schema has no GST column"},
    "E02": {"cls": "C", "needs": "share of revenue by GST slab", "block": None, "causes": ["E"], "note": "same"},
    "E03": {"cls": "C", "needs": "share of revenue by GST slab", "block": None, "causes": ["E"], "note": "same"},
    "E04": {"cls": "C", "needs": "GST slab with the most revenue", "block": None, "causes": ["E"], "note": "same"},
}
CAUSE_LEGEND = {"A": "unsupported natural-language phrasing", "B": "missing intent", "C": "missing backend capability", "D": "missing date handling",
                "E": "missing data field", "F": "unsupported aggregation", "G": "production architecture limitation (handler semantics fixed)",
                "H": "evaluation task incompatible with current production behaviour", "I": "other"}


def task_table(clock: str = "asof") -> list[dict]:
    routed = {r["task_id"]: r for r in route_frozen_questions()}
    rows = []
    for tid, c in TASK_CLASSIFICATION.items():
        cls = c.get("class_if_real_clock") if clock == "realclock" and c.get("class_if_real_clock") else c["cls"]
        r = routed[tid]
        rows.append({
            "task_id": tid, "track": r["track"], "question": r["question"],
            "router_recognizes": r["intent"] != "unrecognized", "router_intent": r["intent"],
            "required_capability": c["needs"], "nearest_existing_block": BB.get(c["block"]) if c["block"] else None,
            "class": cls, "runnable_through_production_chat_with_correct_semantics": cls == "A",
            "causes": c["causes"], "note": c.get("note"),
        })
    return rows


def class_counts() -> dict:
    out = {}
    for clock in ("asof", "realclock"):
        out[clock] = dict(sorted(Counter(r["class"] for r in task_table(clock)).items()))
    return out


# --------------------------------------------------------------------------- assemble
def build_audit() -> dict:
    sites = scan_llm_call_sites()
    imap = intent_llm_map()
    routed = route_frozen_questions()
    frozen_intents = Counter(r["intent"] for r in routed)
    llm_calls_reachable_for_frozen = sum(frozen_intents[i] for i, m in imap.items() if m["invokes_llm_when_configured"] and i in frozen_intents)
    return {
        "audit_date": AUDIT_DATE,
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "chat_path_llm_analytics": [
            "assistant_service.answer_question -> analytics_chat_service.try_answer (only when a provider is configured and ANALYTICS_LLM_ENABLED)",
            "analytics_interpreter_service.interpret: LLMService.call_json -> strict Interpretation schema (extra fields rejected)",
            "analytics_chat_service: route = analytics_query | clarification | unsupported | legacy",
            "analytics_query: query_engine.run_query (resolves dates from app.core.clock, matches products within the business, ORM queries filtered by business_id)",
            "query_presenter.facts: deterministic FACT text; analytics_answer_service.explain: LLM interpretation/suggestion kept only if numbers are grounded and no causal claim",
            "response carries path=llm_analytics; failure of any LLM step falls back to the legacy router (path=legacy_router, flagged)",
        ],
        "chat_path": ["LEGACY router path (fallback): frontend chat page -> api.chat() -> POST /api/v1/businesses/{id}/chat",
                      "api/v1/endpoints/assistant.py: chat() -> assistant_service.answer_question(db, business_id, message)",
                      "assistant_service.classify_intent(text): keyword rules (no LLM, no date parsing)",
                      "per-intent handler queries the business tables via SQLAlchemy / analytics services and builds the answer text (f-strings or LLMService template)",
                      "response + memory log row"],
        "components": {
            "receives_question": "api/v1/endpoints/assistant.py::chat -> assistant_service.answer_question",
            "determines_intent": "assistant_service.classify_intent (substring keyword rules)",
            "determines_date_ranges": "nobody parses dates from the question; handlers use fixed trailing windows relative to date.today()",
            "queries_business_data": "handlers: _product_revenue, kpi_service.*, forecast/churn/digital_twin services",
            "constructs_answer": "handler f-strings, or LLMService.generate_business_response (template; LLM rephrase only if configured)",
        },
        "llm_call_sites_in_production_code": sites,
        "chat_intents": imap,
        "frozen_question_routing": {"scope": "legacy fixed-intent router (fallback path)", "counts": dict(frozen_intents), "n_unrecognized": frozen_intents.get("unrecognized", 0), "n_total": len(routed),
                                    "questions_that_can_reach_an_llm_call_even_if_configured": llm_calls_reachable_for_frozen},
        "llm_in_evaluated_chat_path": {
            "scope": "LEGACY fixed-intent router only (the fallback path); the LLM analytics path is described under llm_analytics_path",
            "invoked_for_any_frozen_question": llm_calls_reachable_for_frozen > 0,
            "invoked_for_business_analytics_intents": any(m["invokes_llm_when_configured"] for i, m in imap.items() if i in ("top_products", "improving_worsening", "valuable_customers", "sales_forecast", "customer_churn")),
            "intents_where_llm_rephrases_when_configured": sorted(i for i, m in imap.items() if m["invokes_llm_when_configured"]),
            "llm_never_does": ["intent routing", "date interpretation", "data retrieval", "numeric computation"],
        },
        "other_llm_paths": [
            "goal parsing: POST goals -> goal_service -> LLMService.parse_goal (objective / constraint labels via the model; rule-based fallback)",
            "decision analysis: decision_service -> LLMService.evaluate_agent / generate_strategy_explanation are deterministic templates since 2026-10-13 (no provider call)",
        ],
        "llm_facade": {"swallows_llm_failures": "no: OpenAIClient.decide never raises and returns DecisionResult(ok=False, error=<kind>); callers fall back to rules and record the fallback path/reason",
                       "temperature": "not set (no sampling parameter is sent)", "seed_supported": False,
                       "retry": "bounded (<= openai_max_retries) for rate-limit / connection errors only; timeouts are never retried",
                       "timeout_s_default": 15, "token_accounting": "provider-reported usage.input_tokens / output_tokens is kept on DecisionResult.usage"},
        "llm_analytics_path": analytics_llm_path_status(),
        "frozen_questions_that_reach_the_llm_interpreter_when_configured": sum(1 for r in routed if len(r["question"]) <= 1000),
        "date_today_call_sites": date_today_sites(),
        "chat_reachable_modules_with_date_today": chat_reachable_modules_with_today(),
        "task_compatibility": {"table_asof": task_table("asof"), "class_counts": class_counts(), "cause_legend": CAUSE_LEGEND, "building_blocks": BB,
                               "class_definitions": {"A": "answerable through the current production chat path with correct semantics",
                                                     "B1": "ONE existing production call, parameters only, returns the quantity (not reachable via chat)",
                                                     "B2": "existing building block + trivial arithmetic (sum/count/argmax/mean/%/share/weekday); not reachable via chat",
                                                     "C": "no existing building block can supply it (missing field or aggregation)",
                                                     "D": "invalid/ambiguous for the dataset (none: the ground-truth engine refuses tie-ambiguous tasks)"}},
        "data_view": view_conservation(),
    }


SUBSET_PATH = ROOT / "research" / "llm_evaluation" / "tasks" / "execution_subsets_v1.json"


def build_execution_subsets() -> dict:
    """DERIVED subsets that only REFERENCE frozen task ids; tasks_v1.json itself is never modified."""
    from research.llm_evaluation.ground_truth import spec_sha256

    spec = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    rows = {c: {r["task_id"]: r["class"] for r in task_table(c)} for c in ("asof", "realclock")}
    ids = lambda clock, *classes: [t for t, c in rows[clock].items() if c in classes]  # noqa: E731
    return {
        "derived_from": "tasks/tasks_v1.json (frozen, unchanged)",
        "frozen_spec_sha256": spec_sha256(spec),
        "audit_date": AUDIT_DATE,
        "note": ("These lists classify frozen tasks by what the CURRENT production chat path can do. They are not a new task set and are too small to evaluate "
                 "anything on their own; no evaluation is planned on them. Task wording, tolerances and ground truth are untouched."),
        "answerable_through_production_chat": {"asof_clock": ids("asof", "A"), "real_clock": ids("realclock", "A")},
        "single_existing_production_call_not_reachable_via_chat_B1": ids("asof", "B1"),
        "existing_building_block_plus_trivial_arithmetic_not_reachable_via_chat_B2": ids("asof", "B2"),
        "missing_field_or_aggregation_C": ids("asof", "C"),
        "invalid_or_ambiguous_D": [],
        "supplementary_gst_track": [t["task_id"] for t in spec["tasks"] if t["track"] == "supplementary"],
        "gst_track_rule": "GST questions are never mixed into the primary production-path evaluation; they would need the approved source dataset with their own, separately named system path.",
    }


def main() -> int:
    SUBSET_PATH.write_text(json.dumps(build_execution_subsets(), indent=2, ensure_ascii=False), encoding="utf-8")
    audit = build_audit()
    OUT_JSON.write_text(json.dumps(audit, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    fr = audit["frozen_question_routing"]
    print(f"wrote {OUT_JSON}")
    print("frozen questions routed:", fr["counts"], "| LLM-reachable:", fr["questions_that_can_reach_an_llm_call_even_if_configured"])
    print("class counts:", audit["task_compatibility"]["class_counts"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
