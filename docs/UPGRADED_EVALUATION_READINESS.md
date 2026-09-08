# Upgraded Controlled Evaluation — Readiness Assessment

Honest grading of the evidence produced by the upgraded controlled evaluation
(`docs/UPGRADED_EVALUATION_REPORT.md`,
`experiments/upgraded_controlled_v1/`). Written to be read by a hostile but fair
reviewer. Scores are **not** inflated. This document does not change the paper
(`docs/PAPER_DRAFT.md`, `docs/ieee_paper/` are untouched).

The upgraded evaluation returned a **negative result** for the downstream
components. That does not lower the *methodological* grade — a rigorous null is
a valid contribution — but it does bound hard what may be claimed.

---

## 1. Category grades

Scale: A (publishable as-is) · B (solid, minor gaps) · C (usable with explicit
caveats) · D (weak) · F (not usable).

| # | Category | Grade | Justification |
|---|---|:--:|---|
| 1 | **Methodological validity** | **B+** | Pre-registered before the locked run, family-level hold-out, fixed power analysis, one-shot locked test, exclusion rules specified in advance, protocol-deviation section. Deductions: power model ignores ties; condition A is a minimal-intervention reference rather than a literal no-op (disclosed, and `D_vs_naive` covers the gap). |
| 2 | **Internal validity** | **B** | Identical-feasible-action-space invariant enforced and verified per instance (0 failures); R0/D0 read-only; architecture fingerprint captured and reproduced. Deduction: the pipeline seeds an ephemeral business, so a few production knobs (marketing ROI sign) are fixed by the harness rather than varied. |
| 3 | **Metric independence** | **A−** | Primary metric is a closed-form model that imports none of the pipeline; enforced by a static-import scan **and** a poisoned-`sys.modules` runtime test. The internal `goal_achievement` is demoted to a labelled secondary. Residual: ground truth and `classical_optimizer` share the same closed form, so that baseline's small regret is partly definitional (stated). |
| 4 | **Baseline strength** | **B+** | naive, greedy, oracle, classical optimizer — none call DecisionGPT. greedy and classical are genuinely informative (both beat D). Missing: a learned/tuned external decision baseline, and any non-synthetic baseline. |
| 5 | **Scenario diversity** | **B** | 17 parameterised families, 340 instances, 20/family, seed-replicated. Locked test is only 4 families (80 instances) — adequate for the pre-registered power but a narrow slice of the design space for the *primary* conclusion. |
| 6 | **Statistical rigor** | **A−** | Scenario as the unit, matched-pairs rank-biserial estimator (not p-derived), paired scenario cluster bootstrap as the primary interval, Holm across the confirmatory family, both raw and adjusted p reported, a pre-stated "supported" rule combining p + CI + effect size. |
| 7 | **Robustness** | **C+** | 10 perturbation families, degradation curves, ground truth held fixed. But run on a 20-scenario × 2-seed subsample of the locked set — descriptive only, explicitly not confirmatory. |
| 8 | **Reproducibility** | **A−** | Every number in a machine-readable file with a recorded SHA-256; all seeds fixed; `generate`/`analyze`/`audit` deterministic; `run` deterministic up to the pipeline's own determinism (0 errors, stable fingerprint); full command sequence and an automated 12-check audit. Deduction: the frozen pipeline itself is not bit-for-bit re-verified across machines here. |
| 9 | **Agent informativeness** | **C** | The evaluation *exposes* that the agent layer, while active (FA/RM score ranges 0.57 / 0.71; changes D's pick vs greedy 82 % of the time), produces **no measurable objective improvement over decision simulation** and its family-level effects are bimodal. That is a clean negative finding — graded C because the object being evaluated underperforms, not because the evaluation is weak. |
| 10 | **External validity** | **F** | Zero. Synthetic only, by design and by hard constraint. No real SME data, no real customers, no real LLM, no prospective intervention, no human study. Nothing here transfers to a real-world claim. |
| 11 | **Publication readiness** | **B** (as a controlled-evaluation / negative-result / reproducibility paper) · **F** (as any "the system works / is validated / is superior" paper) | See §7. |

**Overall:** a methodologically sound, reproducible, **negative** controlled
synthetic evaluation. Grade the *method* B+/A−; grade the *system under test* on
this evaluation C/D; grade external validity F.

## 2. What claims are now supported

Supported **strictly within the synthetic controlled setting**:

1. On an exogenous objective, over 80 independently generated locked-test
   scenarios, **adding the agent layer to decision simulation gave no measurable
   improvement** (`D_vs_B`: mean Δ +0.034, 95 % CI [−0.078, +0.143], Holm
   p = 1.0).
2. **The single agent also gave no measurable improvement over decision
   simulation** (`C_vs_B` null).
3. **The full architecture performed significantly worse than a
   minimal-intervention reference** (`D_vs_A`: mean Δ +0.109, 95 % CI
   [+0.059, +0.161], Holm p = 0.0026).
4. **The full architecture is statistically indistinguishable from doing
   nothing** (`D_vs_naive` null) and **clearly worse than a trivial greedy
   heuristic** (mean Δ +0.227) and a standard optimiser on the modelled
   objective (mean Δ +0.399).
5. The agent layer's effect is **conditional** (associational, exploratory):
   it recovers value when decision simulation is misled by degraded observations
   and destroys value when decision simulation is already near-optimal.
6. The evaluation itself — exogenous metric, hold-out, power, seeds — is
   reproducible.

## 3. What remains unsupported

- Any real-world, SME, ROI, revenue, customer-behaviour, deployment, or
  business-effectiveness claim.
- Any claim that DecisionGPT, the Digital Twin, the agent layer, or the full
  system **improves decisions**.
- Any causal claim about real businesses.
- Any "validated for Indian SMEs" / "superior for SMEs" / "proven business
  improvement" statement.
- Any positive claim resting on the internal `goal_achievement` metric.
- Any claim that the agent layer adds objective value (the primary contrast is
  null; `D_vs_A` is negative).
- A general "the architecture is robust" claim (robustness is a descriptive
  subsample).

## 4. Does the upgraded evaluation materially improve on the original study?

**Yes, methodologically — and it makes the negative finding harder to dismiss.**

- It removes the original study's **metric circularity** (exogenous closed-form
  objective, independence enforced by tests).
- It removes the **no-hold-out** problem (family-level locked test, sealed
  pre-registration).
- It removes the **effective-n ≈ 12 / uncontrolled-multiplicity** problem
  (80 locked scenarios, scenario-level unit, Holm, cluster bootstrap,
  pre-registered power 0.86).
- It adds **external baselines** (greedy and classical both beat D — the
  original study had nothing to calibrate against).
- It adds a **generator ↔ risk-mechanism** decoupling (non-degenerate price
  histories) so the risk term is not saturated by construction.

It does **not** improve external validity (still zero) and it narrows the
*primary* conclusion to 4 families.

## 5. Which original weaknesses remain

| Original weakness | Status after upgrade |
|---|---|
| Circular / self-graded metric | **Resolved** (exogenous primary; internal demoted to secondary) |
| 12 hand-coded scenarios, no hold-out | **Resolved** (340 parameterised, family-level locked test) |
| Effective n ≈ 12, multiplicity uncontrolled | **Resolved** (scenario unit, Holm, cluster bootstrap, pre-registered power) |
| No external baselines / oracle | **Resolved** (naive/greedy/oracle/classical) |
| Generator ↔ risk confound | **Largely resolved** (non-degenerate histories; `adversarial_risk_trap` kept as a labelled diagnostic) |
| Rule-based agents, no real LLM | **Unchanged** (hard constraint) — findings are about this deterministic config |
| **No real SME / real-world / causal evidence** | **Unchanged — still zero** |
| Narrow scenario slice for the *primary* claim | **New, minor**: locked test is 4 of 17 families |
| Condition A ≠ literal no-op | **New, minor**: disclosed; `D_vs_naive` covers it |

## 6. Is the central RQ2 claim ("the multi-agent layer improves decision quality") supported, weakened, or unresolved?

**Refuted on this evaluation, consistent with the frozen study.**

- Primary confirmatory contrast `D_vs_B`: **null** (Holm p = 1.0, CI includes 0,
  |Δ| = 0.034 < the 0.10 minimum effect of interest).
- `D_vs_A`: the full architecture is **significantly worse** than the
  minimal-intervention reference.
- The only component that is ever near-optimal here is **decision simulation
  (B)**, and only on 2 of the 4 locked families; the agent layer then moves the
  decision *away* from that optimum on those families.

RQ2, as "the agent/coordination layer improves objective decision quality," is
**not supported**. The defensible residual claim is narrower and
mechanism-shaped: *the agent layer's contribution is conditional and, in
aggregate on this suite, not positive.*

## 7. Can the paper remain a "controlled synthetic evaluation" paper?

**Yes — and it should be explicitly a controlled-evaluation / negative-result /
reproducibility paper.** The upgraded evaluation is exactly the kind of evidence
that framing needs: a pre-registered, reproducible, exogenously-scored,
held-out component ablation with external baselines, returning a clear negative
result with a mechanistic (associational) explanation.

It **cannot** support a paper framed as "DecisionGPT works / is validated / is
superior / is effective for SMEs." Every such phrasing must be removed or
reframed as a research question that the evidence answers in the negative.

Recommended contribution statement: *"We build a decision-support architecture
(prediction → digital model → rule-based multi-agent evaluation → optimisation)
and subject it to a pre-registered, reproducible, exogenously-scored controlled
ablation. Adding the multi-agent evaluation layer does not improve objective
decision quality over the digital-model baseline on our synthetic suite, and the
full system underperforms a minimal-intervention reference and a trivial greedy
heuristic. We characterise, associationally, the conditions under which the
layer helps and hurts. All artifacts and analyses are reproducible from fixed
seeds."*

## 8. What must NOT be claimed (hard list)

- "validated" / "superior" / "effective" / "proven" for SMEs, Indian SMEs, or
  any real users
- any ROI, revenue, profit, cost, or customer-behaviour improvement
- any real-world or causal impact
- "the multi-agent layer improves decision quality" (refuted)
- "the full system outperforms simpler configurations" (refuted; the opposite on
  `D_vs_A`, null on `D_vs_B`)
- decision "accuracy" for any model metric
- deployment success or readiness
- anything resting on `goal_achievement` / the internal metric
- promotion of R3 or any change to R0/D0

## 9. Bottom line

The upgraded evaluation is a **strong methodological upgrade** and a **clean
negative result**. It makes the paper *more* publishable **as a negative-result
/ controlled-evaluation / reproducibility contribution** and **less** defensible
as anything else. External validity is unchanged at zero. Table 2 stays NOT
READY; real LLM stays BLOCKED; production stays R0/D0; R3 stays NOT PROMOTED.
