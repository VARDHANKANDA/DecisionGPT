# Upgraded Controlled Evaluation — V2 Report

**Status: STOPPED AT THE PRE-LOCK GATE. No V2 locked test was run.**

V2 built a corrected, **verified action-responsive** synthetic environment to
give condition B (the production Decision Simulation) genuine, learnable
information. The Phase-16 pre-lock diagnostic then showed that **condition B
remains a constant "+10 % price" policy even in that environment**, and that this
degeneracy originates in the **production Digital Twin**, not the synthetic
environment. Per the Phase-16 mandate the locked test was not run. This is the
V2 finding, and it is more informative than any locked-test number would have
been.

`upgraded_controlled_v1` remains frozen and valid for its environment. The two
studies are never pooled. Production architecture, the frozen 16-experiment
study, R0/D0, R3's status, and the IEEE paper are unchanged (verified,
`INTEGRITY_AUDIT_V2.md`).

---

## 1. Motivation from V1

The V1 independent audit (`docs/INDEPENDENT_SCIENTIFIC_AUDIT.md`) verified V1's
apparatus (metric independence, oracle, candidate/information fairness, exact
statistical reproduction, reproducibility) but found the **primary contrast could
not answer its question**: V1's history generator produced `units` independently
of the historical `price`/`marketing` series, so no action-response was
identifiable, and condition B (`argmax` of the Digital Twin's projected KPI over
the candidate set) collapsed to selecting `price_change=+10 %` on **100 % of the
800 V1 locked executions**. A `D_vs_B` comparison against a constant policy
cannot test "does the downstream pipeline add incremental value over a
*functioning* Decision Simulation."

## 2. The V1 limitation, precisely

V1 `_history` used only `base_price`, `base_demand`, `marketing_base_spend`;
never `price_elasticity`, `marketing_response`, `kappa`, `unit_cost`. The
historical data therefore contained **no identifiable price→demand or
marketing→demand relationship**. Whether this was the *cause* of B's degeneracy
(environment) or merely *coincident* with it (architecture) was unresolved by V1.

## 3. V2 design (full detail: `docs/UPGRADED_EVALUATION_V2_DESIGN.md`)

**What V2 changed:** one thing — a new **action-responsive** history generator,
`backend/app/evaluation/scenario_families_v2.py` ("System A"), plus 22
structurally distinct families, a stratified family-level holdout, per-seed
noise so seeds are genuine replicates, and a fresh (planned) power analysis.

**What V2 did NOT change:** the production architecture (R0/D0, condition
definitions A/B/C/D), the exogenous objective (`ground_truth.py` = "System B",
byte-identical to V1), `stats.py` / `perturbations.py` / `mechanism.py`, and the
harness fairness logic. The **only** shared-infrastructure change is one optional
keyword argument (`realise_history=`) on `harness.run_instance`; omitting it
reproduces V1 behaviour byte-identically (V1's eval tests and V1's 14/14
reproducibility audit still pass).

## 4. Synthetic environment — "System A"

```
price_t  = base_price · exp(mean-reverting log walk, band ≈ 12–45 %) · promo cycles
spend_t  = base_spend · exp(mean-reverting log walk)
demand_t = base_demand · (price_t/base_price)**a_elast · (spend_t/base_spend)**a_mkt
           · season_t · inv_avail_t · exp(N(0, sigma_obs))
units_t  = min(demand_t, capacity_cap, on_hand_t)
```

`a_elast` (historical elasticity, drawn per scenario) and `a_mkt` (marketing
exponent) are the parameters a system *can* learn from the V2 history. The
functional form is **log-linear/multiplicative**, deliberately distinct from
System B's **additive-linear** form. The System-B objective parameters are noisy
monotone functions of the System-A parameters (a parameter relationship, not
shared code).

**Verification that the environment is genuinely action-responsive** (Phase-16
check #2, independent of the pipeline): an OLS of `log(units)` on `log(price)`
and `log(spend)` over the *generated* history recovers the true `a_elast`:

| statistic | value |
|---|---|
| median \|recovered − true a_elast\| | **0.097** |
| mean \|recovered − true a_elast\| | 0.180 |
| median log-price SD over the history | **0.119** |

(V1 had near-zero price variation and no recoverable relationship.) Example
per-family recoveries: `inelastic_demand` true −0.51 → recovered −0.65;
`low_volatility` −1.77 → −1.67; `unit_elastic` −1.04 → −0.91; `low_data`
−1.25 → −1.30. The one poor case is `inventory_bound` (−1.59 → −0.42) because
demand is censored by the stock cap — expected and realistic.

## 5. Scenario families

22 regimes, 6 instances each, `master_seed = 20260906`, `suite_checksum
d28d521fa32509647dc6fd0aa8bd43a0b82ce131c92c74e14c32423d2b83e6f5`. Locked-test
partition (stratified, deterministic): `capacity_bound`, `conflicting_signals`,
`delayed_effects`, `low_marketing_response`, `seasonal_strong` — 5 families from
5 different structural super-groups. **The locked partition was never run.**

## 6. Ground truth

`backend/app/evaluation/ground_truth.py`, **unchanged from V1**
(`exogenous_objective_v1`). Re-verified independent (imports only
`math`, `dataclasses`, `typing`, `numpy`, `scipy.optimize`; no history use;
distinct additive-linear form). Oracle re-verified exactly correct on the
diagnostic set (0/68 mismatches vs independent enumeration).

## 7. A / B / C / D

Retained exactly from V1. Production `decision_service.analyze_goal` invoked with
no options (R0/D0) for D. Not redesigned.

## 8. Baselines

`naive` / `greedy` / `oracle` / `classical_optimizer`, retained from V1, labelled
**external computational benchmarks** (they call `ground_truth.evaluate`
directly; A/B/C/D cannot). Not run for V2 (no locked test).

## 9. Power

Not completed. The study stopped at the pre-lock gate before the power step.

## 10. Locked test

**Not run.** Phase-16 check #1 failed (§11). Per the pre-registration's stopping
rule, the locked test is run only after every pre-lock check passes.

## 11. Primary result — the pre-lock diagnostic (development + validation only)

`experiments/upgraded_controlled_v2/prelock_diagnostics.json`. 68 scenarios × 4
seeds = **272 real-pipeline executions, 0 errors**. Locked-test partition never
touched. Frozen manifest `94aa419c…` verified unchanged before and after.

### 11.1 Condition B is degenerate — even in the action-responsive environment

| Family (16 executions each) | B's selected action | | Family | B's selected action |
|---|---|---|---|---|
| elastic_demand | `price_change=+10` | | noisy_observations | `price_change=+10` |
| inelastic_demand | `price_change=+10` | | missing_observations | `price_change=+10` |
| unit_elastic | `price_change=+10` | | promotion_decision | `price_change=+10` |
| high_marketing_response | `price_change=+10` | | low_data | `price_change=+10` |
| low_volatility | `price_change=+10` | | competing_objectives | `price_change=+10` |
| high_volatility | `price_change=+10` | | thin_margin_profit | `price_change=+10` |
| cash_constrained | `price_change=+10` | | fat_margin_profit | `price_change=+10` |
| asymmetric_risk | `price_change=+10` | | supplier_shock | `price_change=+10` |
| | | | inventory_bound | `inventory_change=+20` |

- **Unique B actions across 272 executions: 2** (`price_change=+10`, and
  `inventory_change=+20` on the one family whose goal is inventory-risk).
- **Correlation between B's chosen price move and the true demand elasticity:
  0.03** — i.e. **none**. B raises price by 10 % whether demand is inelastic
  (`a_elast ≈ −0.4`) or strongly elastic (`a_elast ≈ −2.5`).
- B's per-family regret swings from **0.0** (`competing_objectives`,
  `thin_margin_profit`, `inventory_bound`, `supplier_shock` — where "raise
  price / max stock" is optimal) to **1.0** (`elastic_demand`, `low_volatility`,
  `missing_observations`, `promotion_decision` — where it is exactly wrong),
  purely as a function of whether "+10 % price" happens to match the true
  optimum. This is the identical pattern V1 exhibited.

### 11.2 Root cause — the production Digital Twin (directly probed)

Calling `digital_twin_service.simulate_strategy` on the candidate set for elastic
vs inelastic scenarios:

| scenario | true `a_elast` | DT-projected revenue: `p+10` → `p−10` | oracle |
|---|---:|---|---|
| `inelastic_demand` | −0.51 | 2.316M > 2.211M > … > 1.895M (monotone ↑ in price) | `price_change=+10` |
| `low_volatility` | **−1.77** (elastic) | 0.287M > 0.274M > … > 0.235M (**still monotone ↑ in price**) | `price_change=−10` |
| `promotion_decision` | **−2.48** (very elastic) | 0.368M > … > 0.301M (**still monotone ↑ in price**) | `price_change=−10` |

The Digital Twin's projected revenue is **monotonically increasing in price for
every scenario**. Its internal demand model behaves as though price elasticity is
≈ −0.1 regardless of the historical data (revenue ≈ price × near-fixed demand),
so the KPI argmax over the candidate set is **always the largest price increase**.
Marketing candidates project nearly identically to one another (the DT is
insensitive to the marketing lever beyond a threshold).

**Condition B ≡ "always select `price_change=+10 %`"** on the current production
architecture, invariant to the decision environment. This is a property of
`digital_twin_service` and cannot be changed in the evaluation layer without
modifying production Decision Simulation (forbidden).

### 11.3 Phase-16 gate

| check | verdict |
|---|---|
| 2. outcomes respond to actions | PASS (identifiable, median err 0.097) |
| 3. ground-truth independence | PASS |
| 4. oracle exactly correct | PASS (0/68) |
| 5. candidate-space identity | PASS (0 failures) |
| 6/7. no future / objective leakage | PASS |
| 9. families structurally distinct | PASS (22 regimes) |
| **1. B not trivially constant** | **FAIL — 2 unique actions; unavoidable without changing production** |

**→ STOP. The V2 locked test was not run.**

## 12. Secondary results

Not produced (no locked test). The pre-lock diagnostic did record C and D
behaviour on development/validation (C and D *do* vary across scenarios, unlike
B), but these are development-partition numbers and are **not** reported as
results — they informed only the gate decision.

## 13. Agent analysis

Not produced. (V1's agent analysis stands: the agent layer is active — FA/RM
score ranges 0.57 / 0.71 — but its net objective contribution over B was not
detected. V2 cannot improve on that because B is not a functioning baseline.)

## 14. Robustness

Not run (no locked test).

## 15. Mechanism analysis

Not run (no locked test).

## 16. Failure cases

Not applicable (no locked test). The pre-lock finding *is* the failure case:
condition B fails to use identifiable information on 100 % of instances.

## 17. V1 vs V2 — methodological comparison

| | **V1** | **V2** |
|---|---|---|
| Environment | history NOT action-responsive (`units` ⟂ `price`, `marketing`) | history **action-responsive**; elasticity recoverable from data (median OLS err 0.10) |
| Families | 17 (~6 structural regimes) | 22 (genuinely distinct regimes) |
| Locked partition | 4 families, 3 degraded/adversarial (blind draw) | 5 families from 5 super-groups (stratified) — **not run** |
| Seeds | A, B deterministic (0 replication) | per-seed noise ⇒ genuine replicates — **not exercised at lock** |
| Condition B behaviour | constant `price_change=+10` (100 % of 800) | constant `price_change=+10` (100 % of 272 dev) |
| B degeneracy attributable to | ambiguous (environment or architecture?) | **architecture** — the production Digital Twin, confirmed by direct probing |
| Primary `D_vs_B` result | null (Holm p = 1.0), underpowered, vs a constant B | **not obtained** — a clean `D_vs_B` cannot be constructed while B is degenerate |

**Is V2 a cleaner test?** V2 is a cleaner *environment* — verified
action-responsive and identifiable. But it revealed that the obstacle to a clean
`D_vs_B` is **not** the environment. So V2 does not yield a cleaner *primary
result*; it yields a cleaner *diagnosis*.

**Did B become informative?** **No.** With genuinely learnable elasticity in the
data, B still ignores it and picks `price_change=+10` everywhere.

**Did the `D_vs_B` conclusion change?** There is no V2 `D_vs_B` conclusion (not
run). The V1 `D_vs_B` null stands for V1; V2 explains *why* it is hard to
interpret — B is a constant policy by architecture.

**Does the V1 negative finding remain useful?** Yes, with the scoping the V1
audit already requires: on the V1 suite, adding the agent layer to the
digital-model baseline produced no detected improvement, and the full pipeline
underperformed simple references. V2 adds: this cannot be blamed on the V1
environment — the digital-model baseline itself is a constant policy on the
production architecture.

## 18. Limitations

- **No V2 locked-test result.** By design (Phase-16 stop).
- The pre-lock diagnostic is development/validation only (68 scenarios × 4
  seeds); it is a **gate**, not evidence for a claim.
- The Digital-Twin probe (§11.2) covers a handful of scenarios directly; the
  degeneracy is inferred to be general from the 272-execution B action
  distribution + the probe, not from an exhaustive DT characterisation.
- V2, like V1, is synthetic; System A is a modelling choice (log-linear power
  law); a different data-generating process could in principle interact
  differently with the Digital Twin (though the Twin's near-zero implied
  elasticity makes this unlikely to matter).
- "Condition B" here means the specific operationalisation *"argmax of the
  Digital Twin's projected KPI over the production candidate set."* A different
  B (e.g. one that fits its own elasticity) is not "the existing Decision
  Simulation."

## 19. External validity

**Zero**, unchanged. Synthetic only, by design and by hard constraint. Nothing
here supports real-SME effectiveness, Indian-SME validation, customer-behaviour,
ROI, deployment, or real-world causal claims.

## 20. Reproducibility

`generator_version = upgraded_eval_scenarios_v3`, `env_version =
system_A_action_responsive_v1`, `master_seed = 20260906`, `suite_checksum
d28d521f…`, per-instance `content_hash`. Pre-lock diagnostic seeds
`20260906–20260909`. All V2 artifacts under
`experiments/upgraded_controlled_v2/` with SHA-256 in `checksums.txt`. Frozen
experiment manifest `94aa419c…` re-verified. `INTEGRITY_AUDIT_V2.md` records the
machine checks. `scripts/run_eval_v2.py prelock-diagnose` reproduces the
diagnostic; `scripts/run_eval_v2.py generate` reproduces the suite.

## 21. Conclusions

1. **A corrected, verified action-responsive synthetic environment does not
   rescue condition B.** With demand elasticity recoverable from the data
   (median OLS error 0.10), condition B still selects `price_change=+10 %` on
   ~100 % of executions, uncorrelated with the true elasticity.
2. **The degeneracy of condition B is architectural, not environmental.** The
   production Digital Twin projects revenue as monotonically increasing in price
   for every scenario (implied elasticity ≈ −0.1), so "argmax of the Digital
   Twin's projected KPI" is a constant "+10 % price" policy.
3. **A controlled ablation of the form "does the downstream pipeline add value
   over Decision Simulation (B)?" is not constructible against the current
   production architecture** by changing the evaluation environment alone,
   because "Decision Simulation alone" is not a functioning optimiser in this
   action space. It would require modifying the production Digital Twin
   (forbidden) or redefining B (which would no longer be "the existing Decision
   Simulation").
4. **The V1 negative finding stands, re-scoped:** on the V1 suite the agent
   layer added no detected value over the digital-model baseline and the full
   pipeline lost to simple references; V2 establishes that the digital-model
   baseline is itself a degenerate constant policy on the production
   architecture, so the interesting comparison for a future study is
   **"D vs a competent action-selector"**, which requires either a production
   change or an explicitly non-production B.
5. **Recommended framing for the paper:** report V1 as the controlled
   negative-result / reproducibility contribution (with the audit's
   qualifications), and report V2 as a **diagnostic** result: *"we built a
   verified action-responsive environment and showed that the production Digital
   Twin's action ranking is invariant to identifiable demand elasticity,
   collapsing the Decision-Simulation condition to a constant policy; a clean
   incremental-value ablation of the downstream stack is therefore not possible
   without changing the production model."*
