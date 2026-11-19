#!/usr/bin/env bash
# Pre-registered execution order (EXPERIMENT_PLAN.md section 7). Re-running resumes from fits/ when the configuration hash matches.
# Run from the repository root:  PYTHONPATH=. bash research/forecast_study_v1/run_all.sh
set -u
PY=backend/.venv/Scripts/python.exe
M=research.forecast_study_v1
export STUDY_THREADS=${STUDY_THREADS:-4}
for cell in "m5_ca1 28" "or2_top100 28" "m5_tx1 28" "m5_ca1 7" "or2_top100 7" "m5_tx1 7"; do
  set -- $cell
  echo "=== $1 H=$2 start $(date +%T)"
  $PY -m $M.run_forecast_study "$1" "$2" || echo "=== FAILED $1 H=$2"
  echo "=== $1 H=$2 end $(date +%T)"
done
echo "=== ablations (m5_ca1 H=28)"
$PY -m $M.run_forecast_study m5_ca1 28 --ablate price || echo "=== FAILED ablate price"
$PY -m $M.run_forecast_study m5_ca1 28 --ablate calendar || echo "=== FAILED ablate calendar"
$PY -m $M.run_forecast_study m5_ca1 28 --ablate history_stats || echo "=== FAILED ablate history_stats"
$PY -m $M.run_forecast_study m5_ca1 28 --ablate static_ids || echo "=== FAILED ablate static_ids"
echo "=== S2 classification"
$PY -m $M.run_classification_study || echo "=== FAILED S2"
echo "=== ALL DONE $(date +%T)"
