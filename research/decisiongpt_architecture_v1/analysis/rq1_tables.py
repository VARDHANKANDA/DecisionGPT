"""Analysis D (protocol section 6): RQ1 predictive-performance tables, generated from STORED results only (no model is retrained).

    python research/decisiongpt_architecture_v1/analysis/rq1_tables.py

Sources (read-only): experiments/ml_benchmark_v1/{f1,f2,c1,c2}_*/results.json, backend/dev.db (models.lifecycle_json['reevaluation'], opened read-only; produced by the verified re-scoring service).
Writes results/rq1_summary.json and overleaf/architecture_paper_v1/tables/tab_rq1_*.tex.
"""
from __future__ import annotations

import glob
import json
import sqlite3
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
BM = REPO / "experiments" / "ml_benchmark_v1"
TAB = REPO / "overleaf" / "architecture_paper_v1" / "tables"
RES = REPO / "research" / "decisiongpt_architecture_v1" / "results"
TAB.mkdir(parents=True, exist_ok=True)


def run(prefix: str) -> dict:
    p = sorted(glob.glob(str(BM / f"{prefix}_*" / "results.json")))
    if prefix == "c2":
        p = [x for x in p if "ec3d89a4" in x]                # the non-superseded C2 run
    assert len(p) == 1, (prefix, p)
    return json.loads(Path(p[0]).read_text(encoding="utf-8")) | {"_run_dir": Path(p[0]).parent.name}


def tex_escape(s: str) -> str:
    return s.replace("_", r"\_").replace("%", r"\%").replace("&", r"\&")


def write(name: str, caption: str, label: str, header: list[str], rows: list[list[str]], colspec: str, note: str = "") -> None:
    lines = [r"\begin{table}[t]", r"\centering", rf"\caption{{{caption}}}", rf"\label{{{label}}}", r"\footnotesize", rf"\begin{{tabular}}{{{colspec}}}", r"\toprule",
             " & ".join(header) + r" \\", r"\midrule"] + [" & ".join(r) + r" \\" for r in rows] + [r"\bottomrule", r"\end{tabular}"]
    if note:
        lines += [rf"\par\vspace{{2pt}}{{\scriptsize {note}}}"]
    lines += [r"\end{table}"]
    (TAB / name).write_text("\n".join(lines) + "\n", encoding="utf-8")


def f(x, d=3):
    return "--" if x is None else f"{x:.{d}f}"


def main() -> None:
    S: dict = {}
    # ---- F1: M5 CA_1, item-day, 28-day direct horizon
    f1 = run("f1")
    t = f1["test"]
    S["f1"] = {"run": f1["_run_dir"], "n_series": f1["n_series"], "n_points": f1["n_test_points"], "selected": f1["validation_selected_method"], "test": {k: {m: v.get(m) for m in ("wape", "mae", "rmse", "aggregate_daily_wape", "bias")} for k, v in t.items()}}
    order = ["baseline:seasonal_naive_28", "baseline:same_weekday_mean4", "linear:ols", "xgboost:depth6", "lightgbm:tweedie", "catboost:depth6", "ensemble:nnls_weighted"]
    label = {"baseline:seasonal_naive_28": "Seasonal naive ($t{-}28$)", "baseline:same_weekday_mean4": "Same-weekday mean (4 wk)", "linear:ols": "Linear (OLS)", "xgboost:depth6": "XGBoost (depth 6)",
             "lightgbm:tweedie": "LightGBM (Tweedie)", "catboost:depth6": "CatBoost (depth 6)$^\\dagger$", "ensemble:nnls_weighted": "Ensemble (NNLS)"}
    rows = [[label[k], f(t[k]["wape"]), f(t[k]["mae"]), f(t[k]["rmse"]), f(t[k]["aggregate_daily_wape"])] for k in order]
    pc = f1["paired_test_comparisons"]["catboost:depth6 vs baseline:seasonal_naive_28"]
    S["f1"]["catboost_vs_seasonal_naive"] = {"diff": pc["difference_a_minus_b"], "ci95": pc["ci95"]}
    write("tab_rq1_m5.tex", "RQ1: daily unit demand, M5 store CA\\_1 (350 series, 9\\,800 test item-days, direct 28-day horizon). WAPE and error in units/item-day; the last column is WAPE of the store-total series. "
          "$\\dagger$ validation-selected model. Lower is better.", "tab:rq1m5", ["Model", "WAPE", "MAE", "RMSE", "WAPE (store total)"], rows, "lcccc",
          f"CatBoost minus seasonal naive, WAPE: {pc['difference_a_minus_b']:+.3f} (95\\% series-cluster bootstrap CI [{pc['ci95'][0]:+.3f}, {pc['ci95'][1]:+.3f}]). "
          "At store-total level the simple same-weekday mean is the best method.")

    # ---- F2b: Online Retail II top-20 SKUs
    f2 = run("f2")
    t2 = f2["top20_sku_daily_units"]["test"]
    S["f2b"] = {"run": f2["_run_dir"], "n_series": f2["top20_sku_daily_units"]["n_series"], "n_points": f2["top20_sku_daily_units"]["n_test_points"], "selected": f2["top20_sku_daily_units"]["validation_selected_method"],
                "test": {k: {m: v.get(m) for m in ("wape", "mae", "rmse", "aggregate_daily_wape")} for k, v in t2.items()}}
    S["f2a"] = {"test": {k: {m: v.get(m) for m in ("wape", "mae", "rmse", "bias")} for k, v in f2["total_daily_revenue"]["test"].items()}, "n_points": f2["total_daily_revenue"]["n_test_points"]}
    ord2 = ["baseline:seasonal_naive", "baseline:same_weekday_mean4", "linear:ols", "xgboost:depth4", "lightgbm:tweedie", "catboost:depth8", "ensemble:nnls_weighted"]
    lab2 = {"baseline:seasonal_naive": "Seasonal naive", "baseline:same_weekday_mean4": "Same-weekday mean (4 wk)", "linear:ols": "Linear (OLS)", "xgboost:depth4": "XGBoost (depth 4)",
            "lightgbm:tweedie": "LightGBM (Tweedie)$^\\dagger$", "catboost:depth8": "CatBoost (depth 8)", "ensemble:nnls_weighted": "Ensemble (NNLS)"}
    rows = [[lab2[k], f(t2[k]["wape"]), f(t2[k]["rmse"], 1), f(t2[k]["aggregate_daily_wape"])] for k in ord2]
    write("tab_rq1_retail.tex", "RQ1: daily units of the top-20 SKUs of a single UK online retailer (Online Retail II; 20 series, 560 test item-days, 28 test days). "
          "$\\dagger$ validation-selected. No family wins on every dataset (compare Table~\\ref{tab:rq1m5}).", "tab:rq1retail", ["Model", "WAPE", "RMSE", "WAPE (total)"], rows, "lccc")

    # ---- churn / inactivity
    c1, c2 = run("c1"), run("c2")
    def crow(res, key, name):
        m = res["models"][key]["uncalibrated"]["test"]
        return [name, f(m["roc_auc"], 4), f(m["pr_auc"], 4), f(m["brier"], 4), f(m["ece"], 3)]
    names = [("logistic_regression", "Logistic regression"), ("random_forest", "Random forest"), ("xgboost", "XGBoost"), ("catboost", "CatBoost"), ("soft_voting", "Soft voting"), ("stacking_logistic_meta", "Stacking")]
    rows = [[r[0] + " (C1)"] + r[1:] for r in (crow(c1, k, n) for k, n in names)] + [[r[0] + " (C2)"] + r[1:] for r in (crow(c2, k, n) for k, n in [(k, n) for k, n in names if k in c2["models"]])]
    S["churn"] = {"c1_run": c1["_run_dir"], "c2_run": c2["_run_dir"], "c1": {k: c1["models"][k]["uncalibrated"]["test"] for k in c1["models"]}, "c2": {k: c2["models"][k]["uncalibrated"]["test"] for k in c2["models"]},
                  "c1_prevalence": c1["prevalence"], "c1_brier_prevalence_baseline": c1["models"]["random_forest"]["uncalibrated"]["test"]["brier_prevalence_baseline"],
                  "c1_paired_auc_vs_best_single": c1["paired_vs_best_single_by_validation_auc"], "c2_paired_auc_vs_best_single": c2["paired_vs_best_single_by_validation_auc"]}
    write("tab_rq1_churn.tex", "RQ1: customer-inactivity classification, test split, uncalibrated. C1: Online Retail II with a \\emph{proxy} label (no purchase in the following 90 days; not observed churn; "
          "5\\,256 test customers). C2: synthetic platform data with a known logistic generating mechanism (1\\,200 test rows). Prevalence-only Brier: 0.246 (C1), 0.248 (C2).",
          "tab:rq1churn", ["Model (dataset)", "ROC-AUC", "PR-AUC", "Brier", "ECE"], rows, "lcccc")

    # ---- registered production models re-scored from stored artifacts (read-only DB)
    con = sqlite3.connect(f"file:{(REPO / 'backend' / 'dev.db').as_posix()}?mode=ro", uri=True)
    reg = []
    for name, ver, life in con.execute("select model_name,version,lifecycle_json from models where model_type like 'forecasting%' order by model_name,version"):
        r = (json.loads(life or "{}")).get("reevaluation")
        row = {"model": name, "version": ver, "status": (r or {}).get("status", "not_run"), "reason": (r or {}).get("reason")}
        if r and r.get("status") == "evaluated":
            m, b = r["metrics"], r["baseline"]
            row |= {"wape": m.get("wape"), "mae": m.get("mae"), "rmse": m.get("rmse"), "baseline_wape": b.get("wape"), "baseline_name": b.get("name"), "improvement": r.get("improvement"), "n": m.get("n") or m.get("n_rows") or r.get("split", {}).get("n_test")}
        reg.append(row)
    S["registry_rescoring"] = reg
    rows = []
    for r in [x for x in reg if x["version"] == "v1"]:
        nm = tex_escape(f"{r['model'].replace('sales_forecast_', '')} {r['version']}")
        if r["status"] == "evaluated":
            rows.append([nm, f(r["wape"]), f(r["mae"], 2), f(r["rmse"], 2), f(r["baseline_wape"])])
        else:
            rows.append([nm, "\\multicolumn{4}{l}{" + ("not available (artifact missing)" if r["status"] == "unavailable" else "withheld: re-scoring did not reproduce the recorded metrics") + "}"])
    write("tab_rq1_registry.tex", "RQ1: registered production forecasting models, re-scored from their stored artifacts on the held-out chronological test block (1-day-ahead; baseline: previous day's value on the same rows). "
          "Trained on the synthetic platform file \\texttt{platform-forecasting-v1}, so this is \\emph{synthetic} evidence. A re-score is accepted only if it reproduces the recorded MAE, RMSE and MAPE (relative tolerance $10^{-6}$); all three did. Version-2 models, trained on a local upload of unrecorded provenance, are excluded (one failed verification, one artifact missing).",
          "tab:rq1registry", ["Model", "WAPE", "MAE", "RMSE", "Baseline WAPE"], rows, "lcccc")

    (RES / "rq1_summary.json").write_text(json.dumps(S, indent=1, default=str), encoding="utf-8")
    print("wrote tables:", sorted(p.name for p in TAB.glob("tab_rq1_*.tex")))
    for r in reg:
        print(r)


if __name__ == "__main__":
    main()
