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

## Experiment 5 — Decision architecture comparison

`experiment_service.run_experiment("decision_architecture")` — same synthetic
scenario, same seed (42), same goal target (+15 %) for every architecture.

| Architecture | Selected strategy | Expected benefit | Risk-adjusted score | Goal achievement | Latency (s) |
|---|---|---:|---:|---:|---:|
| A · Prediction only | *(none — no strategy mechanism)* | 0.00 | 0.00 | 0.00 | 0.146 |
| B · Prediction + Digital Twin | Price +5 % | 5 653.75 | 2 826.88 | **0.333** | 1.236 |
| C · + Single Agent | Marketing +10 % | 0.00 | 0.00 | 0.00 | 1.467 |
| D · Full DecisionGPT | Marketing +10 % | 0.00 | 0.00 | 0.00 | 1.624 |

**Honest negative result:** on this *single* synthetic scenario the agent
layer steers C and D toward "Marketing +10 %", which the Digital Twin scores
at zero benefit, so the leaner architecture **B outperforms the full system**.
This is one scenario with one seed — **descriptive only; not evidence that a
leaner architecture is generally better.** A multi-scenario suite is required
for a meaningful comparison (see *Remaining limitations*).

`multi_agent` sub-comparison: single-agent (C) 0.00 vs multi-agent (D) 0.00
goal achievement — no measurable difference on this scenario.

---

## Experiment 6 — Ablation study (A–F)

`experiment_service.run_experiment("ablation")` — same scenario/seed.

| Config | Component removed | Goal achievement | Risk-adj. score | Confidence | Δ goal achievement vs Full |
|---|---|---:|---:|---:|---:|
| A | *(Full DecisionGPT)* | 0.00 | 0.00 | 0.150 | — |
| B | Digital Twin | 0.00 | 0.00 | — | **0.0** (no strategy can be recommended without it) |
| C | Causal Graph | 0.00 | 0.00 | 0.272 | **0.0** |
| D | Multi-Agent | 0.00 | 0.00 | 0.150 | **0.0** |
| E | Explainability | 0.00 | 0.00 | 0.150 | **0.0** |
| F | Memory | 0.00 | 0.00 | 0.150 | **0.0** |

**Every delta is 0.0** and is reported as such — not hidden. Explanation:

- Full DecisionGPT already lands on a zero-benefit strategy on this scenario,
  so removing a component cannot lower an already-zero goal achievement.
- **Explainability** is generated *after* strategy selection, so by design it
  has no scoring effect — a **structural** zero delta, not a measurement
  artefact.
- **Memory** has no effect because there are **no recorded outcomes** on a
  fresh synthetic scenario — nothing to remember.
- Removing the **Digital Twin** does change *behaviour* (no strategy is
  recommendable at all) even though the goal-achievement delta is 0.

Confidence *does* move: removing the Causal Graph raises confidence 0.150 →
0.272 (the causal-evidence penalty is dropped). This is a real, if narrow,
component effect. **A single scenario cannot support an ablation conclusion —
descriptive only.**

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
| Architecture / ablation | 1 scenario, 1 seed | Descriptive; **insufficient sample size for statistical inference**. Deltas reported exactly, including zeros. |
| Causal (synthetic) | 1 graph, 250 steps, seed 42 | Method-validation point estimate; documented Granger limitations. |

No significance test was performed, and **no significance is claimed**.

---

## Paper tables

| Table | Status | Backing |
|---|---|---|
| **Table 1 — Predictive Model Performance** | **READY** | `forecasting_performance` + `churn_performance` exports; rows carry `Status` + `Data category` so `INDIA_REAL_BUSINESS` and `SYNTHETIC_CONTROLLED` stay separate |
| **Table 2 — Digital Twin Prediction Evaluation** | **NOT READY — requires additional `DecisionOutcome` records** | `PredictionEvaluation` (0 matched) |
| **Table 3 — Causal Graph Evaluation** | **READY** | experiment `causal` (seed 42) — labelled `SYNTHETIC GROUND TRUTH` |
| **Table 4 — Decision Architecture Comparison** | **READY** | experiment `decision_architecture` (seed 42) |
| **Table 5 — Ablation Study** | **READY** | experiment `ablation` (seed 42) |

Every table row traces to an `experiment_id` / `model_version` /
`dataset_version` / `seed` via `experiments/experiment_manifest.json`.

## Paper figures

| Figure | Status | Data source |
|---|---|---|
| 1 · Architecture overview | READY | static (`docs/INDIAN_SME_DATA_ARCHITECTURE.md`) |
| 2 · Forecasting model comparison | READY | Table 1 (real + synthetic blocks) |
| 3 · Digital Twin predicted vs actual | **NOT READY** — no actual outcomes | — |
| 4 · Causal graph recovery metrics | READY | experiment `causal` |
| 5 · Decision architecture comparison | READY | experiment `decision_architecture` |
| 6 · Ablation results | READY (all-zero deltas — reported as-is) | experiment `ablation` |
| 7 · Feedback loop | READY as a schematic; no live data (0 outcomes) | schematic only |

## Research Dashboard

Verified pages: Overview, Dataset Registry (`{platform, external, uploaded}`,
`data_category` on every entry), Training Center, Model Registry, Experiments
(+ reproducibility manifest download), Model Performance, Digital Twin
Evaluation (explicit empty state), Causal Evaluation, Multi-Agent Evaluation,
Ablation, Paper Results (4/5 ready, Table 2 shows its missing-data reason).
No hard-coded research metric; every number resolves to a stored row.

## Tests (final audit)

| Check | Result |
|---|---|
| Backend `pytest` | **209 passed, 1 skipped, 0 failed** (1 test updated: `forecasting_performance` CSV header now `Model,Version,Status,Data category,MAE,RMSE,MAPE,Dataset version`) |
| Frontend `next build` | ✅ compiled (26 routes) |
| ESLint | ✅ 0 errors (1 pre-existing unrelated warning) |
| Alembic `0001→0006` up / down-to-base / up | ✅ 30 tables (no new migration) |
| `scripts/audit_e2e.py` | ✅ 18/18 SME flow + research pipeline + exports + access control |
| Active model set | unchanged (6 v1) — asserted in the run |

## Remaining limitations

1. **Digital Twin evaluation is empty** — needs real `DecisionOutcome`
   records (target: 5–10). Table 2 / Figure 3 are `NOT READY` by design, not
   fabricated.
2. **Architecture & ablation rest on one synthetic scenario** — every delta is
   0.0 and the full system underperforms architecture B on it. This is a
   descriptive negative result; a multi-scenario suite is needed before any
   architecture claim.
3. **Indian real forecasting dataset is tiny** (~500 orders, 1 year, 3
   categories) with unverified provenance — a point estimate, not evidence of
   generalisation.
4. **AGMARKNET is `DATA_PENDING`** — excluded from this run.
5. **Customer benchmark is synthetic** — a demonstration, not validation.
6. No repeated-seed runs → no confidence intervals on any metric.

## Recommended next step

Collect **5–10 real SME `DecisionOutcome` records** (or a controlled user
study) so Experiment 3 / Table 2 / Figure 3 become real, and expand the
decision-architecture / ablation experiments to a **multi-scenario suite**
(≥ 10 scenarios, ≥ 5 seeds) so Tables 4–5 can support a defensible claim.
Then, with `DATA_GOV_IN_API_KEY`, populate AGMARKNET and add it as a second
`INDIA_*` forecasting row.
