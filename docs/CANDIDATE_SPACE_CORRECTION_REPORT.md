# Candidate-Space Correction & Controlled Re-test

## Problem identified

The multi-agent diagnostic (`docs/MULTI_AGENT_DIAGNOSTIC_REPORT.md`, experiment
`multi_agent_diagnostic` id `c58c4537`) found a **candidate-space mismatch**:

- Architectures **B / C** sweep the fixed `decision_service.CANDIDATE_GRID`,
  which **includes `Price +5%`**.
- Architecture **D** (Full DecisionGPT) instead calls
  `strategy_generation_service.generate_candidates`, whose
  `_revenue_templates()` / `_sales_templates()` contained **only
  marketing-increase and price-*decrease*** levers — **no price-increase**.
- Result: in **30 / 60** scenario-seed pairs the Digital-Twin's best strategy
  (`Price +5%`, on the `increase_revenue` / `increase_sales` scenarios) was
  **never presented to the agents** — classified `CANDIDATE_SET_MISMATCH`
  (50 % of all pairs). The architectures were not comparing the same
  legitimate strategy space.

## Correction applied (principled, capability-gated — not tuning)

`strategy_generation_service._revenue_templates()` gains two entries:
`Price +5%` and `Price +10%`, framed around revenue (revenue = price ×
volume; a price rise lifts revenue where the volume it costs is smaller than
the price gain — the Digital Twin checks which). `_sales_templates()` derives
from `_revenue_templates()` and inherits them.

This is legitimate because a price increase:
- is a real revenue/sales lever the **Digital Twin already simulates**
  (same `price_change` action type; within `ACTION_VALUE_BOUNDS`),
- is already in the fixed `CANDIDATE_GRID` that B/C sweep,
- is already in the sibling `_profit_templates()`.

**Not touched:** the Risk Manager (preserved exactly), the Causal Graph, the
Multi-Agent Engine, the Digital Twin, the optimizer, the agents, the
scenarios, the seeds, the metrics, the dataset, the statistical methodology.
`Marketing -10%` remains **excluded** for revenue/sales goals — it is
counterproductive for those objectives, not unsupported (documented; the
coverage check confirms it never causes a *supported* DT-best to be missing).
Goals that need data the business lacks (`improve_marketing_roi`,
`reduce_inventory_risk`) still return an explicit insufficient-evidence result.

## Candidate-coverage check (task §6 / §7)

Computed per `(scenario, seed)` before the final rerun: `DT_candidate_count`,
`Full_candidate_count`, `DT_best_strategy`, `DT_best_strategy_present_in_full`,
`dt_best_strategy_supported` (a price/marketing lever is *supported* for
revenue/profit/orders goals; for `inventory_risk` / `marketing_roi` goals the
`max(expected_revenue)` "DT best" is an artefact of architecture B's crude
ranking rule and is **not** a strategy Full DecisionGPT should generate).

| | Pre-correction (`c58c4537`) | **Post-correction (`f24abc1b`)** |
|---|---:|---:|
| `candidate_coverage_rate` (DT-best present in Full's generated set) | 0.333 (20/60) | **0.833 (50/60)** |
| `missing_supported_strategy_rate` | 0.500 (30/60 — S01/S03/S06/S09/S11/S12 × 5 seeds) | **0.000 (0/60)** |
| mean DT candidates / mean Full candidates | 6.0 / 5.5 | 6.0 / **6.5** |
| invariant *(DT-best present when supported)* | **FAILS** — 30 supported pairs missing the DT-best strategy | **HOLDS** — 0 missing supported pairs |

The pre-correction column is derived from run `c58c4537`'s stored
failure-mode breakdown (`CANDIDATE_SET_MISMATCH` 30 = DT-best absent for a
*supported* goal; `UNSUPPORTED_KPI` 10 = DT-best absent for a proxy-KPI goal;
present = 60 − 30 − 10 = 20); the post-correction column is the
`candidate_coverage` block the instrumented diagnostic (`f24abc1b`) now stores
directly.

The 10 remaining "not present" post-correction pairs are S04
(`reduce_inventory_risk`) and S07 (`improve_marketing_roi`) × 5 seeds — where
the `max(expected_revenue)` "DT best" is a `Price +5%` that is **not** a
legitimately-supported strategy for those objectives (the objective's template
set correctly excludes it). They are classified `UNSUPPORTED_KPI`, not a
coverage failure — so `missing_supported_strategy_rate` is 0.000 and the
invariant holds.

**The confound is fixed.** The pre-run STOP condition of §6 (invariant fails)
was cleared before the final controlled re-test.

## Controlled re-test

Identical configuration — Scenarios S01–S12, Seeds 42–46, architectures
A/B/C/D, same evaluation horizon, same metrics, same paired-Wilcoxon
methodology (`docs/STATISTICAL_ANALYSIS.md`). The pre-correction experiments
are **preserved** and relabelled `PRE_CORRECTION …`; the new runs are
`POST_CORRECTION …` with fresh experiment IDs. `multi_scenario_ablation` **was
re-run** because the corrected `generate_candidates` is on the decision
pipeline path the ablation exercises.

### Architecture comparison — PRE vs POST (n = 60 per architecture)

| Architecture | PRE mean (95% CI) | POST mean (95% CI) |
|---|---:|---:|
| A · Prediction only | 0.000 [0.000, 0.000] | **0.000 [0.000, 0.000]** |
| B · Prediction + Digital Twin | 0.486 [0.405, 0.567] | **0.486 [0.405, 0.567]** |
| C · + Single Agent | 0.003 [0.001, 0.004] | **0.003 [0.001, 0.004]** |
| D · Full DecisionGPT | 0.084 [0.013, 0.156] | **0.084 [0.013, 0.156]** |

**Every aggregate is byte-identical.** PRE `675cf17e`, POST `0e1bd8dc`.

### Pairwise (paired Wilcoxon, 60 pairs) — PRE vs POST

| Comparison | PRE | POST |
|---|---|---|
| Full (D) vs Prediction only (A) | +0.084, W/T/L 10/50/0, p = 0.0045, r = 0.90 | **+0.084, 10/50/0, p = 0.0045, r = 0.90** |
| Full (D) vs Prediction + Digital Twin (B) | −0.401, W/T/L 0/15/45, **p < 0.0001**, r = 0.87 | **−0.401, 0/15/45, p < 0.0001, r = 0.87** |

### Override analysis — PRE vs POST

| | PRE (`c58c4537`) | POST (`f24abc1b`) |
|---|---:|---:|
| DT-best → Final override rate | 1.00 (60/60) | **1.00 (60/60)** |
| Override improved | 0 | **0** |
| Override degraded | 45 (0.75) | **45 (0.75)** |
| Override neutral | 15 (0.25) | **15 (0.25)** |

### Failure modes — the mechanism SHIFTED, the outcome did not

| Failure mode | PRE count (%) | POST count (%) |
|---|---:|---:|
| `CANDIDATE_SET_MISMATCH` | 30 (50 %) | **0 (0 %)** |
| `RISK_OVERRULE` | 15 (25 %) | **45 (75 %)** |
| `AGENT_OVERRULE` | 5 (8 %) | 5 (8 %) |
| `UNSUPPORTED_KPI` | 10 (17 %) | 10 (17 %) |
| `OPTIMIZER_RERANKING` / `TIE_BREAK` / `CAUSAL_PENALTY` / `CONFIDENCE_PENALTY` / `OTHER` | 0 | 0 |

**All 30 `CANDIDATE_SET_MISMATCH` pairs became `RISK_OVERRULE` pairs.** Once
`Price +5%` is a real candidate for the revenue/sales goals, the Risk Manager
scores it `RM = 0.0` (risk penalty `1 − 0 = 1.0`), so
`final_score = (BA+FA)/2 − 1.0` sinks it below a zero-benefit marketing move —
exactly as it already did on the profit scenarios.

### Risk Manager — PRE vs POST

| | PRE | POST |
|---|---:|---:|
| RM top-pick ≠ Digital-Twin best | 60/60 (100 %) | **60/60 (100 %)** |
| …of those, degraded the objective | 45 | **45** |
| …of those, improved | 0 | **0** |

### Agent layer / Optimizer

| | PRE | POST |
|---|---:|---:|
| Agent layer changed selection where DT-best WAS in the set | 20 (15 degraded / 0 improved) | **50 (35 degraded / 0 improved)** |
| Optimizer independent reranking | 0 | **0** |
| Round-2 peer-review self-adjustments | none on any pair | **none on any pair** |

### Ablation — PRE vs POST (n = 60 per config)

| Config | PRE mean goal ach. (Δ vs Full) | POST mean goal ach. (Δ vs Full) |
|---|---:|---:|
| A · Full | 0.084 (—) | **0.084 (—)** |
| B · Without Digital Twin | 0.000 (**+0.084**) | **0.000 (+0.084)** |
| C · Without Causal Graph | 0.084 (0.000) | **0.084 (0.000)** |
| D · Without Multi-Agent | 0.084 (0.000) | **0.084 (0.000)** |
| E · Without Explainability | 0.084 (0.000) | **0.084 (0.000)** |
| F · Without Memory | 0.084 (0.000) | **0.084 (0.000)** |

Same structure: only removing the Digital Twin moves the objective. PRE
`be392694`, POST `db58455b`.

## Research question

> *Does the Full DecisionGPT architecture provide additional objective value
> beyond the Digital Twin when both have access to the same legitimate
> strategy space?*

## Final scientific conclusion

**NO — the previous Full-vs-Digital-Twin gap was NOT caused by the
candidate-space mismatch; it persists after the strategy spaces are aligned.**

- The candidate-space mismatch was a **real experimental confound** and it is
  now **fixed**: `candidate_coverage_rate` 0.333 → **0.833**,
  `missing_supported_strategy_rate` 0.500 → **0.000**, the invariant holds.
- After the fix, Full DecisionGPT's mean goal achievement is **0.084 —
  byte-identical to before** (every aggregate, CI, Wilcoxon p and effect size
  matches). It still loses to Prediction + Digital Twin on **45 / 60** paired
  scenario/seed evaluations and never wins (`p < 0.0001`,
  effect size r = 0.87).
- **Reason:** giving the agents access to `Price +5%` did not change what they
  select. The **Risk Manager** assigns near-zero safety to price increases, so
  the optimizer's `(BA+FA)/2 − (1−RM)` score sinks every price move. The
  failure mechanism shifted from `CANDIDATE_SET_MISMATCH` (50 %) to
  `RISK_OVERRULE` (75 %); the objective outcome did not shift at all.
- The **Digital Twin** remains the only component with measurable objective
  value (ablation: removing it costs 0.084 goal achievement; removing the
  Causal Graph / Multi-Agent / Explainability / Memory costs 0.000).

**Outcome (per the task's framing): B — Full DecisionGPT remains worse.** The
next question, now cleanly isolated, is the **risk-penalty term**: it scores
price increases as maximally unsafe and that single term dominates strategy
selection. This is a diagnosis, not a licence to retune — no penalty was
modified.

**Follow-up (`docs/RISK_MANAGER_DIAGNOSTIC_REPORT.md`, `risk_manager_diagnostic`
`ba56e42b`).** A controlled sensitivity variant **D1** (Full DecisionGPT, Risk
Manager still running but its penalty un-weighted in the ranking — a labelled
variant, not the architecture) raises mean goal achievement **0.084 → 0.583**
(paired Wilcoxon p < 0.0001, r = 0.89). Removing only the penalty changes the
selection in 75 % of pairs (35 improved / 0 degraded / 10 neutral). So the
risk-penalty term **is** the proximate mechanism. Caveat: 0 `RISK_SCORE_MISMATCH`
cases — the Risk Manager is faithfully transmitting the Digital Twin's own
extrapolation-risk score (high for price moves because the synthetic businesses
hold price nearly constant), and D1's confidence collapses 0.139 → 0.018. The
next task is a principled calibration experiment, not a retune.

## Preserved

Legacy `decision_architecture` / `ablation`; pre-correction
`multi_scenario_architecture` (`675cf17e`), `multi_scenario_ablation`
(`be392694`), `multi_agent_diagnostic` (`c58c4537`) — metrics, IDs, seeds,
configs all intact (only `experiment_name` prefixed `PRE_CORRECTION`). All
dataset / model versions, production models, and the existing Paper Results
are unchanged. Verified: active model set unchanged; every pre-correction
experiment id still present.
