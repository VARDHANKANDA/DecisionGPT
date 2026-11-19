"""Hash freeze of forecast_study_v3: protocol, code, tests, requirements and the v2 modules it imports.
`python -m research.forecast_study_v3_fresh_stats.freeze3 create|verify`. Internal, timestamped; NOT a public pre-registration."""
from __future__ import annotations

import datetime
import hashlib
import json
import subprocess
import sys

from . import v3common as C

FILES = ["PROTOCOL_V3.md", "v3common.py", "data3.py", "stat_forecasts.py", "run_v3.py", "analysis3.py", "freeze3.py", "requirements_stats.txt", "run_v3.sh"]
V2 = ["pipeline.py", "data.py", "windows.py", "baselines.py", "models.py", "metrics.py", "analysis.py", "common.py", "freeze.py"]
TESTS = ["tests/unit/test_forecast_study_v3.py"]


def _sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def paths():
    out = {f"research/forecast_study_v3_fresh_stats/{f}": C.STUDY / f for f in FILES}
    out.update({f"research/forecast_study_v2/{f}": C.ROOT / "research" / "forecast_study_v2" / f for f in V2})
    out.update({t: C.ROOT / t for t in TESTS})
    out["ml/benchmark/datasets.py"] = C.ROOT / "ml" / "benchmark" / "datasets.py"
    out["ml/benchmark/features.py"] = C.ROOT / "ml" / "benchmark" / "features.py"
    return out


def create():
    try:
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=C.ROOT, capture_output=True, text=True).stdout.strip()
    except Exception:
        head = None
    d = {"frozen_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(), "git_head": head,
         "statement": "forecast_study_v3 protocol and code frozen BEFORE any data of the fresh stores was read for modelling or scoring (prep/validation/test not yet run). Internal timestamped hash, not a public pre-registration.",
         "sha256": {k: _sha(p) for k, p in paths().items()}}
    (C.STUDY / "FREEZE3.json").write_text(json.dumps(d, indent=1), encoding="utf-8")
    print("frozen", len(d["sha256"]), "files at", d["frozen_utc"])


def verify():
    f = json.loads((C.STUDY / "FREEZE3.json").read_text(encoding="utf-8"))["sha256"]
    bad = [k for k, p in paths().items() if f.get(k) != _sha(p)]
    if bad:
        raise RuntimeError(f"frozen v3 files changed: {bad}")
    print("freeze3 verified:", len(f), "files unchanged")


if __name__ == "__main__":
    {"create": create, "verify": verify}[sys.argv[1]]()
