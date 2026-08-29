# REAL SME COLLECTION READINESS REPORT

Operational-preparation task. **No experiment was run. No model, agent, Digital
Twin, Causal Graph, optimizer or Risk Manager was modified. No `DecisionOutcome`
was fabricated.** Production stays **R0 / D0**; R3 stays **experimental / not
promoted**.

## 1. What was audited

| Artefact | Result |
|---|---|
| `docs/REAL_INDIAN_SME_OUTCOME_VALIDATION.md` / `..._REPORT.md` | accurate; still say `PENDING` / Table 2 `NOT READY` |
| `docs/templates/real_indian_sme_outcome_template.{csv,json}` | usable; single row marked `EXAMPLE / SYNTHETIC` |
| `app/services/real_sme_outcome_service.py` | validation, PII rejection, anonymisation, India-only, horizon-consistency, no-leakage checks all present |
| `scripts/import_real_sme_outcomes.py` | CSV + JSON; skips `EXAMPLE`/`SYNTHETIC` rows; per-row validation with a full error list; script-only (no open API ingestion) |
| `DecisionOutcome` model + `0007` migration | additive nullable provenance/horizon columns; `record_outcome()` path untouched |
| outcome API (`POST/GET …/decisions/{id}/outcome`) | unchanged; not used for real-SME import (script path only) |
| Research → Digital Twin Evaluation → **Real Indian SME Outcomes** panel | shows the required fields; honest empty state at n = 0; never shows synthetic data |

**One concrete bug found and fixed:** the importer had **no duplicate
detection** — re-running the same file would double-import. Added a natural-key
check (`business_id | decision_date | decision_type | strategy | horizon`,
stored as an anonymised `_sme_natural_key` in `Decision.expected_outcome_json`,
ignored by every evaluator). A repeated record is now rejected with
`duplicate: …already exists`.

No other redesign was made — the workflow was already sound.

## 2. What was changed

| Change | Kind |
|---|---|
| `real_sme_outcome_service._natural_key` + duplicate rejection in `import_outcome_record` | bug fix (additive) |
| `docs/REAL_SME_DATA_COLLECTION_GUIDE.md` | new — SME-facing, plain language |
| `docs/templates/real_sme_consent_and_provenance.md` | new — research consent/provenance template (labelled: needs institutional/legal review; no compliance claims) |
| `docs/templates/real_sme_collection_checklist.md` | new — per-record checklist |
| `docs/REAL_INDIAN_SME_DATA_DICTIONARY.md` | new — every field: type, meaning, unit, required?, source, privacy class, allowed values, example, prediction/eval use |
| `docs/REAL_INDIAN_SME_VALIDATION_METHODOLOGY.md` | new — 13-section paper methodology outline (no results — none exist) |
| Tests: no-leakage proof, horizon/window alignment, duplicate detection, natural-key anonymity | new |

Not changed: any experiment ID or result (`experiment_manifest.json`
byte-identical, 16 experiments), active model registry, production defaults,
causal thresholds (`MIN_OUTCOMES_FOR_OBSERVATIONAL = 3`), the Digital Twin,
Causal Graph, Multi-Agent architecture, optimizer, Risk Manager.

## 3. Current collection workflow

```
SME fills docs/templates/real_indian_sme_outcome_template.{csv,json}
      (delete the EXAMPLE row; one row per real decision)
   │
   ▼
project team completes the consent/provenance form (kept outside repo/DB)
   │
   ▼
DATABASE_URL=... python scripts/import_real_sme_outcomes.py <file>
   │  validate_record: schema · anonymisation · India-only · consent ·
   │                   supported decision type · horizon ∈ {7,14,30,60,90} ·
   │                   horizon↔window consistency · outcome-after-decision ·
   │                   PII rejection · duplicate rejection
   ▼
anonymised Business + Goal + Strategy + Decision + DecisionOutcome
      (source_type = real_indian_sme)  +  PredictionEvaluation
   │
   ▼
Research → Digital Twin Evaluation → Real Indian SME Outcomes
      (per-target MAE/RMSE/MAPE · goal achievement · R0 vs R3 ·
       causal status · provenance · clustering note · Table 2 status)
```

## 4. Data schema

Full field list, types and privacy classes: `docs/REAL_INDIAN_SME_DATA_DICTIONARY.md`.
Minimum required per record: business type, state, district, decision date,
decision type, goal, strategy, horizon, baseline/predicted/actual **revenue**,
predicted risk & confidence, outcome date, outcome status, and the five
provenance fields. Profit and units are optional (units required for a
marketing decision). Never accepted: Aadhaar/PAN/GSTIN, phone, email, customer
data, bank/account numbers, identifying address, non-opaque `business_id`.

## 5. Privacy safeguards

- Field-name rejection: `aadhaar|pan|gstin|phone|mobile|email|bank|account_no|
  ifsc|customer_name|customer_id|owner|contact|address|pincode`.
- Value rejection: email pattern, Indian phone pattern (`[6-9]\d{9}`, optional
  `+91`), any 11+ digit number.
- `business_id` must match `^[A-Za-z0-9][A-Za-z0-9_-]{1,63}$`.
- `anonymization_status` must be `anonymized`; `data_consent_status` must record
  explicit consent; `business_country` must be India.
- Stored business = *"Anonymised Indian SME [code]"* + business type + state +
  the numbers. No personal or transaction-level data.
- Consent/provenance template explicitly states it needs
  institutional/legal review and makes **no** compliance claim.

## 6. No-leakage safeguards

| Guarantee | Mechanism | Test |
|---|---|---|
| The actual outcome cannot pre-date the decision | `validate_record`: reject `outcome_recorded_date < decision_date` | `test_no_leakage_outcome_recorded_date_must_be_after_decision_date` |
| A prediction is only compared with an actual at the **same** horizon | `validate_record`: observed window must be within `[0.5·h, 2·h+7]` days of `h` | `test_horizon_and_actual_window_must_align` |
| The actual outcome never influences the stored *prediction* | `expected_outcome_json` is built **only** from `predicted_*` / `baseline_*`; `actual_outcome_json` only from `actual_*`; `PredictionEvaluation` computes `predicted_change` and `actual_change` independently | `test_no_leakage_expected_outcome_json_never_contains_actuals` |
| Duplicate records cannot inflate n | natural-key rejection | `test_duplicate_decision_record_is_rejected` |

## 7. Three data categories (kept separate — task §7)

| Category | What it is | Role | Where |
|---|---|---|---|
| **A. `REAL_INDIAN_SME_OUTCOME`** | a genuine SME decision + its **actual** business outcome | the target evidence; the only source for Table 2 | `DecisionOutcome.source_type = real_indian_sme`; the "Real Indian SME Outcomes" panel |
| **B. `INDIA_REAL_BUSINESS`** | external Indian business dataset (Benroshan) | descriptive / forecasting evaluation only — **not** DecisionOutcome evidence | Experiment 1a; `risk_manager_real_data_validation` (`70617412`) |
| **C. `SYNTHETIC_*`** | controlled research scenarios / synthetic datasets | controlled causal / architecture / calibration experiments | multi-scenario / ablation / diagnostic / calibration experiments |

These are never merged. The real-SME panel and Table 2 exclude B and C.

## 8. Testing results

```
Backend:   pytest -q — 311 passed, 1 skipped
Frontend:  npm run build compiled (tsc clean) ; npm run lint — 0 errors
E2E:       scripts/audit_e2e.py — no assertion failures
Alembic:   0001 → head → base → head clean (head = 0007)

Verified:
  existing experiments unchanged  — experiment_manifest.json byte-identical (16 experiments)
  active models unchanged         — asserted in tests
  production defaults unchanged   — PipelineOptions(risk_model=None, risk_penalty_lambda=1.0)
  no synthetic DecisionOutcome    — DecisionOutcome where source_type=real_indian_sme = 0; total = 0
  Table 2 remains NOT READY
  no PII accepted                 — validate_record / importer tests
  real SME import is script-only  — no API ingestion route added
  data categories remain separate — §7
```

## 9. Current evidence count

```
Real Indian SME businesses:   0
Real decisions:               0
Real actual outcomes:         0
Table 2:                       NOT READY
Real-LLM validation:           NOT TESTED  (no provider configured)
Causal validation:             NOT READY   (needs >= 3 consistent per-edge interventions)
R3:                            EXPERIMENTAL / NOT PROMOTED
Production:                     R0 / D0
```

## 10. Exact next human action required

> **This is a data-collection step, not a coding step.**

1. A project member obtains appropriate **institutional / legal review** for
   collecting anonymised SME decision data in the relevant jurisdiction(s)
   (`docs/templates/real_sme_consent_and_provenance.md`).
2. Recruit **genuine Indian SMEs** who have used DecisionGPT for a supported
   decision (price / marketing / inventory) and can report the **actual**
   result at a fixed horizon.
3. For each SME: complete the consent/provenance form; help them fill one row
   per decision in `docs/templates/real_indian_sme_outcome_template.csv` using
   `docs/REAL_SME_DATA_COLLECTION_GUIDE.md` and the checklist.
4. Run `python scripts/import_real_sme_outcomes.py <file>` and confirm the
   **Real Indian SME Outcomes** panel shows the expected counts.
5. Once **≥ 5** genuine outcomes exist, Table 2 auto-populates
   (`REAL_INDIAN_SME_OUTCOME` only) and the analysis proceeds **descriptively**
   per `docs/REAL_INDIAN_SME_VALIDATION_METHODOLOGY.md`.

Until step 5 completes, the correct state is:
`REAL SME COLLECTION WORKFLOW = READY`, `REAL SME OUTCOMES = 0`,
`TABLE 2 = NOT READY`.
