# AUDIT_LOG

Audit of `research/forecast_study_v1` and its manuscript, 2026-10-22 (UTC times from file modification times; local IST = UTC + 5:30).

## 0. Independence statement and mode

* **Who audited:** the same AI assistant that authored the study and the manuscript earlier the same day. The audit is *procedurally* independent (new code that imports nothing from the study or from `ml/`; adversarial checks; sources re-read from primary pages) but **not independent in authorship**. This is recorded as blocker A6.
* **Mode:** read-only with respect to the study. All outputs are in `research/forecast_study_v1/audit_v1/`. The SHA-256 of **543 protected files** (the whole study directory except `audit_v1/`, `experiments/ml_benchmark_v1/`, `experiments/experiment_manifest.json`) was recorded before the audit (05:46:51Z) and again after (06:12:14Z): **0 changed, 0 added, 0 removed** (`protected_snapshot_before.json`, `protected_snapshot_after.json`).
* No experiment, fit or backend suite was re-run; no commit, submission, upload, account creation, contact or payment. No credentials were read or printed. The only external requests were read-only web fetches of publisher/venue/dataset pages and the public Crossref and arXiv metadata APIs.

## 1. Timeline of audit steps

| time (UTC) | step | output |
|---|---|---|
| 05:46:39 | inventory of required files (all present); `snapshot_hashes.py before` | `.started`, `protected_snapshot_before.json` |
| 05:48-05:50 | wrote `ind_core.py` (independent metrics, baselines, loaders, bootstrap, delta-method variance, rank metrics) | `ind_core.py` |
| 05:50:39 | step 1: targets vs raw data; 16 baselines x 6 cells | `work/step1.json` |
| 05:51:16 | step 2: metric recomputation; manuscript tables parsed | `work/step2.json`, `METRIC_RECOMPUTATION.csv` (356 rows) |
| 05:51:49 | step 4: aggregation decomposition; segment labels from raw | `work/step4.json` |
| 05:52:24 | step 5: independent conformal | `work/step5.json` |
| 05:52:42 | step 3: independent bootstrap, delta method, Holm, simulation | `work/step3.json` |
| 05:53:11 | step 6: inactivity study from raw transactions | `work/step6.json` |
| 05:54:49 | step 7: reproducibility checks (temporary regeneration; fits vs predictions; hashes) | `work/step7.json` |
| 05:55:19 | step 8: E1, ablations, segments | `work/step8.json` |
| 05:57:29 | step 9: reference verification (Crossref/arXiv) | `work/step9_refs.json` |
| 05:58-06:03 | web checks: Kaggle M5 data and rules pages; UCI dataset page; IJF/TMLR/PLOS pages; prior-work records | notes in the CSV/MD files |
| 06:03:32 | step 10: 104 extension comparisons (sections 11-15) | `METRIC_RECOMPUTATION.csv` (460 rows) |
| 06:04:20 | step 11: best-method, Kendall, four-classifier checks | `work/step11.json` |
| 06:06:17 | steps 12-13: claim matrix; references/rights | `CLAIM_EVIDENCE_MATRIX.csv`, `REFERENCE_AND_DATA_RIGHTS_AUDIT.csv` |
| 06:08-06:12 | narrative deliverables | `STATISTICAL_AUDIT.md`, `PREREGISTRATION_AND_DEVIATIONS.md`, `FORECAST_DESIGN_AND_AGGREGATION_AUDIT.md`, `REPRODUCIBILITY_AUDIT.md`, `VENUE_READINESS.md`, `BLOCKER_CHECKLIST.md`, `AUDIT_SUMMARY.md` |
| 06:12:14 | `snapshot_hashes.py after`; comparison | 0 differences |

## 2. Commands run (all from the repository root, using `backend/.venv/Scripts/python.exe -I` for audit scripts)

```
python research/forecast_study_v1/audit_v1/snapshot_hashes.py before|after
python -I research/forecast_study_v1/audit_v1/step1_targets_baselines.py   # ~1.2 min
python -I research/forecast_study_v1/audit_v1/step2_metrics.py             # 356 comparisons, 0 FAIL
python -I research/forecast_study_v1/audit_v1/step3_inference.py           # bootstrap B=4000 per test; simulation 2 x 300 replications
python -I research/forecast_study_v1/audit_v1/step4_aggregation.py
python -I research/forecast_study_v1/audit_v1/step5_conformal.py
python -I research/forecast_study_v1/audit_v1/step6_inactivity.py
python -I research/forecast_study_v1/audit_v1/step7_repro.py
python -I research/forecast_study_v1/audit_v1/step8_exploratory.py
python -I research/forecast_study_v1/audit_v1/step9_references.py
python -I research/forecast_study_v1/audit_v1/step10_extend_csv.py         # +104 comparisons, 2 within-noise tolerance exceedances
python -I research/forecast_study_v1/audit_v1/step12_claim_matrix.py ; step13_refs_rights_csv.py ; step14_write_stats_prereg.py ; step15_write_design_agg.py
PYTHONPATH="backend;." pytest tests/unit/test_forecast_study.py -q          # 23 passed
PYTHONPATH=. python research/r4/audit/verify_historical_freeze.py           # OK, 22 artifacts unchanged
sha256sum experiments/experiment_manifest.json                              # 94aa419c... unchanged
git log -- research/forecast_study_v1                                       # empty (untracked)
```
Ad-hoc read-only Python snippets: listing mtimes of fit/selection files, reading `analysis.json`/`results.json`, the transcript timestamp extraction (`C:\Users\VARDHAN\.claude\projects\D--DecisionGPT\bc252fc2-...jsonl`, read-only), and Crossref lookups of eight additional candidate prior-work records.

## 3. Files and pages inspected

* **Study files:** `README.md`, `EXPERIMENT_PLAN.md`, `FREEZE.json`, `REPRODUCIBILITY.md`, `manuscript/MANUSCRIPT.md` (+ parts), `SUBMISSION_CHECKLIST.md`, `VENUE_COMPARISON.md`, `EVIDENCE_CLAIM_MATRIX.md`, `LIMITATIONS_AND_THREATS.md`, `RESEARCH_AUDIT.md`, `LITERATURE_REVIEW.md`, `environment_freeze.txt`, `run_all.sh`, all study code (`protocol.py`, `baselines.py`, `metrics.py`, `inference.py`, `run_forecast_study.py`, `run_classification_study.py`, `analyze.py`, `aggregate.py`, `ablation_report.py`, `verify_cell.py`, `make_report.py`, `exploratory_l1.py`, `s2_customer_disjoint.py`, `make_freeze.py`), tests, `results/**` (config, selection, results, analysis, verification, segments, metadata, predictions, fits, E1, ablations, S2), `audit/` (rerun comparison, recompute report), `inventory/`.
* **Repository:** `ml/benchmark/{datasets,churn,f2_retail,models}.py` (loader and cleaning specifications), `experiments/ml_benchmark_v1/HISTORICAL_HASHES.json`, `experiments/experiment_manifest.json`, `research/r4/audit/verify_historical_freeze.py`, `backend/requirements*.txt`, `ml/benchmark/requirements.txt`.
* **Raw data:** `data/external/m5_forecasting/raw/sales_train_evaluation.csv`; `data/external/uci_online_retail_ii/processed/online_retail_ii_raw_as_csv.csv`.
* **External pages (2026-10-22):** Kaggle M5 Accuracy data page and rules page; Mcompetitions/M5-methods GitHub page; UCI Online Retail II page; IJF aims & scope, guide for authors, open-access options; TMLR main, author guide, acceptance criteria, editorial policies; PLOS ONE criteria, submission guidelines, data availability (fee page blocked); M5 results article (ScienceDirect); Kolassa 2020 article page; proceedings pages for Guo, Ke, Prokhorenkova; arXiv pages for Gibbs & Candès and Chronos; Crossref API records for every DOI; arXiv API for three arXiv items; web searches for Holm 1979, Gneiting 2011, Prestwich et al. 2014, Gibbs & Candès venue, Chronos venue.
* **Missing:** no separate "deviation log" file exists (deviations are in `EXPERIMENT_PLAN.md` section 11); no run log inside the study directory (the run log is in the session scratchpad: `run_all.log`).

## 4. Verification limitations

1. Independence limited as in section 0; conventions defined only by study code (Croston/TSB initialisation, Online Retail II cleaning rules, M5 series draw) were replicated from the code, so an error in a *specification* would not be caught by re-implementation.
2. Model predictions were not regenerated; fits equal stored predictions, nothing more.
3. The customer-split sensitivity, the historical benchmark re-runs and the backend suite were not re-executed; their values are author-reported.
4. File modification times and transcript timestamps are not tamper-proof.
5. PLOS ONE fee, Guo et al.'s bin count, the origin of the term "Mondrian", Prokhorenkova page range, and the content (beyond abstracts/metadata) of Januschowski et al., Bojer & Meldgaard and Spiliotis et al. were not verified; marked as such.
6. Web pages were read as rendered to an automated browser; policies can change.
7. Bootstrap-based values in the audit carry Monte-Carlo error (reported tolerances).
8. The Bash tool mangles backslashes in here-documents; all non-trivial code was written with file tools.
