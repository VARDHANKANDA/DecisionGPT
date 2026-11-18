# Architecture audit — what can legitimately be evaluated today (2026-10-08)

> **SUPERSEDED / HISTORICAL (2026-10-13).** This document describes the OpenAI-era architecture as of 2026-10-08. The provider is now TypeSafe AI Jev (typed decisions only; see `docs/JEV_INTEGRATION.md` and `DEVIATIONS.md` entry 8). Do not re-run `render_audit_doc` over this file: it would replace this record with the current audit.

*Dated addendum to `research/LLM_EVALUATION_PROTOCOL.md`, `research/llm_evaluation/PROTOCOL_ADDENDUM.md` and `DEVIATIONS.md`. Nothing is rewritten; the frozen task spec `tasks/tasks_v1.json` (sha256 `98f37037…`) is unchanged. No LLM was configured or called. No research results exist.*

## Verdict

**The current production DecisionGPT business-analytics chat path is not LLM-powered.** It is a fixed-intent keyword router that dispatches to hand-written handlers which query the database and build the answer text themselves. When a provider is configured, an LLM is called in exactly four chat intents (`why_kpi_fell`, `price_change_advice`, `marketing_change_advice`, `what_focus`) and only to *rephrase an already-computed template answer*. **None of the 27 frozen analytics questions can reach an LLM call, even with a provider configured** (shown by an AST scan and by a behavioural test that counts calls to the LLM client).

- **Target A — current production chat (exists):** a deterministic router + template system. It can be evaluated today without any LLM, and must be described as exactly that.
- **Target B — an LLM-powered DecisionGPT analytics path (does not exist):** the other production LLM paths are goal-sentence parsing (`goal_service → LLMService.parse_goal`, structure extraction) and decision narration (`decision_service → evaluate_agent / generate_strategy_explanation`). They are reachable production code, but neither answers analytics questions. No unused or experimental LLM Q&A implementation exists (a repository-wide scan finds no other LLM call site). The research tool-use baseline is a research adapter, **not** DecisionGPT.

**Outcome 3 applies:** *DecisionGPT's current production chat path is not currently LLM-powered, so a real-LLM evaluation of the actual production system cannot yet be performed.* The harness stays ready; it must not be used to make an adapter look like the product.

## 1. Production chat architecture (traced from code)

1. frontend chat page -> api.chat() -> POST /api/v1/businesses/{id}/chat
2. api/v1/endpoints/assistant.py: chat() -> assistant_service.answer_question(db, business_id, message)
3. assistant_service.classify_intent(text): keyword rules (no LLM, no date parsing)
4. per-intent handler queries the business tables via SQLAlchemy / analytics services and builds the answer text (f-strings or LLMService template)
5. response + memory log row

| Question | Component |
|---|---|
| receives question | api/v1/endpoints/assistant.py::chat -> assistant_service.answer_question |
| determines intent | assistant_service.classify_intent (substring keyword rules) |
| determines date ranges | nobody parses dates from the question; handlers use fixed trailing windows relative to date.today() |
| queries business data | handlers: _product_revenue, kpi_service.*, forecast/churn/digital_twin services |
| constructs answer | handler f-strings, or LLMService.generate_business_response (template; LLM rephrase only if configured) |

## 2. LLM architecture

`LLMService` (facade) → `LLMClient` (OpenAI-style `/chat/completions` or Anthropic `/v1/messages`). Provider/key/model/base URL come from `LLM_*` settings; the model defaults in code (`gpt-4o-mini` / `claude-sonnet-4-20250514`) if unset. Temperature is hard-coded 0, there is no seed parameter, retries use tenacity (3 attempts, exponential backoff), the default timeout is 30 s, **response token usage is discarded**, and **every `LLMService` method swallows LLM errors and silently falls back to the template** — an LLM failure is invisible in the answer (the evaluation recorder measures calls from outside; production is unchanged).

| Call site (production) | Function | Method |
|---|---|---|
| `services/assistant_service.py:99` | `_why_kpi_fell` | `generate_business_response` |
| `services/assistant_service.py:114` | `_simulation_advice` | `generate_business_response` |
| `services/assistant_service.py:148` | `_what_focus` | `generate_business_response` |
| `services/decision_service.py:409` | `analyze_goal` | `generate_strategy_explanation` |
| `services/decision_service.py:403` | `analyze_goal` | `evaluate_agent` |
| `services/decision_service.py:741` | `explain_decision` | `evaluate_agent` |
| `services/goal_service.py:56` | `parse_and_validate_goal` | `parse_goal` |

| Chat intent | Handler | LLM when configured |
|---|---|---|
| why_kpi_fell | _why_kpi_fell | yes — rephrases an already-computed template answer |
| price_change_advice | _simulation_advice | yes — rephrases an already-computed template answer |
| marketing_change_advice | _simulation_advice | yes — rephrases an already-computed template answer |
| why_recommend | _why_recommend | no |
| what_focus | _what_focus | yes — rephrases an already-computed template answer |
| top_products | _top_products | no |
| improving_worsening | _improving_worsening | no |
| sales_forecast | _sales_forecast | no |
| customer_churn | _customer_churn | no |
| valuable_customers | _valuable_customers | no |
| unrecognized | (fixed refusal text) | no |

The LLM never routes, interprets dates, retrieves data or computes numbers.

## 3. Why 24 of the 27 frozen questions fail

The router recognises 3/27 (unrecognized: 24, top_products: 3). Cause legend: A = unsupported natural-language phrasing; B = missing intent; C = missing backend capability; D = missing date handling; E = missing data field; F = unsupported aggregation; G = production architecture limitation (handler semantics fixed); H = evaluation task incompatible with current production behaviour; I = other.

- **B/D/F — no intent, no date parsing, no aggregation:** the router has no month/date vocabulary at all; handlers use fixed trailing windows. Absolute-window sums, % changes, daily extremes, weekday groupings and distinct counts have no intent.
- **G — recognised but incompatible semantics (C01, C02, C03):** `top_products` ranks by *revenue* over a fixed trailing 30-day window ([today−30, today], inclusive) and ignores the metric and dates in the question. It is not a phrasing problem.
- **E — missing field (E01–E04):** the production sales schema has no GST column.
- **C/F — missing aggregation (F02):** no production function returns daily unit totals.

## 4. 27-task compatibility classification (frozen tasks, unmodified)

Classes: **A** answerable through the current production chat path with correct semantics; **B1** ONE existing production call, parameters only, returns the quantity (not reachable via chat); **B2** existing building block + trivial arithmetic (sum/count/argmax/mean/%/share/weekday); not reachable via chat; **C** no existing building block can supply it (missing field or aggregation); **D** invalid/ambiguous for the dataset (none: the ground-truth engine refuses tie-ambiguous tasks).

Counts under the primary evaluation clock (2025-03-31): `{'B1': 3, 'B2': 19, 'C': 5}`. Under the real clock: `{'A': 1, 'B1': 2, 'B2': 19, 'C': 5}` — the one Class A task is **C02**, answerable only by coincidence (the handler's “nothing in the last 30 days” fallback ranks all sales by revenue, and the data span equals the asked window).

| task | track | router | class | required capability | nearest existing block | causes | note |
|---|---|---|---|---|---|---|---|
| A01 | primary | unrecognized | B2 | revenue sum, absolute window 1-31 Jan | services/assistant_service._product_revenue(start,end) | B,D,F |  |
| A02 | primary | unrecognized | B2 | revenue sum, absolute window 1-28 Feb | services/assistant_service._product_revenue(start,end) | B,D,F |  |
| A03 | primary | unrecognized | B1 | revenue sum over the whole data span | analytics/kpi_service.compute_kpis(period_days) | B,D | kpis(period_days=89) equals Jan 1-Mar 31 only under the evaluation clock 2025-03-31 |
| A04 | primary | unrecognized | B2 | unit sum, absolute window March | services/assistant_service._product_revenue(start,end) | B,D,F |  |
| A05 | primary | unrecognized | B2 | unit sum, absolute window February | services/assistant_service._product_revenue(start,end) | B,D,F |  |
| B01 | primary | unrecognized | B2 | % change between two absolute windows (Feb vs Jan) | services/assistant_service._product_revenue(start,end) | B,D,F |  |
| B02 | primary | unrecognized | B2 | % change between two absolute windows (Mar vs Feb) | services/assistant_service._product_revenue(start,end) | B,D,F | period_over_period uses equal-length trailing windows, which do not align with calendar months |
| B03 | primary | unrecognized | B2 | argmax of daily revenue | analytics/kpi_service.revenue_trend(days) | B,F |  |
| B04 | primary | unrecognized | B2 | argmin of daily revenue over days with sales | analytics/kpi_service.revenue_trend(days) | B,F |  |
| B05 | primary | unrecognized | B2 | % change between two absolute half-month windows | services/assistant_service._product_revenue(start,end) | B,D,F |  |
| C01 | primary | top_products | B2 | argmax units by product, absolute window Feb | services/assistant_service._product_revenue(start,end) | G,D,F | router -> top_products, but that handler ranks by REVENUE over a fixed trailing 30-day window and ignores the dates/metric in the question |
| C02 | primary | top_products | B1 | top-3 products by revenue over the whole data span | analytics/breakdown_service.top_products(limit) | G | router -> top_products. Under the evaluation clock the handler answers for March only; under the real clock its 'no sales in the last 30 days' fallback ranks ALL sales by revenue, which coincidentally equals the task because the data span is exactly the asked window |
| C03 | primary | top_products | B2 | top-3 products by UNITS, absolute window March | services/assistant_service._product_revenue(start,end) | G,F | router -> top_products, but the handler ranks by revenue, not units |
| C04 | primary | unrecognized | B1 | units of one product over the whole data span | analytics/breakdown_service.top_products(limit) | B | single call of GET /analytics/products?limit>=2 returns units_sold; equals the asked window because the data span is exactly Jan-Mar |
| C05 | primary | unrecognized | B2 | compare units of two products | analytics/breakdown_service.top_products(limit) | B,F |  |
| C06 | primary | unrecognized | B2 | one product's revenue / total revenue | analytics/breakdown_service.top_products(limit) | B,F |  |
| D01 | primary | unrecognized | B2 | weekday with the largest revenue | analytics/kpi_service.revenue_trend(days) | B,F |  |
| D02 | primary | unrecognized | B2 | weekday with the smallest revenue | analytics/kpi_service.revenue_trend(days) | B,F |  |
| D03 | primary | unrecognized | B2 | revenue summed over Sundays | analytics/kpi_service.revenue_trend(days) | B,F |  |
| D04 | primary | unrecognized | B2 | mean daily revenue over days with sales | analytics/kpi_service.revenue_trend(days) | B,F |  |
| F01 | primary | unrecognized | B2 | count of distinct products sold in January | services/assistant_service._product_revenue(start,end) | B,D,F |  |
| F02 | primary | unrecognized | C | mean DAILY UNITS in March | — | C,F | no production function returns daily unit totals (revenue_trend returns revenue only) |
| F03 | primary | unrecognized | B2 | largest daily revenue | analytics/kpi_service.revenue_trend(days) | B,F |  |
| E01 | supplementary | unrecognized | C | revenue by GST slab | — | E | the production sales schema has no GST column |
| E02 | supplementary | unrecognized | C | share of revenue by GST slab | — | E | same |
| E03 | supplementary | unrecognized | C | share of revenue by GST slab | — | E | same |
| E04 | supplementary | unrecognized | C | GST slab with the most revenue | — | E | same |

Class D (invalid/ambiguous) is empty: the ground-truth engine refuses tie-ambiguous tasks and all 27 compute. `tasks/execution_subsets_v1.json` lists these classes by task id; it references the frozen ids and is too small to evaluate anything — no evaluation is planned on it.

## 5. The evaluation-date problem

`date.today()` enters the chat path at: `breakdown_service.py::customer_summary`, `churn_service.py::predict_churn`, `kpi_service.py::period_over_period`, `kpi_service.py::revenue_trend`, `kpi_service.py::compute_kpis`, `assistant_service.py::_top_products`, `assistant_service.py::_improving_worsening`, `assistant_service.py::_sales_forecast`. Run on another day, the same historical question gets a different window (the real clock in 2026 makes every “last 30 days” window empty). Windows are inclusive on both ends ([today−N, today], N+1 days; `period_over_period` compares N+1 days with the N days before), so “30 days” is 31 days.

**Current research-only mechanism:** `DecisionGPTSystem.set_clock(date)` temporarily replaces the `date` name inside four modules (`CLOCK_PATCHED_MODULES`); tests prove every chat-reachable module with a `date.today()` site is covered and that the real clock is restored. It works but depends on module attribute names.

**Smallest safe production change (documented, NOT implemented):** add `app/core/clock.py` with `def today() -> date: return _override or date.today()` and replace the chat-related `date.today()` call sites with `clock.today()`. With no override set the behaviour is byte-identical; the evaluation harness sets the override to 2025-03-31. Guard: honour the override only when an explicit environment variable is set and log it, so a production process can never be silently frozen. Until then the monkey-patch plus the scan-based tests are the safeguard.

## 6. Evaluation data view (conservation audit)

Label: *evaluation-compatible view derived from the approved Indian POS dataset (NOT the original dataset)*. Rules: whole-quantity lines (`sales.quantity` is an integer), amount agrees with a printed column, then merge lines sharing (date, product, unit price) by summing quantity (production rejects duplicate rows).

| quantity | value |
|---|---|
| original processed lines | 94,290 |
| original revenue (₹) | 5,567,256.65 |
| original quantity (mixed units: pieces and kg) | 151,377.4 |
| **rejected: fractional quantity** (production ingestion cannot represent it) | 34,045 lines (36.11%), ₹1,212,310.49 (21.78% of revenue), quantity 19,829.4 |
| rejected: printed amount disagrees | 1 line, ₹210.00 |
| whole-quantity lines retained | 60,244 lines, ₹4,354,736.16, quantity 131,545 |
| evaluation view rows after merge | 30,293 (29,951 lines merged away) |
| view revenue (₹) / quantity | 4,354,736.16 / 131,545 |
| **conservation across the merge** | revenue exactly conserved: True; quantity exactly conserved: True; max difference per merged group: ₹0.0 |
| retained: rows / lines represented / revenue | 32.13% of original rows (rows are merged) / 63.89% of lines / **78.22% of revenue** |

Identity: for lines sharing (date, product, unit price p): sum(q_i * p) = p * sum(q_i), so merging by summing quantity conserves revenue; verified numerically above. **The production ingestion contract cannot represent fractional (weighed) quantities; they are excluded explicitly, not silently, and any report must say the view covers 78.22% of the register's revenue.**

## 7. GST track

GST is absent from the production schema, so production DecisionGPT cannot answer GST questions. E01–E04 stay a *supplementary dataset-level* track: they would need the approved source dataset and their own separately named system path, are never mixed into primary-track metrics, and must never be reported as production-DecisionGPT answers (tests enforce the separation).

## 8. Baseline design

The planned baseline (same LLM client + sandboxed pandas) is **not a simpler baseline**: it can run arbitrary computation, which the router cannot. It gets the same data fields as the production database, plus column descriptions, five sample rows, the covered date range and one repair attempt — documentation DecisionGPT does not receive (and GST only on the supplementary track). It is therefore only valid when **framed as a tool-use reference** (what an LLM with direct data access can do), not as “the same system without DecisionGPT's orchestration”. Runs now label it `Reference tool-use system … NOT a simpler baseline, NOT DecisionGPT` (`SYSTEM_LABELS`). No prompt or tolerance was changed.

## 9. Exact conditions required before any execution

1. An analytics question-answering path **in DecisionGPT** that actually calls an LLM (production request → DecisionGPT → LLM API call → DecisionGPT answer). Today none exists; building one is a product decision and is out of scope for this evaluation work.
2. `LLM_PROVIDER`, `LLM_API_KEY`, `LLM_MODEL` set to a real provider (a separate, second blocker).
3. The evaluation clock injected (research mechanism above, or the documented `clock.today()` change).
4. The system under test named exactly in every report; the tool-use reference reported as a reference.
5. If a deterministic evaluation of Target A is wanted instead, it must be labelled “fixed-intent router/template system (no LLM)” and cannot answer the research question about LLM-powered DecisionGPT.

*Regenerate: `python -m research.llm_evaluation.audit.architecture` then `python -m research.llm_evaluation.audit.render_audit_doc`. The audit is pinned by `tests/unit/test_llm_eval_architecture.py`.*
