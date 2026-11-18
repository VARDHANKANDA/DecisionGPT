"""Render research/llm_evaluation/ARCHITECTURE_AUDIT_2026-10-08.md from architecture_audit.json (so the tables cannot drift from the audit).

HISTORICAL: the prose in this renderer describes the OpenAI-era architecture (2026-10-08). The committed document carries a SUPERSEDED banner;
re-running this script would overwrite it. The current provider is TypeSafe AI Jev - see docs/JEV_INTEGRATION.md.
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "ARCHITECTURE_AUDIT_2026-10-08.md"


def main() -> None:
    a = json.loads((HERE / "architecture_audit.json").read_text(encoding="utf-8"))
    tc = a["task_compatibility"]
    dv = a["data_view"]
    rows = tc["table_asof"]
    cc = tc["class_counts"]
    fr = a["frozen_question_routing"]
    L: list[str] = []
    w = L.append

    w("# Architecture audit — what can legitimately be evaluated today (2026-10-08)")
    w("")
    w("*Dated addendum to `research/LLM_EVALUATION_PROTOCOL.md`, `research/llm_evaluation/PROTOCOL_ADDENDUM.md` and `DEVIATIONS.md`. Nothing is rewritten; the frozen task spec "
      "`tasks/tasks_v1.json` (sha256 `98f37037…`) is unchanged. No LLM was configured or called. No research results exist.*")
    w("")
    w("## Verdict")
    w("")
    w("**The current production DecisionGPT business-analytics chat path is not LLM-powered.** It is a fixed-intent keyword router that dispatches to hand-written handlers which query the "
      "database and build the answer text themselves. When a provider is configured, an LLM is called in exactly four chat intents (`why_kpi_fell`, `price_change_advice`, "
      "`marketing_change_advice`, `what_focus`) and only to *rephrase an already-computed template answer*. **None of the 27 frozen analytics questions can reach an LLM call, even with a provider configured** "
      "(shown by an AST scan and by a behavioural test that counts calls to the LLM client).")
    w("")
    w("- **Target A — current production chat (exists):** a deterministic router + template system. It can be evaluated today without any LLM, and must be described as exactly that.")
    w("- **Target B — an LLM-powered DecisionGPT analytics path (does not exist):** the other production LLM paths are goal-sentence parsing (`goal_service → LLMService.parse_goal`, structure extraction) and decision narration "
      "(`decision_service → evaluate_agent / generate_strategy_explanation`). They are reachable production code, but neither answers analytics questions. No unused or experimental LLM Q&A implementation exists "
      "(a repository-wide scan finds no other LLM call site). The research tool-use baseline is a research adapter, **not** DecisionGPT.")
    w("")
    w("**Outcome 3 applies:** *DecisionGPT's current production chat path is not currently LLM-powered, so a real-LLM evaluation of the actual production system cannot yet be performed.* "
      "The harness stays ready; it must not be used to make an adapter look like the product.")
    w("")
    w("## 1. Production chat architecture (traced from code)")
    w("")
    for i, step in enumerate(a["chat_path"], 1):
        w(f"{i}. {step}")
    w("")
    w("| Question | Component |")
    w("|---|---|")
    for k, v in a["components"].items():
        w(f"| {k.replace('_', ' ')} | {v} |")
    w("")
    w("## 2. LLM architecture")
    w("")
    w("`LLMService` (facade) → `LLMClient` (OpenAI-style `/chat/completions` or Anthropic `/v1/messages`). Provider/key/model/base URL come from `LLM_*` settings; the model defaults in code (`gpt-4o-mini` / `claude-sonnet-4-20250514`) if unset. "
      "Temperature is hard-coded 0, there is no seed parameter, retries use tenacity (3 attempts, exponential backoff), the default timeout is 30 s, **response token usage is discarded**, and **every `LLMService` method swallows LLM errors and silently falls back to the template** — "
      "an LLM failure is invisible in the answer (the evaluation recorder measures calls from outside; production is unchanged).")
    w("")
    w("| Call site (production) | Function | Method |")
    w("|---|---|---|")
    for s in a["llm_call_sites_in_production_code"]:
        w(f"| `{s['file'].replace('backend/app/', '')}:{s['line']}` | `{s['function']}` | `{s['method']}` |")
    w("")
    w("| Chat intent | Handler | LLM when configured |")
    w("|---|---|---|")
    for i, m in a["chat_intents"].items():
        w(f"| {i} | {m['handler']} | {'yes — ' + m['llm_role'] if m['invokes_llm_when_configured'] else 'no'} |")
    w("")
    w("The LLM never routes, interprets dates, retrieves data or computes numbers.")
    w("")
    w("## 3. Why 24 of the 27 frozen questions fail")
    w("")
    counts = ", ".join(f"{k}: {v}" for k, v in fr["counts"].items())
    legend = "; ".join(f"{k} = {v}" for k, v in tc["cause_legend"].items())
    w(f"The router recognises {fr['n_total'] - fr['n_unrecognized']}/{fr['n_total']} ({counts}). Cause legend: {legend}.")
    w("")
    w("- **B/D/F — no intent, no date parsing, no aggregation:** the router has no month/date vocabulary at all; handlers use fixed trailing windows. Absolute-window sums, % changes, daily extremes, weekday groupings and distinct counts have no intent.")
    w("- **G — recognised but incompatible semantics (C01, C02, C03):** `top_products` ranks by *revenue* over a fixed trailing 30-day window ([today−30, today], inclusive) and ignores the metric and dates in the question. It is not a phrasing problem.")
    w("- **E — missing field (E01–E04):** the production sales schema has no GST column.")
    w("- **C/F — missing aggregation (F02):** no production function returns daily unit totals.")
    w("")
    w("## 4. 27-task compatibility classification (frozen tasks, unmodified)")
    w("")
    defs = "; ".join(f"**{k}** {v}" for k, v in tc["class_definitions"].items())
    w(f"Classes: {defs}.")
    w("")
    w(f"Counts under the primary evaluation clock (2025-03-31): `{cc['asof']}`. Under the real clock: `{cc['realclock']}` — the one Class A task is **C02**, answerable only by coincidence "
      "(the handler's “nothing in the last 30 days” fallback ranks all sales by revenue, and the data span equals the asked window).")
    w("")
    w("| task | track | router | class | required capability | nearest existing block | causes | note |")
    w("|---|---|---|---|---|---|---|---|")
    for r in rows:
        blk = (r["nearest_existing_block"] or "—").split(" — ")[0]
        intent = r["router_intent"] if r["router_recognizes"] else "unrecognized"
        w(f"| {r['task_id']} | {r['track']} | {intent} | {r['class']} | {r['required_capability']} | {blk} | {','.join(r['causes'])} | {r['note'] or ''} |")
    w("")
    w("Class D (invalid/ambiguous) is empty: the ground-truth engine refuses tie-ambiguous tasks and all 27 compute. "
      "`tasks/execution_subsets_v1.json` lists these classes by task id; it references the frozen ids and is too small to evaluate anything — no evaluation is planned on it.")
    w("")
    w("## 5. The evaluation-date problem")
    w("")
    chat_sites = [s for s in a["date_today_call_sites"] if s["file"].split("/")[-1] in ("assistant_service.py", "kpi_service.py", "churn_service.py", "breakdown_service.py")]
    sites = ", ".join(f"`{s['file'].split('/')[-1]}::{s['function']}`" for s in chat_sites)
    w(f"`date.today()` enters the chat path at: {sites}. Run on another day, the same historical question gets a different window (the real clock in 2026 makes every “last 30 days” window empty). "
      "Windows are inclusive on both ends ([today−N, today], N+1 days; `period_over_period` compares N+1 days with the N days before), so “30 days” is 31 days.")
    w("")
    w("**Current research-only mechanism:** `DecisionGPTSystem.set_clock(date)` temporarily replaces the `date` name inside four modules (`CLOCK_PATCHED_MODULES`); tests prove every chat-reachable module with a `date.today()` site is covered and that the real clock is restored. It works but depends on module attribute names.")
    w("")
    w("**Smallest safe production change (documented, NOT implemented):** add `app/core/clock.py` with `def today() -> date: return _override or date.today()` and replace the chat-related `date.today()` call sites with `clock.today()`. "
      "With no override set the behaviour is byte-identical; the evaluation harness sets the override to 2025-03-31. Guard: honour the override only when an explicit environment variable is set and log it, so a production process can never be silently frozen. "
      "Until then the monkey-patch plus the scan-based tests are the safeguard.")
    w("")
    w("## 6. Evaluation data view (conservation audit)")
    w("")
    w(f"Label: *{dv['label']}*. Rules: whole-quantity lines (`sales.quantity` is an integer), amount agrees with a printed column, then merge lines sharing (date, product, unit price) by summing quantity (production rejects duplicate rows).")
    w("")
    fq = dv["rejected_fractional_quantity"]
    w("| quantity | value |")
    w("|---|---|")
    w(f"| original processed lines | {dv['original_processed_lines']:,} |")
    w(f"| original revenue (₹) | {dv['original_revenue_inr']:,.2f} |")
    w(f"| original quantity (mixed units: pieces and kg) | {dv['original_quantity_mixed_units']:,} |")
    w(f"| **rejected: fractional quantity** (production ingestion cannot represent it) | {fq['lines']:,} lines ({fq['pct_of_lines']}%), ₹{fq['revenue_inr']:,.2f} ({fq['pct_of_revenue']}% of revenue), quantity {fq['quantity']:,} |")
    w(f"| rejected: printed amount disagrees | {dv['rejected_amount_disagreement']['lines']} line, ₹{dv['rejected_amount_disagreement']['revenue_inr']:,.2f} |")
    w(f"| whole-quantity lines retained | {dv['whole_quantity_lines_retained']:,} lines, ₹{dv['whole_quantity_revenue_inr']:,.2f}, quantity {dv['whole_quantity_lines_quantity']:,} |")
    w(f"| evaluation view rows after merge | {dv['view_rows_after_merge']:,} ({dv['lines_merged_away']:,} lines merged away) |")
    w(f"| view revenue (₹) / quantity | {dv['view_revenue_inr']:,.2f} / {dv['view_quantity']:,} |")
    w(f"| **conservation across the merge** | revenue exactly conserved: {dv['revenue_conserved_by_merge']}; quantity exactly conserved: {dv['quantity_conserved_by_merge']}; max difference per merged group: ₹{dv['max_abs_difference_per_merged_group_inr']} |")
    w(f"| retained: rows / lines represented / revenue | {dv['pct_original_rows_in_view']}% of original rows (rows are merged) / {dv['pct_original_lines_represented']}% of lines / **{dv['pct_original_revenue_retained']}% of revenue** |")
    w("")
    w(f"Identity: {dv['identity']}. **The production ingestion contract cannot represent fractional (weighed) quantities; they are excluded explicitly, not silently, and any report must say the view covers {dv['pct_original_revenue_retained']}% of the register's revenue.**")
    w("")
    w("## 7. GST track")
    w("")
    w("GST is absent from the production schema, so production DecisionGPT cannot answer GST questions. E01–E04 stay a *supplementary dataset-level* track: they would need the approved source dataset and their own separately named system path, "
      "are never mixed into primary-track metrics, and must never be reported as production-DecisionGPT answers (tests enforce the separation).")
    w("")
    w("## 8. Baseline design")
    w("")
    w("The planned baseline (same LLM client + sandboxed pandas) is **not a simpler baseline**: it can run arbitrary computation, which the router cannot. It gets the same data fields as the production database, plus column descriptions, "
      "five sample rows, the covered date range and one repair attempt — documentation DecisionGPT does not receive (and GST only on the supplementary track). It is therefore only valid when **framed as a tool-use reference** (what an LLM with direct data access can do), "
      "not as “the same system without DecisionGPT's orchestration”. Runs now label it `Reference tool-use system … NOT a simpler baseline, NOT DecisionGPT` (`SYSTEM_LABELS`). No prompt or tolerance was changed.")
    w("")
    w("## 9. Exact conditions required before any execution")
    w("")
    w("1. An analytics question-answering path **in DecisionGPT** that actually calls an LLM (production request → DecisionGPT → LLM API call → DecisionGPT answer). Today none exists; building one is a product decision and is out of scope for this evaluation work.")
    w("2. `LLM_PROVIDER`, `LLM_API_KEY`, `LLM_MODEL` set to a real provider (a separate, second blocker).")
    w("3. The evaluation clock injected (research mechanism above, or the documented `clock.today()` change).")
    w("4. The system under test named exactly in every report; the tool-use reference reported as a reference.")
    w("5. If a deterministic evaluation of Target A is wanted instead, it must be labelled “fixed-intent router/template system (no LLM)” and cannot answer the research question about LLM-powered DecisionGPT.")
    w("")
    w("*Regenerate: `python -m research.llm_evaluation.audit.architecture` then `python -m research.llm_evaluation.audit.render_audit_doc`. The audit is pinned by `tests/unit/test_llm_eval_architecture.py`.*")
    OUT.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
