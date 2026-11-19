"""Re-run the historical benchmark tasks into a NEW directory to test whether the stored results regenerate.

The historical runner (``ml.benchmark.run``) writes under ``experiments/ml_benchmark_v1``. That folder is frozen, so its output root is redirected
here before anything runs; nothing under ``experiments/`` is created or modified. The historical code, configuration and seeds are used unchanged.

    python -m research.forecast_study_v1.audit.rerun_historical c1 c2 f2 f1
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import ml.benchmark.run as hist

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "research" / "forecast_study_v1" / "audit" / "reruns"
assert not str(OUT).startswith(str(ROOT / "experiments")), "refusing to write into the frozen experiments tree"
OUT.mkdir(parents=True, exist_ok=True)
hist.OUT_ROOT = OUT

TASKS = {"c1": hist.run_c1, "c2": hist.run_c2, "f2": hist.run_f2, "f1": hist.run_f1}

if __name__ == "__main__":
    for name in sys.argv[1:] or list(TASKS):
        t0 = time.time()
        print(f"=== {name} start", flush=True)
        path = TASKS[name]()
        print(f"=== {name} done in {round(time.time() - t0)}s -> {path}", flush=True)
