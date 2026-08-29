# Real Indian SME Decision-Outcome Validation — Methodology

Companion workflow doc for `docs/REAL_INDIAN_SME_OUTCOME_VALIDATION_REPORT.md`.
See also: `docs/REAL_SME_DATA_COLLECTION_GUIDE.md` (SME-facing),
`docs/REAL_INDIAN_SME_DATA_DICTIONARY.md` (every field),
`docs/REAL_INDIAN_SME_VALIDATION_METHODOLOGY.md` (paper outline),
`docs/REAL_SME_COLLECTION_READINESS_REPORT.md` (readiness),
`docs/templates/real_sme_consent_and_provenance.md`,
`docs/templates/real_sme_collection_checklist.md`.
This is an **evidence-collection** design, not an optimization. Production stays
**R0 / D0** (`risk_model = None`, `risk_penalty_lambda = 1.0`).

## 1. Research question

Do DecisionGPT's simulated recommendations correspond to **actual** Indian SME
business outcomes? Specifically:
- Are predicted revenue / profit / units close to what actually happened?
- Does the Digital Twin's accuracy reproduce on real data?
- Does confidence correspond to prediction reliability?
- Where technically possible, does **R3** produce better-calibrated decisions
  than **R0** *without* discarding useful risk information?

## 2. Data-collection methodology

An Indian SME contributes one **anonymised, aggregate** row per decision
(schema in §5; template `docs/templates/real_indian_sme_outcome_template.{csv,json}`).
Import is **script-only** — `scripts/import_real_sme_outcomes.py` — deliberately
*not* an open API endpoint, so the real-outcome table cannot be populated by an
unvetted path. Each row becomes a `Decision` + `DecisionOutcome`
(`source_type = real_indian_sme`) and a `PredictionEvaluation` via the existing
`digital_twin_evaluation_service` (unchanged).

The template's single illustrative row is marked `EXAMPLE / SYNTHETIC` and the
importer **skips** any row whose `business_id` starts with `EXAMPLE` or whose
text contains `EXAMPLE` / `SYNTHETIC`. Synthetic scenario data is **never**
inserted here.

## 3. Indian SME inclusion criteria

- `business_country` = India (`IN`).
- `decision_type` ∈ {`price_increase`, `price_decrease`, `marketing_increase`,
  `marketing_decrease`, `inventory_decision`} — only decisions the Digital Twin
  can actually simulate (§7). Marketing decisions require `baseline_units`.
- The pre-decision baseline (`baseline_revenue`, and `baseline_profit` /
  `baseline_units` where the decision needs them) is known.
- Explicit data consent recorded; the record is anonymised.
- Realistic diversity (retail / clothing / electronics / grocery / restaurant /
  manufacturing / wholesale / e-commerce) is **preferred but never fabricated** —
  if one business participates, the report says exactly that.

## 4. Anonymisation / privacy

Business-level only. **Rejected at validation** (`validate_record`):
- any field whose name matches `aadhaar|pan|gstin|phone|mobile|email|bank|
  account_no|ifsc|customer_name|customer_id|owner|contact|address|pincode`;
- any value that looks like an email, an Indian phone number, or an 11+ digit
  number (Aadhaar / account);
- a `business_id` that is not an opaque token (letters / digits / `_` / `-`);
- `anonymization_status` ≠ `anonymized`, or missing `data_consent_status`.

No transaction-level data is requested — aggregate baseline / predicted /
actual figures are sufficient.

## 5. Decision schema (template fields)

| Field | Meaning |
|---|---|
| `business_id` | opaque anonymised token (not a name / contact) |
| `industry`, `state`, `district` | coarse context only |
| `decision_date` | when the intervention was made (`YYYY-MM-DD`) |
| `decision_type` | one of the supported types (§7) |
| `goal`, `strategy` | e.g. `increase_profit`, `Price +5%` |
| `prediction_horizon_days` | 7 / 14 / 30 / 60 / 90 (§8) |
| `baseline_revenue` / `_profit` / `_units` | figures **before** the decision |
| `predicted_revenue` / `_profit` / `_units` | what the SME's DecisionGPT run predicted (production config = R0) |
| `predicted_risk`, `predicted_confidence` | in [0, 1], as reported |
| `historical_price_min` / `_max` / `_median` | optional — enables an R0/R3 risk recompute |
| `actual_revenue` / `_profit` / `_units` | observed at the horizon |
| `outcome_recorded_date`, `outcome_status` | `achieved` / `partially_achieved` / `not_achieved` / `inconclusive` |
| `notes` | optional short free text, no PII |
| `source_type` | must be `real_indian_sme` |
| `business_country` | `IN` |
| `data_consent_status`, `anonymization_status`, `collection_method`, `collection_date` | provenance (§15) |

## 6. Outcome horizon

Recorded explicitly per row. `validate_record` rejects a row whose observed
window (`outcome_recorded_date − decision_date`) is not within `[0.5·h, 2·h + 7]`
days of the stated horizon `h` — a 30-day prediction is never silently compared
with a 90-day actual. Horizons are reported and never mixed without labelling.

## 7. Decision types & capability

Only the five types the Digital Twin simulates are accepted; the existing
capability system is unchanged. A `marketing_*` decision without `baseline_units`
is rejected (the outcome could not be evaluated).

## 8. Prediction-vs-actual methodology

Per decision, per target (revenue / profit / units), from
`digital_twin_evaluation_service._metric_eval`:
`predicted_change = predicted − baseline`, `actual_change = actual − baseline`,
`error = actual_change − predicted_change`, `abs_pct_error = |error| /
|actual_change|` (only where `actual_change ≠ 0`). **Forecast accuracy and
decision quality are reported separately** and never combined into one metric.

## 9. Digital Twin evaluation

Aggregated over the real SME outcomes only (`get_real_sme_outcome_report`):
per target — `n`, MAE, RMSE, MAPE (where defined). Revenue, profit and units
are reported as **separate** rows; no cross-unit aggregation.

## 10. Risk Manager evaluation (R0 vs R3)

Aggregate outcome records do **not** carry the price history needed to recompute
the Digital Twin's extrapolation-risk score, so a true R0-vs-R3 re-simulation is
not possible from them → the report states
`R0 vs R3 = NOT RECOMPUTABLE FROM OUTCOME RECORD` (missing historical values are
never reconstructed). If an SME also supplies
`historical_price_{min,max,median}`, R0 and R1 risk for the recorded strategy
can be compared for that row; on the synthetic and Benroshan evidence to date
R0 and R1 coincide except on degenerate (near-zero-variance) histories.

## 11. Causal-evidence rules

Unchanged. Real intervention feedback flows through the existing
`causal_feedback_service` (`MIN_OUTCOMES_FOR_OBSERVATIONAL = 3`,
`CONSISTENCY_THRESHOLD = 2/3`). One outcome agreeing with an edge never lifts it.
With < 3 consistent per-edge interventions: `CAUSAL VALIDATION = NOT READY`.

## 12. Real-world counterfactual limitation

For a historical decision "Price +5%" we observe the outcome of **Price +5%**
only. We do **not** observe what Price +10% / Marketing +20% / Price −5% would
have produced. Observational actual outcomes validate **prediction accuracy for
the chosen intervention** — they do **not** establish causal superiority of
alternative strategies. The report states this explicitly.

## 13. Statistical limitations

Target: 5–10 genuine decisions. That is not a large sample. The report always
prints `n_businesses`, `n_decisions`, `n_outcomes`, `decision_types`,
`outcome_horizons`. With `n < 5`: `DESCRIPTIVE ONLY`, no p-values. Repeated
decisions from one business are **clustered** — never counted as independent
businesses.

## 14. Table 2

Populated from persisted records **only when ≥ 5 real outcomes exist**, tagged
`DATA CATEGORY = REAL_INDIAN_SME_OUTCOME`, kept separate from
`SYNTHETIC_CONTROLLED` / `INDIA_REAL_BUSINESS` / `INDIA_AGRICULTURAL_PRICE` /
`SYNTHETIC_INDIAN_CONTEXT`. Columns: business category, decision type, N,
revenue MAE, profit MAE, units MAE, goal achievement, R0 risk, R3 risk,
confidence. No cross-unit aggregation without normalisation.

## 15. Provenance

Every real outcome stores `source_type`, `business_country`, `business_industry`,
`data_consent_status`, `anonymization_status`, `collection_method`,
`collection_date`, `outcome_horizon_days`, `outcome_status`, `notes` (migration
`0007`, all nullable). The research documentation states, where applicable:
*Real Indian SME outcome — anonymised — used for research evaluation.*

## 16. Reproducibility

- Schema + validation: `app/services/real_sme_outcome_service.py`.
- Import: `scripts/import_real_sme_outcomes.py` (CSV or JSON template).
- Report: `real_sme_outcome_service.get_real_sme_outcome_report(db)`, surfaced on
  **Research → Digital Twin Evaluation → Real Indian SME Outcomes**.
- Schema change: migration `0007` (additive, nullable, `decision_outcomes`).
- No experiment IDs, production defaults, models or synthetic experiments are
  changed.
