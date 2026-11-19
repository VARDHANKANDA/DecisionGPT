"""Tables of manuscript R3 that are NEW relative to R2, generated from stored artifacts (no hand-typed numbers) -> quality_gate/tables/*.md|csv.
Sources: quality_gate/results/{audit_sensitivity,e1_reproduction,e2_selection_robustness}.json and forecast_study_v3_fresh_stats/results/analysis/*.json (each table is written only if its source exists).

    python research/forecast_study_v2/quality_gate/tools/build_tables_r3.py
"""
import csv
import json
from pathlib import Path

HERE = Path(__file__).resolve().parents[2]            # forecast_study_v2
QG = HERE / "quality_gate"
OUT = QG / "tables"
OUT.mkdir(exist_ok=True)
V3 = HERE.parent / "forecast_study_v3_fresh_stats" / "results"
NAME = {"m5_ca1": "CA_1", "m5_tx1": "TX_1", "m5_wi1": "WI_1", "or2": "Online Retail II", "m5_ca2": "CA_2", "m5_tx2": "TX_2", "m5_wi2": "WI_2"}
MODEL = {"lgbm_l1": "absolute error", "lgbm_l1_small": "absolute error (small)", "lgbm_quantile50": "0.5 quantile", "lgbm_l2": "squared error", "lgbm_tweedie_p11": "Tweedie 1.1", "lgbm_tweedie_p15": "Tweedie 1.5", "xgb_l1": "XGBoost absolute error", "ridge_a100": "ridge"}
VERD = {"SUPPORTED": "supported", "INCONCLUSIVE": "inconclusive", "CONTRADICTED": "contradicted"}
MI = "−"


def pct(x, d=1):
    return f"{100 * x:+.{d}f} %".replace("-", MI)


def ci(c, d=1):
    return f"[{100 * c[0]:+.{d}f}, {100 * c[1]:+.{d}f}]".replace("-", MI)


def fp(x, d=3):
    return "<0.001" if x < 0.0005 else f"{x:.{d}f}"


def cell(c):
    k, H = c.rsplit("_H", 1)
    return f"{NAME[k]} H{H}"


def write(name, header, rows, source, caption):
    with open(OUT / f"{name}.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    md = [f"**{caption}**", "", "| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"] + ["| " + " | ".join(str(x) for x in r) + " |" for r in rows] + ["", f"*Source: {source}.*", ""]
    (OUT / f"{name}.md").write_text("\n".join(md), encoding="utf-8")


def load(p):
    p = Path(p)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def main():
    s = load(QG / "results" / "audit_sensitivity.json")
    if s:
        rows = []
        for c, r in s["A_weekly_dependence"]["W2"].items():
            st = r["H1_stationary_weeks"]
            rows.append([cell(c), f"{r['lag1_weekly_difference']:+.2f}".replace("-", MI), f"{r['ar1_effective_weeks']:.1f}", ci(r["frozen_ci_H1"]), ci(st["ci95"]), fp(st["holm_p"], 4), VERD[st["verdict_frozen_rule"]], VERD[r["frozen"]["H1"]]])
        write("tR3_dependence_W2", ["cell", "lag-1 autocorr. of weekly differences", "AR(1) effective weeks (of 24)", "H1 interval, frozen method", "H1 interval, stationary-block weeks", "Holm p (sensitivity)", "verdict (sensitivity, frozen rule)", "verdict (frozen analysis)"], rows,
              "`quality_gate/results/audit_sensitivity.json` (A); exploratory sensitivity analysis, not a replacement of the frozen result", "Table R3-1. Weekly dependence of the item-day comparison and a stationary-block-week bootstrap sensitivity analysis (W2, H1)")
        n_same = sum(1 for w in s["A_weekly_dependence"].values() for r in w.values() if r["H1_stationary_weeks"]["verdict_frozen_rule"] == r["frozen"]["H1"])
        n_all = sum(len(w) for w in s["A_weekly_dependence"].values())
        n_h2 = sum(1 for w in s["A_weekly_dependence"].values() for r in w.values() if r["H2_stationary_weeks"] and r["H2_stationary_weeks"]["verdict_frozen_rule"] == r["frozen"]["H2"])
        n_h2_all = sum(1 for w in s["A_weekly_dependence"].values() for r in w.values() if r["H2_stationary_weeks"])
        (OUT / "dependence_counts.json").write_text(json.dumps({"H1_same": n_same, "H1_all": n_all, "H2_same": n_h2, "H2_all": n_h2_all, "max_lag1": max(r["lag1_weekly_difference"] for w in s["A_weekly_dependence"].values() for r in w.values())}), encoding="utf-8")
        rows = []
        for k, r in s["B_selection_margins"].items():
            if not k.startswith("W2/"):
                continue
            i, a = r["item_day"], r["subset_day"]
            rows.append([cell(k.split("/")[1]), MODEL[i["selected"]], MODEL[i["runner_up"]], f"{100 * i['relative_margin']:.2f} %", f"{r['matched_baseline_item_day']['relative_margin'] * 100:.2f} %", MODEL[a["selected"]], MODEL[a["runner_up"]], f"{100 * a['relative_margin']:.2f} %"])
        write("tR3_selection_margins_W2", ["cell", "item-day: selected", "item-day: runner-up", "relative validation margin", "margin between best and second-best matched baseline", "subset-day: selected", "subset-day: runner-up", "relative validation margin"], rows,
              "`quality_gate/results/audit_sensitivity.json` (B), from the stored validation tables of `selection.json`", "Table R3-2. Validation-stage margins between the selected model and its runner-up (W2, mean over three validation blocks)")
        rows = []
        for c, r in s["C_pinball_exploratory"].items():
            rows.append([cell(c)] + [f"{pct(r[t]['improvement'])} {ci(r[t]['ci95'])}" for t in ("0.5", "0.7", "0.8", "0.9")])
        write("tR3_pinball_W2", ["cell", "tau = 0.5 (= absolute error)", "tau = 0.7", "tau = 0.8", "tau = 0.9"], rows, "`quality_gate/results/audit_sensitivity.json` (C); crossed bootstrap B = 2,000, no multiplicity control; exploratory",
              "Table R3-3. Pinball-loss improvement of the item-day-selected model over the best matched baseline when under-forecasting is penalised more (W2; illustrative, no cost data)")
    e1 = load(QG / "results" / "e1_reproduction.json")
    if e1:
        rows = [[c, r["selection_identical"], r["methods_compared"], f"{r['max_abs_diff_metrics']:.2e}", f"{r['max_abs_diff_forecasts']:.2e}", "identical" if r["verdicts_identical"] else "DIFFERENT"] for c, r in e1["cells"].items()]
        write("tR3_reproduction", ["window / cell", "selection identical", "method summaries compared", "max abs. diff. of metrics", "max abs. diff. of stored forecasts", "verdicts recomputed from re-run"], rows, "`quality_gate/results/e1_reproduction.json` (re-run in a fresh pinned environment into a scratch directory)", "Table R3-4. Clean-environment reproduction of all cells")
    e2 = load(QG / "results" / "e2_selection_robustness.json")
    if e2:
        rows = []
        for c, r in e2.items():
            cand = {k: v["item_day_improvement_vs_matched_baseline"] for k, v in r["candidates"].items()}
            lg = [cand[k] for k in ("lgbm_l1", "lgbm_l1_small", "lgbm_quantile50")]
            mean_t = [cand[k] for k in ("lgbm_tweedie_p11", "lgbm_tweedie_p15", "lgbm_l2", "ridge_a100")]
            rows.append([cell(c), MODEL[r["selected_item_day"]], pct(r["selected_item_day_improvement"]), f"{r['selected_item_day_test_rank']} / 8", MODEL[r["test_rank_item_day"][0]],
                         f"{pct(min(lg))} … {pct(max(lg))}", pct(cand["xgb_l1"]), f"{pct(min(mean_t))} … {pct(max(mean_t))}"])
        write("tR3_selection_robustness_W2", ["cell", "validation-selected model", "its test improvement", "its test rank among 8 (item-day WAPE)", "best on test (hindsight)", "range over the three LightGBM median-type candidates", "XGBoost absolute error", "range over the four mean-type candidates"], rows,
              "`quality_gate/results/e2_selection_robustness.json`; post-hoc, exploratory: all eight candidates refit on the six W2 test blocks, improvement over the same validation-selected matched item-day baseline", "Table R3-5. Selection robustness on the confirmatory window (item-day WAPE improvement over the best matched baseline)")
    a3 = load(V3 / "analysis" / "analysis_W4.json")
    x3 = load(V3 / "analysis" / "analysis3_W4_extra.json")
    if a3 and x3:
        rows = []
        for c, v in a3["cells"].items():
            e = x3[c]
            h1, h1b, h2, h3 = v["H1"], v["H1b"], v["H2"], v["H3"]
            rows.append([cell(c), MODEL[v["selection"]["model_item_day"]], v["selection"]["baseline_item_day_matched"].replace("matched__", "").replace("_", " "), f"{h1['wape_reference']:.3f} / {h1['wape_model']:.3f}", f"{pct(h1['improvement'])} {ci(h1['primary']['ci95'])}", fp(h1["holm_p"], 4), f"{h1['blocks_won']}/6", VERD[h1["verdict"]],
                         f"{VERD[h1b['verdict']]} ({pct(h1b['improvement'])})", f"{VERD[h2['verdict']] if 'verdict' in h2 else 'n/a'}" + (f" ({pct(h2['improvement'])})" if "improvement" in h2 else ""), f"{pct(e['H1_orig']['improvement'])} ({VERD[e['H1_orig']['verdict']]})",
                         f"{VERD[h3['verdict']]} ({pct(h3['improvement'])})"])
        write("tR3_v3_main", ["cell", "item-day model", "best matched baseline (expanded set)", "WAPE baseline / model", "H1 improvement [95 % CI]", "Holm p", "blocks won", "H1 (primary)", "H1b", "H2", "H1-orig (31 simple baselines only)", "H3"], rows,
              "`forecast_study_v3_fresh_stats/results/analysis/analysis_W4.json`, `analysis3_W4_extra.json`; separate confirmatory family on fresh stores and a fresh window", "Table R3-6. Fresh-window study (v3): stores CA_2, TX_2, WI_2, window W4")
        rows = []
        for c, e in x3.items():
            d = e["descriptive_item_day_wape"]
            rows.append([cell(c), f"{d['model']:.3f}", f"{d['best_matched_original31']:.3f}", f"{d['best_matched_expanded']:.3f}"] + [f"{d[n]:.3f}" for n in ("matched__ets", "matched__arima", "matched__theta", "fresh__ets", "fresh__arima", "fresh__theta")] + [f"{e['lag1_weekly_difference_H1']:+.2f}".replace("-", MI)])
        write("tR3_v3_statistical", ["cell", "model (item-day WAPE)", "best simple matched baseline", "best matched baseline, expanded set", "matched ETS", "matched ARIMA", "matched Theta", "fresh ETS", "fresh ARIMA", "fresh Theta", "lag-1 autocorr. of weekly differences (H1)"], rows,
              "`forecast_study_v3_fresh_stats/results/analysis/analysis3_W4_extra.json` (descriptive item-day WAPE on the six test blocks)", "Table R3-7. Fresh-window study (v3): item-day WAPE of the statistical baselines")
    print(sorted(p.name for p in OUT.glob("*.md")))


if __name__ == "__main__":
    main()
