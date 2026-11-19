"""Reporting for forecast_study_v2 (added after the freeze; reads stored analysis/results only). Produces METRIC_RESULTS.csv, MODEL_COMPARISON.csv, results/TABLES.md and figures.

    python -m research.forecast_study_v2.report
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from . import analysis as an  # noqa: E402
from .common import RESULTS, STUDY  # noqa: E402

FIG = STUDY / "figures"
NAME = {"m5_ca1": "M5 CA_1", "m5_tx1": "M5 TX_1", "m5_wi1": "M5 WI_1", "or2": "Online Retail II"}
WINDOWS = ("W2", "W3", "W1")
plt.rcParams.update({"font.size": 9, "axes.spines.top": False, "axes.spines.right": False, "svg.fonttype": "none"})
C = {"W2": "#1f5fa8", "W3": "#b36b00", "W1": "#6b6b6b"}


def save(fig, name):
    """svg (editable), png (markdown preview) and pdf (LaTeX)."""
    for ext in ("svg", "png", "pdf"):
        fig.savefig(FIG / f"{name}.{ext}", dpi=200 if ext == "png" else None, bbox_inches="tight")


def cells_of(window):
    return [(k, H) for k, H in an.CELL_KEYS if (RESULTS / window / f"{k}_H{H}" / "results.json").exists()]


def load_all():
    out = {}
    for w in WINDOWS:
        f = RESULTS / "analysis" / f"analysis_{w}.json"
        if f.exists():
            out[w] = json.loads(f.read_text(encoding="utf-8"))
    return out


def metric_rows(analyses):
    rows = []
    for w, a in analyses.items():
        for c, v in a["cells"].items():
            res = json.loads((RESULTS / w / c / "results.json").read_text(encoding="utf-8"))
            sel = v["selection"]
            roles = {f"pred__{sel['model_item_day']}": "model selected on item-day WAPE", f"pred__{sel['model_subset_day']}": "model selected on subset-day WAPE", f"pred__{sel['reference_model']}": "original reference model (Tweedie p=1.1)",
                     f"base__{sel['baseline_item_day_matched']}": "best matched baseline (item-day)", f"base__{sel['baseline_item_day_any']}": "best baseline any information (item-day)", f"base__{sel['baseline_subset_day_matched']}": "best matched baseline (subset-day)", "base__matched__zero": "all-zero forecast"}
            for m, s in res["summary"].items():
                if m in roles or m.startswith("seed"):
                    rows.append({"window": w, "cell": c, "method": m, "role": roles.get(m, "seed sensitivity"), **{k: s[k] for k in ("item_day_wape", "item_week_wape", "subset_week_wape", "subset_day_wape", "rel_bias", "mae", "rmse", "zero_forecast_share")},
                                 "item_day_wape_by_block": json.dumps(s["item_day_wape_by_block"])})
    return rows


def model_rows(analyses):
    rows = []
    for w, a in analyses.items():
        for c, v in a["cells"].items():
            for h in ("H1", "H1b", "H2", "H3"):
                r = v[h]
                if "primary" not in r:
                    rows.append({"window": w, "cell": c, "hypothesis": h, "note": r.get("not_applicable", "")})
                    continue
                sec = r.get("cgm_t") or r.get("secondary")
                rows.append({"window": w, "cell": c, "hypothesis": h, "model": v["selection"]["model_subset_day" if h == "H3" else "model_item_day"], "reference": {"H1": v["selection"]["baseline_item_day_matched"], "H1b": v["selection"]["baseline_item_day_any"],
                             "H2": v["selection"]["reference_model"], "H3": v["selection"]["baseline_subset_day_matched"]}[h], "wape_reference": r["wape_reference"], "wape_model": r["wape_model"], "improvement": r["improvement"],
                             "ci95_primary_lo": r["primary"]["ci95"][0], "ci95_primary_hi": r["primary"]["ci95"][1], "p_primary": r["primary"]["p"], "holm_p": r["holm_p"], "ci95_secondary_lo": sec["ci95"][0], "ci95_secondary_hi": sec["ci95"][1],
                             "holm_p_secondary": r["holm_p_secondary"], "blocks_won": r["blocks_won"], "verdict_primary": r["verdict_primary_method"], "verdict_secondary": r["verdict_secondary_method"], "verdict_final": r["verdict"], "methods_agree": r["methods_agree_on_verdict"]})
    return rows


def write_csv(path, rows):
    keys = list({k: 1 for r in rows for k in r})
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)


def fig_forest(analyses):
    FIG.mkdir(exist_ok=True)
    fig, axes = plt.subplots(1, 3, figsize=(10.5, 4.6), sharey=True)
    for ax, (h, title) in zip(axes, (("H1", "H1: item-day, vs best matched baseline"), ("H2", "H2: item-day, vs original Tweedie model"), ("H3", "H3: subset-day, vs best matched baseline"))):
        y = 0
        ticks, labs = [], []
        for w in WINDOWS:
            if w not in analyses:
                continue
            for c, v in analyses[w]["cells"].items():
                r = v[h]
                if "primary" not in r:
                    y += 1
                    continue
                lo, hi = r["primary"]["ci95"]
                ax.errorbar(100 * r["improvement"], y, xerr=[[100 * (r["improvement"] - lo)], [100 * (hi - r["improvement"])]], fmt="o", color=C[w], capsize=2, ms=3.5)
                ticks.append(y)
                labs.append(f"{w} {NAME[v['dataset']]} H={v['H']}")
                y += 1
            y += 0.6
        ax.axvline(0, color="#6b6b6b", lw=0.8)
        ax.axvline(2, color="#6b6b6b", lw=0.8, ls=":")
        ax.set_title(title, fontsize=8.5)
        ax.set_xlabel("relative improvement (%), 95% CI")
        if h == "H1":
            ax.set_yticks(ticks, labs, fontsize=6.5)
            ax.invert_yaxis()
    fig.tight_layout()
    save(fig, "fig1_forest")
    plt.close(fig)


def fig_ladder(analyses):
    if "W2" not in analyses:
        return
    cells = list(analyses["W2"]["cells"].items())
    fig, axes = plt.subplots(2, 4, figsize=(10.5, 5.2))
    levels = [("item_day_wape", "item-day"), ("item_week_wape", "item-week"), ("subset_week_wape", "subset-week"), ("subset_day_wape", "subset-day")]
    for ax, (c, v) in zip(axes.ravel(), cells):
        L = v["ladder"]
        sel = v["selection"]
        m = L[f"pred__{sel['model_item_day']}"]
        b = L[f"base__{sel['baseline_item_day_matched']}"]
        x = np.arange(len(levels))
        ax.bar(x - 0.2, [m[k] for k, _ in levels], 0.4, color=C["W2"], label="model (item-day selected)")
        ax.bar(x + 0.2, [b[k] for k, _ in levels], 0.4, color=C["W3"], label="best matched baseline")
        ax.set_xticks(x, [n for _, n in levels], fontsize=6.5, rotation=25)
        ax.set_title(f"{NAME[v['dataset']]} H={v['H']}", fontsize=8)
    h, l = axes[0, 0].get_legend_handles_labels()
    fig.legend(h, l, loc="lower center", ncol=2, frameon=False, fontsize=8)
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    save(fig, "fig2_aggregation_ladder_W2")
    plt.close(fig)


def fig_endpoint(analyses):
    fig, ax = plt.subplots(figsize=(4.8, 4.4))
    for w in WINDOWS:
        if w not in analyses:
            continue
        for c, v in analyses[w]["cells"].items():
            ax.scatter(100 * v["H1"]["improvement"], 100 * v["H3"]["improvement"], color=C[w], s=22, label=w if c == list(analyses[w]["cells"])[0] else None)
    ax.axhline(0, color="#6b6b6b", lw=0.8)
    ax.axvline(0, color="#6b6b6b", lw=0.8)
    ax.set_xlabel("item-day improvement, H1 (%)")
    ax.set_ylabel("subset-day improvement, H3 (%)")
    ax.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    save(fig, "fig3_endpoint_dependence")
    plt.close(fig)


def tables_md(analyses):
    L = ["# Generated tables (report.py)", ""]
    for w, a in analyses.items():
        L += [f"## Window {w}", "", "| cell | model (item-day) | best matched baseline | WAPE base / model | H1 improvement [95% CI] | Holm p | blocks won | verdict H1 | H1b | H2 | H3 verdict (subset-day improvement) |", "|---|---|---|---|---|---|---|---|---|---|---|"]
        for c, v in a["cells"].items():
            h1, h1b, h2, h3 = v["H1"], v["H1b"], v["H2"], v["H3"]
            L.append(f"| {NAME[v['dataset']]}, H={v['H']} | {v['selection']['model_item_day']} | {v['selection']['baseline_item_day_matched']} | {h1['wape_reference']:.3f} / {h1['wape_model']:.3f} | {100 * h1['improvement']:+.1f}% [{100 * h1['primary']['ci95'][0]:+.1f}, {100 * h1['primary']['ci95'][1]:+.1f}] | {h1['holm_p']:.3f} | {h1['blocks_won']}/6 | {h1['verdict']} | "
                     f"{h1b['verdict']} | {h2.get('verdict', 'n/a')} | {h3['verdict']} ({100 * h3['improvement']:+.1f}%) |")
        L.append("")
    return "\n".join(L)


def main():
    an_all = {w: an.analyse_window(w) for w in WINDOWS if cells_of(w)}
    mr, mo = metric_rows(an_all), model_rows(an_all)
    write_csv(STUDY / "METRIC_RESULTS.csv", mr)
    write_csv(STUDY / "MODEL_COMPARISON.csv", mo)
    (RESULTS / "TABLES.md").write_text(tables_md(an_all), encoding="utf-8")
    fig_forest(an_all)
    fig_ladder(an_all)
    fig_endpoint(an_all)
    print("windows:", list(an_all), "| metric rows:", len(mr), "| comparison rows:", len(mo))


if __name__ == "__main__":
    main()
