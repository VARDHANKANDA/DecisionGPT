# DecisionGPT Business Operating System — what was built, and what was not

Written 2026-10-09. This describes the product layer added on top of the existing analytics, forecasting, decision and research code.
It is **not research evidence**: nothing here touches the frozen experiments, the manifest (`94aa419c…`), the LLM-evaluation task spec
(`98f370377280…`) or any research artifact.

## Honesty rules the code enforces

* No live AI call is needed to browse. The only provider is TypeSafe AI Jev (typed decisions, no text). Without a key the rule-based paths
  run; the AI-model debate is never available and reports `ai_model_unavailable` (nothing is run, nothing is saved, nothing is invented).
* Every number comes from the owner's stored records through a deterministic calculation. Unavailable inputs give an explicit
  "Not available" / `not_enough_data` state, never a guess.
* Every query is filtered by `business_id`; the new router is mounted behind `verify_business_access`.
* Destructive data operations (cleaning, transformation) need an explicit `confirm`, are previewed first, are recorded in
  `data_prep_runs`, and can be undone. A transformation that raises the number of failed validation checks undoes itself.
* No user-supplied code or SQL is ever executed.

## Data platform (`/data/*`)

| Page | Route | Backend |
|---|---|---|
| Sources & Uploads | `/data` (existing) | existing upload / manual entry |
| Inspection & Profiling | `/data/profile` | `GET /data/profile/{table}`, `GET /data/preview/{table}` |
| Cleaning | `/data/clean` | `GET /data/cleaning/{table}`, `POST /data/cleaning/apply`, `POST /data/runs/{id}/revert` |
| Validation | `/data/validate` | `POST /data/validation/run` (23 rule checks over 6 tables) |
| Transformation | `/data/transform` | `GET /data/transform/options`, `POST /data/transform/preview|apply` |
| Preparation & Readiness | `/data/prepare` | `GET /data/pipeline` (7 stages; states not_started / in_progress / needs_attention / ready / failed) |
| Data Quality History | `/data/quality` | upload checks + `GET /data/prep-history` |

Limits: source files are not retained, so "original data" means the stored rows before a step (each applied step snapshots them).
Customers and products are not changed by cleaning (other records point to them). Joins and free-form derived columns do not exist.

## Monitoring

* **KPI Monitoring** `/kpis` — 7 KPIs, period 7/30/90 days, counted back from today or from the newest sale, trend, owner-set targets
  (`PUT /kpis/{key}/target`). Status is `met` / `not_met` only when a target exists.
* **Business Health** `/health` — `health-v1`: five disclosed components, weights and thresholds; a component with missing inputs is left
  out and the weights rescaled; no composite below 3 components / 50% of the weight. A heuristic, not a validated predictor.
* **Smart Alerts** `/alerts` — six rules with owner-editable thresholds, severity rules shown, deduplicated (one active alert per
  condition, enforced by a partial unique index and a per-business lock), 24 h cooldown after "resolved". Checked **on demand** (opening the
  page or the Overview, or "Check now"); there is no background monitoring and the UI says so.
* **Reports** `/reports` — six types, saved as generated and re-openable (`/reports/view?id=`), printable from the browser. Earlier chat
  answers remain at `/reports/answers`.

## Multi-agent and decision intelligence

* **Multi-Agent Debate** `/agents/debate` — stages: question → shared evidence → independent specialist analyses → challenges →
  evidence review → synthesis → decision brief. Mode `rule_based` (default): fixed specialist rules; each claim cites fact ids; numeric disputes
  are settled by recomputing across 7/30/90-day windows; stale or failed-validation data blocks a confident recommendation; a majority does
  not decide. Mode `ai_model`: **not available** — TypeSafe AI Jev returns typed decisions, not written reasoning, so the request is answered with
  `ai_model_unavailable` and nothing is generated. Nothing is ever applied automatically.
* **Causal AI Engine** `/causal` — states `not_enough_data`, `not_configured`, `assumptions_not_satisfied`, `exploratory_association`,
  `causal_estimate`, `failed`. An association is never called causal. Difference-in-differences needs a pre-trend test that is not rejected
  (p ≥ 0.10); untestable assumptions are listed as "unverified".
* **Counterfactual Analysis** `/counterfactual` — three distinct, labelled kinds: deterministic scenario arithmetic, model prediction (not
  causal), causal counterfactual (only from a saved valid causal estimate).
* **Explainable AI** `/explain` — KPI definitions with rows used; how a stored chat answer was produced (fixed-rule router vs. AI-assisted
  analytics path, where Jev only makes typed decisions and the numbers come from the deterministic engine). No SHAP-style attribution is shown unless a stored analysis actually contains it.
* **Compare Strategies** `/compare` — up to three option sets through the existing what-if model, side by side.
* **Recommendation Outcomes** `/outcomes` — expected vs. recorded; no ROI is computed.

## Not built (stated in the UI where relevant)

Reinforcement-learning optimiser; Business Knowledge library; external system integrations; continuous background monitoring; cash-flow
forecasting; price optimisation; per-product price elasticity.

## Persistence (migrations 0008, 0009)

`kpi_targets`, `alert_rules`, `alerts`, `saved_reports`, `health_snapshots`, `data_prep_runs`, `analysis_runs`; JSON columns use `SafeJSON`
(Decimal / date / numpy values are converted before storing). 0009 adds the one-active-alert-per-condition index (existing duplicates are
marked `cleared` first).

## Tests

`tests/unit/test_platform_kpi_health_alerts.py`, `test_platform_data_and_reports.py`, `test_platform_causal_counterfactual_debate.py`,
`tests/api/test_platform_api.py` (authentication, cross-tenant 403/404, strict request validation, confirmation gates, AI-model-debate
unavailable state), and `frontend/src/components/platform-ui.test.tsx`. `tests/unit/test_llm_eval_architecture.py` pins the Jev call sites
(the only one is `JevClient._post`).

## Running it

```
# backend (from the repository root; the blank LLM_* variables keep any provider out)
TYPESAFE_API_KEY= AUTH_ENABLED=true DATABASE_URL=sqlite:///./backend/dev.db PYTHONPATH=. \
  backend/.venv/Scripts/python -m uvicorn app.main:app --app-dir backend --port 8000
# frontend
cd frontend && npm run dev
```

Apply migrations first when the database is older: `cd backend && DATABASE_URL=sqlite:///./dev.db alembic upgrade head`.
