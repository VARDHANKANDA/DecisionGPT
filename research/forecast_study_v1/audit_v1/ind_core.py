"""Independent audit library. DOES NOT import research.forecast_study_v1.* or ml.* (only numpy / pandas / scipy / stdlib).

Everything here is re-implemented from the written specification (EXPERIMENT_PLAN.md, module docstrings, the manuscript) so that an error in the study's own
implementation cannot be inherited. Where a convention is defined only by the study's code (Croston/TSB initialisation, the OR2 cleaning rules, the M5 row order),
that is stated in AUDIT_LOG.md as a limit on independence.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[3]
STUDY = ROOT / "research" / "forecast_study_v1"
RES = STUDY / "results"
M5_RAW = ROOT / "data" / "external" / "m5_forecasting" / "raw"
OR2_CSV = ROOT / "data" / "external" / "uci_online_retail_ii" / "processed" / "online_retail_ii_raw_as_csv.csv"
NON_PRODUCT = {"ADJUST", "AMAZONFEE", "B", "BANK CHARGES", "C2", "CRUK", "D", "DOT", "GIFT", "M", "PADS", "POST", "S", "TEST001", "TEST002"}
CELLS = [f"fs1_{d}_H{h}" for d in ("m5_ca1", "m5_tx1", "or2_top100") for h in (28, 7)]
NAMES = ("naive", "seasonal_naive", "weekday_mean4", "weekday_mean8", "trailing_mean28", "trailing_median28", "croston_sba", "tsb")


def jload(p):
    return json.load(open(p, encoding="utf-8"))


def stored(cell):
    z = np.load(RES / cell / "predictions.npz")
    return {k: z[k] for k in z.files}


# ------------------------------------------------------------------------------------------------ raw data
def load_m5_series(store: str, ids: list[str]) -> np.ndarray:
    """Daily unit sales of the named M5 series, rows in the order of ``ids`` (read straight from the competition CSV)."""
    df = pd.read_csv(M5_RAW / "sales_train_evaluation.csv", usecols=lambda c: c == "id" or c == "store_id" or c.startswith("d_"))
    df = df[df["store_id"] == store].set_index("id")
    dcols = [f"d_{i}" for i in range(1, 1942)]
    return df.loc[ids, dcols].to_numpy(dtype=np.float64)


def load_or2_clean() -> pd.DataFrame:
    raw = pd.read_csv(OR2_CSV, dtype={"Invoice": str, "StockCode": str}, parse_dates=["InvoiceDate"])
    d = raw[~raw["Invoice"].str.startswith("C")]
    d = d[d["Quantity"] > 0]
    d = d[d["Price"] > 0]
    d = d[~d["StockCode"].isin(NON_PRODUCT)]
    d = d[~d.duplicated(["Invoice", "StockCode", "Quantity", "InvoiceDate", "Price", "Customer ID"])].copy()
    d["revenue"] = d["Quantity"] * d["Price"]
    d["day"] = d["InvoiceDate"].dt.normalize()
    return d


def or2_units_top100(d: pd.DataFrame):
    """100 SKUs with the largest revenue before the first validation block (day index T-168-84) and their daily units, calendar-complete."""
    full = pd.date_range(d["day"].min(), d["day"].max(), freq="D")
    T = len(full)
    cut = full[T - 168 - 84]
    top = d[d["day"] < cut].groupby("StockCode")["revenue"].sum().sort_values(ascending=False, kind="mergesort").head(100).index.tolist()
    u = d[d["StockCode"].isin(top)].groupby(["StockCode", "day"])["Quantity"].sum().unstack(fill_value=0).reindex(index=top, columns=full, fill_value=0)
    return u.to_numpy(dtype=np.float64), top, full


# ------------------------------------------------------------------------------------------------ metrics (own definitions)
def wape(y, p):
    den = np.abs(y).sum()
    return float(np.abs(p - y).sum() / den) if den > 0 else float("nan")


def rel_bias(y, p):
    den = np.abs(y).sum()
    return float((p - y).sum() / den) if den > 0 else float("nan")


def agg_wape(y, p, day):
    """Sum all series for each day first, then score the daily totals (pooled over days): sum_d |sum_s e| / sum_d sum_s y."""
    tot_e = pd.Series(p - y).groupby(day).sum()
    tot_y = pd.Series(y).groupby(day).sum()
    return float(np.abs(tot_e).sum() / np.abs(tot_y).sum())


def week_agg_wape(y, p, series, day, day0):
    """Intermediate aggregation: sum each series over its 7-day target blocks first, then score item-weeks."""
    w = (day - day0) // 7
    df = pd.DataFrame({"s": series, "w": w, "y": y, "p": p}).groupby(["s", "w"]).sum()
    return float(np.abs(df["p"] - df["y"]).sum() / np.abs(df["y"]).sum())


# ------------------------------------------------------------------------------------------------ baselines (own implementation, explicit slicing)
def _croston_sba(y, alpha=0.1):
    out = np.zeros(len(y))
    z, p, q, seen = 0.0, 1.0, 1.0, False
    for t, v in enumerate(y):
        if v > 0:
            if not seen:
                z, p, seen = v, q, True
            else:
                z += alpha * (v - z)
                p += alpha * (q - p)
            q = 1.0
        else:
            q += 1.0
        out[t] = (1 - alpha / 2) * z / max(p, 1e-12) if seen else 0.0
    return out


def _tsb(y, alpha=0.1, beta=0.1):
    out = np.zeros(len(y))
    z, prob, seen = 0.0, 0.0, False
    for t, v in enumerate(y):
        d = 1.0 if v > 0 else 0.0
        if d and not seen:
            z, prob, seen = v, 1.0 / (1.0 + t), True
        elif seen:
            if d:
                z += alpha * (v - z)
            prob += beta * (d - prob)
        out[t] = prob * z if seen else 0.0
    return out


def baseline_rows(Y: np.ndarray, series: np.ndarray, day: np.ndarray, cutoff_of_day, label: str) -> np.ndarray:
    """Forecast of baseline ``label`` for each (series, day) row, using ONLY Y[series, :cutoff+1] (explicit slice => no future access possible)."""
    S, T = Y.shape
    sba = np.vstack([_croston_sba(Y[s]) for s in range(S)]) if label == "croston_sba" else None
    tsb = np.vstack([_tsb(Y[s]) for s in range(S)]) if label == "tsb" else None
    out = np.empty(len(series))
    for i, (s, t) in enumerate(zip(series, day)):
        c = int(cutoff_of_day(int(t)))
        hist = Y[s, : c + 1]                     # nothing after the cutoff is reachable
        gap = int(t) - c
        k = math.ceil(gap / 7)
        src = [int(t) - 7 * (k + j) for j in range(8)]
        if label == "naive":
            v = hist[c]
        elif label == "seasonal_naive":
            v = hist[src[0]]
        elif label == "weekday_mean4":
            v = hist[src[:4]].mean()
        elif label == "weekday_mean8":
            v = hist[src[:8]].mean()
        elif label == "trailing_mean28":
            v = hist[c - 27: c + 1].mean()
        elif label == "trailing_median28":
            v = np.median(hist[c - 27: c + 1])
        elif label == "croston_sba":
            v = sba[s, c]
        else:
            v = tsb[s, c]
        out[i] = v
    return out


# ------------------------------------------------------------------------------------------------ cell matrices and inference
def cells_from_rows(series, day, abs_err, y, S, day0, block=7):
    W = int((day.max() - day0) // block) + 1
    idx = series * W + (day - day0) // block
    N = np.bincount(idx, weights=abs_err, minlength=S * W).reshape(S, W)
    D = np.bincount(idx, weights=np.abs(y), minlength=S * W).reshape(S, W)
    return N, D


def improvement(Na, Nb, rows, cols):
    a = Na[np.ix_(rows, cols)].sum()
    b = Nb[np.ix_(rows, cols)].sum()
    return float(1.0 - b / a)


def pigeonhole_ci(Na, Nb, B=4000, seed=987654):
    """Independent re-implementation of the two-way (rows x columns) resampling bootstrap, different seed."""
    rng = np.random.default_rng(seed)
    S, W = Na.shape
    draws = np.empty(B)
    for b in range(B):
        draws[b] = improvement(Na, Nb, rng.integers(0, S, S), rng.integers(0, W, W))
    pt = improvement(Na, Nb, np.arange(S), np.arange(W))
    p = float(min(1.0, 2 * min(np.mean(draws <= 0), np.mean(draws >= 0))))
    return pt, [float(np.percentile(draws, 2.5)), float(np.percentile(draws, 97.5))], p, float(draws.std(ddof=1))


def one_way_ci(Na, Nb, axis, B=4000, seed=24680):
    rng = np.random.default_rng(seed)
    S, W = Na.shape
    draws = np.empty(B)
    for b in range(B):
        if axis == 0:
            draws[b] = improvement(Na, Nb, rng.integers(0, S, S), np.arange(W))
        else:
            draws[b] = improvement(Na, Nb, np.arange(S), rng.integers(0, W, W))
    pt = improvement(Na, Nb, np.arange(S), np.arange(W))
    return pt, [float(np.percentile(draws, 2.5)), float(np.percentile(draws, 97.5))], float(draws.std(ddof=1))


def cgm_linearised(Na, Nb):
    """Delta-method variance of theta = 1 - sum(Nb)/sum(Na) with two-way cluster-robust (Cameron-Gelbach-Miller) clustering on series and week blocks."""
    A, Bm = Na.sum(), Nb.sum()
    theta = 1.0 - Bm / A
    r = Bm / A
    u = -(Nb - r * Na) / A                     # influence of each cell on theta (sums to ~0)
    vs = (u.sum(axis=1) ** 2).sum()
    vw = (u.sum(axis=0) ** 2).sum()
    vsw = (u ** 2).sum()
    v2 = vs + vw - vsw
    out = {"theta": float(theta), "var_series": float(vs), "var_week": float(vw), "var_cell": float(vsw), "var_twoway": float(v2)}
    for k, v in (("series", vs), ("week", vw), ("twoway", v2)):
        se = math.sqrt(max(v, 1e-30))
        z = theta / se
        out[f"se_{k}"] = se
        out[f"ci95_{k}"] = [theta - 1.959964 * se, theta + 1.959964 * se]
        out[f"p_{k}"] = float(math.erfc(abs(z) / math.sqrt(2)))
    return out


def holm(p: dict[str, float]) -> dict[str, float]:
    items = sorted(p.items(), key=lambda kv: kv[1])
    m, run, out = len(items), 0.0, {}
    for i, (k, v) in enumerate(items):
        run = max(run, min(1.0, (m - i) * v))
        out[k] = run
    return out


# ------------------------------------------------------------------------------------------------ rank metrics (own)
def auc_rank(y, s):
    r = stats.rankdata(s)
    n1 = int(y.sum())
    n0 = len(y) - n1
    return float((r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def avg_precision(y, s):
    """Step-wise average precision with one threshold per DISTINCT score value (tied scores enter together)."""
    o = np.argsort(-s, kind="mergesort")
    ys, ss = y[o], s[o]
    last = np.r_[np.flatnonzero(np.diff(ss) != 0), len(ss) - 1]     # last index of every tie group
    tp = np.cumsum(ys)[last]
    n = (last + 1).astype(float)
    prec, rec = tp / n, tp / ys.sum()
    return float(np.sum(np.diff(np.r_[0.0, rec]) * prec))
