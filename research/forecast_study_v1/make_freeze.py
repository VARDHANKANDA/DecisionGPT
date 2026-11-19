"""Write FREEZE.json: sha256 of the plan, the study code and its tests, plus the git head, before any confirmatory run."""
import datetime
import hashlib
import json
import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[2]
D = pathlib.Path(__file__).resolve().parent


def main() -> dict:
    files = sorted(D.glob("*.py")) + [D / "EXPERIMENT_PLAN.md", ROOT / "tests" / "unit" / "test_forecast_study.py"]
    sha = {f.relative_to(ROOT).as_posix(): hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
    hist = ROOT / "experiments" / "ml_benchmark_v1" / "HISTORICAL_HASHES.json"
    out = {"frozen_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(), "git_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
           "statement": "EXPERIMENT_PLAN.md and the code listed here were fixed before any confirmatory (full) run; later changes go to the plan's deviations log.",
           "sha256": sha, "historical_hash_file_sha256": hashlib.sha256(hist.read_bytes()).hexdigest(),
           "results_dir_at_freeze": sorted(p.name for p in (D / "results").glob("*"))}
    (D / "FREEZE.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    return out


if __name__ == "__main__":
    o = main()
    print(o["frozen_utc"], o["git_head"][:10], len(o["sha256"]), o["results_dir_at_freeze"])
