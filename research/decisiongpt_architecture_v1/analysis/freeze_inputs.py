"""Hash-freeze the protocol and record sha256 of every read-only input (run with the stage label as argument)."""
import hashlib
import json
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[3]
R = REPO / "research" / "decisiongpt_architecture_v1"
stage = sys.argv[1] if len(sys.argv) > 1 else "before"
dirs = ("experiments/r1", "experiments/upgraded_controlled_v1", "experiments/ml_benchmark_v1", "experiments/model_comparison_v1")
files = [REPO / "experiments/experiment_manifest.json"] + [p for d in dirs for p in sorted((REPO / d).rglob("*")) if p.is_file()]
out = {p.relative_to(REPO).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
if stage == "before":
    h = hashlib.sha256((R / "EXPERIMENT_PROTOCOL.md").read_bytes()).hexdigest()
    (R / "PROTOCOL.sha256").write_text(f"{h}  EXPERIMENT_PROTOCOL.md\n")
    print("protocol", h)
dest = R / "results" / f"input_hashes_{stage}.json"
dest.write_text(json.dumps({"stage": stage, "files": out}, indent=1))
prev = R / "results" / "input_hashes_before.json"
if stage != "before" and prev.exists():
    b = json.loads(prev.read_text())["files"]
    diff = [k for k in out if b.get(k) != out[k]] + [k for k in b if k not in out]
    print("CHANGED:" if diff else "inputs unchanged", diff)
print(len(out), "files; manifest", out["experiments/experiment_manifest.json"][:16])
