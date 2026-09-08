#!/usr/bin/env python
"""R1 publication figures — pure SVG, no plotting library.

Reads ONLY experiments/r1/figure_data.json (extracted read-only from the frozen
R1 locked artifacts by `build_figure_data()` below, which runs no experiment).
Every plotted value comes from that file; nothing is typed by hand.

    python scripts/r1_figures.py build     # extract figure_data.json from experiments/r1/*.json
    python scripts/r1_figures.py render    # write docs/figures/r1_figure{1..5}.svg

Figures:
  1  Evaluation architecture + information boundary (schematic)
  2  Paired D-B normalised-regret differences (sorted, with 0 line + mean/CI)
  3  A/B/C/D mean normalised regret with 95% cluster-bootstrap intervals
  4  Scenario-family D-B effect distribution (per-family mean + CI)
  5  Mechanism: D changed action vs B -> improved / worsened / no-change
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
R1 = REPO / "experiments" / "r1"
FIGDIR = REPO / "docs" / "figures"
DATA = R1 / "figure_data.json"

INK = "#222"; ACCENT = "#3b5bdb"; MUTED = "#8a8f98"; BAD = "#c0392b"; GOOD = "#2f9e44"; FILL = "#c9d2f2"


# --------------------------------------------------------------------------- #
def build_figure_data() -> dict:
    import numpy as np
    sr = json.loads((R1 / "statistical_results.json").read_text())
    res = json.loads((R1 / "results.json").read_text())
    mech = json.loads((R1 / "mechanism_results.json").read_text())
    rob = json.loads((R1 / "robustness_results.json").read_text()) if (R1 / "robustness_results.json").exists() else None

    # per-(scenario) D and B regret means for the paired-diff figure
    from collections import defaultdict
    d_by = defaultdict(list); b_by = defaultdict(list)
    for rec in res["records"]:
        if "result" not in rec:
            continue
        C = rec["result"]["conditions"]
        if rec["result"]["exclude_from_primary"]:
            continue
        if any(C[c]["status"] != "ok" for c in ("A", "B", "C")):
            continue
        if C["D"]["primary_regret"] is not None and C["B"]["primary_regret"] is not None:
            d_by[rec["scenario_id"]].append(C["D"]["primary_regret"])
            b_by[rec["scenario_id"]].append(C["B"]["primary_regret"])
    diffs = sorted(float(np.mean(d_by[s]) - np.mean(b_by[s])) for s in d_by if s in b_by)

    P = sr["primary_and_confirmatory_contrasts"]
    pos = sr["positioning"]
    fam = sr["family_level_D_vs_B"]
    ac = mech["action_change_vs_improvement"]
    out = {
        "source": {"statistical_results.json": _sha(R1 / "statistical_results.json"),
                   "results.json": _sha(R1 / "results.json"),
                   "mechanism_results.json": _sha(R1 / "mechanism_results.json")},
        "n_scenarios": sr["n_scenarios_eligible"], "n_seeds": sr["n_seeds"],
        "paired_D_minus_B_sorted": [round(x, 6) for x in diffs],
        "primary": {k: {"mean": P[k]["mean_difference"], "ci95": P[k]["cluster_bootstrap"]["ci95"],
                        "p_holm": sr["confirmatory_family_holm"]["results"][k]["p_holm"],
                        "rank_biserial": P[k]["matched_pairs_rank_biserial"],
                        "wtl": P[k]["wins_ties_losses"], "n_nonzero": P[k]["n_nonzero"]}
                    for k in ("B_vs_A", "C_vs_B", "D_vs_C", "D_vs_B")},
        "abcd_mean_regret": {c: pos[c]["mean_regret"] for c in "ABCD"},
        "abcd_vs_oracle_ci": {k: sr["secondary_contrasts"][k]["cluster_bootstrap"]["ci95"]
                              for k in ("A_vs_oracle", "B_vs_oracle", "C_vs_oracle", "D_vs_oracle")},
        "baselines_mean_regret": {b: pos[b]["mean_regret"] for b in ("naive", "greedy", "classical_optimizer", "oracle")},
        "family_D_minus_B": {f: {"mean": v["mean_D_minus_B"], "ci95": v["cluster_bootstrap_ci95"],
                                 "n": v["n_structural_scenarios"], "direction": v["direction"]}
                             for f, v in fam.items()},
        "mechanism_action_change": {"n": ac["n"], "changed": ac["D_changed_action_vs_B"],
                                    "improved": ac["D_changed_and_improved"],
                                    "worsened": ac["D_changed_and_worsened"],
                                    "no_change": ac["D_changed_no_change"]},
        "robustness_primary_conclusion_changes": (rob["primary_conclusion_changes"] if rob else None),
    }
    DATA.write_text(json.dumps(out, indent=2))
    print(f"wrote {DATA.relative_to(REPO)}")
    return out


def _sha(p: Path) -> str:
    import hashlib
    return hashlib.sha256(p.read_bytes()).hexdigest()


# --------------------------------------------------------------------------- #
def _svg(w, h, body):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
            f'viewBox="0 0 {w} {h}" font-family="Helvetica,Arial,sans-serif">'
            f'<rect width="{w}" height="{h}" fill="#fff"/>{body}</svg>')


def _txt(x, y, s, size=11, anchor="start", fill=INK, weight="normal"):
    s = str(s).replace("&", "&amp;").replace("<", "&lt;")
    return f'<text x="{x}" y="{y}" font-size="{size}" text-anchor="{anchor}" fill="{fill}" font-weight="{weight}">{s}</text>'


def _line(x1, y1, x2, y2, stroke=INK, w=1, dash=""):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    return f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{stroke}" stroke-width="{w}"{d}/>'


def _rect(x, y, w, h, fill, stroke="none"):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill}" stroke="{stroke}"/>'


def fig1(_d):
    b = [_txt(300, 24, "Figure 1  R1 evaluation architecture & information boundary", 13, "middle", INK, "bold")]
    boxes = [("Scenario (System A)\nhistory + goal", 40), ("A  Prediction only", 190),
             ("B  + R1 research-only\nDecision Simulation", 340), ("C  + single agent", 500),
             ("D  full system\n(agents+risk+optimizer)", 640)]
    for label, x in boxes:
        b.append(_rect(x, 60, 130, 56, FILL, ACCENT))
        for i, ln in enumerate(label.split("\n")):
            b.append(_txt(x + 65, 80 + i * 13, ln, 9, "middle"))
    for x in (170, 320, 470, 630):
        b.append(f'<path d="M{x} 88 l16 0" stroke="{INK}" stroke-width="1.4" marker-end="url(#a)"/>')
    b.append('<defs><marker id="a" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">'
             f'<path d="M0 0 L6 3 L0 6 z" fill="{INK}"/></marker></defs>')
    b.append(_rect(40, 150, 730, 44, "#f4f6fb", MUTED))
    b.append(_txt(52, 168, "A/B/C/D may use: seeded history, goal, candidate set, and (B/C/D) the "
                           "R1-DT elasticity ESTIMATED from that history.", 9))
    b.append(_txt(52, 182, "None may use: true scenario elasticity, oracle action, objective value, future "
                           "outcomes, test labels.  Oracle uses full System-B ground truth (reference only).", 9))
    b.append(_rect(40, 210, 730, 30, "#fff", MUTED))
    b.append(_txt(52, 229, "Exogenous scorer = ground_truth.exogenous_objective_v1 (System B, unchanged, "
                           "independent) -> normalised regret, computed AFTER selection.", 9))
    return _svg(800, 260, "".join(b))


def fig2(d):
    diffs = d["paired_D_minus_B_sorted"]
    n = len(diffs)
    W, H, L, R, T, B_ = 760, 340, 60, 20, 40, 50
    pw, ph = W - L - R, H - T - B_
    lo, hi = min(diffs + [-0.2]), max(diffs + [0.2])
    def X(i): return L + pw * i / max(1, n - 1)
    def Y(v): return T + ph * (hi - v) / (hi - lo)
    b = [_txt(W / 2, 22, "Figure 2  Paired  D-B  normalised-regret difference, per scenario (sorted)  "
                         "— negative = D better", 12, "middle", INK, "bold")]
    b.append(_line(L, Y(0), L + pw, Y(0), MUTED, 1, "4 3"))
    b.append(_txt(L - 6, Y(0) + 3, "0", 9, "end", MUTED))
    for v in (round(lo, 1), 0.0, round(hi, 1)):
        b.append(_txt(L - 6, Y(v) + 3, f"{v:+.1f}", 8, "end", MUTED))
    pts = " ".join(f"{X(i):.1f},{Y(v):.1f}" for i, v in enumerate(diffs))
    b.append(f'<polyline points="{pts}" fill="none" stroke="{ACCENT}" stroke-width="1.4"/>')
    for i, v in enumerate(diffs):
        b.append(f'<circle cx="{X(i):.1f}" cy="{Y(v):.1f}" r="1.6" fill="{BAD if v>0 else GOOD}"/>')
    m = d["primary"]["D_vs_B"]["mean"]; ci = d["primary"]["D_vs_B"]["ci95"]
    b.append(_rect(L + pw + 4, Y(ci[1]), 8, max(1, Y(ci[0]) - Y(ci[1])), "#ddd"))
    b.append(_line(L, Y(m), L + pw + 14, Y(m), INK, 1.4))
    b.append(_txt(L + pw + 16, Y(m) + 3, f"mean {m:+.3f}", 8, "start", INK))
    w, t, l = d["primary"]["D_vs_B"]["wtl"]
    b.append(_txt(W / 2, H - 22, f"n={n} scenarios ({d['n_seeds']} seeds each) · "
                                 f"D better/tie/D worse = {w}/{t}/{l} · Holm p = {d['primary']['D_vs_B']['p_holm']} · "
                                 f"95% CI [{ci[0]:+.3f}, {ci[1]:+.3f}]", 9, "middle", MUTED))
    return _svg(W, H, "".join(b))


def fig3(d):
    reg = d["abcd_mean_regret"]; W, H = 520, 300
    L, T, B_ = 60, 44, 46
    ph = H - T - B_
    hi = max(list(reg.values()) + list(d["baselines_mean_regret"].values()) + [0.5])
    def Y(v): return T + ph * (1 - v / hi)
    b = [_txt(W / 2, 22, "Figure 3  Mean normalised regret by condition (lower = better)", 12, "middle", INK, "bold")]
    xs = {"A": 90, "B": 160, "C": 230, "D": 300, "greedy": 390, "classical_optimizer": 445, "oracle": 490}
    b.append(_line(L, Y(0), W - 20, Y(0), MUTED))
    for k, x in xs.items():
        v = reg.get(k, d["baselines_mean_regret"].get(k, 0.0))
        b.append(_rect(x - 16, Y(v), 32, Y(0) - Y(v), FILL if k in "ABCD" else "#e6e6e6", ACCENT if k in "ABCD" else MUTED))
        b.append(_txt(x, Y(v) - 4, f"{v:.3f}", 8, "middle"))
        b.append(_txt(x, Y(0) + 14, k if len(k) < 6 else k[:5] + "…", 8, "middle", MUTED))
    b.append(_txt(W / 2, H - 16, f"n={d['n_scenarios']} scenarios · A=prediction-only, "
                                 f"B=+Decision Simulation, C=+1 agent, D=full", 8, "middle", MUTED))
    return _svg(W, H, "".join(b))


def fig4(d):
    fam = d["family_D_minus_B"]
    items = sorted(fam.items(), key=lambda kv: (kv[1]["mean"] if kv[1]["mean"] is not None else 0))
    n = len(items); W = 760; rowh = 20; H = 60 + n * rowh + 30
    L = 210; pw = W - L - 90
    vals = [v["mean"] for _, v in items if v["mean"] is not None] + [-0.3, 0.3]
    lo, hi = min(vals), max(vals)
    def X(v): return L + pw * (v - lo) / (hi - lo)
    b = [_txt(W / 2, 24, "Figure 4  Per-family mean  D-B  (negative = D better) with 95% bootstrap CI",
              12, "middle", INK, "bold")]
    b.append(_line(X(0), 40, X(0), H - 20, MUTED, 1, "3 3"))
    for i, (f, v) in enumerate(items):
        y = 54 + i * rowh
        if v["mean"] is None:
            continue
        ci = v["ci95"]
        b.append(_line(X(ci[0]), y, X(ci[1]), y, MUTED, 1))
        b.append(f'<circle cx="{X(v["mean"]):.1f}" cy="{y}" r="3" fill="{BAD if v["mean"]>0 else GOOD}"/>')
        b.append(_txt(L - 8, y + 3, f"{f} (n={v['n']})", 8, "end"))
        b.append(_txt(W - 84, y + 3, f"{v['mean']:+.3f}", 8, "start", MUTED))
    return _svg(W, H, "".join(b))


def fig5(d):
    m = d["mechanism_action_change"]; W, H = 520, 240
    b = [_txt(W / 2, 24, "Figure 5  When D changes the action vs B: does the objective improve?",
              12, "middle", INK, "bold")]
    tot = max(1, m["changed"])
    cats = [("improved (D lower regret)", m["improved"], GOOD),
            ("worsened (D higher regret)", m["worsened"], BAD),
            ("no regret change", m["no_change"], MUTED)]
    x = 60; barw = W - 120
    b.append(_txt(60, 60, f"D changed the action on {m['changed']} / {m['n']} eligible instances", 10))
    xx = x
    for label, v, col in cats:
        w = barw * v / tot
        b.append(_rect(xx, 74, max(0.5, w), 30, col))
        xx += w
    yy = 130
    for label, v, col in cats:
        b.append(_rect(60, yy - 9, 10, 10, col))
        b.append(_txt(76, yy, f"{label}: {v} ({100*v/tot:.0f}% of changes)", 9))
        yy += 18
    b.append(_txt(60, yy + 8, "A changed action is NOT evidence of a better decision (pre-registered).", 8, "start", MUTED))
    return _svg(W, H, "".join(b))


def render():
    d = json.loads(DATA.read_text())
    FIGDIR.mkdir(parents=True, exist_ok=True)
    for i, fn in enumerate((fig1, fig2, fig3, fig4, fig5), 1):
        p = FIGDIR / f"r1_figure{i}.svg"
        p.write_text(fn(d), encoding="utf-8")
        print(f"wrote {p.relative_to(REPO)}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "build"
    if cmd == "build":
        build_figure_data()
    elif cmd == "render":
        render()
    elif cmd == "all":
        build_figure_data(); render()
    else:
        print("usage: r1_figures.py [build|render|all]"); raise SystemExit(2)
