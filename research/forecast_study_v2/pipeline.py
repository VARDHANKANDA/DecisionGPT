"""Per (dataset, window, H) pipeline of forecast_study_v2.

    python -m research.forecast_study_v2.pipeline --dataset m5_ca1 --window W2 --H 28 --stage validation
    python -m research.forecast_study_v2.pipeline --dataset m5_ca1 --window W2 --H 28 --stage test [--seeds 43 44]

Stage 'validation' reads only validation blocks and writes selection.json (+ leakage checks). Stage 'test' REFUSES to start unless the freeze record verifies and selection.json exists; it
fits only the prespecified test configurations (selected-by-item-day-WAPE model, selected-by-subset-day-WAPE model, and the original reference model) and writes predictions and results.
No test block is read in stage 'validation'. Interrupted runs resume from fits/ when the configuration hash is unchanged.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from ml.benchmark import direct as hist_direct
from ml.benchmark import features as ft

from . import baselines as bl
from . import data as dat
from . import metrics as mt
from . import models as md
from . import windows as win
from .common import RESULTS, SEED, atomic_save_npy, atomic_save_npz, atomic_write_json, code_fingerprint, sha256_file, versions

_STATE_CACHE: dict = {}


def cell_dir(window: str, key: str, H: int) -> Path:
    return RESULTS / window / f"{key}_H{H}"


def rows(F, valid, y, lo, hi):
    return hist_direct.rows(F, valid, y, lo, hi)


class Prepared:
    def __init__(self, key: str, window: str, H: int, log=print):
        t0 = time.time()
        self.key, self.window, self.H = key, window, H
        self.d = dat.load(key, window)
        T = self.d.T
        self.spec = win.check_ordered(T, H)
        self.blocks = win.blocks(T, H)
        assert T == win.truncated_length(self.d.T_full, window), "series was not truncated to the window length"
        self.F, self.names, self.valid = self._features()
        ck = (key, window)
        if ck not in _STATE_CACHE:
            _STATE_CACHE.clear()
            _STATE_CACHE[ck] = bl.states(self.d.y)
        self.state = _STATE_CACHE[ck]
        starts = self.blocks["val"] + self.blocks["test"]
        self.base = bl.table(self.d.y, H, starts, self.state)
        self.seg = dat.segments(self.d.y, self.blocks["val"][0])
        self.prep_seconds = round(time.time() - t0, 1)
        log(f"[{key} {window} H={H}] T'={T} series={self.d.y.shape[0]} features={len(self.names)} baselines={len(self.base)} prepared in {self.prep_seconds}s")

    def _features(self):
        d, H = self.d, self.H
        F, names = ft.build_direct_features(d.y, d.price, d.cal, d.static, H)
        valid = ft.valid_mask(d.y, d.price, H, win.MIN_HISTORY)
        if d.drop_features:
            keep = [i for i, n in enumerate(names) if n not in d.drop_features]
            F, names = F[:, :, keep], [names[i] for i in keep]
            valid = np.ones_like(valid, dtype=bool)
            valid[:, : H + win.MIN_HISTORY] = False
        return F, names, valid

    def ok_mask(self, s, t) -> np.ndarray:
        ok = np.ones(len(s), dtype=bool)
        for v in self.base.values():
            ok &= np.isfinite(v[s, t])
        return ok

    def block_rows(self, o: int):
        X, y, s, t = rows(self.F, self.valid, self.d.y, o, o + win.BLOCK - 1)
        ok = self.ok_mask(s, t)
        return X, y, s, t, ok


def _config(P: Prepared, extra: dict | None = None) -> dict:
    cfg = {"study": "forecast_study_v2", "dataset": P.key, "window": P.window, "H": P.H, "T_trunc": P.d.T, "blocks": P.blocks, "train_span": win.TRAIN_SPAN, "min_history": win.MIN_HISTORY,
           "candidates": {k: {"kind": v["kind"], "params": v["params"], "target": v["target"]} for k, v in md.CANDIDATES.items()}, "reference_model": md.REFERENCE_MODEL, "features": P.names,
           "lgbm_base": md.LGBM_BASE, "xgb_base": md.XGB_BASE, "baselines": sorted(P.base), "seed": SEED, "series_ids_sha256": hashlib.sha256("|".join(P.d.series_ids).encode()).hexdigest()}
    if extra:
        cfg.update(extra)
    cfg["config_hash"] = hashlib.sha256(json.dumps(cfg, sort_keys=True, default=str).encode()).hexdigest()[:16]
    return cfg


def _fit_predict(P: Prepared, out: Path, stage: str, o: int, cid: str, seed: int, runtimes: dict) -> np.ndarray:
    f = out / "fits" / f"{stage}_{o}_{cid}_s{seed}.npy"
    if f.exists():
        return np.load(f)
    Xtr, ytr, _, _ = rows(P.F, P.valid, P.d.y, max(0, o - win.TRAIN_SPAN), o - 1)
    Xte, _, _, _ = rows(P.F, P.valid, P.d.y, o, o + win.BLOCK - 1)
    t0 = time.time()
    m = md.Model(cid, P.names, seed)
    m.fit(Xtr, ytr)
    pred = m.predict(Xte)
    runtimes[f"{stage}_{o}_{cid}_s{seed}"] = round(time.time() - t0, 1)
    atomic_save_npy(f, pred)
    return pred


def leakage_checks(P: Prepared) -> list[dict]:
    """Perturb everything after four cutoffs (all inside the validation span or earlier) and require identical history features; also confirm nothing at or after T' exists."""
    out = []
    for e in (P.blocks["val"][0] - 1, P.blocks["val"][-1] - 1, P.blocks["test"][0] - 1):
        ok = ft.assert_no_future_leakage(P.d.y, P.d.price, P.d.cal, P.d.static, P.H, e)
        out.append({"cutoff_day": int(e), "H": P.H, "history_features_unchanged_when_future_is_perturbed": bool(ok)})
        if not ok:
            raise AssertionError(f"future information reached the features at cutoff {e}")
    out.append({"series_length_equals_window_length": bool(P.d.T == P.spec["T_trunc"]), "first_unused_day": int(P.spec["first_unused_day"])})
    return out


def stage_validation(P: Prepared, log=print) -> dict:
    out = cell_dir(P.window, P.key, P.H)
    (out / "fits").mkdir(parents=True, exist_ok=True)
    cfg = _config(P)
    cpath = out / "config.json"
    if cpath.exists() and json.loads(cpath.read_text(encoding="utf-8")).get("config_hash") != cfg["config_hash"]:
        raise RuntimeError(f"{out} exists with a different configuration; refusing to mix runs")
    atomic_write_json(cpath, cfg)
    leak = leakage_checks(P)
    runtimes: dict[str, float] = {}
    val_item = {c: [] for c in md.CANDIDATES}
    val_agg = {c: [] for c in md.CANDIDATES}
    base_item = {b: [] for b in P.base}
    base_agg = {b: [] for b in P.base}
    t0 = time.time()
    for o in P.blocks["val"]:
        X, y, s, t, ok = P.block_rows(o)
        for cid in md.CANDIDATES:
            p = _fit_predict(P, out, "val", o, cid, SEED, runtimes)
            val_item[cid].append(mt.wape(y[ok], p[ok]))
            val_agg[cid].append(mt.subset_day_wape(y[ok], p[ok], t[ok]))
        for b, arr in P.base.items():
            v = arr[s, t].astype(float)
            base_item[b].append(mt.wape(y[ok], v[ok]))
            base_agg[b].append(mt.subset_day_wape(y[ok], v[ok], t[ok]))
        log(f"[{P.key} {P.window} H={P.H}] validation block {o} done ({round(time.time() - t0)}s)")

    def mean(xs):
        xs = [x for x in xs if x is not None]
        return float(np.mean(xs)) if xs else None

    def best(scores: dict, names=None):
        names = sorted(names if names is not None else scores)
        return min(names, key=lambda k: (mean(scores[k]) if mean(scores[k]) is not None else float("inf"), k))

    matched = [b for b in P.base if b.startswith("matched__")]
    sel = {
        "rule": "lowest mean over the three validation blocks of the endpoint being evaluated; ties broken by name",
        "model_item_day": best(val_item), "model_subset_day": best(val_agg), "reference_model": md.REFERENCE_MODEL,
        "baseline_item_day_matched": best(base_item, matched), "baseline_item_day_any": best(base_item),
        "baseline_subset_day_matched": best(base_agg, matched), "baseline_subset_day_any": best(base_agg),
        "validation": {"models_item_day_wape": {c: {"by_block": v, "mean": mean(v)} for c, v in val_item.items()}, "models_subset_day_wape": {c: {"by_block": v, "mean": mean(v)} for c, v in val_agg.items()},
                       "baselines_item_day_wape": {c: {"by_block": v, "mean": mean(v)} for c, v in base_item.items()}, "baselines_subset_day_wape": {c: {"by_block": v, "mean": mean(v)} for c, v in base_agg.items()}},
        "leakage_checks": leak, "segments_counts": {k: {v: int((np.array(P.seg[k]) == v).sum()) for v in sorted(set(P.seg[k]))} for k in ("frequency", "volume")},
        "created_utc": datetime.now(timezone.utc).isoformat(), "config_hash": cfg["config_hash"], "runtimes_seconds": runtimes}
    atomic_write_json(out / "selection.json", sel)
    log(f"[{P.key} {P.window} H={P.H}] selection written: item-day model={sel['model_item_day']} subset-day model={sel['model_subset_day']} baseline(item,matched)={sel['baseline_item_day_matched']}")
    return sel


def stage_test(P: Prepared, seeds: list[int], log=print) -> Path:
    from . import freeze

    freeze.verify()                                                   # refuses to continue if the frozen protocol or code changed
    out = cell_dir(P.window, P.key, P.H)
    sel = json.loads((out / "selection.json").read_text(encoding="utf-8"))
    cfg = _config(P)
    if sel["config_hash"] != cfg["config_hash"]:
        raise RuntimeError("selection.json was produced with a different configuration")
    sel_t = (out / "selection.json").stat().st_mtime
    runtimes: dict[str, float] = {}
    configs = list(dict.fromkeys([sel["model_item_day"], sel["model_subset_day"], sel["reference_model"]]))
    cols: dict[str, list] = {"y": [], "series": [], "day": [], "block": []}
    preds: dict[str, list] = {f"pred__{c}": [] for c in configs}
    seed_preds: dict[str, list] = {f"seed{sd}__{sel['model_item_day']}": [] for sd in seeds}
    base_cols: dict[str, list] = {f"base__{b}": [] for b in P.base}
    t0 = time.time()
    for o in P.blocks["test"]:
        X, y, s, t, ok = P.block_rows(o)
        cols["y"].append(y[ok]); cols["series"].append(s[ok].astype(np.int32)); cols["day"].append(t[ok].astype(np.int32)); cols["block"].append(np.full(int(ok.sum()), o, dtype=np.int32))
        for c in configs:
            preds[f"pred__{c}"].append(_fit_predict(P, out, "test", o, c, SEED, runtimes)[ok])
        for sd in seeds:
            seed_preds[f"seed{sd}__{sel['model_item_day']}"].append(_fit_predict(P, out, "test", o, sel["model_item_day"], sd, runtimes)[ok])
        for b, arr in P.base.items():
            base_cols[f"base__{b}"].append(arr[s, t][ok].astype(np.float32))
        log(f"[{P.key} {P.window} H={P.H}] test block {o} done ({round(time.time() - t0)}s)")
    cat = {k: np.concatenate(v) for d_ in (cols, preds, seed_preds, base_cols) for k, v in d_.items() if v}
    first_fit = min((f.stat().st_mtime for f in (out / "fits").glob("test_*.npy")), default=None)
    day0 = P.blocks["test"][0]
    summary = {}
    for k, v in cat.items():
        if k.startswith(("pred__", "base__", "seed")):
            summary[k] = mt.ladder(cat["y"], v, cat["series"], cat["day"], day0)
            summary[k]["item_day_wape_by_block"] = [mt.wape(cat["y"][cat["block"] == o], v[cat["block"] == o]) for o in P.blocks["test"]]
    results = {"dataset": P.key, "window": P.window, "H": P.H, "n_rows": int(len(cat["y"])), "n_series": int(P.d.y.shape[0]), "blocks": P.blocks, "selection": {k: sel[k] for k in sel if k not in ("validation", "leakage_checks", "runtimes_seconds")},
               "summary": summary, "test_fits_after_selection": bool(first_fit is None or first_fit >= sel_t), "segments": P.seg, "total_test_seconds": round(time.time() - t0)}
    atomic_save_npz(out / "predictions.npz", **cat)
    atomic_write_json(out / "results.json", results)
    meta = {"created_utc": datetime.now(timezone.utc).isoformat(), "versions": versions(), "code_sha256": code_fingerprint(), "dataset_info": P.d.info, "series_ids": P.d.series_ids, "config_hash": cfg["config_hash"],
            "freeze_sha256": (sha256_file(Path(__file__).parent / "FREEZE.json") if (Path(__file__).parent / "FREEZE.json").exists() else None)}
    atomic_write_json(out / "metadata.json", meta)
    log(f"[{P.key} {P.window} H={P.H}] test done -> {out}")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", required=True, choices=dat.KEYS)
    ap.add_argument("--window", required=True, choices=list(win.OFFSETS))
    ap.add_argument("--H", type=int, nargs="+", required=True, choices=list(win.HORIZONS))
    ap.add_argument("--stage", required=True, choices=["validation", "test", "both"])
    ap.add_argument("--seeds", type=int, nargs="*", default=[])
    a = ap.parse_args()
    log = lambda s: print(s, flush=True)  # noqa: E731
    for H in a.H:
        try:
            P = Prepared(a.dataset, a.window, H, log)
        except win.Infeasible as e:
            log(f"INFEASIBLE {a.dataset} {a.window} H={H}: {e}")
            continue
        if a.stage in ("validation", "both"):
            stage_validation(P, log)
        if a.stage in ("test", "both"):
            stage_test(P, a.seeds, log)


if __name__ == "__main__":
    main()
