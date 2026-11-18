# Business outcome tracking and decision effectiveness

Designed 2026-10-15 after a read-only inspection of the repository. Companion to `REAL_WORLD_VALIDATION_PLAN.md` (evidence levels),
`MODEL_LIFECYCLE.md` and `BUSINESS_FORECASTING.md`. Nothing here claims that DecisionGPT improves business outcomes: the point is to make
that question answerable once real observations exist.

## 1. What the repository already had (verified in code)

| Need | Existing structure | Assessment |
|---|---|---|
| Recommendation record | `decisions` (+ `strategies`, `digital_twin_simulations`, `agent_runs`): selected strategy, alternatives (`candidate_strategy_ids_json`), expected outcome (`expected_outcome_json` = the Digital Twin output), assumptions, uncertainty, model versions, business-state snapshot | **Reuse as is.** Complete for what was recommended and why |
| Outcome capture | `decision_outcomes` (one free-form JSON per decision), `POST/GET /decisions/{id}/outcome` | Insufficient: no metric names, units, window, status, provenance, revisions |
| Acceptance / execution | none | **Gap**: nothing says whether the owner accepted, rejected, modified or executed |
| Forecast snapshots | none (`forecast_sales` returns and discards; the page says "Forecast history isn't currently saved") | **Gap**: a forecast cannot later be compared with actuals |
| Expected vs observed | `digital_twin_evaluation_service` -> `prediction_evaluations`; `memory_service._score_outcome`; the Outcomes page | **Unsound** (see 1.1) |
| Causal evidence from outcomes | `causal_feedback_service` (ASSUMED -> OBSERVATIONAL after >= 3 consistent outcomes) | Assumes the action was executed (uses the sign of the recommended action) and compares against the model baseline (see 1.1) |
| Real-SME import | `real_sme_outcome_service` (provenance columns, migration 0007) | Kept unchanged; a separate research-collection protocol |
| Tenant scoping | `BusinessScopedMixin`, `verify_business_access` router dependency | Reuse |

### 1.1 Defects found in the existing comparison path
1. **Scale and scope mismatch.** `expected_outcome_json` is the registered *synthetic-platform* model's output (a 14-day sum on a different
   scale). The comparison subtracts that model baseline from whatever "revenue" number the owner typed, with no window, units or scope.
2. **Wrong metric mapping.** `orders` and `sales` are mapped to `units_sold`; they are not units sold.
3. **Execution assumed.** The causal-feedback lever direction is the sign of the *recommended* action; no record says it was carried out.
4. **Owner-facing claim.** The Outcomes page shows "Share of the expected change that happened" from (1); agents are fed
   "your previous ... exceeded what the simulation predicted" text from the same numbers.
5. **Forecast horizon and data cutoff are not stored** with a decision, so an in-sample comparison could not be detected.

## 2. Data model (migration 0011)

Decisions stay in `decisions`; tracking is added beside them, never over them. Model lifecycle tables are untouched.

### `tracked_expectations` - what was expected, as it was when it was expected
| Field | Meaning |
|---|---|
| `business_id`, `id`, `created_at` | tenant and identity |
| `source_kind` | `forecast` (snapshot of `/analytics/forecast`), `decision` (from a stored decision), `owner_plan` (a number the owner states) |
| `decision_id` (nullable) | link to the decision it came from |
| `question` | the original question, if any |
| `metric`, `unit`, `scope` | `units_sold`/units, `revenue`/INR, `orders`/orders, `marketing_spend`/INR; scope is `business_total` |
| `window_start`, `window_end`, `horizon_days` | the period the figure is about |
| `data_cutoff` | the last data date the expectation could use (null for an owner plan) |
| `expected_value` | total over the window; `points_json` holds per-day values and band where they exist |
| `interval_reliable`, `interval_method` | how the band was labelled when shown |
| `method`, `model_name`, `model_version`, `basis`, `config_json` | what produced it |
| `reference_json` | simple references computed at the same cutoff (naive last value, trailing mean) so accuracy is reported against them |
| `assumptions_json`, `limitations_json` | what was shown to the user |
| `comparable_to_actuals`, `comparability_reason` | whether the figure is on the business's own scale (false for the synthetic model) |
| `input_sha256` | identity of the daily series used |

### `decision_responses` - append-only; the latest row is the current state
`decision_id`, `seq`, `response` (`pending|accepted|rejected|modified|deferred`), `action_status` (`unknown|not_executed|partially_executed|executed`),
`action_taken_json`, `action_start`, `action_end`, `modified_action_json`, `known_changes_json` (other things that changed),
`evaluation_design` (`none|before_after|matched_control|randomized`, as *declared*, never inferred), `follow_up_date`, `note`, `recorded_by`,
`created_at`. Unknown stays null/`unknown`; accepting is never read as executing.

### `outcome_observations` - append-only revisions
`expectation_id`, `business_id`, `metric`, `unit`, `scope`, `window_start`, `window_end`, `value` (null when unknown - never 0), `status`
(`pending|incomplete|observed|invalid`), `unavailable_reason`, `covered_until` (last date actually observed), `coverage_days` /
`window_days`, `source` (`owner_entered|derived_from_sales|derived_from_marketing`), `provenance` (`owner_entered`, `derived_from_uploaded_data`,
`demo_synthetic`), `revision`, `supersedes_id`, `revision_reason`, `is_current`, `recorded_by`, `created_at`.
A correction writes a new row and flips `is_current` on the old one; nothing is deleted.

## 3. Comparison rules (service `outcome_tracking_service.compare`)

An expectation and an observation are compared only when **all** hold; otherwise the result says which rule failed and is *excluded*, not zero:

1. same `metric`, `unit` and `scope`;
2. same window - or, for an `incomplete` observation, only the covered days (labelled `partial_period`, with the coverage fraction), and only
   when the expectation has per-day values;
3. the window starts after the expectation's `data_cutoff` (otherwise `in_sample`, excluded);
4. the expectation is `comparable_to_actuals` (otherwise `not_comparable`, with the reason; the observation is still stored);
5. the observation is `observed` or `incomplete` with a value (never `pending` or `invalid`).

Output: `signed_error = expected - observed` (positive = over-forecast, the same convention as `bias_units_per_day` in the validation
reports), `abs_error`, `abs_pct_error` (null when the observed value is 0), errors of the references from `reference_json`, the share of
days inside the band where per-day values exist, and the horizon. **Predictive accuracy and business impact are separate sections.**

## 4. Causal policy

For every decision the report states, separately: predicted outcome; observed outcome; difference; whether the action was *recorded as*
executed; other changes the owner recorded; and `causal_impact`:

* `not_identified` unless the owner has declared an evaluation design **and** recorded the control data - and even then DecisionGPT does not
  compute an effect in this module (the causal module's classification is the only place that can);
* a prediction preceding an outcome is never attribution; an accepted-but-not-executed recommendation is never "implemented";
* price effects remain withheld by the existing policy; recording outcomes does not alter model eligibility, retrain, or promote anything.

Later, defensible designs the records can carry (declared, not run): a **randomized holdout** (some customers/stores/days keep the old
price or offer), a **matched control** (comparable stores or products left unchanged), a **staggered start** (the same change introduced on
different dates). Each needs the control group's observations recorded with the same metric, unit and window.

## 5. Evaluation report (`GET /tracking/report`)

Counts: decisions recorded; latest response distribution; actions confirmed executed; expectations; observations by status; pending or
missing outcomes. Accuracy: per metric and horizon bucket, `n`, MAE, mean signed error, mean absolute percentage error where defined,
against the references. Exclusions with reasons. Data completeness and provenance (including `demo_synthetic`). Date range and sample size.
Limitations are always listed. **No single success percentage** is produced; with fewer than the minimum comparable cases the report says
the impact cannot yet be evaluated.

## 6. Existing paths aligned with this design

| Path | Change |
|---|---|
| `causal_feedback_service.apply_outcome_feedback` | only decisions whose latest response records the action as `executed` count as interventions |
| `memory_service.get_relevant_outcome_insights` | only decisions recorded as executed whose expectation is comparable; today none, so no "exceeded what the simulation predicted" text is generated |
| Outcomes page | the "share of expected change" column is replaced by whether the comparison is valid and why |
| `digital_twin_evaluation_service._METRIC_KEYS` | `orders` and `sales` are no longer treated as units sold |
| `decision_outcomes` / `prediction_evaluations` / real-SME import | kept for research and backward compatibility; their records are labelled `unverified comparison` in the new report |

## 7. Not in scope / not claimed

No automatic experiments; no change to operations; no model retraining or promotion from outcomes; no customer-level data is required
(everything is business-level totals); no result in this document is from a real customer business.

## 8. API (all under `/businesses/{business_id}/tracking`, owner-authorised, strict bodies)

| Route | Purpose |
|---|---|
| `POST /forecasts` `{horizon_days, question?}` | snapshot the business forecast as shown now (cutoff, horizon, method, band label, references, dataset sha256) |
| `POST /expectations` | an owner's own plan for a metric and window (for example planned marketing spend); metric and unit are validated together |
| `GET /expectations`, `GET /expectations/{id}` | stored expectations; one with its observation history and the current comparison |
| `POST /expectations/{id}/observations` | record what was observed: `metric`, `unit` (both required), `status`, `value`, `covered_until`, `unavailable_reason` |
| `POST /expectations/{id}/observations/from-data` | measure the window from the business's own uploaded sales or campaigns (pending when no data reaches it, never zero) |
| `POST /observations/{id}/correction` | a new revision with a mandatory reason; the earlier value stays |
| `POST /decisions/{id}/response` | response (`accepted|rejected|modified|deferred`), action status, action taken, dates, other known changes, declared design |
| `GET /decisions/{id}` | current response, full history, expectations with comparisons |
| `GET /report` | the evaluation report (section 5) |

Existing `POST/GET /decisions/{id}/outcome` is unchanged for backward compatibility; what it stores is reported as an unverified,
free-form outcome and is no longer used for claims (section 6).

## 9. What the system can now measure, and what it cannot

**Measurable now, when real observations exist:** forecast error (signed, absolute, percentage) of a stored forecast against units
actually sold in the same window, after its data cutoff, against naive and trailing-mean references, with band hits; planned versus observed
revenue, units or marketing spend; response and execution rates; how many recommendations have a comparable outcome.

**Not measurable without real business observations:** whether any recommendation changed an outcome (impact); price, marketing or stock
effects; churn probability. Even with observations, impact needs a declared control design and the causal module; accuracy of a decision's
figure needs a model that is eligible for the business's own scale (none is today, so decision figures are stored and not compared).

## 10. Verified results (only what was run)

| Check | Result | Exit |
|---|---|---|
| Complete backend suite (`backend/.venv`, started after the last code change, no overlapping pytest process, exit code written by the wrapper) | **1271 passed, 1 skipped, 0 failed**, 26m50s | **0** |
| Frontend `tsc` / ESLint / `vitest` / `next build` | clean / clean / 25 files, 155 passed / 62 of 62 pages (all exit 0, no frontend file changed after) | see report |
| Migration 0010 -> 0011 -> 0010 on a fresh SQLite database; `backend/dev.db` upgraded 0010 -> 0011 (three tables added, existing rows untouched) | passed | 0 |

New tests: `tests/integration/test_outcome_tracking.py` (service rules, comparison, report, causal policy), `tests/api/test_outcome_tracking_api.py`
(authentication, tenant isolation, strict inputs, empty state, migration), a negative control in `test_digital_twin_feedback.py`, and a
tightened `test_memory.py`. The evidence is **synthetic fixtures only**: generated sales with fixed past dates, and the labelled demo
business. There are 0 real business outcome records, and nothing here supports a claim that DecisionGPT improves business outcomes.

## 11. Contract before this change (inspected, then extended additively)

| Item | Before | Now |
|---|---|---|
| `POST /analytics/forecast` response | method, points, warnings, interval fields, `data_as_of`, `forecast_basis`, `validation` | the same, plus `fingerprint`, `dataset_sha256`, `generated_at`, `horizon_requested`, `horizon_returned`, `forecast_start`, `forecast_end`, `data_cutoff`, `references` (older clients ignore them) |
| `POST /tracking/forecasts` body | `{horizon_days, question?}`; recomputed and stored whatever it computed | `+ fingerprint?`; verified against the forecast shown, **409** if it changed, an identical saved forecast is returned (`already_saved`), response adds `already_saved` and `verified_against_shown` |
| `GET /tracking/decisions` | did not exist | `{decisions: [{decision_id, current}]}` for every decision of the business in one call |
| `POST /tracking/decisions/{id}/response` | append-only, validated | unchanged contract; a lost race is a 409 or a duplicate refusal instead of two rows with the same revision |
| `GET /tracking/report` | decisions, expectations, observations, comparisons, accuracy, impact | `+ awaiting_actuals`, `observations.comparable / not_comparable / mean_coverage_fraction` |
| decision horizon and cutoff | inferred at tracking time (14 days; latest sale created before the decision) | recorded with the decision: `debate_json.pipeline_options.scenario_horizon_days` and `.data_cutoff`; decisions made earlier keep an inferred value, labelled |
| migrations | 0011 | 0012 adds a unique `(decision_id, seq)` and a partial unique index (one current observation per expectation, metric, window) |

## 12. Forecast snapshot: exactly what is saved

Saved through the existing `tracked_expectations` row (`source_kind = forecast`); nothing is recomputed to different values.

| Field | Value |
|---|---|
| business scope, creation time | `business_id`; `created_at`; forecast `generated_at` in `config_json` (distinct from the last data date) |
| metric, unit, scope | `units_sold`, `units`, `business_total` (`config_json.aggregation`, `granularity`: daily values, expected value is their sum over the window) |
| exact dates | `window_start`, `window_end`; one point per day in `points_json` with `date`, `value`, `lower`, `upper` and the per-day references `baseline_naive_last`, `baseline_trailing_mean_28` |
| horizon | `horizon_days` (returned) and `config_json.horizon_requested` / `horizon_returned`, `horizon_provenance = recorded` |
| data cutoff and latest data date | `data_cutoff` (the latest sale date used) and `config_json.cutoff_provenance = recorded`; `calendar`: calendar dates without a time zone |
| method and version | `method`, `model_name`, `model_version`, `basis` |
| interval | `interval_method`, `interval_reliable`, `config_json.interval` (method, reliable, nominal coverage) and per-day bounds |
| references | `reference_json`: naive last-value and trailing-28-day totals and daily values |
| dataset identity | `input_sha256` = `config_json.dataset_sha256`; `config_json.fingerprint` identifies the forecast itself |
| assumptions, limitations, validation status | `assumptions_json`, `limitations_json` (the warnings shown), `config_json.validation_status` and `validation` |
| verification | `config_json.shown_fingerprint_verified` (`true`, or `null` when saved without a shown fingerprint) |

A forecast is refused (422, nothing stored) when its fingerprint, forecast dates, data cutoff or dataset identity cannot be established.

## 13. Horizon and cutoff provenance

| Record | Horizon | Cutoff |
|---|---|---|
| forecast snapshot | `recorded` (requested and returned stored) | `recorded` = the latest sale date the forecast used |
| decision made after this change | `recorded` (`scenario_horizon_days`) | `recorded` (latest sale date when the analysis ran) or `none_existed` when there was no data |
| decision made before | `assumed_pipeline_default` (14 days) | `inferred_from_upload_time` (reconstructed from upload times) or `unknown`; an inferred cutoff is flagged `cutoff_inferred` in every comparison and an `unknown` one is never compared |
| owner plan | the stated window | none (a plan is not a prediction from data) |

## 14. Comparisons accepted and withheld

| Accepted (`evaluated` or `partial`) | Withheld (`excluded`, with the reason code) |
|---|---|
| same metric, unit and scope; same window; the window starts after the cutoff; the expectation is on the business's own scale; the observation is `observed`, or `incomplete` over a covered part with per-day expectations (labelled `partial` with the covered fraction) | `missing_observation`, `observation_pending`, `observation_invalid`, `metric_mismatch`, `not_comparable` (a model figure not on the business's scale), `cutoff_unknown`, `in_sample`, `window_mismatch`, `partial_period_without_daily_expectation` |

Revenue is never compared with units; a missing observation is never zero; the original cutoff, horizon, method and model version are
reported with every comparison; accuracy and business impact are separate report sections and no success percentage exists.

## 15. UI workflows

* **Forecast page**: "Save this forecast" sends the horizon and the on-screen fingerprint. States: idle, saving (button disabled), saved
  (period, data date and a link to Outcomes), already saved, "changed since it was shown - nothing saved, refresh and save again", error,
  and "cannot be saved" when the data date or identity is missing.
* **Decision History**: a radio group (accepted, modified, rejected, deferred); "was it carried out?" (not recorded / not carried out / partly /
  carried out) with a start date only for accepted or modified; a description is required for modified; rejected or deferred are recorded as
  not carried out; the note is optional. The recorded response, whether it was carried out, and the response history are shown; changing a
  response adds a revision. Double clicks send one request.
* **Outcomes page**: counts, saved forecasts awaiting results, each comparison with its reason when withheld, and the impact statement.

## 16. Verified results (this change)

| Check | Result | Exit |
|---|---|---|
| Complete backend suite (`backend/.venv`, started after the last code change, no overlapping pytest process, exit code written by the wrapper) | **1290 passed, 1 skipped, 0 failed**, 29m13s | **0** |
| Frontend `tsc` / ESLint / `vitest` / `next build` | clean / clean / 27 files, 173 passed / 62 of 62 pages (all exit 0) | see report |
| Migration 0010 -> 0012 -> 0010 on a fresh SQLite database | passed | 0 |

The evidence is synthetic fixtures only; 0 real business outcomes are recorded. The workflow is verified by tests across the API, the
service and the page components; a browser walkthrough is reported separately.

## 17. Integrity audit (2026-10-16): findings and status

Found by reading the service, models, endpoints and migrations, then confirmed by a failing test before each fix.

| # | Finding | Severity | Status |
|---|---|---|---|
| 1 | Snapshot de-duplication was check-then-insert with the fingerprint only inside JSON: simultaneous saves of one forecast could both insert | High | **Fixed**: `fingerprint` column + partial unique index (migration 0013); the loser of a race returns the winner. Verified with 6 simultaneous threads: one snapshot |
| 2 | `from-data` measurement could supersede an owner's corrected observation | High | **Fixed**: refused with an instruction to correct the owner's entry |
| 3 | A reconstructed (inferred) data cutoff could still feed aggregate accuracy although it can be earlier than the real cutoff (in-sample risk) | Medium | **Fixed**: such comparisons are withheld (`cutoff_inferred`) |
| 4 | Aggregates mixed forecasts with owner plans, dropped unavailable percentages silently, and had no WAPE or coverage disclosure | Medium | **Fixed** (section 19) |
| 5 | A near-zero observed value produced an inflated percentage error | Medium | **Fixed**: unavailable below 1 unit, with the reason |
| 6 | Saved snapshots and history rows were changeable through the ORM | Medium | **Fixed**: append-only guard (section 18) |
| 7 | A `modified` description survived a later change to `accepted` | Low | **Fixed** |
| 8 | A commit failure other than a constraint violation left the session in a failed state | Low | **Fixed**: every commit rolls back completely on error |
| 9 | An identical retry that lost a race was reported as a conflict instead of "already recorded" | Low | **Fixed** |
| 10 | Verified correct, no change: unique `(decision, seq)`, one current observation per window, a correction is one transaction, tenant resolution is server-side, a failed save leaves nothing behind, concurrent report reads are consistent per observation | - | evidence in section 22 |

## 18. Database constraints and transaction guarantees

| Guarantee | Mechanism | Verified by |
|---|---|---|
| One saved snapshot per business and forecast fingerprint | unique partial index `uq_tracked_expectations_forecast_fingerprint` (`fingerprint IS NOT NULL`); an `IntegrityError` returns the existing snapshot | 6-thread race; forced lost race; migration test |
| One revision number per decision response | unique `(decision_id, seq)`; a lost race is a 409 (or "already recorded" if identical) | forced interleaving with a barrier; 6 simultaneous different responses: sequence unique and contiguous |
| One current observation per expectation, metric and window | unique partial index `uq_outcome_observations_current_window` (`is_current`) | simultaneous identical submissions (one wins), simultaneous corrections (one new revision), forced interleaving |
| A correction is atomic | old revision flagged not-current and the new revision inserted in one transaction, flushed in that order | readers during 8 revisions never see zero or two current observations |
| Nothing partial survives a failure | every commit site rolls back on any exception | injected commit failure for an observation and a snapshot; the retry succeeds |
| Saved records are not edited | ORM guard: expectations and responses reject any update or delete; observations allow only `is_current` to change | tests that attempt each |

Not guaranteed: raw SQL or bulk Core statements bypass the ORM guard and there are no database triggers; PostgreSQL was not available, so
the partial indexes are exercised on SQLite only (they are written for both dialects).

## 19. Aggregation rule and unavailable metrics

Per group (metric, source kind, horizon bucket): the unweighted mean of per-forecast absolute and signed errors; WAPE = sum of absolute errors / sum of observed values; only fully compared (not partial, not excluded) cases contribute; groups are never combined.

* Percentage error is reported only when the observed value is at least 1 unit of the metric; otherwise it is `null` with a stated
  reason, and the group reports how many cases had a percentage (`pct_error_n`) and how many did not.
* A group with fewer than 5 cases is listed, not summarised. The report discloses compared-in-full, partial (not aggregated) and withheld
  (not aggregated) counts. Forecast accuracy, execution rate and business impact are separate sections; nothing is combined into one score.

## 20. Legacy and recorded metadata

| `metadata_quality` | Meaning | Used in accuracy |
|---|---|---|
| `known_persisted` | recorded with the record (forecast snapshots; decisions made after 2026-10-15; `none_existed` when there was no data) | yes, if every other rule passes |
| `reconstructed` | rebuilt from reliable evidence | no record currently qualifies |
| `inferred` | reconstructed from upload times (cutoff) or the pipeline default (horizon) | **no**: withheld as `cutoff_inferred` |
| `unknown` | cannot be reconstructed | **no**: withheld as `cutoff_unknown` |

An inferred value is never upgraded: re-materialising a legacy decision returns the existing expectation unchanged. No backfill is
possible without the original analysis time data; legacy decisions simply stay out of accuracy, and the decision figures from the
synthetic model were never comparable anyway.

## 21. Remaining risks and limitations

* **Tenant isolation exists only when `AUTH_ENABLED=true`.** With auth off (the local and test default) any caller can read any business.
* A request for a business that does not exist returns 404 while another owner's business returns 403, so a business id can be probed for
  existence; ids are UUIDs and this is existing behaviour of the shared guard.
* The report issues several read statements; under PostgreSQL READ COMMITTED a snapshot saved between them can appear in one list and
  not another (each correction itself is atomic, so no observation is ever half-written).
* Calendar dates have no time zone; zero-sale days with later data count as zero units; owner-entered observations cannot be verified.
* No real business outcomes exist: everything is verified on synthetic fixtures, and impact stays not evaluable.

## 22. Verified results (integrity audit)

| Check | Result | Exit |
|---|---|---|
| Complete backend suite (`backend/.venv`, started after the last code change, no overlapping pytest process, exit code written by the wrapper) | **1320 passed, 1 skipped, 0 failed**, 52m48s | **0** |
| Frontend `tsc` / ESLint / `vitest` / `next build` | clean / clean / 27 files, 173 passed / 62 of 62 pages (all exit 0; no frontend file changed) | see report |
| Migrations 0010 -> 0013 -> 0010 on a disposable database, including backfill of duplicate fingerprints | passed | 0 |

New tests: `test_tracking_integrity.py` (deterministic report fixtures with independently computed metrics, immutability, failure paths,
legacy metadata), `test_tracking_concurrency.py` (file-backed SQLite, real threads and forced interleavings; run 3 times, stable),
`test_tracking_tenancy_and_migration.py` (every route with real authorization, no leakage, migration constraints and backfill).

