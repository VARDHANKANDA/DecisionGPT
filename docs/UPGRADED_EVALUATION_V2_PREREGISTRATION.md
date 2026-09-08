# Upgraded Controlled Evaluation — V2 Pre-Registration

**Status: DESIGN FROZEN; LOCKED TEST NOT RUN — stopped at the Phase-16 pre-lock
gate.**

This document records the V2 protocol that *would* have governed the locked test,
and the pre-lock validation result that caused the study to **stop before**
locking, per the Phase-16 mandate ("If these fail, STOP. Do not proceed to
locked testing."). See §16 and `docs/UPGRADED_EVALUATION_V2_REPORT.md`.

`upgraded_controlled_v1` is frozen and untouched. The frozen 16-experiment study,
production architecture (R0/D0), R3's status, `docs/PAPER_DRAFT.md`, and
`docs/ieee_paper/` are untouched.

---

## 1. Objective and design type

A **controlled, reproducible, component-level evaluation** of the *existing*
DecisionGPT architecture in an **action-responsive** synthetic environment, with
the **same exogenous objective as V1**. Motivated by the V1 independent audit
(`docs/INDEPENDENT_SCIENTIFIC_AUDIT.md`), which found that V1's primary contrast
could not test its intended question because V1's history was not
action-responsive and condition B degenerated to a constant policy.

**Primary question:** *Does the existing Decision Simulation + multi-agent + risk
+ optimisation pipeline provide incremental objective value over the existing
Decision Simulation condition (D vs B)?*

Not a real-world, SME, LLM, causal, or deployment study.

## 2. Hypotheses (two-sided; direction reported, not assumed)

- **H1 (`B_vs_A`).** B differs from A on the exogenous metric.
- **H2 (`C_vs_B`, `D_vs_B`).** The agent layer adds value beyond Decision
  Simulation. **`D_vs_B` is the primary confirmatory contrast.**
- **H3 (`D_vs_A`).** The full architecture differs from A. **Secondary and
  interpreted cautiously** — A is a fixed smallest-magnitude policy, not a
  generic prediction-only policy (V1 audit finding C-1/DA-1). `D_vs_A` is **not**
  the main argument.
- **H4 (reference, descriptive).** All conditions vs oracle / naive / greedy /
  classical optimiser — labelled **external computational benchmarks**, not
  architecture competitors (V1 audit finding B-1).
- **H5 (mechanism, exploratory, associational).** `D−B` vs scenario factors.
  Never causal; effective cluster count = number of locked families.

## 3. Primary and secondary endpoints

- **PRIMARY:** exogenous **normalised regret** (0 = oracle, 1 = worst feasible;
  lower is better), computed by `backend/app/evaluation/ground_truth.py`
  (**unchanged from V1 — "System B"**) from scenario parameters, **after** action
  selection.
- **SECONDARY (labelled, never a conclusion):** the DecisionGPT-internal
  `goal_achievement`.
- **Tertiary:** latency; action feasibility; agent diagnostics.

## 4. Synthetic environment — "System A" (the V2 change)

`backend/app/evaluation/scenario_families_v2.py`, `GENERATOR_VERSION =
upgraded_eval_scenarios_v3`, `ENV_VERSION = system_A_action_responsive_v1`.

Historical demand **responds to** historical price and marketing via a
**log-linear (power-law)** model with real, identifiable variation in the price
and spend series:

```
price_t  = base_price · exp(mean-reverting walk, band = price_walk_pct)  · promo cycles
spend_t  = base_spend · exp(mean-reverting walk, band = spend_walk_pct)
demand_t = base_demand · (price_t/base_price)**a_elast · (spend_t/base_spend)**a_mkt
           · season_t · inv_avail_t · exp(N(0, sigma_obs))
units_t  = min(demand_t, capacity_cap, on_hand_t)
```

`a_elast < 0`, `a_mkt > 0` are drawn per scenario (family-dependent ranges).
Per-seed `exp(N(0, sigma_obs))` noise ⇒ seeds are genuine independent replicates
for **all** conditions (including B), addressing V1 audit finding E-1.

**System-A ↔ System-B coupling** (so B has *useful but imperfect* information):
`price_elasticity = clip(a_elast + N(0, 0.35), −3.0, −0.15)`;
`marketing_response = clip((0.4 + 3.0·a_mkt)·(1 + N(0, 0.25)), 0.2, 2.0)`;
`kappa = clip(kappa_family + N(0, 0.05), 0.2, 1.0)`. A **parameter relationship**,
not shared code — System A (log-linear) and System B (additive-linear) are
different functional forms (Phase-3 requirement).

**Frozen suite:** `master_seed = 20260906`, `n = 132` (6 per family),
`suite_checksum = d28d521fa32509647dc6fd0aa8bd43a0b82ce131c92c74e14c32423d2b83e6f5`.

## 5. Scenario families — 22 structurally distinct regimes

`elastic_demand`, `inelastic_demand`, `unit_elastic`, `high_marketing_response`,
`low_marketing_response`, `inventory_bound`, `capacity_bound`, `cash_constrained`,
`thin_margin_profit`, `fat_margin_profit`, `competing_objectives`,
`asymmetric_risk`, `delayed_effects`, `high_volatility`, `low_volatility`,
`seasonal_strong`, `noisy_observations`, `missing_observations`, `low_data`,
`conflicting_signals`, `promotion_decision`, `supplier_shock`.

Each corresponds to a genuine structural difference in System A (elasticity
regime, marketing-response regime, inventory/capacity/cash binding, seasonality
amplitude, observation-degradation mode, horizon decay, cost shock, …), not a
cosmetic label. Full parameter ranges: `scenario_families_v2.py`, recorded in
`scenario_manifest.json`.

## 6. Partition — deterministic stratified family-level holdout

Families are ordered by structural super-group, shuffled within group by a fixed
seed, then walked with the repeating pattern `[dev, dev, val, locked]` so the
validation and locked families come from *different* super-groups (addresses V1
audit finding G-1). Deterministic from `master_seed`; fixed at design time,
independent of any outcome.

- **development:** 12 families
- **validation:** 5 families (`cash_constrained`, `competing_objectives`,
  `elastic_demand`, `high_volatility`, `missing_observations`)
- **locked test:** 5 families (`capacity_bound`, `conflicting_signals`,
  `delayed_effects`, `low_marketing_response`, `seasonal_strong`),
  `locked_test_family_checksum = <in config.json>`.

## 7. Sample size and power

Simulation-based (`stats.simulate_power`) from a **V2 development-stage pilot**
variance estimate (development + validation only; **never** locked-test
outcomes). Assumptions to be frozen: `primary_comparison = D_vs_B`,
`min_effect_of_interest` (normalised regret, chosen on substantive grounds),
`alpha = 0.05`, `target_power ≥ 0.80`, `n_scenarios` (locked), `n_seeds`,
`metric_sd_between_scenarios` (conservative; from the pilot, ≥ the pilot value),
`within_scenario_seed_sd`. N chosen to reach the target power — **not** chosen
for significance. **Not completed** — the study stopped before freezing (§16).

## 8. Seeds

Exactly **10** independent seeds per scenario (`20260906 … 20260915`); each drives
an independent `scenario_families_v2.realise_history`. Scenario-level evidence is
distinguished from seed-level variation; the inferential unit is the **scenario**.

## 9. Conditions and baselines

`A` Prediction only (scored as `ground_truth._noop_action`) · `B` + Decision
Simulation · `C` + single agent · `D` Full system (`decision_service.analyze_goal`
with **default `PipelineOptions` = R0/D0**). Identical to V1; production unchanged.

Baselines (external computational benchmarks, never architecture competitors):
`naive` · `greedy` · `oracle` · `classical_optimizer`. Outperforming them proves
nothing about production usefulness (V1 audit finding B-1).

Identical-feasible-action-space invariant verified per instance.

## 10. Statistical analysis (pre-specified)

Unit = **scenario** (10 seeds aggregated to the scenario mean first). Per primary
contrast: n, mean & median paired difference, SD, W/T/L, `n_nonzero`, paired
**Wilcoxon signed-rank**, matched-pairs **rank-biserial** (estimator), paired
**scenario cluster bootstrap** 95 % interval (10 000 resamples, seed 12345),
Student-t interval (secondary). **Holm–Bonferroni** across
`{B_vs_A, C_vs_B, D_vs_B, D_vs_A}`. Reference contrasts descriptive, excluded from
the correction.

A non-significant `D_vs_B` is reported as **"no statistically significant
incremental improvement was detected"**, never as "equivalence" (unless a
pre-registered equivalence test — not planned — supports it).

## 11. Exclusion rules (pre-specified)

Same as V1: (1) identical-action-space invariant fails; (2) any of A/B/C did not
complete (`status != "ok"`), e.g. Digital-Twin `insufficient_data`. Excluded
instances reported with counts + reasons.

## 12. Robustness (descriptive, not confirmatory)

The 10-perturbation V1 suite (`perturbations.py`, unchanged) on a deterministic
locked-test subsample. `input_noise`, `forecast_error_bias`, `missing_values`,
`uncertainty_inflation`, `constraint_tighten/relax`, `distribution_shift`,
`contradictory_signals`, `extreme_but_feasible`, `adversarial`. DecisionGPT is
never tuned to improve these.

## 13. Mechanism analysis (exploratory, associational)

OLS of `D−B` / `C−B` / `B−A` on standardised scenario factors + bootstrap CIs +
tertile buckets. Not primary evidence. Never causal. Effective cluster count =
number of locked families (5) — factor-level claims not supported;
family-level description only.

## 14. Stopping rules

The locked test runs **once**, only after (a) this pre-registration is frozen
with a checksum and (b) **all** Phase-16 pre-lock checks pass. No tuning, no
sample-size expansion, no scenario removal, no result shopping after the locked
run.

## 15. Interpretation prohibitions

No real-world / SME / Indian-SME / ROI / customer / deployment / causal claim,
regardless of outcome. A positive `D_vs_B` is **not** SME validation. A negative
`D_vs_B` is **not** proof that multi-agent systems never work. The internal
`goal_achievement` metric is never external validation.

## 16. Pre-lock validation result (Phase 16) — **GATE NOT PASSED → STOP**

Run on **development + validation only** (68 scenarios × 4 seeds = 272 real-
pipeline executions; `experiments/upgraded_controlled_v2/prelock_diagnostics.json`;
locked-test partition **never touched**; frozen manifest `94aa419c…` verified
unchanged before and after):

| Phase-16 check | Result |
|---|---|
| 3. Ground truth independent | **PASS** — `ground_truth.py` imports only stdlib + numpy + scipy; unchanged from V1 |
| 4. Oracle exactly correct | **PASS** — 0/68 mismatches vs independent enumeration |
| 5. Candidate-space identity | **PASS** — 0 invariant failures; declared == resolved on all 272 |
| 6/7. No future / objective leakage | **PASS** — `ground_truth.*` called only after selection (harness fairness logic reused unchanged) |
| 2. Scenario outcomes respond to actions | **PASS** — an OLS of log(units) on log(price) over the *generated history* recovers the true `a_elast` with **median abs error 0.097** (log-price SD ≈ 0.12). The environment is action-responsive and the response is identifiable. |
| 9. Families structurally distinct | **PASS** — 22 regimes; parameter ranges differ, not just labels |
| **1. B is not trivially constant** | **FAIL** — across all 272 development executions, condition B selects **`price_change=+10%`** on every non-inventory family (and `inventory_change=+20` on the inventory family). **2 unique actions total**; correlation between B's chosen price move and the true elasticity ≈ **0.03**. B does **not** respond to the (recoverable) demand elasticity. |
| 10. Planned power adequate | **NOT REACHED** — study stopped before the power step |
| 11. Statistical unit defined | (would be scenario) — not reached |

**Root cause (verified by directly probing `digital_twin_service.simulate_strategy`
on elastic and inelastic scenarios):** the production Digital Twin's projected
revenue is **monotonically increasing in price for every scenario**, because its
internal demand model carries a near-zero price elasticity (implied ≈ −0.1) that
is not fitted from the historical price↔demand covariance. Its projected KPI
argmax over the candidate set is therefore **always the largest price increase**
(`price_change=+10`), irrespective of the true elasticity. Marketing candidates
project nearly identically to each other (the DT is insensitive to the marketing
lever beyond a point).

**Decision (Phase 16):** Condition B is trivially constant, and this is
**genuinely unavoidable** without modifying the production Decision Simulation
(`digital_twin_service`), which is forbidden. Phase-16 check #1 fails. **The V2
locked test was NOT run.** This pre-registration is therefore *design-frozen but
not sealed for a locked run*; `config.prereg_frozen` remains `false` and
`config.status = "STOPPED_AT_PRELOCK_GATE"`.

## 17. Sign-off

- [x] Design frozen (`docs/UPGRADED_EVALUATION_V2_DESIGN.md`, this document).
- [x] Suite generated + partition sealed (`scenario_manifest.json`,
  `suite_checksum d28d521f…`).
- [x] Pre-lock diagnostics run on development/validation only
  (`prelock_diagnostics.json`); locked-test partition never touched.
- [x] Phase-16 gate evaluated → **check #1 FAILED (B trivially constant,
  unavoidable) → STOP**.
- [ ] ~~Power analysis frozen~~ — not reached.
- [ ] ~~`config.prereg_frozen = true`~~ — deliberately not set; locked test not run.
- [x] Date: **2026-09-06**.
