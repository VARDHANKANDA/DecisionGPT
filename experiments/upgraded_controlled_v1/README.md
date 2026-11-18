# Upgraded Controlled Evaluation — v1

**This tree is ADDITIVE and separate from the frozen study.** It never modifies
`experiments/experiment_manifest.json` or `experiments/paper_results_snapshot.json`
(the 16 frozen experiments), and it makes no real-world claims.

## Relationship to the frozen original study

| | FROZEN ORIGINAL STUDY | UPGRADED CONTROLLED EVALUATION (this tree) |
|---|---|---|
| Manifest | `experiments/experiment_manifest.json` (SHA-256 `94aa419c…`) — **never touched** | `experiments/upgraded_controlled_v1/config.json` + `scenario_manifest.json` |
| Scenarios | 12 hand-coded `multi_scenario_service.SCENARIOS` × 5 seeds | ≥ 50 parameterised instances across ≥ 15 families (`backend/app/evaluation/scenario_families.py`), scaling to 100+ |
| Primary metric | `goal_achievement` = the Digital Twin's own projection (self-graded) | **exogenous** normalised regret / performance ratio vs an independent ground-truth objective (`backend/app/evaluation/ground_truth.py`) — the internal metric is retained only as a labelled SECONDARY |
| Baselines | A (floor), B (greedy-on-twin), C, D | + naive, greedy, **oracle upper bound**, classical optimiser |
| Hold-out | none | family-level development / validation / **locked test** (`config.json → partitions`) |
| Statistics | Student-t CI + paired Wilcoxon + p-derived `r` | scenario-level paired Wilcoxon + **cluster bootstrap** + matched-pairs **rank-biserial** + **Holm** correction + simulation-based **power** (`backend/app/evaluation/stats.py`) |
| Architecture | R0/D0 production | **unchanged** — invoked read-only via the existing `PipelineOptions` defaults |

## Files (created by `scripts/run_upgraded_eval.py`; schema in `SCHEMA.md`)

| File | Produced by | Contents |
|---|---|---|
| `config.json` | `generate` / `split` / `power` | master seed, partitions, checksums, `prereg_frozen` gate |
| `scenario_manifest.json` | `generate` | every `EvalScenario` (params, history, constraints, objective, feasible actions, provenance, content hash) |
| `power_analysis.json` | `power` | simulation-based power at the pre-stated minimum effect of interest |
| `results.json` | `run` | per-instance A/B/C/D + baseline outcomes on the exogenous metric |
| `statistical_results.json` | `run` | scenario-level paired analyses + Holm-corrected family |
| `robustness_results.json` | `run` | degradation curves per perturbation × severity × condition |
| `checksums.txt` | every step | SHA-256 of each machine-readable artifact |

## Status

**COMPLETE (synthetic, controlled).** Pre-registration frozen 2026-09-05
(`config.json → prereg_frozen = true`); locked-test partition run **once**
(80 scenarios × 10 seeds = 800 instances, 0 errors); analysis, robustness, and
the reproducibility audit (14/14) done.

- **Suite:** `generator_version = upgraded_eval_scenarios_v2`, `master_seed =
  20260906`, `n = 340` (20/family), `suite_checksum
  2215a1bdde0294a08d5ea786f2c657f8b15b5e9ba6e37e82329df68a39629697`.
- **Locked families:** `asymmetric_risk`, `competing_objectives`,
  `missing_observations`, `promotion_decision` (`locked_test_family_checksum
  47f0afd643b72211b1a3423c99f186bc38f7776d8e68342ba00b67186da5ea95`).
- **Primary contrast `D_vs_B`: NULL** (Holm p = 1.0; 95 % cluster-bootstrap CI
  [−0.078, +0.143] includes 0; |mean Δ regret| = 0.034 < MEI 0.10).
- **`D_vs_A`: D significantly *worse*** than the minimal-intervention reference
  (Holm p = 0.0026; CI [+0.059, +0.161]; mean Δ +0.109).
- Full write-up: `docs/UPGRADED_EVALUATION_REPORT.md`; honest grading:
  `docs/UPGRADED_EVALUATION_READINESS.md`; integrity: `REPRODUCIBILITY_AUDIT.md`,
  `forbidden_claim_scan.json`.

The frozen 16-experiment manifest (`94aa419c…`), `paper_results_snapshot.json`,
`experiments/results/*`, R0/D0, R3's status, and `docs/PAPER_DRAFT.md` /
`docs/ieee_paper/` are **unchanged** (verified).

## Files

| File | Produced by | Contents |
|---|---|---|
| `config.json` | `generate`/`split`/`power`/`freeze-prereg`/`run`/`analyze` | master seed, partitions, checksums, `prereg` block, run + analysis ledger |
| `scenario_manifest.json` | `generate` + `split` | every `EvalScenario` (params, history_spec, reference_history, constraints, objective, feasible actions, provenance, content hash) + partition stamp |
| `power_assumptions.json` / `power_analysis.json` | (input) / `power` | pre-stated assumptions; simulation power = 0.860 |
| `dry_run_report.json` | `dry-run` | Phase-3 real-pipeline dry run (8/8 checks) |
| `results.json`, `results_locked_test.jsonl` | `run` | per-instance A/B/C/D + baselines on the exogenous metric; append log |
| `statistical_results.json` | `analyze` | scenario-level paired analyses + Holm family + positioning + per-family |
| `analysis_supplement.json` | `analyze` | agent diagnostics, associational mechanism, failure cases |
| `robustness_results.json`, `robustness_runs.jsonl` | `robustness` | degradation curves per perturbation × condition (locked-test subsample) |
| `REPRODUCIBILITY_AUDIT.md` | `audit` | 14 integrity checks + reproduction commands |
| `forbidden_claim_scan.json` | `scripts/scan_upgraded_claims.py` | over-claim / number-integrity scan (0 prohibited) |
| `checksums.txt` | every step | SHA-256 of every artifact |
