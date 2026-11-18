"""Price-response identification diagnostics (Digital Twin investigation).

Two separate questions, never conflated:
  1. *Is price sensitivity identifiable in the data?*  Within-item fixed-effects log-log regression with item-clustered standard errors.
     This is an ASSOCIATION; prices are not randomised and promotions / availability co-move with them.
  2. *What does a fitted forecasting model do when the scenario price changes?*  A counterfactual that recomputes every price-derived
     feature for the scored window and compares predictions. This is a property of the model, not evidence about demand.
Nothing here imposes an elasticity or a sign.
"""
from __future__ import annotations

from typing import Any

import numpy as np


def within_item_elasticity(y: np.ndarray, price: np.ndarray, dow: np.ndarray, month_idx: np.ndarray, *, t_lo: int, t_hi: int,
                           positive_only: bool = False, controls: np.ndarray | None = None) -> dict[str, Any]:
    """OLS of log(1+units) [or log(units) on positive days] on log(price) with item fixed effects (within transform), day-of-week and
    month dummies, optional extra controls; cluster-robust (item) SE. Returns the price coefficient and diagnostics."""
    n, T = y.shape
    sl = slice(t_lo, t_hi + 1)
    P = price[:, sl]
    Y = y[:, sl]
    ok = ~np.isnan(P) & (P > 0)
    if positive_only:
        ok &= Y > 0
        resp = np.log(np.where(Y > 0, Y, 1.0))
    else:
        resp = np.log1p(Y)
    lp = np.log(np.where(ok, P, 1.0))
    item = np.repeat(np.arange(n), P.shape[1]).reshape(n, -1)
    d = np.broadcast_to(dow[sl], P.shape)
    m = np.broadcast_to(month_idx[sl], P.shape)
    cols = [lp]
    names = ["log_price"]
    for k in range(1, 7):
        cols.append((d == k).astype(float)); names.append(f"dow_{k}")
    for k in np.unique(m)[1:]:
        cols.append((m == k).astype(float)); names.append(f"month_{int(k)}")
    if controls is not None:
        for j in range(controls.shape[0]):
            cols.append(controls[j][sl]); names.append(f"control_{j}")
    X = np.stack(cols, axis=-1)  # [n, t, k]
    flat_ok = ok.reshape(-1)
    Xf = X.reshape(-1, X.shape[-1])[flat_ok]
    yf = resp.reshape(-1)[flat_ok]
    g = item.reshape(-1)[flat_ok]
    # within transformation (item fixed effects)
    ids, inv = np.unique(g, return_inverse=True)
    cnt = np.bincount(inv).astype(float)
    Xm = np.zeros((len(ids), Xf.shape[1]))
    np.add.at(Xm, inv, Xf)
    Xm /= cnt[:, None]
    ym = np.bincount(inv, weights=yf) / cnt
    Xw = Xf - Xm[inv]
    yw = yf - ym[inv]
    # within-item variation of log price: if (almost) none, the coefficient is not identified
    var_lp = float(np.var(Xw[:, 0]))
    XtX = Xw.T @ Xw
    try:
        inv_xtx = np.linalg.pinv(XtX)
    except np.linalg.LinAlgError:
        return {"identified": False, "reason": "singular design"}
    beta = inv_xtx @ (Xw.T @ yw)
    e = yw - Xw @ beta
    meat = np.zeros_like(XtX)
    # cluster sums
    S = np.zeros((len(ids), Xw.shape[1]))
    np.add.at(S, inv, Xw * e[:, None])
    meat = S.T @ S
    G = len(ids)
    dof = (G / max(G - 1, 1)) * ((len(yf) - 1) / max(len(yf) - Xw.shape[1] - G, 1))
    V = dof * inv_xtx @ meat @ inv_xtx
    se = float(np.sqrt(max(V[0, 0], 0.0)))
    b = float(beta[0])
    return {
        "identified": bool(var_lp > 1e-6), "coefficient_log_price": b, "std_error_item_clustered": se,
        "ci95": [b - 1.96 * se, b + 1.96 * se], "n_obs": int(len(yf)), "n_items": int(G),
        "within_item_sd_log_price": float(np.sqrt(var_lp)),
        "specification": ("log(units) on positive-sales days" if positive_only else "log(1+units)") + " ~ log(price) + item FE + day-of-week + month dummies",
        "reading": "association only: promotions, availability and seasonality are not randomised; not a causal elasticity",
    }


def model_price_counterfactual(predict_fn, F_base: np.ndarray, F_cf: np.ndarray, rows_idx: tuple[np.ndarray, np.ndarray],
                               pct: float) -> dict[str, Any]:
    """Compare predictions on identical rows between the base and counterfactual feature tensors."""
    s, d = rows_idx
    p0 = predict_fn(F_base[s, d])
    p1 = predict_fn(F_cf[s, d])
    delta = p1 - p0
    ok = p0 > 1e-6
    return {
        "price_change_pct": pct, "n_rows": int(len(s)),
        "mean_predicted_units_base": float(p0.mean()), "mean_predicted_units_cf": float(p1.mean()),
        "mean_change_pct_of_total": float((p1.sum() - p0.sum()) / p0.sum() * 100) if p0.sum() > 0 else None,
        "share_rows_decrease": float(np.mean(delta < -1e-9)), "share_rows_increase": float(np.mean(delta > 1e-9)),
        "share_rows_unchanged": float(np.mean(np.abs(delta) <= 1e-9)),
        "mean_row_pct_change_where_base_positive": float(np.mean(delta[ok] / p0[ok]) * 100) if ok.any() else None,
    }
