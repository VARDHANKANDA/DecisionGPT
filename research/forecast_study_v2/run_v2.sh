#!/usr/bin/env bash
# forecast_study_v2 orchestration. Run from the repository root:
#   PYTHONPATH=. bash research/forecast_study_v2/run_v2.sh validation   # stage 1: validation fits + selection (no test block is read)
#   PYTHONPATH=. bash research/forecast_study_v2/run_v2.sh test         # stage 2: refuses to run unless FREEZE.json verifies and selection.json exists
# Environment: PY (python interpreter, default: python). Interrupted runs resume from fits/ when the configuration hash is unchanged.
set -u
stage=${1:?usage: run_v2.sh validation|test}
PY=${PY:-python}
M=research.forecast_study_v2
# confirmatory window first, then replication windows, then the non-independent re-evaluation
CELLS=("W2 m5_ca1" "W2 m5_tx1" "W2 m5_wi1" "W2 or2" "W3 m5_ca1" "W3 m5_tx1" "W3 m5_wi1" "W1 m5_wi1" "W1 m5_ca1" "W1 m5_tx1" "W1 or2")
for c in "${CELLS[@]}"; do
  set -- $c
  w=$1; d=$2
  seeds=""
  if [ "$stage" = "test" ] && [ "$w" = "W2" ]; then seeds="--seeds 43 44"; fi
  echo "=== $stage $w $d start $(date +%T)"
  $PY -m $M.pipeline --dataset "$d" --window "$w" --H 28 7 --stage "$stage" $seeds || echo "=== FAILED $stage $w $d"
  echo "=== $stage $w $d end $(date +%T)"
done
echo "=== ALL DONE $stage $(date +%T)"
