"""Generate every manuscript table from stored result artifacts (no hand-typed numbers) -> tables/*.md and tables/*.csv.

Sources: results/analysis/analysis_{W2,W3,W1}.json, results/summary_extra.json, results/supplementary/h3_convergence.json.

    python research/forecast_study_v2/tools/build_tables.py
"""
import csv
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
R = HERE / "results"
OUT = HERE / "tables"
OUT.mkdir(exist_ok=True)
NAME = {"m5_ca1": "CA_1", "m5_tx1": "TX_1", "m5_wi1": "WI_1", "or2": "Online Retail II"}
MODEL = {"lgbm_l1": "absolute error", "lgbm_l1_small": "absolute error (small)", "lgbm_quantile50": "0.5 quantile", "lgbm_l2": "squared error", "lgbm_tweedie_p11": "Tweedie 1.1", "lgbm_tweedie_p15": "Tweedie 1.5"}
VERD = {"SUPPORTED": "supported", "INCONCLUSIVE": "inconclusive", "CONTRADICTED": "contradicted"}
A = {w: json.loads((R / "analysis" / f"analysis_{w}.json").read_text(encoding="utf-8")) for w in ("W2", "W3", "W1")}
SUP = json.loads((R / "supplementary" / "h3_convergence.json").read_text(encoding="utf-8"))["windows"]
EXTRA = json.loads((R / "summary_extra.json").read_text(encoding="utf-8"))


def base(n):
    n = n.split("__", 1)[1]
    k = n.rstrip("0123456789")
    return k.replace("_", " ") + " " + n[len(k):]


def cell(c, v):
    return f"{NAME[v['dataset']]} H{v['H']}"


def fp(x, d=3):
    return "<0.001" if x < 0.0005 else f"{x:.{d}f}"


def pct(x, d=1):
    return f"{100 * x:+.{d}f} %".replace("-", "−")


def ci(c, d=1):
    return f"[{100 * c[0]:+.{d}f}, {100 * c[1]:+.{d}f}]".replace("-", "−")


def write(name, header, rows, source, caption):
    with open(OUT / f"{name}.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    md = [f"**{caption}**", "", "| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"] + ["| " + " | ".join(str(x) for x in r) + " |" for r in rows] + ["", f"*Source: {source}; CSV: `tables/{name}.csv`.*", ""]
    (OUT / f"{name}.md").write_text("\n".join(md), encoding="utf-8")


def table2():
    rows = []
    for c, v in A["W2"]["cells"].items():
        h1, h1b, h2, s = v["H1"], v["H1b"], v["H2"], v["selection"]
        rows.append([cell(c, v), base(s["baseline_item_day_matched"]), f"{h1['wape_reference']:.3f} / {h1['wape_model']:.3f}", f"{pct(h1['improvement'])} {ci(h1['primary']['ci95'])}", fp(h1['holm_p'], 4), f"{h1['blocks_won']}/6", VERD[h1["verdict"]],
                     f"{VERD[h1b['verdict']]} ({pct(h1b['improvement'])})", f"{VERD[h2['verdict']]} ({pct(h2['improvement'])})"])
    write("table2_h1_W2", ["cell", "best matched baseline", "WAPE baseline / model", "improvement [95 % CI]", "Holm p", "blocks won", "H1", "H1b: vs best any-information baseline", "H2: vs original Tweedie 1.1 model"], rows,
          "`results/analysis/analysis_W2.json` (H1, H1b, H2)", "Table 2. Item-day endpoint, window W2 (confirmatory): item-day-selected model (absolute-error LightGBM in all cells) versus the best matched baseline")


def table3():
    rows = []
    for c, v in A["W2"]["cells"].items():
        h, s = v["H3"], v["selection"]
        g = SUP["W2"][c]["converged"]
        rows.append([cell(c, v), MODEL[s["model_subset_day"]], base(s["baseline_subset_day_matched"]), f"{h['wape_reference']:.3f} / {h['wape_model']:.3f}", f"{pct(h['improvement'])} {ci(h['primary']['ci95'])}", f"{fp(h['holm_p'])} / {fp(h['holm_p_secondary'])}", f"{h['blocks_won']}/6", VERD[h["verdict"]], f"{fp(g['holm_primary'])} / {fp(g['holm_secondary'])}"])
    write("table3_h3_W2", ["cell", "model", "best matched baseline", "WAPE baseline / model", "improvement [95 % CI]", "frozen Holm p primary / secondary", "blocks won", "verdict (frozen rule)", "supplementary converged Holm p primary / secondary"], rows,
          "`results/analysis/analysis_W2.json` (H3); `results/supplementary/h3_convergence.json`", "Table 3. Subset-day endpoint, window W2 (confirmatory): subset-day-selected model versus the best matched baseline")


def table4():
    rows = []
    for w, lab in (("W2", "W2 (confirmatory)"), ("W3", "W3 (M5, independent replication)"), ("W1", "W1 (WI_1 fresh store; CA_1, TX_1, Online Retail II non-independent)")):
        k = EXTRA["counts"][w]
        f = lambda h: "/".join(str(k[h][x]) for x in ("SUPPORTED", "CONTRADICTED", "INCONCLUSIVE"))  # noqa: E731
        rows.append([lab, k["n_cells"], f("H1"), f("H1b"), f("H2"), f("H3"), f"{pct(k['median_H1_improvement'])} ({pct(k['range_H1_improvement'][0])} … {pct(k['range_H1_improvement'][1])})", f"{k['sign_H1_positive']}/{k['n_cells']}"])
    write("table4_replication", ["window", "cells", "H1 s/c/i", "H1b s/c/i", "H2 s/c/i", "H3 s/c/i", "median H1 improvement (range)", "H1 improvement > 0"], rows, "`results/summary_extra.json` (from `analysis_*.json`)", "Table 4. Verdict counts (supported / contradicted / inconclusive) by window; each window has its own Holm adjustment")


def table5():
    rows = []
    for c, v in A["W2"]["cells"].items():
        L, s = v["ladder"], v["selection"]
        for lab, key in (("absolute-error model (item-day winner)", "pred__" + s["model_item_day"]), ("best item-day baseline", "base__" + s["baseline_item_day_matched"]), (f"{MODEL[s['model_subset_day']]} model (subset-day winner)", "pred__" + s["model_subset_day"]), ("best subset-day baseline", "base__" + s["baseline_subset_day_matched"])):
            m = L[key]
            rows.append([cell(c, v), lab, f"{m['item_day_wape']:.3f}", f"{m['item_week_wape']:.3f}", f"{m['subset_week_wape']:.3f}", f"{m['subset_day_wape']:.3f}", f"{m['rel_bias']:+.3f}".replace("-", "−"), f"{m['zero_forecast_share']:.2f}"])
    write("table5_ladder_W2", ["cell", "method", "item-day WAPE", "item-week WAPE", "subset-week WAPE", "subset-day WAPE", "relative bias", "share of zero forecasts"], rows, "`results/analysis/analysis_W2.json` (`ladder`)", "Table 5. Aggregation ladder and bias, window W2, all cells")


def table6():
    r = SUP["W2"]["m5_tx1_H28"]
    f, g, d = r["frozen"], r["converged"], r["diagnostics"]
    rows = [["raw p, primary (iid-week bootstrap)", f"{f['p_primary']:.4f}", f"{g['iid']['p_mean']:.4f} (seed SD {g['iid']['p_seed_sd']:.4f})"], ["raw p, secondary (stationary bootstrap)", f"{f['p_secondary']:.4f}", f"{g['stationary']['p_mean']:.4f} (seed SD {g['stationary']['p_seed_sd']:.4f})"],
            ["Holm p, primary", f"{f['holm_primary']:.4f}", f"{g['holm_primary']:.4f}"], ["Holm p, secondary", f"{f['holm_secondary']:.4f}", f"{g['holm_secondary']:.4f}"], ["verdict under the frozen dual-method rule", VERD[f["verdict"]], VERD[g["verdict_dual_rule"]]],
            ["exact sign-flip test (unadjusted p; different statistic)", "–", f"{r['signflip_exact']['p_two_sided']:.4f}"], ["weeks in which the model has the smaller absolute total error", "–", f"{d['weeks_model_better']}/{d['n_weeks']}"], ["lag-1 autocorrelation of the weekly differences / AR(1) effective weeks", "–", f"{d['lag1_autocorr_of_weekly_difference']:+.2f} / {d['ar1_effective_weeks']:.1f}"]]
    write("table6_tx1_h28_h3", ["quantity", "frozen run (B = 10,000)", "supplementary (3 × 10^6 draws)"], rows, "`results/analysis/analysis_W2.json`; `results/supplementary/h3_convergence.json`", "Table 6. W2, TX_1, H = 28, subset-day (H3): frozen result and supplementary convergence check")


def table_a1():
    rows = []
    for w in ("W3", "W1"):
        for c, v in A[w]["cells"].items():
            h1, s = v["H1"], v["selection"]
            rows.append([w, cell(c, v), MODEL[s["model_item_day"]], base(s["baseline_item_day_matched"]), f"{h1['wape_reference']:.3f} / {h1['wape_model']:.3f}", f"{pct(h1['improvement'])} {ci(h1['primary']['ci95'])}", f"{h1['holm_p']:.4f}", f"{h1['blocks_won']}/6", VERD[h1["verdict"]], VERD[v["H3"]["verdict"]] + f" ({pct(v['H3']['improvement'])})"])
    write("tableA1_replication_H1", ["window", "cell", "item-day model", "best matched baseline", "WAPE baseline / model", "H1 improvement [95 % CI]", "Holm p", "blocks won", "H1", "H3 (improvement)"], rows, "`results/analysis/analysis_W3.json`, `analysis_W1.json`", "Table A1. Replication windows W3 and W1: item-day (H1) and subset-day (H3) results")


def table_a2():
    rows = []
    for c, v in A["W2"]["cells"].items():
        s = v["seed_sensitivity"]
        x = [s["seed42"], s["seed43"], s["seed44"]]
        rows.append([cell(c, v)] + [pct(q, 2) for q in x] + [f"{100 * (max(x) - min(x)):.2f} pp"])
    write("tableA2_seeds", ["cell", "seed 42 (frozen primary)", "seed 43", "seed 44", "range"], rows, "`results/analysis/analysis_W2.json` (`seed_sensitivity`)", "Table A2. Seed sensitivity of the W2 item-day improvement (H1)")


def table_a3():
    rows = []
    for c, v in A["W2"]["cells"].items():
        for k, x in v["segments_exploratory"].items():
            if "improvement" in x:
                rows.append([cell(c, v), k, x["n_series"], f"{pct(x['improvement'])} {ci(x['ci95'])}"])
    write("tableA3_segments", ["cell", "segment", "series", "item-day improvement vs matched baseline [95 % CI]"], rows, "`results/analysis/analysis_W2.json` (`segments_exploratory`; B = 2,000, no multiplicity control)", "Table A3 (exploratory). Segment results, window W2")


def table_a4():
    rows = []
    for c, v in A["W2"]["cells"].items():
        e = EXTRA["design_effects_W2"][c]
        rows.append([cell(c, v), e["series"], e["weekly_blocks"], e["cells"], f"{e['design_effect_se']:.1f}", f"{e['effective_independent_cells_approx']:.0f}"])
    write("tableA4_design_effect", ["cell", "series", "weekly blocks", "series-week cells", "design effect on the s.e.", "approx. effective independent cells"], rows, "`results/summary_extra.json` (`design_effects_W2`)", "Table A4. Design effect of the crossed series × week structure (H1 comparison, W2)")


if __name__ == "__main__":
    for f in (table2, table3, table4, table5, table6, table_a1, table_a2, table_a3, table_a4):
        f()
    print(sorted(p.name for p in OUT.glob("*.md")))
