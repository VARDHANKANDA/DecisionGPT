"""Orchestration of forecast_study_v3 (pinned environment). The v2 pipeline modules are used UNCHANGED (patched in memory by data3.install(); no v2 file is modified).

    python -m research.forecast_study_v3_fresh_stats.run_v3 prep        --stores m5_ca2 m5_tx2 m5_wi2
    (STATS_PY stat_forecasts.py --stage val  ...)   # statistical baselines for the validation blocks
    python -m research.forecast_study_v3_fresh_stats.run_v3 validation  --stores ...
    (STATS_PY stat_forecasts.py --stage test ...)   # only after selection.json exists for the store
    python -m research.forecast_study_v3_fresh_stats.run_v3 test        --stores ... --seeds 43 44
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from research.forecast_study_v2 import pipeline as pl
from research.forecast_study_v2 import windows as win

from . import data3
from . import v3common as C

data3.install()
pl.RESULTS = C.RESULTS


def _atomic_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=1, default=str), encoding="utf-8")


def prep(store_key: str):
    d = data3.load(store_key, C.WINDOW)
    T = d.T
    out = C.RESULTS / "prep" / store_key
    out.mkdir(parents=True, exist_ok=True)
    np.save(out / "y.npy", d.y.astype(np.float32))
    b = {H: win.blocks(T, H) for H in (28, 7)}
    assert b[28] == b[7]
    _atomic_json(out / "blocks.json", {"T_trunc": T, "val": b[28]["val"], "test": b[28]["test"], "series_ids_sha256": hashlib.sha256("|".join(d.series_ids).encode()).hexdigest(), "dataset_info": d.info})
    print(f"prep {store_key}: T'={T} series={d.y.shape[0]} val={b[28]['val']} test={b[28]['test']} eligible={d.info.get('eligible_series_in_store')} retired_excluded={d.info.get('excluded_retired_benchmark_series_in_store')}", flush=True)


def stat_arrays(store_key: str, H: int, S: int, T: int) -> dict[str, np.ndarray]:
    root = C.RESULTS / "stat" / store_key
    arrs = {}
    for model in C.STAT_MODELS:
        for kind, name in ((f"matched{H}", f"matched__{model}"), ("fresh", f"fresh__{model}")):
            a = np.full((S, T), np.nan)
            for f in root.glob(f"{kind}_{model}_o*.npy"):
                if f.name.endswith(".tmp.npy"):
                    continue
                o = int(f.stem.split("_o")[-1])
                a[:, o: o + 28] = np.load(f)
            arrs[name] = a
    return arrs


def _prepared(store_key: str, H: int):
    P = pl.Prepared(store_key, C.WINDOW, H, lambda s: print(s, flush=True))
    P.base.update(stat_arrays(store_key, H, P.d.y.shape[0], P.d.T))
    return P


def run(stage: str, stores: list[str], seeds: list[int]):
    for sk in stores:
        for H in C.HORIZONS:
            P = _prepared(sk, H)
            if stage == "validation":
                pl.stage_validation(P, lambda s: print(s, flush=True))
            else:
                missing = [n for n in P.base if n.startswith(("matched__", "fresh__")) and any(m in n for m in C.STAT_MODELS) and not np.isfinite(P.base[n][:, P.blocks["test"][0]: P.blocks["test"][0] + 28]).any()]
                if missing:
                    raise RuntimeError(f"statistical baselines for the test blocks are missing: {missing}")
                pl.stage_test(P, seeds, lambda s: print(s, flush=True))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["prep", "validation", "test"])
    ap.add_argument("--stores", nargs="+", default=list(C.STORES))
    ap.add_argument("--seeds", type=int, nargs="*", default=[])
    a = ap.parse_args()
    if a.action == "prep":
        for s in a.stores:
            prep(s)
    else:
        run(a.action, a.stores, a.seeds)


if __name__ == "__main__":
    main()
