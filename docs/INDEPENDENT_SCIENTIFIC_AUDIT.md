# Independent Scientific Audit — Upgraded Controlled Evaluation

**Auditor role:** independent, hostile-but-fair methodological review of the
completed upgraded controlled evaluation (`experiments/upgraded_controlled_v1/`,
`docs/UPGRADED_EVALUATION_REPORT.md`).
**Audit only.** No production code, no frozen artifact, no result, no
pre-registration, no paper was modified. The locked test was **not** re-run.
Every quantitative check below is a read-only reconstruction from the stored
artifacts or a purely analytical derivation.

Issue tags: **SEVERITY** Critical / Major / Moderate / Minor · **TYPE**
validity / bias / statistics / reproducibility / interpretation /
implementation · **AFFECTS** primary result / secondary result / interpretation
/ none · **ACTION** must fix / should disclose / no action.

---

## 1. Executive Verdict

**VERDICT: B — SOUND WITH MATERIAL QUALIFICATIONS.**

The *machinery* is sound and independently verified: the exogenous objective is
genuinely independent of DecisionGPT (static + structural), the oracle is exactly
correct on all 80 locked scenarios, the identical-action-space invariant holds on
all 800 executions, no information leaks into action selection, every headline
statistic reproduces to full precision, and every checksum matches. Production
and the frozen study are untouched.

The *interpretation* of the headline contrasts is over-reached relative to what
the design supports. Three findings drive this:

1. **Condition B is a degenerate constant policy.** On **all 200 instances of
   every one of the 4 locked families**, B selects the identical action
   `price_change=+10%`. B has no discriminating behaviour on the locked set; its
   per-family regret is entirely determined by whether that family's true
   optimum happens to be "raise price." `D_vs_B` is therefore a comparison
   against a constant "always +10% price" policy on a 2-vs-2 family split, not
   against an adaptive decision-simulation baseline.
2. **The primary null is underpowered relative to plan.** The pre-registered
   power (0.860) assumed a between-scenario paired-difference SD of 0.28; the
   **observed** SD for `D_vs_B` is **0.508** (1.8×) and for `B_vs_A` is **0.650**
   (2.3×). The `D_vs_B` 95% CI is [−0.078, +0.143]; the upper bound **exceeds**
   the 0.10 minimum effect of interest. The correct statement is *"no
   statistically significant incremental effect was detected,"* not *"no effect"*
   and not *"equivalent."*
3. **Condition A is a constructed fixed policy, not an architectural ablation.**
   A always plays the smallest-magnitude catalogued action (`price_change=−3%`
   for revenue families, `price_change=+5%` for the profit family). `D_vs_A`
   ("significantly worse") means "the full pipeline is beaten by a fixed small
   price nudge on these 4 families."

None of this invalidates the *primary* contrast — `D_vs_B` is a clean,
same-data, same-action-space, same-information comparison, and its (weak) null is
directionally consistent with the frozen study. But the report's conclusions
must be scoped to: *on synthetic decision problems where the price/marketing
response is not identifiable from the supplied history, adding the rule-based
agent layer to the digital-model baseline produced no detectable change in
exogenous regret, and the full pipeline did not beat a fixed minimal-intervention
policy or the status quo.*

---

## 2. Audit Scope

Artifacts audited (SHA-256 verified in §3):
`ground_truth.py`, `scenario_families.py`, `harness.py`, `stats.py`,
`perturbations.py`, `mechanism.py`; `scenario_manifest.json`, `config.json`,
`power_assumptions.json`, `power_analysis.json`, `results.json` (7.2 MB, 800
records), `statistical_results.json`, `analysis_supplement.json`,
`robustness_results.json`, `checksums.txt`, `REPRODUCIBILITY_AUDIT.md`;
`docs/UPGRADED_EVALUATION_{REPORT,READINESS,PREREGISTRATION,IMPLEMENTATION}.md`.

Independent tooling: a single read-only reconstruction script
(`scratchpad/audit_recon.py`, not part of the study) that re-derives the oracle,
the per-scenario regrets, the paired statistics, Holm, the family structure, the
pick distributions, seed stability and the factor variance decomposition.

---

## 3. Frozen-Artifact Verification

| Item | Recomputed | Recorded / expected | Match |
|---|---|---|:--:|
| Frozen experiment manifest | `94aa419c…c15cbff` | `94aa419c…c15cbff` | ✅ |
| Frozen manifest at locked-run time (in `results.json`) | `94aa419c…c15cbff` | — | ✅ |
| `scenario_manifest.json` file hash | `12ad7707…d74c06` | `12ad7707…d74c06` (`checksums.txt`) | ✅ |
| `suite_checksum` | `2215a1bd…629697` | manifest == config | ✅ |
| `locked_test_family_checksum` | `47f0afd6…5ea95` | `47f0afd6…5ea95` | ✅ |
| Pre-registration doc | `72c99bcf…fd7dd` | `72c99bcf…fd7dd` (`config.prereg.doc_sha256`) | ✅ |
| `results.json` file hash | `804fbe91…f506e` | `804fbe91…f506e` | ✅ |
| Architecture fingerprint | `60ca9c9e…d26e37` | in `results.json` | ✅ |
| `PipelineOptions().label()` | `"full"` | R0/D0 | ✅ |
| `git diff` — `backend/app/{services,analytics,agents,decision_engine}`, `experiments/experiment_manifest.json`, `paper_results_snapshot.json`, `experiments/results/`, `docs/PAPER_DRAFT.md`, `docs/ieee_paper/` | empty | empty | ✅ |
| Tracked working-tree changes | `.gitignore` only (Phase-2) | — | ✅ |

**No issue.** Reproducibility and non-interference claims independently confirmed.

---

## 4. Ground-Truth Independence (AUDIT QUESTION 1)

**Static analysis.** `ground_truth.py` AST import set is exactly
`{__future__, dataclasses, math, numpy, scipy.optimize, typing}`. **Zero**
matches against `digital_twin`, `decision_service`, `decision_architecture`,
`forecast_service`, `app.agents`, `app.services`, `app.analytics`,
`goal_achievement`.

**Structural analysis.** `evaluate(scenario, action)` is a pure closed-form
function of `scenario.params` (base_price, unit_cost, base_demand,
price_elasticity, marketing_response, marketing_base_spend, kappa, holding_rate,
capacity_cap, inventory_cap) + `scenario.constraints` (price floor/ceiling,
cash_cap) + the action's three percentage deltas. It does **not** read
`scenario.reference_history`, `history_spec`, or any realised history; it makes
no I/O and no external call. The classical-optimizer baseline lazily imports
`scipy.optimize` only.

**Call-graph.** `harness.py` calls `gt.oracle` / `gt.score_selection` /
`gt.{naive,greedy,classical}_baseline` **only after** each condition's action is
selected (lines 321–343, 355, 364, 377, 434). `_pick_argmax` (B, C) receives a
`score_fn` closed over the Digital-Twin `SimulationOutput` only; D calls
`decision_service.analyze_goal` with no arguments derived from `gt`. `oracle_res`
is passed to the scoring helpers, never to a picker or to `analyze_goal`.

**Shared elements (conceptual overlap, not circularity):** the action vocabulary
(price/marketing/inventory %), the identity `revenue = price × units`, and the
notion of an elastic demand curve are shared *domain assumptions*. The
*functional forms differ*: the objective uses a **linear** own-price factor
`max(0, 1 + eps·Δp/100)` and a **linear** marketing term
`mr·(Δspend/1000)·kappa`; the Digital Twin uses recursive last-value
extrapolation. No coefficient, transformation, or internal score is shared.

**Classification: A — genuine metric independence.** No direct dependency, no
indirect dependency, no leakage.

*Issue: none. ACTION: no action.*

---

## 5. Objective Bias Audit (AUDIT QUESTION 2)

Each objective component, its motivation, and whether it structurally favours a
condition:

| Component | Why it exists | Independently motivated? | Favours a condition? |
|---|---|---|---|
| Linear own-price elasticity `1 + eps·Δp/100` | textbook demand curve | yes (standard micro) | **No** condition can observe `eps` (see §6); it is not exposed to any of A/B/C/D. The *baselines* greedy/classical/oracle evaluate it directly (§19). |
| Linear marketing response `mr·Δspend/1000·kappa` | diminishing-return proxy with a horizon-decay factor | yes | same — `mr`, `kappa` unobservable to A/B/C/D |
| `units = clip(demand, 0, min(eff_inv_cap, capacity_cap))` | capacity/inventory ceilings | yes | neutral; only 2 development families set finite caps, `capacity_constraint` is not in the locked test |
| `cost = unit_cost·units + mkt_spend`; `profit = revenue − cost` | accounting identity | yes | neutral |
| `holding_cost = holding_rate·unsold` | inventory carrying cost | yes | `holding_rate = 0` in every generated scenario ⇒ inert |
| Feasibility: price floor/ceiling, `cash_cap` | scenario constraints | yes | applied identically to every condition and to the oracle |

**Privileged information.** The objective's decisive parameters
(`price_elasticity`, `marketing_response`, `kappa`, `unit_cost`) are **not
present in the seeded business history** (§6). No architecture condition
(A/B/C/D) has privileged access. The reference baselines (greedy, classical,
oracle) **do** have exact analytic access — this is intrinsic to their role but
must be labelled (§19).

**Can any condition game the objective?** No. Selection happens before any
`gt.*` call; the objective is computed once, post-hoc, from frozen parameters.

**Structural direction.** The objective is not tilted toward or against a
*condition*. It is, however, tilted toward **extreme catalogued actions**: on
the locked families the oracle action is `price_change=−10` (promotion_decision,
20/20), `price_change=+10` (asymmetric_risk 20/20; competing_objectives 18/20),
or a marketing extreme — i.e. the true optimum is almost always a boundary
action whose identity flips with the sign of `(1 + eps)` and the objective type.
A data-driven policy that cannot recover `eps` cannot systematically hit these.
**This is a validity scoping issue (§9, §21), not objective bias against a
condition.**

*Issue O-1. SEVERITY: Moderate. TYPE: validity. AFFECTS: interpretation. ACTION:
should disclose — the objective's optima are boundary actions determined by
unobservable parameters; the evaluation therefore tests "recover an
unidentifiable response," on which any data-driven condition is expected to
fail.*

---

## 6. Ground-Truth vs. Observable Data — the central structural finding

`scenario_families._history()` generates the business history every condition
ingests:

```
price[d]  = base_price · (random walk in ±band) · (0.94 every 10th day) · jitter
units[d]  = base_demand · (1 + N(0, demand_noise_sd)) + 0.15·base_demand every 10th day
mkt[d]    = marketing_base_spend · (1 ± 0.10 noise)
```

`units` is generated **independently of `price[d]` and `mkt[d]`**. `_history()`
never references `price_elasticity`, `marketing_response`, `kappa`, or
`unit_cost`. Therefore the historical data contains **no identifiable
price→demand or marketing→demand relationship**; the only price/demand
co-movement is a spurious artefact of the shared 10-day cycle (−6% price / +15%
units on the same days), which if anything implies a *constant* fake elasticity
for every family.

**Consequence for condition B.** B = argmax over the feasible set of the Digital
Twin's projected KPI. Fitting from this history, the Twin concludes higher price
⇒ higher revenue/profit and B selects `price_change=+10%` on **every single one
of the 800 locked executions** (verified: `B_keys = {"price_change=+10": 200}`
for each of the 4 families). B is a constant policy on the locked set.

**Consequence for the comparison.** A/B/C/D are being asked to optimise an
objective whose decisive parameters are absent from their inputs. Only the
reference baselines (greedy, classical, oracle), which call `evaluate()`
directly, can "see" the objective.

*Issue S-1. SEVERITY: Major. TYPE: validity. AFFECTS: primary result +
interpretation. ACTION: must disclose — B is a degenerate constant "raise price"
policy on the locked set; `D_vs_B` and `B_vs_A` compare against a constant
policy, and the tested regime is one in which no data-driven condition can
succeed. The clean, defensible reading of `D_vs_B` is "the agent layer does not
change the outcome relative to the digital-model baseline **when the response is
non-identifiable from data**"; a general "adds no value" claim is not supported.*

---

## 7. Candidate-Space Fairness (AUDIT QUESTION 4)

Independent reconstruction from `results.json` `action_space_detail` over all 800
records:

| Check | Result |
|---|---|
| `action_space_invariant_ok` | **800 / 800 true**, 0 failures |
| declared vs resolved candidate count | `8/8` on 600 revenue instances, `6/6` on 200 profit instances — always equal |
| D `status` | `"ok"` on **800 / 800**; `pick_outside_feasible_set` = 0 |
| A selected action | `price_change=−3` on 600 (revenue), `price_change=+5` on 200 (profit) — a **fixed** policy |
| "marketing +10%" extra profit candidate | present in both declared and resolved profit sets (6/6) — invariant preserved |
| low-data exclusions | none in the locked test (locked families all have 90-day history); `low_data` is in the *validation* partition |

A/B/C/D all select over the **identical** enumerated feasible set per instance;
the oracle enumerates that set plus the explicit no-op; greedy/classical project
onto the same discrete set. **No condition receives extra candidates or
information via the candidate mechanism.**

**On condition A.** `ground_truth._noop_action(feasible)` returns the
smallest-|Σ value| feasible candidate because the production candidate list
never contains the literal `()` action. So A ≠ "prediction recommends nothing
⇒ status quo"; A = "always play the gentlest catalogued move." The literal
status quo is the separate `naive` baseline. `D_vs_A` is therefore a comparison
against a **hand-constructed minimal-intervention policy**, not an ablation of a
prediction stage. It is still interpretable — but only as "the full pipeline is
beaten by a fixed −3% price move on these 4 families (2 of which reward a small
price cut)."

*Issue C-1. SEVERITY: Major. TYPE: interpretation. AFFECTS: the one significant
architecture contrast (`D_vs_A`). ACTION: must disclose — every statement of
"D worse than A" must carry the "A = fixed smallest-move policy" qualifier and
be read alongside `D_vs_naive` (null).*

*Otherwise: candidate-space fairness holds. ACTION: no action on the invariant
itself.*

---

## 8. Information-Set Fairness (AUDIT QUESTION 5)

Traced in `harness.run_instance`:

| Information | A | B | C | D | Leakage? |
|---|---|---|---|---|---|
| Seeded history (price/units/marketing) | ✓ (unused; A is fixed) | ✓ (via DT fit) | ✓ | ✓ | intended |
| Digital-Twin projections | ✗ | ✓ | ✓ | ✓ | intended architectural difference |
| Single-agent score | ✗ | ✗ | ✓ | ✓ (+ 2 more agents + optimizer) | intended |
| Exogenous objective value | ✗ | ✗ | ✗ | ✗ | **none** — `gt.*` only called after selection |
| Oracle action / value | ✗ | ✗ | ✗ | ✗ | **none** — `oracle_res` never passed to a picker or to `analyze_goal` |
| True future / true parameters | ✗ | ✗ | ✗ | ✗ | **none** |

`gt.evaluate` appears in `_post_run_factor_inputs` (mechanism factor extraction)
— that is post-selection and feeds only the exploratory mechanism analysis, not
any condition's choice.

**No leakage into selection. Information-set fairness holds** for A/B/C/D (the
only asymmetries are the intended architectural ones). *ACTION: no action.*

---

## 9. Scenario-Generation Audit (AUDIT QUESTION 6)

**Family distinctness.** The 17 families are constructed by overriding a small
number of `_base_params` fields and history knobs. Independent tabulation of the
generated 340-instance suite:

| Aspect | Finding |
|---|---|
| `price_elasticity` ranges | 12 families draw from the wide default ≈ [−1.8, −0.5]; overridden to elastic in `promotion_decision` [−2.1,−1.3], `competing_objectives` [−1.8,−1.5], `conflicting_signals` [−2.0,−1.5], `high_volatility` [−2.4,−1.6]; **inelastic** only in `asymmetric_risk` [−0.5,−0.2] and `adversarial_risk_trap` [−0.35,−0.16] |
| `kappa` (horizon decay) | 1.0 in 16 families; only `delayed_effects` varies it [0.25,0.48] |
| Gross margin | ≈ [0.19, 0.55] in most; thin only in `supplier_uncertainty` [0.06,0.18], `competing_objectives` [0.10,0.20], `high_volatility` [0.07,0.14] |
| Feasible-action count | 8 (revenue/sales) or 5–6 (profit/inventory) — **2 distinct values** across the whole suite |
| Objective type | revenue (9 families), profit (6), orders (1), holding_cost (0 — never generated) |
| Oracle action per family | almost always a single boundary action (`p±10`, `m±20`) determined by `sign(1+eps)` and objective type |

**Assessment.** Several "families" are minor parameter variants of a common
structure (e.g. `demand_uncertainty` / `price_uncertainty` / `noisy_observations`
/ `missing_observations` / `low_data` differ mainly in a history-noise knob, with
the same objective and the same wide elasticity draw). The genuinely distinct
decision regimes are roughly: *elastic-revenue*, *inelastic-revenue*,
*thin-margin-profit*, *capacity/inventory-bound*, *delayed marketing*,
*degraded-observation*. So ~6 structural regimes, not 17. This inflates the
apparent breadth of the suite.

**Locked-test composition.** The family-level split is deterministic from
`master_seed = 20260906` via `random.Random(f"{ms}:family_partition_v1")` — it
was **not** hand-picked, and the seed was fixed in the (later-frozen)
pre-registration, so there is **no evidence of selection to bias D downward**
(§10). But the draw yielded a narrow and structurally lopsided locked set:

| Locked family | regime | who it is hard for |
|---|---|---|
| `asymmetric_risk` | inelastic-revenue, 2%-wide price history | **hard for D** — the risk manager penalises the out-of-distribution price rise that is exogenously optimal |
| `competing_objectives` | elastic, thin-margin profit | **hard for D** — agents drift from the profit optimum B happens to hit |
| `promotion_decision` | strongly elastic revenue | **hard for B** — B's constant "+10% price" is the exact opposite of the `−10%` optimum |
| `missing_observations` | wide-elasticity revenue, 25–45% days dropped | **hard for B** — same, plus sparse data |

So the locked set is 2 families where the agent layer is expected to hurt and 2
where the digital-model baseline is expected to fail — a rough balance for
`D_vs_B`, but only 4 of ~6 structural regimes (no thin-margin-only,
capacity-bound, or delayed-effect family in the locked test), and 3 of the 4 are
degraded/adversarial rather than "ordinary."

*Issue G-1. SEVERITY: Moderate. TYPE: bias / validity. AFFECTS: primary-result
generality. ACTION: should disclose — the locked test covers 4 of ~6 structural
regimes; 3 of 4 are degraded/adversarial; the split was blind so this is a
coverage limitation, not p-hacking.*

*Issue G-2. SEVERITY: Minor. TYPE: interpretation. AFFECTS: none. ACTION: should
disclose — "17 families" overstates the number of distinct decision structures
(~6).*

---

## 10. Locked-Test Integrity (AUDIT QUESTION 7)

| Check | Evidence | Result |
|---|---|---|
| No family crosses partitions | reconstructed `fam→partition` map | 0 overlaps; all 17 assigned |
| Locked ⊄ development/validation | family-level split, disjoint by construction and by check | ✅ |
| Scenario-ID collision with S01–S12 | set intersection | ∅ |
| Duplicate scenario IDs | 340 ids, 340 unique | none |
| `locked_test_family_checksum` | recomputed `sha256(sorted(locked))` | `47f0afd6…5ea95` == recorded |
| Pre-registration unchanged since freeze | `sha256(prereg.md)` == `config.prereg.doc_sha256` | ✅ `72c99bcf…` |
| Config `prereg_frozen` | `true` | ✅ |
| Analysis plan == executed analysis | prereg §9 (unit = scenario, paired Wilcoxon, rank-biserial estimator, cluster bootstrap, Holm over {B_vs_A,C_vs_B,D_vs_B,D_vs_A}) vs `statistical_results.json` | matches |
| Timeline | `results.json` written 23:07, `statistical_results.json` 23:08 (immediately after); `run` refuses `locked_test` unless `prereg_frozen` and the doc SHA matches | consistent with "freeze → run once → analyze" |

**"Could someone have tuned the evaluation using locked-test information?"**
The `analyze` / `robustness` / `audit` code is generic (no scenario- or
family-specific constants) and was authored in the same commit as `run`. Only
`locked_test` appears in `config.runs` (no dev/val runs recorded; the Phase-3
dry run touched *development* families only). The pre-registered analysis family
of 4 contrasts is exactly what was reported. **No evidence of locked-test
leakage into methodology selection.** The residual, unfalsifiable risk is that
the analyst *looked* at `results.json` before finalising `analyze` — but since
the plan was pre-registered and the code is parameter-free, the exposure is
minimal.

*Issue L-1. SEVERITY: Minor. TYPE: reproducibility. AFFECTS: none. ACTION: no
action — noted for completeness.*

---

## 11. Power Audit (AUDIT QUESTION 8)

| Item | Value |
|---|---|
| Pre-specified before locked results? | Yes — `power_assumptions.json` fixed at freeze; `power_analysis.json` shows `estimated_power = 0.8601` |
| Assumptions | primary `D_vs_B`, MEI 0.10 (normalised regret), α 0.05, target 0.80, n=80, seeds=10, `metric_sd_between_scenarios = 0.28`, `within_scenario_seed_sd = 0.12` |
| Method | Monte-Carlo: 20 000 draws of `d ~ N(MEI, sd_eff)`, `sd_eff = hypot(0.28, 0.12/√10) = 0.283`, scenario-level paired Wilcoxon vs 0, count p < 0.05 |
| `n` sized from it? | Yes — n went 51 → 102 → 340 (20/family ⇒ locked 80) to clear 0.80 |
| Ties modelled? | **No** — disclosed in prereg §7 as a stated limitation |
| Cluster structure | represented (the sim is at the scenario level, matching the analysis unit) |
| Post-hoc N inflation | **None** — N fixed before the run; audit found no re-run |

**Achieved vs planned.** The observed between-scenario SD of the paired
differences is:

| Contrast | planned `sd_eff` | **observed `sd_diff`** | ratio |
|---|---:|---:|---:|
| `D_vs_B` | 0.283 | **0.508** | 1.80× |
| `B_vs_A` | 0.283 | **0.650** | 2.30× |
| `D_vs_A` | 0.283 | **0.231** | 0.82× |

With the *observed* `D_vs_B` SD (0.508), the achieved power to detect a 0.10
effect at n=80 is far below 0.86 (roughly 0.3–0.4 by the same simulation logic —
effect/SD fell from 0.35 to 0.20). `D_vs_A`, by contrast, had *lower* variance
than planned and its rejection is robust.

**"Planned power = 0.860" is a defensible statement about the pre-registered
design**, but it does **not** guarantee: (a) that the *executed* test had 0.86
power — it did not, because the variance assumption was ~2× too optimistic for
`D_vs_B` and `B_vs_A`; (b) that a null `D_vs_B` is evidence of a negligible
effect — the CI [−0.078, **+0.143**] does not exclude a difference larger than
the MEI.

*Issue P-1. SEVERITY: Major. TYPE: statistics. AFFECTS: primary result. ACTION:
must disclose — report planned power **and** the observed-vs-planned variance
(1.8×–2.3×); state the `D_vs_B` null as "underpowered failure to detect," not
"no/negligible effect," and never as "equivalence."*

---

## 12. Statistical Reconstruction (AUDIT QUESTION 9)

Recomputed independently from `results.json` (per-(scenario,seed) regret →
scenario mean over 10 seeds → paired analysis on 80 scenarios; cluster bootstrap
seed 12345, 10 000 resamples; SciPy Wilcoxon exact/approx by n_nonzero):

| Contrast | mean Δ (stored / recon) | Wilcoxon p (stored / recon) | 95% CI (stored / recon) | rank-biserial | W/T/L | Holm p (stored / recon) |
|---|---|---|---|---|---|---|
| `B_vs_A` | 0.075121 / **0.075121** | 0.00487134 / **0.00487134** | [−0.068771,+0.219137] / **same** | −0.10 | 36/0/44 | 0.01461403 / **same** |
| `C_vs_B` | 0.030282 / **0.030282** | 0.50497405 / **0.50497405** | [−0.078189,+0.136653] / **same** | +0.10 | 44/0/36 | 1.0 / **1.0** |
| `D_vs_B` | 0.033664 / **0.033664** | 0.53926505 / **0.53926505** | [−0.077636,+0.142779] / **same** | +0.10 | 44/0/36 | 1.0 / **1.0** |
| `D_vs_A` | 0.108785 / **0.108785** | 0.00063792 / **0.00063792** | [+0.058531,+0.160706] / **same** | +0.225 | 49/0/31 | 0.00255169 / **same** |

Reference contrasts also reproduce: `D_vs_naive` mean −0.0278, p 0.825, CI
[−0.091,+0.035] (null); `D_vs_greedy` mean +0.2275, p 7.0e−14, W/T/L 73/0/7;
`D_vs_classical` mean +0.3987, p 2.9e−12; `D_vs_oracle` mean +0.4826, p 7.8e−15,
W/T/L 80/0/0.

Condition-level mean regret reproduces: A 0.3738 · B 0.4489 · C 0.4792 ·
D 0.4826 · naive 0.5104 · greedy 0.2551 · classical 0.0839 · oracle 0.

**Every stored primary statistic matches the independent reconstruction to full
printed precision.** No computational discrepancy. *Issue: none. ACTION: no
action.*

---

## 13. Effective Sample Size (AUDIT QUESTION 10)

The analysis uses **scenario as the unit** (n = 80): 10 seeds are averaged to a
per-scenario regret *before* the paired tests; the cluster bootstrap resamples
the 80 scenarios; Wilcoxon is at n = 80. **This is correct** and is *not* the
"800 independent scenarios" error.

However, independent decomposition of the within-scenario seed variance:

| Condition | mean within-scenario SD of regret (over 10 seeds) | scenarios with **zero** seed variance |
|---|---:|---:|
| A | **0.000** | 80 / 80 |
| B | **0.000** | 80 / 80 |
| C | 0.174 | 3 / 80 |
| D | 0.163 | 3 / 80 |

**A and B are fully deterministic across the 10 seeds** (A is a fixed policy; B's
Digital-Twin argmax is invariant to the history realisation). So the "10
independent seeds" contribute replication variance **only to C and D**. For the
primary `D_vs_B` contrast, the paired value is
`mean₁₀ₛₑₑ_d(regret_D) − regret_B(constant)` — the seed averaging shrinks D's
noise (conservative for a null), but the pre-registration's framing that v2
seeds are "genuine independent replicates" is **overstated for the paired
analysis**, and "800 locked-test executions" overstates the information content
(effectively 80 decision problems for B, 80 × 10 varying runs for D).

*Issue E-1. SEVERITY: Moderate. TYPE: statistics / interpretation. AFFECTS:
interpretation (headline framing). ACTION: should disclose — the effective design
is 80 scenario clusters; A and B carry no seed replication; do not present "800
executions" or "10 independent replicates" as the strength of the primary
evidence. (Does not bias the null; if anything the seed-averaging makes the D
estimate tighter.)*

---

## 14. Multiplicity Audit (AUDIT QUESTION 11)

Independent Holm–Bonferroni over the pre-registered family
`{B_vs_A, C_vs_B, D_vs_B, D_vs_A}`:

| rank | contrast | p_raw | (m−i)·p | p_holm (monotone) | reject @ .05 |
|---|---|---:|---:|---:|:--:|
| 1 | `D_vs_A` | 0.00063792 | ×4 = 0.00255 | 0.00255169 | **yes** |
| 2 | `B_vs_A` | 0.00487134 | ×3 = 0.01461 | 0.01461403 | **yes** |
| 3 | `C_vs_B` | 0.50497405 | ×2 = 1.0 (clip) | 1.0 | no |
| 4 | `D_vs_B` | 0.53926505 | ×1 = 0.539 → monotone 1.0 | 1.0 | no |

Matches `statistical_results.json` exactly. Ordering, adjusted p, and rejection
decisions are correct.

**Confirmatory vs other.** The confirmatory family is exactly the 4 above.
`D_vs_oracle`, `D_vs_naive`, `D_vs_greedy`, `D_vs_classical_optimizer` are
correctly labelled *reference / descriptive* and excluded from the correction.
The mechanism, agent, robustness and failure-case analyses are labelled
exploratory/descriptive. No non-preregistered analysis is presented as
confirmatory. *Issue: none. ACTION: no action.*

---

## 15. Robustness Audit (AUDIT QUESTION 12)

**Scope.** 20 locked scenarios (`sorted(locked)[::4]` = 5 per family) × seeds
`20260906–07` × 10 perturbations × ≤2 severities = **720 runs, 0 errors**
(reconstructed count matches).

**Perturbation classification** (from `perturbations.py`):

| Perturbation | Alters | Objective? | Candidate space? | Future info? | Impossible? |
|---|---|:--:|:--:|:--:|:--:|
| `input_noise` | history units/price/marketing (multiplicative noise) | no | no | no | no |
| `forecast_error_bias` | last-third `units` drift | no | no | no | no |
| `missing_values` | drops history rows | no | no | no | no |
| `uncertainty_inflation` | jitter on units/price | no | no | no | no |
| `constraint_tighten` / `constraint_relax` | scales `cash_cap`/`inventory_cap`/`capacity_cap`/`price_ceiling_pct` **in the seeded goal only** | **no** (the exogenous scorer always uses `scenario.constraints`, untouched) | no | no | no |
| `distribution_shift` | scales last-third `units` | no | no | no | no |
| `contradictory_signals` | pushes recent units **and** price up together | no | no | no | no |
| `extreme_but_feasible` | alternating ±swings on units; nudges caps toward the edge | no | no | no | stays feasible |
| `adversarial` | compresses historical price range toward its median | no | no | no | no |

All perturbations are **class A — inputs only**. Ground-truth parameters and the
scored `scenario.constraints` are never touched (`harness.run_instance` passes
the true `scenario` to every `gt.*` call and only the realised *history* to the
perturbation). No candidate-space change, no future leak, no infeasible
scenario.

Caveat: because the harness does not thread abstract constraints
(`cash_cap` etc.) into the production goal in a way the pipeline consumes, the
`constraint_tighten/relax` perturbations have **little effective bite** on the
pipeline — consistent with their observed ~0 AUC. This limits what the
constraint-stress rows can show, but does not invalidate them.

**"No perturbation reached 50 % degradation."** Verified: every curve has
`severity_at_50pct_degradation = null`. AUC-degradation range across all
perturbation×condition curves is **[−0.057, +0.039]** (negative = regret fell).
The only clear degrader is `contradictory_signals` (D AUC +0.039); several
noise perturbations *reduce* C/D regret. Descriptive only; not in the
confirmatory family.

*Issue R-1. SEVERITY: Minor. TYPE: implementation. AFFECTS: none. ACTION: should
disclose — `constraint_tighten/relax` barely perturb the pipeline (no path from
the abstract cap into the seeded goal), so those two rows are near-inert by
construction.*

---

## 16. Mechanism Audit (AUDIT QUESTION 13)

`mechanism.interaction_analysis`: OLS of each per-scenario contrast (`B−A`,
`C−B`, `D−B`) on 7 standardised factors, with a 5000-sample cluster bootstrap
(seed 4242) and tertile buckets, over the 80 locked scenarios.

**Factor variance decomposition (independent):**

| Factor | overall SD | between-family SD | distinct family means | verdict |
|---|---:|---:|---:|---|
| `action_space_size` | 0.866 | 0.866 | **2** | pure family dummy (8 vs 6 candidates) |
| `objective_conflict` | 0.846 | 0.842 | **2** | pure family dummy (revenue vs profit) |
| `constraint_tightness` | **0.000** | 0.000 | 1 | constant — contributes nothing (report already notes β = 0) |
| `uncertainty` | 0.025 | 0.025 | **2** | ~constant, family-level |
| `agent_disagreement` | 0.077 | 0.054 | 4 | ~70 % between-family |
| `risk_exposure` | 0.393 | 0.331 | 4 | ~85 % between-family |
| `prediction_error` | 10.33 | 3.84 | 4 | some within-family, dominated by scale/outliers |

With only **4 locked families**, there are at most ~3 effective between-cluster
degrees of freedom. 3 of 7 regressors are family dummies, 1 is constant, and the
rest are ≥ 70 % between-family. The reported associations ("`D_vs_B` worsens with
`uncertainty` β +0.19 and `agent_disagreement` β +0.22, CIs excluding 0") are
**very largely a re-encoding of "`D_vs_B` differs across the 4 families," with the
families ordered by their (family-constant) factor values.** The bootstrap CIs
under-state the true uncertainty because they resample scenarios within a fixed
4-family structure.

**Threats present:** family confounding (dominant), effective n ≈ 4 clusters not
80, multiple factors ≈ collinear with family identity, tertile buckets that
mostly separate families. Regression-to-the-mean is a lesser concern (the
contrasts are not selected on an extreme). Not causal (correctly labelled).

**What the mechanism analysis can support:** a *descriptive* statement that
`D_vs_B` is negative on the two degraded-observation families and positive on the
two agent-adversarial families, and that this ordering lines up with declared
uncertainty and measured agent disagreement. **What it cannot support:** any
factor-level effect size, any claim that uncertainty *per se* (rather than family
membership) drives the degradation, or any inference beyond the 4 families.

*Issue M-1. SEVERITY: Moderate. TYPE: statistics. AFFECTS: mechanism section
(already exploratory). ACTION: should disclose — state n_effective ≈ 4 families;
3/7 factors are family dummies; coefficients are not interpretable at the factor
level; downgrade to "family-level description."*

---

## 17. Failure-Case Reconstruction (AUDIT QUESTION 14)

Independently reconstructed rankings from raw records match the report:

| Reported | Reconstructed | Match |
|---|---|:--:|
| best `D−B` = top 5 all `missing_observations` (B 1.0 → D 0.05–0.23) | `missing_observations__{0015,0014,0000,0011,0018}`, mean `D−B` −0.95…−0.75, **seed SD 0.00–0.03** | ✅ stable |
| worst `D−B` = top 5 all `competing_objectives` (B 0.0 → D 0.57–0.66) | `competing_objectives__{0012,0005,0006,0018}` then `asymmetric_risk__0003`, mean `D−B` +0.66…+0.57 | ✅ family, but see caveat |
| highest abs `D` regret = all `promotion_decision` | confirmed (D 0.68–0.87 on that family) | ✅ |
| greedy beats D | **73 / 80** locked scenarios | ✅ (report says "every promotion_decision + some missing_observations"; actual is nearly universal) |
| naive beats D | **37 / 80** | consistent |
| near-oracle D (≤ 0.02) | 1 scenario | ✅ |

**Seed stability caveat.** The "worst `D−B`" `competing_objectives` scenarios
have **seed SD 0.23–0.38** with per-seed `D−B` ranging **0.0 to 1.0** — i.e. on
some seeds D matches B and on others D is maximally worse. The
`missing_observations` "best `D−B`" cases are rock-solid (seed SD ≈ 0.00–0.03).
So the *recovery* story is stable; the *worst-case* story is partly seed noise on
`competing_objectives` (`asymmetric_risk` worst cases are stable, seed SD ≈
0.08). Not cherry-picked, but the instability should be stated.

*Issue F-1. SEVERITY: Minor. TYPE: interpretation. AFFECTS: failure-case
narrative. ACTION: should disclose — `competing_objectives` `D−B` is
seed-unstable (range 0–1); the stable worst-case family is `asymmetric_risk`.*

---

## 18. Agent Audit (AUDIT QUESTION 15)

From `analysis_supplement.json` + reconstruction of the pick distributions:

| Quantity | Value | Reading |
|---|---|---|
| Business-Analyst score range (mean per instance) | **0.009** | inert — near-constant across actions |
| Financial-Advisor score range | 0.573 | active output |
| Risk-Manager score range | 0.708 | active output |
| Inter-agent agreement (mean) | 0.634 | moderate |
| D changes selection vs single-agent C | **10.6 %** of instances | the RM-gate + optimizer rarely overrides C |
| D changes selection vs greedy | **82.1 %** | D's pick is usually different from the first-order heuristic |
| `C − B` mean / `D − B` mean | +0.030 / +0.034 | both null (§12) |

**Distinguishing the three senses:**

* **Active outputs** — YES for FA and RM (ranges 0.57 / 0.71), NO for BA (0.009).
* **Action-changing** — YES: on the locked families C and D produce a *spread*
  of actions where B produces one (`missing_observations`: D plays m+10 151×,
  m+20 48× vs B's constant p+10; `promotion_decision`: D spreads over
  p+10/p+5/m+10/p−3).
* **Objective-improving** — NOT detectably: `D_vs_B` and `C_vs_B` are null, and
  the family-level effect is bimodal (helps on the 2 degraded-observation
  families, hurts on the 2 agent-adversarial families).

The report's statement *"agents are active but net objective contribution is
indistinguishable from zero"* is **supported as worded**, with the refinement
that (a) one of the three agents (BA) is essentially inert, and (b) the null is
underpowered (§11), so "indistinguishable from zero" means "not detected," not
"shown to be zero."

*Issue A-1. SEVERITY: Minor. TYPE: interpretation. AFFECTS: agent section.
ACTION: should disclose — BA agent is inert (range 0.009); "net contribution
indistinguishable from zero" is an underpowered non-detection.*

---

## 19. Baseline Fairness (AUDIT QUESTION 16)

| Baseline | Objective access | Candidate space | Info available | Feasibility | Fair contest with D? |
|---|---|---|---|---|---|
| `naive` | none (fixed `()`); calls `evaluate` only to *report* its value | n/a (fixed action) | none | scored feasible | **Yes** — a fixed do-nothing policy; `D_vs_naive` is clean (both are objective-blind at selection). Result: null. |
| `greedy` | **full** — computes `evaluate` at ±1 % on each lever (a first-order oracle) | snaps to the discrete set | exact local gradient of the true objective | yes | **No** — greedy queries the true objective; A/B/C/D structurally cannot (§6). Label: *objective-gradient reference*. |
| `oracle` | **full** — enumerates `evaluate` over the candidate set | the shared discrete set + no-op | exact objective | yes | **No** — upper bound by construction; correctly labelled. |
| `classical_optimizer` | **full** — SLSQP on `evaluate`, then projects to the discrete set | continuous box + cash constraint → discrete | exact objective | yes | **No** — optimises the *same closed form used for scoring*; its 0.084 regret is partly definitional. Report already discloses this for classical; it does **not** adequately flag that **greedy has the same unfair advantage.** |

Independent check: `classical` value never exceeds `oracle` value on any of the
80 locked scenarios (max diff 0.0) — projection is consistent, no
super-oracle artefact.

**"greedy and classical optimizer beat D" is a fair *descriptive* statement**
(the numbers are real: greedy 0.255, classical 0.084, D 0.483) but it **does
not imply** that a practitioner running a simple heuristic would beat
DecisionGPT: greedy and classical here are handed the true objective function,
whereas D (and a real practitioner) must infer the response from data that does
not contain it. The honest framing is: *"reference policies with analytic access
to the true objective substantially outperform every architecture condition;
this bounds how much of the regret is 'inherent difficulty' vs 'architecture' —
most of it is the former."*

*Issue B-1. SEVERITY: Moderate. TYPE: interpretation. AFFECTS: reference /
secondary results. ACTION: should disclose — relabel `greedy` an
"objective-gradient reference" (not a "trivial heuristic"); state explicitly
that greedy/oracle/classical all have true-objective access that A/B/C/D lack,
so `D_vs_{greedy,classical,oracle}` are difficulty benchmarks, not fair
contests.*

---

## 20. Promotion-Decision Audit (AUDIT QUESTION 17)

**Facts (reconstructed).** `promotion_decision`: eps ∈ [−2.1, −1.3] (strongly
elastic), objective = revenue, price floor −20 %. **Oracle = `price_change=−10`
on all 20/20 scenarios** (the deepest catalogued cut). **B = `price_change=+10`
on all 200 executions** (exactly wrong ⇒ regret 1.000). D spreads over
p+10 (81), p+5 (56), m+10 (33), p−3 (30) ⇒ mean regret 0.681. A = fixed p−3 ⇒
0.231. greedy = p−3 ⇒ 0.231. naive = `()` ⇒ 0.369.

**Mechanism.** `_history()` generates `units` independently of the price random
walk, so the strong true elasticity is invisible in the data. The Digital Twin,
seeing price vary while demand does not respond, infers demand is inelastic and
projects that a price increase raises revenue → B picks +10 %, the polar
opposite of the −10 % optimum. D's agent layer perturbs this toward smaller
moves and marketing, reducing but not fixing the error. A/greedy happen to play
a small price cut, which is the *right direction*, hence their low regret.

**Classification: F — a data/information problem** (the decisive parameter is
not identifiable from the provided history), compounded by **A — a real behaviour
of the Digital-Twin baseline** (it collapses to "raise price" under
non-informative data). It is **not** a ground-truth mismatch (the objective is a
standard elastic demand curve), **not** candidate-generation bias (the −10 %
action is in every condition's feasible set), and **not** an optimizer pathology
specific to D (B fails first and worse).

*Issue PD-1. SEVERITY: Major (shared with S-1). TYPE: validity. AFFECTS: primary
result. ACTION: must disclose — on this family the baseline B is not just beaten,
it is anti-optimal because the generator hides the elasticity; averaging this
family into `B_vs_A` / `D_vs_B` pins B's regret at 1.0 and dominates the
contrast.*

---

## 21. Missing-Observation Audit (AUDIT QUESTION 18)

**Facts.** `missing_observations`: wide default elasticity [−1.7, −0.6],
objective = revenue, 25–45 % of history days dropped. **Oracle varies**
(`p−10` 12/20, `m+20` 2, `m+10&p−5` 2, `p+5` 1, `p+10` 3). **B = p+10 on all
200** (regret 0.772). **D = m+10 (151/200) or m+20 (48/200)** ⇒ regret 0.260.
Best `D−B` cases here are seed-stable (seed SD ≈ 0.00–0.03).

**Trace.** input (sparse, non-informative history) → DT fit (still "raise
price") → B picks p+10 (wrong: the family mostly wants a price cut or marketing
up). D's pipeline: the agents/risk-manager down-weight the aggressive price move
and the optimizer lands on a **marketing increase** (m+10/m+20). On this family
the oracle set frequently *includes* a marketing-up action, so "shift from an
aggressive price rise to a marketing rise" is *closer* to optimal — regret drops
from 0.77 to 0.26.

**Is the recovery a genuine architectural property or a synthetic artefact?**
**Mostly artefact / bias-variance, not intelligence.** D does not identify the
elasticity (it cannot — the data does not contain it); it defaults toward a
milder, marketing-weighted action, and on a family whose optimum is "cut price
or raise marketing," a marketing raise is a lucky-adjacent choice. The mirror
image is `asymmetric_risk`, where the same conservative shift moves D *away* from
the (correct) aggressive price rise and regret rises from 0.0 (B) to 0.52 (D).
So the agent layer supplies **shrinkage toward smaller / marketing-weighted
moves**, which helps when B overshoots and hurts when B is right — a
regularisation effect, not a reasoning effect.

*Issue MO-1. SEVERITY: Moderate. TYPE: interpretation. AFFECTS: mechanism /
narrative. ACTION: should disclose — the "recovery" is a shrinkage/regularisation
artefact of the agent layer's bias toward smaller and marketing-weighted
actions, not evidence that the architecture reasons its way out of degraded
data; it is exactly offset by the harm on `asymmetric_risk`.*

---

## 22. D-vs-B Audit (AUDIT QUESTION 19)

Reconstructed: mean Δregret **+0.0337**, median +0.0 (44 ties-broken as wins for
D-worse / 36 for D-better; **0 exact ties**, n_nonzero 80), SD 0.508, 95%
cluster-bootstrap CI **[−0.0776, +0.1428]**, Wilcoxon p 0.539, Holm p **1.0**,
rank-biserial +0.10.

**Statistical characterisation.**
* This is a **failure to reject** H₀ of no difference.
* It is **not** evidence *for* equivalence: no equivalence test (e.g. TOST
  against ±0.10) was pre-registered or run, and the CI upper bound (+0.143)
  **exceeds** the MEI, so a practically-meaningful disadvantage for D is not
  excluded. The lower bound (−0.078) is inside ±MEI.
* It is **not** "evidence of a negligible effect" for the same reason, and
  because the test was underpowered relative to plan (§11: observed SD 1.8×
  planned).

**Strongest defensible statement:** *"No statistically significant incremental
change in exogenous regret from adding the agent layer to the digital-model
baseline was detected (Δ = +0.034, 95% CI [−0.078, +0.143], Holm p = 1.0); the
interval does not exclude a difference as large as the pre-registered minimum
effect of interest, so this is a non-significant result under a test that was
underpowered relative to its design assumptions, not a demonstration of
equivalence."*

The report's wording ("null," "no measurable improvement," "not detectable")
is acceptable and does **not** claim equivalence — but it must be paired with the
power caveat (§11) and must not be paraphrased elsewhere as "D and B are the
same" or "the agent layer has no effect."

*Issue DB-1. SEVERITY: Major (statistics/interpretation). AFFECTS: primary
result. ACTION: must disclose — add the "underpowered failure to detect, not
equivalence, CI exceeds MEI" framing wherever the `D_vs_B` null is stated.*

---

## 23. D-vs-A Audit (AUDIT QUESTION 20)

Reconstructed: mean Δregret **+0.1088**, 95% CI **[+0.0585, +0.1607]** (excludes
0 **and** exceeds the 0.10 MEI), Wilcoxon p 6.4e−4, Holm p 0.00255,
rank-biserial +0.225, W/T/L 49/0/31. Observed SD 0.231 (below plan) ⇒ this test
was **well-powered** and the rejection is **robust**.

**What A is.** `_noop_action(feasible)` ⇒ A plays `price_change=−3` on every
revenue locked scenario and `price_change=+5` on every profit locked scenario —
a **fixed, hand-constructed minimal-intervention policy**, not an ablation of a
"prediction" stage (a genuine prediction-only condition would either recommend
nothing → the `naive` baseline, or use the forecast to choose — neither is A).

**Interpretation.** `D_vs_A` establishes, robustly, that *the full DecisionGPT
pipeline attains higher exogenous regret than a fixed policy of "apply the
smallest catalogued price move"* on these 4 families — 2 of which
(`promotion_decision`, `missing_observations`) happen to reward a small price cut,
so A's fixed −3 % is well-aligned there. It is a **real and reproducible
finding**, but it is a comparison against a **specially constructed intervention
policy**, not a clean architectural statement that "prediction beats the full
system." The scientifically clean sibling is `D_vs_naive` (vs the literal status
quo), which is **null** (−0.028, CI [−0.091, +0.035]).

*Issue DA-1. SEVERITY: Major. TYPE: interpretation. AFFECTS: the only significant
architecture contrast. ACTION: must disclose — always state `D_vs_A` as "worse
than a fixed minimal-move policy," lead the abstract/headline with `D_vs_naive`
(null) as the "vs doing nothing" comparison, and do not phrase `D_vs_A` as
"the full system is worse than prediction-only."*

---

## 24. External Validity (AUDIT QUESTION 21)

Confirmed: the study supports **only** a controlled synthetic
architectural/component evaluation, and only within the tested regime
(non-identifiable response, 4 of ~6 structural regimes). It provides **zero**
support for real-SME effectiveness, Indian-SME validation, customer-behaviour
claims, real business ROI, deployment performance, or real-world causal effects.
The report's §20 evidence-boundary section and the readiness doc's grade of
**F** for external validity are accurate and must be preserved. The forbidden-
claim scan (`forbidden_claim_scan.json`, 0 prohibited) was re-run and is clean.

*Issue: none. ACTION: no action — keep the boundary section verbatim.*

---

## 25. Reproducibility (AUDIT QUESTION 22)

Independently verified without re-running the experiment:

* Frozen manifest SHA, scenario-manifest SHA (file == recorded), `suite_checksum`
  (manifest == config), `locked_test_family_checksum` (recomputed == recorded),
  pre-registration doc SHA (file == `config.prereg.doc_sha256`), `results.json`
  SHA (file == recorded), architecture fingerprint (in `results.json`),
  `PipelineOptions().label() == "full"` — **all match**.
* `git diff` on all production + frozen + paper paths — **empty**.
* All 80 oracle values reproduce from independent enumeration; all four primary
  contrasts + Holm reproduce to full precision from `results.json`.
* `REPRODUCIBILITY_AUDIT.md` (14/14) is corroborated.

The one thing **not** re-verifiable here is the frozen pipeline's own run-to-run
determinism (the locked test was not re-run, per the audit rules); the study's
own evidence for it is "800/800 completed, 0 errors, stable fingerprint," plus
the observation that B is bit-identical across all 10 seeds.

*Issue: none. ACTION: no action.*

---

## 26. Claim-to-Evidence Matrix (AUDIT QUESTION 23)

| # | Claim | Evidence in this study | Directly supported? | Qualification required |
|---|---|---|---|---|
| 1 | Decision Simulation improves over Prediction | `B_vs_A` mean +0.075 (B **worse** on average), Holm p 0.015 but CI [−0.069,+0.219] includes 0, rank-biserial −0.10 | **No** — significant on signed-rank, but CI includes 0 and direction is inconsistent; B is a constant policy (§6) | must state "no directional improvement; B is a constant +10% price policy" |
| 2 | Single agent adds value over Decision Simulation | `C_vs_B` null (p 0.505, CI [−0.078,+0.137]) | **No** | underpowered non-detection |
| 3 | Full system improves over Decision Simulation | `D_vs_B` null (p 1.0 Holm, CI [−0.078,+0.143]) | **No** | underpowered; CI exceeds MEI; not equivalence (§22) |
| 4 | Full system improves overall decision quality | D mean regret 0.483 > A/B/C and ≈ naive; every reference policy better | **No — evidence points the other way** | within the non-identifiable regime only |
| 5 | Full system is worse than Prediction-only | `D_vs_A` +0.109, CI [+0.059,+0.161], Holm p 0.0026, well-powered | **Partly** | A is a fixed smallest-move policy, not a prediction ablation; use `D_vs_naive` (null) for "vs doing nothing" (§23) |
| 6 | Full system beats naive | `D_vs_naive` −0.028, CI [−0.091,+0.035] | **No (null)** | statistically tied |
| 7 | Full system beats greedy | `D_vs_greedy` +0.227 (D **worse**), p 7e−14 | **No — greedy beats D** | greedy has true-objective gradient access (§19); difficulty benchmark, not fair contest |
| 8 | Full system beats classical optimizer | `D_vs_classical` +0.399 (D **worse**) | **No — classical beats D** | classical optimises the scoring function itself; partly definitional |
| 9 | Agents are active | FA range 0.573, RM 0.708; D action-spread vs B's constant | **Yes** | BA agent is inert (range 0.009) |
| 10 | Agents improve decisions | `C_vs_B`, `D_vs_B` null; family effect bimodal | **No** | underpowered non-detection |
| 11 | Agents hurt decisions under some conditions | `asymmetric_risk` D 0.52 vs B 0.00; `competing_objectives` D 0.47 vs B 0.02 | **Descriptively yes**, on 2 locked families | seed-unstable on `competing_objectives` (range 0–1); stable on `asymmetric_risk` |
| 12 | Agent disagreement associated with `D−B` degradation | OLS β +0.22, bootstrap CI excludes 0 | **Weak** | confounded with family (n_eff ≈ 4); factor ≈ 70% between-family |
| 13 | Uncertainty associated with `D−B` degradation | OLS β +0.19, CI excludes 0 | **Weak** | `uncertainty` factor has 2 distinct values = family dummy (§16) |
| 14 | Robustness findings (no perturbation → 50% degradation; noise sometimes helps C/D; `contradictory_signals` the one degrader) | `robustness_results.json`, 720 runs, AUC ∈ [−0.057,+0.039] | **Yes, descriptively** | 20-scenario × 2-seed subsample; `constraint_*` perturbations near-inert |
| 15 | Mechanism findings (`D−B` negative on degraded-obs families, positive on agent-adversarial families; agent layer = shrinkage toward smaller/marketing moves) | pick distributions + per-family regret | **Yes, as family-level description** | not factor-level; not causal |
| 16 | RQ2 ("multi-agent layer improves decision quality") is refuted | `D_vs_B`, `C_vs_B` null; `D_vs_A` shows D worse than a fixed policy | **"Not supported," not "refuted"** — an underpowered null cannot refute; but combined with the frozen study it is *unsupported and directionally negative* | state as "no supporting evidence; consistent with the frozen study's negative finding" |
| 17 | Results generalize to SMEs | none | **No** | forbidden |
| 18 | Results establish real-world effectiveness | none | **No** | forbidden |

---

## 27. Remaining Threats

| ID | Threat | SEV | TYPE | AFFECTS | ACTION |
|---|---|---|---|---|---|
| S-1 / PD-1 | B is a degenerate constant "+10% price" policy on the entire locked set; the generator hides the objective's decisive parameters from all conditions | Major | validity | primary | must disclose; scope every A/B/C/D conclusion to "non-identifiable-response regime" |
| P-1 / DB-1 | Observed paired-difference SD is 1.8–2.3× the planned value; the `D_vs_B`/`B_vs_A` tests were underpowered; the `D_vs_B` CI exceeds the MEI | Major | statistics | primary | must disclose planned-vs-achieved power; "failure to detect," not "equivalence" |
| C-1 / DA-1 | Condition A is a fixed minimal-move policy, not a prediction ablation; `D_vs_A` (the only significant architecture contrast) is "vs a constructed policy" | Major | interpretation | primary/significant contrast | must disclose; lead with `D_vs_naive` (null) |
| B-1 | greedy (and oracle, classical) have analytic access to the true objective that A/B/C/D structurally lack | Moderate | interpretation | reference results | should disclose; relabel greedy an "objective-gradient reference" |
| G-1 | Locked test = 4 of ~6 structural regimes; 3 of 4 are degraded/adversarial; blind split but narrow coverage | Moderate | bias/validity | generality of primary | should disclose |
| M-1 | Mechanism OLS: n_eff ≈ 4 families, 3/7 factors are family dummies, 1 constant; factor-level claims are family confounding | Moderate | statistics | mechanism (exploratory) | should disclose; downgrade to family-level description |
| E-1 | A and B have zero seed variance (0/80); "10 independent replicates" / "800 executions" overstates the primary evidence | Moderate | statistics/interpretation | headline framing | should disclose; effective design = 80 clusters |
| MO-1 | The `missing_observations` "recovery" is a shrinkage artefact of the agent layer's bias toward smaller/marketing moves, exactly offset by harm on `asymmetric_risk` | Moderate | interpretation | narrative | should disclose |
| O-1 | The objective's optima are boundary actions set by unobservable parameters | Moderate | validity | interpretation | should disclose |
| F-1 | `competing_objectives` `D−B` is seed-unstable (per-seed range 0–1); listed as top worst-case | Minor | interpretation | failure-case narrative | should disclose |
| A-1 | BA agent inert (range 0.009); "net contribution ≈ zero" is an underpowered non-detection | Minor | interpretation | agent section | should disclose |
| R-1 | `constraint_tighten/relax` perturbations barely bite the pipeline | Minor | implementation | none | should disclose |
| G-2 | "17 families" overstates distinct decision structures (~6) | Minor | interpretation | none | should disclose |
| L-1 | Unfalsifiable residual: analyst could have viewed `results.json` before finalising the (pre-registered, parameter-free) `analyze` code | Minor | reproducibility | none | no action |

**No Critical issue and no INVALID-PRIMARY-EVIDENCE finding.** The reproduction
is exact; the primary contrast is clean in construction; the risk is
over-claiming a *negative*, which the qualifications above contain.

---

## 28. Final Verdict

### FINAL VERDICT: **B — SOUND WITH MATERIAL QUALIFICATIONS**

The evaluation's apparatus (metric independence, oracle correctness,
candidate-space and information-set fairness, statistical implementation,
multiplicity control, reproducibility, non-interference with the frozen study and
production) is **verified and sound**. The evaluation does **not** measure "does
the multi-agent architecture improve decision quality" in a general sense —
because on the tested suite the digital-model baseline (B) degenerates to a
constant policy, the "prediction" condition (A) is a hand-built fixed policy, the
reference policies are objective-aware, and the tested regime is one where the
objective's decisive parameters are unlearnable from the provided data. It
**does** support a narrow, reproducible, directionally-negative statement, and it
is consistent with the frozen study. Grade the method B; grade the *evidential
reach of the conclusions as currently written* C until the §27 disclosures are
added.

### TOP 5 REMAINING THREATS
1. **B is a degenerate constant "+10% price" policy on 100% of the locked set** —
   the primary comparison is against a constant, not an adaptive baseline
   (S-1/PD-1).
2. **The `D_vs_B` / `B_vs_A` tests were underpowered** — observed variance
   1.8–2.3× the pre-registered assumption; the `D_vs_B` CI does not exclude a
   more-than-MEI disadvantage for D (P-1/DB-1).
3. **`D_vs_A` — the only significant architecture contrast — compares against a
   constructed fixed minimal-move policy**, not a prediction ablation (C-1/DA-1).
4. **The tested regime hides the objective's decisive parameters from every
   data-driven condition**, so no A/B/C/D condition could succeed; the
   objective-aware baselines "winning" is near-tautological (S-1, B-1, O-1).
5. **Locked test covers 4 of ~6 structural regimes, 3 of them
   degraded/adversarial**, and the mechanism analysis has ~4 effective clusters
   (G-1, M-1).

### TOP 5 STRONGEST EVIDENCE POINTS
1. **Metric independence is genuine** — `ground_truth.py` imports nothing from
   the pipeline, never reads history, is a distinct closed form; verified by AST
   + structural trace.
2. **The oracle is exactly correct** — 80/80 independent-enumeration agreement;
   no degenerate normalisation spans; classical never exceeds it.
3. **Every primary statistic reproduces to full precision** from `results.json`
   (means, Wilcoxon p to 1e−15, cluster-bootstrap CI, rank-biserial, W/T/L,
   Holm).
4. **Candidate-space and information-set fairness hold** — 800/800 identical-set
   invariant, D never picks outside the set, no objective/oracle/future leak into
   selection.
5. **Full reproducibility and non-interference** — all checksums match; frozen
   manifest byte-identical; production, frozen results, and the IEEE paper
   untouched; R0/D0 intact; R3 not promoted.

### EXACT CLAIMS THE IEEE PAPER MAY MAKE
* "We built a pre-registered, reproducible, exogenously-scored controlled
  evaluation harness for component ablation of a decision-support architecture;
  all artifacts and analyses reproduce from fixed seeds."
* "On a synthetic locked-test suite in which the price/marketing response is
  **not identifiable from the provided history**, adding the rule-based
  multi-agent evaluation layer to the digital-model baseline produced **no
  statistically significant change** in exogenous normalised regret
  (Δ = +0.034, 95% CI [−0.078, +0.143], Holm p = 1.0); this is an underpowered
  non-detection, not a demonstration of equivalence."
* "The full pipeline did not outperform the literal status-quo policy
  (`D_vs_naive` null) and attained higher regret than a fixed
  minimal-intervention policy on the four locked families (`D_vs_A`, Holm
  p = 0.003), which are drawn from degraded-observation and
  agent-adversarial regimes."
* "Reference policies with analytic access to the true objective (greedy /
  classical optimiser / oracle) substantially outperform every architecture
  condition, indicating that most of the observed regret reflects the inherent
  non-identifiability of the tested regime rather than the architecture."
* "Descriptively, the agent layer behaves as shrinkage toward smaller,
  marketing-weighted actions: it reduces regret where the digital-model baseline
  overshoots (degraded-observation families) and increases it where the baseline
  is already near-optimal (agent-adversarial families); the net is not
  distinguishable from zero on this suite."
* "This evaluation is synthetic and controlled; it makes no real-world, SME,
  ROI, deployment, or causal claim."
* "The findings are consistent with, and independent of, the frozen 12×5 study;
  the two are not pooled."

### EXACT CLAIMS THE IEEE PAPER MUST NOT MAKE
* "The multi-agent layer adds no value" / "the agent layer has no effect" /
  "D and B are equivalent." (Underpowered null; CI exceeds MEI.)
* "The full system is worse than prediction-only." (A is a constructed fixed
  policy; use "worse than a fixed minimal-move policy," and note `D_vs_naive` is
  null.)
* "Decision simulation does not help over prediction." (`B_vs_A` CI includes 0;
  B is a constant policy.)
* "A simple greedy heuristic beats DecisionGPT" **without** "greedy is given the
  true objective gradient."
* "RQ2 is refuted." (Say "unsupported; directionally negative; consistent with
  the frozen study.")
* Any statement of real-SME effectiveness, Indian-SME validation, ROI,
  customer-behaviour, deployment success, or real-world causal impact.
* Any claim from the internal `goal_achievement` metric (B 0.895 vs D 0.315).
* "17 distinct decision environments" (there are ~6 structural regimes).
* "800 independent locked-test executions" as a measure of evidential weight
  (effective n = 80 scenario clusters; A and B carry no seed replication).
* Promotion of R3 or any change to R0/D0.

### WHETHER PAPER INTEGRATION IS NOW SAFE
**Conditionally yes — as a negative-result / controlled-evaluation /
reproducibility paper, after the §27 disclosures (S-1, P-1, C-1, DA-1, DB-1,
B-1, E-1, G-1, M-1) are written into the methods and threats-to-validity
sections and the claim language is tightened to the "EXACT CLAIMS THE PAPER MAY
MAKE" list above.** It is **not** safe to integrate the current headline
phrasings ("full system worse than prediction-only," "multi-agent layer adds no
value," "RQ2 refuted") verbatim. The primary numbers themselves are correct and
may be reported as-is with the qualifications attached. Do not integrate any
number from this study into a claim of real-world or SME effectiveness.

---

*End of independent audit. No study artifact, production file, pre-registration,
or paper was modified in producing this document.*
