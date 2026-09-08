# R1 — Pre-Registration

**Status: DESIGN FROZEN pending the pre-lock gate.** Every design decision that
can affect the primary outcome is fixed here BEFORE the R1 locked test is
generated or run (task Section 12). `config.prereg_frozen` is set to `true` only
by `scripts/run_eval_r1.py freeze-prereg`, after `docs/R1_PRELOCK_GATE.md`
records a GO.

R0/D0, R3, V1, and V2 are historically frozen and untouched. R1 is a **versioned
research-only Decision-Simulation correction** (`docs/R1_DT_DIAGNOSTIC.md`); it is
never presented as the production system and never as real-SME validation. V1
and V2 results are **not pooled** with R1.

Frozen checksums verified before this work began and re-verified in the audit:
`experiment_manifest.json` = `94aa419c703b1babb465975463b26e55255755a7687ecbecadb6db4c4c15cbff`;
V1 `suite_checksum 2215a1bd…` / `results.json 804fbe91…` / `evaluation_complete`;
V2 `suite_checksum d28d521f…` / `STOPPED_AT_PRELOCK_GATE`.

---

## 1. Objective and design type

A controlled synthetic **component ablation** of the DecisionGPT architecture
(A → B → C → D) in an environment where the Decision-Simulation condition (B) can
genuinely react to identifiable price/marketing response. It answers:

**Primary question:** *In a research-only corrected Decision-Simulation
environment, does the full downstream architecture (D) produce lower exogenous
normalised regret than Decision Simulation alone (B)?*

Not a real-world, SME, Indian-SME, LLM, causal, ROI, or deployment study.

## 2. The R1 correction (the ONLY architectural difference)

`backend/app/evaluation/r1/r1_dt.py` (`r1_dt_constant_elasticity_v1`), injected
at test time by `r1.harness`, production files byte-identical:

```
u_a  = u_base · clip((1+Δp/100)**ε̂ , 0, 5) · clip((1+Δm/100)**â , 0, 5) · fulfil_cap
revenue_a = u_a · p_a ;  profit_a = u_a · (p_a − ĉ)
```

- `u_base`, `baseline_*`, `risk_score`, `risk_level`, model name, control flow,
  candidate set, agents, optimizer, risk manager, `analyze_goal` (R0/D0) — **all
  from production, unchanged**.
- `ε̂ ∈ [−4, −0.05]`, `â ∈ [0, 1]` — estimated per instance by OLS of
  `log(units) ~ log(price) + log(marketing_spend) + weekday` over the business's
  own seeded history. Fallback to the scenario generator's `a_elast`/`a_mkt`
  (System A, **not** System B) when the history is too short / degenerate /
  wrong-signed; logged, reported, and sensitivity-analysed (§13).
- `fulfil_cap`: current inventory × (1+Δi/100) and the scenario `capacity_cap` —
  known operational limits, **not** the objective or oracle.
- No coefficient is hand-tuned; none is chosen to favour a condition.

Information boundary: `docs/R1_INFORMATION_BOUNDARY.md`.

## 3. Hypotheses (two-sided; direction reported, not assumed)

- **H1 (`B_vs_A`).** B differs from A on exogenous regret.
- **H2 (`C_vs_B`).** The single agent changes regret vs B.
- **H3 (`D_vs_C`).** The remaining agents + risk + optimizer change regret vs C.
- **H4 (`D_vs_B`) — PRIMARY.** The full downstream architecture differs from
  Decision Simulation alone.
- **H5 (reference, descriptive).** All conditions vs oracle / naive / greedy /
  classical (external computational benchmarks with documented information
  advantages — never architecture competitors).
- **H6 (mechanism, exploratory, associational, non-causal).** `D−B` depends on
  scenario factors and on DT-vs-ground-truth action discrepancy.

## 4. Endpoints

- **PRIMARY:** exogenous **normalised regret**, `0 = oracle`, `1 = worst
  feasible`, lower is better; computed by `app.evaluation.ground_truth`
  ("System B", unchanged, independent) **after** action selection. Primary
  contrast statistic = the **paired scenario-level difference** `regret_D −
  regret_B`.
- **SECONDARY (labelled, never external validation):** DecisionGPT-internal
  `goal_achievement`.
- **Tertiary:** action feasibility; latency; agent diagnostics;
  `r1_dt` estimation method + `|ε̂ − a_elast|`.

## 5. Scenario environment

- `backend/app/evaluation/r1/scenario_families.py`,
  `GENERATOR_VERSION = r1_eval_scenarios_v1`, `ENV_VERSION =
  system_A_action_responsive_v1` (the verified V2 System-A engine).
- **27 structurally distinct families** (Section 9 mechanism list): price
  elastic / inelastic; strong / weak / asymmetric marketing response; competing
  objectives; asymmetric risk; inventory / capacity / budget / interacting
  constraints; delayed marketing / price effects; seasonal (weak / moderate /
  strong); conflicting signals; noisy / missing / sparse observations; demand
  saturation; diminishing marketing returns; promotion threshold; high / low
  uncertainty; regime shift; nonlinear response.
- `master_seed = **20260907**` (a fresh seed — an earlier `20260906` draft suite
  was discarded once the power analysis showed a larger locked partition was
  needed, so that no scenario observed during design sizing could land in the
  final locked set), **34 scenarios per family**, **N = 918 unique scenarios**.
  `suite_checksum =
  cd73f0d59aafa87c7b1502f24d2c737fc9d92e77f43280ee06fb43abfbba9afd`.
- Parameter ranges, distributions, and per-scenario `content_hash` are recorded
  in `experiments/r1/scenario_manifest.json` (frozen at `freeze-prereg`).

## 6. Train / development / locked split (Section 11 — strict)

Deterministic **stratified round-robin** family-level holdout (pattern
`[locked, dev, dev, val, locked, dev]` over the group-ordered,
shuffled-within-group family list), fixed at design time, independent of any
outcome:

- **development:** 11 families (374 scenarios) — pre-lock diagnostics, variance
  estimation, all debugging.
- **validation:** 4 families (136 scenarios) — allowed for methodology sanity
  checks, sparingly.
- **locked test:** **12 families, 408 scenarios**
  (`asymmetric_risk`, `capacity_bound`, `delayed_price`, `demand_saturation`,
  `noisy_observations`, `nonlinear_response`, `price_elastic`,
  `promotion_threshold`, `regime_shift`, `strong_seasonality`, `weak_marketing`,
  `weak_seasonality`), `locked_test_family_checksum` and the 408
  `locked_scenario_ids` in `config.json`. **Not touched for any purpose until
  `freeze-prereg`.** The locked partition is deliberately large (12 of 27
  families) — sized from the development-stage variance so the planned power at
  MEI = 0.05 clears 0.80 (§9); the ratio is fixed by the *variance magnitude*
  only, and every family is placed by the deterministic stratified rule, never
  by its outcome.

## 7. Seeds (Section 13)

Exactly **10** seeds per locked scenario (`20260906 … 20260915`); each drives an
independent `r1.scenario_families.realise_history` (per-seed log-normal noise +
independent random walks). Seeds are stochastic replicates, **not** independent
structural scenarios. The **primary inferential unit is the scenario** (10 seeds
aggregated to the scenario mean before the paired tests). A seed-level
sensitivity analysis is reported alongside.

## 8. Conditions and baselines

`A` Prediction only (scored as `ground_truth._noop_action`) · `B` + Decision
Simulation (`r1_dt`) · `C` + single agent · `D` full system
(`decision_service.analyze_goal`, default `PipelineOptions` = R0/D0). Definitions
unchanged from V1/V2. `naive` / `greedy` / `oracle` / `classical_optimizer` are
**external computational benchmarks** with documented information advantages
(`docs/R1_INFORMATION_BOUNDARY.md`); outperforming them proves nothing about
production usefulness. Identical-feasible-action-space invariant verified per
instance.

## 9. Power analysis (Section 12) — **COMPLETED from development-stage variance only**

Simulation-based (`app.evaluation.stats.simulate_power`, 20 000 Monte-Carlo
draws, `rng_seed = 20260907`) from `experiments/r1/power_assumptions.json`.
Variance components come **only** from the R1 development-stage pilot
(`prelock_diagnostics.json`: `D_vs_B` scenario-level SD **0.282**, within-scenario
seed SD **0.180**, over 45 development/validation scenarios × 4 seeds).
Locked-test outcomes are **not** used. Assumptions, frozen before the locked run:

| assumption | value | basis |
|---|---|---|
| `primary_comparison` | `D_vs_B` | the confirmatory question |
| `min_effect_of_interest` | **0.05** | 5 % of the oracle-to-worst-feasible span — the smallest incremental change worth attributing to the downstream stack; a substantive choice, **not** raised or lowered to hit a power target |
| `alpha` | 0.05 two-sided | |
| `target_power` | **0.80** (Section-12 floor; ≥ 0.90 aspiration) | |
| `n_scenarios` (locked) | **408** | 12 locked families × 34 |
| `n_seeds` | **10** | §7 |
| `metric_sd_between_scenarios` | **0.30** | pilot 0.282 **rounded up** (conservative) |
| `within_scenario_seed_sd` | **0.18** | pilot value |

**Result (`power_analysis.json`): `estimated_power = 0.894` ≥ 0.80.**
`assumed_effective_sd = 0.305`. The locked N of 408 was set *from* this analysis
(an earlier 126-scenario draft would have given ≈ 0.40 — reported honestly,
N was raised, **not** the effect of interest lowered).

**Stated limitation.** `simulate_power` does not model exact ties; the dev pilot
shows ≈ 31 % exact `D = B` ties, so the *achieved* power is somewhat below 0.894
(estimated ≈ 0.82–0.86). The report will state `n_nonzero` and the observed tie
rate, and a non-significant `D_vs_B` is reported as *"no statistically
significant incremental improvement was detected"*, never as equivalence.

## 10. Primary statistical analysis (Section 14)

Unit = **scenario** (10 seeds → scenario mean first). For each pre-registered
contrast:

- n, **mean** and **median** paired difference, SD, wins / ties / losses,
  `n_nonzero`;
- **paired Wilcoxon signed-rank** (exact for `n_nonzero ≤ 25`, normal approx
  otherwise; "not assessed" if `< 2` non-zero); exact zero-difference handling
  via `zero_method="wilcox"`;
- **matched-pairs rank-biserial** correlation (Kerby estimator) — the **primary
  effect size**; the p-derived `|Z|/√N` is **not** used as an effect size;
- **paired scenario cluster bootstrap** 95 % interval of the mean difference
  (10 000 resamples, seed 12345) — the primary interval; Student-t interval as a
  secondary reference;
- **Holm–Bonferroni** across the confirmatory family
  `{B_vs_A, C_vs_B, D_vs_C, D_vs_B}`; raw and adjusted p both reported.
  Reference/benchmark contrasts are descriptive and excluded from the correction.

## 11. Secondary comparisons (Section 15)

`A/B/C/D vs oracle`; `B_vs_A`, `C_vs_B`, `D_vs_C`, `D_vs_B`, `D_vs_A`;
`D vs naive`, `D vs greedy`, `D vs classical_optimizer`. Information advantages of
the analytical benchmarks are stated with every mention.

## 12. Success criterion for a positive `D_vs_B` (Section 16) — all 8 required

1. D has **lower** mean normalised regret than B (`mean(D−B) < 0`).
2. `|mean(D−B)|` ≥ the pre-registered MEI (**0.05**) — practically meaningful.
3. The 95 % cluster-bootstrap CI for `mean(D−B)` **excludes 0** in the favourable
   direction.
4. Wilcoxon survives **Holm** correction (`p_holm < 0.05`).
5. The effect is **not driven by a single family**: it holds (same sign,
   `|mean| ≥ 0.5·MEI`) with **any one locked family removed** (leave-one-family-out).
6. The effect **survives the pre-registered robustness perturbations** (§14):
   sign preserved on ≥ 7 of the 10 perturbations.
7. The **mechanism analysis** (§15) yields a plausible, pre-registered
   explanation (e.g. the agent layer reduces the DT-vs-ground-truth action
   discrepancy in identifiable regimes).
8. **No post-hoc exclusion** is required to obtain it.

**Classification (pre-registered):**
- **supported** — all 8 hold.
- **promising** — 1–2 of {3, 4, 5, 6} fail but sign + magnitude hold.
- **null / inconclusive** — CI includes 0 or `|mean(D−B)| < MEI`.
- **negative** — `mean(D−B) > 0` with CI excluding 0 (D **worse** than B).

A null or negative result is reported as such and is an acceptable scientific
outcome. "supported" is never relabelled from a weaker class.

## 13. Sensitivity analyses (pre-registered)

- Repeat the primary `D_vs_B` analysis **excluding all `r1_dt` fallback
  instances** (OLS-only elasticity).
- Repeat with `r1_dt` fallback source switched off entirely (drop instances
  needing it).
- Seed-level analysis: per-seed `D−B` distribution; ICC / design effect.
- Leave-one-family-out (feeds criterion 5).

## 14. Robustness perturbations (Section 17 — frozen before the locked run)

The 10-perturbation V1 suite (`app.evaluation.perturbations`, unchanged):
`input_noise`, `forecast_error_bias`, `missing_values`, `uncertainty_inflation`,
`constraint_tighten`, `constraint_relax`, `distribution_shift`,
`contradictory_signals`, `extreme_but_feasible`, `adversarial`. On a
deterministic locked-test subsample (`sorted(locked)[::k]`) × 2 seeds × low/high
severity. For each: effect direction, magnitude, bootstrap CI, and **whether the
primary `D_vs_B` conclusion changes**. Descriptive; not in the confirmatory
family. DecisionGPT is **not** tuned to improve any of these.

## 15. Mechanism analysis (Section 18 — exploratory, associational, NOT causal)

For `D−B` (and `C−B`, `B−A`): action-change frequency; objective-value change;
risk-score change; agent disagreement; scenario uncertainty; constraint
pressure; scenario family; **DT-vs-ground-truth action discrepancy**
(`argmax_a r1_dt.revenue` vs `oracle`). OLS on standardised factors + scenario
cluster bootstrap + tertile buckets, plus per-family `D−B`. Effective cluster
count = number of locked families (9); factor-level claims are **not** made —
family-level description only. If the agent layer changes actions but does not
improve exogenous regret, that is reported explicitly.

## 16. Stopping rules (Section 23)

The locked test runs **once**, only after (a) this document is frozen with a
checksum and a recorded git commit, and (b) every critical item in
`docs/R1_PRELOCK_GATE.md` passes. Then: no tuning, no parameter change, no
scenario / seed / family removal, no re-run because results are unfavourable, no
sample-size expansion.

## 17. Interpretation prohibitions (Section 27)

No claim of production superiority, real-SME / Indian-SME validation, real-world
business improvement, ROI, customer improvement, causal business impact, or
deployment success — regardless of outcome. A positive R1 result is about **this
research-only corrected variant**, not the shipped product, and is not SME
validation. A negative R1 result is not proof that multi-agent systems never
work. The internal `goal_achievement` metric is never external validation.

## 18. Sign-off

- [ ] `docs/R1_DT_DIAGNOSTIC.md`, `docs/R1_INFORMATION_BOUNDARY.md`, this
  document — complete.
- [ ] Development-stage pilot variance recorded; §9 power completed;
  `estimated_power ≥ 0.90` (or the shortfall disclosed).
- [ ] `docs/R1_PRELOCK_GATE.md` — GO on every critical item.
- [ ] `config.prereg_frozen = true`; git commit + `checksums.txt` recorded.
- [ ] Date frozen: ______
