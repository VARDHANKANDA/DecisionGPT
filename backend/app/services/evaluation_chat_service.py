"""Evaluation results in chat.

A question about evaluation metrics, accuracy, baselines, horizons, benchmarks or validation is answered HERE, before any language model is
involved: the question is recognised by deterministic rules, the numbers come from ``evaluation_console_service`` (the same service and metric
registry the Research Console uses), and the answer is assembled from those cards. This module computes no metric. It selects, groups, labels and
paginates what the evaluation layer recorded; a value that was not recorded stays "Not available" with its reason.

Who sees what (decided by the caller, never here):
  * business validation  - the signed-in owner of THIS business only (``business_id`` is already authorised by the route guard and is the only
                           business any query here can touch);
  * registered-model and benchmark results (research datasets) - only callers who could open the Research Console (``research_access``).

The four kinds of evidence are never merged: business backtest, registered models on their research dataset, stored public benchmarks, and live
outcomes (not aggregated into these results, and always said so).
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.core.errors import AppError, InsufficientDataError, NotFoundError, ValidationFailedError
from app.services import analysis_run_service, evaluation_console_service as console, forecast_validation_service, model_performance_service
from app.services.metric_registry import REGISTRY, metric_definitions

PAGE_METRIC_BUDGET = 45            # metric values per page; a result block (one model / horizon / benchmark row) is never split across pages
STALE_AFTER_DAYS = 7
MAX_HISTORY = 25

STATE_LABEL = {
    "available": "Evaluated and available",
    "not_evaluated": "Not evaluated",
    "not_applicable": "Not applicable",
    "not_recorded": "Not recorded for this run",
    "insufficient_data": "Insufficient data",
    "failed": "Failed evaluation",
    "unreliable": "Withheld as not reliable",
}
EVIDENCE_LABEL = {
    "business": "Your business: backtest on its own history",
    "training": "Registered models: held-out part of their research dataset",
    "benchmark": "Public-data benchmark runs (as stored)",
}
EVIDENCE_ORDER = ("business", "training", "benchmark")
RESEARCH_ONLY_NOTE = ("Model-level and benchmark results are measured on research and public datasets and are shown to administrators in the Research Console, "
                      "not in business chat.")
NO_ACCURACY_PERCENT = ("There is no single 'accuracy percentage' for these models, and I will not turn an error score into one. Which metric answers the question "
                       "depends on the task: forecasts are judged by their error (MAE, WAPE) against a simple baseline, customer scores by how well they rank (ROC-AUC, "
                       "PR-AUC) and, at a stated threshold, precision, recall and accuracy.")


# ------------------------------------------------------------------------------------------------ understanding the question
@dataclass
class Query:
    mode: str = "all"                       # all | specific | definitions | unavailable | baseline | horizon | accuracy | reliability | history | run
    category: str | None = None             # forecasting | classification
    evidence: set[str] = field(default_factory=set)   # business | training | benchmark; empty = whatever this caller may see
    keys: list[str] = field(default_factory=list)     # registry metric keys asked for by name
    horizon: int | None = None
    page: int = 1
    run_id: str | None = None
    action: str | None = None               # run_forecast | run_customer
    wants_live: bool = False
    historical: bool = False
    text: str = ""

    def describe(self) -> dict[str, Any]:
        return {"mode": self.mode, "category": self.category, "evidence": sorted(self.evidence), "metrics": self.keys, "horizon_days": self.horizon,
                "page": self.page, "run_id": self.run_id}


_METRIC_WORDS: list[tuple[str, list[str]]] = [
    (r"\bmae\b|mean absolute error", ["mae"]),
    (r"\brmse\b|root mean squared? error", ["rmse"]),
    (r"\bwape\b|weighted absolute percentage", ["wape"]),
    (r"\bmape\b|mean absolute percentage", ["mape"]),
    (r"relative bias", ["relative_bias"]),
    (r"\bbias\b|over-?forecast|under-?forecast", ["bias", "relative_bias"]),
    (r"\bcoverage\b|prediction interval|confidence interval|uncertainty band", ["coverage"]),
    (r"\brmsse\b|scaled error", ["rmsse"]),
    (r"aggregate[- ]day|aggregate daily", ["aggregate_daily_wape"]),
    (r"median[- ]series", ["median_series_wape"]),
    (r"\broc\b|roc[- ]?auc|\bauc\b", ["roc_auc"]),
    (r"pr[- ]?auc|precision[- ]recall (curve|auc)", ["pr_auc"]),
    (r"\bprecision\b", ["precision"]),
    (r"\brecall\b", ["recall"]),
    (r"\bf1\b|f-?1 score", ["f1"]),
    (r"\bbrier\b", ["brier", "brier_baseline", "brier_vs_baseline"]),
    (r"\bece\b|expected calibration", ["ece"]),
    (r"log[- ]?loss", ["log_loss"]),
    (r"\blift\b|top[- ]decile|top 10", ["top_decile_lift", "top_decile_inactive_rate"]),
    (r"positive rate|prevalence|class balance", ["prevalence"]),
    (r"sample (size|count)|how many (rows|points|customers)|evaluated points", ["n_eval", "n_zero_actual", "n_invalid"]),
]
_STRONG = re.compile(
    r"\bevaluat|\bbenchmarks?\b|\bbaselines?\b|confusion matri|calibrat|\bbrier\b|log[- ]?loss|\b(mae|rmse|wape|mape|rmsse|ece|auc|roc|f1)\b|pr[- ]?auc|"
    r"top[- ]decile|score check|forecast validation|\bmetrics?\b|per[- ]horizon|each (forecast )?horizon|by (forecast )?horizon|interval coverage|prediction interval")
_WEAK = re.compile(r"\baccura|\breliab|\bprecision\b|\brecall\b|\bbias\b|\bvalidat|\blift\b|\bhorizons?\b|how (good|well) (is|are)")
_MODEL_CONTEXT = re.compile(r"model|forecast|predict|score|churn|classif|regress|result|my business|customer|metric|evaluat|baseline")
_KPI = re.compile(r"\bkpis?\b")


def _is_evaluation_question(t: str) -> bool:
    if _STRONG.search(t):
        # "which metrics are on my dashboard" is a KPI question; it needs a model/evaluation word to count here
        return not (_KPI.search(t) and not re.search(r"model|evaluat|forecast|classif|score|baseline|accura", t))
    return bool(_WEAK.search(t) and _MODEL_CONTEXT.search(t))


def detect(question: str) -> Query | None:
    """The evaluation question this is, or None when it is something else (and the normal analytics path should answer it)."""
    t = " ".join(question.lower().split())
    if not _is_evaluation_question(t):
        return None
    q = Query(text=t)

    for rx, keys in _METRIC_WORDS:
        if re.search(rx, t):
            q.keys += [k for k in keys if k not in q.keys]
    fc = bool(re.search(r"forecast|regression|horizon|\b(mae|rmse|wape|mape|rmsse)\b|interval|coverage|bias", t))
    cls = bool(re.search(r"classif|churn|customer|score|\broc\b|\bauc\b|precision|recall|\bf1\b|confusion|brier|\bece\b|log[- ]?loss|lift|calibrat|positive rate", t))
    q.category = "forecasting" if fc and not cls else "classification" if cls and not fc else None
    if re.search(r"benchmark|public data|\bm5\b|online retail", t):
        q.evidence.add("benchmark")
    if re.search(r"training|registered|model registry|research dataset|candidate model", t):
        q.evidence.add("training")
    if re.search(r"\bmy\b|\bour\b|business[- ]specific|business validation|for my business|own (data|history)", t):
        q.evidence.add("business")
    if q.evidence == {"business"} or (re.search(r"validation", t) and not q.evidence):
        q.evidence = {"business"}

    m = re.search(r"\bpage (\d{1,3})\b", t)
    if m:
        q.page = max(1, int(m.group(1)))
    m = re.search(r"\b(\d{1,3})[- ]?day", t) or re.search(r"horizon (?:of )?(\d{1,3})", t)
    if m:
        q.horizon = int(m.group(1))
    m = re.search(r"\brun[ -]?(?:id )?([0-9a-f]{8,36}(?:-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})?)\b", t)
    if m:
        q.run_id = m.group(1)
    q.wants_live = bool(re.search(r"\b(production|live|real[- ]world|in practice|actual(ly)? (accuracy|performance|results))\b", t))
    q.historical = bool(re.search(r"histor|previous|past (runs|evaluations)|older|over time", t))

    if re.match(r"^(please |can you |could you |would you |will you )?(run|start|perform|execute|launch|validate|back-?test)\b", t) and re.search(r"validat|back-?test|score check", t):
        q.mode, q.action = "run", ("run_customer" if re.search(r"customer|score|churn", t) else "run_forecast")
    elif re.search(r"unavailable|not available|missing|not recorded|not evaluated|cannot be (shown|evaluated)|can'?t be (shown|evaluated)|insufficient|why (is|are) .*(no|not)\b", t):
        q.mode = "unavailable"
    elif re.search(r"\bwhat (metrics|measures)\b|\bwhich (metrics|measures)\b.*\b(used|evaluate|measure|applicable|supported)|metrics (are )?(used|supported)|"
                   r"how (is|are|do you|does it) .*(evaluated|measured|scored)|\bdefin(e|ition)|\bwhat (does|do) .*\bmean|\bexplain\b.*(metric|mae|rmse|wape|auc|brier|ece|lift|bias)", t):
        q.mode = "definitions"
    elif re.search(r"baseline|naive|\bcompare\b.*\b(model|forecast)|\bbeat\b", t):
        q.mode = "baseline"
    elif q.horizon is not None or re.search(r"horizon", t):
        q.mode = "horizon"
    elif re.search(r"reliab|trust|dependable", t):
        q.mode = "reliability"
        q.category = q.category or "classification"
    elif re.search(r"accura|how (good|well|precise)", t):
        q.mode = "accuracy"
    elif q.historical and not q.evidence & {"benchmark"} and not re.search(r"\ball\b|every", t):
        q.mode = "history"
    elif q.keys and not re.search(r"\ball\b|every|complete|full|everything|entire|inventory", t):
        q.mode = "specific"
    return q


# ------------------------------------------------------------------------------------------------ collecting what exists
def _cards(subject: dict[str, Any]) -> list[dict[str, Any]]:
    return [c for g in subject["groups"] for c in g["cards"]]


def _fact(label: str, value: Any) -> dict[str, Any] | None:
    if value is None or value == "":
        return None
    return {"label": label, "value": value if isinstance(value, (str, int, float, bool)) else str(value)}


def _facts(*pairs: tuple[str, Any]) -> list[dict[str, Any]]:
    return [f for f in (_fact(k, v) for k, v in pairs) if f]


def _when(iso: Any) -> str | None:
    """'2026-10-21 18:29 UTC' for an ISO timestamp (what was recorded is shown unchanged if it cannot be read)."""
    if not iso:
        return None
    try:
        t = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    except ValueError:
        return str(iso)
    if t.tzinfo is not None:
        t = t.astimezone(timezone.utc)
    return t.strftime("%Y-%m-%d %H:%M UTC")


def _age_days(iso: str | None) -> int | None:
    if not iso:
        return None
    try:
        t = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return None
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    return max(0, (datetime.now(timezone.utc) - t).days)


_GENERIC_TOKENS = {"sales", "forecast", "forecasting", "churn", "model", "models", "baseline", "ensemble", "single", "depth6", "leaf5", "alpha1", "the", "and",
                   # parts of real method names that are also ordinary words in a question ("ensemble:mean_all" must not make "show me ALL results" a model choice)
                   "all", "mean", "top3", "weighted", "nnls", "same", "weekday", "mean4", "random", "tweedie", "hist", "gradient", "boosting"}


def _tokens(*names: str) -> list[str]:
    """Words a person could use to name this model ("xgboost", "random_forest"): the full name and its parts, minus words every model shares."""
    out: list[str] = []
    for n in names:
        n = n.lower()
        for tok in [n, *re.split(r"[^a-z0-9]+", n)]:
            if len(tok) > 2 and tok not in _GENERIC_TOKENS and tok not in out:
                out.append(tok)
    return out


def _training_subjects(overview: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for m in overview["sections"]["training"]["forecasting"]:
        n = next((c for c in m["test"] if c["key"] == "n_eval"), None)
        split = (m["setup"].get("splits") or {}).get("test") or {}
        groups = [{"title": "Against the baseline (yesterday's value, same rows)", "cards": m["baseline"]["test"]},
                  {"title": "Held-out test block", "cards": m["test"]}]
        if m["validation"]:
            groups.append({"title": "Validation block (used to choose between models; kept separate)", "cards": m["validation"]})
        groups.append({"title": "Prediction interval", "cards": [m["interval_coverage"]]})
        out.append({
            "id": f"training:{m['id']}", "evidence": "training", "category": "forecasting", "title": f"{m['model_name']} {m['version']}",
            "facts": _facts(("Model", f"{m['model_name']} {m['version']} ({m['status']})"), ("Training run", m["setup"].get("training_run_id")),
                            ("Dataset", m["setup"].get("dataset_version")), ("Task", "Forecasting / regression"), ("Target", m["target"]),
                            ("Sample", f"{n['display']} test points" if n and n["status"] == "available" else "not recorded for this model"),
                            ("Period", f"{split['first']} to {split['last']}" if split.get("first") else None), ("Horizon", "1 day ahead"),
                            ("Baseline", m["baseline"]["baseline"]), ("Split", m["setup"].get("split_scheme")), ("Code revision", m["setup"].get("code_revision")),
                            ("Trained", _when(m["setup"].get("trained_at")))),
            "groups": groups, "extras": {"verdict": m["baseline"]["verdict"], "notes": [m["by_horizon"]["reason"]]}, "state": None,
            "model_tokens": _tokens(m["model_name"], m["model_type"]),
        })
    for m in overview["sections"]["training"]["classification"]:
        cm = m["confusion_matrix"]
        groups = [{"title": "Held-out test block", "cards": m["test"]}]
        if m["class_balance"]:
            groups.append({"title": "Class balance", "cards": [m["class_balance"]["train_positive_rate"], m["class_balance"]["test_positive_rate"]]})
        if m["validation"]:
            groups.append({"title": "Validation (kept separate from the test figures)", "cards": m["validation"]})
        out.append({
            "id": f"training:{m['id']}", "evidence": "training", "category": "classification", "title": f"{m['model_name']} {m['version']}",
            "facts": _facts(("Model", f"{m['model_name']} {m['version']} ({m['status']})"), ("Training run", m["setup"].get("training_run_id")),
                            ("Dataset", m["setup"].get("dataset_version")), ("Task", "Classification / customer scoring"), ("Target", m["target"]),
                            ("Positive class", m["positive_class"]), ("Sample", f"{cm['n']:,} customers" if cm else "not recorded for this model"),
                            ("Threshold", cm["threshold"] if cm else None), ("Split", m["setup"].get("split_scheme")),
                            ("Code revision", m["setup"].get("code_revision")), ("Trained", _when(m["setup"].get("trained_at")))),
            "groups": groups, "extras": {"confusion_matrix": cm, "threshold_note": m["threshold_note"], "score_meaning": m["score_meaning"], "calibrated": m["calibrated"],
                                         "verdict": None, "notes": [m["score_meaning"], m["baseline"]["reason"]]}, "state": None,
            "model_tokens": _tokens(m["model_name"], m["model_type"]),
        })
    return out


def _benchmark_subjects(overview: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for run in overview["sections"]["benchmark"].get("runs", []):
        if run["kind"] == "forecast":
            for s in run.get("sections", []):
                for r in s["rows"]:
                    out.append({
                        "id": f"benchmark:{run['run_id']}:{s['name']}:{r['method']}", "evidence": "benchmark", "category": "forecasting",
                        "title": f"{run['title']} - {s['name']}: {r['method']}" + (" (baseline)" if r.get("kind") == "baseline" else ""),
                        "facts": _facts(("Benchmark run", run["run_id"]), ("Evidence class", run.get("evidence_class")), ("Task", "Forecasting"),
                                        ("Series", s.get("n_series")), ("Sample", f"{s['n_test_points']:,} test points" if s.get("n_test_points") else None),
                                        ("Period", " to ".join(s["test_window"]) if s.get("test_window") else None), ("Baseline", s.get("baseline_used_for_comparison")),
                                        ("Chosen on validation", "yes" if r["selected_by_validation"] else None), ("Code revision", run.get("git_revision")),
                                        ("Recorded", _when(run.get("created_utc")))),
                        "groups": [{"title": "Test results", "cards": r["cards"]}], "extras": {"verdict": None, "notes": ["Comparable only with rows of the same benchmark section."]},
                        "state": None, "model_tokens": _tokens(r["method"]),
                    })
        elif run["kind"] == "classification":
            split = run.get("rows_per_split") or {}
            prev = run.get("prevalence") or {}
            for r in run.get("rows", []):
                out.append({
                    "id": f"benchmark:{run['run_id']}:{r['method']}", "evidence": "benchmark", "category": "classification", "title": f"{run['title']}: {r['method']}",
                    "facts": _facts(("Benchmark run", run["run_id"]), ("Evidence class", run.get("evidence_class")), ("Task", "Classification (proxy or synthetic label)"),
                                    ("Rows", ", ".join(f"{k} {v:,}" for k, v in split.items()) if split else None),
                                    ("Positive rate", ", ".join(f"{k} {v:.3f}" for k, v in prev.items()) if prev else None),
                                    ("Chosen on validation", "yes" if r["selected_by_validation"] else None), ("Code revision", run.get("git_revision")),
                                    ("Recorded", _when(run.get("created_utc")))),
                    "groups": [{"title": "Test results", "cards": r["cards"]}],
                    "extras": {"verdict": None, "notes": ["Scores rank customers; they are not probabilities."]}, "state": None, "model_tokens": _tokens(r["method"]),
                })
    return out


def _business_subjects(validation: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    fr = validation.get("forecast")
    if fr:
        age = _age_days(fr.get("generated_at"))
        stale = f"run {age} days ago - may be out of date if sales changed since" if age is not None and age >= STALE_AFTER_DAYS else None
        data = fr.get("dataset") or {}
        for h in fr.get("horizons", []):
            state = None
            if h["status"] in ("descriptive_only", "insufficient_history"):
                state = {"kind": "insufficient_data", "reason": h.get("statement") or "Too little history to keep an untouched holdout."}
            elif h["status"] == "refused":
                state = {"kind": "failed", "reason": h.get("statement") or "The product declined to forecast this horizon."}
            groups = [{"title": "Untouched holdout results", "cards": h.get("cards", [])}] if h.get("cards") else []
            if h["status"] == "evaluated":
                groups.append({"title": "Prediction interval", "cards": [h["interval_coverage"]]})
            out.append({
                "id": f"business:forecast:{fr.get('run_id')}:{h['horizon_days']}", "evidence": "business", "category": "forecasting", "horizon": h["horizon_days"],
                "title": f"{h['horizon_days']}-day horizon: your business's forecast",
                "facts": _facts(("Validation run", fr.get("run_id")), ("Run date", _when(fr.get("generated_at"))), ("Task", "Forecasting / regression (backtest)"),
                                ("Target", "business daily units sold"), ("Data", f"{data.get('first_date')} to {data.get('last_date')}" if data.get("first_date") else None),
                                ("Horizon", f"{h['horizon_days']} days ahead"), ("Method", h.get("method")), ("Backtest periods", h.get("origins")),
                                ("Selection / holdout periods", f"{h.get('selection_origins')} / {h.get('holdout_origins')}" if h.get("selection_origins") is not None else None),
                                ("Baselines", "naive last value, trailing mean, seasonal naive (same holdout periods)"), ("Code revision", fr.get("code_revision")),
                                ("Freshness", stale)),
                "groups": groups,
                "extras": {"verdict": h.get("verdict"), "comparisons": h.get("baseline_comparison", []), "references": h.get("references", []),
                           "notes": [h["statement"]] if h.get("statement") else []},
                "state": state, "model_tokens": [],
            })
    cr = validation.get("customer")
    if cr:
        age = _age_days(cr.get("generated_at"))
        stale = f"run {age} days ago - may be out of date if sales changed since" if age is not None and age >= STALE_AFTER_DAYS else None
        target = cr.get("target") or {}
        for c in cr.get("cutoffs", []):
            state = None if c["status"] == "evaluated" else {"kind": "insufficient_data", "reason": c.get("reason") or "Too few customers or too few of one kind."}
            out.append({
                "id": f"business:customer:{cr.get('run_id')}:{c['cutoff']}", "evidence": "business", "category": "classification",
                "title": f"Customer score check, cut-off {c['cutoff']}: your customers",
                "facts": _facts(("Validation run", cr.get("run_id")), ("Run date", _when(cr.get("generated_at"))), ("Task", "Customer ranking vs a proxy label"),
                                ("Target", target.get("definition")), ("Cut-off", c["cutoff"]), ("Label window", " to ".join(c["label_window"]) if c.get("label_window") else None),
                                ("Sample", f"{c['customers']:,} customers ({c.get('inactive', 0):,} inactive)" if c.get("customers") else None),
                                ("Model", f"{(cr.get('model') or {}).get('name')} {(cr.get('model') or {}).get('version') or ''}".strip() if cr.get("model") else None),
                                ("Freshness", stale)),
                "groups": [{"title": "Results at this cut-off", "cards": c["cards"]}] if c.get("cards") else [],
                "extras": {"verdict": None, "notes": [target["limits"]] if target.get("limits") else []}, "state": state, "model_tokens": [],
            })
        if cr.get("calibration"):
            out.append({
                "id": f"business:customer:{cr.get('run_id')}:calibration", "evidence": "business", "category": "classification", "title": "Customer score calibration: your customers",
                "facts": _facts(("Validation run", cr.get("run_id"))), "groups": [{"title": "Calibration", "cards": [cr["calibration"]]}],
                "extras": {"verdict": None, "notes": []}, "state": None, "model_tokens": [],
            })
    return out


# ------------------------------------------------------------------------------------------------ assembling the answer
@dataclass
class EvalAnswer:
    text: str
    details: dict[str, Any]
    sources: list[str]
    sufficient: bool = True


def _count_kinds(subjects: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for s in subjects:
        for c in _cards(s):
            counts[c.get("kind", "available")] = counts.get(c.get("kind", "available"), 0) + 1
        if s["state"] and not _cards(s):
            counts[s["state"]["kind"]] = counts.get(s["state"]["kind"], 0) + 1
    return counts


def _paginate(subjects: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    pages: list[list[dict[str, Any]]] = []
    cur: list[dict[str, Any]] = []
    used = 0
    for s in subjects:
        n = max(1, len(_cards(s)))
        if cur and used + n > PAGE_METRIC_BUDGET:
            pages.append(cur)
            cur, used = [], 0
        cur.append(s)
        used += n
    if cur:
        pages.append(cur)
    return pages or [[]]


def _page_prompt(q: Query, page: int) -> str:
    base = {"all": "Show all evaluation results", "baseline": "Compare the models with their baselines", "horizon": "Show results for each forecast horizon",
            "unavailable": "Which metrics are unavailable and why", "accuracy": "How accurate are the models", "reliability": "How reliable are the customer scores",
            "specific": "Show " + (", ".join(q.keys) if q.keys else "the metrics")}.get(q.mode, "Show all evaluation results")
    if q.category == "forecasting" and q.mode == "all":
        base = "Show the forecasting evaluation results"
    if q.category == "classification" and q.mode == "all":
        base = "Show the classification evaluation metrics"
    extra = (" for my business" if q.evidence == {"business"} else " from the benchmark runs" if q.evidence == {"benchmark"} else
             " for the registered models" if q.evidence == {"training"} else "")
    return f"{base}{extra}, page {page}"


def _line(c: dict[str, Any], seen: set[str]) -> str:
    head = f"- {c['name']} ({c['abbr']}): {c['display']}"
    if c["status"] == "available":
        head += f" - {c['direction_text'].lower()}"
    else:
        head += f" - {STATE_LABEL.get(c.get('kind', ''), 'Not available')}: {c['reason']}"
    if c["key"] not in seen:
        seen.add(c["key"])
        head += f". {c['explanation']}"
        if c.get("sign_note"):
            head += f" {c['sign_note']}"
        if c.get("caveat"):
            head += f" Keep in mind: {c['caveat']}"
    return head


def _render_subject(s: dict[str, Any], seen: set[str]) -> list[str]:
    lines = [f"{s['title']}  [{EVIDENCE_LABEL[s['evidence']]}]"]
    if s["facts"]:
        lines.append("Evaluated on: " + "; ".join(f"{f['label']}: {f['value']}" for f in s["facts"]))
    if s["state"]:
        lines.append(f"{STATE_LABEL[s['state']['kind']]}: {s['state']['reason']}")
    for g in s["groups"]:
        lines.append(f"{g['title']}:")
        lines += [_line(c, seen) for c in g["cards"]]
    ex = s["extras"]
    cm = ex.get("confusion_matrix")
    if cm:
        lines.append(f"Confusion matrix (n = {cm['n']:,}, threshold {cm['threshold']}, positive class {cm['positive_class']}; rows are actual, columns predicted): "
                     f"true negative {cm['tn']:,}, false positive {cm['fp']:,}, false negative {cm['fn']:,}, true positive {cm['tp']:,}.")
        if ex.get("threshold_note"):
            lines.append(ex["threshold_note"])
    if ex.get("verdict"):
        lines.append("Against the references: " + ex["verdict"].replace("_", " ") + ".")
    for comp in ex.get("comparisons", []):
        ratio = "not available" if comp["mae_ratio"] is None else f"{comp['mae_ratio']:.2f}"
        lines.append(f"- MAE ratio vs {comp['reference'].replace('_', ' ')}: {ratio} ({comp['reading']})")
    for ref in ex.get("references", []):
        lines.append(f"- Reference {ref['method']}: " + ", ".join(f"{c['abbr']} {c['display']}" for c in ref["cards"]))
    for note in ex.get("notes", []):
        if note:
            lines.append(f"Note: {note}")
    return lines


def _limitations(evidences: set[str], categories: set[str], wants_live: bool) -> list[str]:
    out = []
    if "business" in evidences:
        out.append(console.LIMITATIONS[3])
    if "training" in evidences:
        out.append(console.LIMITATIONS[0])
    if "benchmark" in evidences:
        out.append(console.LIMITATIONS[1])
    if "classification" in categories:
        out.append(console.LIMITATIONS[2])
    out.append("These are recorded evaluations, not live outcomes: accuracy of live forecasts against what actually happened has not been measured in these "
               "results" + (", so no production accuracy can be quoted. The closest evidence is shown above, separately." if wants_live else "."))
    out.append(console.LIMITATIONS[4])
    return out


def _coverage(subjects: list[dict[str, Any]]) -> dict[str, Any]:
    """Counts of what is and is not available across ALL in-scope results (not just this page), plus every unavailable item with its reason."""
    items = []
    n_values = 0
    for s in subjects:
        for c in _cards(s):
            if c["status"] == "available":
                n_values += 1
            else:
                items.append({"result": s["title"], "evidence": s["evidence"], "metric": c["name"], "abbr": c["abbr"], "kind": c["kind"], "state": STATE_LABEL[c["kind"]], "reason": c["reason"]})
        if s["state"] and not _cards(s):
            items.append({"result": s["title"], "evidence": s["evidence"], "metric": "all metrics", "abbr": "-", "kind": s["state"]["kind"],
                          "state": STATE_LABEL[s["state"]["kind"]], "reason": s["state"]["reason"]})
    counts = _count_kinds(subjects)
    return {"available_values": n_values, "counts_by_state": {STATE_LABEL[k]: v for k, v in counts.items()}, "unavailable": items}


def _definitions_payload(keys: list[str]) -> list[dict[str, Any]]:
    wanted = [d for d in metric_definitions() if not keys or d["key"] in keys]
    task_label = {"regression": "Forecasting and regression", "classification": "Classification and customer scoring", "calibration": "Calibration diagnostics (classification)",
                  "data": "Sample and data-quality counts"}
    for d in wanted:
        d["applies_to"] = task_label.get(d["task"], d["task"])
        d["unit"] = REGISTRY[d["key"]].unit
    return wanted


def _gather(db: Session, business_id: str, q: Query, research: bool) -> tuple[list[dict[str, Any]], list[str], dict[str, Any]]:
    """(subjects in scope, sources, notes) for this caller. Research-level results are only collected when ``research`` is true."""
    sources: list[str] = []
    notes: dict[str, Any] = {"restricted": False, "business_present": False}
    subjects: list[dict[str, Any]] = []
    want = set(q.evidence) or ({"business", "training", "benchmark"} if research else {"business"})
    if not research and want - {"business"}:
        notes["restricted"] = True
        want = {"business"} if not q.evidence or q.evidence == {"business"} else want & {"business"}
    if "business" in want:
        if q.run_id:
            validation: dict[str, Any] = {"forecast": None, "customer": None}
            for kind, key in (("forecast_eval", "forecast"), ("customer_eval", "customer")):
                try:
                    run = analysis_run_service.get(db, business_id, q.run_id, kind)    # business_id scopes it: another business's run id is "not found"
                except (NotFoundError, AppError):
                    continue
                validation[key] = console.present_run({**(run.get("result") or {}), "id": run["id"]}, key)
            notes["run_found"] = any(validation.values())
        else:
            validation = console.business_validation(db, business_id)
        biz = _business_subjects(validation)
        subjects += biz
        notes["business_present"] = bool(biz)
        for key, label in (("forecast", "forecast validation"), ("customer", "customer-score validation")):
            r = validation.get(key)
            if r:
                sources.append(f"Stored {label} report {r.get('run_id')} for this business ({r.get('generated_at')})")
    if want & {"training", "benchmark"}:
        overview = console.overview(db)
        if "training" in want:
            tr = _training_subjects(overview)
            subjects += tr
            if tr:
                sources.append("Model registry metrics recorded by training runs (research datasets)")
        if "benchmark" in want:
            bm = _benchmark_subjects(overview)
            subjects += bm
            if bm:
                sources.append("Stored benchmark runs under experiments/ml_benchmark_v1 (read-only)")
        notes["limitations"] = overview["limitations"]
        notes["production"] = overview["sections"]["production"]["reason"]
    return subjects, sources, notes


def _select(subjects: list[dict[str, Any]], q: Query) -> tuple[list[dict[str, Any]], list[str]]:
    """Apply category / horizon / model / metric filters. Returns (subjects, messages explaining anything that matched nothing)."""
    msgs: list[str] = []
    out = [s for s in subjects if not q.category or s["category"] == q.category]
    if q.category and not out and subjects:
        msgs.append(f"No {q.category} results are available in this scope.")
    if q.horizon is not None:
        biz_h = [s for s in out if s["evidence"] == "business" and s.get("horizon") is not None]
        hit = [s for s in biz_h if s["horizon"] == q.horizon]
        if biz_h and not hit:
            msgs.append(f"No {q.horizon}-day horizon was evaluated for your business. Evaluated horizons: " + ", ".join(str(h) for h in sorted({s['horizon'] for s in biz_h})) + " days.")
        out = hit or [s for s in out if s["evidence"] != "business"]
    # a model named in the question (research callers only: only they have registered-model subjects)
    named = [] if q.mode in ("baseline", "definitions", "unavailable") else [s for s in out if s["evidence"] in ("training", "benchmark") and any(tok and re.search(rf"(?<![a-z0-9]){re.escape(tok)}(?![a-z0-9])", q.text) for tok in s["model_tokens"])]
    if named:
        keep = {s["id"] for s in named}
        out = [s for s in out if s["evidence"] == "business" or s["id"] in keep]
    if q.keys and q.mode in ("specific", "baseline", "accuracy"):
        wanted = set(q.keys)
        narrowed = []
        for s in out:
            groups = [{"title": g["title"], "cards": [c for c in g["cards"] if c["key"] in wanted]} for g in s["groups"]]
            groups = [g for g in groups if g["cards"]]
            if groups:
                narrowed.append({**s, "groups": groups})
        for k in q.keys:
            if not any(c["key"] == k for s in narrowed for c in _cards(s)):
                msgs.append(f"{REGISTRY[k].name} ({REGISTRY[k].abbr}) is not reported by any result in this scope. It applies to {_applies(k)}.")
                continue
            # reported somewhere, but not by every kind of result in scope: say which kinds do not carry it
            for cat in sorted({s["category"] for s in out}):
                if not any(c["key"] == k for s in narrowed if s["category"] == cat for c in _cards(s)):
                    msgs.append(f"{REGISTRY[k].name} ({REGISTRY[k].abbr}) is not reported by {cat} results. It applies to {_applies(k)}.")
        out = narrowed
    return out, msgs


def _applies(key: str) -> str:
    return {"regression": "forecasting and regression results", "classification": "classification and customer-scoring results",
            "calibration": "classification results (calibration diagnostics)", "data": "any result (sample counts)"}[REGISTRY[key].task]


_ACCURACY_KEYS = {"forecasting": ["mae", "wape", "relative_bias", "bias", "mae_vs_baseline", "baseline_mae", "coverage", "n_eval"],
                  "classification": ["roc_auc", "pr_auc", "precision", "recall", "f1", "accuracy", "prevalence", "brier", "brier_vs_baseline", "ece", "top_decile_lift", "n_eval"]}
_BASELINE_KEYS = ["mae", "baseline_mae", "mae_vs_baseline", "rmsse", "wape", "brier", "brier_baseline", "brier_vs_baseline"]


def _headline_for(q: Query, subjects: list[dict[str, Any]], page: int, pages: int, n_values: int) -> str:
    if q.mode == "accuracy":
        return NO_ACCURACY_PERCENT
    if q.mode == "reliability":
        return ("The customer scores are a ranking, not a calibrated probability of leaving. How reliable that ranking is shows in the results below; whether it is "
                "calibrated has " + ("not been evaluated for your customers." if any(s["evidence"] == "business" for s in subjects) else "only been checked as a diagnostic (Brier, ECE) where recorded."))
    if q.mode == "unavailable":
        return "Here is every metric that is not available for the results in scope, and why."
    if q.mode == "baseline":
        return "Here is how each model compares with its baseline, on the same rows and period for both. A baseline comparison only counts where both were scored on the same observations."
    if q.mode == "horizon":
        return "Here are the results for each evaluated forecast horizon."
    if q.mode == "specific":
        shown = [f"{c['abbr']}" for c in {c['key']: c for s in subjects for c in _cards(s)}.values()]
        return f"Here are the recorded values for {', '.join(shown) if shown else 'the metrics you asked about'} in every result that reports them."
    if q.mode == "history":
        return "Here are the evaluation runs on record."
    paging = f" (page {page} of {pages})" if pages > 1 else ""
    return f"Here are all {len(subjects)} evaluation results I can show you, with {n_values} recorded metric values{paging}."


def answer(db: Session, business_id: str, q: Query, *, research_access: bool) -> EvalAnswer:
    """Build the chat answer for an already-recognised evaluation question."""
    # --- stated actions: run (and store) a validation of THIS business, then show it
    action_note = None
    if q.mode == "run":
        try:
            (forecast_validation_service.run_forecast_validation if q.action == "run_forecast" else forecast_validation_service.run_customer_score_validation)(db, business_id)
            action_note = "I ran the validation on your business's own data and stored the report. It changed no model."
        except (InsufficientDataError, ValidationFailedError) as exc:
            return EvalAnswer(f"Insufficient data: the validation could not be run. {exc.message}", _wrap(q, [], [], {"state": "insufficient_data"}, research_access, 1, 1),
                              ["Business sales and customer records (read-only)"], sufficient=False)
        except AppError as exc:
            return EvalAnswer(f"The validation failed: {exc.message}", _wrap(q, [], [], {"state": "failed"}, research_access, 1, 1), [], sufficient=False)
        q = Query(**{**q.__dict__, "mode": "all", "evidence": {"business"}})

    if q.mode == "definitions":
        defs = _definitions_payload(q.keys)
        lines = ["These are the metrics the evaluations record, grouped by the kind of task they apply to. A metric appears on a result only when that evaluation recorded it."]
        by_task: dict[str, list[dict[str, Any]]] = {}
        for d in defs:
            by_task.setdefault(d["applies_to"], []).append(d)
        for task, items in by_task.items():
            lines.append(f"\n{task}")
            for d in items:
                lines.append(f"- {d['name']} ({d['abbr']}): {d['definition']} {d['direction_text']}. Unit: {d['unit']}." + (f" {d['sign_note']}" if d["sign_note"] else "")
                             + (f" Keep in mind: {d['caveat']}" if d["caveat"] else ""))
        details = _wrap(q, [], [], {"definitions": defs}, research_access, 1, 1)
        return EvalAnswer("\n".join(lines), details, ["Shared metric registry (backend/app/services/metric_registry.py)"])

    if q.mode == "history":
        return _history(db, business_id, q, research_access)

    subjects, sources, notes = _gather(db, business_id, q, research_access)
    msgs: list[str] = []
    if notes.get("restricted"):
        msgs.append(RESEARCH_ONLY_NOTE)
    if q.run_id and not notes.get("run_found", True):
        return EvalAnswer(f"I could not find a validation run with that id for your business. Ask for 'the validation history' to see your runs.",
                          _wrap(q, [], sources, {"state": "failed", "messages": msgs}, research_access, 1, 1), sources, sufficient=False)
    subjects, filt_msgs = _select(subjects, q)
    msgs += filt_msgs

    if q.mode == "accuracy" or q.mode == "reliability":
        cat_keys = {"forecasting": _ACCURACY_KEYS["forecasting"], "classification": _ACCURACY_KEYS["classification"]}
        narrowed = []
        for s in subjects:
            keys = set(cat_keys[s["category"]])
            groups = [{"title": g["title"], "cards": [c for c in g["cards"] if c["key"] in keys]} for g in s["groups"]]
            groups = [g for g in groups if g["cards"]]
            narrowed.append({**s, "groups": groups})
        subjects = narrowed
    elif q.mode == "baseline":
        keys = set(q.keys) if q.keys else set(_BASELINE_KEYS)
        subjects = [{**s, "groups": [g2 for g2 in ({"title": g["title"], "cards": [c for c in g["cards"] if c["key"] in keys]} for g in s["groups"]) if g2["cards"]]} for s in subjects]
        subjects = [s for s in subjects if s["groups"] or s["extras"].get("comparisons") or s["state"]]
    elif q.mode == "unavailable":
        pass

    subjects.sort(key=lambda s: (EVIDENCE_ORDER.index(s["evidence"]), s["category"], s.get("horizon") or 0, s["title"]))
    if not subjects:
        text = _nothing_to_show(q, notes, msgs, research_access, action_note)
        return EvalAnswer(text, _wrap(q, [], sources, {"state": "not_evaluated", "messages": msgs, "business_present": notes["business_present"]}, research_access, 1, 1),
                          sources, sufficient=False)

    pages = [subjects] if q.mode == "unavailable" else _paginate(subjects)        # the unavailable list is one complete table, not result blocks to page through
    n_pages = len(pages)
    page = q.page
    if page > n_pages:
        return EvalAnswer(f"There are only {n_pages} page(s) of results for this request. Ask for page 1 to {n_pages}.",
                          _wrap(q, [], sources, {"messages": [f"page {page} is out of range"]}, research_access, n_pages, n_pages), sources, sufficient=False)
    on_page = pages[page - 1]
    coverage = _coverage(subjects)
    seen: set[str] = set()
    lines: list[str] = []
    if action_note:
        lines.append(action_note)
    lines.append(_headline_for(q, subjects, page, n_pages, coverage["available_values"]))
    lines += msgs
    lines.append("\nEvaluation summary")
    ev_counts = {e: sum(1 for s in subjects if s["evidence"] == e) for e in EVIDENCE_ORDER if any(s["evidence"] == e for s in subjects)}
    for e, n in ev_counts.items():
        lines.append(f"- {EVIDENCE_LABEL[e]}: {n} result(s)")
    lines.append("- Metric values recorded: " + str(coverage["available_values"]) + "; not shown: " + (", ".join(f"{k} {v}" for k, v in coverage["counts_by_state"].items() if k != STATE_LABEL["available"]) or "none"))
    lines.append("- These four kinds of evidence are kept apart and never merged. Live accuracy against real outcomes is not part of these results.")
    if n_pages > 1:
        lines.append(f"- Page {page} of {n_pages}; ask 'page {min(page + 1, n_pages)}' for the next. Nothing is dropped: every result is on one of the pages.")
    if q.mode == "unavailable":
        lines.append("\nWhat is not available, and why")
        for it in coverage["unavailable"]:
            lines.append(f"- {it['result']} - {it['metric']}: {it['state']}. {it['reason']}")
    else:
        for e in EVIDENCE_ORDER:
            block = [s for s in on_page if s["evidence"] == e]
            if not block:
                continue
            lines.append(f"\n{EVIDENCE_LABEL[e].upper()}")
            for s in block:
                lines.append("")
                lines += _render_subject(s, seen)
    if page == n_pages:
        dq = [c for s in subjects for c in _cards(s) if c["key"] in ("n_eval", "n_zero_actual", "n_invalid")]
        if dq:
            lines.append("\nData quality and evaluation coverage")
            lines += [f"- {c['name']}: {c['display']}" + ("" if c["status"] == "available" else f" ({c['reason']})") for c in dq]
        lines.append("\nLimitations and interpretation")
        lines += [f"- {x}" for x in _limitations({s["evidence"] for s in subjects}, {s["category"] for s in subjects}, q.wants_live)]
    details = _wrap(q, [] if q.mode == "unavailable" else on_page, sources,
                    {"messages": msgs, "coverage": coverage, "action": action_note, "headline": lines[1] if action_note else lines[0]},
                    research_access, page, n_pages, all_subjects=subjects)
    return EvalAnswer("\n".join(lines), details, sources)


def _nothing_to_show(q: Query, notes: dict[str, Any], msgs: list[str], research: bool, action_note: str | None) -> str:
    parts = []
    if action_note:
        parts.append(action_note)
    if q.mode == "accuracy":
        parts.append(NO_ACCURACY_PERCENT)
    if notes.get("restricted") or (q.mode in ("accuracy", "reliability") and not research):
        parts.append(RESEARCH_ONLY_NOTE)
    if "business" in (q.evidence or {"business"}) and not notes.get("business_present"):
        parts.append("Not evaluated: no validation has been run on your business's own data yet, so there are no business-specific evaluation results to show. "
                     "Ask me to 'run a forecast validation for my business' (it only reads your data and changes no model). I will not substitute a public "
                     "benchmark for your own performance.")
    if q.wants_live:
        parts.append("Live accuracy against what actually happened has not been measured in these evaluation results.")
    parts += msgs
    return " ".join(dict.fromkeys(parts)) or "There are no evaluation results to show for this request."


def _history(db: Session, business_id: str, q: Query, research: bool) -> EvalAnswer:
    runs = []
    for kind in ("forecast_eval", "customer_eval"):
        runs += [{**r, "kind": kind} for r in analysis_run_service.list_runs(db, business_id, kind, limit=MAX_HISTORY)]
    runs.sort(key=lambda r: r.get("created_at") or "", reverse=True)
    runs = runs[:MAX_HISTORY]
    lines = ["Here are your business's evaluation runs on record, newest first."] if runs else ["No validation has been run on your business yet (not evaluated)."]
    for r in runs:
        lines.append(f"- {r['created_at']} - {'forecast' if r['kind'] == 'forecast_eval' else 'customer score'} validation, run {r['id']}: {r.get('headline') or 'no headline'}")
    if runs:
        lines.append("Ask for 'validation results for run <id>' to open one. Registered-model training history is in the Research Console.")
    sources = ["Stored validation runs for this business"]
    if research:
        hist = model_performance_service.get_model_performance(db)["training_history"][:MAX_HISTORY]
        lines.append("\nTraining runs on record (administrators):")
        for h in hist:
            lines.append(f"- {h['created_at']} - {h['task']} / {h['model_type']} on {h['dataset_version_label'] or 'unknown dataset'}: {h['status']}" + (f" ({h['error_message']})" if h["error_message"] else ""))
        sources.append("Training run history")
    return EvalAnswer("\n".join(lines), _wrap(q, [], sources, {"history": runs}, research, 1, 1), sources, sufficient=bool(runs))


def _wrap(q: Query, on_page: list[dict[str, Any]], sources: list[str], extra: dict[str, Any], research: bool, page: int, pages: int,
          all_subjects: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    sections = []
    for e in EVIDENCE_ORDER:
        block = [s for s in on_page if s["evidence"] == e]
        if block:
            sections.append({"evidence": e, "title": EVIDENCE_LABEL[e], "results": [{k: v for k, v in s.items() if k != "model_tokens"} for s in block]})
    total = all_subjects if all_subjects is not None else on_page
    page_prompts = [_page_prompt(q, i + 1) for i in range(pages)] if pages > 1 else []
    return {
        "evaluation": {
            "version": 1, "query": q.describe(), "access": {"research": research, "scope": "business + research" if research else "business only"},
            "pagination": {"page": page, "pages": pages, "results_total": len(total), "metric_values_total": sum(len(_cards(s)) for s in total),
                           "results_on_page": len(on_page), "next_prompt": page_prompts[page] if page < pages else None, "page_prompts": page_prompts},
            "sections": sections, "inventory": {"by_evidence": {e: sum(1 for s in total if s["evidence"] == e) for e in EVIDENCE_ORDER}},
            **extra,
        }
    }


def sanitize_for_json(obj: Any) -> Any:
    """Defence in depth: no NaN/Infinity can ever leave this service, whatever a stored report contained."""
    if isinstance(obj, float):
        return obj if math.isfinite(obj) else None
    if isinstance(obj, dict):
        return {k: sanitize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [sanitize_for_json(v) for v in obj]
    return obj
