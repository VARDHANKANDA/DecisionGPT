# Upgraded Controlled Evaluation — V2 Design

**Status: DESIGN (Phase 1).** This document is written *before* the V2 code and
*before* the V2 locked test. It explains why a V2 is needed, what V2 changes, and
— just as importantly — what V2 does **not** change.

`upgraded_controlled_v1` (`experiments/upgraded_controlled_v1/`,
`docs/UPGRADED_EVALUATION_REPORT.md`) is **frozen and remains valid for the V1
environment**. V2 is a **separate, independently versioned** evaluation
(`experiments/upgraded_controlled_v2/`). The two are never statistically pooled.

---

## 1. What the independent audit found wrong with V1

`docs/INDEPENDENT_SCIENTIFIC_AUDIT.md` verified that V1's *apparatus* is sound
(metric independence, oracle correctness, candidate-space and information-set
fairness, exact statistical reproduction, reproducibility, non-interference with
production and the frozen study). It also found that the *primary contrast could
not do the job it was built for*, for one root reason:

> **The V1 scenario history-generating process (`scenario_families._history`)
> produces `units` independently of the historical `price` and `marketing`
> series.** `_history` uses only `base_price`, `base_demand`,
> `marketing_base_spend`; it never references `price_elasticity`,
> `marketing_response`, `kappa`, or `unit_cost`. So the historical data that
> every condition ingests contains **no identifiable price→demand or
> marketing→demand relationship** (the only price/demand co-movement is a
> spurious artefact of a shared 10-day cycle).

### 1.1 Why B became a constant policy

Condition B = `argmax` over the feasible action set of the Digital Twin's
projected KPI. The production Digital Twin fits a response from the seeded
`Sale` / `MarketingCampaign` history. Given a history where demand does not move
with price, the Twin infers demand is price-insensitive and therefore projects
that raising price raises revenue/profit. Result (verified in `results.json`):

> **B selects `price_change=+10%` on 100 % of all 800 V1 locked executions** —
> the identical action on every instance of all four locked families.

B has no discriminating behaviour on the V1 locked set. Its per-family regret is
determined entirely by whether that family's *true* optimum happens to be "raise
price" (it is for `asymmetric_risk` and `competing_objectives`; it is the exact
opposite for `promotion_decision` and `missing_observations`).

### 1.2 Why this affects interpretation of D-vs-B

The primary question is *"does the downstream pipeline (Decision Simulation +
agents + risk + optimisation) add incremental objective value over Decision
Simulation alone?"* That question presupposes that **Decision Simulation alone
(B) is a functioning, information-using baseline.** In V1 it is not — it is a
constant "always +10 % price" policy. So the V1 `D_vs_B` null answers a narrower
question: *"does adding the agent layer change the outcome relative to a constant
raise-price policy, on a 2-vs-2 split of families?"* — not the intended one.

Secondary V1 issues the audit raised (all carried into V2's design):

| # | V1 issue | V2 response |
|---|---|---|
| 3 | `D_vs_B` doesn't cleanly test incremental value over a *functioning* B | action-responsive environment so B has real information (Phases 2–4) |
| 4 | Planned power used SD = 0.28; observed `D_vs_B` SD ≈ 0.51 | new power analysis from a **V2 development-stage pilot** variance estimate, conservative; N sized to that (Phase 7) |
| 5 | A is a hand-built smallest-magnitude policy | A retained unchanged **but demoted**: `D_vs_A` is *not* the main argument; `D_vs_naive` is the "vs doing nothing" contrast (Phases 9, 18) |
| 6 | oracle/greedy/classical have analytic objective access | retained, explicitly relabelled **external computational benchmarks**, not architecture competitors (Phase 10) |
| 7 | Only 4 structural regimes in the locked test | **≥ 20 structurally distinct families**; ≥ 5 in the locked partition (Phases 5–6) |
| 8 | Mechanism analysis has ~4 effective clusters | more regime diversity ⇒ more informative, but stays **exploratory / associational** (Phase 14) |
| 1–2 | B degenerate; history not action-responsive | the core V2 change (Phases 2–3) |

V1 is **not** being defended. The V1 negative result stands *for the V1
non-identifiable-response environment*; V2 asks whether a cleaner environment
changes the conclusion.

---

## 2. What V2 changes

### 2.1 A new action-responsive history-generating process ("System A")

`backend/app/evaluation/scenario_families_v2.py` (`GENERATOR_VERSION =
upgraded_eval_scenarios_v3`) replaces V1's `_history`. The V2 history is
generated so that **historical demand genuinely responds to historical price and
marketing**, and that response is **identifiable from the data** (the historical
price and spend series carry real, non-degenerate variation):

```
System A (history generator), per day t:
  price_t     = base_price · rw_price_t · promo_t                 # random walk + promo dips, real variance
  spend_t     = base_spend · rw_spend_t                           # random walk, real variance
  demand_t    = base_demand
                · (price_t / base_price) ** a_elast              # CONSTANT-ELASTICITY (power law) in price
                · (spend_t / base_spend) ** a_mkt                # power law in marketing
                · season_t                                       # multiplicative weekly seasonality
                · inv_avail_t                                     # in inventory/capacity families only
                · exp( N(0, sigma_obs) )                          # multiplicative log-normal noise (per seed)
  units_t     = min(demand_t, capacity_cap, on_hand_t)           # fulfilment ceiling where relevant
```

* `a_elast` (historical price elasticity, **negative**) and `a_mkt` (historical
  marketing response, **positive**) are drawn per scenario. They are the
  parameters a system *can* learn from the V2 history.
* The functional form is **multiplicative / log-linear**, deliberately **distinct
  from System B's additive-linear form** (§3).
* Per-seed `exp(N(0, sigma_obs))` noise means the realised history — and hence
  the Digital-Twin fit and B's argmax — **varies across seeds**, so seeds are
  genuine replicates for B as well as C/D (Phase 11).

### 2.2 System-A ↔ System-B coupling (so B has *useful but imperfect* information)

The exogenous objective's `price_elasticity` (`eps`, System B) is drawn as a
**noisy monotone function of `a_elast`** (System A), and `marketing_response`
(`mr`) / `kappa` likewise relate to `a_mkt`:

```
eps  = clip( a_elast + N(0, 0.35), -3.0, -0.15 )          # related, not equal
mr   = clip( f(a_mkt) · (1 + N(0, 0.25)), 0.2, 2.0 )
kappa= clip( 1 - 0.5·(a_mkt<median) + N(0, 0.1), 0.2, 1.0 )   # horizon-decay, family-dependent
```

Rationale: in a real business the *historical* data-generating process and the
*counterfactual outcome* process are related (same underlying market) but not
identical (regime drift, unmodelled factors, measurement). A system that
correctly recovers the historical elasticity therefore gets **informative but
imperfect** guidance about the true objective — which is exactly the regime in
which "does Decision Simulation's downstream stack add value?" is a meaningful
question. If `eps` were unrelated to `a_elast`, learning from history would be
useless and V2 would be no better than V1; if `eps == a_elast`, the environment
would be trivially solvable and circular.

### 2.3 ≥ 20 structurally distinct families

Each family corresponds to a genuine structural difference in **System A**
(elasticity regime, marketing-response regime, inventory/capacity/cash binding,
seasonality amplitude, observation degradation mode, delayed-effect decay,
conflicting-signal construction, competing-objective construction, volatility).
Family labels are not cosmetic: the parameter *ranges* differ, not just a noise
knob. Full list + ranges in the V2 pre-registration (Phase 15).

### 2.4 Fresh power analysis, fresh N, fresh pre-registration, fresh locked test

* Variance for the power simulation comes from a **V2 development-stage pilot**
  (development + validation scenarios only), clearly labelled *design-stage
  pilot information* and explicitly **not** locked-test outcomes.
* N (scenarios per family, seed count) is chosen to reach ≈ 0.80 planned power
  for the primary `D_vs_B` under the pilot variance — **not** chosen for
  significance.
* `docs/UPGRADED_EVALUATION_V2_PREREGISTRATION.md` is frozen with a checksum
  before the locked run; the locked test runs **once**.

### 2.5 Pre-lock non-degeneracy diagnostic (Phase 4 / 16)

Before freezing, on development/validation scenarios only, V2 measures B's
realised action distribution (unique actions, frequencies, by family, vs
scenario parameters). The goal is **not** to force a distribution — it is to
verify that the environment offers genuine variation B can respond to. If B is
still constant, that is **documented as a finding**; B is never artificially
perturbed and Decision Simulation is never modified.

---

## 3. Preventing circularity — System A vs System B (Phase 3)

There remain **two conceptually separate systems**:

| | **System A** — information environment | **System B** — exogenous evaluator |
|---|---|---|
| Role | generates the historical `Sale`/`Marketing`/`Inventory` rows DecisionGPT ingests | scores the *selected* action, once, after selection |
| Module | `scenario_families_v2.py` (`realise_history`) | `ground_truth.py` (`evaluate`), **unchanged from V1** |
| Demand form | multiplicative power law: `d0·(p/p0)^a_elast·(s/s0)^a_mkt·season·e^N(0,σ)` | additive linear: `d0·max(0, 1+eps·Δp/100) + mr·(Δs/1000)·kappa` |
| Parameters | `a_elast`, `a_mkt`, `sigma_obs`, `season_amp`, … (drawn per scenario) | `eps`, `mr`, `kappa`, `unit_cost`, caps (drawn per scenario, coupled to A's by noisy monotone maps §2.2) |
| Stochastic? | yes — per-seed log-normal noise, random-walk price/spend | no — deterministic in `(scenario, action)` |
| Sees the action? | no — history is generated before any action; the candidate actions are counterfactuals A/B/C/D choose among | yes — but only the *chosen* action, only after selection |

**Mathematically distinct, not the same formula twice:** a log-linear
multiplicative process (A) versus an additive linear process with an explicit
demand floor and separate marketing term (B). They agree only on domain
primitives (there is a price, a marketing spend, an elasticity sign, a capacity
ceiling). The coupling in §2.2 is a **noisy monotone relationship between
parameters**, not shared code or shared coefficients.

**The V2 ground-truth objective is byte-identical to V1's `ground_truth.py`** and
therefore continues to pass the V1 independence audit (static import scan +
poisoned-`sys.modules` runtime test). No new circularity surface is introduced.

**No future leakage:** the pipeline sees only the generated history; candidate
actions are counterfactuals; `evaluate()` is called only after selection. Same
guarantee as V1 (verified there by reading `harness.run_instance`).

---

## 4. What V2 does NOT change

* **Production architecture** — `decision_service`, `decision_architecture_service`,
  `digital_twin_service`, `app/agents/*`, `strategy_optimizer`,
  `strategy_generation_service`: untouched. R0/D0 defaults. Condition D calls
  `decision_service.analyze_goal` with **no `PipelineOptions`**.
* **The A/B/C/D definitions** — A = prediction only (scored as
  `ground_truth._noop_action`), B = + Decision Simulation, C = + single agent,
  D = full system. Identical to V1.
* **The exogenous objective** — `ground_truth.py` unchanged (System B).
* **`stats.py`, `perturbations.py`, `mechanism.py`** — reused unchanged
  (audit-blessed).
* **The harness fairness logic** — `harness.py` is reused. The **only** change is
  one optional keyword argument, `realise_history=`, on `run_instance`: when
  omitted, behaviour is **byte-identical to V1**; V2 passes
  `scenario_families_v2.realise_history`. No other line of `harness.py` changes.
  V1's eval unit tests and V1's 14/14 reproducibility audit still pass after this
  change (verified).
* **`upgraded_controlled_v1/`** — its results, pre-registration, config,
  checksums: not modified.
* **The frozen 16-experiment study** — `experiments/experiment_manifest.json`
  (SHA-256 `94aa419c…`), `paper_results_snapshot.json`, `experiments/results/*`:
  not modified.
* **`docs/PAPER_DRAFT.md`, `docs/ieee_paper/`** — not modified.
* **No real LLM, no real SME data.**
* **R3 stays PROMISING / NOT PROMOTED.**

---

## 5. V2 module & artifact layout

| Path | Role | New? |
|---|---|---|
| `backend/app/evaluation/scenario_families_v2.py` | System A generator, ≥ 20 families, `from_dict`, `suite_checksum`, family partition | **new** |
| `backend/app/evaluation/ground_truth.py` | System B objective + oracle + baselines | reused, unchanged |
| `backend/app/evaluation/harness.py` | per-instance runner | reused; +1 optional kwarg |
| `backend/app/evaluation/{stats,perturbations,mechanism}.py` | stats / robustness / mechanism | reused, unchanged |
| `scripts/run_eval_v2.py` | V2 CLI: `generate` / `split` / `prelock-diagnose` / `power` / `freeze-prereg` / `run` / `analyze` / `robustness` / `audit` | **new** |
| `scripts/scan_v2_claims.py` | forbidden-claim scan for V2 docs | **new** |
| `experiments/upgraded_controlled_v2/` | versioned outputs + checksums | **new** |
| `docs/UPGRADED_EVALUATION_V2_{DESIGN,PREREGISTRATION,REPORT}.md`, `docs/INDEPENDENT_SCIENTIFIC_AUDIT_V2.md` | V2 docs | **new** |
| `tests/unit/test_eval_v2_*.py` | V2 generator + System-A/B independence tests | **new** |

---

## 6. Success criteria for "V2 is a cleaner test"

1. **Action-responsiveness verified** (Phase 16): on development scenarios, the
   Digital Twin's projected KPI for a candidate action changes materially with
   the candidate (not flat), and B's realised action varies across scenarios and
   correlates with the scenario's `a_elast` / `a_mkt` in the expected direction.
2. **B non-degeneracy** (Phase 4): B selects ≥ 4 distinct actions across the
   development suite, with a family-conditional distribution that tracks the
   underlying regime. (If not met → documented, not forced.)
3. **Independence preserved** (Phase 20 audit): `ground_truth.py` still passes
   the static + runtime independence checks; System A and System B remain
   distinct in form.
4. **Power adequate** (Phase 7): planned `D_vs_B` power ≥ 0.80 under a
   conservative pilot-derived variance.
5. **Reproducibility & integrity** (Phase 23): production, V1, and the frozen
   study byte-identical; all V2 artifacts checksummed.

If (1) or (3) fails, V2 does not proceed to the locked test.

---

## 7. Decision — is V2 necessary?

**Yes.** The V1 `D_vs_B` null is uninterpretable as an answer to the primary
question because B is degenerate in the V1 environment. A corrected,
action-responsive, still-independent environment is the minimum needed to make
the primary comparison meaningful. V2 is that environment. It may still return a
null (which would then be *stronger* evidence), a negative, or a positive result;
the design above is built to make whichever outcome occurs credible and
independently checkable, not to produce any particular one.
