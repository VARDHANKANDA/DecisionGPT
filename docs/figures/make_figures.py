"""Render the four paper figures for docs/PAPER_DRAFT.md.

Reads only docs/figures/figure_data.json, which was extracted read-only from the
frozen DecisionGPT experiment runs (source experiment IDs are recorded in that
file). This script runs no experiment and touches no research artifact.

Usage (with a Python that has matplotlib + numpy):
    python docs/figures/make_figures.py

Outputs (SVG, vector):
    docs/figures/figure1_architecture.svg
    docs/figures/figure2_primary_comparison.svg
    docs/figures/figure3_ablation_mechanism.svg
    docs/figures/figure4_risk_calibration.svg

On-figure text is intentionally minimal; the detailed interpretation lives in the
figure captions in the manuscript. The only stochastic element is the paired
bootstrap in Figure 2, seeded with numpy default_rng(42); it re-analyses the
frozen paired differences and is not a new experiment.
"""
from __future__ import annotations

import json
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = json.load(open(os.path.join(HERE, "figure_data.json")))

plt.rcParams.update(
    {
        "font.size": 9,
        "axes.titlesize": 9.5,
        "axes.labelsize": 9,
        "xtick.labelsize": 8.5,
        "ytick.labelsize": 8.5,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "figure.dpi": 150,
        "savefig.bbox": "tight",
    }
)

INK = "#222222"
ACCENT = "#3b5bdb"
MUTED = "#8a8f98"
BAD = "#c0392b"
FILL = "#c9d2f2"


def _save(fig, name):
    path = os.path.join(HERE, name)
    fig.savefig(path, format="svg")
    fig.savefig(path.replace(".svg", ".png"), format="png", dpi=150)
    plt.close(fig)
    print("wrote", os.path.relpath(path, os.path.dirname(HERE)))


# ---------------------------------------------------------------------------
# Figure 1 — architecture / evaluation decomposition (schematic; no data)
# ---------------------------------------------------------------------------
def figure1():
    fig, ax = plt.subplots(figsize=(8.2, 2.7))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 26)
    ax.axis("off")

    labels = [
        "Goal\nspecification",
        "Capability\ndetection",
        "Strategy\ngeneration",
        "Decision-\nsimulation\nlayer",
        "Association\ngraph",
        "Rule-based\nmulti-agent\nevaluation",
        "Optimizer\n(Eq. 1)",
    ]
    n = len(labels)
    w, h, y = 11.2, 12.0, 8.5
    span = 98.0
    gap = (span - n * w) / (n - 1)
    centers = []
    for i, label in enumerate(labels):
        x = i * (w + gap)
        ax.add_patch(
            FancyBboxPatch(
                (x, y), w, h, boxstyle="round,pad=0.15,rounding_size=0.6",
                linewidth=1.0, edgecolor=INK, facecolor="#eef1fb",
            )
        )
        ax.text(x + w / 2, y + h / 2, label, ha="center", va="center", color=INK, fontsize=8)
        centers.append((x, x + w / 2, x + w))
    for (l0, c0, r0), (l1, c1, r1) in zip(centers[:-1], centers[1:]):
        ax.add_patch(
            FancyArrowPatch((r0, y + h / 2), (l1, y + h / 2), arrowstyle="-|>",
                            mutation_scale=11, linewidth=1.0, color=INK)
        )

    ax.text(
        0, 3.0,
        "All stages are deterministic in every experiment reported here. When configured, an LLM parses the "
        "goal sentence and narrates the\nfinal result only — it does not compute agent scores or the "
        "selection in Eq. 1. No LLM was configured for any result in this paper.\n"
        "Explanation and memory run after selection and are not inputs to Eq. 1.",
        ha="left", va="center", color=MUTED, fontsize=7.4,
    )
    ax.set_title("Figure 1. DecisionGPT pipeline and evaluation decomposition (schematic).",
                 loc="left", pad=8)
    _save(fig, "figure1_architecture.svg")


# ---------------------------------------------------------------------------
# Figure 2 — primary paired comparison (experiment 0e1bd8dc)
# ---------------------------------------------------------------------------
def figure2():
    a = DATA["architecture"]
    agg = a["aggregates"]
    order = ["A", "B", "C", "D"]
    tick = ["A", "B", "C", "D"]
    means = [agg[k]["mean"] for k in order]
    los = [agg[k]["mean"] - agg[k]["ci95"][0] for k in order]
    his = [agg[k]["ci95"][1] - agg[k]["mean"] for k in order]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(8.4, 3.6), layout="constrained")

    colors = [MUTED, ACCENT, MUTED, BAD]
    ax1.bar(range(4), means, yerr=[los, his], capsize=4, color=colors, width=0.6,
            error_kw={"elinewidth": 1, "capthick": 1})
    ax1.set_xticks(range(4))
    ax1.set_xticklabels(tick)
    ax1.set_xlabel("A: prediction only   B: + decision simulation   C: + single agent   D: full (+ multi-agent)",
                   fontsize=7.6)
    ax1.set_ylabel("Mean simulated goal achievement  [0, 1]")
    ax1.set_ylim(0, 0.78)
    for i, mn in enumerate(means):
        ax1.text(i, mn + his[i] + 0.02, f"{mn:.3f}", ha="center", va="bottom", fontsize=8.5)
    ax1.set_title("(a) Architecture comparison  (n = 60 paired obs. per bar)", loc="left")

    diffs = np.array(a["diffs_D_minus_B"])
    p = a["paired_D_vs_B"]
    rng = np.random.default_rng(42)
    idx = rng.integers(0, len(diffs), size=(20000, len(diffs)))
    boot = diffs[idx].mean(axis=1)
    lo, hi = np.percentile(boot, [2.5, 97.5])

    ax2.axvline(0, color=MUTED, linewidth=0.8, linestyle="--")
    ax2.hist(diffs, bins=np.linspace(-1.05, 0.15, 25), color=FILL, edgecolor=INK, linewidth=0.4)
    ax2.axvline(float(diffs.mean()), color=BAD, linewidth=1.5)
    ax2.annotate(
        f"mean = {diffs.mean():.4f}\nbootstrap 95% CI\n[{lo:.4f}, {hi:.4f}]",
        xy=(diffs.mean(), 12.5), xytext=(-0.99, 13.7), fontsize=7.4, color=BAD,
        va="top",
    )
    ax2.set_xlabel("Paired difference  D − B  in simulated goal achievement")
    ax2.set_ylabel("Number of (scenario, seed) pairs")
    ax2.set_xlim(-1.08, 0.18)
    ax2.set_ylim(0, 17)
    ax2.set_title(
        f"(b) Paired differences, D vs B   (0 / {p['ties']} / {p['full_losses']}"
        f"  D-better / tie / B-better)", loc="left"
    )

    fig.suptitle(
        "Figure 2. Primary result (experiment 0e1bd8dc): 12 designed synthetic scenarios × 5 seeds, "
        "paired by (scenario, seed). Simulated metric on\nprocedurally generated businesses — not "
        "real-world effectiveness. Error bars in (a): Student-t 95% CI (within-suite variability). "
        "In (b) all 45\nnon-tied pairs favour B; Wilcoxon two-sided p < 10⁻⁴ (recomputed "
        "4.8×10⁻⁹); rank-biserial = −1.00.",
        fontsize=7.5, x=0.01, ha="left",
    )
    _save(fig, "figure2_primary_comparison.svg")


# ---------------------------------------------------------------------------
# Figure 3 — component ablation (db58455b) + risk-penalty mechanism (ba56e42b)
# ---------------------------------------------------------------------------
def figure3():
    abl = DATA["ablation"]["configs"]
    name_map = {
        "B": "− Decision\nSimulation",
        "C": "− Assoc.\nGraph",
        "D": "− Multi-\nAgent",
        "E": "− Expla-\nnation",
        "F": "− Memory",
    }
    full = abl["A"]["mean"]
    keys = ["B", "C", "D", "E", "F"]
    deltas = [full - abl[k]["mean"] for k in keys]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(8.4, 3.6), layout="constrained",
                                   gridspec_kw={"width_ratios": [1.3, 1]})

    ci = DATA["ablation"]["paired"].get("Full_vs_B", {}).get("mean_difference_ci95")
    colors = [ACCENT] + [MUTED] * 4
    ax1.bar(range(5), deltas, color=colors, width=0.62)
    if ci:
        ax1.errorbar(0, deltas[0], yerr=[[deltas[0] - ci[0]], [ci[1] - deltas[0]]],
                     fmt="none", ecolor=INK, elinewidth=1, capsize=4, capthick=1)
    ax1.axhline(0, color=INK, linewidth=0.8)
    ax1.set_xticks(range(5))
    ax1.set_xticklabels([name_map[k] for k in keys], fontsize=7.8)
    ax1.set_ylabel("Δ mean simulated goal achievement\n(Full − variant)")
    ax1.set_ylim(-0.02, 0.21)
    for i, d in enumerate(deltas):
        ax1.text(i, d + 0.006 if i == 0 else 0.006, f"{d:+.3f}", ha="center", va="bottom", fontsize=8)
    ax1.set_title("(a) Component ablation  (experiment db58455b, n = 60)", loc="left")

    mech = DATA["mechanism"]
    d0 = mech["D0_goal_achievement"]
    d1 = mech["D1_goal_achievement"]
    m = [d0["mean"], d1["mean"]]
    lo = [d0["mean"] - d0["ci95"][0], d1["mean"] - d1["ci95"][0]]
    hi = [d0["ci95"][1] - d0["mean"], d1["ci95"][1] - d1["mean"]]
    ax2.bar([0, 1], m, yerr=[lo, hi], capsize=4, color=[BAD, "#6b7280"], width=0.5,
            error_kw={"elinewidth": 1, "capthick": 1})
    ax2.set_xticks([0, 1])
    ax2.set_xticklabels(["D0: full\n(λ = 1)", "D1: diagnostic\n(λ = 0)"], fontsize=8)
    ax2.set_ylabel("Mean simulated goal achievement")
    ax2.set_ylim(0, 0.9)
    for i, v in enumerate(m):
        ax2.text(i, v + hi[i] + 0.03, f"{v:.3f}", ha="center", fontsize=8.5)
    ax2.set_title("(b) Risk-penalty mechanism  (experiment ba56e42b, n = 60)", loc="left")

    fig.suptitle(
        "Figure 3. (a) Only removing the decision-simulation layer moves the objective (95% CI shown); "
        "the other four removals are exactly\n0.000 (significance not assessed). (b) Neutralising the "
        "optimizer's risk-penalty term (λ = 0) recovers most of the lost metric; the risk\nmanager is "
        "decisive in 75% of pairs (35 improved / 0 degraded / 10 neutral), with 0/390 risk-score "
        "transmission errors. λ = 0 is a\ndiagnostic intervention within the deterministic architecture "
        "— not a production recommendation and not causal evidence. Synthetic.",
        fontsize=7.5, x=0.01, ha="left",
    )
    _save(fig, "figure3_ablation_mechanism.svg")


# ---------------------------------------------------------------------------
# Figure 4 — risk recalibration variants (b8516eef) + S04/S07 robustness (0e1bd8dc)
# ---------------------------------------------------------------------------
def figure4():
    cal = DATA["risk_calibration"]["variants"]
    verdict = DATA["risk_calibration"]["verdict_by_variant"]
    order = ["R0", "R1", "R2-0.25", "R2-0.50", "R2-0.75", "R3"]
    means = [cal[v]["goal_achievement_mean"] for v in order]
    cis = [cal[v]["goal_achievement_ci95"] for v in order]
    los = [m - c[0] for m, c in zip(means, cis)]
    his = [c[1] - m for m, c in zip(means, cis)]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(8.4, 3.7), layout="constrained",
                                   gridspec_kw={"width_ratios": [1.5, 1]})

    cols = []
    for v in order:
        if v == "R0":
            cols.append(INK)
        elif verdict.get(v) == "PROMISING":
            cols.append(ACCENT)
        else:
            cols.append(MUTED)
    ax1.bar(range(6), means, yerr=[los, his], capsize=3, color=cols, width=0.62,
            error_kw={"elinewidth": 1, "capthick": 1})
    dt = DATA["risk_calibration"]["digital_twin_mean_goal_achievement"]
    ax1.axhline(dt, color=ACCENT, linewidth=0.9, linestyle=":")
    ax1.text(5.4, dt + 0.012, "B reference = 0.486", ha="right", fontsize=7, color=ACCENT)
    ax1.set_xticks(range(6))
    ax1.set_xticklabels(["R0", "R1", "R2-\n0.25", "R2-\n0.50", "R2-\n0.75", "R3"], fontsize=8)
    ax1.set_ylabel("Mean simulated goal achievement  (n = 60 per variant)")
    ax1.set_ylim(0, 0.56)
    for i, mn in enumerate(means):
        ax1.text(i, mn + his[i] + 0.014, f"{mn:.3f}", ha="center", fontsize=7.6)
    ax1.set_title("(a) Pre-registered risk-heuristic recalibration  (experiment b8516eef)", loc="left")

    a = DATA["architecture"]
    diffs = np.array(a["diffs_D_minus_B"])
    keys = sorted(a["scenario_level_D_minus_B"].keys())
    per_scen = {s: diffs[i * 5:(i + 1) * 5] for i, s in enumerate(keys)}
    all_d = np.concatenate([per_scen[s] for s in keys])
    keep_d = np.concatenate([per_scen[s] for s in keys if s not in {"S04", "S07"}])

    def wtl(d):
        return int((d > 1e-9).sum()), int((np.abs(d) <= 1e-9).sum()), int((d < -1e-9).sum())

    m = [float(all_d.mean()), float(keep_d.mean())]
    ax2.bar([0, 1], m, color=[BAD, "#d98880"], width=0.5)
    ax2.axhline(0, color=INK, linewidth=0.8)
    for i, d in enumerate([all_d, keep_d]):
        w, t, l = wtl(d)
        ax2.text(i, m[i] - 0.02, f"{m[i]:.3f}", ha="center", va="top", fontsize=8)
        ax2.text(i, 0.02, f"{w}/{t}/{l}", ha="center", va="bottom", fontsize=7.4, color=INK)
    ax2.set_xticks([0, 1])
    ax2.set_xticklabels(["all 12\nscenarios\n(n = 60)", "excluding\nS04, S07\n(n = 50)"], fontsize=8)
    ax2.set_ylabel("Mean paired difference  D − B")
    ax2.set_ylim(-0.5, 0.08)
    ax2.set_title("(b) Robustness to the KPI-proxy scenarios", loc="left")

    r3 = DATA["risk_calibration"]["paired_vs_r0"]["R3"]
    fig.suptitle(
        f"Figure 4. (a) R3 raises the synthetic metric to 0.168; R3 − R0 mean shift "
        f"{r3['mean_difference']:+.3f} (95% CI "
        f"[{r3['mean_difference_ci95'][0]:.3f}, {r3['mean_difference_ci95'][1]:.3f}], p = "
        f"{r3['p_value']:.4f}), on only 5 of 60 non-zero\npairs; R3 is NOT PROMOTED, production stays R0. "
        "Blue bars = pre-registered verdict “promising”, grey = “no satisfactory calibration”. "
        "(b) The primary\nnegative result is not driven by the two revenue-proxy scenarios "
        "(excluding them p ≈ 2.2×10⁻⁷; a re-analysis of frozen observations,\nnot a new experiment); "
        "bars labelled wins / ties / losses. Synthetic; no real-world validation.",
        fontsize=7.4, x=0.06, ha="left",
    )
    _save(fig, "figure4_risk_calibration.svg")


if __name__ == "__main__":
    figure1()
    figure2()
    figure3()
    figure4()
    print("done")
