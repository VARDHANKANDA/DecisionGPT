# R1 — Fair Information Boundary (Section 6)

Every system in the R1 evaluation and the exact information it may use. Frozen
before the R1 locked test. "System B" = the exogenous objective
(`app.evaluation.ground_truth`, unchanged from V1). "System A" = the history
generator (`scenario_families_v2._history_v2` engine, reused).

## Matrix

| System | Allowed inputs | Forbidden inputs | Objective (System B) access | Future information |
|---|---|---|---|---|
| **A — Prediction only** | the seeded business history (Sale / MarketingCampaign / InventoryRecord rows), the goal, the production candidate set | oracle action, System-B value, any candidate's realised outcome, test-set membership, post-hoc stats | **none** — scored *after* it "recommends nothing" (mapped to the smallest-magnitude candidate by `ground_truth._noop_action`) | none |
| **B — + Decision Simulation (`r1_dt`)** | same history; plus `r1_dt`'s per-instance OLS estimate `ε̂, â` of price/marketing elasticity **from that same history**; plus known fulfilment limits (current inventory from the DB; the scenario's `capacity_cap` constraint) | oracle action, System-B value/parameters, any candidate's realised System-B outcome, future demand, test labels | **none** — `r1_dt` computes `u_a = u_base·(p_a/p̄)^ε̂·(s_a/s̄)^â`; it never calls `ground_truth` and never sees `eps`/`mr`/`kappa` (the System-B parameters) or the objective value | none — `r1_dt` uses only the *historical* series; the horizon forecast holds price/marketing constant, exactly as production |
| **C — B + single agent** | everything B has, plus the one rule-based agent's score over the `r1_dt` projections | same as B | none | none |
| **D — Full system** | everything C has, plus the two remaining rule-based agents, the risk manager (production R0 extrapolation-overshoot, `risk_model=None`, `λ=1`), and the `strategy_optimizer` (formula `v2`) | same as B | none | none |
| **oracle** (reference) | the full System-B objective over the identical candidate set + no-op | — | **full** — by definition; it is the upper-bound reference, not a competitor | none (it evaluates the objective, not outcomes) |
| **naive** (benchmark) | the literal status-quo action `()` | — | none for *selection*; calls `ground_truth.evaluate` only to *report* its own value | none |
| **greedy** (benchmark) | first-order finite differences of System B at ±1 % per lever, snapped to the nearest feasible single-lever action | — | **local gradient of System B** — a documented information advantage; greedy is an *external computational benchmark*, not an architecture competitor | none |
| **classical_optimizer** (benchmark) | SLSQP on the closed-form System-B objective over continuous lever %s + the cash constraint, projected to the nearest feasible discrete action | — | **full System-B functional form** — documented advantage; benchmark only | none |

## The one R1-specific information channel — `ε̂, â`

`r1_dt` estimates the price elasticity `ε̂` and marketing exponent `â` by an OLS
regression of `log(units_t)` on `log(price_t)`, `log(marketing_spend_t)` and
weekday dummies over the **business's own seeded daily history** — i.e. the
`price` and `marketing_spend` columns the production forecasting model already
ingests but assigns ~2 % combined SHAP importance (`docs/R1_DT_DIAGNOSTIC.md`
§2). This is:

* **not** the System-B objective parameters (`eps`, `mr`, `kappa`) — those are
  drawn as *noisy monotone functions* of the System-A generating parameters, so
  even a perfect `ε̂` for the *historical* response is only an imperfect proxy
  for the *counterfactual* objective;
* **not** the oracle, the objective value, or any future outcome;
* a **genuine estimation with error** — median `|ε̂ − a_elast|` ≈ 0.1 on clean
  histories, materially larger on short / degraded ones.

## Fallback channel (logged, reported, sensitivity-analysed)

When the OLS is unusable — history < 20 usable rows, `SD(log price) < 0.01`,
rank-deficient, or `ε̂` outside `[−4, −0.05]` (wrong sign / implausible) —
`r1_dt` falls back to the frozen scenario generator's **System-A** parameters
`a_elast`, `a_mkt`. This is an explicit information advantage over what a real
decision-maker could estimate. It is:

* logged per instance (`r1_dt_method ∈ {ols, fallback_generator, fallback_default}`);
* reported in the pre-lock gate (fallback rate) and in `docs/R1_RESULTS.md`;
* handled by repeating the primary `D_vs_B` analysis **excluding all
  fallback instances** as a pre-registered sensitivity analysis.

`a_elast` (System A) ≠ `eps` (System B); the fallback still does not give any
system the objective or the optimum.

## What NO system receives

* the true optimal action,
* future realised outcomes / demand,
* hidden System-B objective values,
* test-set labels or partition membership,
* any post-hoc scenario statistic,
* a real LLM output (blocked),
* real SME data (none exists).

## Verification (pre-lock)

`scripts/run_eval_r1.py prelock-diagnose` checks, on development/validation only:
oracle exact vs independent enumeration; identical-action-space invariant on
every instance; `ground_truth` called only after selection (harness fairness
logic reused unchanged from V1, where it was audited). `docs/R1_PRELOCK_GATE.md`
records the results.
