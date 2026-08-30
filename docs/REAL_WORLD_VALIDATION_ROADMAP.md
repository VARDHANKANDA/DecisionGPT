# DecisionGPT Real-World Validation Roadmap

Sequential phases. **Each phase's conclusions depend on the actual evidence
collected in the earlier phases** — a later phase cannot be summarised before
its inputs exist. Production stays **R0 / D0** throughout; R3 stays
**EXPERIMENTAL / NOT PROMOTED**; no phase runs a new synthetic experiment.

| Phase | Name | Status | Exit condition |
|---|---|---|---|
| **1** | Engineering readiness | **COMPLETE** | Real-SME importer + validation + no-leakage + duplicate + PII rejection + provenance schema (migration 0007) + separated dashboard block + frozen real-LLM protocol + Table-2 gate (≥ 5, real-SME only). |
| **2** | Recruit 5–10 genuine Indian SMEs | **CURRENT** | Institutional/legal review obtained; 5–10 eligible businesses across categories/states consented; `docs/REAL_INDIAN_SME_RECRUITMENT_GUIDE.md` followed. |
| **3** | Collect first decisions | pending Phase 2 | For each participant: baseline period defined, DecisionGPT prediction generated and recorded **before** any outcome, strategy recommended, accept/reject/implement recorded. `collection_status = DECISION_IMPLEMENTED` for the implemented ones. |
| **4** | Collect actual outcomes | pending Phase 3 | After each decision's full horizon, the SME's **real** actual revenue (and units/profit where tracked) recorded for the same period; contextual confounders noted; quality protocol run → `VALIDATED`; imported. |
| **5** | Reach ≥ 5 matched real-SME outcomes | pending Phase 4 | `matched_real_sme_eval_count(db) >= 5` — five genuine `REAL_INDIAN_SME_OUTCOME` records each with a `PredictionEvaluation` revenue error. |
| **6** | Enable Table 2 | automatic at Phase 5 | `table_2_status(db).available == True`. Table 2 generated from the **real-SME category only**; reported **descriptively** (n businesses, n decisions, decisions/business, category, state, horizon distribution; per-target MAE/RMSE, MAPE only where valid). No population-level claim. |
| **7** | Real-LLM validation | independent of Phases 2–6; needs a provider | A legitimate provider configured (`LLM_PROVIDER` + `LLM_API_KEY` → `settings.llm_enabled == True`); the two arms of `docs/REAL_LLM_VALIDATION_PROTOCOL.md` run unchanged; goal-parsing agreement + narration-faithfulness + parity reported. (A real LLM affects goal parsing + narration only — not agent scores or strategy selection.) |
| **8** | Decide whether R3 deserves further investigation | pending Phases 5–7 | Only after real matched outcomes exist: compare R0 (production) vs R3 (experimental) **where technically possible** (an aggregate outcome record without price history → `R0 vs R3 = NOT RECOMPUTABLE FROM OUTCOME RECORD`; values are never reconstructed). Report R0 and R3 separately. Any correction becomes a **new preregistered experiment** — not a re-run under an existing ID. |

## Standing constraints (all phases)

- No fabricated participants, decisions, consent, predictions or outcomes.
- No public/Kaggle dataset substituted for a genuine SME participant; Benroshan
  stays `INDIA_REAL_BUSINESS` (not Table-2 evidence).
- Data categories never merged: `REAL_INDIAN_SME_OUTCOME`, `INDIA_REAL_BUSINESS`,
  `INDIA_PUBLIC_CONTEXT`, `INDIA_AGRICULTURAL_PRICE`, `SYNTHETIC_CONTROLLED`,
  `SYNTHETIC_INDIAN_CONTEXT`.
- Causal thresholds unchanged (`MIN_OUTCOMES_FOR_OBSERVATIONAL = 3`,
  `CONSISTENCY_THRESHOLD = 2/3`); before/after improvement is never causal
  evidence on its own; confounders are documented, not corrected.
- Small n → descriptive statistics only; decisions from one SME are clustered,
  not independent businesses; synthetic-suite p-values are never reused as
  real-world evidence.
- Production `risk_model = None`, `risk_penalty_lambda = 1.0`; active model set
  unchanged; 16 prior experiment IDs frozen; `experiments/experiment_manifest.json`
  not modified except by a genuine new preregistered experiment.

## Current state (Phase 2)

```
Real Indian SME businesses:  0
Real decisions:              0
Real actual outcomes:        0
Matched evaluations:         0
Table 2:                     NOT READY
Real LLM:                    BLOCKED
Causal validation:           NOT READY
R3:                          EXPERIMENTAL / NOT PROMOTED
Production:                  R0 / D0
```

**`REAL SME EVIDENCE = PENDING`.** The next action is human recruitment and data
collection, not code.
