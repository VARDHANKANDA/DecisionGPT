# AGENTS.md — Working Rules for DecisionGPT

This file defines hard boundaries that apply across the whole codebase (backend
services, ML pipeline, and the multi-agent decision engine). It exists so that
contributors — human or AI — don't accidentally reintroduce fabricated numbers
into a research-integrity-sensitive product.

## LLM boundary (applies everywhere an LLM is called)

The LLM (via `LLMService`, see `backend/app/services/llm_service.py`) is allowed to:
- parse natural-language goals into structured fields (never invent KPI values),
- generate explanations of results that already exist,
- write strategy/agent narrative language,
- power the chat assistant's phrasing.

The LLM is **never** the source of truth for:
- forecasts, KPI values, or churn probabilities (come from trained models / DB),
- causal edges or causal effect sizes (come from the causal module),
- Digital Twin simulation outputs (come from the simulation transition function),
- agent scores/confidence (come from the documented scoring formula),
- research/experiment metrics (come from recorded experiment runs only).

If `LLM_API_KEY` is unset, the system must still function in deterministic demo
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
