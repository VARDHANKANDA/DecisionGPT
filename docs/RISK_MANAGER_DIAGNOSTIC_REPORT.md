# Risk Manager Diagnostic & Controlled Risk-Penalty Sensitivity Study

Experiment `risk_manager_diagnostic` id `ba56e42b`, seeds 42–46, 12 scenarios
(S01–S12) × 5 seeds = **60 scenario-seed pairs**, LLM template mode.
Nothing in the Risk Manager (weights, thresholds, penalty formula, categories)
was modified. `D1` is a **labelled sensitivity variant**, not the architecture.

## What was done

1. **Traced the risk-score path** for every strategy in every scenario/seed —
   `DT risk → RM score → risk penalty → optimizer final score → selection` —
   from the stored `AgentEvaluation` + `DigitalTwinSimulation` rows and
   `DecisionResult.debate` (390 strategy rows).
2. **Verified the optimizer formula** by recomputation on every row.
3. **Compared RM scores against the Digital Twin's own simulated risk**, per
   price / marketing lever family.
4. **Quantified risk-penalty dominance** — for every scenario/seed, recomputed
   the ranking with the risk-penalty term removed and classified the pair
   `RM_DECISIVE` / `RM_NON_DECISIVE`.
5. **Ran D0 and D1 paired** — `D0` = production Full DecisionGPT;
   `D1` = Full DecisionGPT with `risk_penalty_in_ranking=False` (the Risk
   Manager still runs, still challenges peers in round 2, still feeds the
   confidence `risk_factor`; only its weight in the ranking score is 0).
6. **Paired Wilcoxon** (D1 − D0) via the existing research protocol.

## 1 · Risk-score path (formula verification)

The optimizer applies, unchanged (`strategy_optimizer.FORMULA_VERSION = "v2"`):

```
final_score = (BA_round2 + FA_round2) / 2 − w · (1 − RM_round2)
```

with `w = 1.0` in production. Round-2 self-adjustments are inactive in
template mode, so `BA_round2 = BA_round1`, etc.

| Check | Result |
|---|---|
| `final_score == (BA+FA)/2 − (1−RM)` for every strategy row | **holds — 390/390 rows, max deviation 0.000000** |
| Rows where the Risk Manager top-pick ≠ Digital-Twin sweep best | **60/60 (100 %)** |

## 2 · Risk Manager calibration vs Digital-Twin simulated risk

`risk_manager.evaluate` sets `score = clamp01(1 − DT_risk_score −
uncertainty_penalty − inventory_penalty − causal_penalty)`. The dominant term
is `DT_risk_score`, the Digital Twin's own extrapolation-risk heuristic
(`digital_twin_service._risk_from_extrapolation`: the largest fractional
overshoot of a scenario input beyond the range that input has taken in the
business's history).

| Strategy | Obs | Mean DT risk | Mean RM score | RM = 0 rate | DT-risk LOW rate |
|---|---:|---:|---:|---:|---:|
| Price +5% | 50 | **0.680** | 0.015 | 0.80 | 0.00 |
| Price +10% | 50 | **0.983** | 0.000 | 1.00 | 0.00 |
| Price −3% | 30 | 0.000 | 0.500 | 0.00 | 1.00 |
| Price −5% | 30 | 0.000 | 0.500 | 0.00 | 1.00 |
| Marketing +10% | 50 | 0.000 | 0.507 | 0.00 | 1.00 |
| Marketing +20% | 35 | 0.000 | 0.500 | 0.00 | 1.00 |
| Marketing −10% | 20 | 0.000 | 0.517 | 0.00 | 1.00 |

**`RISK_SCORE_MISMATCH` count = 0 / 390.** There is **no** case of "DT risk
LOW but RM score zero". Every time the RM zeroes a price-increase strategy, the
Digital Twin has itself assigned that strategy a high extrapolation-risk score
(0.68 for `Price +5%`, 0.98 for `Price +10%`). The verdict of the
distinguish-check: *"RM score tracks DT risk across price strategies"*
(RM-score spread 0.5, DT-risk spread 1.0 across the 210 price-strategy
observations).

> **The Risk Manager is not mis-scoring relative to the Digital Twin — it is
> faithfully transmitting the Digital Twin's extrapolation-risk score.** The
> reason that score is high for a *modest* price rise is that the synthetic
> research businesses hold price almost constant in their 90-day history, so
> `_risk_from_extrapolation` treats any price move as far outside the observed
> range. That is a Digital-Twin heuristic × synthetic-scenario-design
> interaction, propagated by the RM and made decisive by the optimizer's
> unbounded `−(1−RM)` term.

## 3 · Risk-penalty dominance

| | Value |
|---|---:|
| `RM_DECISIVE` (removing only the penalty changes the selection) | **45 / 60 (75.0 %)** |
| …of those, the penalty-free pick **improved** the objective | **35** |
| …**degraded** | **0** |
| …**neutral** | **10** |
| Pairs where D1's real selection matched the offline penalty-free recompute | 60/60 (1.00) |

The 15 non-decisive pairs are the proxy-KPI scenarios (S04, S07) and the
no-marketing scenario S10 and similar, where the penalty-free ranking still
tops out at the same strategy.

## 4/5 · D0 vs D1 (paired, n = 60)

| Metric | D0 · Full DecisionGPT | D1 · No Risk Penalty |
|---|---:|---:|
| Goal achievement — mean [95 % CI] | **0.084** [0.013, 0.156] | **0.583** [0.469, 0.698] |
| Goal achievement — median | 0.000 | 0.758 |
| Risk-adjusted score — mean | −2 614.8 | −2 522.0 |
| Confidence — mean [95 % CI] | 0.139 [0.126, 0.152] | **0.018** [0.007, 0.030] |
| DT-best agreement rate | 0.00 | 0.00 |
| Override rate vs DT-best | 1.00 | 1.00 |

### Paired difference (D1 − D0), goal achievement

| | Value |
|---|---:|
| Mean difference | **+0.4989** (95 % CI [0.383, 0.615]) |
| Median difference | +0.5689 |
| D1 wins / ties / D0 wins | **35 / 25 / 0** |
| Wilcoxon signed-rank | N = 60, **p < 0.0001**, effect size **r = 0.89** |

## 6 · Statistical test

Paired Wilcoxon signed-rank on scenario × seed (same protocol as
`docs/STATISTICAL_ANALYSIS.md`): **N = 60, p < 0.0001, r = 0.89 (large)**.
D1 goal achievement is significantly higher than D0; D1 never loses a pair.

## 7 · D1 is a sensitivity variant, not the architecture

The official architecture remains **Full DecisionGPT = D0**. `D1` is the
**Risk-Penalty Sensitivity Variant** (`PipelineOptions(risk_penalty_in_ranking=False)`,
`strategy_optimizer.resolve(..., risk_penalty_weight=0.0)`), used here only to
isolate the mechanism. Paper Table 4 is unchanged.

## 8 · Does removing the penalty help? — **Outcome A (with caveats)**

**D1 mean goal achievement 0.583 vs D0 0.084 (Δ +0.499) — it not only improves,
it slightly exceeds the Digital Twin's 0.486** (124 % of the D0→DigitalTwin
gap). By the objective KPI, the risk-penalty term is the **dominant
bottleneck**.

Three caveats keep this from being a validated fix:

1. **Confidence collapses.** D1 mean confidence 0.139 → **0.018**. The
   confidence formula's `risk_factor` *is* the RM score, and D1 selects
   strategies with RM ≈ 0. D1 buys goal achievement with strategies the system
   itself rates near-zero-confidence.
2. **Risk-adjusted score barely moves** (−2 614.8 → −2 522.0, still deeply
   negative). `risk_adjusted = benefit × (1 − DT_risk_score)` and
   `DT_risk_score ≈ 1` for the picked `Price +10%` moves — the raw KPI rises
   but the risk-discounted view does not.
3. **D1 does not "converge to the Digital Twin's choice."** DT-best agreement
   stays 0.00 — D1 picks `Price +10%` (the most aggressive lever, highest
   `(BA+FA)/2`), not the grid's revenue-max `Price +5%`. Un-weighting the
   penalty removes the only brake on lever magnitude.

## Answers (task section 14)

| Question | Answer |
|---|---|
| Does removing **only** the RM penalty improve Full DecisionGPT? | **YES** — 0.084 → 0.583, p < 0.0001, r = 0.89, 35/60 wins, 0 losses |
| Does the Risk Manager explain the Full-vs-Digital-Twin gap? | **YES (proximately)** — the `−(1−RM)` term is decisive in 75 % of pairs and its removal closes the gap. But the RM is faithfully passing through the **Digital Twin's** extrapolation-risk score (0 mismatch cases), and D1 trades away confidence and risk-adjusted score to get the KPI. |
| Next recommended action | A **principled calibration experiment** targeting (a) `digital_twin_service._risk_from_extrapolation`'s zero-variance-history degeneracy (`span = max(hi−lo, 1e-9)` makes any price move "infinite overshoot"), and (b) whether the optimizer's risk term should be **bounded / weighted** rather than able to swing `final_score` by a full 1.0. Implement neither in this task. |

## Preserved

Legacy `decision_architecture` / `ablation`; PRE/POST `multi_scenario_architecture`
(`675cf17e` / `0e1bd8dc`), `multi_scenario_ablation` (`be392694` / `db58455b`),
`multi_agent_diagnostic` (`c58c4537` / `f24abc1b`); forecasting / churn / causal
/ digital_twin / multi_agent. All 13 prior experiment IDs unchanged; the new
`risk_manager_diagnostic` (`ba56e42b`) is additive. Production models unchanged;
Paper Results still 4/5 ready (Table 2 needs `DecisionOutcome` records).
`decision_architecture_service` / the four architectures A–D / the ablation
meanings A–F are untouched. The only production-code change is an additive,
default-`True` `PipelineOptions.risk_penalty_in_ranking` flag threaded into
`strategy_optimizer.resolve` as `risk_penalty_weight` (default `1.0`, so every
production path is byte-identical).
