# Upgraded Controlled Evaluation — Report

**Status: COMPLETE (synthetic, controlled).** Locked-test evaluation run once on
2026-09-05 per the frozen pre-registration
(`docs/UPGRADED_EVALUATION_PREREGISTRATION.md`, frozen SHA-256
`72c99bcf7a0a99185678625b085a93b527aa699b61f63a4e15eac646c0bfd7dd`).

Every number here is traceable to a machine-readable file under
`experiments/upgraded_controlled_v1/` (`results.json`,
`statistical_results.json`, `analysis_supplement.json`,
`robustness_results.json`, `power_analysis.json`) and its SHA-256 in
`checksums.txt`. No number was hand-entered.

> **This document is kept strictly separate from the frozen original study.**
> The 16 frozen experiments, `experiments/experiment_manifest.json` (SHA-256
> `94aa419c703b1babb465975463b26e55255755a7687ecbecadb6db4c4c15cbff`),
> `experiments/paper_results_snapshot.json`, `experiments/results/*`, the frozen
> 12×5 scenario suite, R0/D0, and R3's "PROMISING / NOT PROMOTED" status are
> **unchanged** (verified: `REPRODUCIBILITY_AUDIT.md`). The two studies are
> **never pooled into one analysis.**

---

## 1. Purpose and scope

A **controlled, reproducible, component-level evaluation** of the *existing*
frozen DecisionGPT decision path, on **parameterised synthetic decision
environments**, scored by an **exogenous** closed-form objective that the
pipeline never sees. It exists to test — more rigorously than the original 12×5
study could — whether the downstream components (decision simulation, agent
coordination, risk handling, optimisation) improve **objective** decision
quality.

**It is not**, and makes no claim to be: a real-world study, an Indian-SME study,
a real-LLM study, a causal-intervention study, a deployment study, or a
human-decision-quality study.

## 2. Relationship to the frozen original study (kept separate)

| | Frozen original study | This upgraded evaluation |
|---|---|---|
| Scenarios | 12 hand-authored (S01–S12) | 340 parameterised instances, 17 families, `generator_version = upgraded_eval_scenarios_v2`, `master_seed = 20260906`, `suite_checksum 2215a1bd…` |
| Replication | 5 fixed seeds (deterministic re-runs) | 10 seeds, each an independent history realisation |
| Hold-out | none | family-level development / validation / **locked-test** split, sealed pre-registration (`locked_test_family_checksum 47f0afd6…`) |
| Primary metric | internal `goal_achievement` (self-graded by the Digital Twin) | **exogenous normalised regret** vs an oracle over the identical feasible set; internal metric kept only as a labelled SECONDARY |
| Baselines | none | naive / greedy / oracle / classical-optimizer (none call DecisionGPT) |
| Statistics | p-derived `effect_size_r`, scenario≈unit implicit | scenario = unit, matched-pairs rank-biserial (estimator), paired cluster bootstrap, Holm across the confirmatory family, pre-registered simulation power |
| Manifest | `experiments/experiment_manifest.json` (unchanged) | `experiments/upgraded_controlled_v1/` (new, versioned) |

Numerical results from the two studies are reported in their own documents and
are **not combined**.

## 3. Research questions and hypotheses (frozen pre-registration §2)

- **H1 (`B_vs_A`).** Prediction + decision simulation differs from prediction
  only, on the exogenous metric.
- **H2 (`C_vs_B`, `D_vs_B`).** The agent layer (single agent; full system) adds
  value beyond decision simulation. **`D_vs_B` is the primary confirmatory
  contrast.**
- **H3 (`D_vs_A`).** The full architecture differs from prediction only.
- **H4 (reference, not confirmatory).** All conditions vs oracle / naive / greedy
  / classical optimizer.
- **H5 (mechanism, exploratory, associational).** The sign/size of each contrast
  depends on scenario factors.

All two-sided. Direction is reported, never assumed.

## 4. Frozen architecture under test (invoked read-only)

Production decision path = `decision_service.analyze_goal` with **default
`PipelineOptions`** — `risk_model = None`, `risk_penalty_lambda = 1.0`, all
`use_* = True`, `.label() == "full"` (**R0/D0**). Optimizer formula `v2`
(`s = (BA + FA)/2 − λ·(1 − RM)`, λ = 1). Extrapolation-risk heuristic R0
(`extrapolation_range_v1`). Architecture fingerprint at locked-run time:
`60ca9c9ed3577b688290d602a5b4d1ab392f173c444d0ee934c86b100fd26e37` (reproduced
in the audit). No production file was modified.

## 5. Conditions

| Cond. | Definition | Selection mechanism |
|---|---|---|
| **A** | Prediction only | recommends no strategy → scored as the **smallest-magnitude feasible candidate** (`ground_truth._noop_action` over the production candidate set; **not** the literal null action — that is the `naive` baseline). A is therefore a *minimal-intervention* reference. |
| **B** | + Decision Simulation | argmax of the Digital Twin's projected objective KPI over the identical feasible set |
| **C** | + single agent | argmax of the single-agent score over the identical feasible set |
| **D** | Full system (R0/D0) | `decision_service.analyze_goal` (business-analyst + financial-advisor + risk-manager + risk-manager gate + optimizer), default options |

**Identical-feasible-action-space invariant:** for every instance the harness
re-derives the production `strategy_generation_service` candidate set and asserts
it equals the scenario's declared `feasible_actions`; A/B/C select strictly over
that set; D's realised pick is checked to lie in it. Held on **all 80** locked
instances (0 invariant failures).

## 6. Baselines (evaluation-only; never call DecisionGPT)

`naive` — literal status quo `()`.
`greedy` — local first-order finite-difference heuristic, snapped to the nearest
feasible single-lever action.
`oracle` — best feasible action under the exogenous objective (**upper-bound
reference, not a competitor**).
`classical_optimizer` — SLSQP continuous relaxation of the exogenous objective +
projection to the nearest feasible action (an OR approach *on the modelled
objective*).

## 7. Exogenous ground-truth objective

`backend/app/evaluation/ground_truth.py` (`exogenous_objective_v1`) — a
closed-form economic model (linear own-price elasticity, marketing response with
a horizon-decay factor, explicit cost / capacity / inventory / cash constraints).
It imports **none** of `digital_twin_service`, `decision_service`,
`decision_architecture_service`, `forecast_service`, `app.agents`
(`tests/unit/test_eval_ground_truth.py`: static-import scan + runs with those
modules poisoned in `sys.modules`). **PRIMARY endpoint = normalised regret**
(0 = oracle, 1 = worst feasible; lower is better). The Digital Twin's own
`goal_achievement` is reported only as `secondary_goal_achievement`, always
labelled, never used for a conclusion.

## 8. Scenario suite and partition (frozen)

340 instances, 20 per family, 17 families. Family-level split from `master_seed`:
**development** 200 (10 families), **validation** 60 (3), **locked test** 80
(4 families: `asymmetric_risk`, `competing_objectives`, `missing_observations`,
`promotion_decision`). Split sealed before the pre-registration was frozen; no
family crosses a partition; no instance id collides with S01–S12.

## 9. Sample size and power (fixed before the locked run)

`power_assumptions.json` → `power_analysis.json`: primary comparison `D_vs_B`,
`min_effect_of_interest = 0.10` (normalised regret), α = 0.05, target power 0.80,
`n_scenarios = 80`, `n_seeds = 10`, assumed `metric_sd_between_scenarios = 0.28`,
`within_scenario_seed_sd = 0.12`. **Estimated power = 0.860.** `n` was sized from
this analysis. Stated limitation: the power model does not model exact ties; the
achieved `n_nonzero` is reported with every contrast.

## 10. Statistical methodology

Unit = **scenario** (10 seeds aggregated to the scenario mean first). Per
contrast: n, mean & median paired difference, SD, wins/ties/losses, `n_nonzero`,
paired **Wilcoxon signed-rank** (exact ≤ 25 non-zero, else normal approx),
matched-pairs **rank-biserial** (Kerby estimator; PRIMARY effect size, not
p-derived), paired **scenario cluster bootstrap** 95 % interval (PRIMARY
interval; 10 000 resamples, seed 12345). **Holm–Bonferroni** across
`{B_vs_A, C_vs_B, D_vs_B, D_vs_A}`. Reference contrasts (`D_vs_oracle`,
`D_vs_naive`, `D_vs_greedy`, `D_vs_classical_optimizer`) are descriptive and
excluded from the correction.

**Contrast convention:** each value = `regret[first] − regret[second]`; a
**negative** value means the first condition has **lower regret (is better)**.

**"Supported" (frozen §14):** a contrast is supported *only if* Holm-adjusted
p < 0.05 **and** the cluster-bootstrap CI excludes 0 **and** |mean shift| > 0.10.

## 11. Primary results — locked test (n = 80 scenarios, 800 instances, 0 errors, 0 exclusions)

### 11.1 Confirmatory family (Holm-corrected)

| Contrast | mean Δ regret | 95 % cluster-bootstrap CI | W/T/L | n_nz | Wilcoxon p (raw) | Holm p | reject @ .05 | rank-biserial | "supported"? |
|---|---:|---|---|---:|---:|---:|:--:|---:|:--:|
| **B_vs_A** | **+0.0751** | [−0.0688, +0.2191] | 36/0/44 | 80 | 0.00487 | **0.01461** | yes | −0.10 | **No** (CI includes 0; direction inconsistent) |
| **C_vs_B** | +0.0303 | [−0.0782, +0.1367] | 44/0/36 | 80 | 0.505 | 1.000 | no | +0.10 | No (null) |
| **D_vs_B** *(primary)* | **+0.0337** | [−0.0776, +0.1428] | 44/0/36 | 80 | 0.539 | 1.000 | no | +0.10 | **No (null)** |
| **D_vs_A** | **+0.1088** | **[+0.0585, +0.1607]** | 49/0/31 | 80 | 0.00064 | **0.00255** | yes | +0.225 | **Yes — in the direction that D is *worse* than A** |

### 11.2 Reference contrasts (descriptive; not Holm-corrected)

| Contrast | mean Δ regret | 95 % cluster-bootstrap CI | reading |
|---|---:|---|---|
| D_vs_oracle | +0.4826 | [+0.4435, +0.5216] | D's mean regret is ≈ 0.48; large gap to the upper bound |
| D_vs_naive | −0.0278 | [−0.0909, +0.0346] | **D is statistically indistinguishable from the literal status quo** |
| D_vs_greedy | +0.2275 | [+0.1892, +0.2663] | D has ≈ 0.23 **more** regret than a trivial first-order heuristic |
| D_vs_classical_optimizer | +0.3987 | [+0.3313, +0.4622] | the OR optimiser on the modelled objective is far ahead of D |

### 11.3 Condition / baseline positioning (mean normalised regret; lower is better)

| oracle | classical_optimizer | greedy | **A** | **B** | **C** | **D** | naive |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.000 | 0.084 | 0.255 | **0.374** | **0.449** | **0.479** | **0.483** | 0.510 |

### 11.4 Headline

On the exogenous objective, over an independently generated locked-test set:

1. **The full multi-agent pipeline (D) does not improve on decision simulation
   alone (B).** Primary contrast `D_vs_B`: null (Holm p = 1.0, CI includes 0,
   |Δ| = 0.034 < 0.10).
2. **The single agent (C) adds nothing detectable over B** (`C_vs_B` null).
3. **The full architecture (D) is significantly *worse* than the
   minimal-intervention reference (A)** by ≈ 0.11 normalised regret
   (Holm p = 0.0026, CI excludes 0, Δ > MEI).
4. **D is not better than doing nothing** (`D_vs_naive` null) and is **clearly
   worse than a trivial greedy heuristic** and than a standard optimiser.
5. `B_vs_A` reaches significance on the signed-rank test but the mean-difference
   CI includes 0 and the direction is inconsistent (mean favours A; 44/80
   scenarios favour B), so no directional claim is made.

This is a **negative result** for the downstream components on this synthetic,
controlled evaluation. It is reported as-is.

## 12. Component-level / per-family results

Mean normalised regret by locked family (lower is better):

| Family (n=20 each) | A | B | C | D | greedy |
|---|---:|---:|---:|---:|---:|
| `asymmetric_risk` | 0.623 | **0.000** | 0.511 | 0.522 | 0.228 |
| `competing_objectives` | 0.406 | **0.023** | 0.441 | 0.468 | 0.406 |
| `missing_observations` | 0.235 | **0.772** | 0.259 | 0.260 | 0.156 |
| `promotion_decision` | 0.231 | **1.000** | 0.705 | 0.681 | 0.231 |

The aggregate `D_vs_B` null is the average of **large offsetting effects**:

- Where decision simulation is near-optimal (`asymmetric_risk` B = 0.000,
  `competing_objectives` B = 0.023), the agent layer **destroys** the gain
  (D = 0.52, 0.47). The risk-manager penalty pushes D away from the
  price-increase that is exogenously optimal under inelastic demand.
- Where decision simulation is badly misled by degraded observations
  (`missing_observations` B = 0.772, `promotion_decision` B = 1.000), the agent
  layer **recovers** much of the loss (D = 0.26, 0.68).

Secondary internal metric (`goal_achievement`, labelled, self-graded by the
Digital Twin): B = 0.895, C = 0.305, D = 0.315 — even the pipeline's own metric
does not favour D over B.

## 13. Baseline analysis (frozen §J)

- **oracle** (upper bound): mean regret 0 by construction; mean 6.0 feasible
  actions per instance.
- **classical_optimizer**: mean regret **0.084**, 0 `na` — a standard optimiser
  on the modelled objective is near the oracle and far ahead of A/B/C/D.
- **greedy**: mean regret **0.255** — a one-line first-order heuristic beats
  every DecisionGPT condition on this suite.
- **naive** (literal status quo): mean regret **0.510** — worse than A (the
  minimal-intervention reference) but statistically tied with D.
- Gap to oracle (= regret): A 0.374, B 0.449, C 0.479, D 0.483.

## 14. Agent analysis (frozen §K; no agent output was modified)

- **Score spread across actions** (mean per-instance range): Business-Analyst
  **0.009** (essentially constant — uninformative on this suite),
  Financial-Advisor **0.573**, Risk-Manager **0.708**. The FA and RM agents are
  *not* inert; they vary strongly.
- **Inter-agent agreement** (mean): 0.634.
- **Selection changes**: the full agent+optimizer layer changes D's selection
  vs the single agent C in **10.6 %** of instances, and vs the greedy baseline
  in **82.1 %** of instances.
- `C − B` mean = +0.030, `D − B` mean = +0.034 (both null, §11.1).
- **Finding:** the agent layer is active (it moves selections and its FA/RM
  scores vary), but on the exogenous metric its net effect over decision
  simulation is indistinguishable from zero, and its family-level effects are
  bimodal (§12). This is reported as a **negative finding for the agent layer's
  objective contribution**, not as "agents are inert."

## 15. Mechanism analysis (frozen §M; ASSOCIATIONAL, EXPLORATORY — NOT causal)

OLS of each per-scenario contrast on standardised scenario factors (bootstrap
CIs, 5000 resamples, seed 4242). Coefficients whose 95 % CI excludes 0:

| Contrast | factor | β (standardised) | 95 % CI | reading (associational) |
|---|---|---:|---|---|
| `D_vs_B` | `uncertainty` | +0.189 | [+0.102, +0.374] | higher declared uncertainty ⇒ D worse relative to B |
| `D_vs_B` | `agent_disagreement` | +0.215 | [+0.113, +0.272] | more inter-agent disagreement ⇒ D worse relative to B |
| `C_vs_B` | `agent_disagreement` | +0.219 | [+0.115, +0.276] | same pattern for the single agent |
| `C_vs_B` | `uncertainty` | +0.184 | [+0.098, +0.374] | |
| `B_vs_A` | `uncertainty` | −0.196 | [−0.479, −0.093] | higher uncertainty ⇒ B better relative to A |
| `B_vs_A` | `risk_exposure` | −0.285 | [−0.374, −0.081] | |
| `B_vs_A` | `agent_disagreement` | −0.225 | [−0.289, −0.067] | |

All other factor coefficients have CIs spanning 0. Language: *component-level
effect under controlled simulation*; **not** a causal statement about real
businesses.

## 16. Failure-case analysis (frozen §N)

- **D much better than B** (largest negative `D − B`): the top 5 are all
  `missing_observations` (B regret 1.000 → D regret 0.049–0.232).
- **D much worse than B** (largest positive `D − B`): the top 5 are all
  `competing_objectives` (B regret 0.000 → D regret 0.569–0.665).
- **Highest absolute D regret**: the top 5 are all `promotion_decision`
  (D regret 0.78–0.87).
- **greedy beats D**: every `promotion_decision` instance (D ≈ 0.76–0.87 vs
  greedy ≈ 0.20–0.26); also present in `missing_observations`.
- **naive beats D**: every `promotion_decision` instance (D ≈ 0.76–0.87 vs
  naive ≈ 0.34–0.40).
- **near-oracle D** (regret ≤ 0.02): 1 instance (`missing_observations__0004`).

Nothing unfavourable is hidden: `promotion_decision` is where the frozen
pipeline is at its worst in absolute terms, and `competing_objectives` /
`asymmetric_risk` are where the agent layer subtracts the most value relative to
decision simulation.

## 17. Robustness results (frozen §11; descriptive, not confirmatory)

Scope (operational choice; frozen §11 leaves it open): the deterministic
20-scenario subsample `sorted(locked)[::4]` of the locked-test partition
(5 instances from each of the 4 locked families), seeds `20260906–20260907`,
each of the 10 perturbations at its lowest and highest configured severity —
**720 runs, 0 errors**. Ground-truth parameters are **never** perturbed — only
the observations the pipeline ingests — so every condition is still graded
against the true optimum. Degradation = **increase in normalised regret**
relative to the clean locked run (a **negative** value = regret *fell*).

`experiments/upgraded_controlled_v1/robustness_results.json` holds the
authoritative per-curve numbers.

| Perturbation (low→high sev) | A auc | B auc | C auc | D auc | reading |
|---|---:|---:|---:|---:|---|
| `input_noise` (.25→.75) | 0.000 | 0.000 | −0.048 | −0.047 | C/D regret **falls** ≈ 0.08 |
| `uncertainty_inflation` (.5→1.0) | 0.000 | 0.000 | −0.057 | −0.028 | C/D regret falls |
| `missing_values` (.2→.4) | 0.000 | 0.000 | −0.011 | −0.009 | C/D regret falls slightly |
| `forecast_error_bias` (.25→.5) | 0.000 | 0.000 | −0.001 | −0.001 | ~no effect |
| `distribution_shift` (.3→.6) | 0.000 | 0.000 | −0.002 | −0.002 | ~no effect |
| `constraint_tighten` / `constraint_relax` | 0.000 | 0.000 | 0.000 | 0.000 | no effect |
| `extreme_but_feasible` (1.0) | 0.000 | 0.000 | 0.000 | −0.002 | ~no effect |
| `adversarial` (1.0) | 0.000 | 0.000 | +0.012 | +0.009 | C/D regret rises slightly |
| `contradictory_signals` (.5→1.0) | 0.000 | 0.000 | **+0.028** | **+0.039** | the one perturbation that clearly degrades C/D |

Baseline (clean-run) mean regret on this subsample: A 0.391, B 0.382, C 0.464,
D 0.470.

Observations:

1. **A and B are perturbation-insensitive on this subsample** (every value equals
   the clean value to 4 dp). A is deterministic and history-independent by
   construction; B's Digital-Twin argmax did not move under these observation
   perturbations here (the subsample is dominated by `asymmetric_risk` /
   `competing_objectives`, where B's extreme-price pick stays argmax-optimal, and
   by `promotion_decision` / `missing_observations`, where B is already at the
   worst-feasible bound). Whether this is genuine stability or limited
   perturbation reach into the DT is not resolved by this descriptive run.
2. **Several observation-noise perturbations *reduce* C/D regret.** Adding noise
   (`input_noise`, `uncertainty_inflation`, `missing_values`) disrupts the agent
   layer's counter-productive steering on the families where it hurts (§12, §16),
   so C/D land closer to B's better pick.
3. **`contradictory_signals` is the only perturbation that clearly degrades
   C/D** (D auc +0.039).
4. **No perturbation drove any condition to 50 % degradation**
   (`severity_at_50pct_degradation = None` for every curve).

This is consistent with the primary finding: the agent layer's net objective
contribution is not positive, and perturbations that damp it tend to *help* the
full system on this suite.

## 18. Secondary (internal) metric — labelled, never a conclusion

`secondary_goal_achievement` (the Digital Twin's own projected KPI attainment):
B 0.895, C 0.305, D 0.315. Reported only to show that the **circular** metric
used by the frozen original study would have painted B favourably and C/D
unfavourably — and still would not have favoured D over B. Not used for any
claim here.

## 19. Limitations

- **Synthetic only.** A designed (though parameterised and seed-replicated)
  family set; no real data of any kind.
- **Condition A is a minimal-intervention reference**, not a literal no-op
  (§5); `D_vs_naive` is the cleaner "vs doing nothing" contrast and is also
  null.
- **The ground-truth objective is a modelling choice** (linear elasticity +
  horizon-decay marketing response). Its divergence from the Digital Twin's
  recursive dynamics is measured (`prediction_error` factor), not assumed away,
  but a different closed form could shift magnitudes.
- **Rule-based agents**, unchanged; no real LLM. Findings about "the agent
  layer" are findings about *this deterministic configuration*.
- The **power model ignores exact ties**; here `n_nonzero = 80` on every primary
  contrast, so this did not bite, but it is a stated caveat.
- Robustness is a **subsample** (20 locked scenarios × 2 seeds), descriptive
  only.
- `classical_optimizer` optimises the *same* closed form used for scoring, so
  its small regret is partly definitional; it is a yardstick, not a competitor.

## 20. Evidence boundaries (exact — unchanged)

No real SME outcome data. No real customer data. No prospective business
intervention. No human decision-quality study. No real-LLM evaluation. No
real-world causal validation. `PredictionEvaluation = 0`,
`CAUSALLY_VALIDATED = 0`, Table 2 **NOT READY**, real LLM **BLOCKED**, production
stays **R0/D0**, **R3 NOT PROMOTED** — all unchanged by this study. The
contribution is *a controlled, reproducible, component-level evaluation of the
existing architecture under parameterised synthetic decision environments with
an exogenous objective, returning a negative result for the downstream
components.*

## 21. What this study does and does not license as a claim

**Supported by this evaluation (synthetic, controlled):**
- On an exogenous objective over 80 independently generated locked scenarios,
  adding the agent layer to decision simulation produced **no measurable
  improvement** (`D_vs_B` null), and the full architecture performed
  **significantly worse than a minimal-intervention reference** (`D_vs_A`).
- The effect of the agent layer is **conditional**: it helps when decision
  simulation is misled by degraded observations and hurts when decision
  simulation is already near-optimal (associational, §15–16).
- The evaluation harness, exogenous metric, power analysis, and family-level
  hold-out are reproducible from fixed seeds.

**NOT supported / explicitly not claimed:**
- Any statement that DecisionGPT (or its agent layer, or the full system)
  improves real decisions, business outcomes, ROI, revenue, or customer
  behaviour.
- Any statement that the architecture is "validated", "superior", or "effective"
  for Indian SMEs or any real users.
- Any causal claim about real businesses.
- Any claim derived from the internal `goal_achievement` metric.
- Promotion of R3 or any change to R0/D0.

## 22. Protocol deviations

**None after the freeze date (2026-09-05).** For completeness, three
evaluation-layer corrections were made *before* the pre-registration was frozen,
during the Phase-3 dry run, and are documented in
`docs/UPGRADED_EVALUATION_IMPLEMENTATION.md`: (a) `generator_version` v1 → v2
(per-seed history realisation, so seeds are genuine replicates); (b) profit
families declare the ROI-positive candidate set so the identical-action-space
invariant holds; (c) `insufficient_data` classification for the Digital-Twin
"no usable simulation" case. None changed a hypothesis, endpoint, statistic, or
the locked-test family list.

## 23. Reproducibility

`generator_version = upgraded_eval_scenarios_v2`, `master_seed = 20260906`,
per-instance `content_hash`, `suite_checksum 2215a1bd…`, run seeds
`20260906–20260915`, bootstrap seed 12345, mechanism seed 4242, power
`rng_seed 20260906`. SHA-256 of every artifact in `checksums.txt`. Frozen
experiment manifest SHA-256 `94aa419c…` re-verified before and after every run
and in `REPRODUCIBILITY_AUDIT.md`. Full command sequence: `REPRODUCIBILITY_AUDIT.md`
§"Reproducing the numbers".
