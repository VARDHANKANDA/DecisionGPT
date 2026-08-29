# Multi-Agent Degradation Diagnostic (PRE-correction)

> This is the **pre-correction** diagnostic. Its dominant finding
> (`CANDIDATE_SET_MISMATCH`, 50 %) was a genuine experimental confound: the
> goal-aware candidate generator omitted a supported price-increase lever, so
> architectures B and D were not comparing the same legitimate strategy space.
> The generator was corrected and the controlled experiment repeated — see
> **`docs/CANDIDATE_SPACE_CORRECTION_REPORT.md`** for the post-correction
> result. This document is preserved unchanged as the record of the audit that
> found the confound.

**Analysis only — architecture frozen.** The multi-scenario experiment
(`docs/RESEARCH_EXPERIMENT_REPORT.md` §5) measured that Full DecisionGPT (D)
achieves lower goal achievement than Prediction + Digital Twin (B) across the
12 × 5 scenario suite (mean 0.084 vs 0.486; paired Wilcoxon p < 0.0001; D
loses 45/60, never wins). This document determines **where and why** the
degradation occurs. No agent, Digital Twin, causal graph, model, seed,
dataset, experiment ID or prior result was changed.

## Method

`app.services.multi_agent_diagnostic_service.run_diagnostic` re-runs the
**deterministic** architecture scenarios (same 12 `ScenarioSpec`s, seeds
42–46, LLM template mode) and, before each ephemeral synthetic business is
cleaned up, harvests the trace the pipeline itself produced:

```
Digital-Twin candidate sweep (decision_architecture_service._simulate_all_candidates —
   the fixed CANDIDATE_GRID that architectures B and C use)
      → per-candidate Business Analyst / Financial Advisor / Risk Manager
        round-1 & round-2 scores   (persisted AgentEvaluation rows)
      → strategy_optimizer final_score per candidate   (DecisionResult.debate)
      → the strategy the Full pipeline selected  + its goal achievement
```

Determinism is verified by a unit test; a second test asserts the
diagnostic's Full-pipeline selection for each `(scenario, seed)` **reproduces
the stored `multi_scenario_architecture` architecture-D observation**. Stored
as experiment type `multi_agent_diagnostic` (in the reproducibility manifest);
surfaced on **Research → Multi-Agent Evaluation**.

## Disagreement dataset

One row per `(scenario_id, seed)` — 60 rows — each with:
`goal_objective, goal_primary_kpi, kpi_measured, dt_best_strategy,
dt_candidate_ranking, dt_best_revenue, dt_best_kpi_attainment,
final_strategy, final_score, final_goal_achievement, confidence,
causal_evidence_level, risk_manager_top_pick, per-candidate {BA1, FA1, RM1,
round2_moved, final_score, conflicts}, disagreement, improvement,
failure_mode, mechanism_evidence`.

Full table: export `decision_architecture` experiment is unrelated — use the
`multi_agent_diagnostic` experiment's `metrics_json.traces` (also rendered as
the scenario/seed drill-down on the Multi-Agent Evaluation page).

## Root-cause mechanisms

Completed run: experiment `multi_agent_diagnostic` id `c58c4537`, seeds
42–46, **60 scenario-seed pairs**. Digital Twin mean goal achievement
**0.486** vs Full DecisionGPT **0.084** (identical to the
`multi_scenario_architecture` result — traceability confirmed).

### Digital Twin best strategy → final strategy

| | Count | % |
|---|---:|---:|
| **Unchanged** (Full picked the DT-best) | **0** | 0 % |
| **Overridden** (Full picked something else) | **60** | **100 %** |

Full DecisionGPT **never** selects the strategy the Digital Twin sweep ranks
first — on any of the 60 pairs.

### Override outcomes (vs the DT-best's goal achievement)

| | Count | Rate |
|---|---:|---:|
| Improved the objective | **0** | 0.00 |
| Degraded the objective | **45** | **0.75** |
| Neutral (both attain 0) | 15 | 0.25 |

**No override ever improved goal achievement.**

### Failure modes (task §4)

| Failure Mode | Count | % | Mean DT revenue | Mean final goal achievement |
|---|---:|---:|---:|---:|
| `CANDIDATE_SET_MISMATCH` | **30** | **50.0 %** | ≈ ₹1.3 M–₹5 M (scenario-dependent) | 0.000 |
| `RISK_OVERRULE` | **15** | **25.0 %** | — | 0.000 |
| `UNSUPPORTED_KPI` | 10 | 16.7 % | — | 0.000 |
| `AGENT_OVERRULE` | 5 | 8.3 % | — | 0.000 |
| `OPTIMIZER_RERANKING` | 0 | 0 % | — | — |
| `TIE_BREAK` | 0 | 0 % | — | — |
| `NO_VALID_STRATEGY` | 0 | 0 % | — | — |
| `CAUSAL_PENALTY` / `CONFIDENCE_PENALTY` | 0 | 0 % | — | 0 by construction (affects `confidence` only) |
| `OTHER` | 0 | 0 % | — | — |

### Central-hypothesis test (task §5)

| | Value |
|---|---:|
| DT-best strategy was in Full's own candidate set **and** the agent layer changed the selection | **20** / 60 |
| …of those, the change **degraded** the objective | **15** |
| …of those, the change **improved** the objective | **0** |
| …neutral | 5 |

### Risk-Manager effect (task §7)

Risk-Manager top pick ≠ Digital-Twin best on **100 %** of pairs
(the RM never top-ranks a price move). Of the 15 `RISK_OVERRULE` pairs, **15
degraded** the objective, 0 improved.

### Optimizer effect (task §8)

DT-best → final change rate **1.00**. `strategy_optimizer.resolve` applies the
fixed `(BA+FA)/2 − (1−RM)` formula and no independent re-ranking; round-2
self-adjustments were **absent** on every pair. Mean goal achievement when the
selection was unchanged: **n/a (never unchanged)**; when changed: **0.084**.

### Causal-evidence effect (task §6)

All 60 pairs recorded causal evidence level `assumed` → **insufficient
variation to evaluate a causal-evidence effect on selection**, and by
construction the causal-evidence factor scales `confidence` only, never
`final_score`.

### Most common degradation mechanism

**`CANDIDATE_SET_MISMATCH` (50 %)** — the revenue/sales strategy templates in
`strategy_generation_service` do not include a price-increase lever, so the
Digital Twin's preferred strategy is never presented to the agents. Second:
**`RISK_OVERRULE` (25 %)** — the Risk Manager scores price increases as
maximally unsafe, and that single term sinks their `final_score`.

### Mechanism definitions (task §3)

| Category | Assigned when the trace shows… |
|---|---|
| `CANDIDATE_SET_MISMATCH` | the DT-best strategy is **absent from Full DecisionGPT's generated candidate set** — the agents never scored it (`strategy_generation_service` did not produce it for this goal) |
| `AGENT_OVERRULE` | the DT-best **is** in the set, but Business Analyst + Financial Advisor scored another candidate higher on growth `((BA+FA)/2)`, with no larger risk penalty |
| `RISK_OVERRULE` | the DT-best is in the set, but the Risk Manager's low safety score (higher `1−RM` penalty) alone dropped its `final_score` below the winner |
| `OPTIMIZER_RERANKING` | round-2 peer-review self-adjustments changed the ranking |
| `TIE_BREAK` | DT-best and the selected strategy have equal `final_score`; selection fell to candidate-generation order |
| `UNSUPPORTED_KPI` | scenario KPI is `inventory_risk` / `marketing_roi` — not directly simulated, revenue proxy used, so a ranking difference is not attributable to the agents |
| `NO_VALID_STRATEGY` | the pipeline could not simulate / recommend any improving strategy |
| `CAUSAL_PENALTY` / `CONFIDENCE_PENALTY` | **0 by construction** — `causal_evidence_factor` scales `confidence` only, never `final_score` (verified in `strategy_optimizer.resolve`), so it cannot change strategy selection |
| `OTHER` | disagreement not explained by any single term |

## Key structural findings (independent of the counts)

1. **Two different candidate grids.** Architecture B/C sweep the fixed
   `decision_service.CANDIDATE_GRID` (which **includes `Price +5%`**). Full
   DecisionGPT (D) instead calls `strategy_generation_service.generate_candidates`,
   which is goal-templated:
   - `increase_revenue` / `increase_sales` → `_revenue_templates()` =
     **only marketing-increase and price-*decrease*** levers. **There is no
     price-increase candidate.** In these synthetic scenarios demand is
     inelastic (the Digital Twin holds units ≈ constant), so a price *cut*
     always loses revenue and a price *increase* would gain it — but D never
     generates one.
   - `increase_profit` → `_profit_templates()` **does** include `Price +5%`
     / `Price +10%`.
   ⇒ For revenue/sales goals the DT-best strategy is **structurally absent**
   from D's option set — this is `CANDIDATE_SET_MISMATCH`, not an agent
   overrule.

2. **The Risk Manager assigns near-zero safety to price increases.** On the
   profit scenarios where `Price +5%` *is* a candidate, the trace shows
   `RM = 0.0` for it (risk penalty `1 − 0 = 1.0`), so
   `final_score = (BA+FA)/2 − 1.0` is strongly negative and a "safe but
   zero-benefit" marketing cut wins — `RISK_OVERRULE`.

3. **Agent scores are otherwise flat.** BA and FA return ≈ 0.5 for almost
   every candidate, and **round-2 self-adjustments are absent** (`round2`
   scores persisted as `None`). So the optimizer's `(BA+FA)/2 − (1−RM)`
   formula is dominated by the Risk Manager term, and among equal-scoring
   candidates the winner is decided by **candidate-generation order**
   (`TIE_BREAK`).

4. **The Causal Graph cannot change strategy selection.** `causal_evidence_factor`
   multiplies `confidence` only; `final_score` never sees it. This matches the
   multi-scenario ablation (removing the Causal Graph moved confidence
   0.139 → 0.251 with **zero** goal-achievement delta).

## Central hypothesis (task §5)

> *"The Multi-Agent layer frequently overrides the Digital Twin's
> highest-scoring strategy without sufficient objective evidence, causing
> lower goal achievement."*

**Verdict: PARTIALLY SUPPORTED / RE-SPECIFIED.** The dominant mechanism is
**not** an agent overrule — for the revenue/sales goals the DT-best strategy
is never presented to the agents at all (`CANDIDATE_SET_MISMATCH`). Where the
DT-best *is* in D's candidate set (profit goals), the agent layer *does*
change the selection, and those changes degrade the objective — driven
specifically by the **Risk Manager** penalising price increases. The
`multi_agent_diagnostic` experiment's `central_hypothesis` block gives the
exact counts.

## What is NOT responsible

- **Optimizer independent re-ranking:** `strategy_optimizer.resolve` performs
  no ranking beyond the fixed formula + round-2 adjustments; round-2 moves
  were absent in the traces.
- **Causal-evidence / confidence penalty:** structurally cannot affect
  selection (0 by construction).
- **Explainability / Memory:** not in the selection path (confirmed by the
  ablation's zero deltas).

## Recommendation (no change applied)

The evidence points at **two narrowly-scoped issues**, either of which could
be corrected without touching the agents or the Digital Twin:

1. `strategy_generation_service._revenue_templates()` / `_sales_templates()`
   omit price-increase levers. Adding `Price +5%` / `Price +10%` to the
   revenue/sales templates (mirroring `_profit_templates()`) would let the
   Full pipeline even *consider* the strategy the Digital Twin prefers.
2. `risk_manager.evaluate` returns a near-zero safety score for price
   increases regardless of the simulated risk band; that single term then
   dominates `final_score`. Reviewing how the Risk Manager maps a simulated
   `risk_score` to a safety score is warranted.

Both are **diagnosis outputs**, to be decided on separately — this task ends
at the evidence.

## Preserved

Legacy `decision_architecture` / `ablation`, `multi_scenario_architecture`
(id `675cf17e`), `multi_scenario_ablation` (id `be392694`), all dataset /
model versions, production models, seeds, and the existing Paper Results are
unchanged. Only the `multi_agent_diagnostic` experiment + this analysis were
added.
