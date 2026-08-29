# Statistical Analysis

Methods used to aggregate the multi-scenario experiments
(`multi_scenario_service`). All computation is in `_summ()` and `_paired()`;
`scipy` / `numpy` do the arithmetic, nothing is hand-typed.

## Sample

- **Architecture comparison:** 12 scenarios × 5 seeds = **60 observations per
  architecture** (A, B, C, D).
- **Ablation:** 12 scenarios × 5 seeds = **60 observations per configuration**
  (A–F).
- Observations are **paired**: each `(scenario_id, seed)` is evaluated by
  every architecture / configuration on the identical generated business.

## Descriptive aggregation (`_summ`)

Per architecture/config and per metric (`goal_achievement`,
`risk_adjusted_score`, `confidence`, `latency_seconds`):

| Quantity | Definition |
|---|---|
| `mean` | sample mean |
| `median` | sample median |
| `std` | sample standard deviation, `ddof=1` (Bessel-corrected) |
| `min` / `max` | extremes across the 60 observations |
| `ci95` | **Student-t confidence interval on the mean**: `mean ± t_{0.975, n-1} · s / √n` (`scipy.stats.t.ppf`). Reported as `null` when `n ≤ 1`. |

The t-interval is a **confidence interval on the sample mean**, not a
tolerance interval and not a claim about the population of all SMEs. `n = 60`
per group; the scenarios are a *designed* set, not a random sample, so the
interval describes sampling variability **within this scenario suite only**.

`confidence` aggregates are computed **only over architectures/configs that
produce a confidence** — architectures A/B/C have no confidence concept, and
ablation config B (no Digital Twin) produces no decision. Those cells read
`n/a`.

## Paired comparison (`_paired`)

For the primary questions — **Full (D) vs Prediction only (A)** and
**Full (D) vs Prediction + Digital Twin (B)** (and, for the ablation,
**Full vs each of B–F**) — differences are taken per `(scenario_id, seed)`:
`d_i = full_i − other_i`.

Reported:

| Quantity | Definition |
|---|---|
| `mean_difference`, `median_difference`, `std_difference` | on the paired differences `d_i` |
| `mean_difference_ci95` | Student-t CI on the mean paired difference (`null` if all `d_i` equal) |
| `full_wins` / `ties` / `full_losses` | count of pairs with `d_i > 0` / `= 0` / `< 0` (tolerance `1e-9`) |
| `test` | **Wilcoxon signed-rank**, paired, two-sided (`scipy.stats.wilcoxon`, `zero_method="wilcox"`, no continuity correction) |
| `statistic`, `p_value` | as returned by scipy |
| `effect_size_r` | `|Z| / √N_nonzero`, with `Z = Φ⁻¹(p/2)` — a rank-biserial-style effect size; reported only when the test ran |
| `interpretation` | plain-language, significance claimed **only** when `p < 0.05` |

### When the test is *not* run

- **All paired differences are exactly zero** → `p_value = null`,
  interpretation: *"statistical significance not assessed (the test is
  undefined). Descriptive result: no difference on any scenario/seed."*
- scipy raises (degenerate input) → `p_value = null`, interpretation records
  the reason.

**No significance is ever manufactured.** If the data do not support a test,
the report says *"Statistical significance not assessed."*

## Robustness analysis

Per architecture (vs Full, on `goal_achievement`, paired):
`vs_full_wins` / `vs_full_ties` / `vs_full_losses`. Plus Full's own
distribution: `best`, `worst`, `median`, `std` across the 60 observations.

## Failure-mode analysis (correlational, not causal)

Observations where **Full DecisionGPT's `goal_achievement` is in the bottom
tercile** (or exactly 0) are listed with `scenario_id, seed, goal_objective,
selected_strategy, goal_achievement, risk_adjusted_score, confidence` and a
list of **associated factors** (low confidence < 0.20; non-positive
risk-adjusted score; goal KPI not directly simulated; a simpler architecture
did better on that pair). These are *associations*, explicitly **not** causes.

## KPI proxy note

`goal_achievement` is measured against the scenario's own primary KPI:
- `revenue` → `(expected_revenue − baseline_revenue) / baseline_revenue`
- `profit` → the profit pair
- `orders` → the units-sold pair
- `marketing_roi`, `inventory_risk` → **no simulated pair exists**, so
  **revenue attainment is used as a documented proxy**. Scenarios S04 and S07
  are the only ones affected; their `kpi_measured` field records `"revenue"`
  and the failure analysis flags `"goal KPI not directly simulated"`.

## Reproducibility of the statistics

`_summ` and `_paired` are pure functions of the stored `observations` array.
Given the same `experiments/experiment_manifest.json`, re-running the
aggregation yields identical numbers. A unit test
(`tests/unit/test_multi_scenario_service.py`) checks `_summ` against a
hand-computed mean/std/CI and checks that the same `(scenario, seed)`
reproduces the same generated business.
