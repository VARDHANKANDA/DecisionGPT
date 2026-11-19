"""Tables (Markdown) and figures (SVG) generated only from the stored ``analysis.json`` / ``results.json`` files: ``python -m research.forecast_study_v1.make_report``.

Writes ``results/TABLES.md`` and ``manuscript/figures/fig*.svg``. Nothing is typed by hand.
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

D = Path(__file__).resolve().parent
RES = D / "results"
FIG = D / "manuscript" / "figures"
CELLS = [f"fs1_{d}_H{h}" for d in ("m5_ca1", "m5_tx1", "or2_top100") for h in (28, 7)]
LABEL = {"m5_ca1": "M5 CA_1", "m5_tx1": "M5 TX_1", "or2_top100": "Online Retail II"}
plt.rcParams.update({"font.size": 9, "axes.spines.top": False, "axes.spines.right": False, "svg.fonttype": "none"})
C_MODEL, C_BASE, C_NEG = "#1f5fa8", "#b36b00", "#6b6b6b"


def name(c):
    p = c.split("_")
    ds = "_".join(p[1:-1])
    return f"{LABEL[ds]}, H={p[-1][1:]}"


def load():
    return {c: json.load(open(RES / c / "analysis.json", encoding="utf-8")) for c in CELLS if (RES / c / "analysis.json").exists()}


def f(x, p=3):
    return "n/a" if x is None else f"{x:.{p}f}"


def tables(A):
    L = ["# Generated tables (make_report.py)", ""]
    L += ["## T1. Primary model and references: pooled vs store-day aggregate WAPE and bias", "",
          "| cell | method | pooled WAPE | store-day aggregate WAPE | rel. bias | MAE | RMSE |", "|---|---|---|---|---|---|---|"]
    for c, a in A.items():
        for role, k in (("primary model", a["primary"]), ("best matched baseline", a["reference_matched"]), ("best baseline (any info)", a["reference_any"])):
            if role == "best baseline (any info)" and a["reference_any"] == a["reference_matched"]:
                continue
            t = a["table"][k]
            L.append(f"| {name(c)} | {role}: {k.split('__', 1)[1].replace('__', ':')} | {f(t['wape'])} | {f(t['aggregate_wape'])} | {f(t['rel_bias'])} | {f(t['mae'])} | {f(t['rmse'])} |")
    L += ["", "## T2. Bootstrap designs for H1 (relative WAPE improvement vs matched reference)", "", "| cell | crossed series x week [95% CI] | stationary weeks [95% CI] | series-only (historical) [95% CI] | crossed/series-only width |", "|---|---|---|---|---|"]
    for c, a in A.items():
        b = a["bootstrap_designs_vs_matched"]
        cell = lambda r: f"{100 * r['estimate']:.1f}% [{100 * r['ci95'][0]:.1f}, {100 * r['ci95'][1]:.1f}]"  # noqa: E731
        L.append(f"| {name(c)} | {cell(b['crossed'])} | {cell(b['stationary_weeks'])} | {cell(b['series_only_historical'])} | {f(b['ci_width_ratio_crossed_over_series_only'], 2)} |")
    L += ["", "## T3. Rank agreement between pooled and store-day aggregate WAPE (21 methods)", "", "| cell | Kendall tau | p | best by pooled WAPE | best by aggregate WAPE |", "|---|---|---|---|---|"]
    for c, a in A.items():
        k = a["kendall_tau_pooled_vs_aggregate"]
        L.append(f"| {name(c)} | {f(k['tau'], 2)} | {f(k['p'], 3)} | {a['ranking_pooled_wape'][0].split('__', 1)[1]} | {a['ranking_aggregate_wape'][0].split('__', 1)[1]} |")
    L += ["", "## T4. Segments (exploratory): improvement of the primary model over the matched reference, 95% crossed CI", "", "| cell | segment | n series | WAPE model | WAPE matched ref | rel. improvement [95% CI] |", "|---|---|---|---|---|---|"]
    for c, a in A.items():
        for s, v in a["segments"].items():
            if "vs_matched" in v:
                r = v["vs_matched"]
                L.append(f"| {name(c)} | {s} | {v['n_series']} | {f(v['wape_model'])} | {f(v['wape_matched_reference'])} | {100 * r['estimate']:.1f}% [{100 * r['ci95'][0]:.1f}, {100 * r['ci95'][1]:.1f}] |")
            else:
                L.append(f"| {name(c)} | {s} | {v['n_series']} | - | - | not estimated (<20 series) |")
    L += ["", "## T5. 80% Mondrian split-conformal coverage (calibrated on validation predictions of the same method)", "", "| cell | method | overall coverage | mean width | min / max coverage over test blocks | frequent / intermittent coverage |", "|---|---|---|---|---|---|"]
    for c, a in A.items():
        for who, v in a["conformal_80"].items():
            if "overall" not in v:
                continue
            bb = list(v["coverage_by_test_block"].values())
            fr = v["by_frequency_segment"]
            L.append(f"| {name(c)} | {who} | {f(v['overall']['coverage'])} | {f(v['overall']['mean_width'], 2)} | {f(min(bb))} / {f(max(bb))} | "
                     f"{f(fr.get('frequent', {}).get('coverage'))} / {f(fr.get('intermittent_or_sparse', {}).get('coverage'))} |")
    L += ["", "## T6. Leave-one-origin-out relative improvement vs matched reference (headline estimate with each block removed)", "", "| cell | " + " | ".join(f"drop {i + 1}" for i in range(6)) + " |", "|---|" + "---|" * 6]
    for c, a in A.items():
        L.append(f"| {name(c)} | " + " | ".join(f"{100 * v:.1f}%" for v in a["leave_one_origin_out_improvement_vs_matched"].values()) + " |")
    (RES / "TABLES.md").write_text("\n".join(L) + "\n", encoding="utf-8")


def extra_tables():
    """S2 (classification), E1 (post-hoc L1) and H5 (ablations) tables, from stored JSON only."""
    L = ["", "# S2: customer inactivity (PROXY label: no invoice in the following 90 days; not churn)", ""]
    p = RES / "s2_online_retail_inactivity" / "results.json"
    if p.exists():
        r = json.load(open(p, encoding="utf-8"))
        L += ["## S2a. Discrimination, calibration and threshold metrics on the test snapshot (primary model chosen on validation PR-AUC)", "",
              "| origin | method | ROC-AUC | PR-AUC | log-loss | Brier | Brier skill vs prevalence | ECE (10 equal-width) | ECE (10 equal-mass) | top-decile lift |", "|---|---|---|---|---|---|---|---|---|---|"]
        for o, v in r["origins"].items():
            m = v["selection"]["primary_model"]
            for var in ("raw", "platt", "isotonic"):
                t = v["models"][m][var]["test"]
                L.append(f"| {o} (test prevalence {t['prevalence']:.3f}) | {m} ({var}) | {f(t['roc_auc'])} | {f(t['pr_auc'])} | {f(t['log_loss'])} | {f(t['brier'])} | {f(t['brier_skill_vs_prevalence'])} | {f(t['ece_10_equal_width'])} | {f(t['ece_10_equal_mass'])} | {f(t['top_decile_lift'], 2)} |")
            b = v["selection"]["best_baseline"]
            t = v["baselines"][b]["test"]
            L.append(f"| {o} | baseline {b} (rank score) | {f(t['roc_auc'])} | {f(t['pr_auc'])} | - | - | - | - | - | {f(t['top_decile_lift'], 2)} |")
            L.append(f"| {o} | constant score (majority/prevalence) | 0.500 | {f(t['prevalence'])} | - | - | - | - | - | 1.00 |")
        L += ["", "## S2b. One validation-chosen threshold (maximum F1) applied to the test snapshot", "", "| origin | method | threshold | precision | recall | F1 | accuracy | majority-class accuracy | TP | FP | FN | TN |", "|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for o, v in r["origins"].items():
            m = v["selection"]["primary_model"]
            for lab, a in ((f"{m} (raw)", v["models"][m]["raw"]["test_at_threshold"]), (f"{m} (Platt)", v["models"][m]["platt"]["test_at_threshold"]), (v["selection"]["best_baseline"], v["baselines"][v["selection"]["best_baseline"]]["test_at_threshold"])):
                c = a["confusion"]
                L.append(f"| {o} | {lab} | {f(a['threshold'], 3)} | {f(a['precision'])} | {f(a['recall'])} | {f(a['f1'])} | {f(a['accuracy'])} | {f(v['majority_class_baseline']['test_accuracy'])} | {c['tp']} | {c['fp']} | {c['fn']} | {c['tn']} |")
        L += ["", "## S2c. Paired difference primary model minus best baseline (customer bootstrap, B=2000) and Holm over 4 tests", "", "| origin | model | baseline | metric | difference | 95% CI | raw p | Holm p |", "|---|---|---|---|---|---|---|---|"]
        for o, v in r["origins"].items():
            for mname in ("roc_auc", "pr_auc"):
                x = v["paired_primary_minus_best_baseline"][mname]
                hp = r["confirmatory"]["holm_p"][f"{o}:{mname}"]
                L.append(f"| {o} | {v['selection']['primary_model']} | {v['selection']['best_baseline']} | {mname} | {x['difference']:+.4f} | [{x['ci95'][0]:+.4f}, {x['ci95'][1]:+.4f}] | {'<0.001' if x['p_two_sided'] < 0.001 else f(x['p_two_sided'])} | {'<0.001' if hp < 0.001 else f(hp)} |")
        L.append(f"\nDecision per metric under the pre-registered rule: {r['confirmatory']['decision_per_metric']}.")
        L += ["", "## S2d. All four classifiers, uncalibrated test ROC-AUC / PR-AUC", "", "| origin | " + " | ".join(r["origins"]["A"]["models"]) + " |", "|---|" + "---|" * len(r["origins"]["A"]["models"])]
        for o, v in r["origins"].items():
            L.append(f"| {o} | " + " | ".join(f"{v['models'][m]['raw']['test']['roc_auc']:.3f} / {v['models'][m]['raw']['test']['pr_auc']:.3f}" for m in v["models"]) + " |")
    p = RES / "S2_customer_disjoint.json"
    if p.exists():
        r = json.load(open(p, encoding="utf-8"))
        L += ["", "## S2e. Customer-disjoint sensitivity (random 50/50 customer split; model and baseline fixed from the main run)", "", "| origin | rows train / val / test | model ROC-AUC | baseline ROC-AUC | diff ROC-AUC [95% CI] | diff PR-AUC [95% CI] |", "|---|---|---|---|---|---|"]
        for o, v in r["origins"].items():
            a, b = v["paired_model_minus_baseline"]["roc_auc"], v["paired_model_minus_baseline"]["pr_auc"]
            L.append(f"| {o} | {v['rows']['train']} / {v['rows']['validation']} / {v['rows']['test']} | {f(v['test_roc_auc'])} | {f(v['baseline_roc_auc'])} | {a['difference']:+.4f} [{a['ci95'][0]:+.4f}, {a['ci95'][1]:+.4f}] | {b['difference']:+.4f} [{b['ci95'][0]:+.4f}, {b['ci95'][1]:+.4f}] |")
    L += ["", "# H5: feature-group ablations (EXPLORATORY; M5 CA_1, H=28, no re-tuning)", ""]
    p = RES / "ABLATIONS_fs1_m5_ca1_H28.json"
    if p.exists():
        r = json.load(open(p, encoding="utf-8"))
        L += ["| removed group | features removed | WAPE full | WAPE ablated | change when removed | 95% CI of full-vs-ablated improvement | Holm p |", "|---|---|---|---|---|---|---|"]
        for k, v in r["ablations"].items():
            L.append(f"| {k.split('_ablate_')[1]} | {len(v['removed_groups'])} | {f(v['wape_full'])} | {f(v['wape_ablated'])} | {100 * v['relative_change_when_removed']:+.2f}% | [{100 * v['full_vs_ablated']['ci95'][0]:+.2f}, {100 * v['full_vs_ablated']['ci95'][1]:+.2f}]% | {'<0.001' if v['holm_p'] < 0.001 else f(v['holm_p'])} |")
    L += ["", "# E1: POST-HOC exploratory: same LightGBM with the L1 (median) objective, no validation selection", "", "| cell | method | pooled WAPE | store-day aggregate WAPE | rel. bias | L1 vs matched ref [95% CI] | L1 vs any-info ref [95% CI] | L1 vs Tweedie primary [95% CI] |", "|---|---|---|---|---|---|---|---|"]
    for c in ("fs1_m5_ca1_H28", "fs1_m5_tx1_H28", "fs1_or2_top100_H28"):
        p = RES / f"E1_l1_{c}.json"
        if not p.exists():
            continue
        r = json.load(open(p, encoding="utf-8"))
        ci = lambda x: f"{100 * x['estimate']:+.1f}% [{100 * x['ci95'][0]:+.1f}, {100 * x['ci95'][1]:+.1f}]"  # noqa: E731
        for who, lab in (("l1_model", "LightGBM L1 (post-hoc)"), ("tweedie_primary", "LightGBM Tweedie (primary)"), ("ref_matched", "matched median baseline")):
            t = r["table"][who]
            tail = f"{ci(r['l1_vs_matched_reference'])} | {ci(r['l1_vs_any_reference'])} | {ci(r['l1_vs_tweedie_primary'])}" if who == "l1_model" else "| |"
            L.append(f"| {name(c)} | {lab} | {f(t['wape'])} | {f(t['aggregate_wape'])} | {f(t['rel_bias'])} | {tail} |" if who == "l1_model" else f"| {name(c)} | {lab} | {f(t['wape'])} | {f(t['aggregate_wape'])} | {f(t['rel_bias'])} | | | |")
    with open(RES / "TABLES.md", "a", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")


def fig_forest(A):
    fig, ax = plt.subplots(figsize=(6.4, 4.0))
    ys, lab = [], []
    for i, (c, a) in enumerate(A.items()):
        for j, (key, col, off) in enumerate((("H1_vs_matched_reference", C_MODEL, -0.12), ("H2_vs_any_reference", C_BASE, 0.12))):
            r = a[key]
            ax.errorbar(100 * r["estimate"], i + off, xerr=[[100 * (r["estimate"] - r["ci95"][0])], [100 * (r["ci95"][1] - r["estimate"])]], fmt="o", color=col, capsize=2.5, ms=4,
                        label=("vs matched-information reference (H1)" if key.startswith("H1") else "vs best baseline of any information set (H2)") if i == 0 else None)
        lab.append(name(c))
    ax.axvline(0, color=C_NEG, lw=0.8)
    ax.axvline(2, color=C_NEG, lw=0.8, ls=":")
    ax.set_yticks(range(len(lab)), lab)
    ax.invert_yaxis()
    ax.set_xlabel("Relative improvement in pooled WAPE of the primary model (%)\nnegative = the baseline is better; dotted line = 2% minimum relevant gain")
    ax.legend(frameon=False, loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=1, fontsize=7.5)
    fig.tight_layout()
    fig.savefig(FIG / "fig1_forest.svg")
    plt.close(fig)


def fig_metric_reversal(A):
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.1), sharey=False)
    for ax, key, title in ((axes[0], "wape", "Item-day pooled WAPE"), (axes[1], "aggregate_wape", "Store-day aggregate WAPE")):
        x = range(len(A))
        w = 0.38
        ax.bar([i - w / 2 for i in x], [a["table"][a["primary"]][key] for a in A.values()], w, color=C_MODEL, label="primary model (LightGBM)")
        ax.bar([i + w / 2 for i in x], [a["table"][a["reference_matched"]][key] for a in A.values()], w, color=C_BASE, label="best matched baseline")
        ax.set_xticks(list(x), [name(c).replace("Online Retail II", "OR II").replace(", ", "\n") for c in A], fontsize=7)
        ax.set_title(title, fontsize=9)
    axes[0].set_ylim(0, 1.2)
    axes[0].legend(frameon=False, fontsize=7.5, loc="upper left")
    axes[0].set_ylabel("WAPE (lower is better)")
    fig.tight_layout()
    fig.savefig(FIG / "fig2_metric_reversal.svg")
    plt.close(fig)


def fig_segments(A):
    a = A.get("fs1_m5_ca1_H28")
    if not a:
        return
    segs = [(s, v) for s, v in a["segments"].items() if "vs_matched" in v and s.startswith(("frequency", "volume"))]
    fig, ax = plt.subplots(figsize=(5.4, 2.8))
    for i, (s, v) in enumerate(segs):
        r = v["vs_matched"]
        ax.errorbar(100 * r["estimate"], i, xerr=[[100 * (r["estimate"] - r["ci95"][0])], [100 * (r["ci95"][1] - r["estimate"])]], fmt="o", color=C_MODEL, capsize=2.5, ms=4)
    ax.axvline(0, color=C_NEG, lw=0.8)
    ax.set_yticks(range(len(segs)), [f"{s.replace('_or_sparse', '')} (n={v['n_series']})" for s, v in segs], fontsize=8)
    ax.invert_yaxis()
    ax.set_xlabel("Relative WAPE improvement vs matched reference (%), M5 CA_1, H=28 (exploratory)")
    fig.tight_layout()
    fig.savefig(FIG / "fig3_segments.svg")
    plt.close(fig)


def fig_coverage(A):
    fig, ax = plt.subplots(figsize=(5.4, 2.9))
    for c, a in A.items():
        m = a["conformal_80"].get("model", {})
        if "coverage_by_test_block" in m:
            ax.plot(range(1, 7), list(m["coverage_by_test_block"].values()), marker="o", ms=3, lw=1, label=name(c))
    ax.axhline(0.8, color=C_NEG, lw=0.8, ls="--")
    ax.set_xlabel("Test block (forecast origin)")
    ax.set_ylabel("Empirical coverage of 80% interval")
    ax.legend(frameon=False, fontsize=6.5, ncol=2)
    fig.tight_layout()
    fig.savefig(FIG / "fig4_coverage.svg")
    plt.close(fig)


def main():
    FIG.mkdir(parents=True, exist_ok=True)
    A = load()
    tables(A)
    extra_tables()
    fig_forest(A)
    fig_metric_reversal(A)
    fig_segments(A)
    fig_coverage(A)
    print("tables + 4 figures written for", len(A), "cells")


if __name__ == "__main__":
    main()
