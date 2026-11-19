# INITIAL_AUDIT — baseline state, file protection and initial findings (R3 quality gate, 2026-10-22)

Auditor: the same AI assistant that produced the study, the verification code, the supplementary analysis and manuscript R2. **This is an internal adversarial audit, not an external one.**

## 1. Baseline state (before any change in this gate)

| item | state |
|---|---|
| repository | `D:\DecisionGPT`, branch `main`, HEAD `41c1d14` (2026-09-08); 403 changed/untracked entries in the working tree before this gate; `research/` entirely untracked; **no commit was made by this gate or any earlier v2 step** |
| v2 freeze | `FREEZE.json` (24 files, 2026-10-22T08:15:19Z): `freeze verify` → 24 files unchanged (re-checked at the start of this gate) |
| protected artifacts | v1 study, `experiments/`, `ml/benchmark/*.py`, raw M5/UCI files: 761 files hashed (`protection/protected_start.json`, `protected_final_r2.json`, `protected_qg_start.json`): **0 differences** between the original start and the start of this gate; `experiments/experiment_manifest.json` sha256 `94aa419c703b1bab…` |
| artifact inventory | `quality_gate/inventory_qg_start.json`: 1,196 files (23 frozen files inside the study directory + 1 frozen test file outside; 988 restricted arrays under `results/**` — `predictions.npz` and `fits/*.npy` contain or reproduce M5 sales and are never to be released) |
| environment | Windows 11, 4 physical / 8 logical cores, 7.7 GB RAM; Python 3.12.0; numpy 2.5.2, pandas 3.0.5, scipy 1.18.0, scikit-learn 1.9.0, lightgbm 4.7.0, xgboost 3.4.0 (`requirements.txt`, `environment_freeze.txt`) |
| tests | study tests `tests/unit/test_forecast_study_v2.py` (17); repository suite 1,777 passed / 34 skipped / 0 failed (33 min, R2); the repository-level `tests/conftest.py` needs the backend stack, so the study tests are also run with `--noconftest` in a pinned environment |
| commands | `REPRODUCIBILITY.md`, `FINAL_HUMAN_REVIEW_PACKAGE.md` §3 |

## 2. File protection rules for this gate

*May be created or changed:* everything under `research/forecast_study_v2/quality_gate/`; the new study directory `research/forecast_study_v3_fresh_stats/`; `tests/unit/test_forecast_study_v3.py`; the new manuscript `MANUSCRIPT_R3.md` (and its figures/tables/build files); the session memory file.
*Must remain untouched:* the 24 frozen v2 files; every file under `research/forecast_study_v2/results/**`; manuscripts `MANUSCRIPT_R2.md` and `MANUSCRIPT_FINAL_DRAFT.md`; `research/forecast_study_v1/**`; `experiments/**`; `ml/benchmark/**`; `data/**`; credentials/environment files. The final report states whether any of them changed (hash comparison, `FINAL_VERIFICATION_REPORT_R3.md`).

## 3. What was audited

Read in full: `windows.py`, `data.py`, `metrics.py`, `baselines.py`, `models.py`, `pipeline.py`, `analysis.py`, parts of `verify_independent.py` and `simulation.py`; `ml/benchmark/datasets.py` (M5 loader) and `ml/benchmark/features.py` (feature construction, leakage assertion). Recomputed from `predictions.npz` with code that does not use the study's metric functions: every H1, H1b, H2, H3 improvement of all 22 cells (maximum absolute difference to `analysis_*.json`: 2.2e-16).

## 4. Initial findings (full register: `SCIENTIFIC_ISSUES.csv`)

**No coding error, leakage path or arithmetic discrepancy was found.** Specifically verified: window arithmetic and disjointness; block ordering; eligibility (units sold on days without a listed price = 0 in all sampled series); baseline information cut-offs (matched: through t − H; fresh: block or week start; perturbation tests exist); features (lag/rolling features shifted by H; price and calendar features use day-t listings only; perturbation assertion at three cut-offs); training rows bounded by o − 1; selection computed from validation blocks only and written before test fits (file modification times checked by the second code path); crossed-bootstrap, delta-method and week-bootstrap implementations consistent with the written protocol.

**Scientific concerns (none invalidates a reported number; several limit what may be claimed):**
1. Selection margins within the median-type class are tiny (0.02–1.1 %) — the claim belongs to the class, not to "absolute-error LightGBM" (SI-01, major).
2. The item-day gain does not extend to asymmetric loss; no decision value is shown (SI-02, major).
3. No classical statistical (ETS/ARIMA/Theta) or other competitor classes in v2 (SI-03, major); "best simple baseline" must always carry its qualifier.
4. H1b at H = 28 inconclusive in all four datasets (SI-04, major reporting).
5. The dual-method rule gives limited corroboration for the item-day endpoint because both methods share dependence assumptions; weekly differences are autocorrelated (lag-1 up to +0.65) (SI-05, moderate) — a dependence-robust sensitivity analysis leaves all 22 H1 verdicts and all H2 verdicts unchanged.
6. The aggregate endpoint has 24 weekly blocks; TX_1 H28 remains a boundary case (SI-06).
7. The primary metric type (wMAPE) is criticised for count data in the literature (SI-07).
8. The M5 eligibility cut-off is window-independent and unsuitable for earlier windows (SI-08).
9. Verification so far is same-agent; the "second code path" takes the stored model forecasts as input (it recomputes baselines, metrics, inference and verdicts, not the model fits), which only a full re-execution (E1) covers (SI-12, SI-13).

**Pre-existing disclosed exposures:** the data audit computed zero shares of test-period *targets* before the v2 freeze (targets only; `DEVIATIONS.md`); no model forecast or score of a W2/W3/WI_1 test block existed before the freeze.

## 5. Statement on novelty and venue fit

The central finding follows from established theory (SI-07, `REFERENCE_AND_RIGHTS_AUDIT.md`); the paper adds effect sizes and robustness evidence for four public datasets and a fresh-window check. That is a modest empirical contribution. Venues with correctness-first review (e.g. TMLR) fit this scope better than venues expecting methodological novelty; no venue is guaranteed (`SUBMISSION_READINESS_REPORT.md`).
