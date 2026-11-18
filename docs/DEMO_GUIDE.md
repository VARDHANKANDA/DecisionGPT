# Demonstration guide — the shortest reliable path

> **Provider update (2026-10-14):** the active AI provider is now OpenAI (`docs/OPENAI_INTEGRATION.md`). Where this page says Jev or typed decisions, read "the OpenAI model classifying into the same closed labels"; the architecture (classification -> deterministic extraction -> validated request -> deterministic engine) is unchanged. Earlier Jev experiment runs remain as historical records.

What each step shows, where the number comes from, and what is *not* claimed. Written 2026-10-14.

## Start

From the repository root (the backend finds `backend/.env` itself, whatever directory it is started from):

```
# backend (uses TYPESAFE_API_KEY from backend/.env when present; blank it to demo the rule-based mode)
PYTHONPATH=. DATABASE_URL=sqlite:///./backend/dev.db AUTH_ENABLED=true \
  backend/.venv/Scripts/python -m uvicorn app.main:app --app-dir backend --port 8000
# frontend
cd frontend && npm run dev
```

Local accounts are listed in the git-ignored `.local/dev_accounts.md`. The demo business is labelled **DEMO DATA** in the UI.

## Path (about 5 minutes)

| # | Where | Say | What backs it |
|---|---|---|---|
| 1 | `/` | What the product is, who it is for, what exists today and what does not | Static page; the "not available yet" list is deliberate |
| 2 | Sign in as the demo business user → `/dashboard` | Sales, orders, health, alerts for the demo business | KPI / health services over the stored demo records |
| 3 | `/chat` — "What were my total sales in the last 30 days?" | The answer, its period, the records used, and a coverage warning if the data only partly covers the period | **Deterministic query engine.** The label under the answer says whether TypeSafe AI Jev understood the question or the standard assistant answered |
| 4 | `/chat` — "How much GST did I collect last month?" | An honest refusal: the data model has no GST field | Closed schema; Jev cannot supply a number |
| 5 | "Show the numbers" on any answer | The raw figures and rows behind the sentence | Same engine output |
| 6 | Sign out → `/login?role=admin` → Research Console → *LLM evaluation* | What has and has not been verified | Files under `research/llm_evaluation/` read by `llm_evaluation_status_service` |

## What the Research Console page can and cannot show

* **Live evaluation: two partial runs** (pilot 6 tasks + stage 2 21 tasks, 1 repeat each: 23/23 scored tasks correct; the 4 GST tasks gave 1 fallback, 1 clarification,
  1 decline and the pilot's 1 fallback). Shown with a "Partial evaluation (pilot)" banner and a coverage panel (27 of 27 tasks, 1 of 5 repeats); it supports no accuracy estimate. A full run is 27 tasks × 5 repeats = 135 provider requests (about 0.18 M input tokens, an estimated $0.008 at the published
  list price; the provider's credit unit is not defined publicly). It is an explicit command, never started by the UI.
* **Provider connectivity: verified** by two real requests (HTTP 200, `jev-1.13.0`, every typed answer accepted by the production parser). This is a
  connectivity check, not an accuracy measurement.
* **Mock validations** exercise the measurement code with a fake provider and are labelled "not a result".
* **B2 (a model writing pandas code)** cannot run on Jev, which returns typed decisions only. No comparison is shown or implied.

## Things a reviewer may ask

* *Can the AI make up a number?* No: Jev returns choices and 0–1 judgements for a fixed question set; values (dates, product names) are extracted by
  code and validated against a closed schema, and the engine computes the result from the business's own rows (`business_id`-scoped).
* *What if Jev is down or unsure?* A labelled fallback to the rule-based assistant, never a silent substitute; one request per question, no retries.
* *Is the classification accurate?* Not measured yet. The first live evaluation is the step that would measure it.
