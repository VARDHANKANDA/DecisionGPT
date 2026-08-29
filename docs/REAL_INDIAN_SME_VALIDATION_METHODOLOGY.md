# Real Indian SME Validation — Methodology Outline

Paper-ready outline for the real-world validation study. **Results are not
written here — none exist yet** (0 genuine outcomes; Table 2 = NOT READY).
Companion: `docs/REAL_INDIAN_SME_OUTCOME_VALIDATION.md` (workflow),
`docs/REAL_INDIAN_SME_DATA_DICTIONARY.md` (fields),
`docs/REAL_SME_DATA_COLLECTION_GUIDE.md` (SME-facing).

## 1. Study objective

Determine whether DecisionGPT's Digital-Twin predictions for a chosen
intervention correspond to the **actual** outcome observed by a real Indian SME,
for supported price / marketing / inventory decisions, at a stated horizon.
Secondary: whether the displayed confidence tracks prediction accuracy, and —
where technically possible — whether the experimental risk formulation **R3**
differs from production **R0** on real data.

## 2. Indian SME inclusion criteria

- Business genuinely located / operating in India (`business_country = IN`).
- Decision type ∈ {`price_increase`, `price_decrease`, `marketing_increase`,
  `marketing_decrease`, `inventory_decision`} — only what the Digital Twin
  simulates. `marketing_*` requires `baseline_units`.
- The pre-decision baseline is known; predicted figures come from the SME's own
  DecisionGPT run (production config = R0).
- Voluntary participation; anonymised; explicit consent recorded.
- Diversity of business type / region is **preferred, never fabricated**.

## 3. Data collection

Anonymised aggregate record per decision (data dictionary). Contributed as
CSV or JSON via `docs/templates/real_indian_sme_outcome_template.*`. Imported
**by script only** (`scripts/import_real_sme_outcomes.py`) — no open API
ingestion path. The template's example row is auto-skipped; example / synthetic
rows can never enter the real table. Consent + provenance recorded on
`docs/templates/real_sme_consent_and_provenance.md` (kept outside the repo/DB).

## 4. Decision capture

Each record becomes an anonymised `Business` + `Goal` + `Strategy` + `Decision`
(`prompt_version = real_sme_import_v1`), with `expected_outcome_json` built
**only** from the SME's reported predicted / baseline figures.

## 5. Prediction generation

Predictions are the values the SME's own DecisionGPT run produced **before** the
outcome window closed. They are recorded as reported — **not recomputed** here
(the aggregate record does not carry the full business state).

## 6. Outcome capture

`DecisionOutcome` with `source_type = real_indian_sme`, `actual_outcome_json`
= observed revenue / profit / units, plus provenance (`outcome_horizon_days`,
`outcome_status`, `data_consent_status`, `anonymization_status`,
`collection_method`, `collection_date`). Validation enforces:
`outcome_recorded_date ≥ decision_date` and the observed window within
`[0.5·h, 2·h + 7]` days of the stated horizon `h` — no silent horizon mismatch,
no outcome-before-decision (no leakage). Duplicates (same
`business_id | decision_date | decision_type | strategy | horizon`) are rejected.

## 7. Digital Twin evaluation

Per target, **separately** (`get_real_sme_outcome_report`, reusing
`digital_twin_evaluation_service._metric_eval`):
`error = (actual − baseline) − (predicted − baseline)`; MAE, RMSE; MAPE **only**
where `actual_change ≠ 0`. Revenue, profit and units are never combined into one
number. Missing targets are reported as `n = 0` for that target, not imputed.

## 8. Risk Manager evaluation

Production stays **R0**. Aggregate records lack the price history to recompute
the Digital-Twin extrapolation-risk score, so R0 vs R3 is reported as
**`R0 vs R3 = NOT RECOMPUTABLE FROM OUTCOME RECORD`** (missing historical values
are never reconstructed) unless an SME also supplies
`historical_price_{min,max,median}` (reserved). The prior generalization study
(`risk_manager_real_data_validation`, `70617412`) already found R0 and R1
**identical** on real Indian implied-price data; that result is not hidden. R3
remains **experimental / not promoted**.

## 9. Causal evidence

Unchanged rules. Real intervention feedback flows through
`causal_feedback_service` (`MIN_OUTCOMES_FOR_OBSERVATIONAL = 3`,
`CONSISTENCY_THRESHOLD = 2/3`). One agreeing outcome never upgrades an edge.
A real outcome (price ↑ then revenue ↑) does **not** establish that the price
change *caused* the revenue change — only prediction accuracy for the chosen
intervention is validated (no counterfactual for alternative strategies).
`CAUSAL VALIDATION = NOT READY` until the thresholds are met.

## 10. Privacy / anonymisation

Business-level, aggregate only. `validate_record` rejects any field name or
value resembling Aadhaar / PAN / GSTIN / phone / email / customer data / bank
or account numbers / identifying address, and any non-opaque `business_id`.
The stored business is *"Anonymised Indian SME [code]"*. Consent template
requires appropriate institutional / legal review before real deployment; the
project makes **no** compliance claim it has not established.

## 11. Statistical analysis

Target n = 5–10 decisions. Always report `n_businesses`, `n_decisions`,
`n_outcomes`, decision-type distribution, horizon distribution, descriptive
metrics, and **every individual prediction error**. With small n:
**`DESCRIPTIVE ONLY`** — no p-values, no significance. Repeated decisions from
one business are clustered — **not** counted as independent businesses
(`n_businesses` is distinct businesses).

## 12. Limitations

- Single-dataset / small-n; not representative of Indian SMEs generally.
- Predicted values self-reported; not independently recomputed.
- Observational outcomes: prediction-accuracy evidence only, not causal.
- Real-LLM validation **NOT TESTED** (no provider configured; template-mode
  agent scores are not real-LLM evidence).
- R0 vs R3 not separable from aggregate records.

## 13. Reproducibility

- Schema + validation + import + report: `app/services/real_sme_outcome_service.py`.
- Importer: `scripts/import_real_sme_outcomes.py <file>.{csv,json}`.
- Dashboard: Research → Digital Twin Evaluation → Real Indian SME Outcomes.
- Schema: migration `0007` (additive, nullable). `alembic upgrade head`.
- No experiment IDs, production defaults, models, causal thresholds or synthetic
  experiments are changed by this workflow.
