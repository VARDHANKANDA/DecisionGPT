# R1 — Independent Hostile Scientific Audit

**Auditor stance:** skeptical conference reviewer trying to find reasons to
reject the R1 result. Audit only — nothing modified, the locked test not re-run.
The machine-checkable subset is `experiments/r1/MACHINE_AUDIT.md` (26/26). This
document covers the judgement calls.

**Headline result under audit:** `D_vs_B` = +0.085 normalised regret (D worse
than the corrected Decision Simulation), 95 % scenario cluster-bootstrap CI
[+0.048, +0.123], Holm p ≈ 0, rank-biserial −0.469, D worse on 274/408
scenarios; pre-registered class **NEGATIVE**.

Verdict codes: **PASS** / **QUALIFIED** (valid but with a caveat that must be
stated) / **FAIL**.

---

## A. Ground-truth independence — **PASS**

`ground_truth.py` (System B) is byte-identical to V1 and imports only
`{__future__, dataclasses, math, numpy, scipy.optimize, typing}`. It is a
closed-form **additive-linear** model; it never reads history and is called only
after action selection. `r1_dt.py` imports no `ground_truth` /
`decision_service` / `decision_architecture` (AST-verified). Oracle exact on
408/408 locked scenarios by independent enumeration. No circularity: the history
generator (System A) is log-linear, `r1_dt` is constant-elasticity on the
production baseline, System B is additive-linear — three different functional
forms; the System-A↔System-B parameter coupling is a *noisy monotone map*
(`eps = clip(a_elast + N(0,0.35), …)`), not shared code.

## B. Information leakage — **PASS**

`r1_dt` estimates `ε̂/â` by OLS on the business's own seeded `Sale` /
`MarketingCampaign` rows — the columns the production model ingests but
under-weights. It does **not** receive the true scenario elasticity, the oracle,
the objective value, future demand, or test labels (machine-verified; the
harness fairness logic is reused unchanged from V1, where it was audited). The
horizon forecast holds price/marketing constant, exactly as production.
Fulfilment ceilings (current inventory, `capacity_cap`) are operational facts a
decision-maker knows, not the objective. Locked-run fallback rate: **0 %** — no
instance used generator parameters.

## C. Scenario generation — **QUALIFIED**

27 genuinely distinct structural families (elasticity regime, marketing regime,
constraint type, seasonality strength, observation degradation, delay, regime
shift, nonlinearity). Deterministic from `master_seed`; `suite_checksum`
reproduces; parameter ranges frozen in the manifest.

*Caveat 1 (QUALIFIED):* the R1 suite uses `master_seed = 20260907`, not the
`20260906` named in the brief. Rationale: a `20260906` sizing draft was run
through the pre-lock diagnostic; when the power analysis required a larger locked
partition (N 126 → 408), some diagnosed families would have moved into the locked
set, breaking test-set isolation. Switching to a fresh seed regenerated all
parameters and the partition so **no scenario observed during design/sizing is
in the locked set** (machine-verified: `D_prelock_never_touched_locked`). This is
a *strengthening* of isolation, disclosed in the pre-registration §5, and the
generator/family definitions are unchanged. A reviewer who insists on the exact
named seed would down-grade this to a protocol deviation; the auditor judges it a
defensible, disclosed improvement.

*Caveat 2:* on **censored-demand families** (`capacity_bound`,
`demand_saturation`, `nonlinear_response`, `inventory_bound`) the OLS `ε̂` from
capacity-truncated history is biased toward inelastic, so B has a residual
over-raise-price failure there. This is a property of the *correction*, not the
scoring, and it is exactly the regime where D "helps" — see O.

## D. Test-set isolation — **PASS**

`prelock_diagnostics.json.scope.locked_test_touched == false`; every family in
the pre-lock diagnostic is in development/validation (machine-verified). The
pre-registration was frozen (git `22ce18c`, doc SHA `d111db68…`) **before**
`run --partition locked_test`; the run refuses to proceed unless the frozen doc
and manifest SHAs match. No development or validation outcome was used to choose
locked families, tune thresholds, or alter the endpoint.

## E. DT correction — **QUALIFIED**

The correction is minimal in scope: one function, only `expected_units_sold` /
`expected_revenue` / `expected_profit` on the scenario side; `risk_score`,
`baseline_*`, model, control flow, candidates, agents, optimiser unchanged.
`ε̂/â` are data-estimated, clipped only to enforce a downward-sloping demand
curve (`ε̂ ≤ −0.05`) and diminishing marketing (`â ∈ [0,1]`) — economic priors,
not favourable tuning; no coefficient is hand-set.

*Caveat (QUALIFIED):* the correction *does* make B a stronger baseline than the
shipped system, and it introduces an estimation channel the production DT does
not exploit. A reviewer could argue a positive `D_vs_B` would then be "about the
research variant." Here the result is **negative for D**, which weakens that
concern for the headline but the framing must remain "research-only corrected
Decision Simulation", never "the production Digital Twin" (Section 40 of the
brief; enforced in all R1 docs and the forbidden-term scan).

## F. Candidate-action fairness — **PASS**

Identical-feasible-action-space invariant holds on **all 4 080** locked
instances (0 failures). A/B/C/D select from the identical enumerated set; the
oracle enumerates that set plus the no-op; the candidate set was **not** modified
for R1.

## G. Randomization — **PASS**

Deterministic generation keyed by `(master_seed, generator_version, family,
index)`; per-(scenario, seed) history keyed by a hash of `(scenario_id, seed)`.
Bootstrap seeds fixed (12345 primary, 4242 mechanism, 777 family). Power
`rng_seed` fixed (20260907). No seed was changed after seeing results; the
locked run was executed once.

## H. Seed interpretation — **PASS**

`statistical_results.json.unit_of_analysis == "scenario"`. The 4 080 seed
observations are aggregated to 408 scenario means before every paired test; the
cluster bootstrap resamples **scenarios**; Wilcoxon is at n = 408. The report
distinguishes structural (scenario) from stochastic (seed) replication. No test
treats 4 080 as the n.

## I. Power — **QUALIFIED**

Planned power 0.894 (MEI 0.05, conservative between-scenario SD 0.30 vs pilot
0.282, within-seed SD 0.18, N 408, 10 seeds), from development-stage variance
only (`power_assumptions.json` `_variance_source` records this). N was **raised**
from a 126-scenario draft (≈ 0.40) to reach the target — not the effect of
interest lowered.

*Caveat (QUALIFIED):* `simulate_power` does not model exact ties. The locked
`D_vs_B` has 35 exact ties (n_nonzero 373/408), so achieved power is slightly
below 0.894 — but the observed effect (0.085) is 1.7× the MEI and the CI is well
clear of 0, so this does not threaten the conclusion. A reviewer wanting a
tie-aware prospective power would note it as a methods gap, not a result flaw.

## J. Statistical assumptions — **PASS**

Paired Wilcoxon signed-rank (exact ≤ 25 non-zero, normal approx otherwise;
`zero_method="wilcox"` for exact zero handling). Cluster bootstrap is
distribution-free. `B_vs_A` and `D_vs_B` are strongly non-null on both the
rank test and the bootstrap. `C_vs_B` shows a **mean-vs-rank divergence** (mean
−0.054 with CI excluding 0, but Wilcoxon p = 0.609, median 0, W/T/L 141/100/167)
— the report handles this correctly by classifying `C_vs_B` as **null** and not
reporting the negative mean as a benefit; a reviewer would want that divergence
called out explicitly, which it is (`R1_RESULTS.md` §16).

## K. Clustering — **PASS**

Scenario-level cluster bootstrap for every CI; family-level analysis reports
per-family n (34 structural scenarios) and CIs; the report explicitly states the
effective cluster count for factor-level claims is 12 (locked families) and does
**not** make factor-level assertions.

## L. Multiplicity — **PASS**

Holm–Bonferroni over the pre-registered confirmatory family exactly
`{B_vs_A, C_vs_B, D_vs_C, D_vs_B}` (machine-verified). Both raw and adjusted p
reported. Secondary contrasts (`D_vs_A`, `D_vs_naive/greedy/classical/oracle`,
`A/B/C_vs_oracle`) are labelled descriptive and excluded from the correction; no
secondary p is presented as confirmatory.

## M. Effect-size interpretation — **PASS**

Primary effect size = matched-pairs rank-biserial (Kerby estimator, `−0.469` for
`D_vs_B`). No p-derived `r` is used. Direction is consistently interpreted
(negative `D−B` = D better; the observed +0.085 = D worse).

## N. Robustness — **PASS**

Pre-registered 10-perturbation suite on a deterministic 30-scenario locked
subsample × 3 seeds × low/high severity (1 620 runs, 0 errors); not tuned; no
favourable perturbation added after the fact. **`primary_conclusion_changes =
False`** — the sign of `D−B` (D worse than B) is preserved on all 18
perturbation × severity cells. Subsample `D−B` ∈ [+0.046, +0.339]; the single
cell whose 95 % CI touches 0 (`input_noise` at 0.75) still has a positive point
estimate; `adversarial` makes D *more* worse (+0.339), consistent with the
mechanism.

*Caveat:* the subsample is 30 of 408 locked scenarios (≈ 7 %) for tractability
and is descriptive, not a re-run of the confirmatory test — but the primary
effect is large relative to MEI and no cell flips.

## O. Mechanism claims — **PASS**

The report separates *action change* (D changed B's action on 57 % of instances)
from *improvement* (of those, 33 % improved / 67 % worsened) and states plainly
that a changed action is not evidence of a better decision — here the changes are
net harmful. The "D helps" story (`nonlinear_response`, `demand_saturation`) is
attributed to a **B residual failure on censored-demand families**, not to D
reasoning — and the report says so. OLS coefficients are labelled associational,
family-clustered, not causal, not interpreted at the factor level. `D_vs_C`
localises the damage to the risk gate + optimiser without claiming a causal
mechanism.

## P. Baseline fairness — **PASS**

`naive` (fixed), `greedy` / `classical_optimizer` / `oracle` (analytic access to
System B). The information advantage of the objective-aware benchmarks is
disclosed everywhere; they are labelled external computational benchmarks, not
architecture competitors. The report explicitly does not claim success from
beating `naive` nor failure from not matching the `oracle`.

## Q. Reproducibility — **PASS**

Commit `22ce18c…`, seeds fixed, every artifact SHA-256 in `checksums.txt`,
`config.prereg` records the hash of every design input. `analyze` regenerates
`statistical_results.json` / `mechanism_results.json` deterministically from
`results.json`. Figures reproduce from stored JSON only. Frozen manifest
`94aa419c…` re-verified before and after.

## R. Production contamination — **PASS**

`git diff` on `backend/app/{services,analytics,agents,decision_engine}`, the
frozen manifest, `paper_results_snapshot.json`, `experiments/results/`,
`experiments/upgraded_controlled_v1/`, `experiments/upgraded_controlled_v2/`,
`docs/PAPER_DRAFT.md`, `docs/ieee_paper/` — **empty** (machine-verified).
`PipelineOptions().label() == "full"`, `risk_penalty_lambda == 1.0`,
`risk_model is None`. `RISK_FORMULA_VERSION == "extrapolation_range_v1"` (R3 not
promoted). `r1_dt` is installed and removed inside `r1.harness` per instance;
production behaviour outside the `with` block is unchanged.

## S. Post-hoc decisions — **QUALIFIED**

The endpoint, primary contrast, direction, families, N, seeds, split, tests, CI
method, multiplicity, robustness set, mechanism factors, success classification,
and exclusion rules were all frozen before the locked run (git commit + hashes
recorded). No scenario/seed/family was removed; there were 0 exclusions and 0
errors; the run was executed once.

*Caveat 1 (QUALIFIED):* the master-seed change and the N increase (126 → 408)
happened *after* an initial development pass, driven by the power analysis. Both
are permitted design-stage decisions (Section 12/15 of the brief use development
data for variance and sizing), both are disclosed, and neither used a locked
outcome — but a strict reviewer would want them logged as pre-lock design
iterations, which the pre-registration §5/§9 does.
*Caveat 2:* one console `print` bug (a `Σ` character) was fixed *after* the first
`analyze` call; the JSON outputs were already written and are byte-identical on
re-run — no numbers changed.

## T. External validity — **PASS (i.e. correctly bounded at ~zero)**

The report states repeatedly that R1 is synthetic, controlled, and a
research-only variant; that it does **not** establish real-world / SME / ROI /
causal / deployment effects; that it cannot show multi-agent architectures are
useless in general; and that a different frozen downstream configuration might
behave differently. The forbidden-claim forms are excluded and a term scan is
run. External validity is appropriately near-zero and is not overstated.

---

## Reasons a skeptical reviewer could still push back

1. **The correction is the reviewer's main target.** `r1_dt` is a
   researcher-authored demand model; a reviewer may argue the whole comparison
   now depends on a wrapper the team wrote. *Response:* it is the **minimal**
   change (one function, data-estimated, no favourable tuning), the scorer
   (System B) is a different functional form and unchanged, and the result is
   **negative for D**, so the wrapper is not "making D win"; the direction of
   interest (does the stack add value over a functioning B) is answered
   independently of the wrapper's exact form because B and D both run through it.
2. **Censored-demand `ε̂` bias.** The 2 D-favourable families exist because the
   correction mis-estimates elasticity under capacity truncation. A reviewer
   could say the environment is partly "rigged against B" there. *Response:*
   disclosed; the aggregate is D-worse **with or without** those families
   (leave-one-family-out +0.050 … +0.159), and B is *better* than D overall.
3. **Effective n for mechanism = 12 families.** Factor-level mechanism claims
   would be under-powered — the report makes none, only family-level description.
4. **Robustness is a 7 % subsample.** Descriptive only; the primary effect is
   large relative to MEI so a subsample sign-flip is unlikely, and it is checked.
5. **Master-seed / N changes** are disclosed design iterations, not outcome-driven
   — but a reviewer insisting on the literal named seed would call it a
   deviation.

## Overall audit verdict

**The R1 NEGATIVE result for `D_vs_B` is scientifically sound as executed.** Every
integrity item is PASS; the QUALIFIED items (C master-seed, E correction framing,
I tie-aware power, N subsample robustness, S design iterations) are disclosed
caveats that do **not** threaten the direction or significance of the primary
finding, which is large (1.7× MEI), highly significant (Holm p ≈ 0), consistent
across the confirmatory family (`D_vs_C` also strongly D-worse), robust to
leave-one-family-out, corroborated by the true-optimal-action hit-rate collapse
(62.5 % → 34.6 %) and by DecisionGPT's own internal metric, and correctly bounded
as a synthetic research-only result. No serious flaw was discovered that would
require repairing or re-running.
