"""Causal AI Engine — reproducible, assumption-aware analysis of cause-and-effect questions about the owner's own data.

WHAT THIS DOES AND DOES NOT CLAIM
* ``association`` (time-series regression of an outcome on a treatment with controls) is EXPLORATORY: it estimates how two recorded series move
  together after adjusting for day-of-week and trend. Without an experiment or a credible identification strategy it cannot establish
  causation, so it is never reported as a causal estimate. Placebo (lead) and feedback (reverse) checks are included to expose problems.
* ``did`` (difference-in-differences) compares products an owner changed on a known date against comparison products over the same dates.
  It can support a causal reading ONLY under its stated assumptions (parallel trends, no spillover, no other simultaneous change, a known
  intervention date). A pre-period parallel-trends test is run; the test cannot prove the assumption, only fail to reject it. If it is
  rejected the result is reported as "assumptions not satisfied".
All numbers come from the code below (numpy OLS with HC3 robust errors); no language model produces or alters them.

Classifications: not_enough_data | not_configured | assumptions_not_satisfied | exploratory_association | causal_estimate | failed
"""
from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core import clock
from app.models.marketing import MarketingCampaign
from app.models.product import Product
from app.models.sale import Sale
from app.services import analysis_run_service as runs

METHOD_VERSION = "causal-v1"
MIN_DAYS = 60
MIN_DISTINCT_TREATMENT = 5
PARALLEL_TRENDS_P = 0.10  # reject parallel trends below this (a stated, conservative convention)
OUTCOMES = {"revenue": "Sales (₹ per day)", "units": "Units sold per day"}
TREATMENTS = {"marketing_spend": "Marketing spend (₹ per day)", "avg_price": "Average selling price (₹ per unit)"}


def ols(X: np.ndarray, y: np.ndarray) -> dict[str, Any]:
    """OLS with HC3 heteroskedasticity-robust standard errors."""
    n, k = X.shape
    XtX_inv = np.linalg.pinv(X.T @ X)
    beta = XtX_inv @ X.T @ y
    resid = y - X @ beta
    h = np.einsum("ij,jk,ik->i", X, XtX_inv, X)
    h = np.clip(h, 0, 0.999999)
    meat = (X * (resid / (1 - h))[:, None]).T @ (X * (resid / (1 - h))[:, None])
    cov = XtX_inv @ meat @ XtX_inv
    se = np.sqrt(np.clip(np.diag(cov), 0, None))
    dof = max(n - k, 1)
    with np.errstate(divide="ignore", invalid="ignore"):
        t = np.where(se > 0, beta / se, 0.0)
    p = 2 * stats.t.sf(np.abs(t), dof)
    ss_tot = float(((y - y.mean()) ** 2).sum())
    r2 = 1 - float((resid**2).sum()) / ss_tot if ss_tot > 0 else 0.0
    crit = stats.t.ppf(0.975, dof)
    return {"beta": beta, "se": se, "p": p, "ci": np.stack([beta - crit * se, beta + crit * se], axis=1), "r2": r2, "n": n, "k": k}


def daily_panel(db: Session, business_id: str) -> pd.DataFrame:
    """Calendar-day panel over the sales date range: revenue, units, avg_price (NaN on days without sales), marketing_spend (NaN outside marketing coverage)."""
    rows = (db.query(Sale.sale_date, func.sum(Sale.revenue), func.sum(Sale.quantity)).filter(Sale.business_id == business_id)
            .group_by(Sale.sale_date).order_by(Sale.sale_date).all())
    if not rows:
        return pd.DataFrame(columns=["revenue", "units", "avg_price", "marketing_spend"])
    s = pd.DataFrame({"date": [pd.Timestamp(r[0]) for r in rows], "revenue": [float(r[1] or 0) for r in rows], "units": [float(r[2] or 0) for r in rows]}).set_index("date")
    idx = pd.date_range(s.index.min(), s.index.max(), freq="D")
    s = s.reindex(idx).fillna({"revenue": 0.0, "units": 0.0})
    s["avg_price"] = np.where(s["units"] > 0, s["revenue"] / s["units"].where(s["units"] > 0), np.nan)
    m = (db.query(MarketingCampaign.campaign_date, func.sum(MarketingCampaign.spend)).filter(MarketingCampaign.business_id == business_id)
         .group_by(MarketingCampaign.campaign_date).all())
    s["marketing_spend"] = np.nan
    if m:
        ms = pd.Series({pd.Timestamp(d): float(v or 0) for d, v in m})
        lo, hi = ms.index.min(), ms.index.max()
        inside = (s.index >= lo) & (s.index <= hi)
        s.loc[inside, "marketing_spend"] = ms.reindex(s.index[inside]).fillna(0.0).values
    return s


def _result(classification: str, headline: str, **kw: Any) -> dict[str, Any]:
    return {"classification": classification, "headline": headline, "method_version": METHOD_VERSION, "generated_on": clock.today().isoformat(), **kw}


STATE_TEXT = {
    "not_enough_data": "Not enough data for this analysis.",
    "not_configured": "This analysis is not fully configured.",
    "assumptions_not_satisfied": "The assumptions this method needs are not satisfied by your data.",
    "exploratory_association": "Exploratory association only — this does not establish cause and effect.",
    "causal_estimate": "A causal estimate under stated assumptions (these cannot be proven from the data alone).",
    "failed": "The analysis failed.",
}


def _next_day(d: pd.DataFrame, col: str) -> pd.Series:
    """Value of ``col`` on the following calendar day (NaN when the next row is not the next day, so gaps are never bridged)."""
    gap = (d.index.to_series().shift(-1) - d.index.to_series()).dt.days
    return d[col].shift(-1).where(gap == 1)


def _design(d: pd.DataFrame, treatment: str, controls: list[str]) -> tuple[np.ndarray, list[str]]:
    cols: list[np.ndarray] = [np.ones(len(d)), d[treatment].to_numpy(float)]
    names = ["intercept", treatment]
    if "trend" in controls:
        cols.append(((np.arange(len(d)) - len(d) / 2) / len(d)).astype(float))
        names.append("trend")
    if "day_of_week" in controls:
        dow = d.index.dayofweek
        for k in range(1, 7):
            cols.append((dow == k).astype(float))
            names.append(f"dow_{k}")
    return np.column_stack(cols), names


def _fit(d: pd.DataFrame, outcome: str, treatment: str, controls: list[str]) -> dict[str, Any]:
    X, names = _design(d, treatment, controls)
    r = ols(X, d[outcome].to_numpy(float))
    i = names.index(treatment)
    return {"coef": float(r["beta"][i]), "se": float(r["se"][i]), "p": float(r["p"][i]), "ci": [float(r["ci"][i][0]), float(r["ci"][i][1])], "r2": float(r["r2"]), "n": int(r["n"])}


def association(db: Session, business_id: str, outcome: str, treatment: str, controls: list[str] | None = None) -> dict[str, Any]:
    controls = [c for c in (controls if controls is not None else ["day_of_week", "trend"]) if c in ("day_of_week", "trend")]
    question = f"How is {OUTCOMES.get(outcome, outcome)} associated with {TREATMENTS.get(treatment, treatment)}?"
    if outcome not in OUTCOMES or treatment not in TREATMENTS:
        return _result("not_configured", STATE_TEXT["not_configured"], question=question, reason=f"Choose an outcome from {list(OUTCOMES)} and a treatment from {list(TREATMENTS)}.")
    panel = daily_panel(db, business_id)
    if panel.empty:
        return _result("not_enough_data", STATE_TEXT["not_enough_data"], question=question, reason="No sales are recorded.")
    d = panel.dropna(subset=[treatment, outcome]).copy()
    if treatment == "avg_price":
        d = d[d["units"] > 0]
    coverage = {"first_day": d.index.min().date().isoformat() if len(d) else None, "last_day": d.index.max().date().isoformat() if len(d) else None, "days_used": int(len(d)),
                "days_in_sales_range": int(len(panel))}
    distinct = int(d[treatment].nunique()) if len(d) else 0
    checks = [
        {"check": f"At least {MIN_DAYS} usable days", "passed": len(d) >= MIN_DAYS, "detail": f"{len(d)} usable days"},
        {"check": f"The treatment takes at least {MIN_DISTINCT_TREATMENT} different values", "passed": distinct >= MIN_DISTINCT_TREATMENT, "detail": f"{distinct} distinct values"},
        {"check": "The treatment varies (not constant)", "passed": bool(len(d) and d[treatment].std() > 0), "detail": "standard deviation > 0"},
    ]
    if treatment == "marketing_spend" and panel["marketing_spend"].isna().all():
        return _result("not_enough_data", STATE_TEXT["not_enough_data"], question=question, coverage=coverage, suitability=checks, reason="No marketing spend is recorded, so there is no treatment series.")
    if not all(c["passed"] for c in checks):
        return _result("not_enough_data", STATE_TEXT["not_enough_data"], question=question, coverage=coverage, suitability=checks,
                       reason="The data does not meet the minimum requirements below, so no estimate is produced.")
    try:
        main = _fit(d, outcome, treatment, controls)
        none_ = _fit(d, outcome, treatment, [])
        half = len(d) // 2
        first, second = _fit(d.iloc[:half], outcome, treatment, controls), _fit(d.iloc[half:], outcome, treatment, controls)
        cut = d[d[outcome] <= d[outcome].quantile(0.95)]
        trimmed = _fit(cut, outcome, treatment, controls) if len(cut) >= MIN_DAYS // 2 else None
        # placebo: tomorrow's treatment should not predict today's outcome
        lead = d.copy()
        lead["_lead"] = _next_day(d, treatment)
        lead = lead.dropna(subset=["_lead"])
        placebo = _fit(lead.rename(columns={treatment: "_orig", "_lead": treatment}), outcome, treatment, controls)
        # feedback: today's outcome predicting tomorrow's treatment
        fb = d.copy()
        fb["_next"] = _next_day(d, treatment)
        fb = fb.dropna(subset=["_next"])
        Xf, nf = _design(fb.rename(columns={outcome: "_o"}), "_o", controls)
        fr = ols(Xf, fb["_next"].to_numpy(float))
        fi = nf.index("_o")
        feedback = {"coef": float(fr["beta"][fi]), "p": float(fr["p"][fi])}
    except Exception as exc:  # noqa: BLE001 - reported, never hidden
        return _result("failed", STATE_TEXT["failed"], question=question, coverage=coverage, suitability=checks, error=f"{type(exc).__name__}: {exc}")

    flags = []
    if placebo["p"] < 0.05:
        flags.append("Tomorrow's treatment 'predicts' today's outcome (placebo test). That points to confounding or planning around expected sales, so the association should not be read as an effect.")
    if feedback["p"] < 0.05:
        flags.append("Today's sales predict tomorrow's treatment (feedback). The owner may be setting the treatment in response to sales, which biases a simple regression.")
    if np.sign(first["coef"]) != np.sign(second["coef"]):
        flags.append("The sign of the association differs between the first and second half of the data (unstable).")
    unit = "₹" if outcome == "revenue" else "units"
    t_unit = "₹1 more marketing spend" if treatment == "marketing_spend" else "₹1 higher average price"
    significant = main["p"] < 0.05
    interp = (f"After adjusting for {', '.join(controls) or 'nothing'}, a day with {t_unit} is associated with {main['coef']:+.3f} {unit} on the same day "
              f"(95% interval {main['ci'][0]:+.3f} to {main['ci'][1]:+.3f}; p = {main['p']:.3f}). "
              + ("The interval excludes zero, so the two series move together in your data. " if significant else "The interval includes zero, so these data do not show a clear association. ")
              + "This is an association, not a measured effect of changing the treatment.")
    return _result(
        "exploratory_association", STATE_TEXT["exploratory_association"], question=question,
        causal_question=f"Would changing {TREATMENTS[treatment]} change {OUTCOMES[outcome]}?",
        method={"name": "Time-series OLS with robust (HC3) standard errors", "model": f"{outcome}(t) = a + b·{treatment}(t) + controls", "controls": controls,
                "why_chosen": "Daily series are the only structure the records support here; a regression shows association after adjusting for weekday and trend.",
                "why_not_causal": "No experiment or other identification strategy is available, so unmeasured factors (promotions, season, stock, weather) can drive both series."},
        coverage=coverage, suitability=checks, estimate={"coefficient": main["coef"], "se": main["se"], "ci95": main["ci"], "p_value": main["p"], "r_squared": main["r2"], "n_days": main["n"], "unit": f"{unit} per day per {'₹ of spend' if treatment == 'marketing_spend' else '₹ of price'}"},
        robustness=[{"check": "Without controls", **{k: none_[k] for k in ("coef", "p")}},
                    {"check": "First half of the data", **{k: first[k] for k in ("coef", "p")}}, {"check": "Second half of the data", **{k: second[k] for k in ("coef", "p")}},
                    *([{"check": "Excluding the top 5% of outcome days", **{k: trimmed[k] for k in ("coef", "p")}}] if trimmed else [])],
        placebo={"description": "Next day's treatment on today's outcome (should be near zero)", "coef": placebo["coef"], "p_value": placebo["p"]},
        feedback={"description": "Today's outcome on tomorrow's treatment", "coef": feedback["coef"], "p_value": feedback["p"]},
        warnings=flags,
        assumptions=[{"assumption": "No unmeasured factor drives both series", "status": "unverified"}, {"assumption": "The relationship is roughly linear within the observed range", "status": "unverified"},
                     {"assumption": "The treatment is not set in response to the outcome", "status": "checked partly (feedback test above)"}],
        interpretation=interp,
        limitations=["Exploratory only. Use an experiment (for example changing the treatment in one place and not another) to learn an effect.", "Uses daily totals across all products."],
    )


def _resolve_products(db: Session, business_id: str, names: list[str]) -> tuple[list[str], list[str]]:
    cat = {p.name.strip().casefold(): p.id for p in db.query(Product).filter(Product.business_id == business_id)}
    ids, missing = [], []
    for n in names:
        pid = cat.get(str(n).strip().casefold())
        (ids if pid else missing).append(pid or n)
    return ids, missing


def did(db: Session, business_id: str, outcome: str, treated: list[str], control: list[str], intervention_date: str | None, window_days: int = 28) -> dict[str, Any]:
    question = f"What was the effect on {OUTCOMES.get(outcome, outcome)} of the change made to {', '.join(treated) or '…'} on {intervention_date or '…'}?"
    if outcome not in OUTCOMES or not treated or not control or not intervention_date:
        return _result("not_configured", STATE_TEXT["not_configured"], question=question,
                       reason="Choose an outcome, at least one product you changed, at least one comparison product you did not change, and the date of the change.")
    try:
        t0 = pd.Timestamp(date.fromisoformat(intervention_date))
    except ValueError:
        return _result("not_configured", STATE_TEXT["not_configured"], question=question, reason="The intervention date is not a valid date (use YYYY-MM-DD).")
    window_days = int(max(7, min(window_days, 120)))
    tid, tmiss = _resolve_products(db, business_id, treated)
    cid, cmiss = _resolve_products(db, business_id, control)
    if tmiss or cmiss or set(tid) & set(cid):
        return _result("not_configured", STATE_TEXT["not_configured"], question=question,
                       reason=("These products were not found: " + ", ".join(tmiss + cmiss) + ". " if tmiss or cmiss else "") + ("A product cannot be both changed and comparison." if set(tid) & set(cid) else ""))
    lo, hi = t0 - pd.Timedelta(days=window_days), t0 + pd.Timedelta(days=window_days - 1)
    rows = (db.query(Sale.product_id, Sale.sale_date, func.sum(Sale.revenue), func.sum(Sale.quantity))
            .filter(Sale.business_id == business_id, Sale.product_id.in_(tid + cid), Sale.sale_date >= lo.date(), Sale.sale_date <= hi.date())
            .group_by(Sale.product_id, Sale.sale_date).all())
    days = pd.date_range(lo, hi, freq="D")
    recs = []
    got = {(r[0], pd.Timestamp(r[1])): (float(r[2] or 0), float(r[3] or 0)) for r in rows}
    for pid in tid + cid:
        for day in days:
            rev, un = got.get((pid, day), (0.0, 0.0))
            recs.append({"pid": pid, "date": day, "treated": 1.0 if pid in tid else 0.0, "post": 1.0 if day >= t0 else 0.0, "y": rev if outcome == "revenue" else un})
    d = pd.DataFrame(recs)
    n_pre = int(((d["post"] == 0) & (d["treated"] == 1)).sum() / max(len(tid), 1))
    n_post = int(((d["post"] == 1) & (d["treated"] == 1)).sum() / max(len(tid), 1))
    sales_days = {g: int(((d["treated"] == g) & (d["y"] > 0)).sum()) for g in (0.0, 1.0)}
    checks = [
        {"check": "At least 7 days before and after the change", "passed": n_pre >= 7 and n_post >= 7, "detail": f"{n_pre} days before, {n_post} days after"},
        {"check": "Both groups have sales in the window", "passed": sales_days[0.0] > 0 and sales_days[1.0] > 0, "detail": f"changed group {sales_days[1.0]} product-days with sales, comparison {sales_days[0.0]}"},
        {"check": "Enough sales days in both periods", "passed": int(((d["y"] > 0) & (d["post"] == 0)).sum()) >= 10 and int(((d["y"] > 0) & (d["post"] == 1)).sum()) >= 10, "detail": "at least 10 product-days with sales before and after"},
    ]
    if not all(c["passed"] for c in checks):
        return _result("not_enough_data", STATE_TEXT["not_enough_data"], question=question, suitability=checks,
                       reason="The window does not contain enough sales on both sides of the change for both groups.")
    X = np.column_stack([np.ones(len(d)), d["treated"], d["post"], d["treated"] * d["post"]])
    r = ols(X, d["y"].to_numpy(float))
    effect, se, p, ci = float(r["beta"][3]), float(r["se"][3]), float(r["p"][3]), [float(x) for x in r["ci"][3]]
    pre = d[d["post"] == 0].copy()
    pre["t"] = (pre["date"] - lo).dt.days.astype(float)
    Xp = np.column_stack([np.ones(len(pre)), pre["treated"], pre["t"], pre["treated"] * pre["t"]])
    rp = ols(Xp, pre["y"].to_numpy(float))
    pt_p = float(rp["p"][3])
    means = {f"{'changed' if g else 'comparison'}_{'after' if po else 'before'}": round(float(d[(d['treated'] == g) & (d['post'] == po)]['y'].mean()), 3) for g in (1.0, 0.0) for po in (0.0, 1.0)}
    parallel_ok = pt_p >= PARALLEL_TRENDS_P
    unit = "₹" if outcome == "revenue" else "units"
    assumptions = [
        {"assumption": "Parallel trends: without the change, the changed and comparison products would have moved alike", "status": "not rejected by the pre-period test" if parallel_ok else "REJECTED by the pre-period test", "p_value": pt_p},
        {"assumption": "No other change hit only one group on or near the same date (promotion, stock-out, season)", "status": "unverified — only you can confirm this"},
        {"assumption": "The changed products did not pull sales from (or push sales to) the comparison products", "status": "unverified"},
        {"assumption": "The date you gave is when the change really took effect", "status": "stated by the owner"},
    ]
    base = dict(question=question, causal_question="What would the changed products' outcome have been without the change?",
                method={"name": "Difference-in-differences (2×2) with robust standard errors", "model": "y = a + b·changed + c·after + d·(changed×after); d is the estimate",
                        "why_chosen": "You supplied an intervention date, products you changed and comparison products you did not change.", "window_days_each_side": window_days},
                suitability=checks, group_means=means, products={"changed": treated, "comparison": control}, intervention_date=intervention_date,
                estimate={"effect_per_product_day": effect, "se": se, "ci95": ci, "p_value": p, "unit": f"{unit} per product per day", "n_observations": int(r["n"]), "changed_products": len(tid), "comparison_products": len(cid)},
                pre_trend_test={"description": "Do the groups already diverge before the change? (interaction of group and time, pre-period)", "p_value": pt_p, "threshold": PARALLEL_TRENDS_P, "rejected": not parallel_ok},
                assumptions=assumptions, limitations=["The pre-trend test cannot prove parallel trends; it can only fail to reject them.", "The estimate describes the changed group compared with the chosen comparison group only."])
    if not parallel_ok:
        return _result("assumptions_not_satisfied", STATE_TEXT["assumptions_not_satisfied"], **base,
                       interpretation="The two groups were already moving differently before the change, so the difference after it cannot be attributed to the change. No causal estimate is reported.")
    sig = "The interval excludes zero." if p < 0.05 else "The interval includes zero, so the data do not show a clear effect."
    return _result("causal_estimate", STATE_TEXT["causal_estimate"], **base,
                   interpretation=f"Under the stated assumptions, the change is estimated to have moved {OUTCOMES[outcome].lower()} by {effect:+.2f} {unit} per product per day "
                                  f"(95% interval {ci[0]:+.2f} to {ci[1]:+.2f}; p = {p:.3f}). {sig} Treat this as the best available evidence from observational data, not as certainty.")


def run(db: Session, business_id: str, params: dict[str, Any]) -> dict[str, Any]:
    kind = params.get("method")
    if kind == "association":
        res = association(db, business_id, params.get("outcome", ""), params.get("treatment", ""), params.get("controls"))
    elif kind == "did":
        res = did(db, business_id, params.get("outcome", ""), list(params.get("treated") or []), list(params.get("control") or []), params.get("intervention_date"),
                  int(params.get("window_days") or 28))
    else:
        res = _result("not_configured", STATE_TEXT["not_configured"], reason="method must be 'association' or 'did'.")
    row = runs.save(db, business_id, "causal", kind, res.get("question"), {k: v for k, v in params.items()}, res, status="failed" if res["classification"] == "failed" else "completed",
                    error=res.get("error"))
    return {"id": row.id, **res}
