# R1 Results

**Status: COMPLETE (locked test run once; synthetic, controlled).**
Every number traces to `experiments/r1/{results.json, statistical_results.json,
mechanism_results.json, robustness_results.json, config.json}` and its SHA-256 in
`experiments/r1/checksums.txt`. No value is entered by hand. Machine integrity
audit: `experiments/r1/MACHINE_AUDIT.md` (26/26). Hostile scientific audit:
`docs/R1_AUDIT.md`.

R0/D0, R3, V1, and V2 are frozen and untouched (verified before and after — §18).
R1 is a **versioned research-only Decision-Simulation correction**, not the
production system, and is never real-SME / real-world / causal evidence.

**Independent recomputation.** Every headline statistic below was re-derived from
the raw `experiments/r1/results.json` with no reuse of the precomputed summaries
(`experiments/r1/independent_recheck.json`): **75/75 checks reproduce** — the
`D_vs_B` mean/median/CI/Wilcoxon/Holm/rank-biserial/W-T-L, all four confirmatory
contrasts, every secondary contrast, the A/B/C/D + baseline ladder,
leave-one-family-out, the internal metric, the mechanism counts, the 12
family-level effects, and the 18 robustness cells.

---

## 1. Objective

Central question: *When the Decision-Simulation environment can respond
meaningfully to decision-relevant price/marketing variables, does adding the
existing downstream decision-support components (agents + risk + optimisation)
improve exogenous decision quality?*

Primary contrast: **`D_vs_B` = regret(D) − regret(B)**, lower regret better, so
**negative = D improves over B**, zero = no difference, **positive = D worse
than B**. Conditions: A = prediction only · B = prediction + Decision Simulation
· C = B + single agent · D = full system.

## 2. Experimental design

Pre-registered (`docs/R1_PREREGISTRATION.md`, frozen 2026-09-06 at git commit
`22ce18c965b61641f3dd28cc35e0cfac22f61dca`, doc SHA
`d111db68e130269a7fc5fa995c3560504499cba59ed5e1aec450bd68b4860cd8`). Unit of
analysis = **scenario** (10 seeds aggregated to the scenario mean before the
paired tests). Confirmatory family `{B_vs_A, C_vs_B, D_vs_C, D_vs_B}` with
Holm–Bonferroni. Primary effect size = matched-pairs rank-biserial (Kerby).
Primary interval = paired **scenario** cluster bootstrap (10 000 resamples, seed
12345, percentile). MEI = 0.05, α = 0.05 two-sided, planned power **0.894**
(`power_analysis.json`, from development-stage variance only).

## 3. R1 research-only Decision-Simulation correction

`backend/app/evaluation/r1/r1_dt.py` (`r1_dt_constant_elasticity_v1`). It wraps
the **production** `digital_twin_service.simulate_strategy` and replaces **only**
the scenario-side `expected_units_sold` / `expected_revenue` / `expected_profit`:

```
u_a = u_base · clip((1+Δp/100)**ε̂ , 0, 5) · clip((1+Δm/100)**â , 0, 5) · fulfil_cap
```

`u_base` = the production baseline forecast (unchanged); `ε̂ ∈ [−4, −0.05]`,
`â ∈ [0, 1]` = OLS of `log(units) ~ log(price) + log(marketing_spend) + weekday`
over the business's own seeded history. `risk_score` / `risk_level` and every
other field come straight from production. Fallback to the scenario generator's
`a_elast` only when the history is unusable — **locked-run fallback rate: 0 %**
(all 4 080 instances used OLS; the pre-lock diagnostic measured ≈ 1.1 %). Diagnosis and
minimality: `docs/R1_DT_DIAGNOSTIC.md`. Production `digital_twin_service.py` is
byte-identical on disk; `r1_dt` is installed per-instance by `r1.harness` and
removed afterwards.

## 4. Information boundary

`docs/R1_INFORMATION_BOUNDARY.md`. A/B/C/D may use the seeded history, the goal,
the candidate set, and (B/C/D) the `ε̂/â` **estimated from that history**. No
condition receives the true scenario elasticity, the oracle action, the
objective value, future outcomes, or test labels. The exogenous scorer
(`ground_truth.exogenous_objective_v1` = "System B", additive-linear, unchanged
from V1, imports only stdlib + numpy + scipy) is applied **after** selection.
Machine-verified: `r1_dt.py` imports no `ground_truth` / `decision_service` /
`decision_architecture`; oracle exact on 408/408 locked scenarios; identical
feasible-action set on all 4 080 instances.

## 5. Scenario construction

`backend/app/evaluation/r1/scenario_families.py`
(`r1_eval_scenarios_v1`; the verified V2 System-A history engine). **27 distinct
structural families**, `master_seed = 20260907` (a fresh seed — the `20260906`
sizing draft was discarded so that no scenario observed during design/power
sizing could enter the locked partition), **34 scenarios per family, N = 918
unique scenarios**, `suite_checksum =
cd73f0d59aafa87c7b1502f24d2c737fc9d92e77f43280ee06fb43abfbba9afd`. Stratified
family-level holdout (fixed at design time from the variance magnitude only):
**development 11 families / validation 4 / locked test 12 families = 408
scenarios**. The pre-lock diagnostic touched development/validation only
(`prelock_diagnostics.json`, `locked_test_touched: false`; machine-verified).

## 6. Locked test

`run_eval_r1.py run --partition locked_test`, **executed once**: 408 scenarios ×
10 seeds = **4 080 scenario-seed evaluations, 0 harness errors, 0 exclusions**.
Architecture fingerprint at runtime `60ca9c9e…`, `PipelineOptions().label() ==
"full"` (R0/D0). Frozen experiment manifest `94aa419c…` re-verified after the
run.

## 7. Ground-truth validation

Independent enumeration reproduces the implemented oracle on **408/408** locked
scenarios (action key and value; 0 mismatches). `classical_optimizer` never
exceeds the oracle. No degenerate normalisation spans. Oracle regret = 0 by
construction on every valid locked scenario.

## 8. Power

Planned (design-stage): `estimated_power = 0.894` at MEI 0.05, conservative
between-scenario SD 0.30 (development pilot 0.282, rounded up), within-scenario
seed SD 0.18, N = 408, 10 seeds (`power_assumptions.json` → `power_analysis.json`).
Stated caveat: the simulation does not model exact ties; the locked `D_vs_B`
analysis has `n_nonzero = 373` of 408 (35 exact ties), so the achieved power for
the primary contrast is close to the planned value.

## 9. Primary result — `D_vs_B`

**`D_vs_B` mean = +0.0852** (D has **higher** regret ⇒ **D is worse than B**),
median +0.100, SD 0.365, 95 % cluster-bootstrap CI **[+0.0479, +0.1231]**
(excludes 0, entirely in the "D worse" region), Wilcoxon p = 5.4 × 10⁻¹⁰,
**Holm-adjusted p ≈ 0** (rejects), matched-pairs rank-biserial **−0.469**
(moderate; D worse on the majority of non-zero pairs), wins/ties/losses (D
better / tie / D worse) = **99 / 35 / 274** of 408 scenarios.

**Pre-registered classification: NEGATIVE.** `mean(D−B) > 0` with the CI
excluding 0 and `|mean| = 0.085 > MEI 0.05`; the direction is preserved with any
single locked family removed (§12). *The full downstream stack degrades
exogenous decision quality relative to the corrected Decision Simulation, by
≈ 0.085 normalised regret.*

## 10. Complete A/B/C/D and secondary comparisons

Mean normalised regret (lower better; `positioning`):

| oracle | classical_opt. | greedy | **C** | **B** | greedy? | **A** | **D** | naive |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.000 | 0.089 | 0.197 | **0.162** | **0.216** | | **0.259** | **0.301** | 0.367 |

Confirmatory family (Holm; negative = first better):

| contrast | mean Δ | 95 % cluster-boot CI | W/T/L (1st-better/tie/1st-worse) | n_nz | Wilcoxon p | Holm p | reject | rank-biserial | reading |
|---|---:|---|---|---:|---:|---:|:--:|---:|---|
| **B_vs_A** | **−0.0436** | [−0.0843, −0.0021] | 292/0/116 | 408 | 4.8e−9 | 1e−8 | yes | +0.431 | **B better than A** — Decision Simulation adds value over prediction-only |
| **C_vs_B** | −0.0540 | [−0.0881, −0.0204] | 141/100/167 | 308 | **0.609** | 0.609 | no | −0.084 | **null** — the single agent does not reliably change regret (mean pulled by a few large C-wins; median 0, W/T/L favour C-worse) |
| **D_vs_C** | **+0.1392** | [+0.1158, +0.1623] | 63/65/280 | 343 | 1.7e−31 | 0.0 | yes | −0.633 | **D much worse than C** — the risk-manager + optimiser layer is where most of the damage occurs |
| **D_vs_B** *(primary)* | **+0.0852** | [+0.0479, +0.1231] | 99/35/274 | 373 | 5.4e−10 | 0.0 | yes | −0.469 | **D worse than B — NEGATIVE** |

Secondary (descriptive; negative = first better):

| contrast | mean Δ | 95 % CI | reading |
|---|---:|---|---|
| `D_vs_A` | +0.0417 | [+0.0157, +0.0678] | D worse than prediction-only |
| `D_vs_naive` | −0.0662 | [−0.0948, −0.0373] | D better than the literal status quo |
| `D_vs_greedy` | +0.1036 | [+0.0789, +0.1287] | greedy (objective-gradient benchmark) beats D |
| `D_vs_classical_optimizer` | +0.2123 | [+0.1835, +0.2412] | classical optimiser (on the modelled objective) beats D |
| `A/B/C/D_vs_oracle` | +0.259 / +0.216 / +0.162 / **+0.301** | | D is the **furthest** condition from the oracle |

**Secondary internal metric** (`goal_achievement`, labelled, never external
validation): B = 0.496, D = 0.364 — DecisionGPT's own internal metric also shows
D worse than B.

## 11. Baseline comparison

`naive` (status quo `()`), `greedy` (±1 % finite-difference on the objective,
snapped), `oracle` (best feasible action under System B — upper-bound
reference), `classical_optimizer` (SLSQP on System B + projection). **greedy,
oracle and classical have analytic access to the System-B objective that
A/B/C/D structurally lack — this is a documented information advantage
(`docs/R1_INFORMATION_BOUNDARY.md`); they are external computational benchmarks,
not architecture competitors.** D beats `naive` (do-nothing) but loses to
`greedy` and `classical` and is far from the `oracle`. Beating a weak baseline
(naive) is not evidence of decision quality; losing to objective-aware
benchmarks bounds how much of D's 0.30 regret is "inherent difficulty" vs
"architecture" — most is architecture, since **B attains 0.216 on the same
problems with the same information**.

## 12. Family-level analysis (Section 22)

`statistical_results.json → family_level_D_vs_B`. Each locked family: **34
structural scenarios × 10 seeds**. `D−B` (negative = D better):

| family | n | mean D−B | median | 95 % boot CI | direction | W/T/L (D-better/tie/D-worse) | mean regret A/B/C/D |
|---|--:|--:|--:|---|---|---|---|
| `nonlinear_response` | 34 | **−0.726** | −0.782 | [−0.793, −0.651] | D better | 34/0/0 | 0.06 / 0.97 / 0.07 / 0.25 |
| `demand_saturation` | 34 | **−0.235** | −0.176 | [−0.347, −0.123] | D better | 23/0/11 | 0.19 / 0.47 / 0.14 / 0.23 |
| `promotion_threshold` | 34 | +0.039 | 0.000 | [+0.017, +0.069] | D worse | 0/18/16 | 0.25 / 0.00 / 0.00 / 0.04 |
| `strong_seasonality` | 34 | +0.074 | +0.117 | [−0.030, +0.173] | D worse | 14/1/19 | 0.24 / 0.27 / 0.28 / 0.34 |
| `price_elastic` | 34 | +0.138 | +0.060 | [+0.089, +0.195] | D worse | 0/7/27 | 0.26 / **0.00** / 0.01 / 0.14 |
| `regime_shift` | 34 | +0.158 | +0.069 | [+0.085, +0.239] | D worse | 9/2/23 | 0.23 / 0.15 / 0.14 / 0.31 |
| `noisy_observations` | 34 | +0.164 | +0.187 | [+0.055, +0.266] | D worse | 9/0/25 | 0.25 / 0.28 / 0.26 / 0.44 |
| `asymmetric_risk` | 34 | +0.189 | +0.286 | [+0.085, +0.278] | D worse | 4/0/30 | 0.56 / 0.16 / 0.38 / 0.35 |
| `delayed_price` | 34 | +0.217 | +0.140 | [+0.156, +0.285] | D worse | 1/1/32 | 0.24 / 0.05 / 0.06 / 0.27 |
| `weak_marketing` | 34 | +0.227 | +0.074 | [+0.133, +0.329] | D worse | 1/6/27 | 0.22 / 0.04 / 0.05 / 0.27 |
| `weak_seasonality` | 34 | +0.300 | +0.287 | [+0.195, +0.399] | D worse | 3/0/31 | 0.23 / 0.18 / 0.19 / 0.48 |
| `capacity_bound` | 34 | **+0.477** | +0.523 | [+0.422, +0.527] | D worse | 1/0/33 | 0.38 / **0.01** / 0.38 / 0.49 |

**Pattern.** On the **2 families where D beats B** (`nonlinear_response`,
`demand_saturation`), B has a *residual failure* — both are censored-demand
(capacity ceiling) + elastic families where the OLS `ε̂` from censored history is
biased mild, so B still over-raises price (B regret 0.97 / 0.47); D's
conservatism accidentally damps this. On the **10 families where D loses**, B is
at or near the optimum (`capacity_bound` B = 0.01, `price_elastic` B = 0.00,
`promotion_threshold` B = 0.00, `delayed_price` B = 0.05, `weak_marketing`
B = 0.04) and the downstream stack moves D **away** from B's good choice.

**Not driven by one family (criterion 5).** Leave-one-family-out `D_vs_B` mean:

| family removed | `D_vs_B` mean | family removed | `D_vs_B` mean |
|---|--:|---|--:|
| `nonlinear_response` (only D-favourable) | **+0.159** | `capacity_bound` (biggest D-hurt) | +0.050 |
| `demand_saturation` | +0.114 | `weak_seasonality` | +0.066 |
| `weak_marketing` | +0.072 | `asymmetric_risk` | +0.076 |
| every other family | +0.073 … +0.089 | | |

The NEGATIVE direction survives removing **any** single family; removing the one
family where D helps makes it markedly worse for D. Top-3 |effect| share of
Σ|effect| = 0.51.

## 13. Robustness

Pre-registered perturbation suite (`app.evaluation.perturbations`, unchanged):
`input_noise`, `forecast_error_bias`, `missing_values`, `uncertainty_inflation`,
`constraint_tighten`, `constraint_relax`, `distribution_shift`,
`contradictory_signals`, `extreme_but_feasible`, `adversarial`, on a
deterministic 30-scenario locked subsample (`sorted(locked)[::4]`) × 3 seeds ×
low/high severity — **1 620 runs, 0 errors**
(`experiments/r1/robustness_results.json`). The clean-subsample `D−B` is +0.182
(the every-4th subsample over-weights D-worse families relative to the full
locked mean +0.085).

**`primary_conclusion_changes = False`.** The sign of `D−B` (D worse than B) is
preserved on **every** perturbation × severity (18/18 cells, `sign_vs_clean =
same`). Subsample `D−B` ranges from **+0.046** (`input_noise` at 0.75 — the only
cell whose 95 % CI touches 0, point estimate still positive) to **+0.339**
(`adversarial` — D degrades *further* when the historical price range is
compressed, consistent with the mechanism finding that D worsens as the
projection error grows). No perturbation was added after the fact; DecisionGPT
was not tuned. **The NEGATIVE `D_vs_B` finding is robust to the pre-registered
perturbation suite.**

## 14. Mechanism analysis (exploratory, associational, NOT causal)

`mechanism_results.json`. Effective cluster count for factor claims = 12 locked
families; **no factor-level effect is asserted** — family-level description only.

- **D changed B's selected action on 2 336 / 4 080 instances (57 %). Of those
  changes: 763 improved regret, 1 573 worsened it — a 2.06 : 1 ratio against.**
  A changed action is **not** evidence of an improved decision (pre-registered);
  here the changes are, on balance, harmful.
- **B's action equals the oracle on 2 550 / 4 080 (62.5 %); D's action equals the
  oracle on 1 410 / 4 080 (34.6 %).** The downstream stack roughly **halves** the
  rate at which the true-optimal action is chosen. Per family the collapse is
  starkest where B is best: `capacity_bound` B = 0.94 → D = 0.04;
  `asymmetric_risk` B = 0.74 → D = 0.01; `price_elastic` B = 1.00 → D = 0.74;
  `weak_seasonality` B = 0.53 → D = 0.23.
- OLS of `D−B` on standardised scenario factors (bootstrap CIs excluding 0):
  `prediction_error` β = +0.171 [+0.136, +0.207] — D does relatively worse vs B
  where the DT-vs-ground-truth projection error is larger; `action_space_size`
  β = −0.179 [−0.249, −0.138] — D does relatively less-badly on the larger
  (8-candidate revenue) action sets. `agent_disagreement` β ≈ 0.
- `D_vs_C` (rank-biserial −0.633, mean +0.139) localises most of the degradation
  to the **risk-manager gate + optimiser** step, not the first agent.

## 15. Failure cases (Section 27 — objective selection rules)

- **Strongest D "wins"** (most negative `D−B`): the top 6 are all
  `nonlinear_response` (B regret ≈ 1.0 → D regret 0.02–0.10). D helps **only** by
  damping a residual B overshoot on this censored-demand + strong-elasticity
  family.
- **Strongest D losses** (most positive `D−B`): `weak_seasonality__0028`
  (B 0.04 → D 0.90), `weak_marketing__0017` (B 0.00 → D 0.84),
  `weak_seasonality__0012` (B 0.00 → D 0.80), `weak_marketing__0020`
  (B 0.00 → D 0.74), `delayed_price__0015` (B 0.04 → D 0.76) — D converts
  near-perfect B decisions into near-worst-case ones.
- **Highest absolute D regret**: `weak_seasonality`, `strong_seasonality`,
  `noisy_observations` instances (D regret 0.86–0.90).
- **Near-oracle D** (regret ≤ 0.02): 43 scenarios, spread across 6 families
  (`delayed_price`, `demand_saturation`, `price_elastic`, `promotion_threshold`,
  `regime_shift`, `weak_marketing`).
- **Systematic family failure**: `capacity_bound` — D worse than B on 33/34
  scenarios; B near-optimal (0.01), D 0.49.

## 16. Statistical interpretation

- The primary `D_vs_B` result is a **rejection** of "no difference" in the
  direction **D worse than B**: Holm p ≈ 0, cluster-bootstrap CI [+0.048,
  +0.123] excludes 0, `|mean| = 0.085 > MEI`, rank-biserial −0.469, robust to
  leave-one-family-out. Pre-registered class: **NEGATIVE**.
- `C_vs_B` is **null** (Holm p = 0.609). The negative *mean* with a CI excluding
  0 is a mean-vs-rank divergence (a few large C-wins on `nonlinear_response`
  pull the mean); the signed-rank test, the median (0.000), and W/T/L
  (141/100/167) show no consistent single-agent effect. It is **not** reported
  as a benefit.
- `B_vs_A` is **supported** in the direction **B better than A** — the corrected
  Decision Simulation genuinely adds value over prediction-only.
- The inferential unit is the **scenario** (n = 408); the 4 080 seed
  observations are stochastic replication, not 4 080 structural scenarios. The
  cluster bootstrap resamples scenarios.
- Effect size is the matched-pairs rank-biserial (estimator). No p-derived `r`
  is used as a primary effect size.

## 17. Limitations

- **Synthetic and controlled.** System A (log-linear history) and System B
  (additive-linear objective) are modelling choices; a different pair could
  shift magnitudes. No real data of any kind.
- **R1 is a research-only variant.** The result is about *this corrected
  Decision Simulation*, not the shipped `digital_twin_service`. It does **not**
  establish that the production system helps or hurts real decisions.
- **`r1_dt` is itself an information channel** (elasticity estimated from the
  business's own history). On censored-demand families (`capacity_bound`,
  `demand_saturation`, `nonlinear_response`, `inventory_bound`) the OLS `ε̂` is
  biased toward inelastic, so B has a residual failure mode there — the 2
  families where D "helps" are of this type. Fallback rate was 0 % on the locked
  run.
- **Effective cluster count = 12 families.** Mechanism factor coefficients are
  associational and not interpreted at the factor level.
- **A is a fixed minimal-magnitude policy** (`ground_truth._noop_action`), not a
  generic prediction-only policy; `D_vs_A` is secondary and `D_vs_naive` is the
  cleaner "vs doing nothing" contrast.
- Condition A/B/C/D vs the **objective-aware benchmarks** (greedy / classical /
  oracle) are difficulty yardsticks, not fair contests.
- The result does **not** establish real-world SME impact, ROI, causal business
  effect, or general superiority/inferiority of multi-agent systems.

## 18. Reproducibility

- Repo commit at prereg freeze: `22ce18c965b61641f3dd28cc35e0cfac22f61dca`.
  Python: CPython 3.12 (`backend/.venv`). Master seed 20260907. Bootstrap seed
  12345 (primary), 4242 (mechanism), 777 (family). Power `rng_seed` 20260907.
- Frozen artifacts: `scenario_manifest.json` (`suite_checksum cd73f0d5…`,
  `content_hash` per scenario), `power_assumptions.json`, `power_analysis.json`,
  `prelock_diagnostics.json`, `config.json` (`prereg` block with all component
  hashes), `results.json`, `results_locked_test.jsonl`,
  `statistical_results.json`, `mechanism_results.json`, `robustness_results.json`
  — SHA-256 of every file in `checksums.txt`.
- Commands:
  ```
  python scripts/run_eval_r1.py generate --n 918 --master-seed 20260907
  python scripts/run_eval_r1.py prelock-diagnose --per-family 3 --seeds 4 --include-validation
  python scripts/run_eval_r1.py power --assumptions experiments/r1/power_assumptions.json
  python scripts/run_eval_r1.py freeze-prereg --date 2026-09-06
  python scripts/run_eval_r1.py run --partition locked_test
  python scripts/run_eval_r1.py analyze
  python scripts/run_eval_r1.py robustness
  python scripts/run_eval_r1.py audit
  python scripts/r1_figures.py all
  python scripts/scan_r1_claims.py
  ```
- Frozen experiment manifest `94aa419c…` re-verified before and after; production
  / V1 / V2 / paper `git diff` empty (§ machine audit).

---

## Tables (Section 35 — every value traces to `experiments/r1/*.json`)

### Table 1 — R1 scenario-family design (27 families; 12 locked)

| # | family | mechanism | objective | partition |
|--:|---|---|---|---|
| 1 | `price_elastic` | strong negative price elasticity | revenue | **locked** |
| 2 | `price_inelastic` | weak price elasticity (price rise optimal) | revenue | development |
| 3 | `strong_marketing` | large marketing exponent | revenue | development |
| 4 | `weak_marketing` | marketing ~inert; price is the lever | revenue | **locked** |
| 5 | `asym_price_marketing` | inelastic to price, elastic to marketing | revenue | (dev/val) |
| 6 | `competing_objectives` | revenue-opt ≠ profit-opt | profit | (dev/val) |
| 7 | `asymmetric_risk` | inelastic + narrow price history | revenue | **locked** |
| 8 | `inventory_bound` | stock cap below demand | orders | development |
| 9 | `capacity_bound` | production cap near demand | profit | **locked** |
| 10 | `budget_bound` | marketing budget barely above status quo | revenue | development |
| 11 | `delayed_marketing` | System-B marketing effect partly in-horizon | revenue | development |
| 12 | `delayed_price` | slow demand decay after prior price moves | revenue | **locked** |
| 13 | `seasonal_demand` | moderate weekly seasonality | revenue | development |
| 14 | `strong_seasonality` | large weekly seasonal amplitude | revenue | **locked** |
| 15 | `weak_seasonality` | near-flat seasonality | revenue | **locked** |
| 16 | `conflicting_signals` | recent uptrend but strongly elastic | revenue | (dev/val) |
| 17 | `noisy_observations` | high obs noise + price jitter | revenue | **locked** |
| 18 | `missing_observations` | 25–45 % of days dropped | revenue | (dev/val) |
| 19 | `sparse_history` | 36–52 days of history | revenue | development |
| 20 | `demand_saturation` | capacity ceiling just above demand | revenue | **locked** |
| 21 | `diminishing_marketing` | very concave marketing response | revenue | (dev/val) |
| 22 | `promotion_threshold` | strongly elastic; deep cut optimal | revenue | **locked** |
| 23 | `high_uncertainty` | large log-normal noise + wide price walk | profit | (dev/val) |
| 24 | `low_uncertainty` | very small observation noise | revenue | development |
| 25 | `interacting_constraints` | inventory and cash both bind | orders | (dev/val) |
| 26 | `regime_shift` | mid-series structural break in demand | revenue | **locked** |
| 27 | `nonlinear_response` | strong elasticity + saturation ceiling | revenue | **locked** |

(Exact parameter ranges/distributions: `scenario_families.py` +
`scenario_manifest.json`. Full partition in `config.json → partitions`.)

### Table 2 — Primary result: `D_vs_B` (n = 408 scenarios, 10 seeds)

| quantity | value |
|---|---|
| mean paired difference `regret_D − regret_B` | **+0.0852** |
| median paired difference | +0.1000 |
| SD of paired differences | 0.3646 |
| 95 % scenario cluster-bootstrap CI (percentile, 10 000, seed 12345) | **[+0.0479, +0.1231]** |
| Student-t 95 % CI (secondary) | [+0.0498, +0.1207] |
| Wilcoxon signed-rank p (approx, n_nonzero 373) | 5.44 × 10⁻¹⁰ |
| Holm-adjusted p (family of 4) | ≈ 0 (< 1 × 10⁻⁸) |
| matched-pairs rank-biserial (primary effect size) | **−0.469** |
| wins / ties / losses (D better / tie / D worse) | **99 / 35 / 274** |
| leave-one-family-out range | +0.050 … +0.159 (always D worse) |
| pre-registered classification | **NEGATIVE** |

### Table 3 — A/B/C/D comparison

| contrast | mean Δ | 95 % CI | Holm p | reject | rank-biserial | direction |
|---|--:|---|--:|:--:|--:|---|
| `B_vs_A` | −0.0436 | [−0.084, −0.002] | 1 × 10⁻⁸ | yes | +0.431 | B better than A |
| `C_vs_B` | −0.0540 | [−0.088, −0.020] | 0.609 | no | −0.084 | null |
| `D_vs_C` | +0.1392 | [+0.116, +0.162] | ≈ 0 | yes | −0.633 | D worse than C |
| `D_vs_B` | +0.0852 | [+0.048, +0.123] | ≈ 0 | yes | −0.469 | **D worse than B** |
| `D_vs_A` | +0.0417 | [+0.016, +0.068] | (secondary) | — | — | D worse than A |

Mean normalised regret: **A 0.259 · B 0.216 · C 0.162 · D 0.301**.
Internal `goal_achievement` (labelled, not external): B 0.496 · D 0.364.

### Table 4 — Baseline comparison (external computational benchmarks)

| policy | mean normalised regret | `D_vs_·` mean | 95 % CI | information advantage over A/B/C/D |
|---|--:|--:|---|---|
| oracle | 0.000 | +0.301 | [+0.278, +0.324] | full System-B objective (reference) |
| classical_optimizer | 0.089 | +0.212 | [+0.184, +0.241] | SLSQP on the System-B closed form |
| greedy | 0.197 | +0.104 | [+0.079, +0.129] | ±1 % objective finite differences |
| **D** | **0.301** | — | — | none (history + estimated `ε̂` only) |
| naive (status quo) | 0.367 | −0.066 | [−0.095, −0.037] | none |

### Table 5 — Family-level `D−B` (see §12 for the full table with CIs)

12 locked families, 34 structural scenarios each. **D better on 2**
(`nonlinear_response` −0.726, `demand_saturation` −0.235 — both censored-demand,
B residual failure). **D worse on 10** (`capacity_bound` +0.477 …
`promotion_threshold` +0.039). Direction robust to leave-one-family-out.

### Table 6 — Robustness (30-scenario locked subsample × 3 seeds; clean subsample `D−B` = +0.182)

| perturbation | severity | mean `D−B` | Δ vs clean | 95 % boot CI | sign vs clean |
|---|--:|--:|--:|---|---|
| `input_noise` | 0.25 / 0.75 | +0.161 / **+0.046** | −0.021 / −0.136 | [.081,.242] / [−.018,.107] | same / same |
| `forecast_error_bias` | 0.25 / 0.5 | +0.174 / +0.158 | −0.008 / −0.024 | [.095,.253] / [.070,.242] | same / same |
| `missing_values` | 0.2 / 0.4 | +0.179 / +0.188 | −0.003 / +0.005 | [.095,.259] / [.105,.266] | same / same |
| `uncertainty_inflation` | 0.5 / 1.0 | +0.134 / +0.201 | −0.048 / +0.019 | [.061,.206] / [.125,.276] | same / same |
| `constraint_tighten` | 0.25 / 0.5 | +0.210 / +0.210 | +0.028 | [.129,.288] | same / same |
| `constraint_relax` | 0.25 / 0.5 | +0.210 / +0.210 | +0.028 | [.129,.288] | same / same |
| `distribution_shift` | 0.3 / 0.6 | +0.174 / +0.151 | −0.008 / −0.031 | [.096,.255] / [.069,.235] | same / same |
| `contradictory_signals` | 0.5 / 1.0 | +0.175 / +0.167 | −0.008 / −0.015 | [.089,.259] / [.068,.263] | same / same |
| `extreme_but_feasible` | 1.0 | +0.170 | −0.012 | [.075,.260] | same |
| `adversarial` | 1.0 | **+0.339** | +0.157 | [.223,.449] | same |

**`primary_conclusion_changes = False`** — D worse than B on all 18 cells.

### Table 7 — Mechanism analysis

| quantity | value |
|---|---|
| D changed B's action | 2 336 / 4 080 (57 %) |
| — of those, regret improved | 763 (33 %) |
| — of those, regret worsened | **1 573 (67 %)** |
| B action == oracle | 2 550 / 4 080 (62.5 %) |
| D action == oracle | 1 410 / 4 080 (34.6 %) |
| OLS `D−B ~ prediction_error` (standardised β) | +0.171, CI [+0.136, +0.207] |
| OLS `D−B ~ action_space_size` (standardised β) | −0.179, CI [−0.249, −0.138] |
| `D_vs_C` rank-biserial (degradation localised to risk+optimiser) | −0.633 |

*(Effective cluster count = 12 families; coefficients are associational,
not causal, not interpreted at the factor level.)*
