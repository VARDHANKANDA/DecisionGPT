# Real Indian SME Decision-Outcome — Data Dictionary

Every field accepted by `real_sme_outcome_service.validate_record` /
`import_real_sme_outcomes.py`. Mirrors
`docs/templates/real_indian_sme_outcome_template.{csv,json}`.

Privacy classification:
- **PUBLIC-AGGREGATE** — coarse, non-identifying business attribute.
- **METRIC** — a number used for the prediction-vs-actual comparison.
- **PROVENANCE** — how / under what consent the record was collected.
- **REJECTED** — never allowed; the importer refuses a record containing it.

| Field | Type | Meaning | Unit | Req? | Source | Privacy | Allowed values | Example | Used for prediction? | Eval only? |
|---|---|---|---|---|---|---|---|---|---|---|
| `business_id` | string token | Self-chosen anonymous code for the business | — | required | SME | PUBLIC-AGGREGATE | `^[A-Za-z0-9][A-Za-z0-9_-]{1,63}$` (no name / contact) | `SME-A1` | no | grouping / clustering |
| `industry` | string | Business type | — | required | SME | PUBLIC-AGGREGATE | free text (≤ 100 chars) | `Clothing Retail` | no | grouping |
| `state` | string | Indian state / region | — | required | SME | PUBLIC-AGGREGATE | free text | `Maharashtra` | no | grouping |
| `district` | string | District (coarse) | — | required | SME | PUBLIC-AGGREGATE | free text | `Pune` | no | context only |
| `decision_date` | date | When the intervention was made / prediction generated | `YYYY-MM-DD` | required | SME | PUBLIC-AGGREGATE | valid date | `2026-01-06` | no | horizon / leakage check |
| `decision_type` | enum | The lever changed | — | required | SME | PUBLIC-AGGREGATE | `price_increase` \| `price_decrease` \| `marketing_increase` \| `marketing_decrease` \| `inventory_decision` | `price_increase` | no | capability gate |
| `goal` | string | Business objective | — | required | SME | PUBLIC-AGGREGATE | free text (`increase_profit`, `increase_revenue`, …) | `increase_profit` | no | context |
| `strategy` | string | Strategy DecisionGPT recommended | — | required | SME | PUBLIC-AGGREGATE | free text | `Price +5%` | no | reporting label |
| `prediction_horizon_days` | integer | Forecast window | days | required | SME | PUBLIC-AGGREGATE | `7` \| `14` \| `30` \| `60` \| `90` | `30` | no | pairing predicted↔actual |
| `baseline_revenue` | number | Revenue for the period **before** the decision | INR | required | SME books | METRIC | ≥ 0 | `850000` | yes (baseline) | — |
| `predicted_revenue` | number | Revenue DecisionGPT predicted | INR | required | DecisionGPT (R0) | METRIC | number | `905000` | yes (predicted) | — |
| `actual_revenue` | number | Revenue actually observed over the horizon | INR | required | SME books | METRIC | number | `872000` | no | yes |
| `baseline_profit` | number | Profit before the decision | INR | optional | SME books | METRIC | number | `170000` | yes (baseline) | — |
| `predicted_profit` | number | Profit DecisionGPT predicted | INR | optional | DecisionGPT | METRIC | number | `196000` | yes (predicted) | — |
| `actual_profit` | number | Profit actually observed | INR | optional | SME books | METRIC | number | `181000` | no | yes |
| `baseline_units` | number | Units / orders before the decision | count | optional* | SME books | METRIC | number | `4200` | yes (baseline) | — |
| `predicted_units` | number | Units / orders DecisionGPT predicted | count | optional | DecisionGPT | METRIC | number | `4150` | yes (predicted) | — |
| `actual_units` | number | Units / orders actually observed | count | optional | SME books | METRIC | number | `4090` | no | yes |
| `predicted_risk` | number | Risk score DecisionGPT displayed | 0–1 | required | DecisionGPT | METRIC | `[0, 1]` | `0.18` | reported | risk calibration |
| `predicted_confidence` | number | Confidence DecisionGPT displayed | 0–1 | required | DecisionGPT | METRIC | `[0, 1]` | `0.62` | reported | confidence calibration |
| `historical_price_min` | number | Lowest observed price in recent history | INR | optional (reserved) | SME | METRIC | number | `190.0` | no | reserved — future R0/R3 risk recompute |
| `historical_price_max` | number | Highest observed price in recent history | INR | optional (reserved) | SME | METRIC | number | `240.0` | no | reserved |
| `historical_price_median` | number | Median observed price | INR | optional (reserved) | SME | METRIC | number | `210.0` | no | reserved |
| `outcome_recorded_date` | date | When the actual result was measured | `YYYY-MM-DD` | required | SME | PROVENANCE | valid date, ≥ `decision_date`, within `[0.5·h, 2·h+7]` days of horizon `h` | `2026-02-05` | no | leakage / horizon check |
| `outcome_status` | enum | Did the strategy meet the goal? | — | required | SME | PUBLIC-AGGREGATE | `achieved` \| `partially_achieved` \| `not_achieved` \| `inconclusive` | `partially_achieved` | no | goal-achievement summary |
| `notes` | string | Optional short free text (no PII) | — | optional | SME | PROVENANCE | ≤ 2000 chars | `festive month` | no | context |
| `source_type` | enum | Origin of this record | — | required | project | PROVENANCE | **must be** `real_indian_sme` | `real_indian_sme` | no | category isolation |
| `business_country` | string | Country | — | required | SME | PROVENANCE | `IN` / `IND` / `INDIA` | `IN` | no | India-only gate |
| `data_consent_status` | enum | Consent record | — | required | project | PROVENANCE | `consented` \| `consent_given` \| `granted` | `consented` | no | governance |
| `anonymization_status` | enum | Anonymisation state | — | required | project | PROVENANCE | `anonymized` / `anonymised` | `anonymized` | no | governance |
| `collection_method` | string | How the record was gathered | — | required | project | PROVENANCE | free text (≤ 60) | `sme_self_report_form` | no | governance |
| `collection_date` | date | When the record was gathered | `YYYY-MM-DD` | optional | project | PROVENANCE | valid date | `2026-02-06` | no | governance |

`*` `baseline_units` is **required** for `marketing_increase` / `marketing_decrease`
(the outcome cannot otherwise be evaluated); optional for other decision types.

## Never accepted (importer rejects the whole record)

Any field whose **name** matches `aadhaar|aadhar|pan|gstin|phone|mobile|email|
bank|account_no|account_number|ifsc|customer_name|customer_id|owner|contact|
address|pincode`, or any **value** that looks like an email address, an Indian
phone number (`[6-9]\d{9}`, optional `+91`), or an 11+ digit number (Aadhaar /
account). A `business_id` that is not an opaque token is also rejected.

## Derived / internal (not provided by the SME)

| Key | Where | Purpose |
|---|---|---|
| `_sme_natural_key` | `Decision.expected_outcome_json` | duplicate detection only (`business_id\|decision_date\|decision_type\|strategy\|horizon`); anonymised; ignored by every evaluator |
| `DecisionOutcome.source_type = real_indian_sme` | DB | keeps the record out of every synthetic aggregate |
| `PredictionEvaluation.metrics_json` | DB | per-target `predicted_change`, `actual_change`, `error`, `abs_pct_error` computed by the existing `digital_twin_evaluation_service` |
