"""Hash every file the audit must not modify (study results, plan, freeze, manuscript, code, historical benchmark). Usage: python snapshot_hashes.py before|after"""
import hashlib
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[3]
STUDY = ROOT / "research" / "forecast_study_v1"
SKIP_PARTS = {"audit_v1", "__pycache__"}


def files():
    for base in (STUDY, ROOT / "experiments" / "ml_benchmark_v1"):
        for p in sorted(base.rglob("*")):
            if p.is_file() and not (SKIP_PARTS & set(p.relative_to(ROOT).parts)) and p.suffix != ".pyc":
                yield p
    m = ROOT / "experiments" / "experiment_manifest.json"
    if m.exists():
        yield m


def main(tag):
    out = {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in files()}
    (pathlib.Path(__file__).parent / f"protected_snapshot_{tag}.json").write_text(json.dumps(out, indent=0), encoding="utf-8")
    print(tag, len(out), "files hashed")


if __name__ == "__main__":
    main(sys.argv[1])
