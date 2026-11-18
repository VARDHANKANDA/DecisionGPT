# Demo readiness checklist

First verified 2026-10-15 against the local application, updated 2026-10-15 for the business-specific forecasting, model-eligibility and
price-response safeguards, then final release verification (sections 0, 1, 4a, 7 and 9 are the current state; section 8 and the historical gate table are preserved
unchanged). Everything marked **verified** was observed in a running app (browser pane or API) or produced by a command whose own exit
code is recorded in section 0; anything else is labelled. Companion to `docs/DEMO_GUIDE.md`, `docs/BUSINESS_FORECASTING.md` and
`docs/OPENAI_INTEGRATION.md`.

**One-line status.** A business owner can upload sales, see what is wrong with the data, get a forecast that says how it was checked (or a
refusal that says what is missing), and is never shown a price effect, a calibrated customer probability or a "reliable" band that the
underlying service has not supported. The demo data is synthetic and labelled; no result here is evidence of accuracy on a real business.

## 0. Verification status (what was run, with exit codes)

### 0-final. Final release verification (latest; supersedes the targeted-run rows of 0a)

Offline throughout (launch configuration `backend-offline`, proxies pointed at a closed port, test-level outbound blocker). No live OpenAI
or Jev request was made. The suite was started only after confirming that no pytest process was running.

| Gate | Result | Exit code | Evidence |
|---|---|---|---|
| **Complete backend suite**, `backend/.venv`, `pytest -q -p no:cacheprovider -W ignore`, run once after the last code change | **1206 passed, 1 skipped, 0 failed**, 22m56s | pytest's own `$?` = **0** (written to the log by the wrapper, not taken from a tail command) | this run's log; provider-isolation and tenant tests are part of it |
| Frontend `tsc --noEmit` | clean | 0 | fresh run after the last UI edit |
| Frontend ESLint (`npm run lint`) | clean | 0 | fresh run |
| Frontend `vitest run` | 24 files, 154 passed | 0 | fresh run |
| Frontend `npm run build` | compiled, 62/62 static pages | 0 | fresh run |
| `backend/dev.db` | byte-identical to its state before the browser walkthrough (hash compared); revision 0010 | – | every upload below went to a disposable copy |
| Historical artifacts (20 hashed files) | unchanged | – | `experiments/ml_benchmark_v1/HISTORICAL_HASHES.json` |

An earlier full run of this pass was stopped on purpose when further fixes (below) were made after it started; it is not counted. Fixes made
during this pass: the counterfactual "model prediction" and the debate's pricing option bypassed the price gate and are now gated like
chat, What-If and decisions; unreadable files now get a plain-language reason; the "band not calibrated" copy no longer blames "too little
history" when the band was measured and simply did not cover the target.

### 0-browser. Browser upload scenarios actually completed (built-in browser pane, disposable database)

**What "file picker" means here.** The built-in browser has no control for the native operating-system file dialog and Claude in Chrome
was not connected. Each file was loaded into the page's real `<input type="file">` programmatically (a `File` placed in the input's
`FileList`, then a `change` event), after which the app's own preview, type check, mapping, upload request and result screens ran
unmodified. The native OS dialog itself was **not** exercised.

| Scenario | File | Result observed in the UI | API agreed |
|---|---|---|---|
| Valid sales file | 90 days, 270 rows | Preview of 5 columns, type guessed "Sales", "270 rows added"; forecast page: 14-day total 329 units, method named, "based on sales recorded up to 15 Oct 2026", band flagged **indicative** because it covered 96% of held-out days against the 80% target | forecast sum 328.5, `interval_reliable=false`, same warning |
| What-If, price +10% on that business | - | "Price effect unavailable", baseline 328.5 units = the Forecast page; no effect figures | `expected_revenue=null`, `withheld=true` |
| Invalid (binary) file | `.csv` of arbitrary bytes | "We couldn't add this file yet. Nothing was saved, and your existing data is unchanged." | status `failed`, 0 rows stored, forecast 422 |
| Unrecognised columns | `when, what, how_many, cost` | Mapping step "Help us match your columns" (Date, Quantity, Price each); nothing stored; Forecast page "Checks on your sales data" names the waiting file | 0 rows, blocker names the file |
| Stale data | 60 days ending 25 days ago | Limited estimate; "Your latest recorded sales are from 2026-09-20 (25 days ago) ... not from today"; "based on sales recorded up to 20 Sept 2026" | same warnings |
| Short history | 10 days | Forecast page check box and a refusal: "A forecast needs at least 14 days ... 10 days of history and 10 days with sales" | 422 `INSUFFICIENT_DATA` |

Tenant isolation, checked live against the running offline backend: another owner's token on a business returned **403** for readiness,
units history, forecast, What-If and chat; no token returned **401**.

### 0a. Current state (business forecasting and price safeguards pass)

Offline throughout: no live OpenAI or Jev request was made (launch configuration `backend-offline*`, test-level outbound blocker).

| Gate | Result | Exit code | Evidence |
|---|---|---|---|
| Full backend suite (start of this pass, after the forecasting work) | **1192 passed, 1 skipped, 0 failed**, 26m11s | pytest's own `$?` = **0** | output of that run; an earlier run of the same code had 1 failure (a raw `date.today()` in the new readiness service, fixed) |
| Targeted backend regression after this pass's fixes (decision, digital twin, pipeline, risk, agent, experiment, price, forecast, assistant, chat, readiness, lifecycle, applicability, churn, customer, architecture, evaluation, R1/upgraded, tenant/access, provider isolation) | **540 passed, 663 deselected** | pytest `$?` = **0** | `pytest -k "<those words>"` over `tests/` |
| Frontend `tsc --noEmit` | clean | 0 | fresh run after the UI edits |
| Frontend ESLint | clean | 0 | fresh run |
| Frontend `vitest run` | **24 files, 154 passed** | 0 | includes the new What-If "no checked model" case |
| Migrations | `backend/dev.db` was at revision **0009**; the code needs **0010**. Against an unmigrated copy the Forecast and What-If endpoints returned **500**. `alembic upgrade head` applied 0009 to 0010 (additive: `models.lifecycle_json` + `model_lifecycle_events`); the forecast then returned 200 from `dev.db` | 0 | see section 1 |
| Frontend `npm run build` | compiled, 62/62 static pages | 0 | fresh run after the UI edits |
| Historical frozen artifacts (20 hashed files in `experiments/ml_benchmark_v1/HISTORICAL_HASHES.json`) | unchanged | – | hash comparison re-run at the end of this pass |

Not re-run in this pass: a second full backend suite (the changes were limited to the forecasting, price-gating, assistant and readiness
modules, each covered by the targeted run above). The five-repeat frozen benchmark and any real-SME collection were not run.

### 0b. Earlier stabilization pass (historical, unchanged)

Offline tests use mocked provider transports and a test-level outbound HTTP blocker (`tests/conftest.py`); none of them sent a provider
request. "Live" below means a real OpenAI request.

| Gate | Result | Exit code | Evidence |
|---|---|---|---|
| Full backend suite (`pytest`, run started 10:26 IST, **before** the isolation file existed) | **1033 passed, 1 skipped, 0 failed, 0 errors**, 28m15s, 8 warnings | pytest's own `$?` = **0** | output of that run; skipped test is a conditional skip, warnings are third-party deprecations |
| Provider-isolation file (`tests/unit/test_provider_isolation.py`) + env loading | **29 passed** (10 + 19) | 0 | after the launch-config change in section 1 |
| Frontend TypeScript (`tsc --noEmit`) | clean, no output | 0 | fresh run |
| Frontend ESLint (`npm run lint`) | clean | 0 | fresh run |
| Frontend tests (`vitest run`) | 20 files, **138 passed** | 0 | fresh run |
| Frontend production build (`npm run build`) | compiled, 61/61 static pages | 0 | fresh run; no key-shaped string in `.next` |
| Reproducibility dropdown change (final pass): `research-pages.test.tsx` incl. new regression test | 11 passed; **negative control** (option restored) fails with exit 1 | 0 | `frontend/src/app/research/research-pages.test.tsx` |
| `tsc --noEmit` and ESLint on the changed files (final pass) | clean | 0 / 0 | fresh run |
| Offline rehearsal (final pass, `backend-offline`) | top-products and improving/worsening answered; both GST phrasings refused; all four `path=legacy_router`; **0 new provider-call rows** in stored chat audit (6 before, 6 after); research API anon 403 / demo 403 / admin 200; tenant cross-chat 403/403, anonymous 401 | – | rehearsal script output |
| Live-provider checks | **none in this stabilization work**, apart from the 4 unintended requests in section 8 | – | `docs/INCIDENT_LOG.md` |
| Live OpenAI smoke run (earlier, 2026-10-14) | 6 tasks × 1 repeat, 11 requests, 5/5 primary correct, E01 clarification | – | `research/llm_evaluation/runs/run_20261014T172246Z_f320dc9f` |

**Baseline caveat:** the 1033-test full-suite result predates `tests/unit/test_provider_isolation.py`, the `HTTP(S)/ALL_PROXY` lines in the
offline launch configuration, and the frontend change below. It has not been re-run in full since; the later items were verified by the
targeted checks listed in the table.

Not run: a second full backend run that includes the isolation file (the new file was run on its own, and its target code was already
covered by the full run); the five-repeat frozen benchmark; any real-SME data collection.

The full-suite result **depends on `tests/conftest.py`**: before this task a test read the model name from the developer's real
`backend/.env` and failed (`gpt-5-mini` adds a `reasoning` field); the model and explain switch are now pinned, the key is pinned to
`None`, and real httpx transports raise in tests.

## 1. Start the services

Two launch configurations exist in `.claude/launch.json`; both use the local SQLite database `backend/dev.db` with `AUTH_ENABLED=true`.

| Mode | Launch name | Provider requests? | Use it for |
|---|---|---|---|
| **Offline (recommended for a safe demo)** | `backend-offline` | **None.** `ANALYTICS_LLM_ENABLED=false`, `ANALYTICS_EXPLAIN_ENABLED=false`, `OPENAI_BASE_URL` and all `HTTP(S)/ALL_PROXY` point at a closed local port (`NO_PROXY=127.0.0.1,localhost`), so a code path that builds a client still cannot leave the machine | Everything except AI question understanding; the standard rule-based assistant answers and says so |
| AI | `backend` | **Yes**, one OpenAI classification request per free-form chat question (an optional second request only for multi-row lists) | Showing the AI understanding step; spends credits |

From the repository root, without the desktop launcher (PowerShell):

```
# backend, offline mode (no provider traffic)
$env:PYTHONPATH='.'; $env:DATABASE_URL='sqlite:///./backend/dev.db'; $env:AUTH_ENABLED='true'
$env:ANALYTICS_LLM_ENABLED='false'; $env:ANALYTICS_EXPLAIN_ENABLED='false'; $env:OPENAI_BASE_URL='http://127.0.0.1:9/v1'
$env:HTTPS_PROXY='http://127.0.0.1:9'; $env:HTTP_PROXY='http://127.0.0.1:9'; $env:ALL_PROXY='http://127.0.0.1:9'; $env:NO_PROXY='127.0.0.1,localhost'
backend\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000

# frontend (second terminal)
cd frontend; npm run dev
```

For AI mode drop the `ANALYTICS_*`, `OPENAI_BASE_URL` and proxy lines. **Do not blank the key with `$env:OPENAI_API_KEY=''`**: in Windows
PowerShell that *removes* the variable and the key in `backend/.env` is then used (this happened once during verification: see section 8). Proxy blocking was proved with a non-provider URL: `httpx` and the OpenAI SDK's own client both fail to connect when these variables are set.

**Migrations before first start.** The application does not migrate the database on startup. After pulling this version run, once:

```
cd backend; $env:PYTHONPATH='..'; $env:DATABASE_URL='sqlite:///./dev.db'; ..\backend\.venv\Scripts\python.exe -m alembic upgrade head
```

An older database (revision 0009 or earlier) makes `/analytics/forecast`, `/digital-twin/simulate` and `/decisions/analyze` return a generic 500
because the model registry reads the new `lifecycle_json` column. Verified on a copy of the development database; `backend/dev.db` is now at 0013 (0011 adds the outcome-tracking tables, 0012 their uniqueness rules and 0013 the snapshot fingerprint; the Recommendation Outcomes and Decision History pages need them).

## 2. URLs (verified)

| What | URL |
|---|---|
| Landing page | http://localhost:3000/ |
| Business sign-in | http://localhost:3000/login?role=user |
| Admin / researcher sign-in | http://localhost:3000/login?role=admin |
| Business chat | http://localhost:3000/chat |
| Unified data preprocessing | http://localhost:3000/data/preprocessing |
| Research Console | http://localhost:3000/research (sub-pages in section 6) |
| Backend API / health | http://127.0.0.1:8000/api/v1/health |

## 3. Sign in

Local development accounts (admin, a normal business user, and a demo business with synthetic data) are listed in the git-ignored
`.local/dev_accounts.md`; open that file for the emails and throwaway passwords. They are not repeated here. The demo business is
**Saanjh Handloom Co. (Demo)** (synthetic data, labelled as such). The sign-in pages route by the account's *server-side* role: a
business account cannot open the Research Console.

## 4. Questions to demonstrate (sign in as the demo business user, open `/chat`)

All three below were **verified in the offline backend** through the real route; the answer is labelled *Standard assistant
(rule-based)* because no AI step ran.

| Purpose | Ask | Expected behaviour |
|---|---|---|
| Supported sales / product question | `Which products sold the most last month?` | A ranked list with rupee figures and units for the last 30 days (`intent=top_products`, answer type "known") |
| Comparison question | `What is improving and what is getting worse?` | Total sales change versus the previous 30 days plus products improving and declining (`intent=improving_worsening`) |
| **Unsupported GST question** | `How much GST did I collect last month?` | "…it doesn't contain GST or tax information, so I can't work this out and I won't estimate it." No product clarification, no figure, labelled as unable to answer (`intent=analytics_unsupported`, evidence flag false) |

A second GST phrasing, `How much of my sales between January and March 2025 came from items with 5% GST?`, gives the same refusal
(verified). In **AI mode** the same refusal comes from the AI path (`path=llm_analytics`): the model's classification is overridden by
the deterministic capability check. Also verified in AI mode, by accident (see section 8): `Which are my top selling products?`
returned the engine's answer for the demo data with no second request.

Free-form period questions such as `What were my total sales in February 2025?` need the AI step; in offline mode they are answered
by the fixed router or reported as not understood, with a notice saying the AI interpreter is off. Their AI-mode behaviour is verified
by mocked tests and by the earlier smoke run on the Indian POS dataset, **not** re-run live on the demo business in this check.

### 4a. What the business owner sees now (verified through the API and, where noted, the browser pane, offline)

Walkthrough businesses were created in a scratch copy of `dev.db` with generated sample files (labelled "WT ..."; they never touched
`backend/dev.db`). The sample files are synthetic.

| Situation | What the owner is told | Verified |
|---|---|---|
| Empty file, text that is not a table, binary, `.exe`, header only | Upload status `failed` with a plain reason ("No columns to parse", "Unsupported file type ... Upload a .csv or .xlsx file", "No rows found"). Nothing is stored. The upload page shows "We couldn't add this file yet. Nothing was saved" | API; page code path read |
| Columns not recognised | Status `needs_mapping_confirmation`; the page asks which column is which. Forecast readiness lists the waiting file by name in its blockers | API + new test |
| Returns, zero or negative prices, revenue not equal to quantity x price, duplicates | Duplicates stop the upload with a count. The others are accepted and named in the readiness report with row counts and severity (a zero price blocks training readiness); the Forecast page shows them in a "Checks on your sales data" box before the forecast is run | API + new frontend test |
| Fewer than 14 days, or fewer than 7 days with sales | Forecast **refused**: "A forecast needs at least 14 days of history with sales on at least 7 of them; this business has 10 days of history and 10 days with sales." The page shows that sentence | API + browser |
| 14 to about 62 days | **Limited estimate**: last-28-day average held flat, heuristic band, `interval_reliable=false`, `validation.status=not_validated`, and `metrics_scope` now says no backtest was possible | API |
| Enough history, no weekday method beats the average | `business_specific_baseline`: simple average, band still measured on the business's own past weeks | API |
| Enough history and a weekday method wins on an untouched holdout | `business_specific_validated`, with the method named; band flagged reliable only if holdout coverage is within 0.15 of 0.80 | API + browser |
| Data older than 7 days | A warning with the date and age ("not from today"); the forecast page and the assistant answer state the "sales recorded up to" date | API + new tests |
| What-If with a price change, flat price history | "Price effect unavailable" with only the unmet requirements listed; baseline shown, no effect figures | API + browser |
| What-If with a price change, price varies in the history | **Still withheld** (`reason = model`): the registered forecasting model is a synthetic-platform model with no recorded price response, so units equal the baseline exactly. A price effect appears only for a model recorded as eligible for price scenarios, labelled association-only, never reliable (covered by tests; no such model exists today) | API + browser + tests |
| Marketing or stock What-If | Shown against the business's own forecast baseline, with the note that the registered model's relative response is applied and has not been validated on the business | API |
| Decision suggestions, every option changes price | 422 "No data-supported recommendation is available ..." with the unmet requirements; the page shows that text | API + browser |
| Chat: "Should I raise my price by 10%?" | Refusal with the same reason; uses the 10% the owner named (previously simulated a fixed 5%); no rupee figure | API |
| Chat: "What will my sales be next week?" | 7-day total, the last 7 days' actual, an 80% range only when the interval is reliable (otherwise "indicative" / "limited estimate"), and the data date | API |
| Customers | Scores are "score N / 100" with the synthetic-label warning; the chat answer and page headline no longer call them a chance or a percentage | API + browser |
| Counterfactual "model prediction" for a price change | "A price effect cannot be estimated for your business, so no figure is shown", with what is needed; no rupee figure | new test |
| Debate: the pricing option | Still offered as an idea to test, with "No effect is shown: ..." instead of a simulated gain | new test |
| Unreadable or empty file | "... it is not plain text, so it does not look like a CSV file ..." / "the file is empty" instead of a codec message | new test |
| Unsupported questions (GST, weather, nonsense) | The honest refusal, labelled as the standard assistant; no figure | API |
| Built-in example rows present (`Example:` products, `EX-` customers) | Readiness report and every forecast carry "Some rows ... are DecisionGPT example data, not records of a real business" | new test |

**Eligibility of the registered models** (`GET /research/models`, admin): `sales_forecast_*` v1 and `churn_*` v1 are labelled "not validated
(first version)" and "not eligible for business use"; they remain registered and active only for backward compatibility. Detail:
`docs/MODEL_LIFECYCLE.md` and `docs/BUSINESS_FORECASTING.md`.

## 5. Preprocessing workflow (verified: page loads, all plan API calls return 200)

Sign in as a business user, then **Data Platform → Data Preprocessing** (`/data/preprocessing`). The six steps are: your data, quality
summary, choose steps, run, before and after, history. It is the single Data Platform entry in the sidebar; the older upload / profile /
clean / validate / transform pages remain reachable only as deep links and highlight this entry.

## 6. Research Console (sign in with the admin account; verified)

`/research` → sidebar: Overview, Dataset registry, Model comparison, LLM evaluation, Architecture evaluation, Causal evaluation, Risk
calibration, Validation, Reproducibility, Limitations. **Digital Twin is not in the navigation**; its old URL redirects to the overview.

To inspect stored evaluation results open **LLM evaluation** (`/research/llm-evaluation`):

* Coverage is shown **per provider and never pooled**: OpenAI 6 of 27 tasks (1 run, 5 of 5 scored correct, 11 requests) and
  TypeSafe Jev, the earlier provider, 27 of 27 tasks (2 runs, 23 of 23 scored correct).
* Use the run selector to open a stored run and read each question, the system answer, the expected answer and the outcome.
* These are single-repeat partial runs: *not* an accuracy estimate and not the five-repeat frozen benchmark.
* The OpenAI smoke run `run_20261014T172246Z_f320dc9f` was produced **before** the explanation guard and the capability policy; its
  stored answers (including repeated explanation sentences and the E01 clarification) are unchanged on purpose.

## 7. Known limitations and manual setup

* The key lives only in git-ignored `backend/.env` (`OPENAI_API_KEY`, `OPENAI_MODEL`). It was printed once into a development
  transcript on 2026-10-14; rotate it before any shared demo. Nothing in this repo reads it back out.
* AI mode makes real, billed requests (about $0.001 per question at `gpt-5-mini` list price). Use offline mode unless you need it.
* The optional restatement is requested only for answers with three or more rows; most answers are the deterministic sentence.
* GST/tax, region, payment-mode and marketing-channel questions get the missing-data refusal. Discount and stock questions are *not*
  refused deterministically (the data model has those columns); they follow the model's own routing.
* Demo data is synthetic (10 Apr – 6 Oct 2026); the research results use the Indian POS register and synthetic platform datasets.
* Digital Twin evaluation is intentionally hidden; research results are controlled-evaluation records, not real-business outcomes.
* The **Reproducibility** page (`/research/experiments`) loads with the experiment runner and history (verified). The obsolete
  "Digital Twin Evaluation" option was **removed from the experiment-type selector** (UI only; the backend experiment type, its API
  and previously stored runs are unchanged, and stored runs still appear in the history list). Verified live: 8 options, none Digital Twin.
* **ML benchmark** (`/research/ml-benchmark`, admin): stored public / real-transaction / proxy-label / synthetic benchmark runs, each labelled by evidence class; verified loading in the browser pane with the offline backend (2026-10-15). Detailed method and numbers: `docs/ML_BENCHMARK_REPORT.md`.
* **Limitations** (`/research/limitations`) loads and lists what is not established (verified).
* The business **overview** (`/dashboard`) loads for the demo user with sales, health score, alerts and data-readiness cards (verified).
* Several research cards say "synthetic" or "partial" by design; read the badges (Measured / Estimated / Simulated / Not evaluated).

* **No evidence of real-world predictive accuracy.** Forecast bands are checked on the business's own past weeks (and the demo data is
  synthetic); no model has been checked against outcomes recorded by a real business.
* **Price decisions are unavailable by design** until a model trained on and checked against a business's own price changes exists and a
  deliberate price test is in its history. This is not a bug; the screens say so.
* The What-If marketing and stock effects still come from the registered synthetic-platform model, expressed against the business's own
  forecast baseline and labelled unvalidated. The first sentence of the assumptions says so.
* The what-if range ("expected range for sales") scales the registered model's own band and is not a measured interval.
* Customer scores come from a synthetic-label model; there is no business-specific churn model and none can exist without observed outcomes.
* Zero-sale days are treated as real zeros; the data cannot say whether they were closures, stockouts or upload gaps.
* A stored simulation created before this change keeps the registered model's own baseline (it has no stored baseline factor).
* Upload currency is assumed to be INR and dates carry no time zone.
* Free-form period questions need the AI interpreter and are not answered in offline mode (a notice says so).

* **Native file dialog not exercised.** Uploads were verified through the page's file input (see 0-browser), not the operating-system picker.
* Sales rows uploaded without a products file show "-" for Product and top-product questions answer "no sales are linked to products"; the
  product name column in a sales file is not used to create products.
* The `-k`-style targeted runs of the earlier passes are no longer the evidence; the complete suite result in 0-final is.

## 8. Incident note from this verification

While checking the chat route, an "offline" launch configuration that used `$env:OPENAI_API_KEY=''` did **not** disable the key, and
four chat questions on the demo business were sent to OpenAI (4 classification requests, 4,856 input / 1,610 output tokens, about
$0.004 estimated; no explanation requests). The configuration was corrected (section 1) and the offline path was re-verified twice, including after the proxy block was added:
the stored audit rows of the later questions contain no provider call. Full record: `docs/INCIDENT_LOG.md` (not part of any evaluation run). The four stored chat rows remain in `backend/dev.db` as normal
chat history of the demo business.

## 9. Offline demo release decision

**GO for an offline demo** on synthetic or sample data, under these conditions:

1. Run the migration first (`alembic upgrade head`, section 1); an older database returns 500 on forecast, What-If and decisions.
2. Use the `backend-offline` launch configuration; do not blank the provider key with `$env:OPENAI_API_KEY=''` (section 8).
3. Present the demo business as synthetic (the "DEMO DATA" banner is always shown) and present every price question as "unavailable until
   a price test exists", not as a missing feature.
4. Do not describe any figure as validated on a real business: none is. Forecast bands are checked on a business's own past weeks only.

**Not covered by this decision:** any real-SME deployment, live AI mode, the native operating-system file dialog, and Claude in Chrome
(not connected during verification).
