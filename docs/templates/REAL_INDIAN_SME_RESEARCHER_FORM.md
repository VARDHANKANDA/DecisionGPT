# Real Indian SME Researcher Collection Form

Fill one form per **decision record** while working with the SME. Transcribe
the values into `docs/templates/real_indian_sme_outcome_template.csv` (or
`.json`) for import. **Do not request or record PII** — no names, phone, email,
Aadhaar / PAN / GSTIN, bank / account numbers, customer identities, or
identifying addresses.

Field meanings & allowed values: `docs/REAL_INDIAN_SME_DATA_DICTIONARY.md`.

---

## Business

| Item | Value | Template field |
|---|---|---|
| Anonymised business ID (opaque token, e.g. `SME-A1`) | | `business_id` |
| Business category / type | | `industry` |
| State | | `state` |
| District (coarse) | | `district` |
| Approximate business age | | *(context; not imported)* |
| Relevant operating context (channel, scale, seasonality) — no PII | | *(context; not imported)* |

## Decision

| Item | Value | Template field |
|---|---|---|
| Decision date (`YYYY-MM-DD`) | | `decision_date` |
| Decision type (`price_increase` / `price_decrease` / `marketing_increase` / `marketing_decrease` / `inventory_decision`) | | `decision_type` |
| Business goal (e.g. `increase_profit`) | | `goal` |
| Baseline period (the period the baseline figures cover) | | *(context; ensure it matches the actual period)* |
| Strategy DecisionGPT recommended (e.g. `Price +5%`) | | `strategy` |
| Strategy accepted?  (yes / no / partial) | | *(context; record deviations below)* |
| Strategy implemented?  (yes / no) | | *(context)* |
| Implementation date (`YYYY-MM-DD`, if implemented) | | *(context; must be >= decision_date)* |
| Prediction horizon (7 / 14 / 30 / 60 / 90 days) | | `prediction_horizon_days` |

## Prediction  (recorded BEFORE the outcome is known)

| Item | Value | Template field |
|---|---|---|
| Prediction timestamp (`YYYY-MM-DD`) | | *(context; must be <= implementation date)* |
| Baseline revenue (period before the decision) | | `baseline_revenue` |
| Predicted revenue | | `predicted_revenue` |
| Baseline profit (if available) | | `baseline_profit` |
| Predicted profit (if available) | | `predicted_profit` |
| Baseline units / orders (if available; required for a marketing decision) | | `baseline_units` |
| Predicted units / orders (if available) | | `predicted_units` |
| Predicted risk (0–1, as displayed) | | `predicted_risk` |
| Predicted confidence (0–1, as displayed) | | `predicted_confidence` |
| Historical price min / max / median (optional; reserved) | | `historical_price_min` / `_max` / `_median` |

## Actual outcome  (recorded AFTER the full horizon)

| Item | Value | Template field |
|---|---|---|
| Outcome date (`YYYY-MM-DD`) | | `outcome_recorded_date` |
| Actual revenue (same period basis as baseline) | | `actual_revenue` |
| Actual units / orders (if available) | | `actual_units` |
| Actual profit (if available) | | `actual_profit` |
| Relevant actual business metric (marketing spend / inventory measure, if applicable) — no PII | | *(context / notes)* |
| Implementation deviations (recommended vs actually applied) | | `notes` (short, no PII) |
| Unusual events in the window (festival, promo, supply disruption, competitor change, weather, stockout, demand spike) | | `notes` — recorded as POSSIBLE CONFOUNDERS, not corrected |
| Outcome status (`achieved` / `partially_achieved` / `not_achieved` / `inconclusive`) | | `outcome_status` |

## Provenance

| Item | Value | Template field |
|---|---|---|
| `source_type` (must be `real_indian_sme`) | `real_indian_sme` | `source_type` |
| `business_country` (must be India) | `IN` | `business_country` |
| Consent status (`consented`) | | `data_consent_status` |
| Anonymisation status (`anonymized`) | `anonymized` | `anonymization_status` |
| Collection method (e.g. `sme_self_report_form`, `researcher_interview`) | | `collection_method` |
| Collection date (`YYYY-MM-DD`) | | `collection_date` |

---

**Reminder:** the actual-outcome section must be blank until the horizon has
fully elapsed. Never estimate it forward or back-fill it. If a target is
unavailable, leave it blank — it is reported as unavailable, never invented.
