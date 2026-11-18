# AGENTS.md — Working Rules for DecisionGPT

This file defines hard boundaries that apply across the whole codebase (backend
services, ML pipeline, and the multi-agent decision engine). It exists so that
contributors — human or AI — don't accidentally reintroduce fabricated numbers
into a research-integrity-sensitive product.

## LLM boundary (applies everywhere an LLM is called)

The AI provider is **OpenAI** (official SDK, Responses API), used only via `LLMService` (`backend/app/services/llm_service.py`,
`openai_client.py`). It is allowed to:
- classify a business question into the closed vocabulary of the analytics query schema (operation, metric, grouping, route) through a
  strict JSON schema — the values (periods, product names, limits) are extracted by deterministic code, never by the model,
- classify a goal sentence into one supported objective (target and horizon stay rule-based; never invent KPI values),
- restate ALREADY VERIFIED facts in one or two sentences, shown only if it passes `analytics_answer_service.validate_explanation`
  (deterministic: no repeated sentence, no near-copy of a fact or caveat, no new number, no causal claim, no advice, no unsupported term;
  `ANALYTICS_EXPLAIN_ENABLED=false` disables the request entirely),

It is **not** used for forecasts, scores, strategies or agent reviews: those are deterministic.
Questions about evaluation results in chat (metrics, accuracy, baselines, horizons, benchmarks, validation) do not reach the model at all: they are
recognised by rules and answered from `evaluation_console_service` and the metric registry by `evaluation_chat_service.py`, so no number in such an
answer can come from, or be changed by, an LLM. Registered-model and benchmark results are shown only to callers who could open the Research Console. There is no other AI provider and no
silent fallback to one; a failure is labelled and the rule-based assistant answers.

The LLM is **never** the source of truth for:
- forecasts, KPI values, or churn probabilities (come from trained models / DB),
- causal edges or causal effect sizes (come from the causal module),
- Digital Twin simulation outputs (come from the simulation transition function),
- agent scores/confidence (come from the documented scoring formula),
- research/experiment metrics (come from recorded experiment runs only).

If `OPENAI_API_KEY` is unset, the system must still function in deterministic demo
mode — every module needs a non-LLM fallback path.

## No fabrication

- Never hard-code example numbers (e.g. "marketing +10% = revenue +8%") as if
  they were real outputs. Examples in docs are illustrative only.
- If a feature lacks sufficient evidence/data, return an explicit
  insufficient-evidence state — do not guess.
- Research Console values must come from stored `experiment_runs` /
  `models.metrics_json` rows, never from prose written by hand.

## Data isolation

Every business-owned table is scoped by `business_id`. Every query must filter
on it. Platform/research datasets (`data/platform/**`) are never exposed
through SME-facing endpoints or UI.

## Traceability

Any code that produces a `decision` must be able to answer: which goal, which
business state, which model versions, which causal graph version, which
strategy, which simulation, which agent runs produced it. See
`docs/RESEARCH_TRACEABILITY.md`.
