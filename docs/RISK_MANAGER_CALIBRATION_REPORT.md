# RISK MANAGER CALIBRATION REPORT

Experiment `risk_manager_calibration` id `b8516eef`, seeds 42–46, 12 scenarios ×
5 seeds = 60 paired evaluations per variant. **Verdict: PROMISING** (R2-0.25 and
R3 satisfy all seven pre-specified criteria). No variant promoted; production
stays R0 / D0.

> **Authoritative current state (updated for paper preparation, 2026-09-03).**
> The "sign-off" block near the end of this report ("all 14 prior experiment IDs
> preserved", "271 passed", "alembic `0001<->0006`") is a **point-in-time
> snapshot** from the task that added `b8516eef`; it was never back-updated.
> Nothing about the `b8516eef` result changed. Current authoritative state:
> **16 frozen experiments**, Alembic head **0007**, backend suite **319 passed,
> 1 skipped**, `experiment_manifest.json` sha256 `94aa419c…`. Production stays
> **R0 / D0**; R3 remains **PROMISING — NOT PROMOTED**. The paper must report the
> R3 vs R0 comparison as **mean paired difference +0.083 [0.019, 0.148],
> p = 0.0253, 5 / 55 / 0 (wins / ties / losses), 5 of 60 non-zero pairs** — do
> not round to +0.084 and do not present r = 1.00 as a large practical effect.

## 1. Research question

Can the Risk Manager incorporate Digital Twin extrapolation uncertainty in a
more *calibrated* way so that (1) genuinely risky extrapolation stays penalised,
(2) ordinary small price changes are not treated as catastrophic merely because
historical price variance is low, (3) the Risk Manager does not dominate
strategy selection, (4) confidence stays meaningful, and (5) Full DecisionGPT
improves **without simply deleting risk management**?

The objective is **not** to maximise goal achievement — it is to determine
whether the existing extrapolation-risk mechanism is miscalibrated and whether a
principled reformulation improves the risk/benefit trade-off.

## 2. Existing risk formulation

`digital_twin_service._risk_from_extrapolation` (`risk_formula_version =
extrapolation_range_v1`): for each of `price` and `marketing_spend`,
`overshoot = (amount the scenario value lies outside the observed [min, max]) /
max(max − min, 1e-9)`; `risk_score = min(max overshoot, 1.0)`; bands
`< 0.15 LOW`, `< 0.5 MODERATE`, else `HIGH`. The Risk Manager maps it via
`RM = clamp01(1 − risk_score − uncertainty_penalty − inventory_penalty −
causal_penalty)`, and the optimizer applies `final_score = (BA+FA)/2 −
λ·(1 − RM)` with `λ = 1`. Full derivation + worked example:
`docs/RISK_CALIBRATION_ANALYSIS.md`.

## 3. Identified numerical / statistical issue

Normalising by the raw observed range `max − min` makes the score explode as the
denominator → 0. In the synthetic research businesses the only price variation
is the promotional discount, so the yardstick for "how far a price *increase*
extrapolates" is the *promo depth* — unrelated to actual extrapolation risk.
Constant-history stress test (`[100,100,100,100,100]`): every move (+5 %, +10 %,
−5 %) scores `risk = 1.0` and the ordering between move sizes is destroyed.
Suite-scale evidence (Risk Manager diagnostic `ba56e42b`): mean R0 risk
`Price +5%` ≈ 0.68, `Price +10%` ≈ 0.98; 0 / 390 `RISK_SCORE_MISMATCH` — the
Risk Manager is faithful; the **formula** is the issue.

## 4. Calibration variants

| Variant | Risk estimate | Ranking penalty | Notes |
|---|---|---|---|
| **R0** | `extrapolation_range_v1` (production) | `λ = 1.0` | == D0. Unchanged. |
| **D1** | `extrapolation_range_v1` | `λ = 0.0` | reference only (risk penalty removed). |
| **R1** | `extrapolation_robust_v1` — normaliser `max(hi−lo, 1.4826·MAD, 0.15·|median|)` | `λ = 1.0` | robust scale; `REL_FLOOR = 0.15` pre-specified, not tuned. |
| **R2-0.25 / R2-0.50 / R2-0.75** | `extrapolation_range_v1` | `λ ∈ {0.25, 0.50, 0.75}` | bounded penalty contribution; pre-specified discrete set. |
| **R3** | `extrapolation_robust_v1` | `λ` = **0.25** | R1 + the λ chosen by the pre-specified criterion (§12): smallest λ whose R2-λ keeps risk-adjusted ≥ D0 and confidence ≥ 0.60 × D0 → λ = 0.25. |

## 5. Experimental protocol

- **Scenarios** S01–S12; **seeds** 42, 43, 44, 45, 46 → 60 paired
  scenario-seed evaluations per variant.
- **Dataset**: the deterministic synthetic research businesses
  (`decision_architecture_service._seed_synthetic_business`, keyed
  `scenario_id:seed`). No real `DecisionOutcome` records.
- **Fairness controls**: each variant runs against a freshly-seeded business
  that is *byte-identical by determinism* to every other variant's; the Digital
  Twin's predicted units / revenue / profit, the candidate set, the agent
  growth scores (BA / FA), the causal evidence and the seeds are unchanged.
  Only risk estimation (R1) and ranking-penalty weight (R2 λ) vary.
- **Statistics**: sample mean / median / std, Student-t 95 % CI; paired
  Wilcoxon signed-rank (variant − R0) on scenario × seed. Results are on the
  fixed synthetic suite — no population-level generalisation is claimed.

## 6. Results

n = 60 per variant. Digital Twin (architecture B) reference mean goal
achievement = **0.486**.

| Variant | Goal achievement (mean [95 % CI]) | Risk-adjusted (mean) | Confidence (mean) | DT-best agreement | Selection changed vs R0 |
|---|---:|---:|---:|---:|---:|
| **R0** (= D0, production) | 0.084 [0.013, 0.156] | −2 614.8 | 0.139 | 0 % | — |
| D1 (no penalty — reference) | 0.583 [0.469, 0.698] | −2 522.0 | **0.018** | 0 % | 45 / 60 |
| **R1** (robust risk, λ = 1) | 0.084 [0.013, 0.156] | −2 263.0 | 0.141 | 8.3 % | 5 / 60 |
| **R2-0.25** | **0.168 [0.071, 0.265]** | −2 614.8 | 0.109 | 0 % | 10 / 60 |
| R2-0.50 | 0.084 [0.013, 0.156] | −2 614.8 | 0.139 | 0 % | 0 / 60 |
| R2-0.75 | 0.084 [0.013, 0.156] | −2 614.8 | 0.139 | 0 % | 0 / 60 |
| **R3** (R1 + λ = 0.25) | **0.168 [0.071, 0.265]** | **+40.5** | 0.109 | 0 % | 10 / 60 |

- **R1 alone changes nothing about goal achievement.** Its 5 selection changes
  are all S10 (`Price +10% → Price +5%`) at equal goal achievement (1.0 → 1.0):
  the robust risk makes the system prefer the *less aggressive* price move. It
  does lower the mean strategy DT-risk 0.271 → 0.154, raise mean RM safety
  0.329 → 0.362, and improve risk-adjusted −2 614.8 → −2 263.0.
- **R2-0.25 improves goal achievement** 0.084 → 0.168. Its 10 changes: S03 ×5
  (`Marketing +10% → Price +10%`, orders KPI, 0 → 0) and **S08 ×5
  (`Marketing −10% → Price +10%`, thin-margin profit, 0 → 1.0)** — 5 genuine
  wins. Risk-adjusted is unchanged (R2 keeps R0's risk score, so the selected
  `Price +10%` still carries `DT_risk ≈ 1` and `benefit × (1 − risk) ≈ 0`).
- **R2-0.50 and R2-0.75 change nothing** — the residual penalty is still large
  enough for the zero-benefit marketing move to win.
- **R3 = R1 + λ = 0.25 is the best variant.** Same 10 selection changes and the
  same goal-achievement gain as R2-0.25, **but risk-adjusted score flips
  −2 614.8 → +40.5**: R1 gives S08's `Price +10%` a realistic lower risk score,
  so its large profit benefit is no longer discounted to zero. Confidence
  0.109 (well above the 0.083 floor); risk ordering intact.

## 7. Risk calibration results

R1 / R3 (`extrapolation_robust_v1`) vs R0 (`extrapolation_range_v1`):

| Quantity | R0 | R1 / R3 |
|---|---:|---:|
| Mean strategy DT-risk (all candidates) | 0.271 | **0.154** |
| Mean strategy RM safety score | 0.329 | **0.362** |
| Mean risk-adjusted score | −2 614.8 | −2 263.0 (R1) / **+40.5** (R3) |
| DT-best agreement rate | 0 % | 8.3 % (R1) |

The robust scale lowers risk **only where the raw range was degenerate** (price
moves against a promo-only history); it does not touch the marketing feature
(non-degenerate) — mean marketing risk is 0 under both.

## 8. Risk ordering / monotonicity

Spearman ρ between the **raw natural-unit extrapolation distance** (₹ the
scenario pushes price / marketing beyond the observed range) and the assigned
risk score, across all 480–560 strategy rows per variant:

| Variant | Spearman ρ | `Price +10%` scored safer than `Price +5%` |
|---|---:|---:|
| R0 | 0.976 | **0** |
| D1 | 0.976 | 0 |
| R1 | 0.969 | **0** |
| R2-0.25 / 0.50 / 0.75 | 0.976 | 0 |
| R3 | 0.969 | **0** |

**Risk ordering is preserved by every calibration variant** (ρ ≈ 0.97–0.98).
R1/R3 lose only 0.007 of ρ — the robust scale does not flatten the
distance→risk relationship. **Zero monotonicity violations** anywhere: a larger
price move is never scored safer than a smaller one.

## 9. Zero-variance analysis

Extrapolation risk for a ±5 % / +10 % price move, by history type (R0 → R1):

| History | +5 % | +10 % | −5 % |
|---|---|---|---|
| constant `[100, 100, 100, 100, 100]` | 1.00 → **0.33** | 1.00 → **0.67** | 1.00 → **0.33** |
| low-variance `[99, 100, 101, 100, 100]` | 1.00 → **0.27** | 1.00 → **0.60** | 1.00 → **0.27** |
| normal-variance `[95, 100, 105, 100, 98]` | 0.00 → 0.00 | 0.50 → **0.33** | 0.00 → 0.00 |

**R0's pathology is real and R1 removes it.** Under R0 a constant history makes
every move — including a *price cut* — maximally risky, and `+5 %` is
indistinguishable from `+10 %`. Under R1 the constant-history scores are
monotone (`0.33 < 0.67`), bounded, and symmetric for ±5 %. The
normal-variance case is barely touched (within-range moves stay 0; the `+10 %`
overshoot softens 0.50 → 0.33 because the 15 %-of-median floor slightly exceeds
the 10-wide observed range).

## 10. Statistical tests

Paired Wilcoxon signed-rank, variant − R0, on scenario × seed (n = 60):

| Variant vs R0 | Mean diff | 95 % CI | Wins / Ties / Losses | p | effect size r |
|---|---:|---:|---:|---:|---:|
| D1 (reference) | +0.499 | [0.383, 0.615] | 35 / 25 / 0 | < 0.0001 | 0.89 |
| **R1** | 0.000 | — | 0 / 60 / 0 | *not assessed (all differences zero)* | — |
| **R2-0.25** | **+0.083** | [0.019, 0.148] | 5 / 55 / 0 | **0.0253** | 1.00 |
| R2-0.50 | 0.000 | — | 0 / 60 / 0 | *not assessed* | — |
| R2-0.75 | 0.000 | — | 0 / 60 / 0 | *not assessed* | — |
| **R3** | **+0.083** | [0.019, 0.148] | 5 / 55 / 0 | **0.0253** | 1.00 |

R2-0.25 and R3 produce a statistically significant, if small, improvement over
D0 (5 wins, 0 losses). The effect size `r = 1.0` reflects that all 5 non-zero
paired differences point the same way — it is *not* a claim of a large practical
effect (the mean shift is +0.083). Results are on the fixed synthetic suite; no
population-level generalisation is claimed.

## 11. Comparison with Digital Twin

| | Goal achievement | Gap to Digital Twin (0.486) | Fraction of D0→DT gap closed |
|---|---:|---:|---:|
| Digital Twin (B) | 0.486 | — | — |
| R0 / D0 | 0.084 | −0.402 | 0 % |
| R2-0.25 | 0.168 | −0.318 | **~21 %** |
| R3 | 0.168 | −0.318 | **~21 %** |
| D1 (no risk mgmt) | 0.583 | +0.097 | > 100 % (but confidence 0.018) |

**Calibration narrows the Full-vs-Digital-Twin gap by roughly a fifth** while
preserving risk sensitivity and confidence. It does **not** close it. The
residual is not the risk term: with the penalty removed entirely (D1) the gap
closes, but only by selecting near-zero-confidence strategies. The remaining
driver is the near-flat agent growth scores (BA / FA ≈ 0.5 for every candidate
in template mode), which leave selection hostage to whatever small term breaks
the tie.

## 12. Pre-specified criteria

A calibration variant is **PROMISING** only if it satisfies all seven:
1. improves goal achievement over D0;
2. does not eliminate risk ordering (Spearman ρ between raw extrapolation
   distance and risk score ≥ 0.30);
3. no `Price +10%` scored safer than `Price +5%` (monotonicity violations = 0);
4. improves or preserves risk-adjusted performance vs D0;
5. avoids the D1 confidence collapse (mean confidence ≥ 0.60 × D0);
6. remains interpretable (one documented formula / weight);
7. no scenario-specific tuning (one global parameter set).

**PARTIALLY PROMISING** = criteria 1–3 hold and ≥ 5 / 7 pass; otherwise
**NO SATISFACTORY CALIBRATION**.

**R3 λ selection (fixed before the run):** among `λ ∈ {0.25, 0.50, 0.75}`, the
smallest λ whose `R2-λ` run keeps mean risk-adjusted score ≥ D0 **and** mean
confidence ≥ 0.60 × D0; else fallback λ = 0.50. → **λ = 0.25** selected
(R2-0.25: risk-adjusted −2 614.8 = D0, confidence 0.109 ≥ 0.083).

| Criterion | R1 | R2-0.25 | R2-0.50 | R2-0.75 | R3 |
|---|:--:|:--:|:--:|:--:|:--:|
| 1. improves goal achievement over D0 | ✗ | ✓ | ✗ | ✗ | ✓ |
| 2. preserves risk ordering (ρ ≥ 0.30) | ✓ (0.969) | ✓ | ✓ | ✓ | ✓ (0.969) |
| 3. no monotonicity violations | ✓ | ✓ | ✓ | ✓ | ✓ |
| 4. preserves risk-adjusted vs D0 | ✓ (−2 263) | ✓ (=D0) | ✓ | ✓ | ✓ (**+40.5**) |
| 5. no confidence collapse (≥ 0.60 × D0) | ✓ (0.141) | ✓ (0.109) | ✓ | ✓ | ✓ (0.109) |
| 6. interpretable | ✓ | ✓ | ✓ | ✓ | ✓ |
| 7. no scenario-specific tuning | ✓ | ✓ | ✓ | ✓ | ✓ |
| **passed** | 6 / 7 | **7 / 7** | 6 / 7 | 6 / 7 | **7 / 7** |
| **verdict** | NO SATISFACTORY | **PROMISING** | NO SATISFACTORY | NO SATISFACTORY | **PROMISING** |

## 13. Verdict

**PROMISING.** Two variants — **R2-0.25** (bounded penalty weight alone) and
**R3** (robust extrapolation scale + λ = 0.25) — satisfy all seven pre-specified
criteria. **R3 is the stronger of the two**: it delivers the same
goal-achievement gain as R2-0.25 (0.084 → 0.168, p = 0.025) *and* turns the mean
risk-adjusted score from −2 614.8 to +40.5, because the robust risk score stops
the Digital Twin from discounting a genuinely good price move to zero.

- **Is the underlying extrapolation-risk formulation poorly calibrated?**
  **YES.** The zero-variance diagnostic is definitive: a constant or
  low-variance price history makes R0 score every move — including a price cut —
  at risk 1.0, and R0 cannot rank `+10 %` above `+5 %` there. `Price +5%` real
  risk ≈ 0.68 across the suite for what is an ordinary lever.
- **Can it be corrected without simply removing risk management?**
  **YES.** R3 keeps the Risk Manager fully active, preserves risk ordering
  (ρ = 0.969, 0 violations) and confidence (0.109, vs D1's collapse to 0.018),
  yet improves both the objective and the risk-adjusted trade-off.
- **Does it close the Full-vs-Digital-Twin gap?** **No — only ~21 % of it.**
  The rest is a separate mechanism (flat template-mode agent growth scores).

## 14. Limitations

- Results are on the 12-scenario × 5-seed **synthetic** suite; the synthetic
  price histories are themselves low-variance (promo-only), which is exactly the
  regime the study probes but is not representative of every real SME.
- LLM template mode: agent growth scores (BA / FA) are near-flat (≈ 0.5), so
  strategy ranking is unusually sensitive to the risk term. A real LLM might
  produce more separated growth scores.
- Round-2 peer review is inactive in template mode.
- `REL_FLOOR = 0.15` and `λ ∈ {0.25, 0.50, 0.75}` are motivated but not the
  only defensible choices; this study deliberately did **not** search further.
- Risk-adjusted score uses `benefit × (1 − DT_risk_score)`, so under R1 it
  reflects the R0 `DT_risk_score` embedded in earlier persisted sims only where
  noted; the calibration run recomputes it from each variant's own sims.

## 15. Recommendation

A **carefully controlled production calibration of R3** — the robust
extrapolation scale (`extrapolation_robust_v1`, `REL_FLOOR = 0.15`) together
with a bounded optimizer risk-penalty weight `λ ≈ 0.25` — is now **justified as
the next task**, subject to:

1. **Validate on non-degenerate real histories.** The synthetic suite is
   deliberately low-variance; R1 must be checked to not *under*-penalise real
   businesses whose price genuinely varies (the `max(hi−lo, …)` term is
   designed to prevent this, but it needs empirical confirmation).
2. **Treat the gain as modest.** R3 closes only ~21 % of the D0→Digital-Twin
   gap; the dominant residual is the flat agent growth scores in template mode.
3. **Re-run with a real LLM** before any production change — separated agent
   growth scores could change which term is decisive.
4. **Keep λ as an explicit, documented optimizer parameter**, not a hidden
   constant, so it stays auditable.

Until then: production stays **R0 / D0**. No variant is promoted by this task.

## 16. Reproducibility information

- Experiment type `risk_manager_calibration`; id `b8516eef`; seeds
  [42, 43, 44, 45, 46]; dataset `synthetic_scenario_suite`.
- Code: `app/services/risk_calibration_service.py`;
  `digital_twin_service._calibrated_risk_from_extrapolation` /
  `_feature_history_stats` / `_robust_feature_scale`
  (`RISK_FORMULA_VERSION_ROBUST = "extrapolation_robust_v1"`,
  `ROBUST_SCALE_REL_FLOOR = 0.15`);
  `PipelineOptions.risk_model` / `.risk_penalty_lambda` (defaults `None` / `1.0`
  → production unchanged); `strategy_optimizer.compute_strategy_score(...,
  risk_penalty_weight)`.
- Pre-registration: `docs/RISK_CALIBRATION_ANALYSIS.md`.
- Manifest: `experiments/experiment_manifest.json`. All prior experiment IDs
  unchanged.

---

## Final summary

```
Baseline D0 (R0):        goal achievement 0.084  [95% CI 0.013, 0.156]
Digital Twin (B):        goal achievement 0.486

Variant:                 R3  (robust extrapolation scale + risk-penalty λ = 0.25)
Goal achievement:        0.168  [95% CI 0.071, 0.265]
Risk-adjusted:           +40.5   (D0: −2614.8)
Confidence:              0.109   (D0: 0.139 ; D1: 0.018)
DT-best agreement:       0%      (selection changed vs R0 on 10/60 pairs; 5 wins, 0 losses)
Spearman rho:            0.969   (raw extrapolation distance vs risk score ; D0: 0.976)
Monotonicity violations: 0       (Price +10% never scored safer than Price +5%)
Wilcoxon (R3 − R0):      N = 60
p:                       0.0253
effect size:             r = 1.00  (5 non-zero paired diffs, all positive; mean shift +0.083)

Also PROMISING:          R2-0.25  (bounded λ alone): goal achievement 0.168, but
                         risk-adjusted unchanged (−2614.8). R1 alone: goal
                         achievement unchanged (0.084) — fails criterion 1.

Verdict:                 PROMISING  (R2-0.25 and R3 pass all 7 pre-specified criteria)

Is the extrapolation-risk formula poorly calibrated?   YES  (zero-variance diagnostic definitive)
Can it be fixed without removing risk management?       YES  (R3 keeps risk ordering + confidence)
Does calibration close the Full-vs-Digital-Twin gap?    NO   (only ~21% of it)

Production architecture changed:   NO   (additive PipelineOptions.risk_model / .risk_penalty_lambda,
                                        defaults None / 1.0 → production byte-identical; no variant promoted)
Production models changed:         NO
Previous experiment results changed: NO   (all 14 prior experiment IDs preserved; new id b8516eef)
New experiment IDs:                b8516eef  (risk_manager_calibration v1)

Tests:  [point-in-time snapshot — see the authoritative box at the top of this file]
Backend:   pytest -q — 271 passed, 1 skipped   (current authoritative: 319 passed, 1 skipped)
Frontend:  npm run build compiled (tsc clean) ; npm run lint 0 errors
E2E:       scripts/audit_e2e.py — no assertion failures ; alembic round-trip clean, no schema change
           (round-trip target was 0001<->0006 at the time; current head is 0007)
```
