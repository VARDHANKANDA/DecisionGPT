"""Classical statistical baselines of forecast_study_v3 (ETS, ARIMA, Theta; Nixtla statsforecast, version pinned in requirements_stats.txt).

Runs in a SEPARATE virtual environment (STATS_PY) from the learned models; communicates through .npy files only. Reads results/prep/<store>/{y.npy,blocks.json}; writes
results/stat/<store>/<kind>_<model>_o<block start>.npy of shape [series, 28] (forecast for the 28 days of the block; clipped at 0).

Information sets (per 28-day block starting at day o; models see at most the last STAT_TRAIN_SPAN=730 days):
  fresh      : history through day o-1,   forecast horizons 1..28        (no fresher information is possible; favourable to the local models)
  matched<H> : history through day o-H,  forecast horizons H..H+27      (never fresher than the learned models' information for any target day, staler later in the block; unfavourable to the local models)
Models: AutoETS(season_length=7); AutoARIMA(season_length=7, approximation=True, max_p=2, max_q=2, max_P=1, max_Q=1, max_d=1, max_D=1, nmodels=40); AutoTheta(season_length=7).
A series whose fit raises, or whose forecast is not finite, receives the fallback forecast = mean of its last 91 observed days (counted in <kind>_<model>_o<o>.fallback.json).
No outcome after the history end is read: the history array is sliced before the model is called (unit-tested by perturbing the future).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import warnings
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

SPAN = 730
BLOCK = 28
CHUNK = 25
FALLBACK_DAYS = 91


def _model(name):
    from statsforecast.models import AutoARIMA, AutoETS, AutoTheta

    if name == "ets":
        return AutoETS(season_length=7)
    if name == "arima":
        return AutoARIMA(season_length=7, approximation=True, max_p=2, max_q=2, max_P=1, max_Q=1, max_d=1, max_D=1, nmodels=40)
    if name == "theta":
        return AutoTheta(season_length=7)
    raise ValueError(name)


def fit_forecast(hist: np.ndarray, model: str, h_max: int):
    """hist [n, L] float -> forecasts [n, h_max]; per-series fallback on failure. Returns (forecasts, n_fallback)."""
    warnings.filterwarnings("ignore")
    import pandas as pd
    from statsforecast import StatsForecast

    n, L = hist.shape
    fb = np.repeat(hist[:, -FALLBACK_DAYS:].mean(axis=1, keepdims=True), h_max, axis=1)

    def run(rows):
        df = pd.DataFrame({"unique_id": np.repeat(np.arange(len(rows)), L), "ds": np.tile(pd.date_range("2000-01-01", periods=L, freq="D"), len(rows)), "y": hist[rows].ravel().astype(float)})
        f = StatsForecast(models=[_model(model)], freq="D", n_jobs=1).forecast(df=df, h=h_max)
        f = f.reset_index() if "unique_id" not in f.columns else f
        f = f.sort_values(["unique_id", "ds"])
        return f.iloc[:, -1].to_numpy(dtype=float).reshape(len(rows), h_max)

    try:
        out = run(np.arange(n))
    except Exception:
        out = np.full((n, h_max), np.nan)
        for i in range(n):
            try:
                out[i] = run(np.array([i]))[0]
            except Exception:
                pass
    bad = ~np.isfinite(out).all(axis=1)
    out[bad] = fb[bad]
    return np.maximum(out, 0.0), int(bad.sum())


def _task(args):
    hist, model, h_max = args
    return fit_forecast(hist, model, h_max)


def history(y: np.ndarray, end: int) -> np.ndarray:
    """The ONLY access to y: days <= end (inclusive), at most SPAN days."""
    return y[:, max(0, end + 1 - SPAN): end + 1].astype(np.float64)


def block_forecast(y, o, kind, model, ex):
    if kind == "fresh":
        end, h0 = o - 1, 1
    else:
        H = int(kind.replace("matched", ""))
        end, h0 = o - H, H
    hist = history(y, end)
    h_max = h0 + BLOCK - 1
    parts = [(hist[i: i + CHUNK], model, h_max) for i in range(0, hist.shape[0], CHUNK)]
    res = list(ex.map(_task, parts))
    f = np.concatenate([r[0] for r in res], axis=0)[:, h0 - 1: h0 - 1 + BLOCK]
    return f.astype(np.float32), int(sum(r[1] for r in res))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--store", required=True)
    ap.add_argument("--stage", required=True, choices=["val", "test"])
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--models", nargs="*", default=["ets", "theta", "arima"])
    a = ap.parse_args()
    root = Path(a.root)
    y = np.load(root / "prep" / a.store / "y.npy")
    blocks = json.loads((root / "prep" / a.store / "blocks.json").read_text(encoding="utf-8"))
    starts = blocks["val"] if a.stage == "val" else blocks["test"]
    out = root / "stat" / a.store
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    with ProcessPoolExecutor(max_workers=a.workers) as ex:
        for model in a.models:
            for o in starts:
                for kind in ("fresh", "matched28", "matched7"):
                    f = out / f"{kind}_{model}_o{o}.npy"
                    if f.exists():
                        continue
                    fc, nfb = block_forecast(y, o, kind, model, ex)
                    tmp = f.with_suffix(".tmp.npy")
                    np.save(tmp, fc)
                    os.replace(tmp, f)
                    (out / f"{kind}_{model}_o{o}.fallback.json").write_text(json.dumps({"series": int(y.shape[0]), "fallback": nfb}), encoding="utf-8")
                    print(f"[{a.store} {a.stage}] {model} {kind} block {o} done fallback={nfb} ({round(time.time() - t0)}s)", flush=True)


if __name__ == "__main__":
    main()
