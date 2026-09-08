# R1 — Hostile Peer Review (simulated IEEE reviewer)

**Stance:** a skeptical IEEE reviewer whose default is *reject*. Every criticism
below is one a real reviewer could raise. For each: **severity** (Critical /
Major / Minor), **evidence**, **required response**, and whether it is
**fixable without a new experiment**. This complements the machine audit
(`experiments/r1/MACHINE_AUDIT.md`, 26/26), the independent recomputation
(`experiments/r1/independent_recheck.json`, 75/75), and the self-audit
(`docs/R1_AUDIT.md`).

The manuscript under review reports a **NEGATIVE** primary result: the full
downstream stack (D) produced **higher** exogenous normalised regret than the
corrected Decision Simulation (B) — `D_vs_B` mean **+0.085**, 95 % CI
[+0.048, +0.123], Holm p ≈ 0, rank-biserial −0.469, robust to
leave-one-family-out (+0.050 … +0.159) and to 18/18 robustness cells.

---

## R1 — Novelty

**Criticism.** "Controlled synthetic ablations of decision-support pipelines are
not new; the negative result is a non-finding."
**Severity:** Minor.
**Evidence / response.** The contribution is not 'we ran an ablation' but
(i) the *diagnosis* that the shipped Decision Simulation ignores the decision
variables (price+marketing 2.2 % SHAP; projected units exactly flat over a 3×
price sweep; `docs/R1_DT_DIAGNOSTIC.md`), (ii) the *minimal research-only
correction* that removes that bottleneck without touching production, and
(iii) the finding that once B is a *functioning* optimiser, the downstream
multi-agent/risk/optimisation stack **subtracts** objective decision quality
from it — a component-level result that the common "add agents → better"
assumption does not predict. The negative result is informative because B beats
A (value enters), C ≈ B (agent adds nothing), D < C < B (value is lost), and the
degradation is characterised mechanistically.
**Fixable without a new experiment?** Yes — framing/positioning only.

## R1 — Methodology (synthetic scenarios legitimate?)

**Criticism.** "Synthetic scenarios can be constructed to produce any desired
outcome."
**Severity:** Major.
**Evidence / response.** The 27 families, their parameter ranges and
distributions, the master seed, the family→partition rule, the N, and the 10
seeds were **frozen in a pre-registration** (`docs/R1_PREREGISTRATION.md`) at git
commit `22ce18c` **before** the locked run; the run script refuses to proceed
unless the frozen doc/manifest SHAs match. The families are structurally distinct
(elasticity regime, marketing regime, constraint type, seasonality strength,
observation degradation, delay, regime shift, nonlinearity), not cosmetic
relabels. The **direction is preserved under leave-one-family-out** (every
removal still D-worse) and under **18/18** pre-registered robustness
perturbations, so the result is not an artefact of any one family or of a benign
data regime.
**Residual concern (must disclose).** Two families (`nonlinear_response`,
`demand_saturation`) are *censored-demand*, where the OLS elasticity estimate is
biased mild and B has a residual over-price failure — these are the only families
where D helps. The aggregate is D-worse with **and without** them (LOFO
+0.114 / +0.159 with them removed). Disclosed in `docs/R1_RESULTS.md` §12 and
§17.
**Fixable without a new experiment?** The disclosure is already present; a
follow-up study with an uncensored elasticity estimator would strengthen it, but
that is future work.

## R1 — Ground truth (independent?)

**Criticism.** "If the scorer shares code or parameters with the simulator, the
comparison is circular."
**Severity:** Critical (if true).
**Evidence / response.** `ground_truth.py` (System B) imports only
`{__future__, dataclasses, math, numpy, scipy.optimize, typing}` (AST-verified in
the machine audit) and is byte-identical to the V1 module. It is an
**additive-linear** model; the history generator (System A) is **log-linear**;
the R1 correction is **constant-elasticity on the production baseline** — three
different functional forms. The System-A ↔ System-B parameter coupling is a
*noisy monotone map* (`eps = clip(a_elast + N(0, 0.35), …)`), not shared code.
The oracle is reproduced by independent enumeration on **408/408** locked
scenarios. `r1_dt.py` imports no `ground_truth` / `decision_service` /
`decision_architecture` (AST-verified).
**Fixable without a new experiment?** N/A — the check passes.

## R1 — Architecture (faithful to the intended system?)

**Criticism.** "You changed the Digital Twin, so this is not DecisionGPT."
**Severity:** Major.
**Evidence / response.** The correction replaces **only** the scenario-side
`expected_units_sold` / `expected_revenue` / `expected_profit`; the baseline
forecast level, the R0 risk score, the production model, the candidate action
space, the three agents, the optimiser (formula `v2`, λ = 1), and the
`analyze_goal` control flow are unchanged and run on the corrected numbers. It is
installed per-instance by `r1.harness` and removed afterwards; production
`digital_twin_service.py` is byte-identical on disk (git-clean). The paper
**never** calls this the production Digital Twin — it is consistently the "R1
research-only action-responsive Decision Simulation wrapper" (terminology
enforced by `scripts/scan_r1_claims.py`).
**Fixable without a new experiment?** Yes — this is a terminology/scoping matter,
already handled.

## R1 — Research-only correction (could it bias the result?)

**Criticism.** "The team wrote the demand model that B and D both use — a
positive `D_vs_B` would be 'about the wrapper', so a negative one is too."
**Severity:** Major.
**Evidence / response.** The wrapper is symmetric across B/C/D (identical demand
numbers feed all three); B and D differ only in the intended downstream
components. `ε̂` is *estimated from data* (median pre-lock error 0.084; **0 %
fallback in the locked run**), clipped only to enforce a downward-sloping demand
curve — an economic prior, not favourable tuning; no coefficient is hand-set.
The scorer is a *different* functional form, so B and D are graded against
something the wrapper does not target. Crucially, the primary question ("does the
stack add value **over a functioning B**?") is answered by the *contrast*
`D_vs_B`, whose sign does not depend on the wrapper's exact elasticity form
because both conditions inherit it.
**Residual concern (must disclose).** The wrapper makes B stronger than the
shipped system; the result therefore speaks to the *architecture given a
functioning Decision Simulation*, not to the current production stack as
deployed. Disclosed in `docs/R1_RESULTS.md` §17 and `docs/R1_FINAL_REPORT.md` §4.
**Fixable without a new experiment?** Disclosure present; a wrapper-form
sensitivity (e.g. linear vs power) is reasonable future work.

## R1 — Information fairness

**Criticism.** "Do A/B/C/D get the same information?"
**Severity:** Critical (if not).
**Evidence / response.** `docs/R1_INFORMATION_BOUNDARY.md` gives the matrix. All
of A/B/C/D see the seeded history, goal, and candidate set; B/C/D additionally
see the `ε̂/â` **estimated from that same history**. **None** receives the true
scenario elasticity, the oracle, the objective value, future outcomes, or test
labels (machine-verified: `r1_dt` imports none of these; oracle exact; identical
action set on all 4 080 instances; `ground_truth` called only post-selection —
the harness fairness logic is the V1 code, previously audited).
**Fixable without a new experiment?** N/A — passes.

## R1 — Baselines (advantaged?)

**Criticism.** "You compare D to an oracle and a classical optimiser that see the
true objective — of course D loses."
**Severity:** Minor (it is disclosed) / Major (if the paper leaned on it).
**Evidence / response.** `greedy`, `classical_optimizer`, and `oracle` have
analytic access to System B; this is stated at **every** mention and they are
labelled *external computational benchmarks*, not architecture competitors. The
paper's central claim rests on `D_vs_B` (same information, same action space),
not on the benchmark comparisons. `D_vs_naive` (D beats do-nothing) is reported
as the honest "is D better than nothing" contrast and is **not** conflated with
`D_vs_B`.
**Fixable without a new experiment?** Yes — already handled.

## R1 — Statistics (scenario clustering)

**Criticism.** "You have 4 080 evaluations — are you treating them as 4 080
independent samples?"
**Severity:** Critical (if so).
**Evidence / response.** **No.** The unit of analysis is the **scenario**
(`statistical_results.json.unit_of_analysis == "scenario"`, machine-verified);
the 10 seeds are aggregated to the scenario mean *before* every paired test; the
cluster bootstrap resamples **scenarios**; Wilcoxon is at n = 408. This is stated
in `docs/R1_RESULTS.md` §16 and reproduced independently
(`independent_recheck.json` — n = 408, W/T/L 99/35/274, matches).
**Fixable without a new experiment?** N/A — passes.

## R1 — Power (prospective?)

**Criticism.** "Post-hoc power, or under-powered."
**Severity:** Major.
**Evidence / response.** Simulation-based power was computed from
**development-stage variance only** (pilot `D_vs_B` SD 0.282, rounded up to 0.30;
`power_assumptions.json._variance_source` records this) **before** the locked
run; `estimated_power = 0.894` at MEI 0.05, N 408, 10 seeds. N was **raised** from
a 126-scenario draft (≈ 0.40) — the effect of interest was **not** lowered. The
observed effect (0.085) is 1.7× the MEI and the CI is well clear of 0.
**Residual concern (must disclose).** `simulate_power` does not model exact ties;
the locked contrast has 35/408 exact ties (n_nonzero 373), so achieved power is
slightly below 0.894 — but the p-value (5.4 × 10⁻¹⁰) and CI leave no ambiguity.
Disclosed in `docs/R1_RESULTS.md` §8 and `docs/R1_AUDIT.md` I.
**Fixable without a new experiment?** Disclosure present; a tie-aware
prospective-power method would be a methods improvement, not a result change.

## R1 — Multiplicity

**Criticism.** "Multiple contrasts, no correction / p-hacked family."
**Severity:** Major.
**Evidence / response.** Holm–Bonferroni over the pre-registered confirmatory
family **exactly** `{B_vs_A, C_vs_B, D_vs_C, D_vs_B}` (machine-verified). Raw and
adjusted p both reported. Secondary contrasts (`D_vs_A`, `D_vs_{naive, greedy,
classical, oracle}`, `A/B/C_vs_oracle`) are labelled descriptive and excluded
from the correction; none is presented as confirmatory. `D_vs_B` survives at
Holm p ≈ 0.
**Fixable without a new experiment?** N/A — passes.

## R1 — Seeds treated as independent samples

**Criticism.** (Same as clustering, restated.) "Are the 10 seeds inflating n?"
**Severity:** Critical (if so).
**Evidence / response.** No — see *Statistics*. Seeds are stochastic replication
within a scenario; the report explicitly distinguishes structural (scenario)
from stochastic (seed) replication and never uses 4 080 as the n. A seed-level
sensitivity (per-seed `D−B`) is discussed alongside the scenario-level primary.
**Fixable without a new experiment?** N/A — passes.

## R1 — External validity

**Criticism.** "This tells us nothing about real businesses."
**Severity:** Major (for over-claiming) / expected (for a synthetic study).
**Evidence / response.** The paper states in the abstract, discussion,
conclusion, and a dedicated Threats-to-Validity section that R1 establishes
**nothing** about real-world / SME / Indian-SME / ROI / customer / causal /
deployment / human-decision / LLM-agent effects, or about the production Digital
Twin as deployed; that it evaluates a *research-only corrected* Decision
Simulation in a controlled synthetic environment with a finite family set; and
that it does **not** show multi-agent systems are useless in general. A
forbidden-term scan (`experiments/r1/forbidden_term_scan.json`) returns **0
prohibited**.
**Fixable without a new experiment?** Yes — bounding language is already present
and enforced.

## R1 — Mechanism (overclaimed?)

**Criticism.** "You claim the risk gate + optimiser cause the degradation without
a causal design."
**Severity:** Major.
**Evidence / response.** The report uses **associational** language throughout:
"the mechanism analysis **localises** much of the observed degradation to the
transition from C to D"; the OLS coefficients are labelled associational,
family-clustered (effective cluster count = 12), and **not interpreted at the
factor level**; no per-component causal attribution is asserted. The concrete,
model-free facts are: D changes B's action on 57 % of instances and, when it
does, worsens the outcome 2 : 1 (1 573 vs 763); B's optimal-action rate 62.5 %
vs D's 34.6 %; `D_vs_C` = +0.139 (rank-biserial −0.633). These are descriptive,
not causal.
**Fixable without a new experiment?** Yes — the language is already
appropriately hedged; a component-swap ablation would be a *separate* future
study.

## R1 — Negative result informativeness

**Criticism.** "A null/negative result on a synthetic benchmark is not
publishable."
**Severity:** Minor.
**Evidence / response.** The result is not a null — it is a **rejection in the
D-worse direction** (Holm p ≈ 0, CI excludes 0, |effect| 1.7× MEI, rank-biserial
−0.469), corroborated by `D_vs_C`, by the optimal-action hit-rate collapse, by
DecisionGPT's **own internal metric** (B 0.496 > D 0.364), and stable under
leave-one-family-out and 18/18 robustness cells. It is a **component-level**
finding — it separates where value enters (B > A) from where it is lost (D < B) —
which is exactly the kind of evidence the "add agents → better" literature lacks.
**Fixable without a new experiment?** Yes — this is a framing point.

## R1 — Reproducibility

**Criticism.** "Can another group reproduce this?"
**Severity:** Major.
**Evidence / response.** The pre-registration, scenario manifest (with per-
scenario `content_hash` and `suite_checksum`), raw locked results
(`results.json`), analysis script (`run_eval_r1.py analyze`), robustness output,
figure code (`r1_figures.py`), independent recheck (`independent_recheck.json`,
75/75), machine audit, checksums of every artifact, the git commit, and the
exact command sequence are all in the repo. Analysis reproduces from the frozen
raw results **without** a new locked run. Bootstrap/mechanism/power seeds are
fixed (12345 / 4242 / 777 / 20260907).
**Fixable without a new experiment?** N/A — passes; a Dockerfile /
`requirements.txt` freeze would further strengthen it (see Publication
Readiness).

## R1 — Leakage (hidden objective information)

**Criticism.** "Could any objective/oracle information reach the system?"
**Severity:** Critical (if true).
**Evidence / response.** `r1_dt` uses only the seeded `Sale` /
`MarketingCampaign` history and known operational ceilings (current inventory,
`capacity_cap`); it imports no `ground_truth`, no oracle, no objective value
(AST-verified). Fallback to generator `a_elast` is logged per instance and
**fired 0 times** on the locked run. The exogenous scorer is applied strictly
**after** action selection. Oracle exact on 408/408.
**Fixable without a new experiment?** N/A — passes.

---

## Summary for the editor

| dimension | reviewer verdict | blocking? | fixable w/o new experiment? |
|---|---|---|---|
| Novelty | acceptable (component-level, diagnostic + negative) | no | yes (framing) |
| Methodology | sound, pre-registered; one disclosed censored-demand caveat | no | disclosure present |
| Ground-truth independence | passes | no | n/a |
| Architecture faithfulness | passes (research-only, disclosed) | no | terminology (done) |
| Correction bias | disclosed; contrast is wrapper-agnostic | no | sensitivity = future work |
| Information fairness | passes | no | n/a |
| Baseline advantage | disclosed; not load-bearing | no | done |
| Statistics / clustering | correct (scenario unit) | no | n/a |
| Power | prospective, from dev variance; tie caveat disclosed | no | tie-aware method = improvement |
| Multiplicity | Holm over pre-registered family | no | n/a |
| Seeds | correct | no | n/a |
| External validity | bounded; 0 forbidden claims | no | enforced |
| Mechanism | associational, hedged | no | component swap = future study |
| Negative-result value | informative (rejection, not null) | no | framing |
| Reproducibility | strong; env freeze recommended | no | add lockfile |
| Leakage | none | no | n/a |

**No Critical issue is substantiated.** The Major issues (synthetic
legitimacy, correction framing, power ties, mechanism causality, external
validity) are all **addressed by disclosure already in the manuscript** and none
requires a new experiment. The strongest legitimate reviewer demand is a
**clearer, earlier statement** that (a) R1 tests the architecture *given a
functioning Decision Simulation*, not the shipped Digital Twin, and (b) the two
D-favourable families are censored-demand cases where B has a known residual
failure — both are present but should be foregrounded in the abstract and
discussion. Recommended decision: **accept with minor revisions** for a
component-level evaluation / negative-result venue.
