# Final Pre-Validation Project Audit

Read-only audit + minimal completion pass before the final human-validation
phase. **No fabricated data. No production change. No new experiment. 16 prior
experiment IDs frozen. Retired datasets untouched.**

Commit: see git hash at the end. Backend: **318 passed, 1 skipped**.

---

## 1. Engineering readiness

| Area | Status | Notes |
|---|---|---|
| Backend pipeline | **OK** | Business data → canonical ingestion → preprocessing → forecasting → Digital Twin → Causal Graph → Multi-Agent → Risk Manager → Strategy Optimizer → recommendation → explanation → decision memory → outcome recording → evaluation → dashboard → paper exports — all wired; no broken links found. |
| Production decision path | **OK / isolated** | `POST /businesses/{id}/decisions/analyze` → `decision_service.analyze_goal(db, business_id, goal_id)` with **no options** → `PipelineOptions()` defaults → `risk_model=None`, `risk_penalty_lambda=1.0` → **R0 / D0**. |
| Research vs production isolation | **OK** | Every non-default `PipelineOptions(...)` construction is in a research service (`ablation_service`, `risk_calibration_service`, `risk_manager_diagnostic_service`, `risk_manager_generalization_service`). None on the production path. `experiment_service` never promotes a model or mutates `MLModel.status`. |
| Database / migrations | **OK** | Alembic head `0007`; `0001 → head → base → head` round-trip clean (30 tables + 10 nullable `decision_outcomes` provenance columns). |
| APIs | **OK** | Research endpoints read stored `ExperimentRun.metrics_json` / evaluation rows; frontend fetches from the API. |
| Tests | **OK** | 318 passed, 1 skipped (AGMARKNET committed-file test, gated on `DATA_PENDING`). No test weakened or deleted. |
| Reproducibility | **OK** | `experiments/experiment_manifest.json` (16 experiments) traces every paper number to an `experiment_id` / seed / dataset & model version. `docs/RESEARCH_REPRODUCIBILITY.md` commands match the code. |
| Dead code / leakage / schema | **checked** | No accidental production dependency on experimental code; no hidden synthetic data in the real-outcome path; `expected_outcome_json` built only from `predicted_*` / `baseline_*` (no-leakage tests present). |

## 2. Data readiness

| Category | State | Correct? |
|---|---|---|
| **SME-private** (sales / customers / products / inventory / finance / marketing / business profile) | canonical schema + capability detection; primary source for real recommendations | ✅ |
| **`INDIA_REAL_BUSINESS`** — Benroshan e-commerce | `external-india-ecommerce-v1`; **provenance UNVERIFIED**; ~500 orders / 12 months / 3 categories; committed **processed** CSVs only (raw gitignored — raw contains customer *first names*, never in any processed/analysis artifact) | ✅ correctly labelled; **not** Table-2 evidence |
| **`INDIA_PUBLIC_CONTEXT`** — festival calendar + RBI repo rate | committed CSVs; covariates only | ✅ |
| **`INDIA_AGRICULTURAL_PRICE`** — AGMARKNET | `DATA_PENDING` (`DATA_GOV_IN_API_KEY` not in environment); integration + tests present, raw bytes not pulled | ✅ kept `DATA_PENDING`; never described as SME retail data |
| **`SYNTHETIC_CONTROLLED`** — platform forecasting / churn / causal ground truth / synthetic decision scenarios | explicitly labelled synthetic | ✅ |
| **`SYNTHETIC_INDIAN_CONTEXT`** — Kundan customer behaviour | synthetic; standalone benchmark, **not an `MLModel`**, not in the Training Center | ✅ |
| **`RETIRED_NON_INDIAN`** — M5 (USA) / UCI (UK) / Supermarket Sales (Myanmar) | in `data/external/_retired_non_indian/`; kept for reproducibility; not in active selection / dashboard / paper tables; `dataset_category.classify` → `RETIRED_NON_INDIAN` | ✅ still retired |
| **`REAL_INDIAN_SME_OUTCOME`** | **0 records** | ✅ pipeline ready, not populated |

No dataset is represented as real Indian SME evidence. No dataset silently promoted.

## 3. Research readiness

| Item | State |
|---|---|
| Experiments | **16**, all `completed`, IDs frozen; manifest byte-identical to before this audit. |
| Forecasting (Benroshan `INDIA_REAL_BUSINESS`, 51 test days) | naive MAE 19.92 / RMSE 31.25 · linear 18.47 / 28.51 · xgboost **15.27 / 23.89**. **Descriptive; not generalised to all Indian SMEs.** |
| Forecasting (platform `SYNTHETIC_CONTROLLED`, 265 test rows) | naive 24.66 / 38.28 · linear 17.29 / 25.51 · xgboost 15.14 / 21.86 · MAPE 15.5 / 12.5 / 10.3 %. |
| Architecture comparison (synthetic 12×5) | Digital Twin **B** (mean goal achievement 0.486) currently outperforms Full DecisionGPT **D** (0.084); D < B `p < 0.0001`. |
| Multi-agent layer | **no demonstrated additional objective value** on the current synthetic suite. |
| Risk Manager calibration | **R3 PROMISING on the synthetic calibration suite only** — robust extrapolation scale + λ = 0.25 lifts synthetic mean goal achievement 0.084 → 0.168 and risk-adjusted −2 614.8 → +40.5, preserving ordering (ρ 0.969) and confidence. **Not** real-world validated. |
| Real Indian external probe (Benroshan) | R3 **inert** — real implied-price ranges did not reproduce the synthetic low-variance pathology (`R0 == R1` on all 184 rows). Verdict: **PROMISING BUT NOT VALIDATED**. |
| Statistics | `STATISTICAL_ANALYSIS.md` matches `multi_scenario_service._summ` / `_paired` exactly (Student-t CI, paired Wilcoxon `zero_method="wilcox"`, effect size `|Z|/√N_nonzero`). |
| Paper tables | 1 / 3 / 4 / 5 READY; **Table 2 NOT READY** (gate: ≥ 5 genuine `REAL_INDIAN_SME_OUTCOME` matched records; currently 0; synthetic / demo / Benroshan / AGMARKNET / public-context never counted). |

## 4. Real-world validation readiness

| Track | State |
|---|---|
| Real SME outcomes | `REAL_INDIAN_SME_OUTCOME = 0` · `DecisionOutcome = 0` · `PredictionEvaluation = 0`. Import pipeline (consent / provenance / anonymisation / India-only / PII rejection / supported-decision / horizon / horizon↔window / decision-before-outcome / duplicate) verified; **not populated**. |
| Real LLM | `LLM_PROVIDER=""`, `LLM_API_KEY=""` → `settings.llm_enabled = False` → **BLOCKED**. Frozen protocol `docs/REAL_LLM_VALIDATION_PROTOCOL.md` present (same inputs, only LLM mode changes, anti-tuning, no secrets, template vs real-LLM separated). Agent **scores** are rule-based (`app/agents/base.py`: "No agent calls an LLM") — a real LLM affects goal parsing + narration only. |
| Digital Twin real-outcome evaluation | **NOT READY** (0 real outcomes). |
| Causal validation | `MIN_OUTCOMES_FOR_OBSERVATIONAL = 3`, `CONSISTENCY_THRESHOLD = 2/3` unchanged. `CAUSALLY_VALIDATED = 0`. The `observational` / `data_supported` edges in the dev DB are correlation/Granger **graph-construction** evidence from synthetic/demo history, **not** intervention evidence. |

## 5. Production readiness

```
Active models:            6 v1 (sales_forecast_{naive,linear,xgboost}, churn_{logistic_regression,random_forest,xgboost}) — unchanged
Production risk model:    None       (R0)
Production risk_penalty_lambda: 1.0  (D0)
R3 / R1 / R2-λ:           EXPERIMENTAL / opt-in only / NOT PROMOTED
Robust risk formula:      never the production default (risk_model defaults to None)
Risk Manager:             active in production (the penalty is applied; only its weight / formula is R0)
```

## 6. Changes made in this audit (minimal — reproducibility / integrity only)

| File | Change | Why |
|---|---|---|
| `backend/app/services/risk_manager_generalization_service.py` | `synthetic_calibration_reference` now resolved from the stored `risk_manager_calibration` experiment (`_calibration_reference(db)`) instead of the hard-coded string `"risk_manager_calibration b8516eef"` + literal verdict `"PROMISING"` | a hard-coded peer experiment id / conclusion breaks reproduction and is a research-integrity smell |
| `tests/unit/test_risk_manager_generalization_service.py` | `test_calibration_cross_reference_is_resolved_not_hard_coded` | regression guard for the above |
| `docs/FINAL_DATASET_INVENTORY.md` | dated-snapshot pointer note (that task's "209 passed / Alembic 0006" line is a point-in-time snapshot; current state → this report / `RESEARCH_REPRODUCIBILITY.md`) | doc-vs-implementation consistency |
| `docs/FINAL_PRE_VALIDATION_AUDIT.md` | this report | — |

Everything else audited was already correct and was left unchanged.

## 7. Remaining blockers

### BLOCKER — required before final real-world validation
- **≥ 5 genuine `REAL_INDIAN_SME_OUTCOME` matched records** (currently 0) — the only thing that enables Table 2 and the Digital Twin real-outcome evaluation.
- **A legitimately configured LLM provider** (`LLM_PROVIDER` + `LLM_API_KEY`) to run `docs/REAL_LLM_VALIDATION_PROTOCOL.md`.

### OPTIONAL — useful, not required
- **AGMARKNET** raw pull (free `DATA_GOV_IN_API_KEY`) → adds a second `INDIA_*` price-forecasting row. Stays `INDIA_AGRICULTURAL_PRICE`.
- Repeated-seed runs for the forecasting / customer experiments to attach CIs.
- A `Decision` lifecycle status column (`generated / accepted / rejected / implemented / outcome_pending / outcome_recorded`) — only if a study needs to track accepted-but-not-implemented decisions; documented, not migrated.

### HUMAN ACTION — cannot be completed by code
1. Institutional / legal review for collecting anonymised SME decision data.
2. Recruit 5–10 genuine Indian SMEs (`docs/REAL_INDIAN_SME_RECRUITMENT_GUIDE.md`), obtain consent, collect real decisions and later actual outcomes at a fixed horizon, run the quality scorecard (`docs/REAL_INDIAN_SME_DATA_QUALITY_PROTOCOL.md`), import via `scripts/import_real_sme_outcomes.py`.
3. Provision a real LLM provider + key.
4. After ≥ 5 real matched outcomes: run the final Digital Twin evaluation, generate Table 2 (real-SME only, descriptive), and record the final real-world conclusions.

## 8. Verdict

> **ENGINEERING / RESEARCH IMPLEMENTATION FREEZE RECOMMENDED.**

The DecisionGPT pipeline, dataset architecture, experiment suite, statistical
methodology, risk-calibration study, validation tooling, no-leakage guarantees,
production/research isolation, and research dashboard are **complete and
internally consistent**. Every remaining gap is **human-dependent** (genuine SME
data, a real LLM provider) — not more code, datasets, synthetic experiments,
architecture changes, or parameter tuning.

The project should now move to the **FINAL HUMAN VALIDATION PHASE**
(`docs/REAL_WORLD_VALIDATION_ROADMAP.md`, Phase 2 onward).

Scientific status (unchanged and correct): `REAL SME EVIDENCE = PENDING`,
`REAL LLM VALIDATION = BLOCKED`, `TABLE 2 = NOT READY`,
`CAUSAL VALIDATION = NOT READY`, `PRODUCTION = R0 / D0`,
`R3 = EXPERIMENTAL / NOT PROMOTED`.

## 9. Git commit

`5c54410` (`5c544109507077d343f5c90e3a3433749b3a38db`)
