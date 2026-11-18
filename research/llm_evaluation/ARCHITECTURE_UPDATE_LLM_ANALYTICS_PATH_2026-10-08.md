# Architecture update — an LLM analytics path now exists in DecisionGPT (2026-10-08)

*Dated addendum. It supersedes the **conclusion** of `ARCHITECTURE_AUDIT_2026-10-08.md` ("the production chat is not LLM-powered; Outcome 3") for the current code, and leaves that document intact as the record of the state before this change. The frozen task spec `tasks/tasks_v1.json` (sha256 `98f37037…`) is unchanged. No real LLM was configured or called. **No research results exist.***

## What changed

The business chat (`POST /businesses/{id}/chat`) now has two paths:

| | A. LLM analytics path (new) | B. Legacy deterministic router (unchanged) |
|---|---|---|
| used when | an LLM provider is configured **and** `ANALYTICS_LLM_ENABLED` is not false | no provider, kill switch off, or the LLM step fails |
| flow | question → **LLM interpreter** → strict structured request → validation → **deterministic query engine** → verified result → deterministic FACT text (+ guarded LLM explanation) → answer | `classify_intent` keyword rules → per-intent handler → template (LLM rephrases 4 intents) |
| response field | `path = "llm_analytics"` | `path = "legacy_router"` (plus a `notice` when a failed LLM step caused the fallback) |

> **The LLM determines what the user is asking; the deterministic DecisionGPT data layer determines what the data says.**

Code: `app/core/clock.py` (scoped reference date), `app/schemas/analytics_query.py` (closed request vocabulary), `app/analytics/query_engine.py` (dates, product matching, ORM execution), `app/analytics/query_presenter.py` (FACT text), `app/services/analytics_interpreter_service.py` (prompt + strict parse), `app/services/analytics_answer_service.py` (numeric / causal / markup guards), `app/services/analytics_chat_service.py` (orchestration + audit), `LLMService.call_json` (typed failures), `assistant_service.answer_question` (path choice). Design notes: `docs/LLM_ANALYTICS_PATH.md`.

## What the LLM does and does not do

* **Does:** classify the question (`analytics_query` / `clarification` / `unsupported` / `legacy`), choose an allowed operation and metric, express the period as a symbolic `DateSpec`, name products as the owner wrote them; optionally write ≤2 sentences of interpretation and 1 suggestion over the *already verified* facts.
* **Does not:** see rows, product lists or other businesses' data; write SQL or code (the schema has no such field and rejects extra fields); compute or supply any number; resolve dates (the engine does, from the clock); pick a table or a tenant (`business_id` comes from the authorised route and is applied by the engine on every query). Any LLM text containing a number that is not in the verified facts, a causal phrase, a link or markup is **dropped**; the deterministic FACT sentence always stands alone.

## Date handling

`app/core/clock.py::today()` is `date.today()` unless a block pins it with `clock.reference_date(d)` (a `ContextVar`: scoped, logged at WARNING, never process-wide, never used by production code). The four chat-reachable modules (`kpi_service`, `churn_service`, `breakdown_service`, `assistant_service`) now call `clock.today()`; the research adapter uses `reference_date(2025-03-31)` instead of monkey-patching `datetime.date`. Relative dates are symbolic (`{"kind":"calendar","unit":"month","offset":0}`) and resolved by the engine; the resolved range and any assumption ("you didn't name a year, so I used February 2025") appear in the answer and in the audit record. Trailing windows are exactly N days (the legacy windows are N+1).

## Frozen-task readiness (technical, not a result)

`audit/llm_path_dryrun.py` (output `audit/llm_path_dryrun.json`, test `tests/integration/test_analytics_llm_trace.py`) pushes all 27 frozen questions through the real route, ingestion and engine with a **mocked** interpreter that supplies only the structured interpretation:

* 27 / 27 flow through the LLM analytics path (27 interpreter calls, 23 explainer calls).
* 23 / 23 primary questions get a verified engine answer that agrees with the independent pandas ground-truth engine (this validates the engine, not a model).
* 4 / 4 GST questions are refused as unsupported (the production schema has no GST field) — they stay a separate supplementary track.
* **NOT RESEARCH RESULTS.** A real model may interpret differently; that is what the later evaluation will measure.

## What the real evaluation will and will not measure

Because the numeric sentence is produced by the engine, a real-LLM run of this path measures **question understanding and request construction** (operation, metric, period, filters, refusals/clarifications) plus end-to-end behaviour — not the model's arithmetic. Report it as exactly that. The tool-use pandas system remains a *reference*, not a simpler baseline and not DecisionGPT. Attempts answered by the legacy fallback carry `path=legacy_router`; the runner records `decisiongpt_answer_paths` and `decisiongpt_attempts_not_served_by_llm_analytics_path` in the run metadata and those attempts must be reported, not silently counted as LLM answers.

## Remaining conditions before execution

1. One real provider/model configured locally (`LLM_PROVIDER`, `LLM_API_KEY`, `LLM_MODEL`), not committed.
2. A separate evaluation-readiness check (smoke on a handful of questions with the real provider, token/latency capture, fallback rate) before the frozen experiment runs.
3. Known limitations to disclose: each analytics chat is two LLM calls; the provider client retries 3× with a 30 s timeout (worst case ≈ 90 s before fallback); weekday rankings are totals per weekday (not per-occurrence means); `orders` counts sales records (rows), which on the merged evaluation view are not bills; `mean_per_calendar_day` averages over the covered part of the period; the explanation guards are lexical (numbers, causal phrases, markup), so an LLM sentence can still be vague or unhelpful, never numerically wrong.

Status: **NOT READY FOR REAL LLM EVALUATION — IMPLEMENTATION COMPLETE, PROVIDER NOT CONFIGURED.**
