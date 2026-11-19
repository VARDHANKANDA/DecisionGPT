# EXPERIMENT_PROTOCOL — decisiongpt_architecture_v1 (v1.0)

Created 2026-10-22 (UTC 17:2x), **after** the locked evaluations it re-uses had been run and inspected in earlier sessions of this project. This is **not** a preregistration of those evaluations (each has its own earlier, hash-frozen preregistration: `docs/R1_PREREGISTRATION.md`, `docs/UPGRADED_EVALUATION_PREREGISTRATION.md`). It is an internal, timestamped protocol for the **new** work of this directory; every analysis below is labelled *new measurement*, *replication of a stored locked analysis*, or *post-hoc secondary analysis*. It is hash-frozen (`PROTOCOL.sha256`) before the new cost measurement is run. Nothing here is a public preregistration.

## 0. Scope and honesty statement

* The "multi-agent layer" of DecisionGPT is **three deterministic, rule-based agent functions plus a rule-based optimizer** (`backend/app/agents/*.py`; no language model is called inside the decision path: `agents/base.py`, `docs/MULTI_AGENT_SPECIFICATION.md`, `AGENTS.md`). The question tested here is therefore about **deterministic multi-agent orchestration around a simulator**, not about LLM-based agent societies. No real LLM evaluation exists in the repository (blocked: no configured evaluation provider); none is run here.
* All decision-quality evidence is **synthetic-benchmark** evidence scored by an exogenous ground-truth module (`backend/app/evaluation/ground_truth.py`); it is not evidence about real SMEs, profit, causal effects or deployed performance.
* Architecture variants compared (existing, `decision_architecture_service.py`): **A** prediction only (recommends nothing), **B** prediction + Decision Simulation (digital twin) with greedy selection, **C** B + a single rule-based agent, **D** the production multi-agent pipeline (3 agents, 2 rounds, optimizer, risk gate). External references: oracle, naive, greedy, classical optimizer (`ground_truth.py`).

## 1. Research questions and how each is addressed

| RQ | Evidence | Status of the evidence |
|---|---|---|
| RQ1 predictive performance | stored benchmark and comparison runs (`experiments/ml_benchmark_v1/*`, `experiments/model_comparison_v1/*`), registered-model test metrics (recorded at training or re-scored from the stored artifact, `backend/app/services/model_reevaluation_service.py`) | stored results, read-only; one new, verified re-scoring of registry models |
| RQ2 architecture effectiveness | R1 locked evaluation (408 scenarios × 10 seeds, `experiments/r1/results.json`), upgraded controlled v1 (80 scenarios × 10 seeds, `experiments/upgraded_controlled_v1/results.json`), historical multi-scenario run (12 × 5) | locked, pre-registered elsewhere; **re-analysed here by independent code** |
| RQ3 component contribution | contrasts B−A, C−B, D−C of the same locked runs; stored mechanism diagnostic (risk-penalty-neutralised variant, `experiments/r1/mechanism_results.json`); stored historical six-way ablation | locked/stored; new paired re-computation |
| RQ4 quality–cost | **new** end-to-end latency and invocation-count measurement (E-COST, §4) combined with stored regret | new measurement + post-hoc combination |

## 2. Inputs (read-only; never modified)

`experiments/experiment_manifest.json` (sha256 `94aa419c703b1babb465975463b26e55255755a7687ecbecadb6db4c4c15cbff`), `experiments/r1/{results.json,scenario_manifest.json,config.json,statistical_results.json,mechanism_results.json,robustness_results.json}`, `experiments/upgraded_controlled_v1/*`, `experiments/ml_benchmark_v1/*`, `experiments/model_comparison_v1/*`. Their sha256 are recorded in `results/input_hashes.json` before and after every analysis run; any difference stops the pipeline.

## 3. Analysis A — decision quality (independent re-computation of locked results; post-hoc secondary analyses labelled)

* **Outcome:** exogenous normalised regret of the selected action (0 = oracle action, 1 = worst reference action), as stored (`primary_regret` per instance). Lower is better. The scenario is the unit of analysis: within each scenario the regret of each condition is averaged over its 10 seeds.
* **Primary architecture contrast (replication of the locked primary):** `D_vs_B` = regret(D) − regret(B), paired by scenario. Other contrasts: `B_vs_A`, `C_vs_B`, `D_vs_C`, `D_vs_A`, and D versus the greedy, classical-optimizer and naive references. Holm adjustment over the first four contrasts (as in R1); the others are descriptive.
* **Inference:** paired scenario-level mean difference; 95 % percentile cluster-bootstrap interval (resample scenarios, B = 10,000, seed 20261023); Wilcoxon signed-rank test on non-zero paired differences; matched-pairs rank-biserial effect size; win/tie/loss counts. Seeds within a scenario are **not** treated as independent observations.
* **Heterogeneity (post-hoc, exploratory):** the same contrast per scenario family with its cluster-bootstrap interval; no multiplicity control; families are the locked R1 families.
* **Second locked study:** the identical code is applied to `upgraded_controlled_v1` (4 other families); results are reported side by side, never pooled.
* **Exclusions:** none pre-specified beyond the locked studies' own (`exclude_from_primary`, none triggered).

## 4. Analysis B — E-COST: end-to-end cost of each workflow (NEW measurement)

Stored `latency_seconds` of conditions A–C exclude the shared Decision-Simulation computation (it is computed once and shared), whereas D includes its own full pipeline; stored latencies are therefore **not comparable across conditions** and are used only descriptively. E-COST measures comparable end-to-end quantities.

* **Instances:** every one of the 408 locked R1 scenarios with the **first** locked seed (`seeds[0]`), plus 3 repeats of a fixed subset (4 scenarios per family, 48 scenarios) to separate run-to-run timing noise from between-scenario variation. Same code path as the R1 locked run (`r1.harness` semantics: `r1_dt` installed, same scenarios, same seed), in a scratch in-memory/SQLite database; no production state is touched.
* **Quantities per instance (wall-clock, `time.perf_counter`):** shared Decision-Simulation time (`_sim_all`); B pick; C pick; D pipeline (`decision_service.analyze_goal`) total; end-to-end **B = shared simulation + B pick**, **C = shared simulation + C pick**, **D = D pipeline**; A recommends nothing (no decision cost; excluded from cost ratios).
* **Counts per instance:** Decision-Simulation calls (inside the shared stage; inside D); per-agent `evaluate` calls (Business Analyst, Financial Advisor, Risk Manager, single agent) attributed to the condition they serve (D's own, C's pick, and the harness diagnostics, which are reported separately and not charged to any condition); registered-model `predict` calls where observable; **language-model calls (expected 0; verified by instrumentation of the AI facade)**.
* **Money:** because no language model is called, API token usage and API cost are **0 by construction and measured as 0**; the cost reported is compute time (and CPU-seconds is not measured). No token-based estimate is made; no hypothetical LLM-agent cost is presented as a result.
* **Statistics:** per-instance D/B, D/C and C/B latency ratios and differences; medians, interquartile ranges and 95th percentiles; 95 % cluster-bootstrap intervals over scenarios for the median log-ratio; run-to-run variation from the repeated subset (coefficient of variation per instance).
* **Determinism check:** the regret values and selected actions of the new run must equal the stored locked values for the same (scenario, seed) (the evaluation is deterministic given the seed); any mismatch is reported, not hidden.

## 5. Analysis C — quality–cost combination (post-hoc, labelled)

* Per condition: mean scenario-level regret (stored locked run, same scenarios) against median end-to-end latency (E-COST); the Pareto frontier is computed from these pairs without a pre-selected "winning" architecture (no single decision criterion is claimed; both axes are shown).
* **Near-optimal decision** (defined here before E-COST is analysed): normalised regret ≤ 0.10 (sensitivity: 0.05 and 0.20); **cost per near-optimal decision** = mean end-to-end latency ÷ share of near-optimal decisions (compute seconds; not money).
* **Heterogeneity by family:** which families (if any) show D better than B; reported descriptively.

## 6. Analysis D — RQ1 predictive evaluation (stored results; read-only)

* **Forecasting metrics:** MAE, RMSE, WAPE (sum |error| ÷ sum |actual|; withheld when the actual total is 0), relative bias, MAE change versus the best simple baseline of the same run, RMSSE where stored. MAPE is not used for intermittent data (zero denominators).
* **Classification metrics:** precision, recall, F1, ROC-AUC, PR-AUC, Brier and ECE where stored; labels are proxy/synthetic where stated (customer inactivity for Online Retail II is a proxy label, not observed churn; the platform churn labels are synthetic) and the paper says what each score measures.
* **Registered models:** test-block figures either recorded at training or produced by the verified re-scoring (accepted only if it reproduces the recorded MAE, RMSE and MAPE). Models that fail verification or lack their artifact are reported as such.
* No model is retrained; no ensemble is created. Existing stored ensembles are reported as stored.

## 7. Reproducibility procedure

Fixed seeds, versions and commands in `README.md`; scripts under `analysis/`; outputs under `results/`, `tables/`, `figures/`; input hashes before/after; the cost measurement writes append-only JSONL (resumable). The paper's tables and figures are generated from these outputs only.

## 8. Known limitations declared in advance

Synthetic benchmark; deterministic agents (not LLM agents); one codebase; timing measured on one machine under variable load (relative comparisons within the same run are more reliable than absolute numbers); the end-to-end definitions above are one reasonable accounting, not the only one; post-hoc analyses were designed after the regret results were known.
