# REAL EVIDENCE STATUS REPORT

Execution task. **Track A (real SME outcomes) and Track B (real-LLM) both hit
their STOP conditions:** no genuine Indian SME data was supplied, and no
legitimate LLM provider is configured. No experiment was run, no
`DecisionOutcome` fabricated, no production behaviour changed. All values below
are read live from the database / configuration on commit `<filled on commit>`.

```
REAL INDIAN SME EVIDENCE
Businesses:                 0
Decisions:                  0
Implemented decisions:      0        (no lifecycle field; the importer's contract is
                                      implemented + outcome recorded — none supplied)
Actual outcomes:            0
Matched evaluations:        0        (PredictionEvaluation with a revenue error, source_type = real_indian_sme)
Table 2 status:             NOT READY   (needs >= 5 genuine REAL_INDIAN_SME_OUTCOME matched records; have 0)

REAL LLM
Provider configured:        NO        (LLM_PROVIDER="", LLM_API_KEY="", LLM_MODEL="" -> settings.llm_enabled = False)
Validation status:          BLOCKED   (frozen protocol registered: docs/REAL_LLM_VALIDATION_PROTOCOL.md)
Experiment ID:              none      (no run — a real-LLM run requires a legitimately configured provider)

DIGITAL TWIN
Real-outcome evaluation status:  NOT READY   (0 real outcomes)
Revenue MAE:                n/a — 0 real outcomes
Revenue RMSE:               n/a — 0 real outcomes
Profit MAE:                 n/a — 0 real outcomes
Units MAE:                  n/a — 0 real outcomes

RISK MANAGER
Production:                 R0 / D0
R0:                         risk_model = None, risk_penalty_lambda = 1.0   (production default, unchanged)
R3:                         EXPERIMENTAL / NOT PROMOTED   (robust extrapolation scale + lambda = 0.25; opt-in only)
R0 vs R3 real-outcome comparison:  NOT RECOMPUTABLE FROM OUTCOME RECORD
                                   (aggregate records carry no historical price range; missing values are
                                    never reconstructed. Prior probe risk_manager_real_data_validation
                                    70617412 found R0 == R1 on real Benroshan implied-price data — not
                                    reinterpreted here.)

CAUSAL
ASSUMED:                    20   (graph-construction evidence from synthetic / demo business history in the dev DB)
OBSERVATIONAL:              5    (same — correlation-based graph construction, NOT real intervention evidence)
DATA_SUPPORTED:             1    (same — Granger-based graph construction, NOT real intervention evidence)
CAUSALLY_VALIDATED:         0
                           Rules unchanged: MIN_OUTCOMES_FOR_OBSERVATIONAL = 3, CONSISTENCY_THRESHOLD = 2/3.
                           No edge was promoted; 0 real DecisionOutcome records exist to drive any upgrade.

DATA CATEGORIES
REAL_INDIAN_SME_OUTCOME:   0 records            (the only source for Table 2)
INDIA_REAL_BUSINESS:       1 dataset (Benroshan external-india-e-commerce-forecasting v1; forecasting/
                           risk-ordering probe only — NOT Table 2 evidence)
INDIA_PUBLIC_CONTEXT:      2 series (India festival calendar, RBI repo rate; covariates only)
INDIA_AGRICULTURAL_PRICE:  DATA_PENDING (AGMARKNET; DATA_GOV_IN_API_KEY not in environment)
SYNTHETIC_CONTROLLED:      platform-forecasting-v1, platform-churn-v1, synthetic causal ground truth,
                           synthetic decision scenarios / multi-scenario suite
SYNTHETIC_INDIAN_CONTEXT:  1 dataset (Kundan customer synthetic; standalone benchmark, not an MLModel)
                           Metrics for these categories are never merged.

SCIENTIFIC VERDICT
What is supported:
  - Synthetic calibration findings: R0's extrapolation-risk formula is miscalibrated on constant /
    low-variance price histories; the robust-scale R1 removes that pathology while preserving risk
    ordering (Spearman rho 0.969, 0 monotonicity violations); R3 (R1 + lambda 0.25) improves synthetic-suite
    mean goal achievement 0.084 -> 0.168 (paired Wilcoxon p = 0.025) and risk-adjusted score
    -2614.8 -> +40.5 — PROMISING on the synthetic suite.
  - Synthetic architecture findings: the Digital Twin is the only component with measurable objective
    value; the multi-agent layer does not add goal achievement on the synthetic suite; the risk-penalty
    term is the proximate mechanism of the Full-vs-Digital-Twin gap.
  - Indian external forecasting benchmark: xgboost MAE 15.27 on ~51 Benroshan test days (INDIA_REAL_BUSINESS,
    provenance unverified, point estimate).
  - Real-data risk-ordering observation: on 23 real Benroshan implied-price sub-series (184 test rows),
    R0 and R1 produce byte-identical risk scores — the zero/low-variance denominator collapse does not
    occur on real implied-price data.
What remains unvalidated:
  - R3's benefit on real Indian SME data (0 genuine outcomes).
  - Digital Twin prediction accuracy against real business outcomes (Table 2 NOT READY).
  - Real-LLM behaviour (BLOCKED; and by architecture a real LLM affects goal parsing + narration only,
    not agent scores or strategy selection).
  - Any causal claim from real interventions (CAUSALLY_VALIDATED = 0).
What cannot be claimed:
  - Universal / population-level Indian SME performance.
  - Real-world causal validity.
  - R3 superiority over R0 in real businesses.
  - Real-LLM superiority.
  - DecisionGPT superiority over the Digital Twin in real businesses.

PRODUCTION
Risk model:                None   (R0)
Risk penalty lambda:       1.0
Active models:             unchanged (the 6 v1 baseline models; asserted by the integration tests)
Production changes:        NONE   (16 prior experiment IDs preserved; experiment_manifest.json byte-identical;
                                   this task adds no experiment)

REMAINING HUMAN ACTIONS:
  1. Real SME evidence (primary): obtain institutional / legal review
     (docs/templates/real_sme_consent_and_provenance.md); recruit genuine Indian SMEs who used
     DecisionGPT for a supported price / marketing / inventory decision and can report the ACTUAL
     outcome at a fixed horizon; complete docs/templates/real_indian_sme_outcome_template.{csv,json}
     per docs/REAL_SME_DATA_COLLECTION_GUIDE.md + the checklist; run
     `python scripts/import_real_sme_outcomes.py <file>`. At n >= 5 genuine matched outcomes Table 2
     auto-populates (real-SME only) and the analysis proceeds DESCRIPTIVELY
     (docs/REAL_INDIAN_SME_VALIDATION_METHODOLOGY.md), accounting for clustering by business.
  2. Real LLM: register with a supported provider, set LLM_PROVIDER / LLM_API_KEY (and optionally
     LLM_MODEL / LLM_BASE_URL) in backend/.env (never committed), confirm get_settings().llm_enabled
     is True, then run the two arms of docs/REAL_LLM_VALIDATION_PROTOCOL.md unchanged.
  3. AGMARKNET (optional): register a free DATA_GOV_IN_API_KEY at data.gov.in, then run
     `scripts/download_india_datasets.py` -> `scripts/build_external_datasets.py --only agmarknet`
     -> `scripts/register_external_datasets.py`. Stays INDIA_AGRICULTURAL_PRICE.
  4. Decision lifecycle field (only if a future study must track accepted-but-not-implemented
     decisions): the Decision model has no explicit status column — documented, not migrated now.
```

---

## Track-by-track outcome

| Track | Action | Result |
|---|---|---|
| **A — real SME outcomes** | check for supplied genuine data | **STOP** — none supplied. Importer, validation, PII/duplicate/no-leakage checks and the ≥ 5 gate are all in place and unused. |
| **B — real-LLM validation** | inspect `LLM_PROVIDER` / `LLM_API_KEY` / `settings.llm_enabled` (no secret printed) | **STOP** — `llm_enabled = False`. `REAL_LLM_VALIDATION = BLOCKED`. No credentials invented; template mode is not reported as real-LLM evidence. |
| **C — real DecisionOutcome eval** | depends on Track A | not run — 0 outcomes. Per-target revenue/profit/units evaluation would use the existing `digital_twin_evaluation_service`; unavailable targets reported as unavailable. |
| **D — R0 vs R3** | depends on Track A | `R0 vs R3 = NOT RECOMPUTABLE FROM OUTCOME RECORD` (aggregate records carry no price history; values never reconstructed). Benroshan R0 == R1 result not reinterpreted. |
| **E — causal** | verify rules unchanged | `MIN_OUTCOMES_FOR_OBSERVATIONAL = 3`, `CONSISTENCY_THRESHOLD = 2/3` unchanged. `CAUSALLY_VALIDATED = 0`. Nothing promoted. |
| **F — Table 2** | verify gate | `NOT READY` — 0 / 5 genuine real-SME matched records; gate counts real-SME category only. |
| **G — statistics** | n/a | with 0 (and later 5–10) records: descriptive only; decisions from one SME are clustered, not independent businesses. No synthetic-suite p-value reused as real-world evidence. |
| **H — paper claims** | audit language | reports already say PROMISING / NOT VALIDATED / BLOCKED; no overclaim introduced. |
| **I — AGMARKNET** | check key | `DATA_GOV_IN_API_KEY` not in environment → `DATA_PENDING`. No account created, no API-limit bypass. |
| **J — dashboard** | verify it reads stored data | Research → Digital Twin Evaluation → **Real Indian SME Outcomes** panel renders 0 / NOT READY / PENDING from `get_real_sme_outcome_report`; no hard-coded research numbers. |

## Changes made this task

- `real_sme_outcome_service.get_real_sme_outcome_report`: the populated-branch
  `r0_vs_r3` string is now
  `"R0 vs R3 = NOT RECOMPUTABLE FROM OUTCOME RECORD …"` (was
  `"NO MEASURABLE DIFFERENCE …"`) — matches Track D's required terminology and
  is more precise (we cannot recompute, so we cannot measure a difference).
  Extracted to `_r0_vs_r3_status`. The empty-state string (`"NOT APPLICABLE —
  0 real outcomes"`) is unchanged.
- Matching wording update in
  `docs/REAL_INDIAN_SME_OUTCOME_VALIDATION.md` / `_REPORT.md` /
  `docs/REAL_INDIAN_SME_VALIDATION_METHODOLOGY.md`.
- One new test asserting the populated-branch `r0_vs_r3` string.
- No experiment, no schema change, no production-config change, no fabricated
  data.

## Tests

```
Backend:   pytest -q — 316 passed, 1 skipped  (all green; no test weakened or deleted)
Frontend:  npm run build — compiled ; tsc — clean ; npm run lint — 0 errors
E2E:       scripts/audit_e2e.py — no assertion failures
Alembic:   0001 -> head -> base -> head — clean (head = 0007)
```

## Commit

`<filled on commit>`

---

**Scientific status: `REAL SME EVIDENCE = PENDING`, `REAL LLM VALIDATION =
BLOCKED`, `TABLE 2 = NOT READY`, `PRODUCTION = R0 / D0`.** This is the correct
state — no synthetic experiment was run to manufacture a result.
