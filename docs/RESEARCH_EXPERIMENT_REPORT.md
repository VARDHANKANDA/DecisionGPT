# DecisionGPT — Research Experiment Report

Frozen experimental evaluation. Every result is read from a stored
`ExperimentRun` / `MLModel` / `benchmark_results.json` — nothing here is
recomputed or hand-typed. Reproduce with `docs/RESEARCH_REPRODUCIBILITY.md`.

## 0. Freeze record

| Field | Value |
|---|---|
| Code commit | `eb7d392` + this commit |
| Seed | 42 (all deterministic experiments) |
| Alembic head | `0006` |
| Manifest | `experiments/experiment_manifest.json` (7 experiments, all `completed`) |
| Paper-results snapshot | `experiments/paper_results_snapshot.json` (4 / 5 tables ready) |
| Active model set | 6 v1 models — **unchanged** before/after the run (asserted) |
| Timestamp | 2026-08-29 |

## 1. Data categories (kept separate — never averaged)

| Category | Datasets in this run |
|---|---|
| `INDIA_REAL_BUSINESS` | `external-india-e-commerce-forecasting` v1 (Benroshan, CC0). Real Indian e-commerce; **provenance not independently verified**; small (~500 orders / 12 months / 3 categories). Not claimed to represent all Indian SMEs. |
| `SYNTHETIC_CONTROLLED` | `platform-forecasting-v1`, `platform-churn-v1`, synthetic causal ground truth, synthetic decision scenario |
| `SYNTHETIC_INDIAN_CONTEXT` | `external-india-customer-…-purchase-prediction` v1 (Kundan, CC BY 4.0) — explicitly simulated |
| `INDIA_PUBLIC_CONTEXT` | India festival calendar, RBI policy repo rate |
| `INDIA_AGRICULTURAL_PRICE` | AGMARKNET — supplementary agri wholesale price series, **`DATA_PENDING`**, excluded from this run. **Not SME retail data.** |

---

## Experiment 1 — Indian forecasting

Existing Training Center (`training_service.start_training`), models `naive`,
`linear`, `xgboost`, seed 42, chronological split. Results recorded as
`experimental` `MLModel` rows; active models untouched.

### 1a. `INDIA_REAL_BUSINESS` — Benroshan e-commerce (daily total units, 51 test days)

| Model | MAE | RMSE | MAPE | improvement_vs_naive (MAE) |
|---|---:|---:|---:|---:|
| naive | 19.92 | 31.25 | — | — |
| linear | 18.47 | 28.51 | — | +7.3 % |
| xgboost | **15.27** | **23.89** | — | **+23.3 %** |

**MAPE omitted** because the test series contains zero actual values
(the recorded MAPE, 110–276 %, is not interpretable). RMSE improvement of
xgboost vs naive: **+23.5 %**. Single small series → **descriptive result;
sample size insufficient for statistical inference.** No significance test
performed or claimed.

### 1b. `SYNTHETIC_CONTROLLED` — platform forecasting (265 test rows)

| Model | MAE | RMSE | MAPE |
|---|---:|---:|---:|
| naive | 24.66 | 38.28 | 15.46 % |
| linear | 17.29 | 25.51 | 12.49 % |
| xgboost | **15.14** | **21.86** | **10.30 %** |

MAPE is valid here (no zero actuals). xgboost vs naive: MAE **−38.6 %**,
RMSE **−42.9 %**.

**The two blocks are reported separately and never combined.**

---

## Experiment 2 — Synthetic Indian customer benchmark (`SYNTHETIC_INDIAN_CONTEXT`)

Standalone (`scripts/run_india_customer_benchmark.py`) — **not** an `MLModel`,
**not** wired into the Training Center. Target `purchased`; stratified 75/25;
seed 42; 6 250 test rows; 22.5 % positive. Leakage fields excluded
(`revenue`, `revenue_normalized`, `cart_abandoned`, `rating`, review fields).
`cart_abandoned` is **not** treated as churn.

| Model | Precision | Recall | F1 | ROC-AUC |
|---|---:|---:|---:|---:|
| logistic_regression | 0.00 | 0.00 | 0.00 | **0.760** |
| random_forest | 0.38 | 0.06 | 0.11 | 0.744 |
| xgboost | 0.36 | 0.01 | 0.02 | 0.757 |

**Class-imbalance-aware reading:** ROC-AUC ≈ 0.75 shows a real ranking
signal; the default-0.5-threshold precision/recall are near zero because the
models rarely predict the minority class. This is a **synthetic-data
demonstration only** — it is *not* real Indian customer validation and its
numbers are never merged with any real-world result.

---

## Experiment 3 — Digital Twin evaluation

`experiment_service.run_experiment("digital_twin")` inspects real
`PredictionEvaluation` records.

**Status: NOT READY.** `sample_size = 0` — there are **no matched
predicted/actual outcomes**. An SME (or a study participant) must record an
actual `DecisionOutcome` before this table can be produced. **No outcomes
were fabricated.**

### Controlled Digital-Twin *simulations* (not outcomes)

To show the twin produces predictions, one full decision was run through the
existing pipeline on the **demo synthetic business** (goal: +15 % revenue /
quarter, seed 42). 6 strategy scenarios were simulated:

| Scenario (strategy) | Predicted revenue | Predicted profit | Predicted units | Risk |
|---|---:|---:|---:|---:|
| baseline | 331 862 | 144 636 | 225.36 | — |
| Marketing +10 % | 332 422 | 144 880 | 225.74 | 0.0 |
| Marketing +20 % *(selected)* | 339 344 | 147 897 | 230.44 | 0.0 |
| Price −3 % | 321 906 | 134 680 | 225.36 | 0.0 |
| Price +5 % | 315 270 | 128 043 | 225.36 | 0.0 |
| (further price scenario) | 301 672 | 112 567 | 227.62 | 0.0 |

These are **simulations**, not actual outcomes — they become outcomes only if
an SME implements a strategy and the result is recorded.

---

## Experiment 4 — Causal graph evaluation (`SYNTHETIC GROUND TRUTH`)

`experiment_service.run_experiment("causal")` — 250 synthetic timesteps,
seed 42. Ground truth: `A → B → C` (lag 1 each), `D` independent noise.

| Metric | Value |
|---|---:|
| precision | 0.40 |
| recall | 1.00 |
| F1 | 0.571 |
| Structural Hamming Distance | 3 |
| recovered (true positive) edges | 2 — `A→B`, `B→C` |
| missing (false negative) edges | 0 |
| extra (false positive) edges | 3 — `A→C` (transitive), `B→A` (reverse), `D→B` |

Recall is perfect; the 3 false positives are the **documented limitation of
pairwise Granger causality** (no multiple-comparison correction; cannot
distinguish a transitive `A→C` from a direct effect). This validates the
*recovery method* on synthetic data — it does **not** prove causal validity
for any Indian business.

### Real-world causal evidence (separate)

| Evidence level | Edges | Note |
|---|---:|---|
| `ASSUMED` | all seeded edges | starting state |
| `OBSERVATIONAL` | 0 | needs ≥ 3 consistent intervention-like outcomes (`causal_feedback_service`) |
| `DATA_SUPPORTED` | 0 | needs the Granger test to pass on real business data |
| `CAUSALLY_VALIDATED` | 0 | **never produced automatically** |

No real `DecisionOutcome` records exist, so **no edge has moved above
`ASSUMED`**.

---

## Experiment 5 — Decision architecture comparison (multi-scenario)

`experiment_service.run_experiment("multi_scenario_architecture")` —
**12 scenarios × 5 seeds = 60 paired evaluations per architecture**
(`multi_scenario_service`, seeds 42–46; protocol in
`docs/MULTI_SCENARIO_EXPERIMENT_PROTOCOL.md`, stats in
`docs/STATISTICAL_ANALYSIS.md`). Same generated business / goal / candidate
grid / seed / horizon for every architecture. `goal_achievement` = attainment
of each scenario's own primary KPI.

> **Table 4 below is the POST-correction run** (`0e1bd8dc`), after the
> candidate-space confound was fixed (`docs/CANDIDATE_SPACE_CORRECTION_REPORT.md`).
> The pre-correction run (`675cf17e`, `PRE_CORRECTION …`) is preserved in the
> manifest. **The two runs are numerically identical for A–D** — the fix
> changed the strategy space Full DecisionGPT could consider but not the
> strategy it selected (the Risk Manager still rejects the price move). The
> Full-vs-Digital-Twin gap is therefore **not** an artefact of the
> candidate-space mismatch; it persists after alignment.

### Table 4 — aggregate (n = 60 per architecture)

| Architecture | Mean goal achievement | Std | 95% CI | Mean risk-adjusted score | Mean confidence | Mean latency (s) |
|---|---:|---:|---:|---:|---:|---:|
| A · Prediction only | 0.000 | 0.000 | [0.000, 0.000] | 0.0 | n/a | 0.19 |
| B · Prediction + Digital Twin | **0.486** | 0.314 | **[0.405, 0.567]** | 2 508.4 | n/a | 1.82 |
| C · + Single Agent | 0.003 | 0.006 | [0.001, 0.004] | 190.9 | n/a | 1.88 |
| D · Full DecisionGPT | 0.084 | 0.278 | [0.013, 0.156] | **−2 614.8** | 0.139 | 1.95 |

### Pairwise comparison (paired Wilcoxon signed-rank, two-sided, 60 pairs)

| Comparison | Mean diff (Full − other) | Median diff | 95% CI of mean diff | Wins / Ties / Losses (Full) | Wilcoxon p | Effect size r | Result |
|---|---:|---:|---:|---:|---:|---:|---|
| **Full (D) vs Prediction only (A)** | **+0.084** | 0.000 | [+0.013, +0.156] | 10 / 50 / 0 | **0.0045** | 0.90 | Full is **significantly higher** than A |
| **Full (D) vs Prediction + Digital Twin (B)** | **−0.401** | −0.413 | [−0.478, −0.324] | 0 / 15 / 45 | **< 0.0001** | 0.87 | Full is **significantly LOWER** than B |

### Interpretation — a decisive **mixed / negative** result

- The **Digital Twin adds large value**: mean goal achievement 0.00 (A) → 0.49
  (B).
- The **agent layers subtract value**: adding the single agent (C) or the full
  multi-agent debate (D) on top of the Digital Twin *reduces* mean goal
  achievement to 0.003 and 0.084 respectively, and makes the mean
  risk-adjusted score **negative**. Across the 60 paired evaluations, the
  simple B architecture **beats Full DecisionGPT on 45 and never loses**
  (`p < 0.0001`).
- Full **does** beat "prediction only" (A) — but only because A has no strategy
  mechanism at all (always 0), and Full still only wins 10 of 60.

**Cause (from the per-observation detail):** the agents repeatedly select a
"Marketing +10 %" / "Marketing −10 %" strategy that the Digital Twin scores at
zero or negative benefit, whereas B directly picks the KPI-maximising
simulated candidate (typically a price move). See *Failure-mode analysis*.

### Robustness (each architecture vs Full, on goal achievement, 60 pairs)

| vs Full | wins | ties | losses |
|---|---:|---:|---:|
| A | 0 | 50 | 10 |
| B | **45** | 15 | 0 |
| C | 5 | 50 | 5 |

Full DecisionGPT's own distribution: best 1.00, worst 0.00, **median 0.00**,
std 0.28 — i.e. on most scenario/seeds Full achieves nothing toward the goal.

### Failure-mode analysis (correlational, not causal)

**50 of 60** Full-DecisionGPT observations fall in the bottom tercile
(goal achievement ≈ 0). Associated factors, in order of frequency:
`non-positive risk-adjusted score` (agents chose a strategy the twin scores ≤ 0),
`simpler architecture B did better on this scenario/seed`,
`low decision confidence (< 0.20)`. The 2 KPI-proxy scenarios (S04, S07) also
carry `goal KPI not directly simulated`. These are **associations**, not
demonstrated causes.

---

## Experiment 6 — Ablation study A–F (multi-scenario)

`experiment_service.run_experiment("multi_scenario_ablation")` — the same 12
scenarios × 5 seeds. Ablation meanings unchanged (B = no Digital Twin →
architecture A; C–F = `PipelineOptions` toggles on the real pipeline).

> **Table 5 below is the POST-correction run** (`db58455b`); it was re-run
> because the corrected `strategy_generation_service.generate_candidates` sits
> on the pipeline path configs C–F exercise. It is **numerically identical**
> to the pre-correction run (`be392694`, `PRE_CORRECTION …`, preserved) — the
> candidate-space fix changed no config's outcome.
> See `docs/CANDIDATE_SPACE_CORRECTION_REPORT.md`.

### Table 5 — aggregate (n = 60 per configuration)

| Config | Component removed | Mean goal achievement | Δ vs Full (mean) | 95% CI of Δ | Mean risk-adjusted score | Mean confidence |
|---|---|---:|---:|---:|---:|---:|
| A · Full DecisionGPT | — | 0.084 | — | — | −2 614.8 | 0.139 |
| B · Without Digital Twin | `digital_twin` | **0.000** | **+0.084** | [+0.013, +0.156] | 0.0 | n/a |
| C · Without Causal Graph | `causal_graph` | 0.084 | 0.000 | [0.000, 0.000] | −2 614.8 | **0.251** |
| D · Without Multi-Agent | `multi_agent` | 0.084 | 0.000 | [0.000, 0.000] | −2 614.8 | 0.132 |
| E · Without Explainability | `explainability` | 0.084 | 0.000 | [0.000, 0.000] | −2 614.8 | 0.139 |
| F · Without Memory | `memory` | 0.084 | 0.000 | [0.000, 0.000] | −2 614.8 | 0.139 |

### Interpretation

Only **one** component moves goal achievement: the **Digital Twin**. Removing
it (config B) drops mean goal achievement 0.084 → **0.000**
(Δ +0.084, 95 % CI [+0.013, +0.156]) — no strategy is recommendable without it.
Removing the **Causal Graph, Multi-Agent, Explainability or Memory** produces a
`Δ vs Full` of **exactly 0.000** (n = 60), reported as-is.

- **Multi-Agent** (D): zero goal-achievement delta — consistent with
  Experiment 5, where adding the agent layer on top of the Digital Twin
  *lowers* mean goal achievement (0.486 → 0.084). Removing the agents from
  Full does not recover that because config D still routes through the same
  agent-selected strategy path as A here; the agent effect is measured
  directly in Experiment 5's A→B→C→D comparison.
- **Explainability** (E): structural zero — generated *after* strategy
  selection, never consulted while scoring. Confidence unchanged.
- **Memory** (F): zero — no recorded outcomes exist on fresh synthetic
  scenarios, so there are no memory insights to remove. Confidence unchanged.
- **Causal Graph** (C): zero goal-achievement delta, but a **real confidence
  effect** — mean confidence 0.139 → **0.251** (removing the causal-evidence
  penalty). This is the only non-Digital-Twin component with any measurable
  quantitative footprint, and it is on *confidence*, not on the objective.

**Conclusion (Experiments 5 + 6 together):** on this 12-scenario suite the
measurable value of DecisionGPT is concentrated entirely in the **Digital
Twin**. The Dynamic Causal Graph affects only reported confidence; the
Multi-Agent layer has **negative** value on the objective; Explainability and
Memory have **zero** quantitative effect (by design / for lack of outcome
history). This is reported exactly, not adjusted.

---

## Legacy single-scenario result (preserved, not overwritten)

The original `1 scenario × 1 seed` runs are kept unchanged as
`experiment_type = decision_architecture` / `ablation`
(`legacy_single_scenario_result` in the manifest):

| Architecture | Goal achievement | Risk-adjusted score |
|---|---:|---:|
| A · Prediction only | 0.00 | 0.00 |
| B · Prediction + Digital Twin | 0.333 | 2 826.88 |
| C · + Single Agent | 0.00 | 0.00 |
| D · Full DecisionGPT | 0.00 | 0.00 |

Legacy ablation: every `Δ vs Full` = 0.0; confidence moves 0.150 → 0.272 when
the Causal Graph is removed. **The multi-scenario run (Experiment 5/6) confirms
and strengthens this single-scenario finding** rather than contradicting it:
Full DecisionGPT does not outperform the leaner Prediction + Digital Twin
architecture — now measured across 12 diverse scenarios with `p < 0.0001`.

---

## Experiment 7 — End-to-end decision quality

Full pipeline (Goal → Strategy Generation → Digital Twin → Causal Context →
Multi-Agent Debate → Strategy Optimizer → Explainability → Recommendation) on
the demo synthetic business, seed 42.

| Field | Value |
|---|---|
| Goal | "Increase revenue by 15 % over the next quarter" |
| Strategy selected | **Marketing +20 %** (score 0.0225) |
| Expected outcome | revenue 339 344 (+2.3 % vs 331 863), profit 147 897, units 230.4 |
| Risk level | low (risk_score 0.0) |
| Confidence | **0.1468** |
| Causal evidence factor | 0.60 |
| Agent agreement | 0.9788 |
| Alternatives considered | Marketing +10 %, Price −3 %, Price +5 %, … (6 simulated) |

No "ground-truth best decision" is defined by this experiment, so none is
claimed. The architecture comparison (Experiment 5) is the closest thing to a
quantitative end-to-end benchmark and is reported there with its caveats.

### Confidence analysis (reproducible from stored components)

```
confidence = agreement × risk × causal_evidence × (1 − uncertainty_penalty)
0.1468     = 0.9788    × 0.5  × 0.6            × (1 − 0.5)
```

| Component | Value |
|---|---:|
| `agreement_factor` | 0.9788 |
| `risk_factor` | 0.5 |
| `causal_evidence_factor` | 0.6 |
| `uncertainty_penalty` | 0.5 |
| **product** | **0.14682** ✓ matches the stored `confidence` |

The confidence number is **not a black box** — it recomputes exactly from
`uncertainty_json.confidence_basis`.

---

## Causal feedback experiment

`causal_feedback_service` — verified by rule inspection + the existing tests
(no real outcomes exist to run it live):

| Rule | Value |
|---|---|
| One outcome upgrades an edge? | **No** — `n < MIN_OUTCOMES_FOR_OBSERVATIONAL` (3) |
| `ASSUMED → OBSERVATIONAL` requires | ≥ 3 consistent intervention-like outcomes on that *specific* edge, ≥ 2/3 consistent with the hypothesised sign |
| Automatic `CAUSALLY_VALIDATED`? | **Never** — still requires the separate Granger test in `causal_graph_service` |
| `CausalEvidenceUpdate` rows in this run | **0** (no real `DecisionOutcome` records) |

Reported fields when an update *does* occur: previous/new evidence level,
sample size, consistency count, supporting decision IDs, supporting outcome
IDs, graph version, method (`CAUSAL_FEEDBACK_METHOD`).

---

## Statistical analysis

| Experiment | Sample | Statement |
|---|---|---|
| Indian forecasting | 1 series, 51 test days | Descriptive result; insufficient sample size for reliable statistical inference. |
| Platform forecasting | 265 test rows, 1 seed | Point estimates only; no repeated seeds run, so no CI reported. |
| Customer benchmark | 6 250 test rows, 1 seed | Point estimates; ROC-AUC is the stable metric under imbalance. |
| **Architecture / ablation (multi-scenario)** | **12 scenarios × 5 seeds = 60 paired obs per group** | Mean / std / **Student-t 95 % CI**; **paired Wilcoxon signed-rank** (two-sided). Significance **is** assessed here and reported (D vs A: p = 0.0045; D vs B: p < 0.0001). |
| Architecture / ablation (legacy) | 1 scenario, 1 seed | Preserved as `legacy_single_scenario_result`; descriptive only. |
| Causal (synthetic) | 1 graph, 250 steps, seed 42 | Method-validation point estimate; documented Granger limitations. |

Forecasting / customer / causal: no repeated-seed runs → point estimates, no
significance claimed. The multi-scenario architecture / ablation experiments
**do** meet the assumptions for a paired non-parametric test (60 matched
pairs) and significance is reported where the test ran; where all paired
differences were zero the report says *"significance not assessed"*.

---

## Paper tables

| Table | Status | Backing |
|---|---|---|
| **Table 1 — Predictive Model Performance** | **READY** | `forecasting_performance` + `churn_performance` exports; rows carry `Status` + `Data category` so `INDIA_REAL_BUSINESS` and `SYNTHETIC_CONTROLLED` stay separate |
| **Table 2 — Digital Twin Prediction Evaluation** | **NOT READY — requires additional `DecisionOutcome` records** | `PredictionEvaluation` (0 matched) |
| **Table 3 — Causal Graph Evaluation** | **READY** | experiment `causal` (seed 42) — labelled `SYNTHETIC GROUND TRUTH` |
| **Table 4 — Decision Architecture Comparison** | **READY (multi-scenario, POST-correction)** | The final table uses the **POST-correction** run `multi_scenario_architecture` `0e1bd8dc` (candidate-space confound fixed); the **PRE-correction** run `675cf17e` is preserved and its result is documented under "Failure analysis / candidate-space correction" (`docs/CANDIDATE_SPACE_CORRECTION_REPORT.md`). The two are numerically identical, so no observations are mixed. `decision_architecture` (legacy, seed 42) also preserved. Exports: `decision_architecture` (aggregate), `decision_architecture_detail`. |
| **Table 5 — Ablation Study** | **READY (multi-scenario, POST-correction)** | Final table uses POST-correction `multi_scenario_ablation` `db58455b`; PRE-correction `be392694` preserved. Numerically identical. `ablation` (legacy) preserved. Exports: `ablation`, `ablation_detail`. |

Every table row traces to an `experiment_id` / `model_version` /
`dataset_version` / `seed` (and `scenario_id`) via
`experiments/experiment_manifest.json` (which now carries a `multi_scenario`
aggregate block) and `experiments/paper_results_snapshot.json`.

**Appendix — Risk Manager Sensitivity & Calibration Analysis.** Not a paper
table; supporting failure-analysis evidence only — the main Table 4 conclusion
continues to use **D0** (production Full DecisionGPT).
- `risk_manager_diagnostic` (`ba56e42b`): sensitivity variant **D1** (Risk
  Manager running, penalty un-weighted) raises mean goal achievement 0.084 →
  0.583 (paired Wilcoxon p < 0.0001, r = 0.89) — the risk-penalty term is the
  proximate mechanism. See `docs/RISK_MANAGER_DIAGNOSTIC_REPORT.md`.
- `risk_manager_calibration` (`b8516eef`): the R0 extrapolation-risk formula is
  confirmed miscalibrated on low-variance histories; a robust scale + bounded
  penalty weight (**R3**, λ = 0.25) improves mean goal achievement 0.084 →
  0.168 (p = 0.025) and risk-adjusted score −2 614.8 → +40.5 while preserving
  risk ordering (ρ 0.969) and confidence (0.109). Verdict **PROMISING**; no
  variant promoted. See `docs/RISK_MANAGER_CALIBRATION_REPORT.md` and the
  pre-registration `docs/RISK_CALIBRATION_ANALYSIS.md`.
- `risk_manager_real_data_validation` (`70617412`): external validation of R3 on
  real Indian data (Benroshan, `INDIA_REAL_BUSINESS`). Across 23 real price
  sub-series R0 and R1 are **byte-identical** — R0's pathology does not occur on
  real implied-price data; risk ordering, monotonicity and extreme-extrapolation
  penalisation all preserved; SIMULATED decision comparison identical across
  variants. Real-LLM **BLOCKED**, `DecisionOutcome` count 0. Verdict:
  **PROMISING BUT NOT VALIDATED** — hold; do not promote. See
  `docs/RISK_MANAGER_GENERALIZATION_REPORT.md`.

## Paper figures

| Figure | Status | Data source |
|---|---|---|
| 1 · Architecture overview | READY | static (`docs/INDIAN_SME_DATA_ARCHITECTURE.md`) |
| 2 · Forecasting model comparison | READY | Table 1 (real + synthetic blocks) |
| 3 · Digital Twin predicted vs actual | **NOT READY** — no actual outcomes | — |
| 4 · Causal graph recovery metrics | READY | experiment `causal` |
| 5 · Decision architecture comparison | READY | `multi_scenario_architecture` — mean goal achievement by architecture with 95 % CI + wins/ties/losses vs Full |
| 6 · Ablation results | READY | `multi_scenario_ablation` — mean Δ goal achievement vs Full per component (most ≈ 0, reported as-is) |
| 7 · Feedback loop | READY as a schematic; no live data (0 outcomes) | schematic only |
| (new) Scenario robustness | READY | per-observation goal-achievement distribution across the 12 scenarios (Experiments page detail view) |

## Research Dashboard

Verified pages: Overview, Dataset Registry (`{platform, external, uploaded}`,
`data_category` on every entry), Training Center, Model Registry, Experiments
(+ reproducibility manifest download; now offers `multi_scenario_architecture`
/ `multi_scenario_ablation` and renders their **aggregate table, 95 % CI,
paired Wilcoxon interpretation, robustness table, failure-mode list and a
scenario / seed / architecture-filterable per-observation table**), Model
Performance, Digital Twin Evaluation (explicit empty state), Causal
Evaluation, Multi-Agent Evaluation (now also renders the **Risk Manager
diagnostic** panel — RM disagreement / RM-decisive rates, DT-risk vs RM-score
calibration table, D0 vs D1 comparison, paired D1−D0 test, formula
verification, scenario drill-down — and the **Risk Manager calibration** panel:
R0/D1/R1/R2-λ/R3 comparison table, variant-vs-goal-achievement and
variant-vs-risk-adjusted charts, the zero-variance diagnostic, paired stats
vs R0, the pre-specified criteria breakdown and the generated PROMISING /
PARTIALLY PROMISING / NO SATISFACTORY CALIBRATION verdict; and the **Risk
Manager generalization** panel: real-Indian-data risk-regime table (LOW /
MODERATE / HIGH variance, Spearman ρ, monotonicity, R0 == R1 flag), SIMULATED
decision comparison, real-LLM / DecisionOutcome availability, pre-registered
H1–H6, and the VALIDATED / PROMISING BUT NOT VALIDATED / NOT VALIDATED
verdict), Ablation, Paper
Results (4/5 ready — Table
4/5 now show the multi-scenario aggregates; Table 2 shows its missing-data
reason). No hard-coded research metric; every number resolves to a stored row
(`experiment_id`, `scenario_id`, `seed`).

## Tests (final audit)

| Check | Result |
|---|---|
| Backend `pytest` | **218 passed, 1 skipped, 0 failed** (was 209; +9 new `tests/unit/test_multi_scenario_service.py` — scenario determinism/uniqueness/variation, `_summ` vs numpy + t-interval, paired-test not-assessed & Wilcoxon paths, small end-to-end traceability + fairness + no-leakage, same-(scenario,seed) reproducibility). 1 pre-existing test updated (`forecasting_performance` CSV header). |
| Frontend `next build` | ✅ compiled (26 routes) — new `MultiScenarioDetail` view on the Experiments page |
| ESLint | ✅ 0 errors (1 pre-existing unrelated warning) |
| `tsc --noEmit` | ✅ clean |
| Alembic `0001→0006` up / down-to-base / up | ✅ 30 tables (**no new migration** — this task added no schema) |
| `scripts/audit_e2e.py` | ✅ 18/18 SME flow + research pipeline + exports + access control |
| Active model set | unchanged (6 v1) — asserted by every experiment run incl. both multi-scenario runs |
| Legacy single-scenario experiments | byte-identical to the pre-change run (B goal 0.333 / risk-adj 2826.88; all ablation deltas 0.0) |
| Production model behaviour | unchanged — `multi_scenario_service` only reads; no `MLModel` written by the arch/ablation runs |

## Remaining limitations

1. **Digital Twin evaluation is empty** — needs real `DecisionOutcome`
   records (target: 5–10). Table 2 / Figure 3 are `NOT READY` by design, not
   fabricated.
2. **The multi-agent layer does not add measurable value on this scenario
   suite — it subtracts it.** Across 12 scenarios × 5 seeds, Full DecisionGPT
   scores significantly *lower* goal achievement than the leaner Prediction +
   Digital Twin architecture (`p < 0.0001`, loses 45 / 60). The value is in
   the Digital Twin (0.00 → 0.49). This is a measured, reproducible **mixed /
   negative** result — reported, not hidden.
3. **The scenarios are synthetic and designed, not sampled** — the 95 % CIs
   describe variability *within this suite*, not a population of Indian SMEs.
4. **`goal_achievement` for S04 / S07** uses a revenue proxy (their KPIs —
   `inventory_risk`, `marketing_roi` — are not directly simulated).
5. **Indian real forecasting dataset is tiny** (~500 orders, 1 year) with
   unverified provenance — a point estimate, not evidence of generalisation.
6. **AGMARKNET is `DATA_PENDING`**; **customer benchmark is synthetic**.
7. Forecasting / customer / causal experiments still run at a single seed →
   no CIs there.

## Recommended next step

1. **The agent-layer regression from Experiment 5 has been diagnosed *and* one
   confound has been corrected.** The pre-correction diagnostic
   (`docs/MULTI_AGENT_DIAGNOSTIC_REPORT.md`, `multi_agent_diagnostic` id
   `c58c4537`, 60 traceable pairs) found Full DecisionGPT overriding the
   Digital-Twin-best strategy on **100 %** of pairs (0 improved, 45 degraded),
   with `CANDIDATE_SET_MISMATCH` 50 % as the top mechanism — the revenue/sales
   templates omitted a supported price-increase lever, so architectures B and D
   were **not comparing the same legitimate strategy space**. That generator
   omission was corrected (capability-gated `Price +5%` / `Price +10%` for
   revenue/sales goals; Risk Manager untouched) and the **identical** 12 × 5
   experiment repeated — `docs/CANDIDATE_SPACE_CORRECTION_REPORT.md`
   (`POST_CORRECTION …`, diagnostic id `f24abc1b`). Result: candidate coverage
   0.333 → **0.833** (missing-supported 0.500 → **0.000**), but every
   architecture / ablation / pairwise aggregate is **byte-identical** — D still
   0.084, D < B `p < 0.0001`, override rate 1.00 (0 improved / 45 degraded).
   The 30 `CANDIDATE_SET_MISMATCH` pairs became `RISK_OVERRULE` pairs
   (`RISK_OVERRULE` 25 % → 75 %). **The Full-vs-Digital-Twin gap is not a
   candidate-space artefact; it persists after alignment**, and the remaining
   mechanism is Risk-Manager conservatism on price moves (diagnosed, not yet
   corrected).
2. **The risk-penalty term has now been isolated as the proximate mechanism**
   — `docs/RISK_MANAGER_DIAGNOSTIC_REPORT.md` (`risk_manager_diagnostic` id
   `ba56e42b`, 60 pairs). A controlled sensitivity variant **D1** (Full
   DecisionGPT with the Risk Manager still running but its penalty given zero
   weight in the ranking — a labelled variant, **not** the architecture) lifts
   mean goal achievement **0.084 → 0.583** (paired Wilcoxon p < 0.0001,
   r = 0.89, D1 wins 35/60, 0 losses), slightly exceeding the Digital Twin's
   0.486. Removing only the risk penalty changes the selection in **75 %** of
   pairs (35 improved / 0 degraded / 10 neutral). The optimizer formula
   `final_score = (BA+FA)/2 − (1−RM)` was verified on all 390 strategy rows.
   **Caveats:** there were **0** `RISK_SCORE_MISMATCH` cases — the RM is
   faithfully transmitting the Digital Twin's own extrapolation-risk score
   (0.68 for `Price +5%`, 0.98 for `Price +10%`, driven by the synthetic
   businesses' near-constant price history); and D1's mean confidence collapses
   0.139 → 0.018 and its risk-adjusted score stays negative.
3. **The principled calibration study is complete** —
   `docs/RISK_MANAGER_CALIBRATION_REPORT.md` (`risk_manager_calibration` id
   `b8516eef`, 7 variants × 60 pairs). The zero-variance diagnostic confirms
   R0's `_risk_from_extrapolation` **is** miscalibrated (a constant / low-variance
   price history scores every move — including a price cut — at risk 1.0, and
   `+5 %` cannot be ranked below `+10 %`). A robust historical scale
   (`extrapolation_robust_v1`, normaliser `max(hi−lo, 1.4826·MAD, 0.15·|median|)`)
   removes the pathology while preserving risk ordering (Spearman ρ 0.969,
   0 monotonicity violations). **Verdict: PROMISING** — `R3` (robust scale +
   bounded optimizer risk-penalty weight λ = 0.25) lifts mean goal achievement
   **0.084 → 0.168** (paired Wilcoxon p = 0.025, 5 wins / 0 losses) **and**
   turns mean risk-adjusted score −2 614.8 → **+40.5**, keeping confidence
   0.109 (vs D1's 0.018) — passing all seven pre-specified criteria. It closes
   only ~21 % of the Full-vs-Digital-Twin gap; the rest is the near-flat
   template-mode agent growth scores. **No variant promoted** — production stays
   R0 / D0.
4. **R3 was then probed against real Indian data (not validated)** —
   `docs/RISK_MANAGER_GENERALIZATION_REPORT.md` (`risk_manager_real_data_validation`
   id `70617412`, Benroshan `INDIA_REAL_BUSINESS`, provenance unverified).
   Across **23 real price sub-series / 184 test rows** (3 LOW / 11 MODERATE /
   9 HIGH variance regimes), **R0 and R1 produce byte-identical risk scores** —
   the zero/low-variance denominator-collapse pathology R3 fixes **does not
   occur** on real Indian implied-price data (a real series still spans a wide
   `min…max`, so `hi−lo` never collapses). Risk ordering (Spearman ρ 0.989),
   monotonicity (0 violations) and extreme-extrapolation penalisation (82 % of
   out-of-range probes ≥ 0.15) are all preserved; in the SIMULATED decision
   comparison every variant makes the identical choice (risk penalty already
   ≈ 0). **Real-LLM validation is BLOCKED** (no provider configured);
   `DecisionOutcome` records = 0 → Table 2 stays NOT READY. **Verdict:
   PROMISING BUT NOT VALIDATED** — nothing regressed, but R3's benefit is
   unconfirmed outside the synthetic regime. **Recommendation: hold** — do not
   promote, do not retune; revisit only with a dataset where R0's pathology
   actually bites, a real-LLM run, and ≥ 5 real decision outcomes.
5. Collect **5–10 real SME `DecisionOutcome` records** so Experiment 3 /
   Table 2 / Figure 3 become real. **The capture workflow is now in place** —
   `docs/REAL_INDIAN_SME_OUTCOME_VALIDATION.md`: an anonymised aggregate
   template (`docs/templates/real_indian_sme_outcome_template.{csv,json}`),
   validation + PII rejection + horizon-consistency checks
   (`app/services/real_sme_outcome_service.py`), a script-only importer
   (`scripts/import_real_sme_outcomes.py`), provenance columns (migration 0007,
   additive), and a separated **Real Indian SME Outcomes** panel on the Digital
   Twin Evaluation page. **No real records exist yet** →
   `REAL SME OUTCOME COLLECTION = PENDING`, **Table 2 = NOT READY**. No
   synthetic `DecisionOutcome` was fabricated. See
   `docs/REAL_INDIAN_SME_OUTCOME_VALIDATION_REPORT.md`. **Operational
   preparation is now complete** (`docs/REAL_SME_COLLECTION_READINESS_REPORT.md`):
   an SME-facing collection guide, consent/provenance + checklist templates, a
   full data dictionary, a paper methodology outline, duplicate-detection on
   import, and no-leakage tests. **Next action is human data collection, not
   coding** — recruit genuine Indian SMEs with actual outcomes for supported
   (price / marketing / inventory) decisions. `REAL SME COLLECTION WORKFLOW =
   READY`, outcomes = 0, Table 2 = NOT READY, real-LLM = NOT TESTED. The
   **recruitment & collection package** is now assembled:
   `docs/REAL_INDIAN_SME_RECRUITMENT_GUIDE.md` (research-team guide),
   `docs/REAL_INDIAN_SME_DATA_QUALITY_PROTOCOL.md` (VALID / REQUIRES_REVIEW /
   REJECTED scorecard), `docs/REAL_WORLD_VALIDATION_ROADMAP.md` (8 sequential
   phases; Phase 2 = current), and `docs/templates/REAL_INDIAN_SME_{PARTICIPANT_CHECKLIST,
   RESEARCHER_FORM,PARTICIPANT_INSTRUCTIONS,COLLECTION_SCHEDULE}`. The dashboard
   real-SME panel now also surfaces Real-LLM / R3 / Production status derived
   live from settings + the production `PipelineOptions` defaults.
6. Populate **AGMARKNET** with a free `DATA_GOV_IN_API_KEY` and add it as a
   second `INDIA_*` forecasting row; add repeated seeds to the forecasting /
   customer experiments for CIs.
