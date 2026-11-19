# REPRODUCE_COMMANDS — every reported result, in dependency order

Run from the repository root (`D:\DecisionGPT`); `PYTHONPATH=.`; `PY` = the pinned Python 3.12.0 environment (`research/forecast_study_v2/requirements.txt`); `STATS_PY` = a separate environment with `research/forecast_study_v3_fresh_stats/requirements_stats.txt`. M5 raw data must be obtained from Kaggle under its rules (`data/external/m5_forecasting/raw/`); Online Retail II from UCI. **Never write outputs into the existing `results/` directories; never publish `predictions.npz`, `fits/` or `y.npy`.**

## A. v2 study (frozen; confirmatory + replication)

```bash
$PY -m pytest tests/unit/test_forecast_study_v2.py -q                 # 17 unit tests
$PY -m research.forecast_study_v2.freeze verify                       # 24 frozen files
$PY -m research.forecast_study_v2.tools.data_audit
$PY -m research.forecast_study_v2.tools.independent_targets_check
PY=$PY bash research/forecast_study_v2/run_v2.sh validation           # ~1 h (existing results are reused only when the config hash matches)
PY=$PY bash research/forecast_study_v2/run_v2.sh test                 # ~1.5 h
$PY -m research.forecast_study_v2.report                              # analysis, tables, figures (also rewrites results/analysis/*.json with identical values)
$PY -m research.forecast_study_v2.report_extra
$PY research/forecast_study_v2/verify_independent.py W2 W3 W1         # second code path (same author)
$PY -m research.forecast_study_v2.supplementary_h3                    # supplementary H3 precision check (~6 min)
```

## B. Quality gate (R3)

```bash
$PY research/forecast_study_v2/quality_gate/tools/inventory.py <tag>                 # artifact inventory (sha256, class, restricted flag)
$PY research/forecast_study_v2/tools/protect_snapshot.py <tag>                       # protected-file hashes
$PY research/forecast_study_v2/quality_gate/audit_sensitivity.py                     # dependence / margins / pinball / recomputation (~1 min)
# E1: clean-environment reproduction of all 22 cells, into a scratch directory OUTSIDE the repository:
#     for each (window, dataset) in the run_v2.sh list: pipeline stage "both" (+ seeds 43 44 for W2) with pipeline.RESULTS patched to the scratch directory (driver: quality_gate/tools/rerun_one.py)
$PY research/forecast_study_v2/quality_gate/e1_compare.py <scratch_results_dir>      # -> quality_gate/results/e1_reproduction.json
$PY research/forecast_study_v2/quality_gate/e2_selection_robustness.py <scratch_dir> # all 8 candidates on the W2 test blocks (~1-3 h); exploratory
$PY research/forecast_study_v2/quality_gate/tools/write_issues.py
```

## C. Fresh-window study (v3)

```bash
$PY -m research.forecast_study_v3_fresh_stats.freeze3 verify
PY=$PY STATS_PY=$STATS_PY bash research/forecast_study_v3_fresh_stats/run_v3.sh prep
PY=$PY STATS_PY=$STATS_PY bash research/forecast_study_v3_fresh_stats/run_v3.sh statval
PY=$PY STATS_PY=$STATS_PY bash research/forecast_study_v3_fresh_stats/run_v3.sh validation
PY=$PY STATS_PY=$STATS_PY bash research/forecast_study_v3_fresh_stats/run_v3.sh stattest
PY=$PY STATS_PY=$STATS_PY bash research/forecast_study_v3_fresh_stats/run_v3.sh test
PY=$PY STATS_PY=$STATS_PY bash research/forecast_study_v3_fresh_stats/run_v3.sh analysis
$PY -m pytest tests/unit/test_forecast_study_v3.py -q
```

## D. Manuscript R3

```bash
$PY research/forecast_study_v2/tools/build_tables.py                                  # v2 tables (from stored artifacts)
$PY research/forecast_study_v2/quality_gate/tools/build_tables_r3.py                  # new R3 tables
$PY research/forecast_study_v2/quality_gate/tools/make_figures_r3.py                  # new R3 figures
$PY research/forecast_study_v2/quality_gate/tools/assemble_r3.py                      # MANUSCRIPT_R3.md
$PY research/forecast_study_v2/quality_gate/tools/check_numbers_r3.py                 # numeric consistency of the manuscript
# PDF (review copy): pandoc + xelatex, see quality_gate/tools/build_pdf_r3.sh
```

## E. Full repository suite

```bash
$PY -m pytest tests -q -p no:cacheprovider        # 33 min; do not run two pytest sessions concurrently
```
