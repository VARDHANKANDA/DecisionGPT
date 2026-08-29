# REAL INDIAN SME OUTCOME VALIDATION REPORT

Evidence-generation task. Methodology: `docs/REAL_INDIAN_SME_OUTCOME_VALIDATION.md`.
**Status: the collection workflow is implemented; no genuine Indian SME decision
outcomes have been contributed. Per the task's stop condition, no synthetic
`DecisionOutcome` records were created.**

## 1. Research question

Do DecisionGPT's simulated recommendations correspond to actual Indian SME
business outcomes (Digital Twin prediction accuracy; confidence calibration;
R0 vs R3 where technically possible)?

## 2. What was built (additive only)

| Component | Change |
|---|---|
| `decision_outcomes` table | migration **0007** — 10 nullable provenance / horizon columns (`outcome_horizon_days`, `outcome_status`, `notes`, `source_type`, `business_country`, `business_industry`, `data_consent_status`, `anonymization_status`, `collection_method`, `collection_date`) + `ix_decision_outcomes_source_type`. Additive; the existing `record_outcome()` path is untouched; older rows load unchanged. |
| Import schema + validation | `app/services/real_sme_outcome_service.py` — `validate_record` (schema, anonymisation, PII rejection, horizon-consistency / no-leakage), `import_outcome_record` (creates an anonymised `Business` + `Decision` + `DecisionOutcome` with `source_type = real_indian_sme` and the `PredictionEvaluation` via the existing `digital_twin_evaluation_service`). |
| Template | `docs/templates/real_indian_sme_outcome_template.{csv,json}` — one row, marked `EXAMPLE / SYNTHETIC`. |
| Importer | `scripts/import_real_sme_outcomes.py` — CSV/JSON; **skips** any `EXAMPLE` / `SYNTHETIC` row; rejects invalid rows with the full error list; script-only (no open API ingestion path). |
| Report | `real_sme_outcome_service.get_real_sme_outcome_report(db)` — Table-2 material restricted to `REAL_INDIAN_SME_OUTCOME`; honest empty state at `n = 0`. |
| Dashboard | **Research → Digital Twin Evaluation → Real Indian SME Outcomes** panel — empty state until real records exist; never shows synthetic outcomes. |

Not changed: the Digital Twin, Causal Graph, Multi-Agent architecture, Risk
Manager formula, optimizer, production models, any experiment ID or result,
production defaults (`risk_model = None`, `risk_penalty_lambda = 1.0`).

## 3. Data collected

**None.** `DecisionOutcome` where `source_type = real_indian_sme` → **0**.
`PredictionEvaluation` → 0. This is a valid research result (task §3, §23).

## 4. Anonymisation / privacy

Enforced at validation: business-level only; opaque `business_id` token; India
only; explicit consent; rejects any field or value resembling a name, phone,
email, Aadhaar, PAN, GSTIN, bank / account number, address or pincode. No
transaction-level data is requested.

## 5–11. Prediction / Digital-Twin / Risk / Causal evaluation

Not runnable — 0 real outcomes. When ≥ 1 exist the report computes per-target
(revenue / profit / units) MAE / RMSE / MAPE separately, goal achievement from
the actual outcome, and — where `historical_price_*` is supplied — an R0-vs-R3
risk comparison for the recorded strategy. Causal-evidence upgrades continue to
require `MIN_OUTCOMES_FOR_OBSERVATIONAL = 3` consistent per-edge interventions
(`causal_feedback_service`, unchanged). Observational outcomes validate
prediction accuracy for the **chosen** intervention only — never the causal
superiority of alternatives (task §12).

## 12. Results

```
n_businesses = 0
n_decisions  = 0
n_outcomes   = 0
Table 2      = NOT READY
```

## 13. Failure cases

None to report — nothing was run. The validation layer's rejection paths
(synthetic source, PII, horizon mismatch, outcome-before-decision, unsupported
decision type, out-of-range confidence/risk) are covered by
`tests/unit/test_real_sme_outcome_service.py`.

## 14. Limitations

- **No access to genuine Indian SMEs.** This session cannot solicit real
  businesses; the workflow is a channel, not evidence.
- Predicted values must be supplied by the SME's own DecisionGPT run (production
  config R0); they are not recomputed here.
- Aggregate records do not carry price history → no full R0-vs-R3 re-simulation
  from them (`R0 vs R3 = NOT RECOMPUTABLE FROM OUTCOME RECORD` unless optional
  `historical_price_*`; missing values are never reconstructed).
- Target sample 5–10 is small → `DESCRIPTIVE ONLY`; clustering by business
  applies.

## 15. Paper interpretation

**Established:** DecisionGPT can now ingest anonymised real Indian SME decision
outcomes and evaluate Digital Twin prediction accuracy against them, kept
strictly separate from every synthetic category.
**Not established:** any real-world prediction-accuracy, risk-calibration or
causal claim — no genuine outcomes exist yet. The paper must say
*"real Indian SME outcome collection is pending; Table 2 is not ready."*

## 16. Reproducibility

- Schema + validation: `app/services/real_sme_outcome_service.py`.
- Import: `scripts/import_real_sme_outcomes.py path/to/records.{csv,json}`.
- Report / dashboard: `get_real_sme_outcome_report` → Digital Twin Evaluation page.
- Migration `0007` (additive, nullable). `alembic upgrade head`.
- Tests: `tests/unit/test_real_sme_outcome_service.py`,
  `tests/api/test_research_evaluations.py`.

---

## REAL INDIAN SME VALIDATION SUMMARY

```
Real Indian SME businesses:   0
Real decisions:               0
Actual outcomes:              0
Outcome horizons:             none recorded

Digital Twin:                 NOT READY
R0 performance:               n/a — 0 real outcomes
R3 performance:               n/a — 0 real outcomes
R0 vs R3:                     NOT APPLICABLE — 0 real outcomes
                              (aggregate records also lack the price history to recompute R0/R3 risk)
Risk calibration:             NOT ASSESSED — 0 real outcomes
Confidence calibration:       NOT ASSESSED — 0 real outcomes
Causal evidence:              NOT READY (rules unchanged: >= 3 consistent per-edge interventions)

Table 2:                      NOT READY
Real-world statistical inference:  DESCRIPTIVE ONLY (planned; n target 5-10)

Final verdict:  PROMISING BUT INSUFFICIENT REAL-WORLD EVIDENCE
                (workflow ready; REAL SME OUTCOME COLLECTION = PENDING)

Production default:            R0 / D0  (risk_model = None, risk_penalty_lambda = 1.0)
R3 production status:          EXPERIMENTAL / NOT PROMOTED
Production models changed:     NO
Previous experiments changed:  NO   (16 experiment IDs preserved; this task creates none)
New experiment IDs:            none (workflow + schema only)

Tests:
Backend:   pytest -q — 305 passed, 1 skipped
Frontend:  npm run build compiled (tsc clean) ; npm run lint 0 errors
E2E:       scripts/audit_e2e.py — no assertion failures ; alembic 0001<->0007 round-trip clean
```
