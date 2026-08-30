# Real Indian SME Data Quality Protocol

Every candidate decision record is classified **`VALID`**, **`REQUIRES_REVIEW`**,
or **`REJECTED`** before import. **Values are never silently repaired.** Most of
these checks are already enforced automatically by
`real_sme_outcome_service.validate_record` / `import_outcome_record`; this
document is the human-facing scorecard and the escalation rule.

Collection-schedule statuses (`docs/templates/REAL_INDIAN_SME_COLLECTION_SCHEDULE.csv`):
`RECRUITMENT` → `CONSENT_PENDING` → `DATA_READY` → `DECISION_PENDING` →
`DECISION_IMPLEMENTED` → `OUTCOME_PENDING` → `OUTCOME_READY` → `VALIDATED` →
`IMPORTED`.

---

## Checks

| # | Check | `VALID` when… | `REJECTED` when… | `REQUIRES_REVIEW` when… | Auto-enforced? |
|---|---|---|---|---|---|
| 1 | **Provenance** | `source_type = real_indian_sme`, `collection_method` + `collection_date` present | `source_type` is synthetic / demo / unknown / blank | provenance fields present but inconsistent (e.g. collection_date before decision_date) | yes (source_type, method) |
| 2 | **Consent** | `data_consent_status ∈ {consented, consent_given, granted}` and a signed consent/provenance form exists off-repo | consent missing or "no" | consent recorded in the record but the off-repo form is not yet filed | partial (string only) |
| 3 | **Anonymisation** | `anonymization_status = anonymized`; `business_id` is an opaque token | status ≠ anonymized; `business_id` is a name / email / phone | token is opaque but re-used across unrelated businesses | yes |
| 4 | **India eligibility** | `business_country = IN` and the business genuinely operates in India | country ≠ India | country = IN but operating status unclear | partial (country only) |
| 5 | **Decision type** | one of `price_increase / price_decrease / marketing_increase / marketing_decrease / inventory_decision` | any other type | supported type but the decision was made *for the study* rather than a genuine business need | yes |
| 6 | **Decision timing** | `decision_date` is a valid date, and the prediction was generated on/before the implementation date | `decision_date` invalid | implementation date missing though the strategy was implemented | partial |
| 7 | **Outcome timing (no leakage)** | `outcome_recorded_date ≥ decision_date` and the outcome was measured **after** the horizon | outcome dated on/before the decision | outcome date present but the measurement window is ambiguous | yes (date order) |
| 8 | **Horizon alignment** | observed window within `[0.5·h, 2·h + 7]` days of the stated horizon `h` | window far outside that range (e.g. 30-day prediction vs 150-day actual) | window slightly outside the band with a documented reason | yes |
| 9 | **Missing values** | all required fields present; optional targets either present or explicitly blank | a **required** field (baseline/predicted/actual revenue, risk, confidence, horizon, status, provenance) missing | an optional target (profit / units) missing where it would materially help | yes (required set) |
| 10 | **PII** | no field name or value resembling Aadhaar / PAN / GSTIN / phone / email / customer data / bank-account / identifying address | any such field name or value present | free-text `notes` contains something borderline | yes |
| 11 | **Duplicate decision** | `business_id \| decision_date \| decision_type \| strategy \| horizon` is new | an identical record was already imported | same business + date but a genuinely different strategy/lever (not a duplicate — proceed) | yes |
| 12 | **Implementation status** | strategy was accepted **and** implemented; deviations documented | strategy not implemented (no real intervention → no outcome to evaluate) | partially implemented — document what was actually done | no (record it) |
| 13 | **Prediction availability** | predicted revenue (and risk, confidence) recorded, generated before the outcome | prediction values missing | prediction recorded but from an unclear DecisionGPT run/version | yes (required set) |
| 14 | **Actual outcome availability** | actual revenue for the same horizon recorded from the SME's real books | actual outcome fabricated / estimated / back-filled | actual revenue present but the period basis differs from the baseline | no (verify with SME) |

## Escalation rule

- **Any `REJECTED`** → the record is not imported. Record the reason in the
  collection schedule (`validation_status = REJECTED`) and, where recoverable,
  ask the SME for a corrected submission (a **new** record, not an edit of the
  actual values).
- **Any `REQUIRES_REVIEW`** (and no `REJECTED`) → two researchers review; the
  record is held at `validation_status = REQUIRES_REVIEW` until resolved. If it
  cannot be resolved without inventing a value, it becomes `REJECTED`.
- **All checks `VALID`** → `validation_status = VALIDATED`; import via
  `python scripts/import_real_sme_outcomes.py <file>`; on success set
  `import_status = IMPORTED`.

## What is never done

- No missing value is imputed, estimated, or reconstructed.
- No actual outcome is edited after import (a correction is a new preregistered
  record with the reason logged).
- No synthetic / demo / external-benchmark record is admitted, regardless of
  how few real records exist.
