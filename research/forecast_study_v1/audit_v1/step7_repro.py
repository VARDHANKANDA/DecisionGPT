"""Step 7: cheap, non-destructive reproducibility checks. Nothing under results/ or the protected directories is written; table/figure regeneration runs in a TEMPORARY copy."""
import filecmp
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import ind_core as ic  # noqa: E402

AUD = Path(__file__).parent
ROOT = ic.ROOT
STUDY = ic.STUDY
out = {}

# (1) stored per-fit arrays vs predictions.npz
chk = {}
for cell in ic.CELLS:
    A = ic.stored(cell)
    sel = ic.jload(STUDY / "results" / cell / "selection.json")
    cfg = ic.jload(STUDY / "results" / cell / "config.json")
    per_family = {}
    for fam, cid in sel["chosen_variant_per_family"].items():
        f, v = cid.split(":")
        parts = [np.load(STUDY / "results" / cell / "fits" / f"test_{o}_{f}-{v}.npy") for o in cfg["windows"]["test"]]
        cat = np.concatenate(parts)
        per_family[cid] = bool(len(cat) == len(A[f"pred__{f}__{v}"]) and np.allclose(cat, A[f"pred__{f}__{v}"], atol=0, rtol=0))
    chk[cell] = per_family
out["fits_equal_predictions_npz"] = chk

# (2) machine-specific paths and hard-coded environment in the study files
pat = re.compile(r"[A-Za-z]:[\\/]|/Users/|backend/\.venv|Scripts/python|\.venv")
hits = {}
for p in sorted(list(STUDY.glob("*.py")) + list(STUDY.glob("*.sh")) + list(STUDY.glob("*.md")) + list((STUDY / "manuscript").glob("*.md"))):
    n = [(i + 1, l.strip()[:120]) for i, l in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines()) if pat.search(l)]
    if n:
        hits[p.name] = n[:6]
out["machine_specific_path_mentions"] = hits

# (3) dependency declarations
decl = {}
for req in sorted((ROOT / "backend").glob("requirements*.txt")) + sorted(ROOT.glob("requirements*.txt")) + sorted(ROOT.glob("ml/**/requirements*.txt")):
    txt = req.read_text(encoding="utf-8", errors="replace").lower()
    decl[str(req.relative_to(ROOT))] = {k: (k in txt) for k in ("lightgbm", "xgboost", "catboost", "scikit-learn", "scipy", "matplotlib", "numpy", "pandas", "openpyxl")}
out["dependency_files"] = decl
out["pyproject_present"] = (ROOT / "pyproject.toml").exists() or (ROOT / "backend" / "pyproject.toml").exists()
out["research_specific_requirements_file"] = any((STUDY / n).exists() for n in ("requirements.txt", "pyproject.toml", "environment.yml"))
out["environment_freeze_txt"] = (STUDY / "environment_freeze.txt").read_text(encoding="utf-8").split()

# (4) regenerate tables + figures in a temporary copy and compare
tmp = Path(tempfile.mkdtemp(prefix="audit_regen_"))
dst = tmp / "research" / "forecast_study_v1"
dst.mkdir(parents=True)
for n in ("make_report.py", "__init__.py"):
    shutil.copy(STUDY / n, dst / n)
(tmp / "research" / "__init__.py").write_text("")
for p in (STUDY / "results").rglob("*.json"):
    if p.name in ("analysis.json", "results.json", "selection.json") or p.name.startswith(("ABLATIONS", "E1_", "S2_", "CONFIRMATORY")) or p.parent.name.startswith("s2_"):
        t = dst / "results" / p.relative_to(STUDY / "results")
        t.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(p, t)
r = subprocess.run([sys.executable, "-I", "-c", f"import sys; sys.path.insert(0, r'{tmp}'); import research.forecast_study_v1.make_report as m; m.main()"], capture_output=True, text=True, cwd=str(tmp))
out["regen_returncode"] = r.returncode
out["regen_stderr_tail"] = r.stderr[-400:]
same_tables = (dst / "results" / "TABLES.md").read_bytes() == (STUDY / "results" / "TABLES.md").read_bytes() if (dst / "results" / "TABLES.md").exists() else None
out["TABLES_md_byte_identical_after_regeneration"] = same_tables
figs = {}
for f in sorted((STUDY / "manuscript" / "figures").glob("*.svg")):
    g = dst / "manuscript" / "figures" / f.name
    if g.exists():
        norm = lambda b: re.sub(rb"<dc:date>.*?</dc:date>", b"", re.sub(rb'id="[^"]+"', b"", re.sub(rb'(xlink:href|clip-path)="[^"]*"', b"", b)))  # noqa: E731
        figs[f.name] = norm(f.read_bytes()) == norm(g.read_bytes())
out["figures_identical_ignoring_ids_and_date"] = figs
shutil.rmtree(tmp, ignore_errors=True)

# (5) missing-input behaviour (read-only calls)
miss = {}
r = subprocess.run([sys.executable, "-I", "-c", f"import sys; sys.path.insert(0, r'{ROOT}'); import research.forecast_study_v1.analyze as a; a.load('fs1_does_not_exist')"], capture_output=True, text=True, cwd=str(ROOT))
miss["analyze_on_missing_cell"] = {"returncode": r.returncode, "last_line": (r.stderr.strip().splitlines() or [""])[-1][:200]}
out["missing_input_behaviour"] = miss

# (6) historical hash file and freeze record
hh = ic.jload(ROOT / "experiments" / "ml_benchmark_v1" / "HISTORICAL_HASHES.json")
bad = []
n = 0
for k, v in hh["files"].items():
    p = ROOT / "experiments" / "ml_benchmark_v1" / k
    if not p.exists():
        p = ROOT / k
    if not p.exists():
        bad.append((k, "missing"))
        continue
    n += 1
    if hashlib.sha256(p.read_bytes()).hexdigest() != (v if isinstance(v, str) else v.get("sha256")):
        bad.append((k, "MISMATCH"))
out["historical_hashes_checked"] = {"checked": n, "listed": len(hh["files"]), "bad": bad}
fz = ic.jload(STUDY / "FREEZE.json")
cur = {k: hashlib.sha256((ROOT / k).read_bytes()).hexdigest() for k in fz["sha256"]}
out["freeze_code_hash_status"] = {k: ("unchanged" if cur[k] == fz["sha256"][k] else "CHANGED") for k in fz["sha256"]}
plan = (STUDY / "EXPERIMENT_PLAN.md").read_bytes()
out["plan_text_above_deviation_log_hash_matches_freeze"] = hashlib.sha256(plan.split(b"## 11. Deviations log")[0]).hexdigest() == fz["plan_sha256_text_above_deviations_log"]
out["freeze_git_head"] = fz["git_head"]
g = subprocess.run(["git", "log", "--oneline", "-3", "--", "research/forecast_study_v1"], capture_output=True, text=True, cwd=str(ROOT))
out["git_history_of_study_dir"] = g.stdout.strip() or "none (directory is untracked: no commit history, no external timestamp)"
(AUD / "work" / "step7.json").write_text(json.dumps(out, indent=1, default=str), encoding="utf-8")
print(json.dumps({k: out[k] for k in ("regen_returncode", "TABLES_md_byte_identical_after_regeneration", "figures_identical_ignoring_ids_and_date", "historical_hashes_checked", "plan_text_above_deviation_log_hash_matches_freeze", "missing_input_behaviour", "git_history_of_study_dir")}, indent=1))
print("fits==npz all:", all(all(v.values()) for v in chk.values()))
print("freeze status:", {k.split("/")[-1]: v for k, v in out["freeze_code_hash_status"].items() if v != "unchanged"})
print("machine-specific mentions:", {k: len(v) for k, v in hits.items()})
print("dependency files:", decl)
