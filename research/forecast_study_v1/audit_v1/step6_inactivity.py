"""Step 6: audit of the customer-inactivity study. (a) labels, recency and customer sets re-derived from the RAW transactions with independent code; (b) ROC-AUC/PR-AUC/differences/CIs/Holm
recomputed from stored scores; (c) calibration and prevalence-shift diagnostics; (d) one-threshold metrics; (e) origin dependence and customer overlap; (f) practical value (precision at fixed
contact budgets). Writes work/step6.json."""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import ind_core as ic  # noqa: E402

AUD = Path(__file__).parent
R = ic.jload(ic.RES / "s2_online_retail_inactivity" / "results.json")
Z = np.load(ic.RES / "s2_online_retail_inactivity" / "predictions.npz")
cfg = ic.jload(ic.RES / "s2_online_retail_inactivity" / "config.json")
d = ic.load_or2_clean()
d = d[d["Customer ID"].notna()]
out = {"origins": {}}
rng = np.random.default_rng(31415)
WIN = pd.Timedelta(days=90)


def snapshot(cut):
    c = pd.Timestamp(cut)
    past = d[d["day"] < c]
    last = past.groupby("Customer ID")["day"].max()
    first = past.groupby("Customer ID")["day"].min()
    act = set(d[(d["day"] >= c) & (d["day"] < c + WIN)]["Customer ID"].unique())
    snap = pd.DataFrame({"recency_days": (c - last).dt.days, "first_day": first})
    snap["inactive"] = (~snap.index.isin(act)).astype(int)
    return snap


def ece10(y, p):
    idx = np.clip(np.digitize(p, np.linspace(0, 1, 11)[1:-1]), 0, 9)
    return float(sum((idx == b).mean() * abs(y[idx == b].mean() - p[idx == b].mean()) for b in range(10) if (idx == b).any()))


def logit(p):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))


def boot_diff(y, a, b, B=2000, seed=5):
    g = np.random.default_rng(seed)
    n = len(y)
    da, dp = [], []
    for _ in range(B):
        i = g.integers(0, n, n)
        if y[i].min() == y[i].max():
            continue
        da.append(ic.auc_rank(y[i], a[i]) - ic.auc_rank(y[i], b[i]))
        dp.append(ic.avg_precision(y[i], a[i]) - ic.avg_precision(y[i], b[i]))
    res = {}
    for nm, arr, pt in (("roc_auc", da, ic.auc_rank(y, a) - ic.auc_rank(y, b)), ("pr_auc", dp, ic.avg_precision(y, a) - ic.avg_precision(y, b))):
        arr = np.array(arr)
        res[nm] = {"difference": float(pt), "ci95": [float(np.percentile(arr, 2.5)), float(np.percentile(arr, 97.5))], "p": float(min(1, 2 * min(np.mean(arr <= 0), np.mean(arr >= 0))))}
    return res


praw = {}
snaps = {}
for o, spec in cfg["origins"].items():
    sel = R["origins"][o]["selection"]
    m = sel["primary_model"]
    te_cut, va_cut = spec["test"], spec["validation"]
    cid, yt = Z[f"{o}__test_customer_id"], Z[f"{o}__y_test"].astype(int)
    sc_raw, sc_pl = Z[f"{o}__test__{m}__raw"], Z[f"{o}__test__{m}__platt"]
    rec = Z[f"{o}__test__{sel['best_baseline']}"]
    yv, scv_raw, scv_pl = Z[f"{o}__y_val"].astype(int), Z[f"{o}__val__{m}__raw"], Z[f"{o}__val__{m}__platt"]
    # (a) labels from raw data
    sn = snapshot(te_cut)
    snaps[o] = sn
    sn_te = sn.loc[cid]
    r = {"model": m, "baseline": sel["best_baseline"], "n_test": int(len(yt)),
         "test_customer_set_equals_raw_derived_set": bool(set(cid.tolist()) == set(sn.index.tolist())),
         "labels_equal_raw_derived": bool(np.array_equal(sn_te["inactive"].to_numpy(), yt)),
         "recency_equals_raw_derived": bool(np.array_equal(sn_te["recency_days"].to_numpy(float), rec.astype(float))),
         "label_window": [te_cut, str((pd.Timestamp(te_cut) + WIN).date())], "last_data_day": str(d["day"].max().date()),
         "prevalence_test": float(yt.mean()), "prevalence_validation": float(yv.mean())}
    # (b) metrics
    r["roc_auc"] = {"model": ic.auc_rank(yt, sc_raw), "baseline": ic.auc_rank(yt, rec), "platt_model": ic.auc_rank(yt, sc_pl)}
    r["pr_auc"] = {"model": ic.avg_precision(yt, sc_raw), "baseline": ic.avg_precision(yt, rec), "prevalence": float(yt.mean())}
    st = R["origins"][o]
    r["agrees_with_study"] = {"roc_auc_model": abs(r["roc_auc"]["model"] - st["models"][m]["raw"]["test"]["roc_auc"]) < 1e-9, "roc_auc_baseline": abs(r["roc_auc"]["baseline"] - st["baselines"][sel["best_baseline"]]["test"]["roc_auc"]) < 1e-9,
                              "pr_auc_model": abs(r["pr_auc"]["model"] - st["models"][m]["raw"]["test"]["pr_auc"]) < 1e-9, "pr_auc_baseline": abs(r["pr_auc"]["baseline"] - st["baselines"][sel["best_baseline"]]["test"]["pr_auc"]) < 1e-9}
    r["paired_bootstrap_independent"] = boot_diff(yt, sc_raw, rec)
    r["paired_study"] = {k: {"difference": st["paired_primary_minus_best_baseline"][k]["difference"], "ci95": st["paired_primary_minus_best_baseline"][k]["ci95"]} for k in ("roc_auc", "pr_auc")}
    # (c) calibration and prevalence shift
    r["calibration"] = {"mean_pred_val_raw": float(scv_raw.mean()), "mean_pred_val_platt": float(scv_pl.mean()), "mean_pred_test_raw": float(sc_raw.mean()), "mean_pred_test_platt": float(sc_pl.mean()),
                        "ece10_test_raw": ece10(yt, sc_raw), "ece10_test_platt": ece10(yt, sc_pl), "study_ece10_raw": st["models"][m]["raw"]["test"]["ece_10_equal_width"], "study_ece10_platt": st["models"][m]["platt"]["test"]["ece_10_equal_width"]}
    # diagnostic (uses TEST labels -> not a method): shift the Platt logit so the mean prediction equals test prevalence
    lo = logit(sc_pl)
    lo_, hi_ = -3.0, 3.0
    for _ in range(60):
        mid = (lo_ + hi_) / 2
        if (1 / (1 + np.exp(-(lo + mid)))).mean() < yt.mean():
            lo_ = mid
        else:
            hi_ = mid
    r["calibration"]["ece10_test_platt_after_oracle_intercept_shift"] = ece10(yt, 1 / (1 + np.exp(-(lo + (lo_ + hi_) / 2))))
    r["calibration"]["oracle_intercept_shift_logit"] = float((lo_ + hi_) / 2)
    # (d) one threshold
    thr = st["models"][m]["raw"]["threshold_from_validation_max_f1"]
    pred = sc_raw >= thr
    tp, fp, fn, tn = int((pred & (yt == 1)).sum()), int((pred & (yt == 0)).sum()), int((~pred & (yt == 1)).sum()), int((~pred & (yt == 0)).sum())
    r["threshold"] = {"thr": thr, "tp": tp, "fp": fp, "fn": fn, "tn": tn, "accuracy": (tp + tn) / len(yt), "precision": tp / (tp + fp), "recall": tp / (tp + fn), "flagged_share": float(pred.mean()),
                      "majority_accuracy": float(max(yt.mean(), 1 - yt.mean())), "study_accuracy": st["models"][m]["raw"]["test_at_threshold"]["accuracy"]}
    # (f) practical value: precision among the top-k% scored customers
    def prec_at(score, frac):
        k = int(np.ceil(frac * len(yt)))
        return float(yt[np.argsort(-score, kind="mergesort")[:k]].mean())

    r["precision_at_budget"] = {f"{int(f * 100)}%": {"model": prec_at(sc_raw, f), "recency": prec_at(rec, f), "prevalence": float(yt.mean())} for f in (0.1, 0.2, 0.3, 0.5)}
    out["origins"][o] = r
    praw[o] = (yt, cid)

# Holm over 4 on independent p
ps = {f"{o}:{k}": out["origins"][o]["paired_bootstrap_independent"][k]["p"] for o in out["origins"] for k in ("roc_auc", "pr_auc")}
out["holm_independent"] = ic.holm({k: max(v, 1 / 2000) for k, v in ps.items()})
out["raw_p_independent"] = ps
# (e) dependence between origins and between train and test customers
ca, cb = set(praw["A"][1].tolist()), set(praw["B"][1].tolist())
common = sorted(ca & cb)
ya = snaps["A"].loc[common, "inactive"].to_numpy()
yb = snaps["B"].loc[common, "inactive"].to_numpy()
last_train_cut = pd.Timestamp(cfg["origins"]["B"]["train"][-1])
out["dependence"] = {"test_A_customers": len(ca), "test_B_customers": len(cb), "customers_in_both": len(common), "share_of_B_test_customers_also_in_A_test": len(common) / len(cb),
                     "label_correlation_A_vs_B_on_common_customers": float(np.corrcoef(ya, yb)[0, 1]),
                     "share_of_A_test_customers_present_in_A_training_snapshots": float(np.mean([any(snaps_c in set(snapshot(c0).index) for c0 in [cfg["origins"]["A"]["train"][-1]]) for snaps_c in list(ca)[:1]])) if False else None}
tr_cut_A = pd.Timestamp(cfg["origins"]["A"]["train"][0])
seen_in_train_A = set(d[d["day"] < tr_cut_A]["Customer ID"].unique())
out["dependence"]["share_of_A_test_customers_already_present_at_first_A_train_cutoff"] = float(len(ca & seen_in_train_A) / len(ca))
seen_B = set(d[d["day"] < pd.Timestamp(cfg["origins"]["B"]["train"][0])]["Customer ID"].unique())
out["dependence"]["share_of_B_test_customers_already_present_at_first_B_train_cutoff"] = float(len(cb & seen_B) / len(cb))
(AUD / "work" / "step6.json").write_text(json.dumps(out, indent=1, default=float), encoding="utf-8")
for o, r in out["origins"].items():
    print(o, "labels/recency/customer set match raw:", r["labels_equal_raw_derived"], r["recency_equals_raw_derived"], r["test_customer_set_equals_raw_derived_set"], "| agree w/ study:", all(r["agrees_with_study"].values()))
print("holm independent:", out["holm_independent"])
print(json.dumps(out["dependence"], indent=1))
