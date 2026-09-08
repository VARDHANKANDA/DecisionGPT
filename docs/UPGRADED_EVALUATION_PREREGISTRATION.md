# Upgraded Controlled Evaluation — Pre-Registration

**Status: FROZEN — 2026-09-05.** `experiments/upgraded_controlled_v1/config.json`
has `prereg_frozen: true`; the frozen SHA-256 of *this file* and of `config.json`
are recorded in `config.json → prereg` and in `checksums.txt`. No section of
this document — design, hypotheses, endpoints, scenario suite, partition, power,
statistics, exclusions, or interpretation rules — may change after this point;
any later change is disclosed as a dated protocol deviation in
`docs/UPGRADED_EVALUATION_REPORT.md`. The locked-test partition may now be run
**once** (§13).

This is an additive study. It does not modify the 16 frozen experiments, the
frozen manifest (`94aa419c…`), R0/D0, or R3's status.

**Frozen suite:** `scenario_manifest.json`, `generator_version =
upgraded_eval_scenarios_v2`, `master_seed = 20260906`, `n = 340`,
`suite_checksum = 2215a1bdde0294a08d5ea786f2c657f8b15b5e9ba6e37e82329df68a39629697`.
**Frozen locked-test families** (`locked_test_family_checksum =
47f0afd643b72211b1a3423c99f186bc38f7776d8e68342ba00b67186da5ea95`):
`asymmetric_risk`, `competing_objectives`, `missing_observations`,
`promotion_decision` (80 instances).

---

## 1. Objective and design type

A **controlled, reproducible component-level evaluation** of the *existing*
DecisionGPT architecture under parameterised synthetic decision environments,
with an **exogenous** ground-truth objective. Not a real-world, Indian-SME,
LLM-agent, causal-intervention, or deployment study.

## 2. Hypotheses (two-sided; direction reported, not assumed)

- **H1.** The business decision-simulation layer contributes measurable value on
  the exogenous metric: B (Prediction + Decision Simulation) differs from A
  (Prediction only). *(primary contrast: `B_vs_A`)*
- **H2.** The agent layer contributes value beyond decision simulation: C
  (single agent) and D (full system) differ from B. *(primary contrasts:
  `C_vs_B`, `D_vs_B`)*
- **H3.** The full architecture differs from prediction-only: `D_vs_A`.
- **H4 (reference).** All conditions are compared to the oracle upper bound and
  to the naive / greedy / classical-optimizer baselines (`D_vs_oracle`,
  `D_vs_greedy`, `D_vs_classical_optimizer`) — descriptive positioning, not
  confirmatory.
- **H5 (mechanism, exploratory).** The sign/size of `B_vs_A`, `C_vs_B`, `D_vs_B`
  depends on scenario factors (uncertainty, constraint tightness, objective
  conflict, prediction error, risk exposure, action-space size, agent
  disagreement). Reported as *component-level effects under controlled
  simulation*; **not** causal.

## 3. Primary and secondary endpoints

- **PRIMARY:** exogenous **normalised regret** (0 = oracle, 1 = worst feasible;
  lower is better) of each condition's selected action, computed by
  `backend/app/evaluation/ground_truth.py` from scenario parameters — never by
  the Digital Twin. `performance_ratio` (= 1 − regret at the endpoints) is
  reported alongside.
- **SECONDARY (labelled, never used for a conclusion):** the DecisionGPT-internal
  `goal_achievement` (the Digital Twin's own projected KPI attainment).
- **Tertiary:** decision latency; feasibility of the selected action;
  agent-diagnostic quantities.

## 4. Scenario generation

- `backend/app/evaluation/scenario_families.py`, `GENERATOR_VERSION =
  upgraded_eval_scenarios_v2`. (`v2` replaced `v1` during the Phase-3 dry run,
  before this document was frozen: a scenario now carries a *history
  specification* and the concrete day-by-day history the system ingests is
  realised per `(scenario, seed)` by `realise_history`, so the seeds of §8 are
  genuine independent replicates rather than deterministic re-runs of one fixed
  history. No methodology in this document changed; the change only makes the
  seed dimension real.)
- **17 families:** demand_uncertainty, price_uncertainty, inventory_constraint,
  cash_constraint, capacity_constraint, promotion_decision, resource_allocation,
  supplier_uncertainty, competing_objectives, asymmetric_risk, delayed_effects,
  noisy_observations, missing_observations, conflicting_signals, low_data,
  high_volatility (stress), adversarial_risk_trap (adversarial).
- `generate_suite(n, master_seed)`; **`master_seed = 20260906`**; **`n = 255`**
  (15 per family). Family-level 60 / 20 / 20 split ⇒ development 165, validation
  45, **locked test 60** (4 families: `asymmetric_risk`, `competing_objectives`,
  `missing_observations`, `promotion_decision`; sealed
  `locked_test_family_checksum` in `config.json`). `n` was fixed here from the
  §7 power analysis, before any locked-test outcome was observed.
- **Feasible-action declaration for profit objectives.** The ephemeral business
  the harness seeds always records positive marketing ROI, so the production
  `strategy_generation_service` always emits its extra "marketing +10%"
  candidate for an `increase_profit` goal. The generator declares that candidate
  in `feasible_actions` for every profit family, so the identical-action-space
  invariant (§6) holds. Verified in the Phase-3 dry run.
- Every instance is fully machine-readable (params, day-by-day history,
  constraints, objective, feasible actions, uncertainty/noise, provenance,
  content hash) in `experiments/upgraded_controlled_v1/scenario_manifest.json`.
- **Action vocabulary is the production one only** (`price_change` /
  `marketing_change` / `inventory_change`). The feasible action set per instance
  is the production `strategy_generation_service` candidate set for the goal; the
  harness re-derives and verifies it per instance.

## 5. Partition terminology (this architecture has no training phase)

- **development scenario set** (60% of families) — methodology iteration allowed.
- **validation scenario set** (20%) — methodology tuning allowed, sparingly.
- **locked test scenario set** (20%) — the primary conclusion. Sealed by
  `scripts/run_upgraded_eval.py split` (family list + checksum in `config.json`).
  Not used to tune anything after this document is frozen. Split is **by family**
  (no family appears in two partitions), deterministic from `master_seed`.
- These are **not** machine-learning training data.

## 6. Conditions and baselines

Frozen, invoked read-only:
`A` Prediction only · `B` Prediction + Decision Simulation · `C` + single agent ·
`D` Full system (`decision_service.analyze_goal` with **default `PipelineOptions`
= R0/D0**).

Evaluation-only baselines (never call DecisionGPT):
`naive` (status quo) · `greedy` (local first-order heuristic) · `oracle`
(best feasible action under the ground-truth objective — **upper-bound reference,
not a competitor**) · `classical_optimizer` (continuous relaxation + projection;
`na` where no smooth formulation exists).

**Identical-feasible-action-space invariant:** every condition A/B/C/D selects
from the identical enumerated feasible set for a given instance;
`harness.verify_identical_action_space` asserts this; a violation →
`exclude_from_primary = True`.

## 7. Sample size and power — **COMPLETED AND FROZEN**

Simulation-based (`stats.simulate_power`), from the explicit assumptions file
`experiments/upgraded_controlled_v1/power_assumptions.json`, fixed **before** any
locked-test result was seen. All assumptions were stated a priori and are **not**
derived from observed results:

| assumption | value | basis |
|---|---|---|
| `primary_comparison` | `D_vs_B` | the confirmatory question of interest |
| `min_effect_of_interest` (normalised regret) | **0.10** | smallest shift, on the 0 = oracle … 1 = worst-feasible scale, that is practically meaningful for an entire decision-support layer; chosen for substantive reasons, not to reach a power target |
| `alpha` | 0.05 | two-sided |
| `target_power` | 0.80 | conventional |
| `n_scenarios` (locked test) | **80** | 4 locked families × 20 instances |
| `n_seeds` | **10** | §8 |
| `metric_sd_between_scenarios` | 0.28 | deliberately wide: paired D−B differences are mostly near zero with occasional large swings (seen in the Phase-3 dry run), so a high scenario-level SD is assumed rather than an easy-to-detect one |
| `within_scenario_seed_sd` | 0.12 | regret noise from per-seed history realisation |
| `n_sim` / `rng_seed` | 20000 / 20260906 | Monte-Carlo settings |

**Result (`power_analysis.json`): estimated power = 0.860 ≥ 0.80.** `n` was sized
*from* this analysis: `n = 340` (20 per family) ⇒ locked test = 80. If the
Phase-3 dry-run assumptions had implied power < 0.80, `n` would have been raised
and this file re-frozen before the locked run — that did not occur.

**Stated limitation.** `simulate_power` models every scenario as contributing a
non-zero `N(MEI, sd_eff)` paired difference; it does **not** model ties. If a
large fraction of locked scenarios are exact D = B ties, the achieved non-zero
`n` — and thus power — is lower than 0.860. The pre-registered mitigation: the
report states the observed tie rate and `n_nonzero`; a null primary contrast
with a wide interval is interpreted as *"no effect detected at MEI = 0.10 given
the achieved non-zero n"*, never as proof of no effect (§14).

## 8. Seeds

Exactly **10** independent seeds per scenario: the integers `20260906 …
20260915` (`master_seed + 0..9`). Each seed drives an independent
`scenario_families.realise_history(scenario, seed)` (genuine replicate — see §4);
`analyze_goal` / `simulate_strategy` are otherwise deterministic given the seeded
business. Every seed is recorded per instance in `results.json`. Deterministic
replications are not counted as independent evidence. The scenario is the unit of
analysis (§9); seeds are aggregated within scenario before the paired tests.

## 9. Statistical analysis (`backend/app/evaluation/stats.py`)

- **Unit = scenario.** Seeds are aggregated within scenario (mean) before the
  paired tests.
- Per primary contrast: n_scenarios, mean & median paired difference, SD,
  wins/ties/losses, n_nonzero, **paired Wilcoxon signed-rank** (exact for
  n_nonzero ≤ 25, normal approx otherwise; "not assessed" when < 2 non-zero),
  **matched-pairs rank-biserial** correlation (PRIMARY effect size; estimator,
  not p-derived), **paired scenario cluster bootstrap** 95% interval of the mean
  difference (PRIMARY interval), Student-t interval (secondary reference only).
- **Multiplicity:** Holm-Bonferroni across the confirmatory family
  `{B_vs_A, C_vs_B, D_vs_B, D_vs_A}`. `alpha = 0.05`. Reference/baseline
  contrasts (`D_vs_oracle`, `D_vs_greedy`, `D_vs_classical_optimizer`) are
  descriptive and excluded from the correction.
- The frozen historical study's p-derived `effect_size_r` in
  `multi_scenario_service` is **not touched**; the new study uses the
  rank-biserial estimator.

## 10. Exclusion rules (pre-specified)

An instance is excluded from the **primary** paired analysis if:
1. the identical-feasible-action-space invariant fails
   (`action_space_invariant_ok == false`) → `exclude_reason =
   "identical_action_space_invariant_failed"`; or
2. any of conditions A/B/C did not complete (`status != "ok"`). The concrete
   case implemented and verified in the Phase-3 dry run: when the frozen Digital
   Twin cannot evaluate **any** feasible action (history below
   `forecast_service.MIN_HISTORY_DAYS = 35`, i.e. some `low_data` instances),
   B and C are marked `insufficient_data` and `exclude_reason =
   "insufficient_data"`.

Excluded instances are still reported (counts + reasons) and retained for
robustness / mechanism description. Condition D failing (`status ∈ {error,
insufficient_data, pick_outside_feasible_set}`) is recorded but does **not** by
itself exclude the instance from `B_vs_A` / `C_vs_B`; it does remove that
instance from any contrast that involves D.

## 11. Robustness analyses (`backend/app/evaluation/perturbations.py`)

For each perturbation × severity in the scenario's `perturbation_config`,
re-run all conditions on the perturbed **observations** (ground truth unchanged)
and report `degradation_curve` per condition
(`experiments/upgraded_controlled_v1/robustness_results.json`). Descriptive;
not part of the confirmatory family.

## 12. Mechanism analysis (`backend/app/evaluation/mechanism.py`)

OLS of each per-scenario contrast on standardised factors + bootstrap CIs +
tertile buckets. Exploratory; language is "component-level effect under
controlled simulation", never causal.

## 13. Stopping rules

The locked-test evaluation is run **once**. No peeking, no adaptive stopping, no
re-running after seeing results. If a bug is found in the harness/ground truth
after the locked run, the fix + a full re-run are disclosed as a protocol
deviation.

## 14. Interpretation rules

- A contrast is "supported" only if the Holm-adjusted p < 0.05 **and** the
  cluster-bootstrap interval excludes 0 **and** the mean shift exceeds the
  pre-stated `min_effect_of_interest`.
- Effect magnitude is always reported as the **mean paired difference**; the
  rank-biserial is reported with its n_nonzero; r near ±1 on few non-zero pairs
  is described as sign-consistency, not a large practical effect.
- No real-world / SME / ROI / causal / LLM / deployment claim is made regardless
  of outcome (see `docs/FROZEN_ARCHITECTURE_EVALUATION_AUDIT.md` §5 PI12).

## 15. Evidence boundaries (restated)

No real SME outcome data; no real customer data; no prospective intervention; no
human decision-quality study; no real-LLM evaluation; no real-world causal
validation. `PredictionEvaluation = 0`, `CAUSALLY_VALIDATED = 0`, Table 2 NOT
READY — unchanged.

## 16. Reproducibility

`generator_version`, `master_seed`, per-instance `content_hash`, `suite_checksum`,
`partition` checksum, bootstrap seeds, power `rng_seed`, and SHA-256s of every
output file (`checksums.txt`). Frozen-manifest SHA-256 re-verified before and
after every run (`scripts/run_upgraded_eval.py verify-freeze`).

## 17. Sign-off

- [x] §7 power analysis completed; `power_assumptions.json` +
  `power_analysis.json` written (estimated power 0.860 ≥ 0.80).
- [x] Scenario suite generated and partition sealed: `scenario_manifest.json`
  (`suite_checksum 2215a1bd…`), `locked_test_family_checksum 47f0afd6…`.
- [x] `experiments/upgraded_controlled_v1/config.json` → `prereg_frozen: true`,
  with `prereg.doc_sha256` and `prereg.config_sha256` recorded.
- [x] Locked-test family list + checksum recorded; unchanged since freeze.
- [x] Date frozen: **2026-09-05**.  Prepared by: DecisionGPT research engineering
  (upgraded controlled evaluation, `evaluation_layer_version =
  upgraded_controlled_v1`).

Anything below this line that must change after the freeze date is a **protocol
deviation** and is disclosed, dated, with rationale, in
`docs/UPGRADED_EVALUATION_REPORT.md` §"Protocol deviations".
