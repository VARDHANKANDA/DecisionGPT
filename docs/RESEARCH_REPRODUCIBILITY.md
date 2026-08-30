# Research Reproducibility

Everything needed to reproduce the DecisionGPT paper experiments. Nothing here
recomputes or approximates a metric — the commands drive the *existing*
Experiment Runner / Training Center, which store what the real evaluation
modules return.

## 1. Environment

| | |
|---|---|
| Python | 3.12.0 |
| Dependencies | `backend/requirements.txt` (24 pinned packages incl. `pandas==2.2.3`, `numpy==2.5.2`, `scikit-learn==1.5.2`, `scipy==1.18.1`, `joblib==1.5.3`, `xgboost==3.4.0`, `shap==0.52.0`, `holidays==0.103`). `numpy` is 2.x because `shap==0.52.0` requires `numpy>=2` (`pandas==2.2.3` / `scikit-learn==1.5.2` both support numpy 2.x); `scipy` and `joblib` are direct imports, pinned explicitly rather than left transitive. See `docs/FINAL_REPRODUCIBILITY_VALIDATION_REPORT.md` for the full clean-environment audit. |
| Node / frontend | `frontend/package.json` (Next.js 16 / React 19); `npm ci` |
| DB (research) | SQLite via `DATABASE_URL=sqlite:///./backend/dev.db` — migrations verified identical on Postgres |
| Alembic head | `0007` (30 tables; 0007 adds nullable real-SME-outcome provenance columns) |
| Seed | **42** for every deterministic experiment |
| Frozen at commit | `eb7d392` (2026-08-29) + this doc's commit |

```bash
cd backend && python -m venv .venv && .venv/Scripts/pip install -r requirements.txt
DATABASE_URL=sqlite:///./backend/dev.db python -m alembic upgrade head
# or, faster, the create_all bootstrap:
DATABASE_URL=sqlite:///./backend/dev.db python backend/scripts/dev_bootstrap_sqlite.py
```

`models/` is a gitignored build product. In a fresh environment the pytest
session fixture (`_ensure_baseline_models`) retrains the forecasting + churn
baselines at seed 42 on first run; metrics are byte-reproducible with the
pinned stack (forecasting xgb MAE 15.139 / RMSE 21.863; churn logreg F1 0.669
/ AUC 0.798). Do not commit `.pkl` files trained on a different scikit-learn.

## 2. Datasets (frozen)

| dataset_id | category | version | source | seed / determinism |
|---|---|---|---|---|
| `platform-forecasting-v1` | `SYNTHETIC_CONTROLLED` | v1 | `data/platform/forecasting/sales_timeseries.csv` (`scripts/generate_platform_data.py`, seed 42) | deterministic |
| `platform-churn-v1` | `SYNTHETIC_CONTROLLED` | v1 | `data/platform/churn/customers.csv` | deterministic |
| synthetic causal ground truth | `SYNTHETIC_CONTROLLED` | — | generated in `causal_evaluation_service` (250 steps, seed 42, A→B→C + D noise) | deterministic |
| synthetic decision scenario | `SYNTHETIC_CONTROLLED` | — | `decision_architecture_service` / `ablation_service` (seed 42, goal +15%) | deterministic |
| `external-india-e-commerce-forecasting` | `INDIA_REAL_BUSINESS` | v1 | Kaggle `benroshan/ecommerce-data` (CC0), adapter `ml/preprocessing/india_ecommerce_adapter.py` seed 42 | deterministic (committed processed CSV) |
| `external-india-customer-…-purchase-prediction` | `SYNTHETIC_INDIAN_CONTEXT` | v1 | Kaggle `kundanbedmutha/…` (CC BY 4.0), adapter `ml/preprocessing/india_customer_adapter.py` seed 42 | deterministic (committed processed CSV) |
| `external-india-agmarknet-forecasting` | `INDIA_AGRICULTURAL_PRICE` | — | data.gov.in AGMARKNET, GODL-India | **`DATA_PENDING`** — needs `DATA_GOV_IN_API_KEY`; excluded from the frozen run |
| India festival calendar / RBI repo rate | `INDIA_PUBLIC_CONTEXT` | v1 | `holidays==0.103` / RBI MPC resolutions | deterministic (committed CSVs) |

## 3. Model versions (frozen)

| model_name | version | status | trained on |
|---|---|---|---|
| `sales_forecast_{naive,linear,xgboost}` | v1 | **active** | `platform-forecasting-v1` (`ml/training/train_forecasting.py`, seed 42) |
| `churn_{logistic_regression,random_forest,xgboost}` | v1 | **active** | `platform-churn-v1` (`ml/training/train_churn.py`, seed 42) |
| `sales_forecast_{naive,linear,xgboost}` | v2 | **experimental** | `external-india-e-commerce-forecasting` v1 (Training Center, seed 42) |

The active set is 6 v1 models and is **never** changed by any experiment
(asserted in `scripts/run_external_benchmarks.py` and the integration tests).

## 4. Commands — the frozen research run

```bash
export DATABASE_URL=sqlite:///./backend/dev.db
python backend/scripts/dev_bootstrap_sqlite.py

# baseline (active) models into the DB
python -c "import sys;sys.path.insert(0,'backend');from app.db.session import SessionLocal;\
from app.services import model_registry_service as m;d=SessionLocal();m.sync_from_file_registry(d);d.close()"

# --- Experiment 1: Indian forecasting (Training Center, experimental only) ---
python scripts/download_india_business_datasets.py            # Kaggle CC0/CC-BY, anonymous
python scripts/build_external_datasets.py --only benroshan
python scripts/register_external_datasets.py --only benroshan
python scripts/register_external_datasets.py --only kundan
python scripts/run_external_benchmarks.py --only benroshan --seed 42

# --- Experiment 2: synthetic Indian customer benchmark (standalone) ---
python scripts/build_external_datasets.py --only kundan
python scripts/run_india_customer_benchmark.py --seed 42
#   -> data/external/india_customer_synthetic/benchmark_results.json

# --- Experiments 3-7: existing Experiment Runner (single-seed) ---
python -c "import sys;sys.path.insert(0,'backend');from app.db.session import SessionLocal;\
from app.services import experiment_service as e;d=SessionLocal();\
[print(t, e.run_experiment(d,t,{'seed':42,'name':'paper_'+t}).status) for t in \
['forecasting','churn','causal','decision_architecture','multi_agent','ablation','digital_twin']];d.close()"

# --- Experiments 5-6 STRENGTHENED: 12 scenarios x 5 seeds (Tables 4/5) ---
# see docs/MULTI_SCENARIO_EXPERIMENT_PROTOCOL.md + docs/STATISTICAL_ANALYSIS.md
python -c "import sys;sys.path.insert(0,'backend');from app.db.session import SessionLocal;\
from app.services import experiment_service as e;d=SessionLocal();\
[print(t, e.run_experiment(d,t,{'seeds':[42,43,44,45,46],'name':'paper_'+t}).status) for t in \
['multi_scenario_architecture','multi_scenario_ablation','multi_agent_diagnostic']];d.close()"
#   multi_scenario_architecture ~= 5 min, multi_scenario_ablation ~= 10-25 min,
#   multi_agent_diagnostic ~= 5 min (all CPU-bound, deterministic, LLM template mode)

# --- Candidate-space correction + controlled re-test (docs/CANDIDATE_SPACE_CORRECTION_REPORT.md) ---
# The diagnostic found a candidate-space confound; strategy_generation_service._revenue_templates()
# was given the supported Price +5% / +10% levers, then the SAME experiments were repeated:
python -c "import sys;sys.path.insert(0,'backend');from app.db.session import SessionLocal;\
from app.services import experiment_service as e;d=SessionLocal();\
[print(t, e.run_experiment(d,t,{'seeds':[42,43,44,45,46],'name':'POST_CORRECTION '+t}).status) for t in \
['multi_scenario_architecture','multi_scenario_ablation','multi_agent_diagnostic']];d.close()"
#   pre-correction runs are relabelled 'PRE_CORRECTION ...' and kept in the manifest.

# --- Risk Manager diagnostic + risk-penalty sensitivity (docs/RISK_MANAGER_DIAGNOSTIC_REPORT.md) ---
# D0 = production Full DecisionGPT; D1 = Full DecisionGPT with
# PipelineOptions(risk_penalty_in_ranking=False) (Risk Manager still runs; its
# penalty weight in strategy_optimizer.resolve is 0). D1 is a labelled
# sensitivity variant, NOT the architecture. Same 12 scenarios x 5 seeds.
python -c "import sys;sys.path.insert(0,'backend');from app.db.session import SessionLocal;\
from app.services import experiment_service as e;d=SessionLocal();\
print(e.run_experiment(d,'risk_manager_diagnostic',{'seeds':[42,43,44,45,46],'name':'risk_manager_diagnostic v1'}).status);d.close()"
#   ~= 8-12 min (2 analyze_goal runs per scenario/seed; CPU-bound; deterministic).

# --- Principled Risk Manager calibration study (docs/RISK_MANAGER_CALIBRATION_REPORT.md,
#     docs/RISK_CALIBRATION_ANALYSIS.md) ---
# Research-only variants: R0 (production) / D1 (no penalty) / R1 (robust
# extrapolation-risk scale, PipelineOptions(risk_model="R1")) / R2-λ (ranking
# penalty weight λ ∈ {0.25,0.50,0.75}, PipelineOptions(risk_penalty_lambda=λ)) /
# R3 (R1 + the λ chosen by a pre-specified criterion). The Digital Twin's
# predicted units/revenue/profit and the agent growth scores are unchanged.
python -c "import sys;sys.path.insert(0,'backend');from app.db.session import SessionLocal;\
from app.services import experiment_service as e;d=SessionLocal();\
print(e.run_experiment(d,'risk_manager_calibration',{'seeds':[42,43,44,45,46],'name':'risk_manager_calibration v1'}).status);d.close()"
#   ~= 25-35 min (7 variants x 60 pairs x 1 analyze_goal). No variant is promoted.

# --- R3 generalization / real-Indian-data validation
#     (docs/RISK_MANAGER_GENERALIZATION_REPORT.md) ---
# External validation of R3 on real Indian data (Benroshan external-india-ecommerce-v1,
# INDIA_REAL_BUSINESS, provenance unverified). Part A: 23 real price sub-series
# partitioned LOW/MODERATE/HIGH variance by robust CV (pre-registered thresholds),
# R0 vs R1(=R3) extrapolation risk + Spearman/monotonicity. Part B: SIMULATED
# R0/R1/R2-0.25/R3 decision comparison on the materialised IEC_TOTAL business.
# Part C real-LLM: BLOCKED (no provider). Part D DecisionOutcome: 0 records.
python -c "import sys;sys.path.insert(0,'backend');from app.db.session import SessionLocal;\
from app.services import experiment_service as e;d=SessionLocal();\
print(e.run_experiment(d,'risk_manager_real_data_validation',{'name':'risk_manager_real_data_validation v1'}).status);d.close()"
#   ~= 1-2 min. Deterministic. Verdict: PROMISING BUT NOT VALIDATED. Production stays R0.

# a controlled decision (Digital Twin simulations + confidence basis) on the demo synthetic business
python -c "import sys;sys.path.insert(0,'backend');from app.db.session import SessionLocal;\
from app.services import demo_business_service as db_,goal_service as g,decision_service as ds;\
d=SessionLocal();b=db_.create_demo_business(d);go=g.create_goal(d,b,'Increase revenue by 15% over the next quarter');\
r=ds.analyze_goal(d,b,go.id);print(r.selected_strategy_name, r.confidence);d.close()"

# --- artifacts ---
curl -s localhost:8000/api/v1/research/experiments/manifest -H "X-Research-Token: $RESEARCH_CONSOLE_TOKEN" \
  > experiments/experiment_manifest.json
curl -s localhost:8000/api/v1/research/paper-results     -H "X-Research-Token: $RESEARCH_CONSOLE_TOKEN" \
  > experiments/paper_results_snapshot.json
```

## 5. Expected outputs (frozen run — `docs/RESEARCH_EXPERIMENT_REPORT.md` has the full tables)

| Experiment | Headline (seed 42) |
|---|---|
| 1 · Indian forecasting (`INDIA_REAL_BUSINESS`, 51 test days) | MAE naive 19.92 / linear 18.47 / xgboost **15.27**; MAPE **omitted** (zero-sales days → 110–276 %) |
| 1 · Platform forecasting (`SYNTHETIC_CONTROLLED`, 265 test rows) | MAE naive 24.66 / linear 17.29 / xgboost **15.14**; MAPE 15.5 / 12.5 / 10.3 % |
| 2 · Synthetic Indian customer (`SYNTHETIC_INDIAN_CONTEXT`, 6 250 test rows) | ROC-AUC 0.760 / 0.744 / 0.757; P/R/F1 ≈ 0 at 0.5 threshold (22.5 % positives) |
| 3 · Digital Twin evaluation | `sample_size = 0` → **NOT READY**, needs `DecisionOutcome` records |
| 4 · Causal graph (synthetic ground truth) | precision 0.40, recall 1.00, SHD 3, TP 2 / FP 3 / FN 0 |
| 5 · Decision architecture (legacy, 1×1) | A 0.00 · B 0.333 · C 0.00 · D 0.00 goal achievement (`legacy_single_scenario_result`) |
| **5 · Decision architecture (multi, 12×5=60/arch)** | **mean goal achievement A 0.000 · B 0.486 [CI 0.405, 0.567] · C 0.003 · D 0.084**. Paired Wilcoxon: D>A p=0.0045; **D<B p<0.0001** (B beats Full on 45/60). Identical PRE (`675cf17e`) and POST-correction (`0e1bd8dc`) — see below. |
| 6 · Ablation A–F (legacy, 1×1) | every `delta_goal_achievement = 0.0`; confidence 0.150→0.272 when Causal Graph removed |
| **6 · Ablation A–F (multi, 12×5=60/config)** | most `Δ vs Full ≈ 0`; large effect only for removing the Digital Twin (config B → 0.00). See the completed `multi_scenario_ablation` run. Identical PRE (`be392694`) / POST (`db58455b`). |
| **Candidate-space correction re-test** | `candidate_coverage_rate` 0.333 → **0.833**, `missing_supported_strategy_rate` 0.500 → **0.000** (invariant now holds). Architecture / ablation / pairwise aggregates **byte-identical** to pre-correction: D still 0.084, D<B p<0.0001, override rate 1.00 (0 improved / 45 degraded). Failure mode shifted `CANDIDATE_SET_MISMATCH` 30 → 0, `RISK_OVERRULE` 15 → 45. POST diagnostic `f24abc1b`. See `docs/CANDIDATE_SPACE_CORRECTION_REPORT.md`. |
| **Risk Manager diagnostic (`ba56e42b`)** | Optimizer formula verified on 390/390 strategy rows. RM-decisive 45/60 (75 %) — 35 improved / 0 degraded / 10 neutral. `RISK_SCORE_MISMATCH` = 0/390 (RM faithfully transmits the DT extrapolation-risk score: mean DT risk `Price +5%` 0.68, `Price +10%` 0.98). Sensitivity variant **D1** (risk penalty un-weighted): mean goal achievement **0.084 → 0.583**, paired Wilcoxon D1−D0 p<0.0001, r=0.89, 35 wins / 25 ties / 0 losses; D1 confidence 0.139 → 0.018. Outcome **A** (with caveats). See `docs/RISK_MANAGER_DIAGNOSTIC_REPORT.md`. |
| **Risk Manager calibration (`b8516eef`)** | R0 formula confirmed miscalibrated on low-variance histories (zero-variance diagnostic). **R3** (robust scale + λ=0.25): mean goal achievement 0.084 → 0.168 (paired Wilcoxon p=0.025, 5/60 non-zero), risk-adjusted −2 614.8 → +40.5, Spearman ρ 0.969, 0 monotonicity violations, confidence 0.109. Verdict **PROMISING** (R2-0.25 & R3 pass all 7 criteria). No variant promoted. See `docs/RISK_MANAGER_CALIBRATION_REPORT.md`. |
| **R3 generalization / real-data validation (`70617412`)** | Benroshan real Indian e-commerce. 23 real price sub-series (3 LOW / 11 MOD / 9 HIGH variance): **R0 == R1 on all 184 test rows** — R0's pathology does not occur on real implied-price data; Spearman ρ 0.989 (identical), 0 monotonicity violations, 82 % of out-of-range extreme probes ≥ 0.15. SIMULATED decision comparison: R0/R1/R2-0.25/R3 all select `Price +10%`, identical GA/RA/confidence (risk penalty already ≈ 0). Real-LLM **BLOCKED**; `DecisionOutcome` count 0 → Table 2 NOT READY. Verdict **PROMISING BUT NOT VALIDATED**. Production stays R0. See `docs/RISK_MANAGER_GENERALIZATION_REPORT.md`. |
| **Real Indian SME outcome capture (no experiment)** | Additive workflow only: migration `0007` (nullable provenance/horizon columns on `decision_outcomes`), `real_sme_outcome_service` (validate + PII reject + horizon-consistency + no-leakage + duplicate detection + import), `scripts/import_real_sme_outcomes.py`, anonymised template `docs/templates/real_indian_sme_outcome_template.{csv,json}`, separated **Real Indian SME Outcomes** dashboard panel. Collection + recruitment package: `docs/REAL_SME_DATA_COLLECTION_GUIDE.md`, `docs/REAL_INDIAN_SME_RECRUITMENT_GUIDE.md`, `docs/REAL_INDIAN_SME_DATA_DICTIONARY.md`, `docs/REAL_INDIAN_SME_VALIDATION_METHODOLOGY.md`, `docs/REAL_INDIAN_SME_DATA_QUALITY_PROTOCOL.md`, `docs/REAL_WORLD_VALIDATION_ROADMAP.md`, `docs/REAL_SME_COLLECTION_READINESS_REPORT.md`, `docs/REAL_EVIDENCE_STATUS_REPORT.md`, `docs/templates/real_sme_{consent_and_provenance,collection_checklist}.md` + `docs/templates/REAL_INDIAN_SME_{PARTICIPANT_CHECKLIST,RESEARCHER_FORM,PARTICIPANT_INSTRUCTIONS,COLLECTION_SCHEDULE}`. Dashboard real-SME panel surfaces Real-LLM / R3 / Production status derived live. **0 real records** → `REAL SME COLLECTION WORKFLOW = READY`, outcomes = 0, Table 2 NOT READY, real-LLM BLOCKED. No synthetic outcome fabricated. Next action = human recruitment + data collection (`REAL_WORLD_VALIDATION_ROADMAP.md` Phase 2). |
| 7 · End-to-end (demo business) | selected "Marketing +20%", confidence 0.1468 = 0.9788 × 0.5 × 0.6 × (1−0.5) |

`churn` platform: logreg F1 0.669 / AUC 0.798, RF F1 0.661 / AUC 0.793, xgb F1 0.658 / AUC 0.792.

## 6. Provenance rule

Every number in `docs/RESEARCH_EXPERIMENT_REPORT.md` traces to
`experiments/experiment_manifest.json` (`experiment_id`, `random_seed`,
`dataset_version`, `model_versions`, `configuration`, timings) or to a
`benchmark_results.json` next to its dataset. If a number cannot be traced to
one of those, it is not a final research result.
