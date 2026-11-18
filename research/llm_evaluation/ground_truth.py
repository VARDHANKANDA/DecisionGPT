"""Deterministic ground-truth engine. No LLM, no hand-typed answers.

Every task in tasks/tasks_v1.json carries a declarative ``ground_truth_definition`` (an ``op`` plus
parameters). This module interprets those definitions over the evaluation data view and returns
the answer plus the exact filter/calculation description that produced it.
"""
from __future__ import annotations

import calendar
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from research.llm_evaluation.data_view import ViewInfo, build_view

GT_VERSION = "gt-1.0"
WEEKDAYS = list(calendar.day_name)  # Monday..Sunday


def _window(df: pd.DataFrame, p: dict) -> pd.DataFrame:
    if p.get("start") is None and p.get("end") is None:
        return df
    return df[(df["date"] >= pd.Timestamp(p["start"])) & (df["date"] <= pd.Timestamp(p["end"]))]


def _unique_top(series: pd.Series, k: int, what: str) -> list[str]:
    ranked = series.sort_values(ascending=False)
    top = ranked.head(k + 1)
    # A tie at the boundary would make the "correct" ranking ambiguous — refuse to define such a task.
    if len(top) > k and top.iloc[k - 1] == top.iloc[k]:
        raise ValueError(f"tie at rank {k}/{k + 1} for {what}; task is ambiguous")
    if k > 1 and top.head(k).duplicated().any():
        raise ValueError(f"tie inside top-{k} for {what}; task is ambiguous")
    return [str(i) for i in ranked.head(k).index]


def compute(defn: dict, view: pd.DataFrame) -> dict:
    """Return {'answer': ..., 'calculation': str} for one ground_truth_definition."""
    op = defn["op"]
    p = defn.get("params", {})
    w = _window(view, p)
    out: dict

    if op == "sum_revenue":
        out = {"answer": round(float(w["revenue"].sum()), 2), "calculation": "sum(quantity*unit_price) over window"}
    elif op == "sum_quantity":
        out = {"answer": int(w["quantity"].sum()), "calculation": "sum(quantity) over window"}
    elif op == "count_lines":
        out = {"answer": int(len(w)), "calculation": "number of view lines in window"}
    elif op == "pct_change_revenue":
        new = float(_window(view, p["new"])["revenue"].sum())
        base = float(_window(view, p["base"])["revenue"].sum())
        out = {"answer": round((new - base) / base * 100, 4), "calculation": "(sum(new window) - sum(base window)) / sum(base window) * 100",
               "detail": {"new_total": round(new, 2), "base_total": round(base, 2)}}
    elif op in ("argmax_day_revenue", "argmin_day_revenue"):
        daily = w.groupby("date")["revenue"].sum()
        day = daily.idxmax() if op == "argmax_day_revenue" else daily.idxmin()
        tied = int((daily == daily.loc[day]).sum())
        if tied > 1:
            raise ValueError("tie for extreme day; task is ambiguous")
        out = {"answer": str(day.date()), "calculation": "day with the extreme total revenue among days that have >=1 sale",
               "detail": {"revenue": round(float(daily.loc[day]), 2)}}
    elif op == "top_products":
        metric = p["metric"]
        series = w.groupby("product")[metric].sum()
        out = {"answer": _unique_top(series, p["k"], f"top_products {metric} {p.get('start')}..{p.get('end')}"),
               "calculation": f"products ranked by sum({metric}) over window, top {p['k']}"}
    elif op == "product_quantity":
        out = {"answer": int(w.loc[w["product"] == p["product"], "quantity"].sum()), "calculation": "sum(quantity) for one product"}
    elif op == "compare_products_quantity":
        a, b = p["products"]
        qa = int(w.loc[w["product"] == a, "quantity"].sum())
        qb = int(w.loc[w["product"] == b, "quantity"].sum())
        if qa == qb:
            raise ValueError("tie between compared products; task is ambiguous")
        out = {"answer": a if qa > qb else b, "calculation": "product with the larger sum(quantity)", "detail": {a: qa, b: qb}}
    elif op == "product_revenue_share":
        total = float(w["revenue"].sum())
        part = float(w.loc[w["product"] == p["product"], "revenue"].sum())
        out = {"answer": round(part / total * 100, 4), "calculation": "product revenue / total revenue * 100",
               "detail": {"product_revenue": round(part, 2), "total_revenue": round(total, 2)}}
    elif op in ("weekday_extreme",):
        by = w.assign(wd=w["date"].dt.day_name()).groupby("wd")["revenue"].sum()
        day = by.idxmax() if p["which"] == "max" else by.idxmin()
        if int((by == by.loc[day]).sum()) > 1:
            raise ValueError("tie for weekday extreme; task is ambiguous")
        out = {"answer": str(day), "calculation": f"weekday with the {p['which']} total revenue",
               "detail": {k: round(float(v), 2) for k, v in by.items()}}
    elif op == "sum_revenue_weekday":
        sel = w[w["date"].dt.day_name() == p["weekday"]]
        out = {"answer": round(float(sel["revenue"].sum()), 2), "calculation": f"sum(revenue) on all {p['weekday']}s in window"}
    elif op == "mean_daily_revenue":
        daily = w.groupby("date")["revenue"].sum()
        out = {"answer": round(float(daily.mean()), 2), "calculation": "mean of daily revenue over days with >=1 sale",
               "detail": {"days": int(len(daily))}}
    elif op == "gst_revenue":
        out = {"answer": round(float(w.loc[w["gst_pct"] == p["gst"], "revenue"].sum()), 2), "calculation": "sum(revenue) where gst_pct == slab"}
    elif op == "gst_share":
        total = float(w["revenue"].sum())
        out = {"answer": round(float(w.loc[w["gst_pct"] == p["gst"], "revenue"].sum()) / total * 100, 4), "calculation": "slab revenue / total revenue * 100"}
    elif op == "gst_argmax":
        by = w.groupby("gst_pct")["revenue"].sum()
        top = by.idxmax()
        out = {"answer": f"{int(top)}%", "calculation": "GST slab with the largest total revenue", "detail": {f"{int(k)}%": round(float(v), 2) for k, v in by.items()}}
    elif op == "distinct_products":
        out = {"answer": int(w["product"].nunique()), "calculation": "count of distinct product names in window"}
    elif op == "mean_daily_quantity":
        daily = w.groupby("date")["quantity"].sum()
        out = {"answer": round(float(daily.mean()), 4), "calculation": "mean of daily unit totals over days with >=1 sale", "detail": {"days": int(len(daily))}}
    elif op == "max_day_revenue":
        daily = w.groupby("date")["revenue"].sum()
        out = {"answer": round(float(daily.max()), 2), "calculation": "largest daily revenue total in window"}
    else:
        raise ValueError(f"unknown ground-truth op {op!r}")

    out["op"] = op
    out["params"] = p
    return out


def compute_all(spec: dict, view: pd.DataFrame | None = None, info: ViewInfo | None = None) -> dict:
    if view is None:
        view, info = build_view()
    answers = {}
    for t in spec["tasks"]:
        answers[t["task_id"]] = compute(t["ground_truth_definition"], view)
    spec_hash = hashlib.sha256(json.dumps(spec, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    return {
        "ground_truth_version": GT_VERSION,
        "spec_sha256": spec_hash,
        "view": info.as_dict() if info else None,
        "computed_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "rounding": "revenue 2 dp, percentages 4 dp; scoring tolerances come from the spec, not from here",
        "answers": answers,
    }


def spec_sha256(spec: dict) -> str:
    return hashlib.sha256(json.dumps(spec, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def write_ground_truth(spec_path: Path, out_dir: Path) -> Path:
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    gt = compute_all(spec)
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"ground_truth_{gt['spec_sha256'][:12]}.json"
    out.write_text(json.dumps(gt, indent=2, ensure_ascii=False), encoding="utf-8")
    return out
