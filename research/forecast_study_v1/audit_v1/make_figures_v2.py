"""Figures for MANUSCRIPT_v2 -> manuscript/figures_v2/*.svg (new directory; the v1 figures are untouched). Reads stored analysis.json and the audit's work/*.json only."""
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

sys.path.insert(0, str(Path(__file__).parent))
import ind_core as ic  # noqa: E402

OUT = ic.STUDY / "manuscript" / "figures_v2"
OUT.mkdir(parents=True, exist_ok=True)
W = Path(__file__).parent / "work"
s4, s5 = ic.jload(W / "step4.json"), ic.jload(W / "step5.json")
plt.rcParams.update({"font.size": 9, "axes.spines.top": False, "axes.spines.right": False, "svg.fonttype": "none"})
M, B, G = "#1f5fa8", "#b36b00", "#6b6b6b"
NAME = {"fs1_m5_ca1_H28": "M5 CA_1\nH=28", "fs1_m5_ca1_H7": "M5 CA_1\nH=7", "fs1_m5_tx1_H28": "M5 TX_1\nH=28", "fs1_m5_tx1_H7": "M5 TX_1\nH=7", "fs1_or2_top100_H28": "OR II\nH=28", "fs1_or2_top100_H7": "OR II\nH=7"}
CELLS = ic.CELLS

# Fig 1: forest plot of H1 / H2
fig, ax = plt.subplots(figsize=(6.4, 4.0))
for i, c in enumerate(CELLS):
    a = ic.jload(ic.RES / c / "analysis.json")
    for key, col, off, lab in (("H1_vs_matched_reference", M, -0.12, "vs best matched-information baseline (H1)"), ("H2_vs_any_reference", B, 0.12, "vs best baseline of any information set (H2)")):
        r = a[key]
        ax.errorbar(100 * r["estimate"], i + off, xerr=[[100 * (r["estimate"] - r["ci95"][0])], [100 * (r["ci95"][1] - r["estimate"])]], fmt="o", color=col, capsize=2.5, ms=4, label=lab if i == 0 else None)
ax.axvline(0, color=G, lw=0.8)
ax.axvline(2, color=G, lw=0.8, ls=":")
ax.set_yticks(range(len(CELLS)), [NAME[c].replace("\n", ", ") for c in CELLS])
ax.invert_yaxis()
ax.set_xlabel("Relative improvement in pooled item-day WAPE of the primary model (%)\nnegative = the baseline is better; dotted line = 2% minimum relevant gain")
ax.legend(frameon=False, loc="lower center", bbox_to_anchor=(0.5, 1.0), fontsize=7.5)
fig.tight_layout()
fig.savefig(OUT / "fig1_forest.svg")
plt.close(fig)

# Fig 2: the same forecasts scored at four aggregation levels
levels = [("pooled_wape", "item-day"), ("item_week_wape", "item-week"), ("subset_week_aggregate_wape", "subset-week"), ("subset_day_aggregate_wape", "subset-day")]
fig, axes = plt.subplots(2, 3, figsize=(7.4, 4.6), sharey=False)
for ax, c in zip(axes.ravel(), CELLS):
    x = range(len(levels))
    ax.bar([i - 0.2 for i in x], [s4[c]["model"][k] for k, _ in levels], 0.4, color=M, label="primary model (LightGBM, Tweedie)")
    ax.bar([i + 0.2 for i in x], [s4[c]["matched_median_reference"][k] for k, _ in levels], 0.4, color=B, label="best matched baseline (trailing 28-day median)")
    ax.set_xticks(list(x), [n for _, n in levels], fontsize=7, rotation=20)
    ax.set_title(NAME[c].replace("\n", ", "), fontsize=8.5)
axes[0, 0].set_ylabel("WAPE")
axes[1, 0].set_ylabel("WAPE")
h, l = axes[0, 0].get_legend_handles_labels()
fig.legend(h, l, frameon=False, fontsize=7.5, loc="lower center", ncol=2)
fig.tight_layout(rect=(0, 0.06, 1, 1))
fig.savefig(OUT / "fig2_aggregation_ladder.svg")
plt.close(fig)

# Fig 3: segment effects (exploratory)
fig, axes = plt.subplots(1, 2, figsize=(7.4, 2.9), sharex=True)
for ax, c in zip(axes, ("fs1_m5_ca1_H28", "fs1_m5_tx1_H28")):
    a = ic.jload(ic.RES / c / "analysis.json")
    segs = [(s, v) for s, v in a["segments"].items() if "vs_matched" in v and s.startswith(("frequency", "volume"))]
    for i, (s, v) in enumerate(segs):
        r = v["vs_matched"]
        ax.errorbar(100 * r["estimate"], i, xerr=[[100 * (r["estimate"] - r["ci95"][0])], [100 * (r["ci95"][1] - r["estimate"])]], fmt="o", color=M, capsize=2.5, ms=4)
    ax.axvline(0, color=G, lw=0.8)
    ax.set_yticks(range(len(segs)), [f"{s.replace('_or_sparse', '')} (n={v['n_series']})" for s, v in segs], fontsize=7)
    ax.invert_yaxis()
    ax.set_title(NAME[c].replace("\n", ", ") + " (exploratory)", fontsize=8.5)
    ax.set_xlabel("relative pooled-WAPE improvement vs matched baseline (%)", fontsize=7.5)
fig.tight_layout()
fig.savefig(OUT / "fig3_segments.svg")
plt.close(fig)

# Fig 4: conformal coverage overall vs zero-demand vs positive-demand rows
fig, ax = plt.subplots(figsize=(6.6, 3.2))
w = 0.26
x = range(len(CELLS))
for k, (key, lab, col) in enumerate((("coverage_overall", "all rows", G), ("coverage_on_zero_demand_rows", "rows with zero demand", B), ("coverage_on_positive_demand_rows", "rows with positive demand", M))):
    ax.bar([i + (k - 1) * w for i in x], [s5[c]["model"][key] for c in CELLS], w, color=col, label=lab)
ax.axhline(0.8, color="k", lw=0.8, ls="--")
ax.set_xticks(list(x), [NAME[c] for c in CELLS], fontsize=7.5)
ax.set_ylabel("empirical coverage of the nominal 80% interval")
ax.set_ylim(0, 1.2)
ax.legend(frameon=False, fontsize=7.5, loc="upper center", ncol=3)
fig.tight_layout()
fig.savefig(OUT / "fig4_coverage_zero_positive.svg")
plt.close(fig)
print("wrote", sorted(p.name for p in OUT.glob("*.svg")))
