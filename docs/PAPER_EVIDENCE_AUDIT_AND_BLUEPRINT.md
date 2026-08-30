# DecisionGPT — Final Paper Evidence Audit & Paper Blueprint

**Status:** implementation + reproducibility FROZEN (`ef9ade8`).
**This document does not write the paper.** It audits what the frozen
implementation and the 16 frozen experiments actually support, and specifies a
reviewer-resistant blueprint to write from.

**Method.** Every core `docs/*` report was read and cross-checked against the
implementation (`app/agents/*`, `app/analytics/*`, `app/services/*`), the
`experiments/experiment_manifest.json` (16 experiments) and
`experiments/paper_results_snapshot.json`. Where a document and the code
disagree, the disagreement is reported in §0 and the authoritative source named.

---

## 0. Documentation-vs-implementation cross-check

| # | Observation | Authoritative source | Impact on paper |
|---|---|---|---|
| D1 | `docs/RESEARCH_EXPERIMENT_REPORT.md` §0 "Freeze record" still says **7 experiments / Alembic head 0006 / 218 passed**. `RISK_MANAGER_CALIBRATION_REPORT.md` says "14 prior IDs / 271 passed / 0006"; `RISK_MANAGER_GENERALIZATION_REPORT.md` says "15 prior IDs / 285 passed". | Current state is **16 experiments / head 0007 / 319 passed, 1 skipped** (`docs/FINAL_REPRODUCIBILITY_VALIDATION_REPORT.md`, `experiment_manifest.json`). | **Meta-count staleness only** — each report's *own* numbers and experiment IDs are internally consistent and still reproduce. The report bodies were extended (they cite `70617412`, R3, POST-correction) but their header tables were never back-updated. Paper must cite the **16-experiment** manifest, head **0007**, suite **319/1**. Not a research-integrity problem; is a documentation-hygiene note for §Reproducibility. |
| D2 | `docs/RESEARCH_EXPERIMENT_REPORT.md` "Tests" line: 218 passed; `RISK_CALIBRATION`: 271; `REAL_EVIDENCE_STATUS`: 316; `FINAL_PRE_VALIDATION`: 318; `FINAL_REPRODUCIBILITY`: 319. | Monotonic growth across tasks; **319 passed, 1 skipped** is final. | Cite 319/1 only. |
| D3 | `RESEARCH_EXPERIMENT_REPORT.md` freeze record: "Manifest (7 experiments)"; "Paper-results snapshot (4/5 tables ready)". | `experiment_count = 16`; snapshot `tables_ready = 4, tables_missing = 1`. | Paper-table readiness (4/5) is unchanged and correct; experiment count is 16. |
| D4 | `paper_multi_agent` experiment `7616425f` (`experiment_type = multi_agent`, ds `synthetic_scenario`) records `single_agent.goal_achievement = 0.0`, `multi_agent.goal_achievement = 0.0` — a **legacy single-scenario** run. | The authoritative multi-agent evidence is the **multi-scenario** architecture comparison (`0e1bd8dc`) + diagnostic (`f24abc1b`). | Do not cite `7616425f` as the agent result; cite the 12×5 suite. `7616425f` belongs in an "early single-scenario runs (preserved)" appendix line. |
| D5 | The **Kundan customer benchmark** is **not** one of the 16 `ExperimentRun` rows. It is `scripts/run_india_customer_benchmark.py` → `benchmark_results.json`, "not an `MLModel`, not wired into the Training Center" (`INDIAN_DATASET_CATALOG.md`, `FINAL_DATASET_INVENTORY.md`). | Code + catalog. | Table 1 / customer section must label it a **standalone synthetic benchmark**, traceable to the script + its JSON, not to an `experiment_id`. |
| D6 | Dev-DB causal evidence levels: `ASSUMED 20 / OBSERVATIONAL 5 / DATA_SUPPORTED 1 / CAUSALLY_VALIDATED 0` (`REAL_EVIDENCE_STATUS_REPORT.md`). | The `OBSERVATIONAL`/`DATA_SUPPORTED` rows are **graph-construction** evidence from synthetic/demo history (correlation / Granger), **not** intervention feedback (`FINAL_PRE_VALIDATION_AUDIT.md` §4). | Paper must not present any non-zero `OBSERVATIONAL`/`DATA_SUPPORTED` count as real causal evidence. Only `CAUSALLY_VALIDATED = 0` is the honest headline. |
| D7 | `RESEARCH_EXPERIMENT_REPORT.md` §0 code commit `eb7d392`; `RESEARCH_REPRODUCIBILITY.md` "Frozen at commit `eb7d392`". | HEAD is now `ef9ade8`; dependency spec changed (numpy 2.5.2, scipy/joblib declared) per `FINAL_REPRODUCIBILITY_VALIDATION_REPORT.md`. | §Reproducibility cites `ef9ade8` + the corrected `requirements.txt` (Python 3.12.0, numpy 2.5.2). |
| D8 | Code confirms **no agent calls an LLM** (`app/agents/base.py` docstring; `risk_manager.py`, `strategy_optimizer.py` are pure functions). `decision_service.analyze_goal` invokes `LLMService` only for `evaluate_agent` / `generate_strategy_explanation` **after** `analyses.sort(...); best = analyses[0]`. `parse_goal` re-validates every field against data. | Code. | The claim "a real LLM affects goal parsing + narration only, never scores or selection" is **code-accurate** and safe to state. |

**No discrepancy changes a single reported metric or verdict.** All are
meta-count staleness or labelling precision.

---

## A. Executive evidence verdict

**What the project has actually built and measured (all defensible):**

1. A working, end-to-end, capability-gated decision-support pipeline: goal →
   candidate strategies → Digital-Twin simulation → causal context → 3-agent
   rule-based evaluation with a 2-round debate → fixed-formula strategy
   optimizer → risk-aware recommendation → explanation → decision/outcome
   memory → evaluation → research dashboard → paper exports. Verified wired
   and isolated from production defaults (R0/D0).
2. A **controlled 12-scenario × 5-seed** architecture experiment (60 paired
   observations per arm) with pre-registered statistics (Student-t CIs, paired
   Wilcoxon, effect sizes), and its full negative result preserved.
3. A **negative headline finding**, reproduced byte-identically before and
   after a candidate-space confound was found and corrected: **the full
   multi-agent DecisionGPT (D) achieves significantly *lower* goal achievement
   than the leaner Prediction + Digital-Twin architecture (B)** — mean 0.084 vs
   0.486, paired Wilcoxon *p* < 0.0001, B wins 45/60 and never loses.
4. A **mechanistic diagnosis** of that finding: the objective value is
   concentrated entirely in the **Digital Twin** (ablation: removing it costs
   0.084 goal achievement; removing Causal Graph / Multi-Agent / Explainability
   / Memory each cost 0.000). The proximate mechanism of the agent-layer
   regression is the optimizer's unbounded risk-penalty term, which in turn
   faithfully transmits the Digital Twin's extrapolation-risk heuristic
   (0/390 risk-score mismatches).
5. A **pre-registered risk-calibration study**: R0's extrapolation-risk formula
   is demonstrably miscalibrated on constant/low-variance price histories; a
   robust-scale + bounded-weight variant (R3) fixes the pathology on the
   synthetic suite (goal achievement 0.084 → 0.168, risk-adjusted −2614.8 →
   +40.5, ordering preserved) — **PROMISING, not promoted**.
6. An **external probe of R3 on the one available real Indian dataset**
   (Benroshan): the pathology does not occur there (R0 == R1 on all 184 rows),
   so R3 is inert — **PROMISING BUT NOT VALIDATED**.
7. A **capability-aware Indian-SME data architecture** with explicit
   provenance/category separation (real / synthetic-controlled /
   synthetic-Indian-context / public-context / agri-price) that never averages
   across categories and refuses recommendations when required data is absent.
8. A **reproducible research infrastructure**: 16 seed-42 experiments, a
   byte-identical manifest, deterministic re-runs, and a clean-room dependency
   validation.

**What the project has NOT established (must be stated as such):**

- No evidence that DecisionGPT (any configuration) improves **real** SME
  outcomes. 0 real decisions, 0 real outcomes.
- No validated Digital-Twin real-world predictive accuracy. **Table 2 = NOT
  READY** (0/5 real matched outcomes).
- No real causal validation. `CAUSALLY_VALIDATED = 0`; causal numbers are
  synthetic method-validation only.
- No real-LLM evaluation. `llm_enabled = False` → **BLOCKED**.
- No human/user study of explainability. Not implemented.
- No population-level Indian-SME claim: one small real dataset (~500 orders,
  unverified provenance), one synthetic Indian-context dataset, public context,
  AGMARKNET pending.
- The multi-agent layer, as implemented in template mode, does **not** add
  objective value; it subtracts it on the tested suite.

**Overall readiness:** the evidence supports a **rigorous
architecture-and-mechanism study with an honest negative result and a
reproducible testbed**, *not* a "DecisionGPT is superior / validated for Indian
SMEs" paper. See §P.

---

## B. Dataset evidence matrix

Categories are never merged. "Frozen ref" is where a reviewer can trace it.

| Dataset | Category | Real/Synthetic | Size / span | License / provenance | What it supports | What it does NOT support | Frozen ref |
|---|---|---|---|---|---|---|---|
| **India E-Commerce Orders (Benroshan)** | `INDIA_REAL_BUSINESS` | **Real**, provenance **UNVERIFIED** ("received from my University, original author unknown") | ~500 orders / 1,500 line items / 36 monthly targets; 2018-04-01…2019-03-31 (12 months); 3 categories (Clothing 949 / Electronics 308 / Furniture 243 lines); 19 states | CC0 | Descriptive Indian retail analytics (sales/profit/geo/target-attainment); a **small** forecasting benchmark (51 test days); a real-data risk-ordering probe (23 derived implied-price sub-series, 184 rows) | Unit-price/elasticity pricing (price is *derived* revenue÷units), discount analysis, churn/customer analytics, causal evaluation, large-scale forecasting, **any Table-2 / DecisionOutcome evidence**, any population-level Indian-SME claim | `external-india-ecommerce-v1`; adapter `ml/preprocessing/india_ecommerce_adapter.py` (seed 42); Table 1 `INDIA_REAL_BUSINESS` rows; experiment `70617412` |
| **India E-Commerce Customer Behaviour (Kundan)** | `SYNTHETIC_INDIAN_CONTEXT` | **Synthetic** (Kaggle page: "generated to simulate realistic online shopping behavior") | 25,000 rows; 6,250 test; 22.5% positive; visit_date 2024 | CC BY 4.0 | A standalone **synthetic** purchase-prediction demonstration (binary `purchased`); ROC-AUC ≈ 0.75 shows a ranking signal | Churn (no churn target; `cart_abandoned` ≠ churn and is excluded as leakage), real Indian customer behaviour, training/influencing any production model, merging with any real result | `external-india-customer-synthetic-v1`; `scripts/run_india_customer_benchmark.py` → `benchmark_results.json`; **not an `MLModel`, not an `ExperimentRun`** |
| **Platform forecasting** | `SYNTHETIC_CONTROLLED` | Synthetic | 265 test rows; 1 seed | bundled | Controlled forecasting evaluation with valid MAPE (no zero actuals) | Any real-world forecasting claim; CIs (single seed) | `platform-forecasting-v1`; experiment `c2b3a2fa` (`paper_forecasting`) |
| **Platform churn** | `SYNTHETIC_CONTROLLED` | Synthetic | 6,000 rows | bundled | Controlled churn/classification evaluation (the **only** churn dataset in the project) | Any real-world churn claim; Indian-context churn | `platform-churn-v1`; experiment `21e8e800` (`paper_churn`) |
| **Synthetic causal ground truth** | `SYNTHETIC_CONTROLLED` | Synthetic | 250 timesteps; seed 42 | bundled | **Method validation** of pairwise-Granger recovery against a KNOWN structure (A→B→C lag 1; D noise) | Any real causal effect; any Indian causal claim; identification (pairwise Granger, no MC correction) | `synthetic_causal_validation`; experiment `36d0d404` (`paper_causal`); `GROUND_TRUTH_EDGES` in `causal_evaluation_service.py` |
| **Synthetic decision scenarios (S01–S12)** | `SYNTHETIC_CONTROLLED` | Synthetic, **designed not sampled** | 12 scenarios × 5 seeds (42–46) = 60 paired obs/arm; ephemeral businesses keyed `scenario_id:seed` | bundled | Controlled architecture comparison, ablation, multi-agent diagnostic, risk-manager diagnostic & calibration | Population inference (CIs describe within-suite sampling variability only); real SME behaviour; `reduce_churn` (no retention lever — excluded) | `synthetic_scenario_suite`; experiments `0e1bd8dc`, `db58455b`, `f24abc1b`, `ba56e42b`, `b8516eef` (+ PRE `675cf17e`, `be392694`, `c58c4537`) |
| **India Festival & Holiday Calendar** | `INDIA_PUBLIC_CONTEXT` | Real (generated offline from `holidays==0.103`) | 351 events / 3,287 daily rows; 2019–2027 | MIT (lib); public facts | Optional exogenous seasonality **covariate** | A forecasting target; causal evidence; any SME-private analysis | `external-india-festivals-v1`; `ml/preprocessing/india_festival_adapter.py` |
| **India Macro — RBI repo rate** | `INDIA_PUBLIC_CONTEXT` | Real | monthly series | public | Optional macro/finance **covariate** | A target; causal evidence; CPI/WPI/GDP (those are `PENDING`) | `ml/preprocessing/india_macro_adapter.py` |
| **AGMARKNET agri wholesale prices** | `INDIA_AGRICULTURAL_PRICE` | Real | **`DATA_PENDING`** — no `DATA_GOV_IN_API_KEY`; integration + tests present, raw bytes not pulled | data.gov.in | (When populated) a *second* `INDIA_*` price-forecasting row + regional analytics | **Not SME retail data**; not used in any current result; 1 adapter test skips until populated | `data/external/india_agmarknet/metadata.md`; skipped test `test_india_agmarknet_adapter.py::test_committed_india_processed_file_trains` |
| SME-uploaded operational data (sales/customers/products/inventory/finance/marketing/profile) | *(SME-private, not in research registry)* | Real (per business) | n/a — none collected for research | consent-gated | The actual production recommendations; capability detection | Any research result today (no SME has contributed) | canonical schema + `capability_service.py` |
| **REAL_INDIAN_SME_OUTCOME** | (own category) | Real | **0 records** | consent + provenance gated | (When ≥ 5) Table 2 + Digital-Twin real-outcome evaluation, descriptively | Anything now | migration `0007` provenance columns; `scripts/import_real_sme_outcomes.py`; gate in `paper_results_snapshot` |
| M5 (USA) / UCI (UK) / Supermarket Sales (Myanmar) | `RETIRED_NON_INDIAN` | Real | archived | — | Reproducibility only | Not in active selection / dashboard / any paper table | `data/external/_retired_non_indian/` |

---

## C. Experiment evidence matrix (all 16 frozen experiments)

Manifest: `experiments/experiment_manifest.json` (`experiment_count = 16`, all
`status = completed`, `random_seed = 42`). "Sample" = evaluation units.

| # | Name (manifest) | ID | Type | Dataset / category | Seed(s) | Sample | Key result | Stat method | Paper use |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `paper_forecasting` | `c2b3a2fa` | forecasting | `platform-forecasting-v1` / SYNTHETIC_CONTROLLED | 42 | 265 test rows | naive MAE 24.66 / RMSE 38.28 / MAPE 15.46%; linear 17.29 / 25.51 / 12.49%; **xgboost 15.14 / 21.86 / 10.30%** | point estimates (1 seed) | **Table 1** (synthetic block) |
| 2 | `paper_churn` | `21e8e800` | churn | `platform-churn-v1` / SYNTHETIC_CONTROLLED | 42 | 6,000-row dataset | logreg P 0.708 / R 0.634 / **F1 0.669 / AUC 0.798**; rf F1 0.661 / AUC 0.793; xgb F1 0.658 / AUC 0.792 | point estimates (1 seed) | **Table 1** (classification block) |
| 3 | `paper_causal` | `36d0d404` | causal | `synthetic_causal_validation` / SYNTHETIC ground truth | 42 | 250 timesteps | precision **0.40**, recall **1.00**, F1 0.571, **SHD 3** (2 TP: A→B,B→C; 3 FP: A→C transitive, B→A, D→B; 0 FN) | confusion vs known DAG | **Table 3** (labelled "method validation, synthetic") |
| 4 | `paper_digital_twin` | `2f7da989` | digital_twin | `real_recorded_outcomes` / REAL_INDIAN_SME_OUTCOME | 42 | **0** | `sample_size = 0`; MAE/RMSE/MAPE = null | n/a | **Table 2 — NOT READY** (show as unavailable) |
| 5 | `paper_multi_agent` | `7616425f` | multi_agent | `synthetic_scenario` (legacy single) | 42 | 1 scenario | single_agent 0.0 / multi_agent 0.0 goal achievement | descriptive | **Appendix only** — superseded by #10/#13 (see §0 D4) |
| 6 | `legacy_single_scenario_result` (arch) | `a32933ca` | decision_architecture | `synthetic_scenario` | 42 | 1×1 | A 0.0 / **B 0.333 (risk-adj 2826.88)** / C 0.0 / D 0.0 | descriptive | Appendix "early single-scenario run (preserved)" |
| 7 | `legacy_single_scenario_result` (abl) | `1fcca452` | ablation | `synthetic_scenario` | 42 | 1×1 | every Δ-vs-Full = 0.0; confidence 0.150→0.272 when Causal Graph removed | descriptive | Appendix (preserved) |
| 8 | `PRE_CORRECTION multi_scenario_architecture` | `675cf17e` | multi_scenario_architecture | `synthetic_scenario_suite` | 42–46 | 60/arm (240) | A 0.000 / **B 0.486** / C 0.003 / **D 0.084**; D vs B *p* < 0.0001 | Student-t CI + paired Wilcoxon | Methodology/failure-analysis (pre-fix), **byte-identical to #10** |
| 9 | `PRE_CORRECTION multi_scenario_ablation` | `be392694` | multi_scenario_ablation | `synthetic_scenario_suite` | 42–46 | 60/config (360) | only removing Digital Twin moves the objective (Δ +0.084) | paired Wilcoxon | Methodology (pre-fix), byte-identical to #11 |
| 10 | **`POST_CORRECTION multi_scenario_architecture`** | `0e1bd8dc` | multi_scenario_architecture | `synthetic_scenario_suite` | 42–46 | **60/arm (240)** | **A 0.000 [0,0] / B 0.486 [0.405,0.567] / C 0.003 [0.001,0.004] / D 0.084 [0.013,0.156]**; risk-adj A 0 / B 2508.4 / C 190.9 / **D −2614.8**; conf D 0.139. D vs A: +0.084, W/T/L 10/50/0, *p* = 0.0045, r = 0.90. **D vs B: −0.401, W/T/L 0/15/45, *p* < 0.0001, r = 0.87.** B beats Full on 45/60, never loses. | Student-t 95% CI; paired Wilcoxon signed-rank, two-sided, `zero_method="wilcox"`; effect size \|Z\|/√N | **Table 4 (primary), Figure 5** |
| 11 | **`POST_CORRECTION multi_scenario_ablation`** | `db58455b` | multi_scenario_ablation | `synthetic_scenario_suite` | 42–46 | **60/config (360)** | Δ goal achievement vs Full: **without Digital Twin +0.084 [+0.013,+0.156]**; without Causal Graph / Multi-Agent / Explainability / Memory = **0.000**. Removing Causal Graph raises confidence 0.139 → 0.251. | paired Wilcoxon (Full vs each) | **Table 5, Figure 6** |
| 12 | `PRE_CORRECTION multi_agent_diagnostic` | `c58c4537` | multi_agent_diagnostic | `synthetic_scenario_suite` | 42–46 | 60 pairs | override rate 1.00 (0 improved / 45 degraded); `CANDIDATE_SET_MISMATCH` 50%; candidate coverage 0.333 | descriptive trace analysis | Methodology / failure analysis (the confound) |
| 13 | **`POST_CORRECTION multi_agent_diagnostic`** | `f24abc1b` | multi_agent_diagnostic | `synthetic_scenario_suite` | 42–46 | 60 pairs | candidate coverage **0.833** (missing-supported 0.000); override rate **1.00** (0 improved / **45 degraded** / 15 neutral); `CANDIDATE_SET_MISMATCH` 50%→**0%**, `RISK_OVERRULE` 25%→**75%** | descriptive trace analysis | **§Multi-Agent Failure Analysis** |
| 14 | `risk_manager_diagnostic` | `ba56e42b` | risk_manager_diagnostic | `synthetic_scenario_suite` | 42–46 | 60 pairs / 390 strategy rows | D1 (risk penalty un-weighted) goal achievement **0.084 → 0.583**, paired Wilcoxon **p < 0.0001, r = 0.89**, 35 wins/0 losses; **confidence collapses 0.139 → 0.018**; risk-adj −2614.8 → −2522.0; RM_DECISIVE 75%; **0/390 `RISK_SCORE_MISMATCH`**; formula verified 390/390 | paired Wilcoxon | **§Risk Manager** (mechanism isolation; D1 is a labelled variant, NOT the architecture) |
| 15 | `risk_manager_calibration` | `b8516eef` | risk_manager_calibration | `synthetic_scenario_suite` | 42–46 | 7 variants × 60 pairs | R0 0.084 → **R3 0.168** (Wilcoxon vs R0 **p = 0.0253**, 5 wins/0 losses, r = 1.00 on 5 non-zero pairs, mean shift +0.083); risk-adj −2614.8 → **+40.5**; confidence 0.109; Spearman ρ (distance↔risk) 0.969 (R0 0.976); **0 monotonicity violations**; closes ~21% of D0→DT gap; **R2-0.25 and R3 pass all 7 pre-registered criteria** | pre-registered criteria + paired Wilcoxon; Spearman ρ | **Table 6 (supplementary), Figure 9** — verdict **PROMISING; not promoted** |
| 16 | `risk_manager_real_data_validation` | `70617412` | risk_manager_real_data_validation | `external-india-ecommerce-v1` / INDIA_REAL_BUSINESS | 42 | 23 sub-series / 184 rows; Part B: 1 business / 307 sale days | **R0 == R1 byte-identical on all 184 rows** (3 LOW / 11 MOD / 9 HIGH variance regimes); Spearman ρ 0.989; 0 monotonicity violations; 82% of out-of-range extreme probes still ≥ 0.15; SIMULATED decision identical across variants (goal ach 1.00 — a SIMULATED artefact of an out-of-domain model); n_businesses = 1 → **NO INFERENTIAL TEST** | descriptive (Spearman ρ, violation counts); pre-registered H1–H6 | **§Risk Manager / §Threats** — verdict **PROMISING BUT NOT VALIDATED** |

Plus the **Kundan customer benchmark** (not an `ExperimentRun`): logreg P/R/F1
0.00/0.00/0.00, **AUC 0.760**; rf 0.38/0.06/0.11, AUC 0.744; xgb 0.36/0.01/0.02,
AUC 0.757. Trace: `scripts/run_india_customer_benchmark.py` + `benchmark_results.json`.

---

## D. Research-question / hypothesis matrix

### Original framing (`docs/RESEARCH_SPECIFICATION.md`) — audited against evidence

| Original | Testable now? | Evidence verdict |
|---|---|---|
| Main RQ: "Can a goal-driven multi-agent framework … improve strategic decision support for Indian SMEs compared with conventional predictive analytics?" | **Partially, and the answer is mixed-to-negative on the synthetic suite; untestable for "Indian SMEs"** | On 12×5 synthetic scenarios the **full** framework (D) is significantly *worse* than Prediction + Digital Twin (B). It is better than prediction-**only** (A) but only because A has no strategy mechanism. No real-SME test exists. |
| RQ1: "Does Digital Twin simulation improve strategy selection over prediction-only?" | **Yes** | **SUPPORTED (synthetic).** B 0.486 vs A 0.000; ablation: removing the Digital Twin drops D 0.084 → 0.000 (Δ +0.084, 95% CI [+0.013,+0.156]). |
| RQ2 / H2: "Does multi-agent evaluation improve over a single-agent baseline?" | **Yes** | **REFUTED (synthetic).** Single agent C = 0.003; full multi-agent D = 0.084; both ≪ B = 0.486. Adding agents on top of the Digital Twin reduces mean goal achievement (0.486 → 0.084) and makes mean risk-adjusted score negative. |
| RQ3 / H1(spec)/H3: "Does the full system improve goal-aligned performance over baselines?" | **Yes** | **REFUTED vs the strongest baseline.** D < B, paired Wilcoxon *p* < 0.0001, r = 0.87, D loses 45/60, wins 0. |
| RQ4 / H4: "Does explainability improve user understanding?" | **No** | **NOT TESTABLE.** No human/user study implemented (`EXPERIMENT_GUIDE.md` §F "not implemented"). Explainability is generated *after* selection and has 0 goal-achievement delta by construction. |
| RQ3 (causal) "improve intervention explanations and strategy quality" | For *strategy quality*, yes | **REFUTED for strategy quality** (0 goal-achievement delta in ablation); the Causal Graph affects only reported **confidence** (0.139 → 0.251 when removed). Explanation quality is not measured. |

### Recommended reframed research questions (defensible with current evidence)

**Primary RQ.**
> *Within an integrated goal-to-strategy decision-support architecture, which
> components carry measurable objective value, and does a multi-agent debate
> layer add value beyond deterministic Digital-Twin simulation?*

**Secondary RQs.**
- **SRQ1.** Does Digital-Twin simulation improve strategy selection over a
  prediction-only pipeline on a controlled multi-scenario suite? *(→ yes)*
- **SRQ2.** Does adding a single evaluator, then a full 3-agent debate, on top
  of the Digital Twin change objective goal achievement? *(→ yes, negatively)*
- **SRQ3.** What mechanism produces the agent-layer regression, and is it a
  candidate-space artefact or a scoring-rule effect? *(→ scoring rule: the
  optimizer's unbounded risk-penalty term over the Digital Twin's
  extrapolation-risk heuristic; the candidate-space confound was found,
  corrected, and shown not to change the result)*
- **SRQ4.** Is the extrapolation-risk formulation well-calibrated, and can a
  principled reformulation improve the risk/benefit trade-off *without removing
  risk management* — on the synthetic suite, and does it generalise to real
  Indian price data? *(→ miscalibrated; R3 fixes it on synthetic = PROMISING;
  inert on the one real dataset = NOT VALIDATED)*

**Hypotheses and testability**

| ID | Hypothesis | Testable with frozen evidence? | Status |
|---|---|---|---|
| H1 | Digital-Twin simulation increases mean goal achievement vs prediction-only. | Yes (exp `0e1bd8dc`, `db58455b`) | **Supported (synthetic suite).** |
| H2 | Adding a multi-agent debate layer on top of the Digital Twin does **not** increase mean goal achievement. | Yes (`0e1bd8dc`) | **Supported** (it decreases it; *p* < 0.0001). |
| H3 | The agent-layer regression is not explained by a candidate-space mismatch. | Yes (`c58c4537` vs `f24abc1b`, `0e1bd8dc` PRE == POST) | **Supported** (byte-identical after the fix). |
| H4 | The optimizer's risk-penalty term is the proximate driver of the regression. | Yes (`ba56e42b`; D1 variant) | **Supported** (0.084 → 0.583 when un-weighted; RM_DECISIVE 75%) — with the caveat that un-weighting collapses confidence and does not fix risk-adjusted score. |
| H5 | R0's extrapolation-risk formula is miscalibrated for low/zero-variance histories. | Yes (`b8516eef` zero-variance diagnostic) | **Supported.** |
| H6 | A robust-scale + bounded-weight variant (R3) improves the synthetic risk/benefit trade-off while preserving risk ordering and confidence. | Yes (`b8516eef`) | **Supported (synthetic) — PROMISING; not promoted.** |
| H7 | R3's benefit generalises to real Indian business data. | Only a probe exists (`70617412`, n_businesses = 1) | **Not validated** (pathology absent on real data → R3 inert). |
| H8 | DecisionGPT improves real Indian SME decision outcomes. | **No** (0 real outcomes) | **Not testable — NOT READY.** |
| H9 | A real LLM changes agent scoring / strategy selection. | **No** (`llm_enabled = False`; agents are rule-based by design) | **Not testable — BLOCKED**; by architecture the LLM only touches goal parsing + narration. |
| H10 | The Digital-Twin's simulated predictions match real business outcomes. | **No** (Table 2 NOT READY) | **Not testable.** |
| H11 | Explainable recommendations improve user comprehension/trust. | **No** (no instrument) | **Not testable.** |

---

## E. Claim-vs-evidence matrix

Classes: **ESTABLISHED** / **SUPPORTED-BUT-LIMITED** / **DESCRIPTIVE-ONLY** /
**SYNTHETIC-ONLY** / **REAL-DATA-DESCRIPTIVE** / **NOT-VALIDATED** /
**NOT-TESTABLE** / **NOT-READY** / **DO-NOT-CLAIM**.

| # | Proposed claim | Evidence | Dataset | Seed | Class |
|---|---|---|---|---|---|
| 1 | An integrated goal→strategy→simulation→multi-agent→optimizer→explanation→memory pipeline is implemented and runs end-to-end with capability gating. | code + `audit_e2e.py` (no assertion failures) | n/a | n/a | **ESTABLISHED** |
| 2 | Production runs a fixed, auditable configuration (R0/D0): `risk_model=None`, `risk_penalty_lambda=1.0`, agents rule-based, LLM narration-only. | `PipelineOptions()` defaults verified at runtime; `app/agents/base.py` | n/a | n/a | **ESTABLISHED** |
| 3 | On a controlled 12-scenario × 5-seed suite, Digital-Twin simulation raises mean goal achievement from 0.000 (prediction-only) to 0.486. | exp `0e1bd8dc`; ablation `db58455b` | synthetic_scenario_suite | 42–46 | **SYNTHETIC-ONLY** (supported) |
| 4 | The full multi-agent DecisionGPT achieves **significantly lower** goal achievement than Prediction + Digital Twin (0.084 vs 0.486; paired Wilcoxon *p* < 0.0001; loses 45/60, wins 0). | exp `0e1bd8dc` (PRE `675cf17e` identical) | synthetic_scenario_suite | 42–46 | **SYNTHETIC-ONLY** (supported; this is the negative headline) |
| 5 | In the ablation, **only** removing the Digital Twin changes the objective (Δ +0.084, 95% CI [+0.013,+0.156]); removing Causal Graph / Multi-Agent / Explainability / Memory each give Δ = 0.000. | exp `db58455b` | synthetic_scenario_suite | 42–46 | **SYNTHETIC-ONLY** (supported) |
| 6 | The Causal Graph affects only reported confidence (0.139 → 0.251 when removed), not the objective. | exp `db58455b` | synthetic_scenario_suite | 42–46 | **SYNTHETIC-ONLY** (supported) |
| 7 | The agent-layer regression is **not** a candidate-space artefact: after adding the missing price-increase lever (coverage 0.333 → 0.833, missing-supported → 0.000), every aggregate/CI/Wilcoxon p is byte-identical. | `c58c4537` → `f24abc1b`; `675cf17e` == `0e1bd8dc` | synthetic_scenario_suite | 42–46 | **SYNTHETIC-ONLY** (supported) |
| 8 | The proximate mechanism is the optimizer's unbounded `−(1−RM)` risk-penalty term: un-weighting it (D1) lifts goal achievement 0.084 → 0.583 (*p* < 0.0001, r = 0.89). | exp `ba56e42b` | synthetic_scenario_suite | 42–46 | **SYNTHETIC-ONLY** (supported; caveat: D1 confidence 0.018, risk-adj still negative) |
| 9 | The Risk Manager is **not** mis-scoring relative to the Digital Twin (0/390 `RISK_SCORE_MISMATCH`); it faithfully transmits the Digital Twin's extrapolation-risk heuristic, which is high for modest price moves because the synthetic histories hold price nearly constant. | exp `ba56e42b` | synthetic_scenario_suite | 42–46 | **SYNTHETIC-ONLY** (supported) |
| 10 | R0's extrapolation-risk formula is miscalibrated on constant/low-variance histories (every move, incl. a price cut, scores risk 1.0; +5% indistinguishable from +10%). | exp `b8516eef` zero-variance diagnostic; `_risk_from_extrapolation` code | synthetic | 42–46 | **ESTABLISHED (formal/analytic + synthetic)** |
| 11 | A robust-scale + bounded-weight variant (R3) removes that pathology on the synthetic suite: goal achievement 0.084 → 0.168 (*p* = 0.0253), risk-adjusted −2614.8 → +40.5, Spearman ρ 0.969, 0 monotonicity violations, confidence 0.109. | exp `b8516eef` | synthetic_scenario_suite | 42–46 | **SYNTHETIC-ONLY — "PROMISING"; not promoted** |
| 12 | On real Indian implied-price data (Benroshan, 23 sub-series, 184 rows), R0 and R1 are byte-identical; the low-variance pathology does not occur; R3 is inert; nothing regressed (ρ 0.989, 0 violations, extremes still penalised). | exp `70617412` | external-india-ecommerce-v1 | 42 | **REAL-DATA-DESCRIPTIVE / NOT-VALIDATED** |
| 13 | XGBoost had the lowest forecasting error on the evaluated Benroshan series (MAE 15.27 / RMSE 23.89 vs naive 19.92 / 31.25, 51 test days). | Table 1 `INDIA_REAL_BUSINESS` rows; `paper_results_snapshot` | external-india-ecommerce-v1 | 42 | **REAL-DATA-DESCRIPTIVE** (single small series; MAPE uninterpretable; no significance) |
| 14 | XGBoost had the lowest error on the synthetic platform forecasting set (MAE 15.14 / RMSE 21.86 / MAPE 10.30%). | exp `c2b3a2fa` | platform-forecasting-v1 | 42 | **SYNTHETIC-ONLY / DESCRIPTIVE** (1 seed, no CI) |
| 15 | On the synthetic churn set the three models reach F1 ≈ 0.66–0.67 and ROC-AUC ≈ 0.79. | exp `21e8e800` | platform-churn-v1 | 42 | **SYNTHETIC-ONLY / DESCRIPTIVE** |
| 16 | On the synthetic Indian-context customer set, models reach ROC-AUC ≈ 0.75 but near-zero precision/recall at the default threshold (22.5% positive). | `benchmark_results.json` | external-india-customer-synthetic-v1 | 42 | **SYNTHETIC-INDIAN-CONTEXT / DESCRIPTIVE** (not real customer behaviour) |
| 17 | Pairwise-Granger recovery on a known synthetic DAG: recall 1.00, precision 0.40, SHD 3 — 3 false positives (transitive + reverse + spurious) are the documented method limitation. | exp `36d0d404` | synthetic_causal_validation | 42 | **SYNTHETIC-ONLY — method validation** |
| 18 | No real causal effect has been validated: `CAUSALLY_VALIDATED = 0`; the feedback rule never auto-promotes; DATA_SUPPORTED needs a Granger pass on real data. | code (`causal_feedback_service.py`); `REAL_EVIDENCE_STATUS_REPORT.md` | n/a | n/a | **NOT-READY / DO-NOT-CLAIM causality** |
| 19 | The Digital Twin's real predicted-vs-actual accuracy is unknown. | exp `2f7da989` `sample_size = 0`; `paper_results_snapshot` Table 2 `available:false` | REAL_INDIAN_SME_OUTCOME | n/a | **NOT-READY** |
| 20 | Real-LLM behaviour is untested. | `settings.llm_enabled = False` | n/a | n/a | **NOT-TESTABLE / BLOCKED** |
| 21 | The confidence score is fully reproducible from stored components (`agreement × risk × causal_evidence × (1 − uncertainty_penalty)`). | `strategy_optimizer.resolve`; `RESEARCH_EXPERIMENT_REPORT.md` §7 worked example | synthetic | 42 | **ESTABLISHED (analytic)** — but not linked to any user-perceived confidence |
| 22 | The system refuses recommendations when required data is absent (marketing-ROI / inventory-risk goals without the data return an explicit insufficient-evidence result). | `capability_service.py`; `strategy_generation_service.generate_candidates` | n/a | n/a | **ESTABLISHED (behavioural)** |
| 23 | DecisionGPT improves outcomes for Indian SMEs. | — | — | — | **DO-NOT-CLAIM** |
| 24 | DecisionGPT is superior to existing decision-support systems. | no external-system comparison exists | — | — | **DO-NOT-CLAIM** |
| 25 | Results generalise to the Indian SME population. | designed synthetic scenarios + 1 real dataset | — | — | **DO-NOT-CLAIM** |

---

## F. Final contribution list (retain only what the repo supports)

1. **An integrated, capability-gated decision-support architecture** that
   connects goal parsing → strategy generation → Digital-Twin simulation →
   evidence-labelled causal context → rule-based multi-agent evaluation with a
   fixed, version-tagged optimizer formula → risk-aware recommendation →
   reproducible confidence → decision/outcome memory. *Contribution type:*
   systems / engineering integration + a precise, auditable scoring pipeline.
2. **A controlled multi-scenario evaluation methodology** (12 designed
   scenarios × 5 seeds, paired per `(scenario, seed)`, pre-registered
   Student-t CIs + paired Wilcoxon + effect sizes, with a documented KPI-proxy
   rule and fairness controls) that isolates the marginal contribution of each
   architectural component. *Type:* methodological.
3. **A reproduced negative result**: within this architecture, deterministic
   Digital-Twin simulation is the only component with measurable objective
   value; a multi-agent debate layer *reduces* goal achievement on the tested
   suite. Reproduced byte-identically across a candidate-space correction.
   *Type:* empirical (and the paper's most defensible novel finding).
4. **Discovery and correction of a candidate-space confound**, with a
   pre-registered coverage invariant, showing the negative result is a
   scoring-rule effect rather than an unequal-strategy-space artefact.
   *Type:* methodological / failure analysis.
5. **A pre-registered diagnosis and calibration of the extrapolation-risk
   formulation**: a formal zero/low-variance degeneracy, a robust-scale fix
   (R3) that is PROMISING on the synthetic suite under seven pre-specified
   criteria, and an honest external probe on real Indian price data where the
   pathology does not arise (R3 inert, nothing regressed). *Type:*
   methodological + empirical, with a clean negative external result.
6. **A reproducible research infrastructure with strict evidence separation**:
   five data categories that are never averaged, provenance/leakage controls, a
   16-experiment manifest tracing every paper number to an
   `experiment_id`/seed/dataset/model version, a clean-room dependency
   validation, and a "NOT READY / BLOCKED" discipline for real-SME, Table 2 and
   real-LLM evidence. *Type:* infrastructure / open-science.

*Not retained as contributions:* "explainability improves understanding" (no
study), "causal reasoning improves decisions" (0 delta), "multi-agent improves
evaluation" (refuted), "validated for Indian SMEs" (no real outcomes).

---

## G. Recommended paper structure

Reordered from the generic outline to lead with the architecture and the
controlled evaluation, and to make the negative result and the risk-calibration
study first-class.

1. **Abstract** — see §O.
2. **Introduction** — Indian SME data-constraint context; the goal→action gap
   in BI/predictive analytics; what an integrated pipeline could do; the
   question of whether more architecture helps.
3. **Research Questions & Contributions** — reframed RQs (§D) + §F.
4. **Related Work** — §J categories; position DecisionGPT as an *integration +
   evaluation testbed*, not a claimed SOTA.
5. **DecisionGPT Architecture** — goal planner; strategy generation
   (goal-templated, capability-gated); Digital Twin (recursive forecast +
   extrapolation-risk heuristic); Dynamic Causal Graph (evidence levels
   ASSUMED→OBSERVATIONAL→DATA_SUPPORTED→CAUSALLY_VALIDATED; never auto-promoted);
   Multi-Agent Engine (3 rule-based agents, 2-round debate — explicitly *no LLM
   in scoring*); Strategy Optimizer (fixed `v2` formula
   `(BA+FA)/2 − λ·(1−RM)`, λ = 1); Explainability (post-hoc narration);
   Memory. State clearly which parts are deterministic.
6. **Indian SME Data Architecture & Data Governance** — five categories,
   capability detection, provenance, leakage controls, the "refuse rather than
   fabricate" rule. (Merge the old "Datasets" section here.)
7. **Experimental Methodology** — seeds; the 12-scenario suite (designed, not
   sampled); pairing; fairness; KPI-proxy rule for S04/S07; statistics
   (`_summ`/`_paired`: Student-t CI, paired Wilcoxon `zero_method="wilcox"`,
   effect size \|Z\|/√N, "significance not assessed" when all diffs zero);
   pre-registration for the risk study.
8. **Predictive Component Evaluation** — Table 1 (forecasting real vs synthetic
   blocks kept separate; churn synthetic) + the synthetic-Indian-context
   customer benchmark, each with its own caveats.
9. **Causal Graph Method Validation** — Table 3; synthetic ground truth;
   pairwise-Granger limitations; explicit `CAUSALLY_VALIDATED = 0`.
10. **Architecture Comparison** — Table 4 / Figure 5; the A/B/C/D result;
    the negative D-vs-B finding with CIs, Wilcoxon, wins/ties/losses.
11. **Ablation Study** — Table 5 / Figure 6; only-the-Digital-Twin-matters;
    Causal Graph → confidence only.
12. **Multi-Agent Failure Analysis** — the candidate-space confound, its
    correction, the coverage invariant, the byte-identical re-test; failure-mode
    shift (`CANDIDATE_SET_MISMATCH` → `RISK_OVERRULE`); the risk-penalty
    isolation (D1) with its caveats.
13. **Risk Manager Calibration** — the zero-variance degeneracy (analytic +
    diagnostic), R0/R1/R2-λ/R3, the seven pre-specified criteria, Table 6,
    Figure 9; the real-data probe (`70617412`) and why R3 is inert there.
    Verdict: PROMISING (synthetic) / NOT VALIDATED (real) / not promoted.
14. **Discussion** — why deterministic simulation dominates a flat-scored agent
    debate in template mode; what a real LLM might change (separated growth
    scores); implications for building decision-support for data-poor SMEs
    (favour transparent simulation; bound risk terms).
15. **Limitations** — §L.
16. **Threats to Validity** — §L (internal / external / construct / statistical).
17. **Reproducibility** — commit `ef9ade8`; Python 3.12.0; corrected
    `requirements.txt` (numpy 2.5.2, scipy/joblib declared); seed 42; 16-experiment
    manifest; deterministic re-run; the `docs/RESEARCH_REPRODUCIBILITY.md`
    commands; note the doc meta-count staleness (§0) is cosmetic.
18. **Conclusion** — the integrated architecture + the honest component-level
    finding + the reproducible testbed; real-world validation is future work.
19. **Future Work** — real SME outcome collection (workflow ready); real-LLM
    arm (protocol frozen); AGMARKNET; repeated-seed CIs for forecasting/churn;
    a real intervention study for causal validation; a human explainability study.
20. **Appendix** — legacy single-scenario runs (preserved); confidence-formula
    worked example; full failure-mode tables; pre-registration texts.

---

## H. Table plan

| Table | Content | Source | Recommendation |
|---|---|---|---|
| **Table 1 — Predictive Model Performance** | Two clearly separated blocks. *Forecasting:* `INDIA_REAL_BUSINESS` (Benroshan, 51 test days): naive MAE 19.92 / RMSE 31.25, linear 18.47 / 28.51, xgboost 15.27 / 23.89 — **MAPE omitted** (zero-actual days → 110–276%, uninterpretable). `SYNTHETIC_CONTROLLED` (platform, 265 test rows): naive 24.66 / 38.28 / 15.46%, linear 17.29 / 25.51 / 12.49%, xgboost 15.14 / 21.86 / 10.30%. *Classification (churn, `SYNTHETIC_CONTROLLED`):* logreg P 0.708 / R 0.634 / F1 0.669 / AUC 0.798; rf F1 0.661 / AUC 0.793; xgb F1 0.658 / AUC 0.792. | `paper_results_snapshot.json`; exps `c2b3a2fa`, `21e8e800`; archived v2 forecasting models | **Include.** Every row carries `Status` + `Data category`. Add a footnote that the two forecasting blocks are never combined and that the real block is a single small series (descriptive, no inference). |
| **Table 2 — Digital Twin Prediction Evaluation (real)** | Predicted vs actual revenue/profit/units for real SME decisions. | exp `2f7da989`, `sample_size = 0` | **Show as an explicit "NOT READY" placeholder in the main text** (one line: "requires ≥ 5 genuine `REAL_INDIAN_SME_OUTCOME` matched records; currently 0"), and list it under Future Work. Do **not** silently omit — its absence is a finding. Do **not** fill it with synthetic simulations. |
| **Table 3 — Causal Graph Recovery (synthetic method validation)** | precision 0.40, recall 1.00, F1 0.571, SHD 3; TP {A→B, B→C}; FP {A→C, B→A, D→B}; FN none. | exp `36d0d404` | **Include**, titled to make "synthetic / method validation" unmissable; caption states pairwise Granger, `max_lag = 3`, no multiple-comparison correction, and `CAUSALLY_VALIDATED = 0`. |
| **Table 4 — Decision Architecture Comparison** | A/B/C/D mean goal achievement + std + 95% CI + mean risk-adjusted + mean confidence + latency; plus the two pairwise rows (D vs A: +0.084, 10/50/0, *p* = 0.0045, r = 0.90; **D vs B: −0.401, 0/15/45, *p* < 0.0001, r = 0.87**); robustness (B beats Full 45/60, never loses). | exp `0e1bd8dc` (POST); note PRE `675cf17e` identical | **Include as the primary result table.** Use the POST-correction run. One row/footnote noting PRE == POST. |
| **Table 5 — Ablation Study** | Δ goal achievement vs Full for "without {Digital Twin, Causal Graph, Multi-Agent, Explainability, Memory}": +0.084 [+0.013, +0.156] / 0.000 / 0.000 / 0.000 / 0.000; plus the confidence effect of removing the Causal Graph (0.139 → 0.251). | exp `db58455b` (POST) | **Include.** Report the exact zeros as-is. |
| **Table 6 — Risk Manager Calibration (supplementary)** | R0 / D1 / R1 / R2-0.25/0.50/0.75 / R3: mean goal achievement, risk-adjusted, confidence, Spearman ρ, monotonicity violations, Wilcoxon vs R0, criteria passed (x/7), verdict. Headline: R3 0.168 / +40.5 / 0.109 / ρ 0.969 / 0 / *p* = 0.0253 / 7-of-7 / PROMISING; not promoted. | exp `b8516eef` | **Include as supplementary** (appendix or a boxed sub-table in §13), explicitly "synthetic suite; production stays R0/D0". |
| **Table 7 — Real-data risk probe (optional, small)** | 23 Benroshan sub-series by variance regime (3/11/9); R0 == R1 on 184/184 rows; ρ 0.989; 0 violations; 82% of out-of-range extremes ≥ 0.15; SIMULATED decision identical across variants. | exp `70617412` | **Optional** — a compact table or prose in §13 / §Threats. Label every decision number "SIMULATED"; state n_businesses = 1, no inferential test. |
| Legacy single-scenario (arch `a32933ca`, abl `1fcca452`) | A 0 / B 0.333 / C 0 / D 0; deltas 0. | manifest | **Appendix only** ("preserved, superseded by the multi-scenario runs"). |

---

## I. Figure plan

| Figure | Content | Supported? | Recommendation |
|---|---|---|---|
| **F1 — Architecture overview** | Goal → strategy gen → Digital Twin → causal context → 3-agent debate → optimizer → recommendation → memory; annotate which blocks are deterministic and where (if enabled) the LLM touches (parse + narrate only). | Yes (static) | Include. |
| **F2 — Forecasting comparison** | Bar chart, real block and synthetic block **side by side but separately scaled/labelled** (MAE, RMSE). | Yes (Table 1) | Include; no combined bar. |
| **F3 — Digital Twin predicted vs actual (real)** | scatter of predicted vs actual outcome. | **No — 0 real outcomes** | **Omit from main paper.** Optionally a greyed "pending" panel in Future Work; never a populated-looking figure. |
| **F4 — Causal recovery** | recovered graph vs ground-truth DAG, FP edges highlighted; precision/recall/SHD. | Yes (`36d0d404`) | Include, labelled synthetic method validation. |
| **F5 — Architecture comparison** | mean goal achievement per architecture with 95% CI; overlay wins/ties/losses vs Full. | Yes (`0e1bd8dc`) | Include (primary figure). |
| **F6 — Ablation** | Δ goal achievement vs Full per removed component (bars near zero except Digital Twin), with CI on the Digital-Twin bar; a second panel for the confidence effect of the Causal Graph. | Yes (`db58455b`) | Include. |
| **F7 — Scenario robustness** | distribution of Full's per-(scenario, seed) goal achievement (median 0.00, best 1.00, std 0.28) vs B's. | Yes (`0e1bd8dc` detail) | Include (strengthens the negative result). |
| **F8 — Feedback loop schematic** | decision → outcome → evaluation → causal/memory update. | Schematic only (0 live data) | Include **as a schematic**, captioned "no live data: 0 recorded outcomes". |
| **F9 — Risk calibration** | R0 vs R1 risk score vs price-move size for constant / low-variance / normal-variance histories (the monotonicity fix); and variant vs goal-achievement / risk-adjusted. | Yes (`b8516eef`) | Include in §13 (supplementary). |
| **F10 — Multi-agent override / failure modes** | PRE vs POST failure-mode composition (CANDIDATE_SET_MISMATCH → RISK_OVERRULE); override rate 1.00, 0 improved / 45 degraded. | Yes (`c58c4537`, `f24abc1b`) | Include in §12. |

---

## J. Literature research plan (search terms + what each must establish; **no fabricated citations**)

| Area | Search terms | The paper needs the literature to establish |
|---|---|---|
| SME / MSME decision support | "SME decision support system", "MSME analytics India", "small business business intelligence adoption", "data poverty small firms" | that data-constrained SMEs are underserved by action-oriented decision support; motivates capability gating and the Indian framing. |
| Decision intelligence / prescriptive analytics | "decision intelligence", "prescriptive analytics", "goal-oriented decision support", "recommendation to action gap" | the goal→strategy→action framing and the gap beyond descriptive/predictive BI. |
| Business digital twins | "digital twin business process", "enterprise digital twin", "what-if simulation decision support", "simulation-based optimization business" | prior use of simulation for strategy what-ifs; positions the Digital Twin as the load-bearing component. |
| Causal inference for business | "Granger causality business time series", "causal discovery observational data limitations", "structural Hamming distance evaluation", "transitive edge pairwise causality", "PC algorithm vs Granger" | that pairwise Granger cannot identify direct vs transitive edges and needs MC correction — supports the precision-0.40 interpretation and `CAUSALLY_VALIDATED = 0`. |
| Multi-agent / LLM-agent decision systems | "multi-agent LLM decision making", "agent debate", "LLM ensemble reasoning", "does multi-agent help", "negative results LLM agents" | prior claims (and any prior negative results) for multi-agent debate improving decisions; frames the negative finding as a contribution, not a bug. |
| Risk-aware optimization | "risk-adjusted decision score", "risk penalty weighting", "extrapolation risk machine learning", "out-of-distribution model reliability", "robust scale MAD normalization" | that penalising extrapolation is standard but weighting it is a design choice; supports the λ / robust-scale study. |
| Forecasting baselines | "naive seasonal baseline forecasting", "XGBoost demand forecasting retail", "MAPE zero values undefined", "forecast accuracy small samples" | why naive/linear/XGBoost is a reasonable ladder and why MAPE is omitted for the real series. |
| Indian retail / MSME data landscape | "AGMARKNET data", "UDYAM registration data", "Indian e-commerce dataset", "retail sales India public dataset availability" | scarcity of row-level real Indian SME data — supports the synthetic-controlled + public-context strategy and the provenance-unverified caveat. |
| Explainable AI for decisions | "explanation faithfulness", "post-hoc explanation decision support", "user trust AI recommendations", "explanation vs decision quality" | that post-hoc narration ≠ decision improvement, and that a user study is the right instrument (future work). |
| Reproducibility / open science in ML | "experiment manifest reproducibility", "seed control ML experiments", "pre-registration machine learning", "data leakage prevention evaluation" | norms the infrastructure contribution is measured against. |
| Research-methods framing | "negative results value", "ablation study methodology", "confound identification experiments", "controlled scenario evaluation" | legitimises a negative-result + failure-analysis paper. |

---

## K. Reviewer attack surface

| # | Likely reviewer objection | Current exposure | Mitigation in the paper |
|---|---|---|---|
| 1 | "The scenarios are synthetic and *designed*, so none of this generalises." | High. All decision evidence is synthetic; CIs are within-suite. | Frame explicitly as a controlled testbed; never say "population"; report the negative result as *architecture-internal*; move real validation to Future Work with the ready workflow. |
| 2 | "Template-mode agents are strawmen — of course a rule-based debate with flat scores loses." | High. BA/FA ≈ 0.5 for every candidate; round-2 inactive. | State it up front as a **scoped** claim ("the implemented configuration in deterministic mode"); dedicate a Discussion paragraph to what a real LLM might change; cite the frozen real-LLM protocol; do not generalise to "multi-agent systems are useless". |
| 3 | "You only compare internal architectures — no external baseline / no SOTA." | High. No comparison to any third-party system. | Do not claim superiority over external systems anywhere; position the contribution as *component isolation within one architecture* + methodology + infrastructure. |
| 4 | "Goal achievement is a proxy KPI; S04/S07 use a revenue proxy for non-simulated KPIs." | Medium. Documented; 2/12 scenarios. | Keep the KPI-proxy rule in Methodology; report S04/S07 flagged; show the result holds if those 2 scenarios are dropped (data exists in the detail export). |
| 5 | "The real forecasting dataset has unverified provenance and n ≈ 1." | Medium. | Label every Benroshan number `INDIA_REAL_BUSINESS`, provenance unverified, single small series, descriptive, no significance; MAPE omitted with reason. |
| 6 | "Precision 0.40 on causal recovery is weak, and you call it validation." | Medium. | Title it *method validation*; explain recall 1.00 + 3 structurally-explained FPs; state pairwise Granger cannot identify direct vs transitive; `CAUSALLY_VALIDATED = 0`. |
| 7 | "R3 looks like p-hacking / a fix in search of a problem." | Medium. | Emphasise the **pre-registration** (`RISK_CALIBRATION_ANALYSIS.md`: formula, worked example, 3 variants, λ rule, 7 criteria all fixed before the run); report the real-data probe where R3 is **inert** (a negative external result you disclose yourself); production stays R0. |
| 8 | "Wilcoxon on 60 pairs where most differences are 0 (D vs A: 10 non-zero; R3: 5 non-zero) — effect sizes r ≈ 0.9–1.0 are inflated." | Medium–high. | Report N_nonzero explicitly next to every test; state r = \|Z\|/√N_nonzero and that r → 1 just means the few non-zero pairs agree in sign; foreground the **mean shift** (+0.084, +0.083) as the practical magnitude; call these "small, consistent" effects. |
| 9 | "Doc counts disagree (7 vs 16 experiments, head 0006 vs 0007, 218 vs 319 tests)." | Low (cosmetic). | §Reproducibility: one paragraph noting report headers are point-in-time snapshots; the manifest (16) + `FINAL_REPRODUCIBILITY_VALIDATION_REPORT.md` are authoritative; no metric affected. |
| 10 | "Confidence is an internal formula with no ground truth — why report it?" | Low–medium. | Report it only as a *reproducible internal signal* (worked example), never as calibrated user trust; note the Causal-Graph→confidence effect is the one place a non-Digital-Twin component moves a number. |
| 11 | "You changed dependencies during 'freeze'." | Low. | `FINAL_REPRODUCIBILITY_VALIDATION_REPORT.md`: the pinned stack was *uninstallable* (shap needs numpy≥2); minimal coherent fix; all frozen metrics reproduce byte-identically; models retrained at seed 42 to identical numbers. |
| 12 | "Kundan is synthetic but sits next to real numbers in Table 1." | Low–medium. | Separate block, `SYNTHETIC_INDIAN_CONTEXT` label, its own caption; never averaged; ROC-AUC only. |
| 13 | "No IRB / ethics for the SME data plan." | Medium (for the Future Work section). | State institutional/legal review is a prerequisite (templates exist); no data collected yet; consent + provenance + PII-rejection + no-leakage pipeline described. |

---

## L. Threats to validity

### Internal validity
- **Synthetic scenario generation.** Businesses are procedurally seeded
  (`scenario_id:seed`); economics (margin, elasticity, marketing effectiveness)
  are hand-set. The agent-layer regression could be specific to these
  generators' near-constant price histories (which is exactly what inflates the
  extrapolation-risk term).
- **Template-mode agents.** BA/FA return ≈ 0.5 for nearly every candidate and
  round-2 self-adjustment is inactive, so strategy ranking is unusually
  sensitive to the single risk term. A real LLM is untested.
- **Candidate-space correction.** A generator omission (no price-increase lever
  for revenue/sales goals) was found *after* the first run; corrected and
  re-run byte-identically, but this shows the initial design under-specified the
  comparison.
- **Risk-calibration design choices.** `REL_FLOOR = 0.15` and
  `λ ∈ {0.25, 0.50, 0.75}` are motivated but not uniquely justified; the study
  deliberately did not search further.
- **Proxy KPIs.** S04 (`inventory_risk`) and S07 (`marketing_roi`) have no
  simulated pair; `goal_achievement` uses a revenue proxy for them.
- **No real interventions.** Every "decision quality" number is simulated; no
  action was taken and measured.
- **Out-of-domain forecasting model in the real probe.** `70617412` Part B runs
  a model trained on synthetic platform data on Benroshan-derived features;
  `goal_achievement = 1.00` there is a simulation artefact.

### External validity
- **One small real dataset** (~500 orders, 12 months, 3 categories, 19 states),
  **provenance unverified**, price is *derived* (revenue ÷ units).
- **Zero real SME decision outcomes**; Table 2 NOT READY; no Digital-Twin
  real-accuracy evidence.
- **Synthetic Indian-context customer data is simulated** — not real behaviour.
- **AGMARKNET is agri wholesale prices**, `DATA_PENDING`, and not SME retail
  data even when populated.
- **Public context (festivals, RBI)** are covariates only.
- No claim beyond "this architecture, these scenarios" is supported.

### Construct validity
- **`goal_achievement`** = attainment of a scenario's own KPI from a *simulated*
  strategy output — a model-internal construct, not realised business value.
- **`risk_adjusted_score`** = `benefit × (1 − DT_risk_score)`; dominated by the
  extrapolation-risk heuristic, so it can stay negative even when raw KPI rises
  (D1 case).
- **`confidence`** = a fixed product of internal factors; not validated against
  any human or outcome notion of confidence.
- **Causal "evidence levels"** are graph-construction labels; `OBSERVATIONAL` /
  `DATA_SUPPORTED` counts in the dev DB come from synthetic/demo history, not
  interventions.

### Statistical validity
- **Designed, not random, scenarios** → Student-t CIs describe within-suite
  sampling variability, not a population.
- **Few non-zero paired differences** (D vs A: 10/60; R3 vs R0: 5/60) → large r
  values reflect sign-consistency of a handful of pairs, not practical effect
  size; the mean shifts (+0.084, +0.083) are the honest magnitudes.
- **Clustering.** Multi-scenario obs share generators across seeds; the real
  probe's 307 "observations" are days of one business — **not** independent
  units (hence "NO INFERENTIAL TEST" there).
- **Single seed** for forecasting / churn / causal / customer → point estimates,
  no CIs, no significance.
- **Synthetic-suite p-values are never reused** as real-world evidence.

---

## M. Forbidden claims (explicit)

The paper must **not** state, imply, or let a figure/table suggest any of:

1. DecisionGPT is proven superior to existing / commercial decision-support
   systems (no external comparison exists).
2. DecisionGPT is validated across Indian SMEs, or improves real Indian SME
   performance / outcomes / revenue / profit.
3. The multi-agent layer improves decisions, evaluation, or business outcomes.
4. The Digital Twin's predictions are validated against real business outcomes
   (Table 2 is NOT READY).
5. R3 (or R1, R2) is superior in real businesses / should be adopted / is
   validated; or that production uses anything other than R0/D0.
6. Any causal effect is established, identified, or validated from the data;
   any `OBSERVATIONAL` / `DATA_SUPPORTED` count represents real causal evidence;
   `CAUSALLY_VALIDATED > 0`.
7. Observational or synthetic correlations demonstrate causation.
8. The synthetic Indian-context customer dataset reflects real Indian customer
   behaviour.
9. AGMARKNET represents SME retail data.
10. Synthetic-suite results generalise to the Indian SME population.
11. Template-mode agent behaviour is equivalent to, or predictive of, real-LLM
    agent behaviour.
12. The 95% CIs are population intervals, or the Wilcoxon effect sizes indicate
    large practical effects.
13. Explainability improves user understanding/trust (no study).
14. The candidate-space correction changed the result (it did not).
15. Forecasting/churn point estimates are statistically significant or
    generalisable (single seed; the real forecasting series is one small sample).
16. Any averaging of metrics across data categories.

---

## N. Recommended title options

Ordered by how well they match the evidence. All avoid "for Indian SMEs" as a
validated claim and avoid foregrounding the component that regresses.

1. **"Does a Multi-Agent Layer Help? A Controlled Component-Level Evaluation of
   an Integrated Decision-Support Architecture for Data-Constrained SMEs"**
   *(Recommended — leads with the real question and the honest finding.)*
2. **"DecisionGPT: An Integrated Goal-to-Strategy Decision-Support Architecture
   and a Reproducible Evaluation of Its Components"**
3. **"When More Architecture Doesn't Help: Isolating the Value of Digital-Twin
   Simulation, Causal Reasoning, and Agent Debate in SME Decision Support"**
4. **"A Reproducible Testbed for Decision-Support Architectures: Evidence that
   Digital-Twin Simulation, Not Agent Debate, Drives Strategy Selection"**
5. **"Goal-Driven Decision Support with a Business Digital Twin, Causal Context,
   and Multi-Agent Debate: Design, Controlled Evaluation, and Failure Analysis"**

Avoid the current working title
("…for Explainable Strategic Decision Support in Indian SMEs") — "explainable"
is unmeasured and "in Indian SMEs" implies validation that does not exist.

---

## O. Recommended abstract claims (skeleton — fill numbers from §C)

Use only these load-bearing statements:

- **Context.** Data-constrained SMEs need action-oriented decision support that
  connects goals to strategies; predictive BI stops short of that.
- **System.** We present DecisionGPT, an integrated architecture combining
  goal parsing, capability-gated strategy generation, a business Digital Twin
  (recursive forecast + extrapolation-risk heuristic), an evidence-labelled
  dynamic causal graph, a three-agent rule-based debate, a fixed-formula
  risk-aware optimizer, post-hoc explanation, and decision memory. Agent
  scoring is deterministic; an LLM, when configured, only parses the goal
  sentence and narrates results.
- **Evaluation.** We run a controlled 12-scenario × 5-seed comparison (60 paired
  observations per arm) with pre-registered statistics, an ablation, a
  multi-agent failure analysis, and a pre-registered risk-calibration study.
- **Findings (state plainly).**
  (i) Digital-Twin simulation is the only component with measurable objective
  value: mean goal achievement 0.000 (prediction-only) → 0.486 (with the Digital
  Twin).
  (ii) Adding a multi-agent debate layer *reduces* mean goal achievement to
  0.084 — significantly below the Digital-Twin-only architecture (paired
  Wilcoxon *p* < 0.0001; it loses 45 of 60 paired scenarios and wins none).
  (iii) The regression is a scoring-rule effect (an unbounded risk-penalty term
  over a mis-scaled extrapolation-risk heuristic), not a candidate-space
  artefact; a pre-registered robust-scale calibration (R3) improves the
  synthetic risk/benefit trade-off (PROMISING) but is inert on the one
  available real Indian dataset (NOT VALIDATED) and is not adopted.
  (iv) Predictive components perform as expected on their (mostly synthetic)
  datasets; causal recovery is validated on synthetic ground truth only
  (recall 1.00, precision 0.40).
- **Scope / non-claims.** All decision evidence is synthetic and scenario-based;
  there are zero real SME decision outcomes, no real-LLM evaluation, and no
  human explainability study; we make no superiority or generalisation claim.
- **Contribution.** A reproducible decision-support testbed, a component-isolation
  methodology, a documented negative result about agent debate, and a
  pre-registered risk-calibration analysis — with all 16 experiments and the
  data-category separation released for reproduction.

---

## P. Final paper-readiness verdict

| Dimension | Verdict |
|---|---|
| Is there a defensible paper here? | **YES** — as a controlled architecture-evaluation + methodology + reproducibility paper with a documented negative result, **not** a superiority/validation paper. |
| Central research question defensible? | **YES**, once reframed to component-level value within one architecture (§D). The original "improves decision support for Indian SMEs vs predictive analytics" is **not** supported and must be dropped as a claim. |
| Tables ready for a main paper? | **Tables 1, 3, 4, 5 READY** (4/5). **Table 2 NOT READY** — present as an explicit placeholder + Future Work. Table 6/7 (risk) READY as supplementary. |
| Figures ready? | F1, F2, F4, F5, F6, F7, F8 (schematic), F9, F10 READY. **F3 (Digital-Twin predicted-vs-actual) NOT available** — omit. |
| Statistics defensible? | **YES**, with the disclosures in §K/§L (report N_nonzero and mean shifts alongside every Wilcoxon; call the effects small-and-consistent; no population language; single-seed experiments stay descriptive). |
| Related work done? | **NO** — external literature search still required (§J). No citations exist yet; none may be fabricated. |
| Real-world validation? | **NOT DONE** — 0 real SME outcomes, real-LLM BLOCKED, no human study. All correctly labelled; belongs in Future Work with the ready collection workflow + frozen protocols. |
| Research integrity risks? | **LOW** — evidence separation, pre-registration, and "NOT READY / BLOCKED" discipline are already in place. The only cleanup is cosmetic doc meta-count staleness (§0), to be acknowledged in §Reproducibility. |
| Recommended positioning | **Moderate claim** (see below). |

### Recommended exact claim level

- **Strong claim (allowed):**
  *"DecisionGPT is a reproducible, capability-gated architecture for goal-driven,
  risk-aware decision support, and our controlled multi-scenario evaluation
  isolates the objective contribution of each component."*
- **Moderate claim (the paper's headline):**
  *"On a controlled 12-scenario suite, deterministic Digital-Twin simulation is
  the only component that improves goal achievement; adding a multi-agent debate
  layer significantly reduces it, through an identifiable and pre-registered
  scoring-rule mechanism rather than an unequal strategy space."*
- **Supplementary claim (allowed):**
  *"The extrapolation-risk formulation is miscalibrated for low-variance price
  histories; a pre-registered robust-scale variant corrects this on the
  synthetic suite (PROMISING) but is inert on the one available real Indian
  dataset (NOT VALIDATED); production is unchanged."*
- **Not allowed (see §M):** any statement that DecisionGPT improves real Indian
  SME outcomes, beats external systems, validates causality, or that its
  multi-agent / Digital-Twin behaviour is validated against real outcomes.

**FINAL VERDICT: EVIDENCE AUDIT COMPLETE — PAPER IS WRITABLE AS A
CONTROLLED-EVALUATION / NEGATIVE-RESULT / REPRODUCIBILITY CONTRIBUTION.**
Blocked only on (a) external literature research (§J) and (b) authors' choice of
title/framing from §N. Do not begin drafting prose until the framing in §D and
the claim level in §P are accepted.
