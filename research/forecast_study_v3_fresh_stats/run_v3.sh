#!/usr/bin/env bash
# forecast_study_v3 orchestration. Run from the repository root.
#   PY=<pinned-env python>  STATS_PY=<statistics-env python>  bash research/forecast_study_v3_fresh_stats/run_v3.sh <stage>
# Stages (must be run in this order; every stage resumes from its cache):
#   prep        data preparation for the three fresh stores (no model is fitted, no score computed)
#   statval     statistical baselines for the three validation blocks (history only)
#   validation  learned models + all baselines on the validation blocks; writes selection.json per cell
#   stattest    statistical baselines for the six test blocks (refuses to run unless selection.json exists for the store)
#   test        test-block fits of the selected models + scoring (v2 pipeline; refuses unless the v2 and v3 freezes verify)
#   analysis    confirmatory analysis (analysis3.py)
set -u
stage=${1:?usage: run_v3.sh prep|statval|validation|stattest|test|analysis}
PY=${PY:-python}
STATS_PY=${STATS_PY:-python}
M=research.forecast_study_v3_fresh_stats
R=research/forecast_study_v3_fresh_stats/results
STORES="m5_ca2 m5_tx2 m5_wi2"
$PY -m $M.freeze3 verify || exit 1
case "$stage" in
  prep)       $PY -m $M.run_v3 prep --stores $STORES ;;
  statval)    for s in $STORES; do $STATS_PY research/forecast_study_v3_fresh_stats/stat_forecasts.py --root $R --store $s --stage val --workers 4; done ;;
  validation) $PY -m $M.run_v3 validation --stores $STORES ;;
  stattest)   for s in $STORES; do
                for H in 28 7; do [ -f $R/W4/${s}_H$H/selection.json ] || { echo "selection.json missing for $s H$H"; exit 1; }; done
                $STATS_PY research/forecast_study_v3_fresh_stats/stat_forecasts.py --root $R --store $s --stage test --workers 4
              done ;;
  test)       $PY -m $M.run_v3 test --stores $STORES --seeds 43 44 ;;
  analysis)   $PY -m $M.analysis3 ;;
esac
