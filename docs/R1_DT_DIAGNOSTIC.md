# R1 — Decision-Simulation (Digital-Twin) Diagnostic

**Phase: DIAGNOSTIC ONLY.** No R1 correction has been implemented and no R1
evaluation has been run. This document identifies the exact cause of condition
B's action degeneracy and proposes the minimal research-only correction, per the
task's Section 4 ("STOP after this diagnostic and present the proposed
correction").

All numbers here are reproducible from `experiments/r1/dt_diagnostic_probe.json`
(a read-only probe of the frozen production forecasting model) and from
`experiments/upgraded_controlled_v2/prelock_diagnostics.json` (the V2 pre-lock
run). Frozen checksums verified before starting: `experiment_manifest.json` =
`94aa419c703b1babb465975463b26e55255755a7687ecbecadb6db4c4c15cbff`; V1
`suite_checksum 2215a1bd…` / `results.json 804fbe91…` / status
`evaluation_complete`; V2 `suite_checksum d28d521f…` / status
`STOPPED_AT_PRELOCK_GATE` / `locked_test_run false`.

---

## 1. Exact source of B's action degeneracy

**Condition B selects `price_change=+10 %` on ~100 % of executions because the
production Digital-Twin's projected *units sold* is effectively constant in
price, so its projected *revenue* (= units × price) is a monotonically
increasing straight line in price, whose argmax over the candidate set is always
the largest price increase.**

Direct probe of the exact model the Digital Twin uses (`sales_forecast_xgboost
v1`, selected by lowest MAE among naive/linear/xgboost):

| scenario price | 50 | 70 | 90 | 100 | 110 | 130 | 150 |
|---|---:|---:|---:|---:|---:|---:|---:|
| model-projected units | 111.84 | 111.84 | 111.84 | 111.84 | 111.84 | 111.84 | 111.84 |
| ⇒ revenue = units × price | 5 592 | 7 829 | 10 066 | 11 184 | 12 303 | 14 540 | 16 776 |

**Range of projected units over a 3× price sweep (50 → 150): exactly 0.0.**
Marketing sweep (spend 100 → 8 000): projected units 111.96 → 111.84 → 112.41
(range 0.57 units, ≈ 0.5 %).

## 2. Exact code path causing it

1. `decision_service.analyze_goal` (condition D) → `decision_architecture_service._simulate_all_candidates`
   (line ~215) → for every candidate action calls
   `digital_twin_service.simulate_strategy(db, business_id, actions)`.
   The V1/V2 evaluation harness computes condition B/C the same way, via
   `harness._sim_all` → `digital_twin_service.simulate_strategy`.
2. `digital_twin_service.simulate_strategy`
   (`backend/app/analytics/digital_twin_service.py` lines 347–372):
   - `compute_scenario_inputs` (line 277) sets
     `scenario_price = baseline_price · (1 + price_pct/100)`,
     `scenario_marketing_spend = baseline_spend · (1 + marketing_pct/100)`.
   - `baseline_points = forecast_service.run_recursive_forecast(model, units_series, last_date, baseline_price, baseline_marketing_spend, …)`
   - `scenario_points = forecast_service.run_recursive_forecast(model, units_series, last_date, scenario_price, scenario_marketing_spend, …)`
   - **The two calls share the identical `units_series`** (the real history), so
     the recursive lag features (`lag_1`, `lag_7`, `rolling_mean_7`,
     `rolling_mean_28`) are *identical* between baseline and scenario at step 1;
     the **only** differing inputs are the `price` and `marketing_spend` feature
     columns (`forecast_service.build_feature_row`, line 131).
3. `forecast_service.run_recursive_forecast` (line 164):
   `predicted = model.predict(feature_row)` with `price` / `marketing_spend`
   held constant across the horizon. The model is
   `ml.features.forecasting_features` `FEATURE_COLUMNS =
   [lag_1, lag_7, rolling_mean_7, rolling_mean_28, day_of_week, is_weekend,
   month, price, marketing_spend, promotion_flag]`.
4. `simulate_strategy` line 446:
   `expected_revenue = round(scenario_units · scenario_price, 2)` and line 415
   `expected_profit = round(scenario_units · scenario_price − scenario_units · avg_cost, 2)`.
5. `decision_architecture_service` line 244:
   `name, best = max(candidates, key=lambda item: item[1].output.expected_revenue)` —
   the Decision-Simulation-preferred candidate is the argmax of projected
   revenue. With projected units flat, this is `argmax_a (baseline_units ·
   baseline_price · (1 + price_pct/100)) = argmax_a price_pct` = **the largest
   `price_change` in the candidate set** (`+10 %`).

**The degenerate step is `model.predict(feature_row)` being flat in the `price`
and `marketing_spend` columns**, combined with the `revenue = units × price`
identity at line 446.

### Why the model is flat in price (root cause, two compounding parts)

**(a) The forecasting model has ~no learned price/marketing sensitivity.**
`sales_forecast_xgboost` global SHAP importances (`metrics_json`):

| feature | SHAP importance | share |
|---|---:|---:|
| lag_7 | 25.08 | 27.9 % |
| rolling_mean_7 | 20.96 | 23.3 % |
| rolling_mean_28 | 13.47 | 15.0 % |
| lag_1 | 10.00 | 11.1 % |
| day_of_week | 9.24 | 10.3 % |
| month | 6.14 | 6.8 % |
| promotion_flag | 3.16 | 3.5 % |
| **marketing_spend** | **1.09** | **1.2 %** |
| **price** | **0.87** | **1.0 %** |
| is_weekend | 0.00 | 0.0 % |

**`price` + `marketing_spend` together carry 2.2 % of the model's explanatory
power; the autoregressive level (lags + rolling means) carries ~77 %.** The
model is an *autoregressive units-level* forecaster; it treats price and
marketing as near-noise.

**(b) Training-data distribution mismatch.** The platform training dataset
(`datasets/forecasting/sales_timeseries.csv`, 29 200 rows) has `price` mean
**1 430**, SD 688 (CV 0.48), min 270, max 2 463, and a **weakly *positive***
crude price–units association (log–log OLS slope **+0.178**; Pearson corr
**+0.10**) — i.e. in that data higher price co-occurs with *more* units (a
product-mix / premium-series confound). The evaluation seeds businesses with
per-business prices in a narrow band around 80–3 000; the XGBoost price splits
either never fire in that region (constant leaf) or, where they do, point the
*wrong way*. Result: `predict` is flat-to-slightly-increasing in price.

**Net:** for every scenario, `projected_units ≈ constant`,
`projected_revenue ≈ constant × price` ⇒ argmax = max price increase ⇒
**B ≡ "raise price to the candidate-set ceiling."**

## 3. Mathematical description of the current DT objective

For a business with recent daily history `H = {(units_t, price_t, spend_t)}`,
baseline price `p̄ = price_last`, baseline spend `s̄` (recent mean), and a
candidate action `a` with lever deltas `(Δp %, Δm %, Δi %)`:

```
p_a       = p̄ · (1 + Δp/100)
s_a       = s̄ · (1 + Δm/100)
u_base    = Σ_{h=1..H_days}  M( lag/rolling(units), dow, month, p̄, s̄ )      # recursive
u_a       = Σ_{h=1..H_days}  M( lag/rolling(units), dow, month, p_a, s_a )    # recursive, SAME lag seed
revenue_a = u_a · p_a
profit_a  = u_a · p_a − u_a · c̄                                              # c̄ = avg unit cost
risk_a    = clip( max_feature ( overshoot of {p_a, s_a} beyond [min,max] of H ) , 0, 1 )   # R0, unchanged
```

where `M(·)` is the trained forecasting model (`sales_forecast_xgboost`).
Empirically `∂u_a/∂p_a ≈ 0` and `∂u_a/∂s_a ≈ 0` over the evaluated range, so
`revenue_a ≈ u_base · p̄ · (1 + Δp/100)` and
`argmax_a revenue_a = argmax_a Δp`.

The **downstream** components (`strategy_optimizer` formula `v2`
`s = (BA + FA)/2 − λ(1 − RM)`, λ = 1; the three rule-based agents; the risk
manager) all consume `u_a, revenue_a, profit_a, risk_a` and are **not** the
source of the degeneracy — they inherit a demand model that does not respond to
the decision.

## 4. Evidence from V2 supporting the diagnosis

`experiments/upgraded_controlled_v2/prelock_diagnostics.json` (272 real-pipeline
executions on the V2 action-responsive environment, where the true elasticity is
recoverable from the seeded history with median OLS error **0.097**):

- **Unique B actions across 272 executions: 2** — `price_change=+10` on every
  one of the 15 non-inventory families (16/16 each), `inventory_change=+20` on
  the inventory family.
- **`corr(true a_elast, B's chosen price-move %) = 0.031`** — no relationship.
- B's per-family regret spans **0.0** (families where "+10 % price" is optimal)
  to **1.0** (elastic families where it is exactly wrong), purely by coincidence
  with the family's true optimum.
- Direct `simulate_strategy` probe on V2 scenarios: projected revenue
  monotonically increasing in price for `inelastic_demand` (a_elast −0.51,
  correct), `low_volatility` (a_elast −1.77, **wrong**), and
  `promotion_decision` (a_elast −2.48, **wrong**).

V2 established that the degeneracy is **architectural** (the production Digital
Twin), not environmental — the environment carried a learnable signal and B
ignored it.

## 5. Minimal correction proposed — `r1_dt`

**Change exactly one thing: the scenario-side demand response.** Everything else
in `simulate_strategy` and everything downstream is untouched.

`r1_dt` wraps the production `digital_twin_service.simulate_strategy`
(research-only, injected at test time by `backend/app/evaluation/r1/harness.py`;
**production files unchanged**). It:

1. calls the **real** `simulate_strategy` to obtain the baseline forecast
   `u_base`, `baseline_revenue`, `baseline_profit`, `risk_score`, `risk_level`,
   the model name/version, and every other field — **all unchanged**;
2. estimates a **price elasticity `ε̂` and a marketing-response exponent `â`**
   from the business's *own seeded history* by an ordinary least-squares
   regression of `log(units_t)` on `log(price_t)` and `log(spend_t)` (plus a
   day-of-week / seasonal control) — i.e. it *uses the price and marketing
   columns the production model reads but does not learn from*. This is a
   genuine estimation with error; on the V2 environment it recovers the true
   elasticity with median error ≈ 0.10 and is materially noisier on short /
   degraded histories;
3. replaces **only** the scenario-side quantities with a structural
   constant-elasticity adjustment applied to the production baseline level:

   ```
   price_effect(r ; ε̂)      = clip( r ** ε̂ , 0 , 5 )                      # r = p_a / p̄ ,  ε̂ < 0
   marketing_effect(m ; â)   = clip( m ** â , 0 , 5 )                      # m = s_a / s̄ ,  â ≥ 0, diminishing
   u_a^{R1}      = u_base · price_effect · marketing_effect · fulfil_cap    # fulfil_cap from existing inventory/capacity logic
   revenue_a^{R1}= u_a^{R1} · p_a
   profit_a^{R1} = u_a^{R1} · (p_a − c̄)
   ```
4. leaves `risk_score` / `risk_level` **exactly as production computed them**
   (R0 extrapolation-overshoot, `risk_model=None`, `risk_penalty_lambda=1.0`).

**Fallback (documented, used only if step 2's estimate is unusable):** if the
regression is rank-deficient or `|ε̂|` is implausible (history too short /
censored), `r1_dt` falls back to a **scenario-provided `demand_hint`** carrying
the *System-A* generating parameters `a_elast`, `a_mkt` (not the System-B
objective parameters, not the oracle, not the objective value). This is an
explicit information advantage and is logged per instance; the pre-lock gate
reports how often the fallback fires and the primary analysis will report
results with and without fallback instances.

**`ε̂` / `â` / all `price_effect` / `marketing_effect` coefficients are estimated
per instance from data or taken from the frozen scenario generator — none are
hand-tuned, and none are chosen to favour any condition.**

## 6. Why the correction does not redesign the architecture

| Component | R1 change? |
|---|---|
| Candidate action generation (`strategy_generation_service`) | **none** — same candidate set |
| Agents (`business_analyst`, `financial_advisor`, `risk_manager`) | **none** — same rule-based code, same interfaces |
| Optimizer (`strategy_optimizer`, formula `v2`, λ = 1) | **none** |
| Risk manager / `_risk_from_extrapolation` (R0) | **none** — R1 keeps production risk verbatim |
| `decision_service.analyze_goal` / `decision_architecture_service` control flow | **none** — condition D still calls it with default `PipelineOptions` (R0/D0) |
| A/B/C/D definitions | **none** |
| Exogenous objective (`ground_truth.py`, System B) | **none** — reused byte-identical |
| Forecasting model, `run_recursive_forecast`, `build_feature_row` | **none** — still used for the *baseline level* |
| **Scenario-side demand/revenue/profit numbers only** | **the single change**: a per-instance data-estimated constant-elasticity adjustment |

R1 does not add or remove an agent, does not touch the optimizer or risk
formula, does not change the candidate space, and does not change the pipeline's
control flow. It makes the one function that is supposed to model "how does
demand respond to this decision?" actually do so, using information the pipeline
already ingests.

## 7. Historical artifacts that remain untouched

- Production: `backend/app/analytics/digital_twin_service.py`,
  `backend/app/analytics/forecast_service.py`, `backend/app/services/*`,
  `backend/app/agents/*`, `backend/app/decision_engine/*` — **byte-for-byte
  frozen**. R1's DT variant lives only in `backend/app/evaluation/r1/` and is
  injected at test time.
- `experiments/experiment_manifest.json` (`94aa419c…`),
  `experiments/paper_results_snapshot.json`, `experiments/results/*` — untouched.
- `experiments/upgraded_controlled_v1/` — all V1 results, pre-registration,
  config, checksums untouched; V1 stays `evaluation_complete`.
- `experiments/upgraded_controlled_v2/` — stays `STOPPED_AT_PRELOCK_GATE`,
  `locked_test_run: false`; the V2 locked test is **not** run retroactively.
- `docs/PAPER_DRAFT.md`, `docs/ieee_paper/` — untouched.
- R0/D0: `risk_model=None`, `risk_penalty_lambda=1.0`, `label()=='full'` —
  unchanged; R3 not promoted; real LLM blocked; no real SME data.

## 8. Parameters fixed before evaluation (frozen in `docs/R1_PREREGISTRATION.md`)

- `r1_dt` functional form: constant-elasticity `price_effect = r**ε̂`,
  `marketing_effect = m**â`; the estimation procedure (OLS of log-units on
  log-price + log-spend + seasonal control over the seeded history); the
  fallback trigger conditions and the fallback source (`a_elast`, `a_mkt`).
- Scenario families (≥ 24), parameter ranges, distributions, `master_seed`,
  per-family count, total N, development / validation / locked split, locked
  family IDs, locked scenario IDs, 10 seeds.
- Primary comparison `D_vs_B`; primary endpoint = paired difference in
  normalised regret; success criterion (Section 16, all 8 conditions);
  statistical plan (scenario as unit, Wilcoxon, matched-pairs rank-biserial as
  the primary effect size, scenario cluster bootstrap CI, Holm over
  `{B_vs_A, C_vs_B, D_vs_C, D_vs_B}`); power target ≥ 0.80 from
  development-stage variance only.
- Pre-registered robustness perturbations and mechanism factors.
- Interpretation labels (`supported` / `promising` / `null` / `negative`).

Nothing that can affect the primary outcome is decided after the locked test is
generated.

## 9. Threats to validity introduced by the correction

| # | Threat | Mitigation / disclosure |
|---|---|---|
| T1 | `r1_dt` gives B (and C, D) a demand model that *does* respond to price/marketing — arguably a more capable Decision Simulation than production, so a positive `D_vs_B` would be about *this variant*, not the shipped product. | Stated everywhere: R1 is a **research-only variant**; results are "in a research-only corrected Decision-Simulation environment", never "the production system". |
| T2 | The constant-elasticity form `r**ε` is itself a modelling choice and is *closer in spirit* to the System-A generator than the production model is. | System B (the scorer) is **additive-linear**, a *different* form from both System A (log-linear) and `r1_dt` (constant-elasticity on the production baseline). The DT still estimates `ε̂` from noisy data and is graded against a different functional form — the estimation gap is preserved and measured. |
| T3 | Estimating `ε̂` from the seeded history is an information channel the production DT does not exploit; on short/degraded histories `ε̂` is noisy and the fallback uses generator parameters. | The information boundary is documented (`docs/R1_INFORMATION_BOUNDARY.md`); fallback frequency and per-instance `ε̂` error are reported; the primary analysis is repeated excluding fallback instances. |
| T4 | If `r1_dt` makes B *near-optimal* by itself, `D_vs_B` has little headroom and a null is uninformative ("ceiling effect"). | The pre-lock gate reports B's regret distribution and the oracle gap on development; if B is already near-oracle everywhere, that is disclosed as a limitation and the families are (pre-lock) checked for genuine trade-offs. |
| T5 | `r1_dt` is injected by monkeypatching `digital_twin_service.simulate_strategy` within the R1 harness — a test-time global patch. | The patch is applied and removed within `r1/harness.run_instance`; a pre-lock check verifies production `simulate_strategy` behaviour is unchanged outside the patched context, and that R0/D0 (`label()`, λ, `risk_model`) is untouched. |
| T6 | Choosing to correct the DT at all is a researcher degree of freedom that could be seen as "fixing the system until it wins". | The correction is the *minimal* one (one function, data-estimated, no favourable hard-coding), is frozen before the locked run, and the task's success criterion requires practical magnitude + direction + multiplicity + no single-family dominance + robustness + mechanism — a null/negative R1 result is reported as such. |
| T7 | Only the demand *level* comes from the production model; its seasonality/autoregressive dynamics may interact oddly with the multiplicative `price_effect`. | `price_effect`/`marketing_effect` multiply the *summed horizon* baseline, not per-step; the pre-lock gate checks monotonicity and trade-off shape. |

---

## Proposed correction — summary for approval

> Implement `backend/app/evaluation/r1/r1_dt.py`: a research-only wrapper that
> keeps the production Digital Twin's baseline forecast, risk score, and every
> other field, and replaces **only** the scenario-side `expected_units_sold` /
> `expected_revenue` / `expected_profit` with a **per-instance,
> data-estimated constant-elasticity** response
> `u_a = u_base · (p_a/p̄)^ε̂ · (s_a/s̄)^â`, where `ε̂`, `â` are estimated by
> OLS from the business's own seeded history (fallback to the frozen scenario
> generator's `a_elast`/`a_mkt` when the history is too short/censored, logged
> and reported). Inject it at test time in `r1/harness.py` by patching
> `digital_twin_service.simulate_strategy`; production files unchanged; A/B/C/D,
> agents, optimizer, risk manager, candidate space, and the exogenous objective
> all unchanged.

**STOP per Section 4.** The next steps (only after this correction stands) are:
implement `r1_dt` + the ≥ 24-family R1 environment + `docs/R1_INFORMATION_BOUNDARY.md`
+ `docs/R1_PREREGISTRATION.md`, run the development-only pre-lock diagnostic, and
produce `docs/R1_PRELOCK_GATE.md`. **No R1 locked test is run until the gate
passes.**
