"""SUPPLEMENTARY (post-hoc, not confirmatory) precision check of the subset-day (H3) inference.

Written after the frozen analysis and after the independent verification found one boundary disagreement (W2, M5 TX_1, H=28). It does NOT replace or alter any stored result:
it recomputes the H3 p-values and intervals of the SAME two prespecified bootstrap methods (iid-week = primary, stationary mean 3 weeks = secondary) with very large B and new seeds,
adds an exact sign-flip randomisation test and a dependence diagnostic, and applies the UNCHANGED frozen decision rule (analysis.verdict + dual-method rule + Holm per family per window)
to the converged values. Output: results/supplementary/h3_convergence.json and SUPPLEMENTARY_H3_RESOLUTION.md.

    python -m research.forecast_study_v2.supplementary_h3
"""
from __future__ import annotations

import json

import numpy as np
from scipy import stats

from . import analysis as an
from .common import RESULTS, STUDY, atomic_write_json

B_BIG = 1_000_000
SEEDS = (910001, 910002, 910003)
CHUNK = 100_000


def weekly_totals(window, key, H):
    A, _, res = an.load_cell(window, key, H)
    sel = json.loads((RESULTS / "analysis" / f"analysis_{window}.json").read_text(encoding="utf-8"))["cells"][f"{key}_H{H}"]["selection"]
    y, d = A["y"].astype(float), A["day"].astype(int)
    day0 = res["blocks"]["test"][0]
    days = np.unique(d)
    wk = (days - day0) // 7
    W = int(wk.max()) + 1

    def tot(p):
        t = np.zeros(len(days))
        np.add.at(t, np.searchsorted(days, d), p - y)
        return np.bincount(wk, weights=np.abs(t), minlength=W)

    return tot(A["base__" + sel["baseline_subset_day_matched"]].astype(float)), tot(A["pred__" + sel["model_subset_day"]].astype(float))


def stationary_idx(rng, n, W, mean_block):
    restart = rng.random((n, W)) < 1.0 / mean_block
    restart[:, 0] = True
    start = rng.integers(0, W, (n, W))
    idx = np.empty((n, W), dtype=np.int64)
    idx[:, 0] = start[:, 0]
    for t in range(1, W):
        idx[:, t] = np.where(restart[:, t], start[:, t], (idx[:, t - 1] + 1) % W)
    return idx


def boot(wa, wb, kind, B, seed):
    rng = np.random.default_rng(seed)
    W = len(wa)
    out = []
    left = B
    while left > 0:
        n = min(CHUNK, left)
        idx = rng.integers(0, W, (n, W)) if kind == "iid" else stationary_idx(rng, n, W, an.MEAN_BLOCK_WEEKS)
        out.append(1.0 - wb[idx].sum(axis=1) / wa[idx].sum(axis=1))
        left -= n
    d = np.concatenate(out)
    k_le, k_ge = int((d <= 0).sum()), int((d >= 0).sum())
    p = min(1.0, 2 * min((k_le + 1) / (B + 1), (k_ge + 1) / (B + 1)))
    return {"p": p, "ci95": [float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))], "B": B, "seed": seed}


def signflip_exact(wa, wb):
    """Exact randomisation test of H0: the weekly paired differences (wa - wb) are symmetric about 0 (2^W sign patterns, W = 24 -> 16.8 M). Statistic: sum of differences."""
    dlt = wa - wb
    W = len(dlt)
    obs = dlt.sum()
    n_ge = n_le = 0
    total = 1 << W
    step = 1 << 19
    bits = np.arange(W, dtype=np.int64)
    for lo in range(0, total, step):
        codes = np.arange(lo, min(lo + step, total), dtype=np.int64)
        signs = 1 - 2 * ((codes[:, None] >> bits[None, :]) & 1)
        s = signs @ dlt
        n_ge += int((s >= obs - 1e-12).sum())
        n_le += int((s <= obs + 1e-12).sum())
    return {"p_two_sided": float(min(1.0, 2 * min(n_ge, n_le) / total)), "n_patterns": total}


def diagnostics(wa, wb):
    dlt = wa - wb
    r1 = float(np.corrcoef(dlt[:-1], dlt[1:])[0, 1]) if len(dlt) > 2 else float("nan")
    n = len(dlt)
    ess = n * (1 - r1) / (1 + r1) if r1 > -1 else float("nan")  # AR(1) effective sample size of the mean
    t = stats.ttest_1samp(dlt, 0.0)
    pos = int((dlt > 0).sum())
    return {"n_weeks": n, "weeks_model_better": pos, "lag1_autocorr_of_weekly_difference": r1, "ar1_effective_weeks": float(ess), "t_test_on_weekly_differences": {"t": float(t.statistic), "p": float(t.pvalue), "df": n - 1},
            "sign_test_binomial_p": float(stats.binomtest(pos, n, 0.5).pvalue), "cv_of_weekly_difference": float(np.std(dlt, ddof=1) / abs(dlt.mean()))}


def main():
    out = {"purpose": "supplementary precision check; frozen results untouched", "B": B_BIG, "seeds": SEEDS, "windows": {}}
    lines = ["# SUPPLEMENTARY_H3_RESOLUTION — precision check of the subset-day (H3) inference", "",
             "Post-hoc and **supplementary**. The frozen results (`results/analysis/analysis_*.json`) are unchanged and remain the reported outcome. Here the two prespecified H3 methods (iid-week bootstrap = primary; stationary bootstrap with mean block 3 weeks = secondary) are recomputed with B = 1,000,000 per seed (3 seeds, new seeds), the frozen decision rule (`analysis.verdict`, dual-method rule, Holm within the family of the window) is applied unchanged to the converged p-values and intervals, and an exact sign-flip test and dependence diagnostics are added.", ""]
    for w in ("W2", "W3", "W1"):
        an_w = json.loads((RESULTS / "analysis" / f"analysis_{w}.json").read_text(encoding="utf-8"))["cells"]
        res = {}
        for c, v in an_w.items():
            key, H = c.rsplit("_H", 1)
            wa, wb = weekly_totals(w, key, int(H))
            th = 1.0 - wb.sum() / wa.sum()
            assert abs(th - v["H3"]["improvement"]) < 1e-12, (w, c)
            runs = {"iid": [boot(wa, wb, "iid", B_BIG, s) for s in SEEDS], "stationary": [boot(wa, wb, "stationary", B_BIG, s) for s in SEEDS]}
            conv = {k: {"p_mean": float(np.mean([r["p"] for r in rs])), "p_seed_sd": float(np.std([r["p"] for r in rs], ddof=1)), "ci95": [float(np.mean([r["ci95"][0] for r in rs])), float(np.mean([r["ci95"][1] for r in rs]))]} for k, rs in runs.items()}
            res[c] = {"improvement": th, "blocks_won": v["H3"]["blocks_won"], "frozen": {"p_primary": v["H3"]["primary"]["p"], "p_secondary": v["H3"]["secondary"]["p"], "holm_primary": v["H3"]["holm_p"], "holm_secondary": v["H3"]["holm_p_secondary"], "verdict": v["H3"]["verdict"], "agree": v["H3"]["methods_agree_on_verdict"]},
                      "converged": conv, "signflip_exact": signflip_exact(wa, wb), "diagnostics": diagnostics(wa, wb)}
        hp, hs = an.holm({c: r["converged"]["iid"]["p_mean"] for c, r in res.items()}), an.holm({c: r["converged"]["stationary"]["p_mean"] for c, r in res.items()})
        hx = an.holm({c: r["signflip_exact"]["p_two_sided"] for c, r in res.items()})
        for c, r in res.items():
            e = r["improvement"]
            vp = an.verdict(e, r["converged"]["iid"]["ci95"][0], r["converged"]["iid"]["ci95"][1], hp[c], r["blocks_won"])
            vs = an.verdict(e, r["converged"]["stationary"]["ci95"][0], r["converged"]["stationary"]["ci95"][1], hs[c], r["blocks_won"])
            r["converged"].update({"holm_primary": hp[c], "holm_secondary": hs[c], "verdict_primary": vp, "verdict_secondary": vs, "verdict_dual_rule": vp if vp == vs else "INCONCLUSIVE", "holm_signflip_exact": hx[c]})
        out["windows"][w] = res
        lines += [f"## Window {w}", "", "| cell | improvement | frozen: p iid / p stat. | frozen verdict | converged: p iid (seed SD) / p stat. (seed SD) | converged Holm iid / stat. | converged verdict (frozen rule) | exact sign-flip p | weeks model better | lag-1 autocorr. | AR(1) effective weeks |", "|---|---|---|---|---|---|---|---|---|---|---|"]
        for c, r in res.items():
            f, g, d = r["frozen"], r["converged"], r["diagnostics"]
            lines.append(f"| {c} | {100 * r['improvement']:+.1f}% | {f['p_primary']:.4f} / {f['p_secondary']:.4f} | {f['verdict']} | {g['iid']['p_mean']:.4f} ({g['iid']['p_seed_sd']:.4f}) / {g['stationary']['p_mean']:.4f} ({g['stationary']['p_seed_sd']:.4f}) | {g['holm_primary']:.4f} / {g['holm_secondary']:.4f} | {g['verdict_dual_rule']} | {r['signflip_exact']['p_two_sided']:.4f} | {d['weeks_model_better']}/{d['n_weeks']} | {d['lag1_autocorr_of_weekly_difference']:+.2f} | {d['ar1_effective_weeks']:.1f} |")
        lines.append("")
    (RESULTS / "supplementary").mkdir(exist_ok=True)
    atomic_write_json(RESULTS / "supplementary" / "h3_convergence.json", out)
    (STUDY / "SUPPLEMENTARY_H3_RESOLUTION.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    for w, res in out["windows"].items():
        n_f = sum(1 for r in res.values() if r["frozen"]["verdict"] == "SUPPORTED")
        n_c = sum(1 for r in res.values() if r["converged"]["verdict_dual_rule"] == "SUPPORTED")
        print(w, "frozen supported", n_f, "converged supported", n_c, "| changed:", [c for c, r in res.items() if r["frozen"]["verdict"] != r["converged"]["verdict_dual_rule"]])


if __name__ == "__main__":
    main()
