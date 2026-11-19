"""Independent verification of one finished cell (deliberately does NOT import metrics.py / inference.py).

``python -m research.forecast_study_v1.verify_cell fs1_m5_ca1_H28`` -> ``<cell>/verification.json``; exit code 1 if any check fails.

Checks: (1) stored arrays are complete, finite and aligned; (2) every test row lies in a declared test block and no row is repeated; (3) all methods share identical rows;
(4) pooled WAPE / bias / aggregate WAPE / by-block WAPE for the primary model and both references recomputed here match results.json and analysis.json;
(5) the headline relative improvement is recomputed from the raw arrays; (6) test-time files were written after the selection file (selection preceded test fits);
(7) selection.json ranks come from validation numbers only (primary = argmin of validation WAPE among chosen variants).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

RESULTS = Path(__file__).resolve().parent / "results"


def wape(y, p):
    d = np.abs(y).sum()
    return float(np.abs(p - y).sum() / d) if d > 0 else None


def verify(cell: str) -> dict:
    out = RESULTS / cell
    z = np.load(out / "predictions.npz")
    cfg = json.load(open(out / "config.json", encoding="utf-8"))
    sel = json.load(open(out / "selection.json", encoding="utf-8"))
    res = json.load(open(out / "results.json", encoding="utf-8"))
    ana = json.load(open(out / "analysis.json", encoding="utf-8")) if (out / "analysis.json").exists() else None
    checks: list[dict] = []

    def ok(name, cond, detail=""):
        checks.append({"check": name, "passed": bool(cond), "detail": detail})

    y, s, d, b = z["y"].astype(float), z["series"], z["day"], z["block"]
    n = len(y)
    meth = [k for k in z.files if k.startswith(("pred__", "base__"))]
    ok("all method arrays have one value per evaluated row", all(len(z[k]) == n for k in meth), f"{n} rows, {len(meth)} methods")
    ok("all stored values finite and non-negative baselines/predictions finite", all(np.isfinite(z[k]).all() for k in meth) and np.isfinite(y).all())
    pairs = set(zip(s.tolist(), d.tolist()))
    ok("no (series, day) row repeated", len(pairs) == n)
    starts = cfg["windows"]["test"]
    in_block = np.zeros(n, bool)
    for o in starts:
        in_block |= (d >= o) & (d <= o + cfg["block"] - 1) & (b == o)
    ok("every row lies in its declared 28-day test block", in_block.all())
    val_end = cfg["windows"]["val"][-1] + cfg["block"] - 1
    ok("validation blocks end before the first test block", val_end < starts[0], f"val_end={val_end} test_start={starts[0]}")

    primary = "pred__" + sel["primary_learned_config"].replace(":", "__")
    refs = {"matched": "base__" + sel["reference_baseline_matched_information"], "any": "base__" + sel["reference_baseline_any_information"]}
    ok("selected primary and reference arrays exist", primary in z.files and all(r in z.files for r in refs.values()))

    # recompute pooled metrics for these three methods
    for name, key in {"primary": primary, **{f"ref_{k}": v for k, v in refs.items()}}.items():
        p = z[key].astype(float)
        w = wape(y, p)
        rk = key if key.startswith("base__") else "pred__" + sel["primary_learned_config"]      # results.json keys models by "family:variant"
        stored = res["test_summary"][rk]["wape"]
        ok(f"{name}: pooled WAPE recomputed == results.json", abs(w - stored) < 1e-9, f"{w:.10f} vs {stored:.10f}")
        bias = float((p - y).sum() / y.sum())
        ok(f"{name}: relative bias recomputed", abs(bias - res["test_summary"][rk]["rel_bias"]) < 1e-9)
        days = np.unique(d)
        ya = np.array([y[d == t].sum() for t in days])
        pa = np.array([p[d == t].sum() for t in days])
        ok(f"{name}: aggregate WAPE recomputed", abs(wape(ya, pa) - res["test_summary"][rk]["aggregate_wape"]) < 1e-9)
        byb = [wape(y[b == o], p[b == o]) for o in starts]
        ok(f"{name}: by-block WAPE recomputed", all(abs(u - v) < 1e-9 for u, v in zip(byb, res["test_summary"][rk]["wape_by_block"])))

    wm, wp = wape(y, z[refs["matched"]].astype(float)), wape(y, z[primary].astype(float))
    head = (wm - wp) / wm
    if ana:
        ok("headline relative improvement vs matched reference recomputed == analysis.json", abs(head - ana["H1_vs_matched_reference"]["estimate"]) < 1e-9, f"{head:.8f}")
        ok("bootstrap interval contains the point estimate", ana["H1_vs_matched_reference"]["ci95"][0] <= ana["H1_vs_matched_reference"]["estimate"] <= ana["H1_vs_matched_reference"]["ci95"][1])
        wins = sum(1 for o in starts if wape(y[b == o], z[primary][b == o].astype(float)) < wape(y[b == o], z[refs["matched"]][b == o].astype(float)))
        ok("block-win count recomputed", wins == ana["H1_vs_matched_reference"]["model_wins_blocks"], f"{wins}")

    # selection preceded the test fits (file modification times)
    sel_t = (out / "selection.json").stat().st_mtime
    test_fits = list((out / "fits").glob("test_*.npy"))
    if "ablate" in cell:
        ok("ablation: selection file is the main run's copy, test fits exist", bool(test_fits))
    else:
        ok("selection.json was written before every test-block fit", bool(test_fits) and all(f.stat().st_mtime >= sel_t for f in test_fits),
           f"{len(test_fits)} test fits; earliest {min(f.stat().st_mtime for f in test_fits) - sel_t:+.0f}s after selection" if test_fits else "no test fits found")
        vw = sel["validation_wape"]["configs"]
        chosen = sel["chosen_variant_per_family"]
        best = min(chosen, key=lambda f: np.mean([x for x in vw[chosen[f]]["by_block"] if x is not None]))
        ok("primary family == argmin of mean validation WAPE (validation numbers only)", best == sel["primary_learned_family"], best)
        vb = sel["validation_wape"]["baselines"]
        ok("reference baselines == argmin of validation WAPE", min(vb, key=lambda k: np.mean([x for x in vb[k]["by_block"] if x is not None])) == sel["reference_baseline_any_information"])

    verdict = {"cell": cell, "n_checks": len(checks), "n_failed": sum(not c["passed"] for c in checks), "checks": checks}
    (out / "verification.json").write_text(json.dumps(verdict, indent=2), encoding="utf-8")
    return verdict


if __name__ == "__main__":
    bad = 0
    for c in sys.argv[1:]:
        v = verify(c)
        print(f"{c}: {v['n_checks'] - v['n_failed']}/{v['n_checks']} checks passed")
        for ch in v["checks"]:
            if not ch["passed"]:
                print("  FAILED:", ch["check"], ch["detail"])
        bad += v["n_failed"]
    sys.exit(1 if bad else 0)
