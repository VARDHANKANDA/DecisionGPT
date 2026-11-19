"""Clean-environment re-run of ONE (window, dataset) pair, both horizons, stage 'both', into a scratch results directory (never the repository's results/).
Used for E1. Usage: python rerun_one.py <window> <dataset> <scratch_results_dir>   (run from the repository root with PYTHONPATH=.)"""
import sys
import time
from pathlib import Path

window, dataset, scratch = sys.argv[1], sys.argv[2], Path(sys.argv[3])
from research.forecast_study_v2 import pipeline as pl  # noqa: E402

assert "forecast_study_v2" not in str(scratch.parent.name) or "scratch" in str(scratch).lower() or "tmp" in str(scratch).lower(), "refusing to write into the repository's results/"
pl.RESULTS = scratch
seeds = ["--seeds", "43", "44"] if window == "W2" else []
sys.argv = ["pipeline", "--dataset", dataset, "--window", window, "--H", "28", "7", "--stage", "both", *seeds]
t = time.time()
pl.main()
print("ELAPSED_S", round(time.time() - t))
