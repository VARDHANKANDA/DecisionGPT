"""Machine-readable artifact inventory of research/forecast_study_v2 (sha256, size, class, restricted flag) -> quality_gate/inventory_<tag>.json.
Usage: python quality_gate/tools/inventory.py <tag>     Read-only. Classes: frozen (listed in FREEZE.json), result (results/**), restricted (contains or reproduces M5 sales), doc, code, figure, table, other."""
import hashlib, json, sys, datetime
from pathlib import Path
HERE = Path(__file__).resolve().parents[2]
ROOT = HERE.parents[1]
tag = sys.argv[1]
frozen = set(json.loads((HERE / "FREEZE.json").read_text(encoding="utf-8"))["sha256"])
def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()
out = []
for p in sorted(HERE.rglob("*")):
    if not p.is_file() or "__pycache__" in p.parts or "quality_gate" in p.parts and p.name.startswith("inventory_"):
        continue
    rel = p.relative_to(ROOT).as_posix()
    rel_h = p.relative_to(HERE).as_posix()
    if rel_h in frozen or rel in frozen: cls = "frozen"
    elif p.suffix in (".npz", ".npy") and "results" in p.parts: cls = "restricted"
    elif "results" in p.parts: cls = "result"
    elif p.suffix == ".py": cls = "code"
    elif p.suffix in (".md", ".txt"): cls = "doc"
    elif p.suffix in (".svg", ".png", ".pdf"): cls = "figure"
    elif p.suffix in (".csv",) and ("tables" in p.parts or p.parent == HERE): cls = "table"
    else: cls = "other"
    out.append({"path": rel, "sha256": sha(p), "bytes": p.stat().st_size, "class": cls})
(HERE / "quality_gate" / f"inventory_{tag}.json").write_text(json.dumps({"created_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(), "n": len(out), "files": out}, indent=0), encoding="utf-8")
print(tag, len(out), "files;", sum(1 for x in out if x["class"] == "frozen"), "frozen;", sum(1 for x in out if x["class"] == "restricted"), "restricted")
