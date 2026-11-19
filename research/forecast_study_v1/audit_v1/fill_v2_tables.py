"""Assemble manuscript/MANUSCRIPT_v2.md from audit_v1/manuscript_v2_template.md by replacing the <<TABLE_*>> markers with tables generated from the stored audit outputs
(work/step2,4,5,6,16.json). Refuses to overwrite an existing MANUSCRIPT_v2.md unless --force is given. The original MANUSCRIPT.md is never touched."""
import json
import sys
from pathlib import Path

AUD = Path(__file__).parent
STUDY = AUD.parent
W = AUD / "work"
OUT = STUDY / "manuscript" / "MANUSCRIPT_v2.md"
if OUT.exists() and "--force" not in sys.argv:
    sys.exit(f"{OUT} exists; pass --force to rebuild")
j = lambda n: json.load(open(W / f"step{n}.json", encoding="utf-8"))  # noqa: E731
s2, s4, s5, s6, s16 = j(2), j(4), j(5), j(6), j(16)
CELLS = list(s4)
NAME = {"fs1_m5_ca1_H28": "M5 CA_1, H=28", "fs1_m5_ca1_H7": "M5 CA_1, H=7", "fs1_m5_tx1_H28": "M5 TX_1, H=28", "fs1_m5_tx1_H7": "M5 TX_1, H=7", "fs1_or2_top100_H28": "Online Retail II, H=28", "fs1_or2_top100_H7": "Online Retail II, H=7"}
f3 = lambda x: f"{x:.3f}"  # noqa: E731
sg = lambda x: f"{x:+.3f}".replace("-", "−")  # noqa: E731


def table(header, rows):
    return "\n".join(["| " + " | ".join(header) + " |", "|" + "---|" * len(header)] + ["| " + " | ".join(r) + " |" for r in rows])


pooled = []
for c in CELLS:
    r = s2[c]
    m, b = r["metrics"][r["primary"]], r["metrics"][r["ref_matched"]]
    two = lambda k, fm=f3: f"{fm(m[k])} / {fm(b[k])}"  # noqa: E731
    pooled.append([NAME[c], two("wape"), two("agg"), f"{sg(m['bias'])} / {sg(b['bias'])}", f"{m['rmse']:.2f} / {b['rmse']:.2f}", f"{m['mae']:.2f} / {b['mae']:.2f}"])
T_POOLED = table(["Cell", "Pooled item-day WAPE (model / baseline)", "Subset-day aggregate WAPE", "Relative bias", "RMSE", "MAE"], pooled)

lad = []
for c in CELLS:
    m, b = s4[c]["model"], s4[c]["matched_median_reference"]
    lad.append([NAME[c]] + [f"{f3(m[k])} / {f3(b[k])}" for k in ("pooled_wape", "item_week_wape", "subset_week_aggregate_wape", "subset_day_aggregate_wape")])
T_LADDER = table(["Cell", "item-day (pooled)", "item-week", "subset-week", "subset-day"], lad)

bias = []
for c in CELLS:
    r = s16[c]
    bias.append([NAME[c], sg(r["bias_median"]), sg(r["bias_share_from_zero_forecast_rows"]), sg(r["bias_share_from_positive_forecast_rows"]), sg(r["bias_trailing_mean_same_window"]), f3(r["zero_forecast_row_share"]),
                 f"{r['demand_weighted_mean_over_median_of_positive_days']:.2f}"])
T_BIAS = table(["Cell", "Matched median: relative bias", "…of which in rows with a zero forecast", "…of which in rows with a positive forecast", "Matched trailing mean (same window): relative bias", "Share of rows with a zero median forecast",
                "Mean / median of positive-demand days (demand-weighted)"], bias)

cov = []
for c in CELLS:
    e = s5[c]["model"]
    cov.append([NAME[c], f3(e["coverage_overall"]), f"{f3(e['coverage_on_zero_demand_rows'])} ({f3(e['share_zero_demand_rows'])})", f3(e["coverage_on_positive_demand_rows"]), f3(e["by_frequency_segment"]["frequent"]), f3(e["by_frequency_segment"]["intermittent_or_sparse"])])
T_COV = table(["Cell", "All rows", "Zero-demand rows (share of rows)", "Positive-demand rows", "Frequent series", "Intermittent/sparse series"], cov)

pb = []
for o, r in s6["origins"].items():
    a = r["precision_at_budget"]
    pb.append([o] + [f"{a[k]['model']:.3f} / {a[k]['recency']:.3f} / {a[k]['prevalence']:.3f}" for k in ("10%", "20%", "30%", "50%")])
T_PREC = table(["Origin", "Top 10 % flagged", "Top 20 %", "Top 30 %", "Top 50 %"], pb)

text = (AUD / "manuscript_v2_template.md").read_text(encoding="utf-8")
for k, v in {"<<TABLE_POOLED_VS_SUBSETDAY>>": T_POOLED, "<<TABLE_LADDER>>": T_LADDER, "<<TABLE_BIAS>>": T_BIAS, "<<TABLE_COVERAGE>>": T_COV, "<<TABLE_PRECISION>>": T_PREC}.items():
    assert text.count(k) == 1, k
    text = text.replace(k, v)
assert "<<" not in text
OUT.write_text(text, encoding="utf-8")
ab = text[text.index("## Abstract"):text.index("## 1. Introduction")]
print("wrote", OUT.name, "| abstract words:", len(ab.split()) - 2, "| total words:", len(text.split()))
