# OpenAI integration (replaces TypeSafe AI Jev) — 2026-10-14

DecisionGPT's only AI provider is **OpenAI**, called through the official `openai` Python SDK (Responses API) from the backend only.
The earlier TypeSafe AI Jev integration is retired for new requests; its experiment records stay in the research history, labelled with
their original provider (`typesafe-jev`). See `docs/JEV_INTEGRATION.md` (historical).

## What the model does — and does not do

| Step | Who | Detail |
|---|---|---|
| 1. Authenticate, resolve business scope | application | `verify_business_access` before anything is sent |
| 2. Classify the question | **OpenAI** | One request. Strict JSON schema: for each field of the closed interpreter vocabulary (route, operation, metric, statistic, grouping, direction, named-products flag, ...) an enum label plus a self-reported confidence. Question text only; no rows, product names, ids or other tenants' data. |
| 3. Extract values and validate | application | Periods, product names (matched against the business's own catalogue), limits and weekdays come from deterministic code; the closed `Interpretation` schema is assembled and strictly validated. Confidence below 0.5 → fallback. |
| 4. Calculate | application | Approved parameterised query services with enforced `business_id` scoping. No SQL, Python, shell or tools come from the model. |
| 5. Verified facts | application | The FACT sentence and caveats from the engine's result. |
| 6. Restate facts | **OpenAI** (optional) | Requested only for a list of three or more rows (a single clear sentence, a comparison or a no-data answer never gets one). One request with only the question and the verified facts. The text is shown only if the deterministic guard (below) passes; otherwise it is dropped and the deterministic text stands. |
| 7. Respond | application | The answer carries `path` (`llm_analytics` or `legacy_router`) and a notice when it is a fallback. |

Goal sentences are classified the same way (objective + constraint flags); target, unit and horizon stay rule-based.

## Configuration (server side only)

| Variable | Meaning | Default |
|---|---|---|
| `OPENAI_API_KEY` | Your key. Put it after `OPENAI_API_KEY=` in `backend/.env` (git-ignored). | blank → rule-based mode |
| `OPENAI_MODEL` | A model your account can use that supports structured outputs. | blank → `gpt-4.1-mini` |
| `OPENAI_TIMEOUT_SECONDS` | Per-request timeout | `20` |
| `OPENAI_MAX_RETRIES` | Extra attempts for errors that cannot have been processed (capped at 2) | `1` |
| `ANALYTICS_LLM_ENABLED` | Kill switch for the classification path (off → the standard rule-based assistant answers) | `true` |
| `ANALYTICS_EXPLAIN_ENABLED` | `false` → the optional restatement request is **never sent**; the question is still interpreted by the model and the verified deterministic text is the whole answer. Blank = `true`. | `true` |

Loading rules (`backend/app/core/config.py`): process environment > `backend/.env` > repo-root `.env`, located from the file itself so
the working directory does not matter; a blank line in a file counts as "not set"; a blank process variable disables the AI path. The key
is excluded from settings `repr`, never logged, never in an error message, and never in a `NEXT_PUBLIC_*` variable or the frontend.
`.gitignore` covers `.env` at any depth and `.dockerignore` excludes `**/.env`.

## Explanation guard and capability policy (implementation change, 2026-10-15)

Added after the 2026-10-14 smoke run, which showed restatements that repeated the verified fact and the caveat almost word for word.
**That run did not have this guard**; its stored answers are unchanged. Any later evaluation is a new run with its own recorded
explainer-prompt hash.

*Why the repetition happened.* (1) The explainer prompt told the model to "reply with one short sentence that points to the key
figure" when the facts were already complete, so it restated the figure; (2) the caveats were sent to the model and then appended again
by the answer assembler; (3) the old check only compared numbers, causal and advice words, so a sentence built from the verified words
passed; (4) a request was made even for a one-sentence answer.

*What happens now* (`analytics_answer_service`, all deterministic, no model judges another model):

1. `explanation_needed`: no request for a no-data answer, one short sentence, or a comparison; one only for a list of 3+ rows.
2. The prompt asks for at most one new sentence and the word `NONE` when nothing can be added.
3. `validate_explanation` rejects: empty / non-text / JSON or code / `NONE`; a duplicated sentence; a sentence equal or near-identical
   (token containment ≥ 0.8 or character similarity ≥ 0.85) to one verified fact or caveat; an explanation with no new context; more than
   two sentences; any number not in the facts; causal, advice, speculative or evaluative wording; a month, weekday or name not in the
   facts; a completeness claim ("whole month") the caveats do not make; a direction opposite to the verified change; any new content
   word outside a small list of neutral ranking / comparison words.
4. `preserves_verified_text` re-checks that every fact and caveat sentence is still verbatim in the final answer.

Any rejection, failure or exception leaves the deterministic answer; the reason is stored in the audit (`explanation_rejected`,
`explanation_error`, `explanation_skipped`).

*Questions about data the records do not hold* (GST/tax, region, payment mode, marketing channel): `UNAVAILABLE_ATTRIBUTES` in
`analytics_interpreter_service` is a capability table kept honest by a test against the data-model columns. When the model's route is
`calculate` or `clarify` and the question mentions one of these, the answer is the single fixed refusal "…it doesn't contain GST or tax
information, so I can't work this out and I won't estimate it." — never a product clarification that cannot help, never a figure. The
same check runs in the standard (rule-based) assistant, so the answer does not depend on whether the model is available. A question
that is genuinely ambiguous and answerable from the data (for example "what share came from it?") is still clarified. Discounts and
stock levels are not in this table because the data model has those columns.

## Failure handling

| Condition | Result kind | Retried? |
|---|---|---|
| no key | `not_configured` | – (nothing sent) |
| 401 / 403 | `authentication_failed` | no |
| 429 with `insufficient_quota` | `quota_exceeded` | no |
| 429 otherwise | `rate_limited` | once (bounded) |
| timeout | `timeout` | **never** (may already be billed) |
| connection failure | `network_error` | once (bounded) |
| 404 / `model_not_found` | `unsupported_model` | no |
| 400 / 422 | `invalid_request` | no |
| refusal / empty / malformed / incomplete | `refusal` / `empty_response` / `malformed_output` | no |
| 5xx | `provider_error` | no |

Every failure becomes a labelled fallback to the standard rule-based assistant. There is no silent switch to another provider.

## Verification status

* Mocked tests (`tests/unit/test_openai_client.py`, `tests/integration/test_openai_chat_path.py`) cover the request contract, valid and invalid
  structured output, refusal, every error class and retry bound, fallback provenance, deterministic numbers, tenant isolation and secret hygiene.
  They prove the application follows the documented contract; they do not prove the live API accepts the request.
* A live connectivity check and a bounded smoke evaluation are run explicitly, only when `OPENAI_API_KEY` is set (see
  `scripts/verify_openai_live.py` and `research/llm_evaluation/pilots/openai_smoke_PROPOSAL_not_executed.json`).
* Estimated cost uses the published per-token price of the configured model (`research/llm_evaluation/pricing.json`, source and retrieval
  date recorded). It is an estimate, not a billing record.
