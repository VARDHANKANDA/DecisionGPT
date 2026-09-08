# Upgraded Controlled Evaluation — Implementation (Phases 2–3)

Companion to `docs/FROZEN_ARCHITECTURE_EVALUATION_AUDIT.md`. This document
describes the **evaluation-only layer** built in Phase 2 and the fixes made
during the Phase-3 real-pipeline dry run. The 16 frozen experiments, the frozen
manifest (`experiments/experiment_manifest.json`, SHA-256 `94aa419c…`), the
frozen snapshot, R0/D0, and R3's status are untouched (`git diff` on
`backend/app/services/`, `backend/app/analytics/`, `backend/app/agents/`, the
frozen manifest and the frozen snapshot is empty).

## Phase-3 dry run — what it exercised and what it changed (evaluation layer only)

`scripts/run_upgraded_eval.py dry-run` builds an **isolated scratch SQLite DB**,
syncs the file model registry, and runs development + `low_data` scenarios
through the **real frozen pipeline**. All eight checks pass: candidate
generation, identical-action-space invariant, A/B/C/D execution, Digital-Twin
execution, optimizer (condition D) execution, agent diagnostics, low-data
boundary exercised, `insufficient_data` exclusion fires. Condition D runs
`decision_service.analyze_goal` with **no `PipelineOptions`** (R0/D0), ~1.2–2.1 s
per instance. Three evaluation-layer fixes were required and made (no production
change):

1. **Genuine seed replicates.** `scenario_families` moved to
   `GENERATOR_VERSION = upgraded_eval_scenarios_v2`: a scenario stores a history
   *specification*; `realise_history(scenario, seed)` produces the concrete
   history the system ingests, so the pre-registration's ≥ 10 seeds are
   independent replicates, not deterministic re-runs.
2. **Profit-objective action space.** The seeded business always has positive
   marketing ROI, so production emits an extra "marketing +10%" candidate for
   `increase_profit` goals. The generator now declares it, so the
   identical-action-space invariant holds for every profit family.
3. **`insufficient_data` classification.** When the Digital Twin cannot evaluate
   any feasible action (e.g. `low_data` history below
   `forecast_service.MIN_HISTORY_DAYS = 35`), conditions B/C are marked
   `insufficient_data` and the instance is dropped from the **primary** paired
   analysis by the pre-registered exclusion rule — reported, never silently
   discarded.

## What was built

| Path | Role | Depends on production? |
|---|---|---|
| `backend/app/evaluation/__init__.py` | package marker + hard-rule statement | no |
| `backend/app/evaluation/scenario_families.py` | 17 parameterised scenario families; `generate_suite(n, master_seed)` (≥ 50, scales to 100 000); deterministic **family-level** dev/val/locked-test partition | **no** (stdlib + numpy) |
| `backend/app/evaluation/ground_truth.py` | **exogenous** closed-form objective + oracle + naive/greedy/classical-optimizer baselines; normalised regret / performance ratio | **no** — independence proven by `tests/unit/test_eval_ground_truth.py` (static import scan + runs with the Digital Twin / pipeline poisoned) |
| `backend/app/evaluation/stats.py` | scenario-level paired Wilcoxon, **cluster bootstrap**, **matched-pairs rank-biserial** (estimator, not p-derived), **Holm** correction, **simulation-based power** | no (stdlib + numpy + scipy) |
| `backend/app/evaluation/perturbations.py` | 10 evaluation-only input transformations + degradation curves | no |
| `backend/app/evaluation/mechanism.py` | scenario-property factor extraction + B−A / C−B / D−B interaction analysis (OLS on standardised factors + tertile buckets); explicitly non-causal | no (+ uses `ground_truth`) |
| `backend/app/evaluation/harness.py` | per-instance runner: seeds an ephemeral synthetic business, verifies the identical-feasible-action-space invariant, runs A/B/C over that set with frozen primitives, runs D via `decision_service.analyze_goal` **with default `PipelineOptions` (R0/D0)**, scores every condition with `ground_truth`, records the DecisionGPT-internal metric as a labelled SECONDARY, collects agent diagnostics | **read-only**, lazy imports; production unmodified |
| `scripts/run_upgraded_eval.py` | CLI: `generate` / `split` / `power` / `run` / `verify-freeze`; uses a **separate scratch DB**; `run --partition locked_test` is **blocked** until `config.prereg_frozen == true`; every `run` currently halts (Phase-2 stop) | read-only |
| `experiments/upgraded_controlled_v1/` | versioned outputs, **schema-only stubs** now (`SCHEMA.md`, `config.json` `status="phase2_scaffold"`) | n/a |
| `tests/unit/test_eval_*.py` | 55 unit tests for the new modules | n/a |

## How the Phase-1 weaknesses are addressed

| Frozen-study weakness | This layer |
|---|---|
| **Circular / self-graded metric** (`goal_achievement` is the Digital Twin's own projection) | `ground_truth.evaluate` is a closed-form economic model with a **different functional form** from the Twin's recursive extrapolation. It imports none of `digital_twin_service` / `decision_service` / `decision_architecture_service` / `forecast_service` / `app.agents` (statically + functionally asserted). PRIMARY = normalised regret / performance ratio vs the ground-truth oracle. The Twin's `goal_achievement` is recorded only as `secondary_goal_achievement`, always labelled. |
| **Generator ↔ risk-mechanism confound** (2-valued price history saturates the R0 term) | `scenario_families._history` produces **non-constant** price paths for the `price_uncertainty`, `promotion_decision`, `resource_allocation`, `competing_objectives`, `high_volatility` families (random walk within a band). The `adversarial_risk_trap` family keeps price constant **on purpose**, as a labelled diagnostic. |
| **12 hand-coded scenarios, no hold-out** | 17 parameterised families, ≥ 50 instances (scales to 100+), deterministic from `(master_seed, family, index)`. `partition_families` splits **by family** into 60/20/20 development/validation/**locked_test**; no family crosses a partition (tested). The locked test is checksum-sealed by `scripts/run_upgraded_eval.py split`. |
| **No external baselines / oracle** | `ground_truth.{oracle, naive_baseline, greedy_baseline, classical_optimizer}` — none call DecisionGPT; oracle is labelled an upper-bound reference. |
| **B/C vs D candidate-set asymmetry** | `harness.verify_identical_action_space` re-derives the production candidate set per instance and asserts it equals `scenario.feasible_actions`; A/B/C select strictly over that set; D's realised pick is checked to be in it. A violation sets `exclude_from_primary = True` with a pre-registered reason — never silent. |
| **Effective n ≈ 12; multiplicity uncontrolled** | `stats` treats the **scenario** as the unit (`scenario_level_aggregate` → `paired_scenario_analysis`), reports a paired **cluster bootstrap** and **rank-biserial**, and applies **Holm** across the pre-registered contrast family. `simulate_power` runs before the locked test with pre-stated assumptions. |
| **No robustness suite** | `perturbations` (input noise, forecast-error bias, missing values, uncertainty inflation, constraint tighten/relax, distribution shift, contradictory signals, extreme-but-feasible, adversarial) → `degradation_curve`. |
| **Post-hoc correlational mechanism** | `mechanism.interaction_analysis` regresses the per-scenario B−A / C−B / D−B contrasts on standardised factors (uncertainty, constraint tightness, objective conflict, prediction error, risk exposure, action-space size, agent disagreement), with bootstrap CIs + tertile buckets; note field states it is associational within the designed suite, not causal. |
| **Agent ablation uninformative** | `harness._agent_diagnostics` records agent score variance / range / inter-agent agreement / whether the agent layer changed the selection vs C and vs greedy — and reports honestly if agent scores are near-constant. Families with varied inputs (`price_uncertainty`, `conflicting_signals`, `asymmetric_risk`) give the agents something to differentiate. |

## Independence guarantee for the primary metric

`ground_truth.py` header lists `FORBIDDEN_DEPENDENCIES`. Two tests enforce it:
`test_source_has_no_forbidden_imports` (AST scan of the module's imports) and
`test_runs_with_digital_twin_and_pipeline_unavailable` (poisons
`sys.modules['app.analytics.digital_twin_service']` etc. and still runs
`evaluate` / `oracle` / `naive` / `greedy` / `classical_optimizer`).

## Running (after explicit Phase-3 approval only)

```bash
# 1. platform forecasting models must be registered for the Digital Twin to run
python -m ml.training.train_forecasting        # if models/registry_index.jsonl is absent
# 2. generate the suite + resolve/verify feasible actions
python scripts/run_upgraded_eval.py generate --n 51 --master-seed 20260906
# 3. seal the family-level split
python scripts/run_upgraded_eval.py split --master-seed 20260906
# 4. power analysis from an explicit assumptions file (BEFORE any locked-test run)
python scripts/run_upgraded_eval.py power --assumptions <assumptions.json>
# 5. finalise docs/UPGRADED_EVALUATION_PREREGISTRATION.md, set config.prereg_frozen = true
# 6. run development / validation, then the locked test  (guard must be removed in run())
python scripts/run_upgraded_eval.py run --partition development
python scripts/run_upgraded_eval.py verify-freeze     # frozen manifest + production still intact
```

Every `run` in the current code halts with a Phase-2 stop message; the guard is
removed only after approval to execute Phase 3+.

## What was NOT changed

`git diff -- experiments/experiment_manifest.json experiments/paper_results_snapshot.json
backend/app/services/ backend/app/analytics/ backend/app/agents/` is **empty**.
`multi_scenario_service.SCENARIOS` (12) and `SEEDS` (`[42..46]`) are unchanged.
No `ExperimentRun` row is written by this layer (standalone scripts + scratch DB).
