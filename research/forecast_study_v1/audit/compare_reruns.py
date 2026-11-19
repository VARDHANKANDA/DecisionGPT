"""Compare regenerated benchmark results (audit/reruns) with the stored historical results, number by number.

Keys that legitimately differ between runs (run id, timestamps, runtimes, inference speed, versions) are ignored; every other number is compared.
Read-only for both sides; writes ``audit/rerun_comparison.json``.

    python -m research.forecast_study_v1.audit.compare_reruns [task ...]
"""
from __future__ import annotations

import glob
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HIST = ROOT / "experiments" / "ml_benchmark_v1"
RERUN = Path(__file__).resolve().parent / "reruns"
OUT = Path(__file__).resolve().parent / "rerun_comparison.json"
IGNORE = {"run_id", "created_utc", "runtime_seconds_total", "runtimes_seconds", "inference_ms_per_row", "fit_seconds", "elapsed_s", "git_revision", "versions", "path"}


def walk(a, b, path, out):
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            if k in IGNORE:
                continue
            if k not in a or k not in b:
                out["structure"].append(f"{path}/{k}: only in {'stored' if k in a else 'rerun'}")
                continue
            walk(a[k], b[k], f"{path}/{k}", out)
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            out["structure"].append(f"{path}: length {len(a)} vs {len(b)}")
            return
        for i, (x, y) in enumerate(zip(a, b)):
            walk(x, y, f"{path}[{i}]", out)
    elif isinstance(a, bool) or isinstance(b, bool) or isinstance(a, str) or isinstance(b, str) or a is None or b is None:
        if a != b:
            out["non_numeric_differences"].append(f"{path}: {a!r} vs {b!r}")
    else:
        try:
            fa, fb = float(a), float(b)
        except (TypeError, ValueError):
            return
        out["n_numbers"] += 1
        if math.isnan(fa) and math.isnan(fb):
            return
        d = abs(fa - fb)
        if d > out["max_abs_diff"]:
            out["max_abs_diff"], out["max_abs_diff_at"] = d, path
        if d > 1e-9 * max(1.0, abs(fa)):
            out["numbers_differing"].append({"path": path, "stored": fa, "rerun": fb, "abs_diff": d})


def main(tasks: list[str]) -> int:
    report = {}
    for t in tasks:
        stored = [d for d in sorted(glob.glob(str(HIST / f"{t}_*"))) if not Path(d, "SUPERSEDED.md").exists()]
        reruns = sorted(glob.glob(str(RERUN / f"{t}_*")))
        if not stored or not reruns:
            report[t] = {"status": "missing", "stored": len(stored), "reruns": len(reruns)}
            continue
        a = json.load(open(Path(stored[-1]) / "results.json", encoding="utf-8"))
        b = json.load(open(Path(reruns[-1]) / "results.json", encoding="utf-8"))
        out = {"n_numbers": 0, "max_abs_diff": 0.0, "max_abs_diff_at": None, "numbers_differing": [], "structure": [], "non_numeric_differences": []}
        walk(a, b, "", out)
        meta = json.load(open(Path(reruns[-1]) / "metadata.json", encoding="utf-8"))
        out.update({"stored_run": Path(stored[-1]).name, "rerun": Path(reruns[-1]).name, "rerun_versions": meta.get("versions"), "rerun_git_revision": meta.get("git_revision"),
                    "identical_within_1e-9": not out["numbers_differing"] and not out["structure"] and not out["non_numeric_differences"]})
        out["numbers_differing"] = out["numbers_differing"][:25]
        report[t] = out
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    for t, r in report.items():
        print(t, {k: r.get(k) for k in ("identical_within_1e-9", "n_numbers", "max_abs_diff", "max_abs_diff_at", "status")}, "| n differing:", len(r.get("numbers_differing", [])),
              "| structure:", len(r.get("structure", [])), "| non-numeric:", len(r.get("non_numeric_differences", [])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:] or ["c1", "c2", "f2", "f1"]))
