# REPRODUCIBILITY — forecast_study_v1

Everything here was produced on **one machine** (Windows 11, 4 physical cores / 8 logical, 7.7 GB RAM, CPU only) with the packages in `environment_freeze.txt`
(Python 3.12.0, numpy 2.5.2, pandas 3.0.5, scipy 1.18.0, scikit-learn 1.9.0, xgboost 3.4.0, lightgbm 4.7.0, catboost 1.2.10, matplotlib 3.11.2).
No GPU, no network access and no AI-provider call is used by any step. Nothing under `experiments/` or `data/` is written.

## 1. One-command reproduction

From the repository root (the M5 and Online Retail II raw files must be present where `ml/benchmark/datasets.py` expects them; their SHA-256 values are recorded in
`results/*/metadata.json` and `inventory/experiment_inventory.json`):

```bash
PYTHONPATH=. bash research/forecast_study_v1/run_all.sh
```

This runs the six forecasting cells (3 datasets × H ∈ {7, 28}), the four ablations, and the inactivity study. Then:

```bash
PYTHONPATH=. python -m research.forecast_study_v1.analyze fs1_m5_ca1_H28   # repeat for each cell -> analysis.json
PYTHONPATH=. python -m research.forecast_study_v1.verify_cell fs1_m5_ca1_H28   # independent recomputation; exit code 1 on any failed check
PYTHONPATH=. python -m research.forecast_study_v1.aggregate                   # Holm across the six cells -> results/CONFIRMATORY_SUMMARY.{json,md}
PYTHONPATH=. python -m research.forecast_study_v1.ablation_report fs1_m5_ca1_H28
PYTHONPATH=. python -m research.forecast_study_v1.make_report                 # tables + figures from stored JSON only
```

Wall-clock on the machine above: `m5_ca1`/`m5_tx1` cells ≈ 15–30 min each (partly overlapping with another job), `or2_top100` ≈ 4–6 min, each ablation ≈ 1 min, the
inactivity study a few minutes. Runs resume from `fits/*.npy` only when the configuration hash is identical; otherwise they refuse to start.

## 2. Determinism and provenance

* One global seed (42) for every model; data subsets are drawn by the historical deterministic rule (seed 20261015, recorded in `metadata.json`).
* Bootstrap seeds are fixed in `inference.py` (20261022–24) and in the classification script (42 + offsets).
* Every run writes `config.json` (with a config hash), `metadata.json` (git revision, SHA-256 of every study source file, package versions, thread count, dataset file hashes), `selection.json` (validation-only choices), `predictions.npz` (every method's test and validation predictions) and `results.json`.
* The git revision recorded is the base commit `41c1d14`; the working tree has many uncommitted files from unrelated work, so **the SHA-256 of each study source file in `metadata.json` and `FREEZE.json` is the authoritative code identity**, not the commit.
* `FREEZE.json` fixes the hash of the plan and the code before the first confirmatory run. The plan text above its deviations log is covered by `plan_sha256_text_above_deviations_log`. Deviations (including the post-hoc experiment E1) are listed in the plan.
* Gradient-boosting libraries can differ in the last digits across thread counts, library versions and platforms. Re-running on this machine with `STUDY_THREADS=4` is expected to reproduce all figures to many decimals; other environments are expected to reproduce the qualitative conclusions, not necessarily every digit.

## 3. Reproduction of the historical results (done before any new experiment)

The frozen runs in `experiments/ml_benchmark_v1/` were not touched. Their numbers were checked in two independent ways.

**(a) Recomputation from stored predictions** (`audit/recompute_from_predictions.py`, own implementations of WAPE, bias, RMSSE scale, aggregate WAPE; `audit/recompute_report.json`):
f1 (M5) all stored metrics match, max difference 5.2e-10; f2 (Online Retail II) all match, max difference 0.

**(b) Re-running the historical code into a new directory** (`audit/rerun_historical.py`; comparison in `audit/rerun_comparison.json`, run directories in `audit/reruns/`):

| Run | Numbers compared | Max abs. difference | Verdict |
|---|---|---|---|
| c1 (Online Retail II inactivity classification) | 708 | 1.5e-5 (2 numbers: random-forest isotonic test ROC-AUC and PR-AUC) | reproduces; tiny non-determinism in the random forest |
| c2 (synthetic-label churn) | 702 | 1.1e-16 | identical |
| f2 (Online Retail II forecasting) | 599 | 1.7e-16 | identical |
| f1 (M5 forecasting) | 266 | 1.4e-14 | all shared numbers identical; 21 key-name differences only (the stored run used the older name `seasonal_naive_28`, whose values equal the rerun's `seasonal_naive` exactly; one text label was reworded) |

## 4. Independent verification of the new results

`verify_cell.py` does **not** import `metrics.py` or `inference.py`. For each cell it checks 19–24 conditions, including: arrays complete/finite/aligned; every test row inside its declared block and not repeated; validation blocks end before the first test block; pooled WAPE, bias, aggregate WAPE and by-block WAPE of the primary model and both references recomputed from `predictions.npz` and compared with `results.json`; the headline relative improvement recomputed and compared with `analysis.json`; the bootstrap interval contains the point estimate; **`selection.json` is older than every test-block fit file**; the primary family is the argmin of validation WAPE; the reference baselines are the argmin of validation WAPE.
Result: all six forecasting cells 24/24 and the four ablation runs 19/19 (`results/*/verification.json`).

Unit tests (`tests/unit/test_forecast_study.py`, 23 tests): baselines do not change when everything after their cutoff is rewritten; fresh-baseline cutoffs; hand-computed Croston-SBA and TSB; metric edge cases and undefined policies; crossed bootstrap (identical forecasts → 0, perfect forecast → 1, interval wider than series-only under a shared week shock, ≈ nominal coverage under a null, detects a real gain); Holm textbook example; Diebold–Mariano; conformal order statistic and coverage; window ordering for M5; segments use only pre-validation history.

## 5. Known limits of reproducibility

* Raw datasets are not redistributed with this directory; licences and hashes are recorded in `inventory/experiment_inventory.json`.
* The M5 subset is a 350-series draw per store by a deterministic rule, not the full 30,490 series.
* Results are one machine, one seed per model; seed variance of the learned models was not studied.
* The study does not re-run the competition-grade M5 metric (WRMSSE).

## 6. Final test and integrity record (2026-10-22, after all study work)

* Complete backend suite, run once on the final tree with no other pytest running: `PYTHONPATH="backend;." pytest tests -q` -> **exit code 0, 1760 passed, 34 skipped, 0 failed (27 min 08 s)**. The skips are the suite's pre-existing conditional skips (e.g. PostgreSQL/Docker-dependent tests), not failures. This includes the 23 new study tests.
* Frozen historical benchmark: `research/r4/audit/verify_historical_freeze.py` -> OK, all 22 historical artifacts unchanged; all 20 files of `experiments/ml_benchmark_v1/HISTORICAL_HASHES.json` match; `HISTORICAL_HASHES.json` itself has the sha256 recorded in `FREEZE.json`; `experiments/experiment_manifest.json` sha256 `94aa419c...cbff` unchanged.
* Study code vs freeze: every source file hashed in `FREEZE.json` is unchanged; the plan text above its deviations log is unchanged. Added after the freeze (all disclosed in the plan's deviations log): `make_report.py` (reporting only), `exploratory_l1.py` (post-hoc E1), `s2_customer_disjoint.py` (replacement sensitivity), `run_all.sh`.
* The frontend was not touched by this work and its tests were not re-run.
* Nothing was committed; all study files are new and untracked.
