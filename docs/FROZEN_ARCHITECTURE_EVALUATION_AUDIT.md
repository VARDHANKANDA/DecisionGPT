# Frozen Architecture — Evaluation Audit (Phase 1)

**Status:** audit only. No code changed, no experiment run, no artifact modified.
**Freeze verified at audit time:** `experiments/experiment_manifest.json` SHA-256
`94aa419c703b1babb465975463b26e55255755a7687ecbecadb6db4c4c15cbff`;
`git diff -- experiments/ backend/` empty; working tree clean apart from the
untracked `docs/ieee_paper/` from the prior task.

**Purpose.** Make the *existing* DecisionGPT evaluation as scientifically rigorous
and publication-strong as possible using **controlled synthetic experimentation
only** — no real SME data, no architecture change, no LLM, no promotion of R3, no
change to R0/D0, no modification of frozen experiments.

---

## 0. Files inspected

| Area | File | What it is |
|---|---|---|
| Frozen manifest | `experiments/experiment_manifest.json` | Byte-frozen 16-experiment reproducibility manifest (committed) |
| Frozen snapshot | `experiments/paper_results_snapshot.json` | Byte-frozen paper tables (committed) |
| Loose results | `experiments/results/*.json` | Training-run outputs (forecasting/churn); referenced, not the decision-architecture evidence |
| Multi-scenario harness | `backend/app/services/multi_scenario_service.py` | The 12-scenario × 5-seed suite: `SCENARIOS` (12 hand-coded `ScenarioSpec`), `SEEDS=[42..46]`, `_summ`, `_paired`, `run_multi_scenario_architecture`, `run_multi_scenario_ablation` |
| A/B/C/D conditions | `backend/app/services/decision_architecture_service.py` | `_seed_synthetic_business`, `_run_architecture_a/b/c/d`, `_goal_achievement`, `_kpi_goal_achievement`, `kpi_for_metric`, `_simulate_all_candidates` |
| A–F ablation | `backend/app/services/ablation_service.py` | `run_ablation_study`; toggles components via `decision_service.PipelineOptions` |
| Production pipeline | `backend/app/services/decision_service.py` | `analyze_goal`, `PipelineOptions`, `CANDIDATE_GRID` |
| Optimizer | `backend/app/agents/strategy_optimizer.py` | `compute_strategy_score` = `goal_benefit − λ·(1−RM)`, `FORMULA_VERSION="v2"`, `resolve` / `resolve_single` |
| Digital Twin | `backend/app/analytics/digital_twin_service.py` | `simulate_strategy`, `_risk_from_extrapolation` (R0 `extrapolation_range_v1`), `_calibrated_risk_from_extrapolation` (R1 robust scale), `_risk_band` |
| Agents | `backend/app/agents/{base,business_analyst,financial_advisor,risk_manager,single_agent}.py` | Rule-based scorers; no LLM |
| Experiment dispatch | `backend/app/services/experiment_service.py` | `_dispatch` (experiment-type table), `run_experiment`, `build_manifest` (recomputes a *live* manifest from the DB — the committed file is a separate frozen snapshot) |
| Diagnostics / calibration | `backend/app/services/{multi_agent_diagnostic,risk_manager_diagnostic,risk_calibration,risk_manager_generalization}_service.py` | Frozen diagnostic experiments |
| Stats spec | `docs/STATISTICAL_ANALYSIS.md`, `docs/MULTI_SCENARIO_EXPERIMENT_PROTOCOL.md` | The current `_summ`/`_paired` methodology |
| Tests | `tests/unit/test_multi_scenario_service.py`, `test_ablation_service.py`, `test_decision_architecture_service.py`, `test_strategy_optimizer.py`, `test_risk_*` | Determinism, `_summ` vs numpy, not-assessed paths, scenario diversity |
| Blueprint / prior audits | `docs/PAPER_EVIDENCE_AUDIT_AND_BLUEPRINT.md`, `docs/PAPER_DRAFT.md`, `docs/PAPER_FINAL_READINESS.md` | The frozen numbers and their provenance |

---

## 1. What is frozen

These are the scientific record. They must remain **byte-for-byte unchanged**.

### 1.1 Frozen artifacts (committed files)
- `experiments/experiment_manifest.json` (SHA-256 `94aa419c…`) — the 16 experiment
  records, their IDs, seeds, dataset versions, model versions, configurations.
- `experiments/paper_results_snapshot.json` — the 5 paper tables (4 ready, Table 2
  NOT READY).
- `experiments/results/*.json` — the loose training-run outputs already committed.
- Every number in `docs/PAPER_DRAFT.md` / `docs/PAPER_REFERENCES.md` /
  `docs/figures/figure_data.json` and the rendered figures.

### 1.2 Frozen production decision path (R0 / D0)
`decision_service.analyze_goal(db, business_id, goal_id)` called with
**`PipelineOptions()` defaults**:
```
use_causal_graph = True   use_multi_agent = True   use_memory = True
use_explainability = True  risk_penalty_in_ranking = True
risk_model = None (== "R0")   risk_penalty_lambda = 1.0   → PipelineOptions().label() == "full"
```
- `strategy_optimizer`: `FORMULA_VERSION = "v2"`,
  `compute_strategy_score = goal_benefit − risk_penalty_weight·(1 − RM)` with
  `risk_penalty_weight = 1.0` in production.
- `digital_twin_service._risk_from_extrapolation` (R0, `extrapolation_range_v1`):
  `overshoot = maxₓ (value−hi)/(hi−lo)  or  (lo−value)/(hi−lo)` over
  `{price, marketing_spend}`, clipped to `[0,1]`; bands `<0.15 low`, `<0.5
  moderate`, else `high`.
- `digital_twin_service.simulate_strategy(...)` KPI projection
  (`expected_revenue / expected_profit / expected_units_sold`).
- `decision_service.CANDIDATE_GRID` (6 fixed candidates) and
  `strategy_generation_service.generate_candidates` for the production path.
- The three rule-based agents and `single_agent`.

### 1.3 Frozen evaluation harness *as used by the 16 runs*
- `multi_scenario_service.SCENARIOS` — the 12 `ScenarioSpec` literals (S01–S12),
  their exact parameter values.
- `multi_scenario_service.SEEDS = [42, 43, 44, 45, 46]`.
- `decision_architecture_service._seed_synthetic_business`, `_goal_achievement`
  (L188), `_kpi_goal_achievement` (L202), `_run_architecture_a/b/c/d`,
  `kpi_for_metric`.
- `ablation_service.run_ablation_study` and its A–F meanings.
- `multi_scenario_service._summ` / `_paired` (Student-t CI + paired Wilcoxon +
  `effect_size_r = |Z|/√N_nonzero`).
- The frozen experiment IDs: `0e1bd8dc` (architecture, POST), `675cf17e`
  (architecture, PRE), `db58455b` / `be392694` (ablation), `f24abc1b` /
  `c58c4537` (multi-agent diagnostic), `ba56e42b` (risk-manager diagnostic),
  `b8516eef` (risk calibration), `70617412` (risk generalization), `36d0d404`
  (causal), `c2b3a2fa` (forecasting), `21e8e800` (churn), `2f7da989`
  (digital-twin evaluation), `7616425f` / `a32933ca` / `1fcca452` (legacy).

### 1.4 Frozen scientific state
- Production = **R0 / D0**. **R3 = PROMISING / NOT PROMOTED.**
- Real SME outcomes = 0. `PredictionEvaluation` = 0. Table 2 = NOT READY.
- Real LLM = BLOCKED (`llm_enabled = False`). `CAUSALLY_VALIDATED = 0`.
- 6 active v1 models / 3 archived v2 models. Alembic head 0007.

---

## 2. What may safely be extended (evaluation-only, no architecture change)

The codebase already contains the sanctioned extension seams. The upgraded
evaluation uses **only** these:

### 2.1 The `PipelineOptions` evaluation knobs (already exist, production ignores them)
`use_causal_graph`, `use_multi_agent`, `use_explainability`, `use_memory`,
`risk_penalty_in_ranking`, `risk_model`, `risk_penalty_lambda`. Production calls
`analyze_goal` with **no options**, so the defaults apply and nothing changes.
Ablation/variant conditions pass non-default `PipelineOptions`. This is exactly
how `ablation_service` and `risk_calibration_service` already work.

### 2.2 The "import the frozen functions, add scenarios + stats" pattern
`multi_scenario_service` already does `from app.services import ablation_service,
decision_architecture_service as da` and *calls the production code unchanged*.
The upgraded evaluation adds a **new, parallel** package that does the same —
never editing `multi_scenario_service`, `decision_architecture_service`,
`ablation_service`, `decision_service`, `digital_twin_service`, or the agents.

### 2.3 Safe to create (all new)
- A **new package** `backend/app/evaluation/` (or `research/upgraded_eval/`) that
  imports and calls the frozen production + harness functions read-only.
- A **new parameterized scenario generator** emitting specs consumable by
  `_seed_synthetic_business` (or a new `_seed_*` that builds *richer* synthetic
  histories — e.g. non-constant price paths — while still only creating and
  destroying ephemeral synthetic businesses).
- A **new exogenous ground-truth objective model** + oracle + naive / greedy /
  classical-optimizer baselines, as pure evaluation code that never calls
  `digital_twin_service` to *grade*.
- A **new statistics module** (`_summ2` / `_paired2`, cluster bootstrap,
  scenario-level tests, Holm correction, simulation-based power). The frozen
  `_summ` / `_paired` are not touched.
- A **new perturbation / robustness suite**.
- A **new mechanism-analysis module** (scenario-property factor extraction +
  interaction analysis).
- A **new versioned results tree** `experiments/upgraded_controlled_v1/` with its
  own manifest, config, scenario manifest, seeds, results, statistical outputs,
  and checksums.
- **New docs**: `docs/UPGRADED_EVALUATION_PREREGISTRATION.md`,
  `docs/UPGRADED_EVALUATION_REPORT.md`.
- **New tests** for every new module.
- A **new seed list (≥ 10)** used **only** by the new runs.
- Optionally a **separate scratch DB** (or standalone scripts that write files
  only) so no `ExperimentRun` row lands in the frozen story's database.

---

## 3. What must never be changed

- Anything in §1 (all four sub-sections).
- Do **not** edit `multi_scenario_service.py`, `decision_architecture_service.py`,
  `ablation_service.py`, `decision_service.py`, `digital_twin_service.py`,
  `strategy_optimizer.py`, or `backend/app/agents/*`.
- Do **not** change `PipelineOptions` defaults or `FORMULA_VERSION`.
- Do **not** add a decision lever the production
  `CANDIDATE_GRID` / `strategy_generation_service` cannot already produce
  (that would be an architecture change). New scenarios must stay inside the
  existing feasible-action vocabulary (`marketing_change`, `price_change`,
  `inventory_change`).
- Do **not** regenerate `experiments/experiment_manifest.json` or
  `experiments/paper_results_snapshot.json`.
- Do **not** route new runs through `experiment_service.run_experiment` into the
  frozen story's database (use a separate DB or standalone scripts).
- Do **not** promote R3 / R1 / R2-λ / D1 or any non-default `PipelineOptions`
  into the production default.
- Do **not** enable a real LLM.
- Do **not** create, require, or assume real SME / customer / human / prospective
  outcome data. Do **not** relabel synthetic data as real-world evidence.
- Do **not** present the upgraded study as changing any frozen result — it is a
  **separate, additive** controlled evaluation.

---

## 4. Current evaluation weaknesses (grounded in the code)

| # | Weakness | Evidence in code |
|---|---|---|
| **EW1** | **Circular / self-graded primary metric.** `goal_achievement` = the Digital Twin's *own* projected KPI (`expected_revenue/profit/units`) for the selected strategy, normalised by target. B, C, D all pick over `digital_twin_service.simulate_strategy` outputs and are then graded by the same simulator's projection. There is **no environment model independent of the Digital Twin**. | `decision_architecture_service._goal_achievement` L188–192, `_kpi_goal_achievement` L202–212; `_run_architecture_b/c/d` all use `simulate_strategy` output; `simulate_strategy(risk_model=)` changes *only* `risk_score`, never the KPI projection (`digital_twin_service.py` L309–312) |
| **EW2** | **Agent layer cannot vary meaningfully in these scenarios.** BA/FA scores are near-constant across candidates on the current generators, so `compute_strategy_score = goal_benefit − (1−RM)` reduces to selection ≈ `argmax RM` = lowest-extrapolation-risk. The negative D<B result is close to analytically forced. | `strategy_optimizer.compute_strategy_score` L34–43; `risk_manager_diagnostic` (frozen `ba56e42b`) reports RM decisive on 75% of pairs, 35 improved / 0 degraded when the penalty is removed |
| **EW3** | **Generator ↔ mechanism confound.** Synthetic price history takes exactly two values (`selling_price`, `promo_price`), so `_risk_from_extrapolation`'s normaliser `span = hi − lo` = the promo-discount depth. Any modest price *increase* overshoots that span and saturates `risk_score` → 1.0. The diagnosed mechanism (risk penalty) is driven by the authors' own generator design. | `_seed_synthetic_business` L131–133 (`price = promo_price if promo else selling_price`); `_risk_from_extrapolation` L186–194 |
| **EW4** | **12 hand-coded scenarios; no parameterised families, no sampling, no held-out set.** The 12 `ScenarioSpec` literals are the same ones used while building the system. No train / dev / locked-test separation. | `multi_scenario_service.SCENARIOS` L69–97; no generator; `test_scenarios_are_meaningfully_different` enforces diversity but not coverage or independence |
| **EW5** | **5 seeds vary only low-variance `rng.randint` noise; effective independent units ≈ 12.** The stats treat the 60 (scenario, seed) observations as the sample size. | `_seed_synthetic_business` `rng = random.Random(f"{scenario_id}:{seed}")`, `quantity = rng.randint(demand_low, demand_high)+…`; `_summ`/`_paired` use `n = 60` |
| **EW6** | **No external baselines and no oracle.** Condition A returns a hard-coded `goal_achievement = 0.0` (a floor, not a policy). B is "greedy on the Digital Twin." There is no naive baseline, no classical optimiser, no oracle upper bound. | `_run_architecture_a` L227–236 (`ArchitectureResult("A", …, 0.0, 0.0, 0.0, …)`); `_run_architecture_b` L244 (`max(candidates, key=expected_revenue)`) |
| **EW7** | **Statistical methodology.** Student-t CI on a `[0,1]` endpoint-heavy metric; `_paired` reports a p-derived `effect_size_r = |Z|/√N_nonzero` (not an independent estimate); no scenario-level (cluster) test as the primary; no scenario bootstrap; **no multiple-comparison correction** across the D–A / D–B / 5 ablation / 6 R-variant / H1–H6 family; **no power / sample-size justification**. | `_summ` L103–119, `_paired` L122–182 (esp. L163–164 `z = norm.ppf(p/2); r = |z|/√nz`) |
| **EW8** | **B/C vs D candidate-set asymmetry.** B/C enumerate `CANDIDATE_GRID` (6); D calls `strategy_generation_service` — different feasible action spaces. The "candidate-space confound" was found and corrected once (`675cf17e` == `0e1bd8dc`), but the harness has no invariant forcing all conditions to choose over an *identical* enumerated feasible set. | `_simulate_all_candidates` L215–224 vs `_run_architecture_d` → `decision_service.analyze_goal` |
| **EW9** | **No robustness / perturbation suite.** No input-noise, forecast-error, missing-value, uncertainty-inflation, constraint-stress, distribution-shift, contradictory-signal, extreme-but-feasible, or adversarial testing. | absent from `multi_scenario_service` and `ablation_service` |
| **EW10** | **Mechanism analysis is post-hoc correlational only.** `failure_mode_analysis` lists "associated factors" for low-`goal_achievement` runs; there is no factorial characterisation of scenario properties (uncertainty, constraint tightness, objective conflict, prediction error, risk, action-space size, agent disagreement, simulation sensitivity) against the B−A / C−B / D−B effects. | `run_multi_scenario_architecture` L258–280 |
| **EW11** | **Ablation of Explainability / Memory is zero by construction.** On a synthetic scenario with no recorded outcomes, there are no memory insights to remove and explainability is post-selection, so their delta is *necessarily* 0.000 — an uninformative ablation cell. | `ablation_service` docstring L16–20; configs E/F |
| **EW12** | **External-validity ceiling (unchanged, and correct to state).** Synthetic-only decision evidence; zero real outcomes; no human study; no real-LLM; one unverified real dataset used only descriptively. This bounds the venue regardless of the fixes below. | frozen state §1.4 |

---

## 5. Proposed evaluation improvements

All additive; all evaluation-only; none touches production. Phase numbers refer to
the task brief.

| ID | Improvement | Phase |
|---|---|---|
| **PI1** | **Parameterised scenario generator.** ≥ 15 scenario families (demand uncertainty, price uncertainty, inventory / cash / capacity constraints, promotion decisions, resource allocation, supplier uncertainty, competing objectives, asymmetric risk, delayed effects, noisy observations, missing observations, conflicting signals, low-data). Each *instance* records: family, seed, parameter vector, constraints, objective function, feasible action space, **true simulated outcome**, uncertainty parameters, noise parameters — machine-readable. ≥ 50 instances initially, framework scaling to 100+. **Realistic (non-constant) price / marketing histories** so EW3 no longer forces the risk term. New module; `SCENARIOS` untouched. | 2 |
| **PI2** | **Family-level hold-out.** 60 % development / 20 % validation / 20 % **locked test**, split **by family** and by a disjoint seed block, so test instances are structurally unseen. Locked test is checksum-sealed before any tuning and named "development / validation / locked test scenario set" (not "training data"). Primary conclusion uses the locked test only. | 3 |
| **PI3** | **Exogenous objective metric = PRIMARY.** For every instance, an independently implemented ground-truth objective `objective(action, params)` — different functional form from `digital_twin_service` (e.g. explicit elasticity / marketing-response / cost equations, not recursive last-value extrapolation) — computed directly from scenario parameters. Oracle = `argmax`/`argmin` over the enumerated feasible action space. **Primary endpoint = normalised regret** `= (obj(oracle) − obj(selected)) / (obj(oracle) − obj(worst_feasible))` (direction-correct), and/or `performance_ratio = obj(selected)/obj(oracle)`. The DecisionGPT internal `goal_achievement` is retained as a clearly-labelled **SECONDARY** metric, never presented as external validation. The DT-projection-vs-ground-truth gap is reported as a first-class result (it *is* the "prediction error" mechanism factor). | 4 |
| **PI4** | **External baselines (evaluation-only).** (1) Naive (do-nothing / status-quo action); (2) Greedy (best single lever by historical response, no simulator); (3) **Oracle upper bound** (best feasible action under the ground-truth objective — labelled a reference, not a deployable competitor); (4) Classical optimiser (enumeration / small LP over the feasible action space against the ground-truth objective) where the scenario admits a well-defined formulation. All four are pure evaluation code; DecisionGPT is unmodified. | 5 |
| **PI5** | **Preserve and re-run the existing A/B/C/D ablation** via `decision_architecture_service` **unchanged** against the new suite. Per instance: A, B, C, D, oracle, greedy, naive, classical-optimiser performance on the exogenous metric. This becomes the primary architectural component analysis. | 6 |
| **PI6** | **Make the agent ablation informative without redesigning agents.** Use the existing agent mechanism unchanged; design families where the agents' available inputs genuinely vary (realistic price / marketing variance, conflicting signals, asymmetric risk) so agent scores are not near-constant. Measure: score distributions, variance, pairwise agreement / disagreement, contribution to the final selection (does the agent layer change the pick vs C / vs greedy?), sensitivity to scenario perturbation. **Report honestly if the agent layer still adds no measurable information.** | 7 |
| **PI7** | **Robustness / perturbation suites (evaluation-only).** Input noise, injected forecast error, missing values, uncertainty inflation, constraint tightening / relaxation, distribution shift, contradictory signals, extreme-but-feasible parameters, adversarial configs. Report degradation curves: baseline → perturbation severity → performance drop, for every condition and baseline. The architecture is **not** modified to be robust. | 8 |
| **PI8** | **≥ 10 independent seeds** for genuinely stochastic elements; every seed recorded; every result reproducible from the new manifest. Deterministic replications are **not** counted as independent evidence. | 9 |
| **PI9** | **New statistical module.** Scenario is the experimental unit: aggregate seeds within scenario, then paired **scenario-level** Wilcoxon + **cluster bootstrap over scenarios** as the primary; report n, N_nonzero, mean / median difference, SD, 95 % CI, exact p, **matched-pairs rank-biserial**, win/tie/loss. Seed-level variability reported separately. **Holm** (pre-registered) correction across the pre-specified contrast family. No selective reporting. Frozen `_summ` / `_paired` untouched. | 10 |
| **PI10** | **Simulation-based power / sample-size analysis** with a **pre-stated** minimum effect of interest, α, target power, scenario count, seed count, clustering structure, primary comparison — documented **before** the locked-test run. | 11 |
| **PI11** | **Mechanism analysis via scenario-property factors.** For each instance extract: uncertainty level, constraint tightness, objective conflict, DT prediction error, risk exposure, action-space size, agent disagreement, simulation sensitivity. Model whether B−A, C−B, D−B depend on these factors ("component X helps under conditions Y, hurts under Z"). Language: "component-level effect under controlled simulation" — no causal claims about real businesses. | 12 |
| **PI12** | **Explicit evidence-boundary section** (unchanged discipline): no real SME / customer / prospective / human / real-LLM / real-world-causal evidence; contribution positioned as *a controlled, reproducible component-level evaluation of a decision-support architecture under parameterised synthetic decision environments.* No SME-effectiveness / ROI / real-customer / real-world-accuracy / deployed-superiority / causal-business-impact claims. | 13 |
| **PI13** | **Versioned experiment family** `experiments/upgraded_controlled_v1/` with its own `manifest.json`, `config.json`, `scenario_manifest.json`, `seeds.json`, `results.json`, `statistical_results.json`, `robustness_results.json`, `checksums.txt`. Document the relationship `FROZEN ORIGINAL STUDY ↔ UPGRADED CONTROLLED EVALUATION`. Frozen files byte-unchanged. | 14 |
| **PI14** | **Machine-readable outputs + pre-registration.** Emit `results.json`, `scenario_manifest.json`, `statistical_results.json`, `robustness_results.json` with checksums. Finalise `docs/UPGRADED_EVALUATION_PREREGISTRATION.md` (hypotheses, endpoints, generation, terminology, sample size, seeds, baselines, tests, correction, exclusions, robustness, stopping rules, interpretation rules) **before** the locked-test evaluation. | 15, 16 |
| **PI15** | **`docs/UPGRADED_EVALUATION_REPORT.md`** — all 17 required sections; **every numerical-results section marked PENDING** until the runs are executed and approved. No fabricated numbers. | 17 |

---

## 6. Weakness → concrete methodological fix

| Weakness | Fix | Mechanism of the fix |
|---|---|---|
| **EW1** circular metric | **PI3** exogenous ground-truth objective + oracle; internal `goal_achievement` demoted to SECONDARY | The primary endpoint is computed by a model the system never calls; the A/B/C/D/baseline ordering is then measured against an external optimum, not the system's own projection |
| **EW2** agents can't vary | **PI6** design families where agent inputs genuinely differ; measure agent score variance / agreement / contribution-to-selection; **PI3** exogenous metric so agent picks are graded externally | If the agents still add nothing when their inputs *do* vary and grading is external, that is a real finding; if they add value under some conditions, **PI11** locates which |
| **EW3** generator↔mechanism confound | **PI1** realistic non-constant price / marketing histories; **PI11** treat DT prediction error and history variance as explicit scenario factors | The extrapolation-risk normaliser (`hi−lo`) is no longer artificially tiny; whether the risk-penalty mechanism still dominates becomes an empirical question conditioned on history variance |
| **EW4** 12 hand-coded scenarios, no hold-out | **PI1** parameterised families (≥ 50 → 100+ instances); **PI2** family-level dev/val/**locked test** | The primary conclusion is drawn on structurally unseen instances the system was never tuned against |
| **EW5** 5 low-variance seeds; effective n ≈ 12 | **PI8** ≥ 10 seeds on genuinely stochastic elements; **PI9** scenario as the unit, cluster bootstrap, seed variance reported separately | Independent evidence is counted at the scenario level; seed noise is characterised, not conflated with sample size |
| **EW6** no external baselines / oracle | **PI4** naive, greedy, oracle upper bound, classical optimiser; **PI5** report all conditions per instance | Every DecisionGPT component is located relative to simple and optimal policies, not only relative to sibling configs |
| **EW7** statistics | **PI9** scenario-level paired tests + cluster bootstrap + rank-biserial + **Holm**; **PI10** pre-stated power analysis | Multiplicity controlled; effect sizes are estimator-based, not p-derived; the sample size is justified before results are seen |
| **EW8** candidate-set asymmetry | **PI4/PI5** harness control: **every condition (A/B/C/D + baselines) selects over the identical enumerated feasible action space** for a given instance, recorded in the scenario manifest | Removes the possibility that a condition wins/loses because it saw a different action set |
| **EW9** no robustness suite | **PI7** perturbation suites + degradation curves for every condition | Stability and failure regions are measured directly instead of assumed |
| **EW10** post-hoc correlational mechanism | **PI11** scenario-property factor extraction + interaction analysis on B−A / C−B / D−B | Moves from "component X changed the score" to "component X helps under Y, hurts under Z" within the controlled design |
| **EW11** E/F ablation zero by construction | Report the structural zero honestly **and** (optional, needs explicit approval) add a variant with *synthetic, clearly-labelled* recorded-outcome history so Memory / Explainability *can* bite — kept out of every real-world table and never called an outcome | Either an honest null or a genuine test; never a fabricated real outcome |
| **EW12** external-validity ceiling | **PI12** explicit boundaries; reposition the contribution | The paper claims exactly what a parameterised synthetic evaluation supports and no more |

---

## 7. Architecture boundary (the line the new code must not cross)

```
        FROZEN — never edited                          NEW — evaluation only
  ┌───────────────────────────────────┐        ┌────────────────────────────────────┐
  │ decision_service.analyze_goal     │◄───────│ evaluation/harness.py              │
  │   (PipelineOptions defaults=R0/D0)│  calls │   builds ephemeral synthetic biz,  │
  │ strategy_optimizer (v2 formula)   │  read- │   runs A/B/C/D via the frozen      │
  │ digital_twin_service.simulate_*   │  only  │   decision_architecture_service,   │
  │ agents/*, single_agent            │        │   runs naive/greedy/OR/oracle,    │
  │ CANDIDATE_GRID, strategy_gen      │        │   scores with ground_truth.py     │
  │ multi_scenario_service.SCENARIOS  │        │ evaluation/scenario_families.py    │
  │ ablation_service (A–F meanings)   │◄───────│ evaluation/ground_truth.py         │
  │ _summ / _paired (frozen stats)    │  uses  │ evaluation/stats.py  (new stats)   │
  │ PipelineOptions knobs ────────────┼────────│ evaluation/perturbations.py        │
  │  (already the sanctioned seam)    │        │ evaluation/mechanism.py            │
  └───────────────────────────────────┘        │ scripts/run_upgraded_eval.py       │
                                               │ experiments/upgraded_controlled_v1/│
                                               └────────────────────────────────────┘
```
The only coupling is **new → frozen, read-only, via public functions and the
existing `PipelineOptions`**. Production (`analyze_goal` with no options) is
byte-unaffected.

---

## 8. Concise implementation plan (for approval — not yet executed)

**Files to CREATE**

| Path | Content |
|---|---|
| `docs/FROZEN_ARCHITECTURE_EVALUATION_AUDIT.md` | *this file* |
| `docs/UPGRADED_EVALUATION_PREREGISTRATION.md` | Phase 16 — finalised before the locked-test run |
| `docs/UPGRADED_EVALUATION_REPORT.md` | Phase 17 — 17 sections, numbers marked PENDING |
| `backend/app/evaluation/__init__.py` | package marker |
| `backend/app/evaluation/scenario_families.py` | `EvalScenario` spec + ≥ 15 parameterised families + generator (≥ 50 → 100+), machine-readable ground truth per instance |
| `backend/app/evaluation/ground_truth.py` | exogenous `objective(action, params)`, oracle, naive, greedy, classical optimiser |
| `backend/app/evaluation/harness.py` | per-instance runner: A/B/C/D via frozen services + baselines; identical enumerated feasible action space per instance; writes machine-readable results |
| `backend/app/evaluation/perturbations.py` | perturbation suites + degradation-curve computation |
| `backend/app/evaluation/stats.py` | scenario-level paired tests, cluster bootstrap, rank-biserial, Holm, simulation-based power |
| `backend/app/evaluation/mechanism.py` | scenario-property factor extraction + interaction analysis |
| `scripts/run_upgraded_eval.py` | CLI: generate → seal locked test → run dev/val → (after prereg) run locked test → emit JSON + checksums; writes to a **separate scratch DB** or files only |
| `experiments/upgraded_controlled_v1/{manifest.json, config.json, scenario_manifest.json, seeds.json, results.json, statistical_results.json, robustness_results.json, checksums.txt}` | populated by the run; committed after approval |
| `tests/unit/test_eval_scenario_families.py`, `test_eval_ground_truth.py`, `test_eval_stats.py`, `test_eval_harness_smoke.py` | determinism, ground-truth vs oracle sanity, stats vs reference, one-instance smoke |

**Files to MODIFY:** none in `backend/app/` production, none in `experiments/`
(frozen), none of `multi_scenario_service` / `decision_architecture_service` /
`ablation_service` / `decision_service` / `digital_twin_service` /
`strategy_optimizer` / `agents/*`. (Optional, post-approval, non-scientific: a
one-line pointer in `docs/RESEARCH_EXPERIMENT_REPORT.md` to the upgraded study;
`.gitignore` entry for a scratch eval DB.)

**Execution order (each step gated on approval):**
1. *(now)* This audit + plan → **STOP, report, wait for approval.**
2. On approval: build `scenario_families.py`, `ground_truth.py`, `stats.py`,
   `harness.py`, `perturbations.py`, `mechanism.py` + unit tests. No runs yet.
3. Generate scenarios; **seal** the locked-test split (checksums); run
   development + validation only; iterate methodology on those.
4. Finalise `docs/UPGRADED_EVALUATION_PREREGISTRATION.md`.
5. Run the **locked-test** evaluation once; emit machine-readable outputs.
6. Fill `docs/UPGRADED_EVALUATION_REPORT.md`; re-verify the frozen manifest
   SHA-256 and `git diff -- experiments/ backend/` (production) are unchanged.

**Confirmations**
- **No real SME data is required** — every scenario is parameterised synthetic;
  the exogenous objective is a synthetic ground-truth model; baselines are pure
  code. Real SME / customer / prospective / human / real-LLM data is neither
  used nor assumed.
- **The production architecture will not change** — new code only imports and
  calls frozen functions read-only and uses the pre-existing `PipelineOptions`
  evaluation knobs; `analyze_goal` with default options (R0/D0) is byte-for-byte
  unaffected; `experiments/experiment_manifest.json` and
  `experiments/paper_results_snapshot.json` are not regenerated.
