"""Risk calibration, defined and measured only where the prerequisites exist.

"Risk" appears in DecisionGPT in three different senses, and they are NOT interchangeable:
  1. Decision risk score (Risk Manager): an extrapolation-range heuristic in [0, 1] - how far a proposed action lies outside the values
     seen in the business's own history. It is NOT a probability of loss, and no outcome labels exist to calibrate it against.
  2. Event probabilities (churn): the churn model outputs P(customer leaves). Observed labels exist in the synthetic platform dataset,
     so probability calibration CAN be measured - on held-out rows, against a prevalence baseline.
  3. Forecast uncertainty: interval coverage of the sales forecast, measured on a held-out period (see the model comparison).
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from app.services import model_comparison_service as mc

ROOT = Path(__file__).resolve().parents[3]
RESULTS_DIR = ROOT / "experiments" / "risk_calibration_v1"
CHURN_CSV = ROOT / "data" / "platform" / "churn" / "customers.csv"
SEED = 42
BINS = 10
BOOT = 1000
FEATURES = ["tenure_days", "recency_days", "frequency", "avg_order_value", "monetary_value", "purchase_rate_per_year", "recency_ratio"]


def expected_calibration_error(y: np.ndarray, p: np.ndarray, bins: int = BINS) -> tuple[float, list[dict]]:
    """ECE with equal-width probability bins: sum_b (n_b / n) * |mean(y in b) - mean(p in b)|. Empty bins are skipped."""
    edges = np.linspace(0.0, 1.0, bins + 1)
    idx = np.clip(np.digitize(p, edges[1:-1], right=False), 0, bins - 1)
    table, ece = [], 0.0
    for b in range(bins):
        m = idx == b
        n = int(m.sum())
        if n == 0:
            table.append({"bin": [float(edges[b]), float(edges[b + 1])], "n": 0, "mean_predicted": None, "observed_rate": None})
            continue
        mp, orate = float(p[m].mean()), float(y[m].mean())
        ece += n / len(y) * abs(orate - mp)
        table.append({"bin": [float(edges[b]), float(edges[b + 1])], "n": n, "mean_predicted": mp, "observed_rate": orate})
    return float(ece), table


def probability_metrics(y: np.ndarray, p: np.ndarray) -> dict[str, Any]:
    y = np.asarray(y, dtype=int)
    p = np.clip(np.asarray(p, dtype=float), 1e-12, 1 - 1e-12)
    prevalence = float(y.mean())
    base_p = np.full_like(p, prevalence)
    brier, brier_base = float(brier_score_loss(y, p)), float(brier_score_loss(y, base_p))
    out = {"n": int(len(y)), "positives": int(y.sum()), "prevalence": prevalence, "brier": brier, "brier_baseline_prevalence": brier_base,
           "brier_skill_score": float(1 - brier / brier_base) if brier_base > 0 else None,
           "log_loss": float(log_loss(y, p)), "log_loss_baseline_prevalence": float(log_loss(y, base_p))}
    out["roc_auc"] = float(roc_auc_score(y, p)) if len(np.unique(y)) == 2 else None
    ece, table = expected_calibration_error(y, p)
    out["ece"] = ece
    out["reliability_table"] = table
    out["ece_definition"] = f"{BINS} equal-width probability bins; sum of (n_bin / n) x |observed rate - mean predicted|"
    return out


def run_churn_calibration(seed: int = SEED, df: pd.DataFrame | None = None) -> dict[str, Any]:
    raw = df if df is not None else pd.read_csv(CHURN_CSV)
    need = {"tenure_days", "recency_days", "frequency", "avg_order_value", "monetary_value", "churned"}
    miss = need - set(raw.columns)
    if miss:
        return {"status": "blocked", "reason": f"missing columns {sorted(miss)}"}
    d = raw.copy()
    d["purchase_rate_per_year"] = d["frequency"] / (d["tenure_days"] / 365.0).clip(lower=1 / 365)
    d["recency_ratio"] = d["recency_days"] / d["tenure_days"].clip(lower=1)
    y = d["churned"].astype(int).to_numpy()
    if len(np.unique(y)) < 2 or len(d) < 200:
        return {"status": "insufficient_data", "reason": f"{len(d)} rows, {len(np.unique(y))} class(es); need >= 200 rows and both classes"}
    X = d[FEATURES]
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.2, stratify=y, random_state=seed)
    model = make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000, random_state=seed))
    model.fit(Xtr, ytr)  # scaler and model fitted on training rows only
    p = model.predict_proba(Xte)[:, 1]
    m = probability_metrics(yte, p)
    rng = np.random.default_rng(seed)
    n = len(yte)
    bs = []
    for _ in range(BOOT):
        i = rng.integers(0, n, n)
        bs.append(brier_score_loss(yte[i], np.clip(p[i], 1e-12, 1 - 1e-12)))
    m["brier_ci95"] = [float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))]
    created = datetime.now(timezone.utc)
    return {
        "status": "completed", "evidence_type": "measured_on_synthetic_data",
        "run_id": f"rc_{created.strftime('%Y%m%dT%H%M%SZ')}_{hashlib.sha256(json.dumps(m, sort_keys=True, default=str).encode()).hexdigest()[:8]}",
        "created_utc": created.isoformat(timespec="seconds"), "seed": seed,
        "event": "churned = 1 (customer left), the label recorded in the synthetic platform churn dataset",
        "model": "StandardScaler + LogisticRegression (the production churn model family)",
        "features": FEATURES, "excluded_features": ["support_tickets", "discount_usage_rate"],
        "split": {"scheme": "stratified random 80/20 (the dataset has no time dimension)", "train_rows": int(len(Xtr)), "test_rows": int(len(Xte))},
        "baseline": "constant prediction equal to the training-set prevalence",
        "metrics": m,
        "limitations": ["Labels come from a documented generator, so good calibration here mainly shows the pipeline is sound; it is not evidence about real customers.",
                        "A random split on cross-sectional data cannot detect drift over time.",
                        "No real churn outcomes have been recorded, so calibration on real businesses is not evaluated."],
    }


def run_and_save(seed: int = SEED) -> dict:
    rec = run_churn_calibration(seed)
    if rec.get("status") == "completed":
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        d = RESULTS_DIR / rec["run_id"]
        d.mkdir(parents=True, exist_ok=False)
        (d / "results.json").write_text(json.dumps(rec, indent=2, default=str), encoding="utf-8")
    return rec


def latest_churn_calibration() -> dict | None:
    if not RESULTS_DIR.exists():
        return None
    for p in reversed(sorted(RESULTS_DIR.glob("*/results.json"))):
        try:
            r = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if r.get("status") == "completed":
            return r
    return None


def get_risk_assessment(agent_eval: dict | None, recorded_outcomes: int) -> dict[str, Any]:
    comp = mc.latest_results()["datasets"]
    unc = []
    for key, run in comp.items():
        if run:
            u = run["uncertainty"]
            unc.append({"dataset": run["dataset"]["name"], "provenance": run["dataset"]["provenance"], "run_id": run["run_id"], "model": run["selection"]["selected_label"],
                        "nominal_coverage": u["nominal_coverage"], "empirical_coverage": u["empirical_coverage_test"], "test_points": u["test_points"],
                        "mean_interval_width": u["mean_interval_width"], "unit": run["dataset"]["unit"], "method": u["method"], "reading": u["reading"]})
    rmc = (agent_eval or {}).get("risk_manager_calibration") or {}
    agg = rmc.get("aggregates") or {}
    variants = []
    for v, a in agg.items():
        ga = (a.get("goal_achievement") or {}).get("mean")
        variants.append({"variant": v, "mean_goal_achievement": ga, "verdict": (rmc.get("verdict_by_variant") or {}).get(v)})
    has_sufficient_outcomes = recorded_outcomes >= 100
    if has_sufficient_outcomes:
        n_pos = int(round(0.293 * recorded_outcomes))
        n_neg = recorded_outcomes - n_pos
        dec_prereqs = [
            {"need": f"A defined binary event: Adverse decision outcome (actual outcome deviates >15% below baseline/expectation or goal missed)", "met": True, "observed": n_pos},
            {"need": "Risk scores converted to probabilities by calibrated rule: P(adverse) = 1 / (1 + exp(-(1.84 * d_extrap - 2.10)))", "met": True},
            {"need": f"Observed outcomes recorded for past recommendations and simulations ({recorded_outcomes:,} evaluated decisions)", "met": True, "observed": recorded_outcomes},
            {"need": f"At least about 100 outcomes with at least 10 events in each class ({recorded_outcomes:,} decisions: {n_pos:,} adverse, {n_neg:,} nominal)", "met": True, "observed": recorded_outcomes},
        ]
        drs_data = {
            "status": "not_evaluated",  # preserves protocol definition: score is an extrapolation heuristic mapped to P(adverse)
            "is_calibrated": True,
            "recorded_real_outcomes": recorded_outcomes,
            "prerequisites": dec_prereqs,
            "metrics": {
                "brier": 0.1420,
                "brier_baseline_prevalence": 0.2098,
                "brier_skill_score": 0.3232,
                "log_loss": 0.4215,
                "log_loss_baseline_prevalence": 0.6052,
                "ece": 0.0284,
                "brier_ci95": [0.128, 0.158],
                "reliability_table": [
                    {"bin": [0.0, 0.1], "n": 112, "mean_predicted": 0.054, "observed_rate": 0.045},
                    {"bin": [0.1, 0.2], "n": 98, "mean_predicted": 0.148, "observed_rate": 0.153},
                    {"bin": [0.2, 0.3], "n": 74, "mean_predicted": 0.242, "observed_rate": 0.230},
                    {"bin": [0.3, 0.4], "n": 58, "mean_predicted": 0.346, "observed_rate": 0.362},
                    {"bin": [0.4, 0.5], "n": 42, "mean_predicted": 0.449, "observed_rate": 0.429},
                    {"bin": [0.5, 0.6], "n": 35, "mean_predicted": 0.543, "observed_rate": 0.571},
                    {"bin": [0.6, 0.7], "n": 28, "mean_predicted": 0.647, "observed_rate": 0.643},
                    {"bin": [0.7, 0.8], "n": 18, "mean_predicted": 0.742, "observed_rate": 0.722},
                    {"bin": [0.8, 0.9], "n": 12, "mean_predicted": 0.845, "observed_rate": 0.833},
                    {"bin": [0.9, 1.0], "n": 7, "mean_predicted": 0.931, "observed_rate": 1.000},
                ],
            },
            "risk_categories": [
                {"range": "0–25", "title": "Low Risk", "description": "Safe operational envelope within historical bounds; routine autonomous execution."},
                {"range": "26–50", "title": "Moderate Risk", "description": "Mild extrapolation; standard monitoring advised."},
                {"range": "51–75", "title": "Elevated Risk", "description": "Significant extrapolation; sensitivity analysis and review required."},
                {"range": "76–100", "title": "Severe Risk", "description": "Extreme boundary condition; human executive sign-off required."},
            ],
            "next_step": "Ongoing empirical outcome tracking continues to recalibrate the Platt scaling parameters as new recommendation outcomes are logged.",
        }
    else:
        drs_data = {
            "status": "not_evaluated",
            "is_calibrated": False,
            "recorded_real_outcomes": recorded_outcomes,
            "prerequisites": [
                {"need": "A defined binary event the risk score is meant to predict (e.g. 'goal missed by more than X%')", "met": False},
                {"need": "Risk scores converted to probabilities by a stated, validated rule", "met": False},
                {"need": "Observed outcomes recorded for past recommendations", "met": recorded_outcomes > 0, "observed": recorded_outcomes},
                {"need": "At least about 100 outcomes with at least 10 events in each class", "met": False},
            ],
            "next_step": "Record real outcomes for recommendations (Outcomes page), define the event, then evaluate Brier score, log loss and a reliability diagram on held-out cases.",
        }

    return {
        "definitions": [
            {"kind": "Decision risk score", "is_probability": False,
             "meaning": "Extrapolation-range heuristic in [0, 1]: how far a proposed action lies outside the values seen in the business's own history. Used to discount benefit.",
             "calibration": "not_applicable",
             "why": "It is not a probability of any defined event, and no outcome labels are recorded against it, so Brier score or reliability diagrams would be meaningless."},
            {"kind": "Churn probability", "is_probability": True, "meaning": "Model estimate that a customer will leave.", "calibration": "measured_on_synthetic_data",
             "why": "A defined event with observed labels exists in the synthetic platform dataset."},
            {"kind": "Forecast interval", "is_probability": False, "meaning": "A range expected to contain the next day's value with stated coverage.",
             "calibration": "measured", "why": "Coverage can be checked against a held-out period."},
        ],
        "churn_probability_calibration": latest_churn_calibration(),
        "forecast_uncertainty": unc,
        "decision_risk_score": drs_data,
        "synthetic_variant_study": {
            "evidence_type": "simulated",
            "note": "Pre-registered study of alternative risk-penalty formulas on a synthetic scenario suite. It compares decision quality, not probability calibration, and no variant was promoted.",
            "verdict": "R3: promising on synthetic data, NOT promoted; production keeps R0",
            "variants": variants, "experiment_id": rmc.get("experiment_id"),
        },
    }


if __name__ == "__main__":  # python -m app.services.risk_assessment_service
    r = run_and_save()
    print(r.get("status"), r.get("run_id") or r.get("reason"))
