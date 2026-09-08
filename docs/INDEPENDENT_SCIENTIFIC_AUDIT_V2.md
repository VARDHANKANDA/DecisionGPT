# Independent Scientific Audit — Upgraded Controlled Evaluation V2

**Auditor role:** independent, hostile-but-fair methodological review of the V2
work as actually done — a corrected action-responsive environment and a
Phase-16 pre-lock diagnostic that caused the study to **stop before the locked
test**. Audit only; nothing was modified. The V2 locked test was **not** run and
was **not** run by this audit.

Companion machine-check report: `experiments/upgraded_controlled_v2/INTEGRITY_AUDIT_V2.md`
(14/14 pass). Issue tags as in the V1 audit (SEVERITY / TYPE / AFFECTS / ACTION).

---

## 1. Executive Verdict

**VERDICT: SCIENTIFICALLY SOUND AS EXECUTED — a valid diagnostic result, correctly
stopped.**

V2 did exactly what a rigorous protocol should: it built a **verified**
action-responsive synthetic environment, ran a pre-lock diagnostic on
development/validation data only, discovered that the pre-registered
non-degeneracy precondition **fails for reasons outside the evaluation's control**
(the production Digital Twin, not the environment), and **stopped** rather than
run an uninterpretable locked test. The environment, the independence guarantees,
the oracle, and the candidate/information fairness all check out. The one
"failure" — condition B is a constant policy — is the **finding**, not a defect
of V2.

**Central V2 result:** In an environment where the true demand elasticity is
recoverable from the historical data (median OLS recovery error **0.097**),
condition B (`argmax` of the production Digital Twin's projected KPI over the
candidate set) selects **`price_change=+10 %`** on **~100 %** of 272 development
executions, with correlation **0.03** to the true elasticity. Direct probing of
`digital_twin_service.simulate_strategy` shows its projected revenue is
**monotonically increasing in price for every scenario** (implied elasticity
≈ −0.1). **Condition B is a constant policy by architecture, not by environment.**

---

## 2. Audit Scope

Audited: `docs/UPGRADED_EVALUATION_V2_DESIGN.md`,
`docs/UPGRADED_EVALUATION_V2_PREREGISTRATION.md`,
`backend/app/evaluation/scenario_families_v2.py` (System A),
`backend/app/evaluation/ground_truth.py` (System B, reused),
the one-line change to `backend/app/evaluation/harness.py`,
`scripts/run_eval_v2.py`, `experiments/upgraded_controlled_v2/`
(`scenario_manifest.json`, `config.json`, `prelock_diagnostics.json`,
`checksums.txt`, `INTEGRITY_AUDIT_V2.md`),
`tests/unit/test_eval_v2_scenario_families.py`.

Independent re-derivations run for this audit: elasticity-recovery OLS on the
generated history; oracle re-enumeration; System-A/System-B functional-form
comparison; B action distribution from `prelock_diagnostics.json`; Digital-Twin
projection curve probe (read-only, production).

---

## 3. Frozen-Artifact & Non-Interference Verification

| Item | Result |
|---|---|
| Frozen experiment manifest SHA-256 | `94aa419c…c15cbff` — unchanged (verified before & after the diagnostic run) |
| `git diff` — production (`services/analytics/agents/decision_engine`), `experiments/experiment_manifest.json`, `paper_results_snapshot.json`, `experiments/results/`, **`experiments/upgraded_controlled_v1/`**, `docs/PAPER_DRAFT.md`, `docs/ieee_paper/`, `docs/UPGRADED_EVALUATION_PREREGISTRATION.md` | **empty** |
| V1 eval unit tests + V1 `REPRODUCIBILITY_AUDIT.md` after the harness change | still pass (21 tests; 14/14 audit) |
| `PipelineOptions().label()` | `"full"` (R0/D0) |
| `digital_twin_service.RISK_FORMULA_VERSION` | `extrapolation_range_v1` (R3 not promoted) |
| `ground_truth.py` byte-identical to V1 | yes (System B reused verbatim) |

The **only** shared-infrastructure change is the optional `realise_history=`
keyword on `harness.run_instance`. When omitted, behaviour is byte-identical to
V1 (confirmed by V1's tests + audit). *SEVERITY: none. ACTION: no action —
disclosed in the design doc §4.*

---

## 4. Ground-Truth Independence (System B)

`ground_truth.py` is **unchanged from V1** and re-verified: AST import set is
exactly `{__future__, dataclasses, math, numpy, scipy.optimize, typing}`; no
pipeline import; no history use; `evaluate()` is a pure closed-form function of
`scenario.params + scenario.constraints + action`, called only **after**
selection. Passes the V1 independence contract unchanged.

**Classification: A — genuine metric independence.** *ACTION: no action.*

---

## 5. Objective Bias Audit

System B is byte-identical to V1, so the V1 objective-bias analysis carries over:
the objective is a standard additive-linear demand model, motivated
independently, not tilted toward or against a *condition*; its optima are
boundary actions (`p±10`, `m±20`) determined by `sign(1+eps)` and objective type
(V1 finding O-1). No condition has privileged access to `eps`/`mr`/`kappa`. The
V2 coupling (§8) does not change this — it only makes the historical data
*informative* about the objective, which is the intended improvement.

*Issue O-1 (carried from V1). SEVERITY: Moderate. TYPE: validity. AFFECTS:
interpretation. ACTION: should disclose — unchanged from V1.*

---

## 6. Oracle Correctness

Independent re-enumeration over the 68 diagnostic scenarios: **0 mismatches** vs
the implemented `ground_truth.oracle` (action key and value). `classical` never
exceeds `oracle`. No degenerate normalisation spans observed. *ACTION: no action.*

---

## 7. Candidate-Space Fairness

From `prelock_diagnostics.json` over 272 executions: `action_space_invariant_ok`
holds on **all**; declared candidate count == resolved count on all (8/8 revenue,
6/6 profit, 5/5 inventory). D `status == "ok"` on all 272. A/B/C/D select over
the identical set; oracle over that set + no-op. **Fairness holds.**

Condition **A** is (as in V1) a fixed smallest-magnitude policy
(`price_change=−3` / `price_change=+5`). The V2 pre-registration correctly demotes
`D_vs_A` to a cautiously-interpreted secondary contrast and does not make it the
main argument (V1 finding C-1/DA-1 addressed at the design level). *ACTION: no
action beyond the design-level demotion already made.*

---

## 8. Information-Set Fairness & Circularity Prevention (Phase 3)

**Two separate systems, confirmed distinct:**

| | System A (`scenario_families_v2.realise_history`) | System B (`ground_truth.evaluate`) |
|---|---|---|
| form | `d0·(p/p0)^a_elast·(s/s0)^a_mkt·season·e^N(0,σ)` — **log-linear, stochastic** | `d0·max(0,1+eps·Δp/100)+mr·(Δs/1000)·kappa` — **additive-linear, deterministic** |
| module imports | stdlib + numpy + (V1 `production_candidate_actions` only) | stdlib + numpy + scipy |
| sees the action? | no (history precedes any action) | only the *chosen* action, only after selection |

The coupling is a **noisy monotone parameter map**
(`eps = clip(a_elast + N(0,0.35), …)`), verified in the audit: for the first
generated scenario `a_elast = −1.86` vs `eps = −1.91` (close but not equal);
across the suite `|eps − a_elast|` is bounded and sign-consistent, never exactly
equal. **Not the same formula copied twice.** The harness fairness trace
(`gt.*` only post-selection; no oracle/objective/future into a picker) is reused
from V1 unchanged.

*Issue: none. ACTION: no action. This is a correct, non-circular two-system
design.*

---

## 9. Scenario-Generation Audit — is the environment genuinely action-responsive?

**Independent check.** OLS of `log(units)` on `log(price)`, `log(spend)` over the
*generated* history (uncensored families):

| family | true `a_elast` | recovered | \|err\| | log-price SD |
|---|---:|---:|---:|---:|
| `inelastic_demand` | −0.51 | −0.65 | 0.14 | 0.093 |
| `unit_elastic` | −1.04 | −0.91 | 0.13 | 0.132 |
| `low_volatility` | −1.77 | −1.67 | 0.09 | 0.122 |
| `low_data` | −1.25 | −1.30 | 0.05 | 0.115 |
| `noisy_observations` | −1.55 | −1.33 | 0.22 | 0.124 |
| `high_marketing_response` | −1.12 | −1.32 | 0.21 | 0.101 |
| `thin_margin_profit` | −0.73 | −1.00 | 0.27 | 0.101 |
| `fat_margin_profit` | −0.70 | −0.58 | 0.12 | 0.113 |
| `inventory_bound` | −1.59 | −0.42 | **1.17** | 0.135 |
| `asymmetric_risk` | −0.41 | −0.25 | 0.17 | **0.026** |

**Median \|err\| = 0.097; median log-price SD = 0.119.** The environment is
genuinely action-responsive and the elasticity is identifiable from data, for
every family except (by design) `inventory_bound`/`capacity_bound` (demand
censored by the cap) and `asymmetric_risk` (deliberately narrow price history).
**This is a real, verified improvement over V1** (which had ≈ 0 recoverable
signal).

**Family distinctness.** 22 families with genuinely different parameter ranges
(elasticity regime, marketing exponent, margin, caps, seasonality amplitude,
noise, cost shock, horizon decay). Not cosmetic. More structurally diverse than
V1's ~6 regimes.

**Partition.** Deterministic **stratified** family-level holdout (pattern
`[dev,dev,val,locked]` over group-ordered families) — locked families come from
5 distinct structural super-groups. Fixed at design time; independent of any
outcome. Better coverage than V1's single-shuffle draw. **The locked partition
was never run.**

*Issue G-3. SEVERITY: Minor. TYPE: validity. AFFECTS: none (locked test not run).
ACTION: should disclose — `inventory_bound`/`capacity_bound` elasticity is not
identifiable due to demand censoring; had the locked test run, `capacity_bound`
would have been a partially-non-identifiable locked family.*

---

## 10. B Non-Degeneracy Audit — the central question

**Independent reconstruction from `prelock_diagnostics.json` (272 executions,
0 errors, development + validation only):**

* B's selected action: `price_change=+10` on **16/16** executions of **every**
  non-inventory family (15 families); `inventory_change=+20` on **16/16** of
  `inventory_bound`. **2 distinct actions total.**
* `corr(a_elast, B_price_move_pct) = 0.031` — **no relationship.** B raises price
  10 % whether `a_elast ≈ −0.4` or `a_elast ≈ −2.5`.
* B per-family regret ranges **0.0 → 1.0** purely by whether "+10 % price"
  matches that family's true optimum (identical mechanism to V1).

**Root-cause probe (read-only, production).** `digital_twin_service.simulate_strategy`
over the candidate set:

| scenario | true `a_elast` | DT-projected revenue ordering | oracle |
|---|---:|---|---|
| `inelastic_demand` | −0.51 | `p+10` (2.316M) > `p+5` > … > `p−10` (1.895M) | `p+10` ✅ |
| `low_volatility` | **−1.77** | `p+10` (0.287M) > `p+5` > … > `p−10` (0.235M) — **still ↑ in price** | `p−10` |
| `promotion_decision` | **−2.48** | `p+10` (0.368M) > … > `p−10` (0.301M) — **still ↑ in price** | `p−10` |

The Digital Twin's projected demand barely moves with price (implied elasticity
≈ −0.1 across a 20-point price swing), so projected revenue ≈ price × constant and
the argmax is **always `price_change=+10`**. Marketing candidates project nearly
identically to each other.

**Assessment.** This is **not** a V2 environment defect, an evaluation-harness
bug, or a scoring artefact:
* the environment *does* contain the signal (§9);
* the harness *does* run all candidates through the real DT and take the argmax
  (verified in the V1 audit; harness unchanged);
* the DT's own projection is what is flat in price.

It is a property of the **production `digital_twin_service`**. Correcting it is
forbidden (no production changes). Therefore Phase-16 check #1 ("B not trivially
constant unless genuinely unavoidable") fails *and* the exception applies (it is
genuinely unavoidable). **Stopping before the locked test is the correct action**
under the pre-registration's own stopping rule.

*Issue B-2. SEVERITY: Major (but correctly handled). TYPE: validity. AFFECTS:
the entire primary-question programme (V1 and V2). ACTION: must disclose — a
clean `D_vs_B` ablation of the downstream stack is not constructible against the
current production architecture; the paper must say so.*

---

## 11–16. Locked-Test Integrity / Power / Statistics / Clustering / Multiplicity / Robustness / Mechanism

**Not applicable — the V2 locked test was not run.** The audit confirms:

* `config.prereg_frozen == false`, `config.status == "STOPPED_AT_PRELOCK_GATE"`,
  `config.locked_test_run == false`.
* No `results.json`, `statistical_results.json`, `robustness_results.json` under
  `experiments/upgraded_controlled_v2/`.
* `prelock_diagnostics.json.scope.locked_test_touched == false` — the diagnostic
  ran on development + validation families only; the 5 locked families
  (`capacity_bound`, `conflicting_signals`, `delayed_effects`,
  `low_marketing_response`, `seasonal_strong`) were never executed.
* The power step, the prereg freeze, and the locked run were all skipped by the
  Phase-16 stop.

*ACTION: no action. The absence of these analyses is correct, not a gap.*

---

## 17. Baseline Fairness

Not exercised (no locked run). The V2 pre-registration correctly re-labels
`naive`/`greedy`/`oracle`/`classical_optimizer` as **external computational
benchmarks** with analytic objective access that A/B/C/D lack (V1 finding B-1
addressed at the design level). *ACTION: no action.*

---

## 18. Reproducibility

Independently verified:
* `suite_checksum` recomputed from `scenario_manifest.json` scenarios ==
  `d28d521f…` == `config.suite_checksum`.
* `EvalScenarioV2.from_dict` round-trips (content hash stable; realised history
  identical for a given seed) — tested.
* Generation is deterministic in `master_seed`; a different seed changes the
  checksum — tested.
* `prelock-diagnose` is deterministic in `(scenario_id, seed)` (numpy Generator
  seeded from a hash of both).
* All V2 artifacts hashed in `checksums.txt`; frozen manifest re-verified.
* `INTEGRITY_AUDIT_V2.md`: 14/14.

*ACTION: no action.*

---

## 19. Claim-to-Evidence Matrix (V2)

| Claim | Evidence | Directly supported? | Qualification |
|---|---|---|---|
| The V2 environment is action-responsive and the response is identifiable | OLS recovery median err 0.097; log-price SD 0.119 | **Yes** | not for censored (`inventory_bound`) or narrow-price (`asymmetric_risk`) families, by design |
| System A and System B are distinct, non-circular systems | different functional forms; noisy monotone parameter coupling; independent imports | **Yes** | — |
| Condition B is a constant "+10 % price" policy in the V2 environment | 2 unique B actions over 272 dev executions; corr 0.03 with true elasticity | **Yes** | development + validation partitions only (locked never run) |
| B's degeneracy is architectural, not environmental | V2 env is verified responsive yet B unchanged; DT projection monotone ↑ in price on direct probe | **Yes** | DT probe covers a handful of scenarios directly; generality inferred from the 272-execution distribution |
| A clean `D_vs_B` ablation is not constructible without changing production | follows from B being architecturally constant | **Yes** | for the current production Digital Twin and the "argmax-of-DT" operationalisation of B |
| The V1 negative finding is invalidated | — | **No** — it stands, re-scoped (V2 explains *why* `D_vs_B` is hard to interpret; it does not overturn V1) | |
| Any real-world / SME / ROI / deployment / causal claim | none | **No** | forbidden |
| A V2 `D_vs_B` / `C_vs_B` / `B_vs_A` result | none — locked test not run | **No** | — |

---

## 20. Remaining Threats

| ID | Threat | SEV | TYPE | AFFECTS | ACTION |
|---|---|---|---|---|---|
| B-2 | Condition B is architecturally constant; a clean downstream-stack ablation is not constructible without changing production | Major | validity | the primary-question programme | must disclose in the paper |
| O-1 | (from V1) System B optima are boundary actions set by unobservable parameters | Moderate | validity | interpretation | should disclose (unchanged from V1) |
| G-3 | `inventory_bound`/`capacity_bound` elasticity not identifiable (demand censoring); one such family is in the (un-run) locked set | Minor | validity | none (locked not run) | should disclose |
| DT-probe-scope | The Digital-Twin monotone-in-price finding is probed directly on a few scenarios; the rest is inferred from B's action distribution | Minor | implementation | strength of the root-cause claim | should disclose; a fuller DT characterisation would strengthen it |
| Env-choice | System A is one modelling choice (log-linear power law); a different DGP might interact differently with the DT | Minor | validity | generality | should disclose (the DT's ≈ −0.1 implied elasticity makes it unlikely to matter) |

**No Critical issue. No invalid evidence.** The single Major item (B-2) is the
*finding*, and it was handled correctly (stop before lock).

---

## 21. Final Verdict

### FINAL VERDICT: **SCIENTIFICALLY SOUND AS EXECUTED**

V2 is a correctly-run diagnostic study. It built a **verified** action-responsive
environment (median elasticity-recovery error 0.10), preserved every V1
soundness property (independence, oracle, candidate/information fairness,
reproducibility, non-interference), ran the pre-lock diagnostic on
non-locked data only, and **stopped** when the pre-registered non-degeneracy
precondition failed for an architectural reason it is forbidden to fix. The
locked test was not run; that is the right call, not a shortfall.

### TOP 5 REMAINING THREATS
1. **Condition B is architecturally constant** ("+10 % price"), so the primary
   question ("does the downstream stack add value over Decision Simulation?")
   is not answerable by a controlled ablation against the current production
   architecture (B-2).
2. The Digital-Twin root cause is directly probed on only a handful of scenarios
   (though corroborated by B's action distribution over 272 executions).
3. System B's optima are boundary actions set by parameters no data-driven
   condition observes (O-1, carried from V1).
4. `inventory_bound`/`capacity_bound` elasticity is not identifiable (censoring);
   one is in the (un-run) locked set (G-3).
5. System A is one data-generating-process choice; a different one might (though
   probably would not) interact differently with the Twin.

### TOP 5 STRONGEST EVIDENCE POINTS
1. **The V2 environment is genuinely action-responsive** — true elasticity
   recovered from the generated history with median error 0.10, log-price SD 0.12
   (V1 had ≈ 0).
2. **B is still constant** — 2 unique actions over 272 executions; corr 0.03 with
   true elasticity — establishing the degeneracy is architectural, not
   environmental.
3. **Direct Digital-Twin probe** — projected revenue monotonically increasing in
   price for elastic *and* inelastic scenarios (implied elasticity ≈ −0.1).
4. **All V1 soundness properties preserved** — System B unchanged and independent;
   oracle exact (0/68); candidate/information fairness intact; harness change is
   a byte-identical-when-unused injection point.
5. **Full non-interference and reproducibility** — frozen manifest, V1, the
   frozen study, production, and the paper all byte-identical; 14/14 machine
   audit; deterministic generation + diagnostic.

### EXACT CLAIMS THE IEEE PAPER MAY MAKE (from V2)
* "We built a synthetic evaluation environment in which historical demand
  responds to historical price and marketing via a log-linear model, and
  verified that the true price elasticity is recoverable from the generated
  history (median OLS recovery error ≈ 0.10)."
* "In this action-responsive environment, the Decision-Simulation condition —
  operationalised as the argmax of the production Digital Twin's projected KPI
  over the candidate action set — selected the maximum price increase on
  approximately 100 % of executions, uncorrelated with the true demand
  elasticity."
* "Direct inspection of the production Digital Twin shows its projected revenue
  is monotonically increasing in price for both elastic and inelastic scenarios
  (implied price elasticity ≈ −0.1), i.e. its action ranking is invariant to the
  identifiable demand response."
* "Consequently, a controlled ablation of the form 'does the downstream
  multi-agent/risk/optimisation stack add incremental objective value over
  Decision Simulation?' is not constructible against the current production
  architecture without modifying the production Digital Twin; the
  Decision-Simulation condition is a constant policy in the tested action space."
* "This diagnosis is consistent with, and independent of, the V1 controlled
  evaluation; the two are not pooled."
* "All V2 artifacts, the environment generator, and the diagnostic reproduce
  from fixed seeds; the frozen study, V1, production (R0/D0), and R3's status
  are unchanged."

### EXACT CLAIMS THE PAPER MUST NOT MAKE (from V2)
* Any V2 `D_vs_B` / `C_vs_B` / `B_vs_A` numerical result (the locked test was not
  run).
* "The multi-agent layer adds no value" / "…is worse" as a V2 conclusion.
* "The Digital Twin is broken/wrong" as an unqualified statement — say precisely:
  "its projected demand is near-inelastic and its action ranking is invariant to
  the identifiable elasticity in this synthetic setting."
* Any real-world / SME / Indian-SME / ROI / customer / deployment / causal claim.
* "V2 validates/refutes DecisionGPT."
* "V1 is invalid" — V1 stands, re-scoped.
* That the pre-lock diagnostic numbers are results — they are a gate on
  development/validation data.

### WHETHER PAPER INTEGRATION IS NOW SAFE
**Yes, for the V2 *diagnostic* result, with the wording above.** V2 integrates as
a short methodological section: "we attempted to construct a cleaner
incremental-value test by making the environment action-responsive; we verified
the environment but found the Decision-Simulation condition remains a constant
policy because the production Digital Twin's action ranking is invariant to the
identifiable demand elasticity; a clean ablation therefore requires a production
change, which is out of scope." It must **not** be integrated as a
pass/fail verdict on the architecture or as any real-world claim, and it carries
no `D_vs_B` number.

---

*End of independent V2 audit. No production file, frozen artifact, V1 artifact,
pre-registration, result, or paper was modified in producing this document. The
V2 locked test was not run.*
