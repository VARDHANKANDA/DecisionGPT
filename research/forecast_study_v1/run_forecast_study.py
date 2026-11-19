"""Run one (dataset, horizon) cell of the forecasting study.

    python -m research.forecast_study_v1.run_forecast_study m5_ca1 28            # full run
    python -m research.forecast_study_v1.run_forecast_study m5_ca1 28 --ablate price calendar history_stats static_ids
    python -m research.forecast_study_v1.run_forecast_study m5_ca1 28 --quick   # smoke run (2 series blocks, 1 family): NOT a result

Writes ``research/forecast_study_v1/results/fs1_<dataset>_H<H>/`` (config.json, metadata.json, results.json, predictions.npz, fits/*.npy). Nothing under
``experiments/`` is touched. Interrupted runs resume from ``fits/`` when the configuration hash matches.

Order of operations (fixed by EXPERIMENT_PLAN.md; the test blocks are not read before the selection is written to disk):
  1. load data, verify window order, build features, run the future-perturbation leakage check at four cutoffs;
  2. for each validation block fit every configuration and score it (pooled WAPE), score all baselines on the SAME rows;
  3. select, per family, the variant with the lowest mean validation WAPE; the primary learned model = the family with the lowest mean validation WAPE;
     the reference baseline = the baseline with the lowest mean validation WAPE (any information set) and the best matched-information baseline;
  4. write the selection; only then fit the chosen variants on each test block's training window and predict the block;
  5. save every prediction; compute pooled summaries.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from ml.benchmark import direct as hist_direct
from ml.benchmark import features as ft
from ml.benchmark import models as zoo
from research.forecast_study_v1 import baselines as bl
from research.forecast_study_v1 import metrics as mt
from research.forecast_study_v1 import protocol as pr

ROOT = Path(__file__).resolve().parents[2]
RESULTS = Path(__file__).resolve().parent / "results"
SEED = 42
THREADS = int(os.environ.get("STUDY_THREADS", "4"))
FAMILIES = {"ridge": ["alpha1", "alpha100"], "hist_gradient_boosting": ["depth4", "depth6"], "xgboost": ["depth4", "depth6"], "lightgbm": ["l2", "tweedie"], "catboost": ["depth6"]}
ABLATION_GROUPS = {
    "price": ("sell_price", "rel_price_91", "price_change_7", "days_since_price_change"),
    "calendar": ("dow", "dom", "month", "event", "snap"),
    "history_stats": ("roll_mean_7", "roll_mean_28", "roll_mean_84", "roll_std_28", "nonzero_share_28", "days_since_sale", "same_weekday_mean4"),
    "static_ids": ("dept_code", "cat_code", "item_code"),
}


def git(*a: str) -> str:
    try:
        return subprocess.check_output(["git", *a], cwd=ROOT, text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return "unknown"


def code_fingerprint() -> dict[str, str]:
    out = {}
    for p in sorted(Path(__file__).resolve().parent.glob("*.py")):
        out[p.name] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


def versions() -> dict[str, str]:
    import catboost, lightgbm, pandas, scipy, sklearn, xgboost  # noqa: E401

    return {"python": sys.version.split()[0], "platform": platform.platform(), "numpy": np.__version__, "pandas": pandas.__version__, "scipy": scipy.__version__,
            "scikit-learn": sklearn.__version__, "xgboost": xgboost.__version__, "lightgbm": lightgbm.__version__, "catboost": catboost.__version__, "threads": THREADS}


def set_threads(pred, n: int) -> None:
    m = pred.model
    try:
        if pred.family in ("xgboost", "lightgbm"):
            m.set_params(n_jobs=n)
        elif pred.family == "catboost":
            m.set_params(thread_count=n)
    except Exception:
        pass


def rows(F, valid, y, lo, hi):
    return hist_direct.rows(F, valid, y, lo, hi)


def leakage_checks(d: pr.Dataset, H: int, cutoffs: list[int]) -> list[dict]:
    out = []
    for e in cutoffs:
        ok = ft.assert_no_future_leakage(d.y, d.price, d.cal, d.static, H, e)
        out.append({"cutoff_day": int(e), "H": H, "features_unchanged_when_future_is_perturbed": bool(ok)})
        if not ok:
            raise AssertionError(f"future information reached the history features at cutoff {e} (H={H})")
    return out


def baseline_table(d: pr.Dataset, H: int, starts: list[int]) -> dict[str, np.ndarray]:
    m = bl.matched(d.y, H)
    f = bl.fresh(d.y, H, starts, pr.BLOCK)
    return {**{f"matched__{k}": v for k, v in m.items()}, **{f"fresh__{k}": v for k, v in f.items()}}


def run(dataset: str, H: int, quick: bool = False, ablate: list[str] | None = None, log=print) -> Path:
    t0 = time.time()
    d = pr.load(dataset)
    T = d.T
    win = pr.windows(T)
    ordered = pr.assert_windows_ordered(T)
    F_full, names_full, valid = pr.build_features(d, H)
    starts = win["val"] + win["test"]
    base = baseline_table(d, H, starts)
    families = {k: (v[:1] if quick else v) for k, v in FAMILIES.items()}
    if quick:
        families = {"ridge": ["alpha1"]}
        win = {"val": win["val"][-1:], "test": win["test"][:1]}
    seg = pr.segments(d.y, pr.windows(T)["val"][0])

    tag = f"fs1_{dataset}_H{H}" + ("_quick" if quick else "")
    drop_cols: tuple[str, ...] = ()
    if ablate:
        drop_cols = tuple(c for g in ablate for c in ABLATION_GROUPS[g])
        tag += "_ablate_" + "-".join(ablate)
    out = RESULTS / tag
    (out / "fits").mkdir(parents=True, exist_ok=True)
    keep = [i for i, n in enumerate(names_full) if n not in drop_cols]
    names = [names_full[i] for i in keep]
    F = F_full[:, :, keep]
    config = {"study": "forecast_study_v1", "dataset": dataset, "H": H, "block": pr.BLOCK, "n_test_blocks": pr.N_TEST, "n_val_blocks": pr.N_VAL, "train_span": pr.TRAIN_SPAN, "seed": SEED,
              "families": families, "features": names, "dropped_features": list(drop_cols), "quick": quick, "windows": win,
              "baselines": sorted(base), "min_history": pr.MIN_HISTORY, "segment_history_days": pr.SEGMENT_HISTORY}
    chash = hashlib.sha256(json.dumps(config, sort_keys=True, default=str).encode()).hexdigest()[:12]
    cfg_path = out / "config.json"
    if cfg_path.exists() and json.load(open(cfg_path, encoding="utf-8")).get("config_hash") != chash:
        raise RuntimeError(f"{out} exists with a different configuration; refusing to mix runs")
    cfg_path.write_text(json.dumps({**config, "config_hash": chash}, indent=2, default=str), encoding="utf-8")
    log(f"[{tag}] T={T} series={d.y.shape[0]} features={len(names)} threads={THREADS}")

    leak = [] if (quick or ablate) else leakage_checks(d, H, [win["val"][0] - 1, win["val"][-1] - 1, win["test"][0] - 1, win["test"][-1] - 1])
    runtimes: dict[str, float] = {}

    def fit_predict(fam: str, var: str, o: int, stage: str):
        f = out / "fits" / f"{stage}_{o}_{fam}-{var}.npy"
        if f.exists():
            return np.load(f)
        Xtr, ytr, _, _ = rows(F, valid, d.y, max(0, o - pr.TRAIN_SPAN), o - 1)
        Xte, _, _, _ = rows(F, valid, d.y, o, o + pr.BLOCK - 1)
        t1 = time.time()
        p = zoo.build(fam, var, names, SEED)
        set_threads(p, THREADS)
        p.fit(Xtr, ytr)
        pred = p.predict(Xte).astype(np.float32)
        runtimes[f"{stage}_{o}_{fam}:{var}"] = round(time.time() - t1, 1)
        np.save(f, pred)
        return pred

    def block_rows(o: int):
        _, y, s, t = rows(F, valid, d.y, o, o + pr.BLOCK - 1)
        b = {k: v[s, t] for k, v in base.items()}
        ok = np.ones(len(y), dtype=bool)
        for v in b.values():
            ok &= np.isfinite(v)
        return y, s, t, b, ok

    # ---- 1) validation blocks: all configurations and all baselines on identical rows
    val_cfg: dict[str, list[float | None]] = {}
    val_base: dict[str, list[float | None]] = {}
    val_store: dict[str, dict[int, np.ndarray]] = {}
    val_truth = {}
    for o in ([] if ablate else win["val"]):
        y, s, t, b, ok = block_rows(o)
        val_truth[o] = (y[ok], s[ok], t[ok], {k: v[ok] for k, v in b.items()})
        for fam, variants in families.items():
            for var in variants:
                cid = f"{fam}:{var}"
                p = fit_predict(fam, var, o, "val")
                val_store.setdefault(cid, {})[o] = p[ok]
                val_cfg.setdefault(cid, []).append(mt.wape(y[ok], p[ok]))
        for k, v in val_truth[o][3].items():
            val_base.setdefault(k, []).append(mt.wape(y[ok], v))
        log(f"[{tag}] validation block {o} done ({round(time.time() - t0)}s)")

    def mean_wape(xs):
        xs = [x for x in xs if x is not None]
        return float(np.mean(xs)) if xs else None

    if ablate:
        main_sel = json.load(open(RESULTS / f"fs1_{dataset}_H{H}" / "selection.json", encoding="utf-8"))
        chosen, primary_family = main_sel["chosen_variant_per_family"], main_sel["primary_learned_family"]
        best_base_any, best_base_matched = main_sel["reference_baseline_any_information"], main_sel["reference_baseline_matched_information"]
        selection = {"chosen_variant_per_family": chosen, "primary_learned_family": primary_family, "primary_learned_config": chosen[primary_family],
                     "reference_baseline_any_information": best_base_any, "reference_baseline_matched_information": best_base_matched,
                     "note": "ablation: variants, family and reference baselines taken unchanged from the main run's selection (no re-tuning, no validation fits)"}
    else:
        chosen = {}
        for fam, variants in families.items():
            chosen[fam] = min((f"{fam}:{v}" for v in variants), key=lambda c: mean_wape(val_cfg[c]))
        primary_family = min(chosen, key=lambda f: mean_wape(val_cfg[chosen[f]]))
        best_base_any = min(val_base, key=lambda k: mean_wape(val_base[k]))
        best_base_matched = min((k for k in val_base if k.startswith("matched__")), key=lambda k: mean_wape(val_base[k]))
    if not ablate:
      selection = {"chosen_variant_per_family": chosen, "primary_learned_family": primary_family, "primary_learned_config": chosen[primary_family],
                 "reference_baseline_any_information": best_base_any, "reference_baseline_matched_information": best_base_matched,
                 "rule": "lowest mean over the validation blocks of the pooled WAPE; baselines scored on the same rows",
                 "validation_wape": {"configs": {c: {"by_block": v, "mean": mean_wape(v)} for c, v in val_cfg.items()},
                                     "baselines": {c: {"by_block": v, "mean": mean_wape(v)} for c, v in val_base.items()}}}
    (out / "selection.json").write_text(json.dumps(selection, indent=2), encoding="utf-8")
    log(f"[{tag}] selection written: primary={chosen[primary_family]} reference={best_base_any}")

    # ---- 2) test blocks (only after the selection is on disk)
    test_arrays: dict[str, list[np.ndarray]] = {}
    fam_to_fit = {primary_family: chosen[primary_family]} if ablate else chosen
    for o in win["test"]:
        y, s, t, b, ok = block_rows(o)
        test_arrays.setdefault("y", []).append(y[ok])
        test_arrays.setdefault("series", []).append(s[ok].astype(np.int32))
        test_arrays.setdefault("day", []).append(t[ok].astype(np.int32))
        test_arrays.setdefault("block", []).append(np.full(int(ok.sum()), o, dtype=np.int32))
        for fam, cid in fam_to_fit.items():
            p = fit_predict(*cid.split(":"), o, "test")
            test_arrays.setdefault(f"pred__{cid}", []).append(p[ok])
        for k, v in b.items():
            test_arrays.setdefault(f"base__{k}", []).append(v[ok].astype(np.float32))
        log(f"[{tag}] test block {o} done ({round(time.time() - t0)}s)")
    cat = {k: np.concatenate(v) for k, v in test_arrays.items()}
    arrays = {k.replace(":", "__"): v for k, v in cat.items()}
    if not ablate:
        arrays.update({f"val_pred__{c.replace(':', '__')}": np.concatenate([val_store[c][o] for o in win["val"]]) for c in val_store})
        arrays.update(val_y=np.concatenate([val_truth[o][0] for o in win["val"]]), val_series=np.concatenate([val_truth[o][1] for o in win["val"]]).astype(np.int32),
                      val_day=np.concatenate([val_truth[o][2] for o in win["val"]]).astype(np.int32),
                      **{f"val_base__{k}": np.concatenate([val_truth[o][3][k] for o in win["val"]]).astype(np.float32) for k in val_truth[win["val"][0]][3]})
    np.savez_compressed(out / "predictions.npz", **arrays)

    scale = mt.series_scale(d.y[:, : win["test"][0]].astype(float))
    summary = {}
    for k in cat:
        if k.startswith(("pred__", "base__")):
            summary[k] = mt.summary(cat["y"], cat[k], cat["series"], cat["day"], scale)
            summary[k]["wape_by_block"] = [mt.wape(cat["y"][cat["block"] == o], cat[k][cat["block"] == o]) for o in win["test"]]
    results = {"tag": tag, "n_test_points": int(len(cat["y"])), "windows": ordered, "segments": {k: v for k, v in seg.items() if k in ("counts", "volume_cuts", "history_days")},
               "leakage_checks": leak, "selection": {k: v for k, v in selection.items() if k != "validation_wape"}, "test_summary": summary,
               "rmsse_scale_from_history_before_day": int(win["test"][0]), "runtimes_seconds": runtimes, "total_runtime_seconds": round(time.time() - t0)}
    (out / "results.json").write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
    meta = {"created_utc": datetime.now(timezone.utc).isoformat(), "git_revision": git("rev-parse", "--short", "HEAD"), "working_tree_modified_paths": len([ln for ln in git("status", "--porcelain").splitlines() if ln.strip()]),
            "code_sha256": code_fingerprint(), "versions": versions(), "dataset": {k: v for k, v in d.info.items() if k not in ("series_ids",)}, "series_ids": d.series_ids,
            "config_hash": chash, "seed": SEED, "runtime_seconds_total": round(time.time() - t0), "quick": quick}
    (out / "metadata.json").write_text(json.dumps(meta, indent=2, default=str), encoding="utf-8")
    (out / "segments.json").write_text(json.dumps(seg), encoding="utf-8")
    log(f"[{tag}] done in {round(time.time() - t0)}s -> {out}")
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("dataset", choices=pr.DATASETS)
    ap.add_argument("horizon", type=int, choices=pr.HORIZONS)
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--ablate", nargs="*", choices=list(ABLATION_GROUPS))
    a = ap.parse_args()
    run(a.dataset, a.horizon, quick=a.quick, ablate=a.ablate, log=lambda s: print(s, flush=True))
