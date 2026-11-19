"""Phase-3 verification (read-only): protected files unchanged vs the phase3_before snapshot; frozen plan/code/historical hashes; manifest; v2 manuscript integrity checks.
Writes audit_v1/phase3_verification.json."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

AUD = Path(__file__).parent
STUDY = AUD.parent
ROOT = STUDY.parents[1]
sys.path.insert(0, str(AUD))
import snapshot_hashes as sh  # noqa: E402

sh.main("phase3_after")
before = json.load(open(AUD / "protected_snapshot_phase3_before.json"))
after = json.load(open(AUD / "protected_snapshot_phase3_after.json"))
out = {"snapshot": {"before_files": len(before), "after_files": len(after), "changed": [k for k in before if k in after and before[k] != after[k]],
                    "removed": [k for k in before if k not in after], "added": [k for k in after if k not in before]}}

# originals untouched (explicit)
originals = ["research/forecast_study_v1/manuscript/MANUSCRIPT.md", "research/forecast_study_v1/EXPERIMENT_PLAN.md", "research/forecast_study_v1/FREEZE.json", "research/forecast_study_v1/results/CONFIRMATORY_SUMMARY.md",
             "research/forecast_study_v1/results/TABLES.md", "research/forecast_study_v1/manuscript/figures/fig1_forest.svg"]
out["originals_identical_before_after"] = {k: before[k] == after[k] for k in originals}
out["predictions_files"] = {"count": sum(1 for k in before if k.endswith("predictions.npz")), "all_identical": all(before[k] == after[k] for k in before if k.endswith("predictions.npz"))}
out["results_tree"] = {"count": sum(1 for k in before if "/results/" in k), "all_identical": all(before[k] == after[k] for k in before if "/results/" in k)}
out["historical_benchmark_tree"] = {"count": sum(1 for k in before if k.startswith("experiments/ml_benchmark_v1/")), "all_identical": all(before[k] == after[k] for k in before if k.startswith("experiments/ml_benchmark_v1/"))}

# frozen records
fz = json.load(open(STUDY / "FREEZE.json"))
cur = {k: hashlib.sha256((ROOT / k).read_bytes()).hexdigest() for k in fz["sha256"]}
out["freeze_code_and_plan"] = {k.split("/")[-1]: ("unchanged" if cur[k] == fz["sha256"][k] else "CHANGED") for k in fz["sha256"]}
plan = (STUDY / "EXPERIMENT_PLAN.md").read_bytes()
out["plan_text_above_deviation_log_matches_freeze"] = hashlib.sha256(plan.split(b"## 11. Deviations log")[0]).hexdigest() == fz["plan_sha256_text_above_deviations_log"]
hh = json.load(open(ROOT / "experiments" / "ml_benchmark_v1" / "HISTORICAL_HASHES.json"))
bad, n = [], 0
for k, v in hh["files"].items():
    p = ROOT / "experiments" / "ml_benchmark_v1" / k
    p = p if p.exists() else ROOT / k
    if not p.exists():
        bad.append((k, "missing"))
        continue
    n += 1
    if hashlib.sha256(p.read_bytes()).hexdigest() != (v if isinstance(v, str) else v.get("sha256")):
        bad.append((k, "MISMATCH"))
out["historical_hashes"] = {"checked": n, "listed": len(hh["files"]), "bad": bad}
out["historical_hash_file_sha256_matches_freeze_record"] = hashlib.sha256((ROOT / "experiments" / "ml_benchmark_v1" / "HISTORICAL_HASHES.json").read_bytes()).hexdigest() == fz["historical_hash_file_sha256"]
out["experiment_manifest_sha256"] = hashlib.sha256((ROOT / "experiments" / "experiment_manifest.json").read_bytes()).hexdigest()
out["experiment_manifest_matches_frozen_constant"] = out["experiment_manifest_sha256"] == "94aa419c703b1babb465975463b26e55255755a7687ecbecadb6db4c4c15cbff"
r = subprocess.run([sys.executable, str(ROOT / "research" / "r4" / "audit" / "verify_historical_freeze.py")], capture_output=True, text=True, cwd=str(ROOT), env={**__import__("os").environ, "PYTHONPATH": str(ROOT)})
out["verify_historical_freeze_py"] = {"returncode": r.returncode, "last_line": r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr.strip()[-200:]}

# v2 integrity
v2 = (STUDY / "manuscript" / "MANUSCRIPT_v2.md").read_text(encoding="utf-8")
out["v2"] = {"words": len(v2.split()), "no_unfilled_markers": "<<" not in v2, "abstract_words": len(v2[v2.index("## Abstract"):v2.index("## 1. Introduction")].split()) - 2,
             "banned_phrases_absent": {p: (p not in v2) for p in ("exactly the official evaluation window", "store-day", "near-nominal", "pre-registered evaluation", "Pre-registered")},
             "required_phrases_present": {p: (p in v2) for p in ("not ready for submission", "Not ready for submission", "post hoc", "**internal** record", "does not show that machine-learning forecasts generally fail to beat simple baselines", "public leaderboard", "zero-demand rows", "Appendix A")}}
(AUD / "phase3_verification.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
ok = (not out["snapshot"]["changed"] and not out["snapshot"]["removed"] and all(out["originals_identical_before_after"].values()) and out["predictions_files"]["all_identical"] and out["results_tree"]["all_identical"]
      and out["historical_benchmark_tree"]["all_identical"] and not out["historical_hashes"]["bad"] and out["plan_text_above_deviation_log_matches_freeze"] and out["experiment_manifest_matches_frozen_constant"] and out["verify_historical_freeze_py"]["returncode"] == 0)
print(json.dumps(out, indent=1))
print("\nPROTECTED ARTIFACTS UNCHANGED:", ok)
