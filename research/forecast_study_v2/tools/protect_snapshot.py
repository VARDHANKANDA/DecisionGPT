"""Timestamped hash inventory of the protected project artifacts (read-only). Usage: python protect_snapshot.py <tag>
Covers: research/forecast_study_v1/** (incl. audit_v1), experiments/**, raw data CSV/ZIP files under data/external, and the historical benchmark code ml/benchmark/*.py."""
import datetime
import hashlib
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[3]
OUT = pathlib.Path(__file__).resolve().parents[1] / "protection"
SKIP = {"__pycache__"}


def sha(p, buf=1 << 20):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        while chunk := f.read(buf):
            h.update(chunk)
    return h.hexdigest()


def files():
    for base in ("research/forecast_study_v1", "experiments", "ml/benchmark"):
        for p in sorted((ROOT / base).rglob("*")):
            if p.is_file() and not (SKIP & set(p.parts)) and p.suffix != ".pyc":
                yield p
    for base in ("data/external/m5_forecasting", "data/external/uci_online_retail_ii"):
        for p in sorted((ROOT / base).rglob("*")):
            if p.is_file():
                yield p


def main(tag):
    snap = {"created_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(), "files": {}}
    for p in files():
        snap["files"][p.relative_to(ROOT).as_posix()] = {"sha256": sha(p), "bytes": p.stat().st_size}
    OUT.mkdir(exist_ok=True)
    (OUT / f"protected_{tag}.json").write_text(json.dumps(snap, indent=0), encoding="utf-8")
    print(tag, len(snap["files"]), "files,", sum(v["bytes"] for v in snap["files"].values()) // 2**20, "MiB hashed")


if __name__ == "__main__":
    main(sys.argv[1])
