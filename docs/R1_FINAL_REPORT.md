# R1 Final Scientific Report

*Versioned research-only Decision-Simulation correction + pre-registered
controlled evaluation. Synthetic. Not real-world, not SME, not causal.*

---

## 1. Executive summary

V1 and V2 established that the production Decision Simulation's projected units
are effectively **flat in price** (price + marketing carry ≈ 2 % of the
forecasting model's importance; a 3× price sweep moves projected units by 0.0),
so condition **B collapsed to "raise price to the candidate ceiling"** on ≈ 100 %
of executions, uncorrelated with the true elasticity. This confounded the
downstream A→B→C→D comparison: B could not express the scenario mechanisms.

R1 removed exactly that bottleneck with the **smallest defensible research-only
correction** — a wrapper that replaces only the scenario-side units/revenue/
profit with a constant-elasticity response whose `ε̂` is estimated by OLS from
the business's own seeded history (fallback to generator parameters only when the
history is unusable — **0 % of the locked run**). Production
`digital_twin_service.py` is byte-identical; the candidate set, agents, risk
manager, optimiser, control flow, A/B/C/D definitions, and the exogenous
objective are all unchanged.

The pre-lock gate passed 12/12 (B now selects 6+ distinct actions, `corr(a_elast,
B price move) = +0.40`, DT revenue direction matches elasticity in 92 % of
probes, oracle exact, no leakage, planned power 0.894). The pre-registration was
frozen (git `22ce18c`, doc SHA `d111db68…`) before the locked test, which was run
**exactly once**: 408 scenarios × 10 seeds = **4 080 evaluations, 0 errors**.

**Primary result — `D_vs_B` = regret(D) − regret(B): mean +0.0852, 95 %
scenario cluster-bootstrap CI [+0.0479, +0.1231] (excludes 0), Holm-adjusted
p ≈ 0, matched-pairs rank-biserial −0.469, D better/tie/D worse = 99/35/274 of
408 scenarios. Pre-registered classification: NEGATIVE.** The full downstream
stack **degrades** exogenous decision quality relative to the corrected Decision
Simulation, by ≈ 0.085 normalised regret, and the direction is preserved with
any single locked family removed (leave-one-family-out range +0.050 … +0.159).

The value that exists is in **B**: `B_vs_A` = −0.044 (Holm p 1 × 10⁻⁸, CI
excludes 0) — Decision Simulation genuinely improves on prediction-only once it
can react to the environment. Adding the single agent does nothing reliable
(`C_vs_B` null, Holm p = 0.609); adding the risk-manager gate + optimiser is
where the damage concentrates (`D_vs_C` = +0.139, rank-biserial −0.633). D is the
condition **furthest** from the oracle (regret 0.301 vs B 0.216, C 0.162,
A 0.259), loses to `greedy` and `classical_optimizer`, and beats only `naive`.

## 2. Research question

*When the Decision-Simulation environment can respond meaningfully to
decision-relevant price/marketing information, does adding the existing
downstream DecisionGPT components (agents + risk + optimisation) add measurable
exogenous decision-quality value over Prediction + Decision Simulation?*
Primary contrast `D_vs_B` (negative = D better). Answer below (§17).

## 3. What changed

One thing: `backend/app/evaluation/r1/r1_dt.py` — a research-only wrapper that
replaces only the scenario-side `expected_units_sold` / `expected_revenue` /
`expected_profit` with `u_a = u_base·(1+Δp/100)^ε̂·(1+Δm/100)^â·fulfil_cap`,
`ε̂/â` estimated by OLS from the seeded history. Installed per-instance by
`r1.harness`, removed afterwards. New R1 code:
`backend/app/evaluation/r1/{__init__,r1_dt,scenario_families,harness,ground_truth,
stats,mechanism,robustness}.py`, `scripts/{run_eval_r1,r1_figures,scan_r1_claims}.py`,
`experiments/r1/`, `docs/R1_*.md`.

## 4. What remained frozen

Production `digital_twin_service.py`, `forecast_service.py`, `decision_service`,
`decision_architecture_service`, `agents/*`, `strategy_optimizer`,
`strategy_generation_service`, `decision_engine/*` — byte-identical (git-clean).
R0/D0: `label()=='full'`, `risk_penalty_lambda==1.0`, `risk_model==None`.
R3 = `extrapolation_range_v1` — NOT PROMOTED. `experiment_manifest.json` =
`94aa419c…` (verified before + after). V1 = `evaluation_complete` /
`results.json 804fbe91…`. V2 = `STOPPED_AT_PRELOCK_GATE` / `locked_test_run
false` (the V2 locked test was **not** run retroactively). `docs/PAPER_DRAFT.md`,
`docs/ieee_paper/` — untouched. `REAL_INDIAN_SME_OUTCOME = 0`,
`PredictionEvaluation = 0`, `CAUSALLY_VALIDATED = 0`, Table 2 NOT READY, no real
LLM, no real SME data.

## 5. Why R1 was necessary

`docs/R1_DT_DIAGNOSTIC.md`. The production forecasting model
(`sales_forecast_xgboost`) has SHAP importance `price` 0.87 + `marketing_spend`
1.09 out of ≈ 90 (2.2 %); `model.predict` is **exactly constant** over a price
sweep 50→150 (range 0.0); training data has a *wrong-signed* crude price→units
slope (+0.18). `simulate_strategy` then computes `revenue = units × price`, so
projected revenue increases monotonically with price and B's argmax is always
`price_change=+10`. Without the correction, `D_vs_B` compares against a constant
policy (V2 finding, confirmed architectural not environmental).

## 6. Pre-lock validation (`docs/R1_PRELOCK_GATE.md`, 12/12 GO)

Development/validation only; locked partition never touched (machine-verified).
DT revenue direction matches elasticity in **0.917** of probes; B has **6**
unique actions; `corr(a_elast, B price move) = +0.397` (B cuts price when
elastic, raises when inelastic); B mean regret **0.158** (not degenerate, not at
a ceiling); OLS `ε̂` median error **0.084**; fallback **1.1 %**; oracle exact;
identical action space; no leakage; planned power **0.894**.

## 7. Locked-test design

Pre-registered N = 408 locked scenarios (12 of 27 families; sized from the
development-stage variance for planned power ≥ 0.80 at MEI 0.05 — an earlier
126-scenario draft gave ≈ 0.40 and N was raised, **not** the effect of interest
lowered). 10 seeds. Unit of analysis = scenario. Holm over
`{B_vs_A, C_vs_B, D_vs_C, D_vs_B}`. Executed once; no re-runs.

## 8. Primary result

`D_vs_B` (regret_D − regret_B; **negative = D better**):

| | |
|---|---|
| mean | **+0.0852** (D worse) |
| median | +0.1000 |
| 95 % scenario cluster-bootstrap CI | **[+0.0479, +0.1231]** (excludes 0) |
| Wilcoxon signed-rank p (n_nonzero 373) | 5.44 × 10⁻¹⁰ |
| Holm-adjusted p | ≈ 0 |
| matched-pairs rank-biserial | **−0.469** |
| wins / ties / losses (D better / tie / D worse) | **99 / 35 / 274** |
| leave-one-family-out | +0.050 … +0.159 (always D worse) |
| **pre-registered classification** | **NEGATIVE** |

## 9. Complete A/B/C/D results

Mean normalised regret: **A 0.259 · B 0.216 · C 0.162 · D 0.301**
(oracle 0, classical 0.089, greedy 0.197, naive 0.367).

| contrast | mean Δ | 95 % CI | Holm p | reject | rank-biserial | reading |
|---|--:|---|--:|:--:|--:|---|
| `B_vs_A` | −0.0436 | [−0.084, −0.002] | 1e−8 | yes | +0.431 | **B better than A** |
| `C_vs_B` | −0.0540 | [−0.088, −0.020] | 0.609 | no | −0.084 | **null** (mean-vs-rank divergence) |
| `D_vs_C` | +0.1392 | [+0.116, +0.162] | ≈ 0 | yes | −0.633 | **D much worse than C** |
| `D_vs_B` | +0.0852 | [+0.048, +0.123] | ≈ 0 | yes | −0.469 | **D worse than B — NEGATIVE** |
| `D_vs_A` (secondary) | +0.0417 | [+0.016, +0.068] | — | — | — | D worse than A |

Internal `goal_achievement` (labelled, not external validation): B 0.496 vs
D 0.364.

## 10. Baseline results

D beats `naive` (`D_vs_naive` −0.066, CI excludes 0). D loses to `greedy`
(+0.104) and `classical_optimizer` (+0.212) and is furthest from `oracle`
(+0.301). greedy / classical / oracle have analytic access to the System-B
objective that A/B/C/D lack — documented information advantage; they are
difficulty yardsticks, not architecture competitors. Beating `naive` is not
evidence of decision quality.

## 11. Family-level findings (12 locked families × 34 scenarios)

- **D better on 2 families**, both censored-demand (capacity ceiling + elastic),
  where B has a *residual failure mode*: `nonlinear_response` `D−B` = −0.726
  (B regret 0.97, D 0.25), `demand_saturation` −0.235 (B 0.47, D 0.23). The OLS
  `ε̂` from censored history is biased mild, B over-raises price, and D's
  conservatism damps it.
- **D worse on 10 families**, including where B is at/near the optimum:
  `capacity_bound` `D−B` = +0.477 (B 0.01 → D 0.49), `weak_seasonality` +0.300,
  `weak_marketing` +0.227 (B 0.04 → D 0.27), `delayed_price` +0.217 (B 0.05),
  `asymmetric_risk` +0.189, `noisy_observations` +0.164, `regime_shift` +0.158,
  `price_elastic` +0.138 (B 0.00 → D 0.14), `strong_seasonality` +0.074,
  `promotion_threshold` +0.039 (B 0.00).
- **Not driven by one family.** Leave-one-family-out `D_vs_B` mean stays positive
  for every removal (+0.050 to +0.159); removing the one D-favourable family
  makes it markedly worse for D.

## 12. Robustness

Pre-registered 10-perturbation suite on a deterministic 30-scenario locked
subsample × 3 seeds × low/high severity — **1 620 runs, 0 errors**
(`experiments/r1/robustness_results.json`). **`primary_conclusion_changes =
False`**: D worse than B on **every** perturbation × severity (18/18 cells).
Subsample `D−B` ranges from +0.046 (`input_noise` high severity — the only cell
whose CI touches 0, point estimate still positive) to +0.339 (`adversarial` — D
degrades further as the projection worsens). No perturbation was added post-hoc;
DecisionGPT was not tuned. **The NEGATIVE `D_vs_B` result is robust.**

## 13. Mechanism

- **D changed B's action on 2 336 / 4 080 (57 %); of those, 763 improved and
  1 573 worsened regret — 2.06 : 1 against.** A changed action is **not** an
  improved decision; here the changes are net harmful.
- **B action == oracle on 62.5 % of instances; D action == oracle on 34.6 %.**
  The downstream stack roughly **halves** the true-optimal-action hit rate; the
  collapse is starkest where B is best (`capacity_bound` 0.94 → 0.04,
  `asymmetric_risk` 0.74 → 0.01).
- OLS (associational, family-clustered, not factor-level): `D−B` grows with
  `prediction_error` (β +0.171) and shrinks with `action_space_size` (β −0.179).
- `D_vs_C` (rank-biserial −0.633) localises most degradation to the risk-manager
  gate + optimiser step.

## 14. Strongest evidence FOR D

*(Required section — present regardless of outcome.)*

1. **`nonlinear_response`** (34/34 scenarios, `D−B` = −0.726, CI [−0.793,
   −0.651]): D turns a near-worst-case B (regret 0.97) into a near-oracle
   outcome (0.25). On strongly-elastic + capacity-censored problems where the
   corrected DT still over-raises price, the agent/risk layer's conservatism is
   a genuine corrective.
2. **`demand_saturation`** (`D−B` = −0.235, 23/34 D better): same mechanism,
   milder.
3. **D beats the literal status quo** (`D_vs_naive` = −0.066, CI [−0.095,
   −0.037]) — the full pipeline is better than doing nothing.
4. **43 near-oracle D outcomes** (regret ≤ 0.02) across 6 families — D does reach
   the optimum on a non-trivial minority of problems.
5. Directionally, the risk layer's *bias toward smaller / less-aggressive moves*
   is protective exactly when the upstream projection is most wrong
   (`D−B ~ prediction_error` β +0.171 is consistent with "D helps most where B is
   worst").

## 15. Strongest evidence AGAINST D

*(Required section.)*

1. **Primary `D_vs_B` = +0.085, Holm p ≈ 0, CI [+0.048, +0.123] excludes 0,
   rank-biserial −0.469, D worse on 274/408 scenarios** — a rejection in the
   "D worse" direction that clears the MEI.
2. **Leave-one-family-out**: D worse in every case (+0.050 … +0.159); the result
   is not an artefact of one family.
3. **Hit-rate collapse**: B picks the true optimum 62.5 % of the time, D only
   34.6 %; on `capacity_bound`/`asymmetric_risk` D's hit rate falls to ≈ 0 while
   B's is ≈ 0.8–0.9.
4. **When D overrides B it is worse 2 : 1** (1 573 worsened vs 763 improved of
   2 336 changes).
5. **D is the condition furthest from the oracle** (0.301 vs B 0.216, C 0.162,
   A 0.259) and loses to a trivial `greedy` and to `classical_optimizer`.
6. **DecisionGPT's own internal metric agrees**: `goal_achievement` B 0.496 vs
   D 0.364.
7. **`D_vs_C` = +0.139** (rank-biserial −0.633) — adding the risk gate +
   optimiser on top of the single agent is where the damage is largest.
8. **`C_vs_B` null** — the agent layer does not add value even at the single-
   agent step.

## 16. Threats to validity

*(Hostile detail: `docs/R1_AUDIT.md`.)*

| threat | assessment |
|---|---|
| R1 is a research-only variant, not the production DT | disclosed everywhere; the result is about *this corrected environment*, not the shipped system |
| `r1_dt` (constant-elasticity on the production baseline) is a modelling choice | System B (the scorer) is a *different* form (additive-linear); `ε̂` is still estimated with error (median 0.08 pre-lock; 0 % fallback in the locked run) and D/B are graded against System B, not against `r1_dt` |
| `r1_dt` gives B/C/D an information channel (estimated elasticity) production does not use | that is the *point* of the correction; the channel is symmetric across B/C/D, uses only permissible history, and is machine-verified to exclude the objective/oracle |
| censored-demand families bias `ε̂` mild ⇒ B residual failure | the 2 families where D "helps" are of this type; disclosed; the aggregate result is D-worse even including them, and worse without them |
| effective cluster count = 12 families | mechanism coefficients are associational, family-level description only; the *primary* contrast is a scenario-level paired test with n = 408 |
| A = fixed minimal-move policy | `D_vs_A` is secondary; `D_vs_naive` (also negative for D... i.e. D better than naive) is the clean "vs nothing" contrast |
| objective-aware benchmarks | greedy/classical/oracle are yardsticks, not fair contests; disclosed |
| synthetic only | no real data; no real-world / SME / causal claim is made |
| single locked run | one run, pre-registered; a null/negative was an accepted outcome and no re-run was performed |

## 17. Scientific conclusion

**Does the existing downstream DecisionGPT stack add measurable decision-quality
value over Prediction + Decision Simulation when the Decision Simulation is made
genuinely responsive to decision-relevant price/marketing information?**

**No. On this pre-registered synthetic controlled evaluation the full downstream
stack (D) produced significantly and practically-meaningfully *worse* exogenous
normalised regret than Decision Simulation alone (B): `D_vs_B` mean +0.085
(D worse), 95 % CI [+0.048, +0.123], Holm p ≈ 0, rank-biserial −0.469, robust to
leave-one-family-out. Pre-registered classification: NEGATIVE.** The measurable
value in the tested environment is in the corrected Decision Simulation itself
(`B_vs_A` supported, B better than A); the single agent adds nothing reliable
(`C_vs_B` null); and the risk-manager gate + optimiser step accounts for most of
the degradation (`D_vs_C` = +0.139).

**What mechanisms explain the result?** The downstream stack changes B's action
on 57 % of instances and, when it does, worsens the outcome 2 : 1. It roughly
halves the rate at which the true-optimal action is selected (62.5 % → 34.6 %),
with the largest collapses on families where B is already near-optimal
(`capacity_bound`, `asymmetric_risk`, `price_elastic`). The one regime where D
helps is censored-demand + strong-elasticity families (`nonlinear_response`,
`demand_saturation`), where B has a residual over-raise-price failure and the
risk layer's conservatism is corrective — i.e. D helps only where B is worst and
hurts where B is good, netting negative.

**What can this experiment NOT establish?** It cannot establish anything about
real businesses, real SMEs, ROI, customer outcomes, causal effects, or
deployment. It evaluates a *research-only corrected* Decision Simulation, not the
production `digital_twin_service`. It cannot show that multi-agent architectures
are useless in general — only that, in this controlled synthetic environment
with these frozen components, the downstream stack subtracts objective value
from a functioning Decision-Simulation baseline. It cannot rule out that a
different downstream configuration (different risk penalty, different optimiser
objective, different candidate set) would behave differently — those were held
frozen by design.

## 18. Executive conclusion: the five publication questions

Concise, artifact-backed answers. All numbers are from
`experiments/r1/statistical_results.json` / `mechanism_results.json` /
`robustness_results.json`, independently recomputed from raw `results.json`
(`experiments/r1/independent_recheck.json`, 75/75).

**Q1 — Does responsive Decision Simulation add value over prediction alone?
(`B_vs_A`)**
Yes. `B_vs_A` mean −0.044 normalised regret (B better), 95 % cluster-bootstrap
CI [−0.084, −0.002], Wilcoxon p = 4.8×10⁻⁹, Holm p = 1×10⁻⁸, rank-biserial
+0.43; B better on 292 of 408 scenarios, worse on 116. Mean regret falls
0.259 → 0.216 and the internal goal-achievement metric rises 0.000 → 0.496.
Pre-registered classification: **SUPPORTED**. Value enters the pipeline at the
corrected Decision-Simulation layer.

**Q2 — Does the downstream stack add value over B? (`D_vs_B`, primary)**
No — it subtracts value. `D_vs_B` mean **+0.085** (D worse), 95 % CI
**[+0.048, +0.123]**, Wilcoxon p = 5.4×10⁻¹⁰, Holm p ≈ 0, rank-biserial −0.469;
D better on 99, tie 35, D worse on 274 of 408 (n≠ = 373). Mean regret rises
0.216 → 0.301; internal goal-achievement falls 0.496 → 0.364; D also fails to
beat prediction alone (`D_vs_A` +0.042, Wilcoxon p = 0.13). Pre-registered
classification: **NEGATIVE**.

**Q3 — Where is the degradation associated, and by what mechanism? (`D_vs_C`
+ trace)**
At the C→D transition. `C_vs_B` is null (mean −0.054, Holm p = 0.61) while
`D_vs_C` is +0.139 (Holm p ≈ 0, rank-biserial −0.63). Model-free: D overrides
B's action on 2336 / 4080 decisions (57 %) and, when it does, worsens the
outcome 1573 vs improves 763 (≈2.1× worse); the optimal-action rate falls from
B's 62.5 % to D's 34.6 %. Family-clustered OLS (associational, not causal,
12 clusters): the `D_vs_B` gap widens most with `prediction_error`
(β = +0.171 [+0.136, +0.207]) and with `risk_exposure` (β = +0.034
[+0.011, +0.052]) — consistent with the risk-penalty term over-correcting a
mis-scaled risk heuristic and steering the optimiser off B's better choice.
Stated as a localisation and a mechanism hypothesis, **not** a causal proof.

**Q4 — Does the result survive robustness? (LOFO + perturbations)**
Yes. Leave-one-family-out: every one of the 12 re-estimates is positive
(D worse), range **+0.050** (drop `capacity_bound`) to **+0.159** (drop
`nonlinear_response`); D is worse in 10 of 12 families. Pre-registered
perturbations: **18 / 18** cells preserve the D-worse sign
(`primary_conclusion_changes = false`), perturbed `D_vs_B` from +0.046 to
+0.339 across adversarial, constraint, contradictory-signal,
distribution-shift, extreme-but-feasible, forecast-bias, input-noise,
missing-value and uncertainty-inflation conditions.

**Q5 — What does this NOT establish?**
Nothing about real businesses, real SMEs, ROI, customer outcomes, causal
effects, deployment, human decision-makers, or LLM agents (the three agents are
deterministic rule components; no LLM was run). It evaluates a *research-only
corrected* Decision Simulation, not the production `digital_twin_service`
(which the diagnostic shows is degenerate). It does not show multi-agent
architectures are unhelpful in general, and it cannot rule out that a different
downstream configuration (different risk penalty, optimiser objective, or
candidate set — all held frozen by design) would behave differently. The
finding is bounded to this architecture, this R1 correction, this synthetic
environment, these 12 scenario families, and this pre-registered protocol.

## 19. Publication recommendation

Integrate R1 into the paper **as a distinct, versioned, research-only
follow-up**, clearly separated from R0/D0 (production), V1 (first upgraded
controlled evaluation), and V2 (diagnostic). Recommended framing: *"After
diagnosing that the production Decision Simulation is unresponsive to
decision-relevant price/marketing information (V1/V2), we built the minimal
research-only correction that makes it responsive, pre-registered a controlled
ablation, and ran it once. In this corrected synthetic environment, adding the
downstream multi-agent / risk / optimisation stack **reduced** objective
decision quality relative to the corrected Decision Simulation alone (`D_vs_B`
NEGATIVE, mean +0.085 normalised regret, Holm p ≈ 0); the value was in the
Decision Simulation itself."* The paper must **not** claim the production system
is validated, superior, or better/worse for real SMEs, and must not call this a
causal or real-world result. All eight forbidden-claim forms (§33 of the brief)
are excluded; a forbidden-term scan is run (`scripts/scan_r1_claims.py`,
`experiments/r1/forbidden_term_scan.json`).

## 20. Reproducibility

Commit `22ce18c965b61641f3dd28cc35e0cfac22f61dca`; CPython 3.12 (`backend/.venv`);
`master_seed 20260907`; bootstrap seeds 12345 / 4242 / 777; power `rng_seed
20260907`. Every artifact hashed in `experiments/r1/checksums.txt`; frozen
manifest `94aa419c…` re-verified. Command sequence in `docs/R1_RESULTS.md` §18.
A clean checkout reproduces `statistical_results.json` /
`mechanism_results.json` from `results.json` via `run_eval_r1.py analyze`; the
figures reproduce via `scripts/r1_figures.py all` from stored JSON only.

---

## Phase-38 final integrity checklist

| item | status |
|---|---|
| Production architecture unchanged | ✅ `git diff` on `backend/app/{services,analytics,agents,decision_engine}` empty |
| R0/D0 unchanged | ✅ `label()=='full'`, `risk_penalty_lambda==1.0`, `risk_model is None` |
| V1 unchanged | ✅ `evaluation_complete`, `results.json 804fbe91…`, audit 14/14 |
| V2 unchanged | ✅ `STOPPED_AT_PRELOCK_GATE`, `locked_test_run false`, audit 14/14 |
| R3 unchanged | ✅ `RISK_FORMULA_VERSION == "extrapolation_range_v1"` (NOT PROMOTED) |
| Experiment manifest unchanged | ✅ `94aa419c703b1babb465975463b26e55255755a7687ecbecadb6db4c4c15cbff` |
| No real SME data used | ✅ none exists; none accessed |
| No fabricated outcomes | ✅ every number from `results.json`; 0 errors, 0 exclusions |
| No real LLM execution claimed | ✅ blocked; not invoked |
| No causal / real-world claims | ✅ forbidden-term scan 0 prohibited; §17 states the bounds |
| Pre-registration frozen before locked run | ✅ git `22ce18c`, doc SHA `d111db68…`, config `prereg` block |
| Locked scenarios frozen | ✅ 408 `locked_scenario_ids` + `locked_test_family_checksum` in `config.json` |
| Locked seeds frozen | ✅ 10 seeds `20260906…20260915` in the pre-registration §7 |
| Locked test executed once | ✅ `run --partition locked_test` refuses a second run; `locked_test_run: true` |
| Expected scenario/seed count accounted for | ✅ 408 × 10 = 4 080 instances (machine-verified) |
| No unexplained exclusions | ✅ 0 exclusions, 0 harness errors |
| Ground truth independent | ✅ AST scan; oracle exact 408/408 |
| Oracle exact | ✅ 0 mismatches vs independent enumeration |
| Information boundary verified | ✅ `docs/R1_INFORMATION_BOUNDARY.md`; `r1_dt` imports no objective/oracle |
| Primary metric fixed | ✅ normalised regret, `D_vs_B`, pre-registered |
| Statistical test fixed | ✅ scenario-level Wilcoxon + cluster bootstrap + rank-biserial |
| Multiplicity handled | ✅ Holm over `{B_vs_A, C_vs_B, D_vs_C, D_vs_B}` |
| Clustered inference handled | ✅ scenario as unit; bootstrap resamples scenarios |
| Effect size correctly interpreted | ✅ matched-pairs rank-biserial; negative `D−B` = D better |
| Robustness pre-registered | ✅ 10-perturbation suite; `primary_conclusion_changes = False` |
| Mechanism analysis pre-registered | ✅ action-change vs improvement + factor OLS + `D_vs_C` |
| All unfavorable families retained | ✅ 12 locked families reported; none dropped |
| No post-hoc tuning | ✅ 0 parameter changes after freeze; console-print bug fix did not alter any number |
| Reproducibility verified | ✅ `analyze` regenerates stats from `results.json`; figures from JSON |
| Hostile audit completed | ✅ `docs/R1_AUDIT.md` (A–T; all PASS/QUALIFIED, no FAIL) |
| Independent recomputation completed | ✅ `experiments/r1/independent_recheck.json` — 75/75 checks reproduce from raw `results.json` |
| Hostile peer review completed | ✅ `docs/R1_HOSTILE_REVIEW.md` (16 reviewer dimensions; no Critical issue substantiated) |
| Publication-readiness scored | ✅ `docs/R1_PUBLICATION_READINESS.md` — 6 PASS / 5 QUALIFIED / 0 FAIL |
| IEEE manuscript drafted | ✅ `docs/ieee_paper_r1/{main.tex,references.bib,README.md,figures/}` (separate from frozen `docs/ieee_paper/`; 24 sections, 9 tables, 5 figures incl. SVG+PDF; structural + 66/66 numeric + citation validation; PDF not compiled — no local LaTeX toolchain) |
| Final submission audit completed | ✅ `docs/FINAL_SUBMISSION_AUDIT.md` (experimental / frozen-artifact / statistical / publication integrity + remaining risks + synthetic-artifact rebuttal) |
| Forbidden-claim scan completed | ✅ `experiments/r1/forbidden_term_scan.json` — 0 prohibited across 13 docs incl. the manuscript |
| Figures reproducible | ✅ `scripts/r1_figures.py all` from `figure_data.json` |
| Tables traceable to raw results | ✅ every value cites `experiments/r1/*.json` |

**Final scientific answer.** In this pre-registered synthetic controlled
evaluation, with the Decision Simulation made genuinely responsive to
decision-relevant price/marketing information via the minimal research-only
correction, **the existing downstream DecisionGPT stack does not add
decision-quality value over Prediction + Decision Simulation — it significantly
and meaningfully reduces it** (`D_vs_B` NEGATIVE: mean +0.085 normalised regret,
95 % CI [+0.048, +0.123], Holm p ≈ 0, rank-biserial −0.469, robust to
leave-one-family-out and to the perturbation suite). The measurable value is in
the corrected Decision Simulation itself.
