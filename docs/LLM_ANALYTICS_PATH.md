# AI analytics path (business chat)

> **Provider update (2026-10-14):** the active AI provider is now OpenAI (`docs/OPENAI_INTEGRATION.md`). Where this page says Jev or typed decisions, read "the OpenAI model classifying into the same closed labels"; the architecture (classification -> deterministic extraction -> validated request -> deterministic engine) is unchanged. Earlier Jev experiment runs remain as historical records.

> **Updated 2026-10-13:** the provider is now TypeSafe AI **Jev** (typed decisions only) — see `docs/JEV_INTEGRATION.md`. Where this document says "LLM interpreter" read "one Jev request of typed questions plus deterministic extraction"; there is no LLM explanation step any more (answers are deterministic templates) and no retries.

Added 2026-10-08. Complements `docs/AI_MODULE_SPECIFICATION.md` and `AGENTS.md` ("LLM boundary"): the LLM *parses a natural-language question into a validated structured request* and *explains already-computed results*; it is never the source of a number.

```
Owner question
  └─ POST /businesses/{id}/chat                      (verify_business_access: authenticated owner only)
      └─ assistant_service.answer_question
          ├─ analytics_chat_service.try_answer       (only if LLM provider configured and ANALYTICS_LLM_ENABLED)
          │    ├─ analytics_interpreter_service      LLM → JSON → strict `Interpretation` (extra fields rejected)
          │    │     route: analytics_query | clarification | unsupported | legacy
          │    ├─ query_engine.run_query             dates from app.core.clock, products matched inside the business,
          │    │                                      ORM queries always filtered by business_id → VerifiedResult
          │    ├─ query_presenter.facts              deterministic FACT sentence(s) + assumptions/caveats
          │    └─ analytics_answer_service.explain   LLM interpretation/suggestion, kept only if every number is in the facts,
          │                                           no causal phrase, no markup/links; otherwise dropped
          └─ _legacy_answer                          fixed-intent router (fallback; response.path = "legacy_router")
```

## Request vocabulary (`app/schemas/analytics_query.py`)

`operation`: `aggregate` · `ranking` · `compare_periods` · `share_of_total`. `metric`: `revenue` · `units` · `orders` · `distinct_products` · `customers` · `profit` (only when products have `unit_cost`). `period`/`comparison_period` (`DateSpec`): `absolute` · `calendar` (day/week/month/quarter/year, relative offset or named) · `trailing` · `all_time`. Filters: `products` (names, matched within the business), `weekdays`. Ranking: `group_by` product/category/weekday/day/week/month, `direction`, `limit` ≤ 50. Statistic (aggregate): `total` · `mean_per_active_day` · `mean_per_calendar_day`. Anything else is rejected before execution.

## Guarantees (each pinned by tests in `tests/integration/test_analytics_llm_chat.py`, `tests/unit/test_analytics_query_*.py`)

* No raw SQL or code: the model has no field for it; new modules contain no `eval/exec/text()/.execute()` (AST test).
* Tenant isolation is enforced by the route guard and by the engine, never by the model; the LLM is not reached for unauthorised requests.
* Uploaded text (product names) is data: it never enters the instructions, and the interpreter is not shown product names at all.
* Unsupported/ambiguous/no-data cases produce explicit refusals or one clarification question; causal questions are not answered with a cause.
* Failures (not configured, timeout, provider error, malformed/invalid output) fall back to the legacy router, flagged `path=legacy_router` with a user-facing `notice`.
* Each LLM-path request stores an audit record (request id, reference date, structured request, validation result, tool, verified-result metadata, provider/model, latency, token usage when reported, explanation guard verdicts) in the chat memory row; logs carry ids and outcomes only (no question text, no secrets).

## Configuration

`TYPESAFE_API_KEY` (see `app/core/config.py`) enables it; `ANALYTICS_LLM_ENABLED=false` switches the path off. With no provider the product behaves exactly as before.

## Known limitations

One Jev request per question (no retries; a 15 s timeout bounds any fallback delay); `Sale.quantity` is an integer column (the engine itself carries decimals) so weighed/fractional quantities cannot be stored today; weekday rankings are totals, not per-occurrence means.
