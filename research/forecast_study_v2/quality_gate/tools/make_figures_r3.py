"""Figures new in R3 (generated from stored artifacts) -> quality_gate/figures/*.svg|png|pdf.
    python research/forecast_study_v2/quality_gate/tools/make_figures_r3.py"""
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

HERE = Path(__file__).resolve().parents[2]
QG = HERE / "quality_gate"
FIG = QG / "figures"
FIG.mkdir(exist_ok=True)
V3 = HERE.parent / "forecast_study_v3_fresh_stats" / "results"
NAME = {"m5_ca1": "CA_1", "m5_tx1": "TX_1", "m5_wi1": "WI_1", "or2": "Online Retail II", "m5_ca2": "CA_2", "m5_tx2": "TX_2", "m5_wi2": "WI_2"}
plt.rcParams.update({"font.size": 9, "axes.spines.top": False, "axes.spines.right": False, "svg.fonttype": "none"})


def save(fig, name):
    for ext in ("svg", "png", "pdf"):
        fig.savefig(FIG / f"{name}.{ext}", dpi=200 if ext == "png" else None, bbox_inches="tight")
    plt.close(fig)


def lab(c):
    k, H = c.rsplit("_H", 1)
    return f"{NAME[k]} H={H}"


def fig_pinball():
    s = json.loads((QG / "results" / "audit_sensitivity.json").read_text(encoding="utf-8"))["C_pinball_exploratory"]
    taus = ["0.5", "0.7", "0.8", "0.9"]
    fig, axes = plt.subplots(1, 2, figsize=(9.5, 3.8), sharey=True)
    for ax, H in zip(axes, ("28", "7")):
        for i, (c, r) in enumerate(s.items()):
            if not c.endswith("_H" + H):
                continue
            y = [100 * r[t]["improvement"] for t in taus]
            ax.plot([float(t) for t in taus], y, marker="o", ms=3.5, lw=1.2, label=lab(c).replace(f" H={H}", ""))
        ax.axhline(0, color="#6b6b6b", lw=0.8)
        ax.set_title(f"H = {H}", fontsize=9)
        ax.set_xlabel("pinball level τ")
        ax.set_xticks([0.5, 0.7, 0.8, 0.9])
    axes[0].set_ylabel("improvement over best matched baseline (%)")
    axes[1].legend(frameon=False, fontsize=7, loc="lower left")
    fig.tight_layout()
    save(fig, "figR3_pinball")


def fig_v3():
    a = V3 / "analysis" / "analysis_W4.json"
    if not a.exists():
        return
    cells = json.loads(a.read_text(encoding="utf-8"))["cells"]
    fig, axes = plt.subplots(1, 3, figsize=(10, 3.2), sharey=True)
    for ax, (h, title) in zip(axes, (("H1", "H1: vs best matched baseline (expanded set)"), ("H1b", "H1b: vs best baseline, any information"), ("H3", "H3: subset-day, vs best matched baseline"))):
        for y, (c, v) in enumerate(cells.items()):
            r = v[h]
            if "primary" not in r:
                continue
            lo, hi = r["primary"]["ci95"]
            ax.errorbar(100 * r["improvement"], y, xerr=[[100 * (r["improvement"] - lo)], [100 * (hi - r["improvement"])]], fmt="o", color="#1f5fa8", capsize=2, ms=3.5)
        ax.axvline(0, color="#6b6b6b", lw=0.8)
        ax.axvline(2, color="#6b6b6b", lw=0.8, ls=":")
        ax.set_title(title, fontsize=8)
        ax.set_xlabel("relative improvement (%), 95% CI")
    axes[0].set_yticks(range(len(cells)), [lab(c) for c in cells], fontsize=7)
    axes[0].invert_yaxis()
    fig.tight_layout()
    save(fig, "figR3_v3_forest")


if __name__ == "__main__":
    fig_pinball()
    fig_v3()
    print(sorted(p.name for p in FIG.glob("*.png")))
