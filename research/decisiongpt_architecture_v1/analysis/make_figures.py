"""Figures for the paper, generated only from results/*.json (no hand-typed numbers).

    python research/decisiongpt_architecture_v1/analysis/make_figures.py
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import FancyBboxPatch

REPO = Path(__file__).resolve().parents[3]
RES = REPO / "research" / "decisiongpt_architecture_v1" / "results"
FIG = REPO / "overleaf" / "architecture_paper_v1" / "figures"
FIG.mkdir(parents=True, exist_ok=True)

C = {"A": "#7f7f7f", "B": "#0072B2", "C": "#009E73", "D": "#D55E00", "ref": "#999999"}
plt.rcParams.update({"font.size": 7.5, "axes.titlesize": 8, "axes.labelsize": 7.5, "xtick.labelsize": 7, "ytick.labelsize": 7, "legend.fontsize": 7,
                     "axes.spines.top": False, "axes.spines.right": False, "pdf.fonttype": 42, "ps.fonttype": 42, "font.family": "DejaVu Sans"})


def save(fig, name):
    fig.savefig(FIG / f"{name}.pdf", bbox_inches="tight")
    fig.savefig(FIG / f"{name}.png", dpi=200, bbox_inches="tight")
    plt.close(fig)


def fig_workflows():
    fig, ax = plt.subplots(figsize=(7.0, 2.45))
    ax.set_xlim(0, 100)
    ax.set_ylim(-3, 44)
    ax.axis("off")

    def box(x, y, w, h, txt, fc="#f2f2f2", ec="#444444", fs=7, bold=False):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.25,rounding_size=0.8", fc=fc, ec=ec, lw=0.8))
        ax.text(x + w / 2, y + h / 2, txt, ha="center", va="center", fontsize=fs, fontweight="bold" if bold else "normal", linespacing=1.15)

    def arrow(x1, y1, x2, y2):
        ax.annotate("", xy=(x2, y2), xytext=(x1, y1), arrowprops=dict(arrowstyle="-|>", lw=0.8, color="#444444", shrinkA=0, shrinkB=0))

    box(1, 14, 13, 12, "Business\nhistory\n(same for\nall workflows)", fc="#ffffff")
    box(19, 14, 15, 12, "Forecasting\nmodel\n(registered,\ndeterministic)", fc="#e8f1fa")
    box(39, 14, 17, 12, "Decision\nSimulation\n(model run per\ncandidate action)", fc="#e8f1fa")
    arrow(14.6, 20, 18.4, 20)
    arrow(34.6, 20, 38.4, 20)
    # workflow rows
    rows = [("A", 35, "A  no recommendation (scored as minimal action)", C["A"]),
            ("B", 26, "B  greedy: highest simulated KPI", C["B"]),
            ("C", 17, "C  B + one rule-based agent score", C["C"]),
            ("D", 8, "D  3 agents, 2 rounds, optimizer, risk gate", C["D"])]
    for k, y, txt, col in rows:
        ax.add_patch(FancyBboxPatch((61, y - 3.2), 38, 6.4, boxstyle="round,pad=0.2,rounding_size=0.8", fc="white", ec=col, lw=1.4))
        ax.text(62, y, txt, ha="left", va="center", fontsize=6.3)
    arrow(56.6, 23, 60.4, 26)
    arrow(56.6, 21, 60.4, 17)
    arrow(56.6, 19, 60.4, 8)
    ax.annotate("", xy=(60.4, 35), xytext=(34.8, 26.8), arrowprops=dict(arrowstyle="-|>", lw=0.8, color="#444444", connectionstyle="arc3,rad=-0.15"))
    ax.text(1, 42, "Every workflow receives the same simulated evidence and the same feasible action set; each choice is scored by an exogenous ground-truth objective.",
            fontsize=7, ha="left", va="center", style="italic")
    ax.text(1, -1.5, "Exogenous references (see ground-truth objective): oracle, naive, greedy, classical optimizer. No language model is called in any decision path.", fontsize=6.6, ha="left", color="#444444")
    save(fig, "fig1_workflows")


def fig_regret(dq):
    fig, axes = plt.subplots(1, 2, figsize=(7.0, 2.35), sharey=False)
    names = [("A", "A"), ("B", "B"), ("C", "C"), ("D", "D"), ("greedy", "greedy*"), ("classical", "classical*"), ("naive", "naive")]
    for ax, key, title in zip(axes, ("r1", "upgraded_v1"), ("R1 locked (408 scenarios)", "Upgraded v1 locked (80 scenarios)")):
        m = dq["studies"][key]["mean_regret_by_policy"]
        xs = np.arange(len(names))
        for i, (k, _) in enumerate(names):
            col = C.get(k, C["ref"])
            ax.errorbar(i, m[k]["mean"], yerr=[[m[k]["mean"] - m[k]["ci95"][0]], [m[k]["ci95"][1] - m[k]["mean"]]], fmt="o", color=col, ms=4.2, capsize=2.2, lw=1.1)
        ax.set_xticks(xs)
        ax.set_xticklabels([n for _, n in names])
        ax.set_title(title)
        ax.set_ylim(0, None)
        ax.grid(axis="y", lw=0.3, alpha=0.5)
    axes[0].set_ylabel("mean normalised regret\n(0 = oracle action; lower is better)")
    fig.tight_layout()
    save(fig, "fig2_regret")


def fig_family(dq):
    fig, axes = plt.subplots(1, 2, figsize=(7.0, 3.1), gridspec_kw={"width_ratios": [1.5, 1]})
    for ax, key, title in zip(axes, ("r1", "upgraded_v1"), ("R1 locked: D $-$ B by family", "Upgraded v1: D $-$ B by family")):
        bf = dq["studies"][key]["by_family"]
        fams = sorted(bf, key=lambda f: bf[f]["D_vs_B"]["mean_diff_a_minus_b"])
        for i, f in enumerate(fams):
            c = bf[f]["D_vs_B"]
            col = C["D"] if c["ci95"][0] > 0 else (C["B"] if c["ci95"][1] < 0 else C["ref"])
            ax.errorbar(c["mean_diff_a_minus_b"], i, xerr=[[c["mean_diff_a_minus_b"] - c["ci95"][0]], [c["ci95"][1] - c["mean_diff_a_minus_b"]]], fmt="o", color=col, ms=3.8, capsize=2, lw=1)
        ax.axvline(0, color="#333333", lw=0.8)
        ax.set_yticks(range(len(fams)))
        ax.set_yticklabels([f.replace("_", " ") for f in fams], fontsize=6.5)
        ax.set_xlabel("regret(D) $-$ regret(B)   (negative: D better)")
        ax.set_title(title)
        ax.grid(axis="x", lw=0.3, alpha=0.5)
    fig.tight_layout()
    save(fig, "fig3_family_D_minus_B")


def fig_cost(cs):
    fig, axes = plt.subplots(1, 2, figsize=(7.0, 2.4), gridspec_kw={"width_ratios": [1.15, 1]})
    ax = axes[0]
    comp = cs["components_seconds"]
    med = {k: comp[k]["median"] for k in ("shared", "B_pick", "C_pick", "D_sim", "D_overhead")}
    labels = ["B", "C", "D"]
    shared = [med["shared"], med["shared"], 0]
    pick = [med["B_pick"], med["C_pick"], 0]
    dsim = [0, 0, med["D_sim"]]
    dov = [0, 0, med["D_overhead"]]
    x = np.arange(3)
    ax.bar(x, shared, color="#9ecae1", label="shared Decision Simulation", width=0.55)
    ax.bar(x, dsim, bottom=np.array(shared), color="#9ecae1", hatch="//", edgecolor="white", label="D's own Decision Simulation", width=0.55)
    ax.bar(x, pick, bottom=np.array(shared) + np.array(dsim), color="#fdae6b", label="selection step (B/C)", width=0.55)
    ax.bar(x, dov, bottom=np.array(shared) + np.array(dsim) + np.array(pick), color=C["D"], label="D: agents, rounds, optimizer, records", width=0.55)
    ax.set_xticks(x)
    ax.set_xticklabels(["B", "C", "D"])
    ax.set_ylabel("median seconds per decision")
    ax.set_title("Where the time goes")
    ax.legend(frameon=False, loc="upper left", fontsize=6)
    ax = axes[1]
    pol = cs["quality_cost"]["policies"]
    for k in ("A", "B", "C", "D"):
        ax.scatter(pol[k]["mean_seconds"], pol[k]["mean_regret"], color=C[k], s=34, zorder=3)
        ax.annotate(k, (pol[k]["mean_seconds"], pol[k]["mean_regret"]), textcoords="offset points", xytext=(5, 4), fontsize=8, color=C[k], fontweight="bold")
    ax.set_xlabel("mean end-to-end seconds per decision")
    ax.set_ylabel("mean normalised regret (lower is better)")
    ax.set_title("Quality versus cost (R1 locked scenarios)")
    ax.grid(lw=0.3, alpha=0.5)
    fig.tight_layout()
    save(fig, "fig4_cost")


def main():
    dq = json.loads((RES / "decision_quality.json").read_text(encoding="utf-8"))
    fig_workflows()
    fig_regret(dq)
    fig_family(dq)
    cs_path = RES / "cost_summary.json"
    if cs_path.exists():
        fig_cost(json.loads(cs_path.read_text(encoding="utf-8")))
    print("figures:", sorted(p.name for p in FIG.glob("fig*.pdf")))


if __name__ == "__main__":
    main()
