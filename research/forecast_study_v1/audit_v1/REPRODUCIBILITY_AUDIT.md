# REPRODUCIBILITY_AUDIT

Independent check of the study's reproducibility claims, 2026-10-22. Only inexpensive, non-destructive checks were run. **Nothing that writes into `results/` was executed** (the study's `analyze.py`, `verify_cell.py`, `aggregate.py` write there), and **no experiment was re-run** (no approval given). All "regenerate" checks used a temporary copy.

## 1. Commands and artifacts checked

| item | what was done | result |
|---|---|---|
| `REPRODUCIBILITY.md` one-command path (`PYTHONPATH=. bash research/forecast_study_v1/run_all.sh`) | read the script; not executed (about 4 hours of CPU, not approved) | **not performed**; static findings below |
| Expected outputs exist (`results/fs1_*`, `s2_*`, `E1_*`, `ABLATIONS_*`, `S2_customer_disjoint.json`, `TABLES.md`, `CONFIRMATORY_SUMMARY.*`, figures) | listed and hashed | all present (31 MB; 57 `fits/*.npy` per full cell) |
| Per-fit arrays vs stored predictions | `fits/test_*_{family}-{variant}.npy` concatenated vs `predictions.npz` for all five families in all six cells | **identical (exact equality)** |
| Tables and figures from stored analysis outputs | `make_report.py` copied with the stored JSON files into a temporary directory and run there | `TABLES.md` **byte-identical**; the four SVG figures identical after removing generator ids/dates |
| Independent recomputation of the results from stored predictions | `audit_v1/step2_metrics.py`, `step3`, `step4`, `step5`, `step6`, `step8` (no study imports) | 458 of 460 comparisons PASS; 2 segment-interval endpoints exceed a preset 0.5 pp tolerance by 0.05 and 0.01 pp (bootstrap noise; no conclusion affected) |
| Evaluation targets and all 16 baselines from raw data | `step1_targets_baselines.py` | all 6 cells: targets equal raw data; every baseline row equal |
| Frozen historical artifacts | `python research/r4/audit/verify_historical_freeze.py` | "OK - all 22 historical artifacts unchanged since freeze at 2026-09-23T22:45:00Z" |
| `experiments/ml_benchmark_v1/HISTORICAL_HASHES.json` | SHA-256 of each listed file | 20 of 20 match |
| `experiments/experiment_manifest.json` | SHA-256 | 94aa419c703b1babb465975463b26e55255755a7687ecbecadb6db4c4c15cbff (matches the repository's frozen constant) |
| `FREEZE.json` | recomputed hashes of the 14 listed files and the plan text above the deviations log | all unchanged except `EXPERIMENT_PLAN.md`, whose text above its deviations log matches |
| Study unit tests | `pytest tests/unit/test_forecast_study.py` | **23 passed** (re-run during the audit) |
| Full backend suite (stated: 1,760 passed, 34 skipped, exit 0) | **not re-run** | historical report value, unverified on the current tree |
| Behaviour with a missing input | `analyze.load('fs1_does_not_exist')` | exits with `FileNotFoundError: ... results\fs1_does_not_exist\predictions.npz` (clear) |
| Network / credentials in study code | grepped `research/forecast_study_v1/*.py` | no network, API or credential use; one environment variable `STUDY_THREADS` |

## 2. Historical reproduction (stored vs re-run, author-recorded in `audit/rerun_comparison.json`, re-read in this audit)

| run | numbers compared | max abs. difference | note |
|---|---|---|---|
| c1 (Online Retail II inactivity classification) | 708 | 1.5e-5 | **2 numbers differ** (random-forest isotonic test ROC-AUC 0.7974521 vs 0.7974527 and PR-AUC 0.8064607 vs 0.8064758): small non-determinism |
| c2 (synthetic-label churn) | 702 | 1.1e-16 | identical |
| f2 (Online Retail II forecasting) | 599 | 1.7e-16 | identical |
| f1 (M5 forecasting) | 266 | 1.4e-14 | all shared numbers identical; 21 key-name differences only (older run named a baseline `seasonal_naive_28`; its values equal the re-run's `seasonal_naive` exactly) |

Also from the author's `audit/recompute_report.json`: f1 and f2 stored metrics recomputed from stored predictions match (max difference 5e-10). These are historical-benchmark results; they are not evidence about the new study's models.

## 3. Could an independent researcher reproduce the reported tables and figures?

* **Tables and figures from the archived analysis files: yes** (byte-identical regeneration).
* **Analysis files from the stored predictions: yes** in principle (`analyze.py`; independently re-derived here to rounding).
* **Predictions from raw data: only with the raw data and about 4 hours of CPU.** The M5 files require a Kaggle account and acceptance of the competition rules (the data page asks to sign in). The processed Online Retail II CSV used by the code is a conversion of the UCI workbook made earlier in this project; the conversion script is not part of the study directory. Model fits were **not** re-executed by the audit, so the generation of the model predictions is "not independently re-verified" beyond internal consistency (fits equal stored arrays).
* **Rights conflict:** the stored predictions contain actual M5 sales values; publishing them would conflict with the Kaggle rules (see `REFERENCE_AND_DATA_RIGHTS_AUDIT.csv`). A public reproduction package therefore cannot include `predictions.npz` for M5 as it stands.

## 4. Environment, dependencies and randomness

* `environment_freeze.txt` records 12 package versions (Python 3.12.0; numpy 2.5.2; pandas 3.0.5; scipy 1.18.0; scikit-learn 1.9.0; xgboost 3.4.0; lightgbm 4.7.0; catboost 1.2.10; matplotlib 3.11.2; joblib 1.5.3; openpyxl 3.1.5; pyarrow 23.0.1; pytest 9.1.1) and `metadata.json` records versions, thread count and the SHA-256 of every study source file.
* **No research-specific requirements file.** Declarations are split: `backend/requirements*.txt` declare xgboost, scikit-learn, scipy, numpy, pandas, openpyxl (not lightgbm, catboost, matplotlib); `ml/benchmark/requirements.txt` declares lightgbm, catboost, scikit-learn, numpy, pandas, openpyxl (not xgboost, scipy, matplotlib). The study needs all of them; a fresh environment built from either file alone would fail. **A clean reproduction in a fresh virtual environment was not performed.**
* Randomness: one model seed (42); M5 series draw seed 20261015; bootstrap seeds fixed in code; thread count (4) recorded. Gradient-boosting libraries can differ in the last digits across thread counts, library versions and platforms; the c1 re-run shows a 1.5e-5 effect for a random forest.
* **Machine specifics:** `run_all.sh` hard-codes the Windows virtual-environment path `backend/.venv/Scripts/python.exe`; the instructions set `PYTHONPATH=.` (Windows tests elsewhere used `;`); documentation states Windows 11, 4 cores, 7.7 GB. These are documented but not portable.
* `FREEZE.json` can be checked only with ad-hoc code: the study has `make_freeze.py` (which would overwrite the record) but **no documented command that verifies** the freeze. Add a verify script.

## 4a. Scientific validity is not established by software tests

The 23 study tests (leak-free baselines, metric edge cases, bootstrap and conformal behaviour on synthetic inputs) and the 1,760-test backend suite show that code behaves as written. They do not show that the design answers the research question, that the baselines are fair, that the inference's assumptions hold for these data, or that the conclusions generalise. The manuscript (Section 18) lists the unit tests as a verification step without this caveat; add it.

## 5. Not performed (and why)

| not performed | reason |
|---|---|
| Re-run of any fit or experiment | no approval; expensive |
| Clean-virtualenv installation and run | expensive; no approval |
| Full backend test suite | not needed to resolve a specific concern |
| Re-execution of the customer-split sensitivity | requires refitting four models |
| Independent check of the feature builder's leakage controls | historical code; only the study's own perturbation checks (all passed) and an independent baseline check were available |
