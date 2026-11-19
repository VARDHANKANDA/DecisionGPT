"""Check the numeric ranges and shares stated in the PROSE of MANUSCRIPT_v2.md that are new in v2 (or restated from the audit) against the stored audit JSON. Prints PASS/FAIL per statement."""
import json
import sys
from pathlib import Path

AUD = Path(__file__).parent
j = lambda n: json.load(open(AUD / "work" / f"step{n}.json", encoding="utf-8"))  # noqa: E731
s3, s4, s5, s6, s16 = j(3), j(4), j(5), j(6), j(16)
M5 = ["fs1_m5_ca1_H28", "fs1_m5_ca1_H7", "fs1_m5_tx1_H28", "fs1_m5_tx1_H7"]
OR = ["fs1_or2_top100_H28", "fs1_or2_top100_H7"]
ALL = M5 + OR
res = []


def chk(name, cond, detail=""):
    res.append(cond)
    print(("PASS " if cond else "FAIL ") + name, detail)


rng = lambda xs: (min(xs), max(xs))  # noqa: E731
lo, hi = rng([s4[c]["ref_forecast_exactly_zero_share_overall"] for c in M5])
chk("M5 zero forecasts 54-69% of rows", round(100 * lo) == 54 and round(100 * hi) == 69, f"{lo:.3f}-{hi:.3f}")
lo, hi = rng([s4[c]["ref_zero_forecast_on_positive_demand_rows"] for c in M5])
chk("M5 zero forecasts on 30-42% of positive-demand rows", round(100 * lo) == 30 and round(100 * hi) == 42, f"{lo:.3f}-{hi:.3f}")
lo, hi = rng([s4[c]["total_demand_in_rows_where_ref_forecasts_zero_share"] for c in M5])
chk("M5 those rows hold 17-24% of demand", round(100 * lo) == 17 and round(100 * hi) == 24, f"{lo:.3f}-{hi:.3f}")
sh = [s16[c]["bias_share_from_zero_forecast_rows"] / s16[c]["bias_median"] for c in M5]
chk("M5 zero-forecast rows ~60-70% of the bias", 0.60 <= min(sh) and max(sh) <= 0.71, f"{min(sh):.2f}-{max(sh):.2f}")
lo, hi = rng([s4[c]["ref_forecast_exactly_zero_share_overall"] for c in OR])
chk("OR II zero forecasts 15-18% of rows", round(100 * lo) == 15 and round(100 * hi) == 18, f"{lo:.3f}-{hi:.3f}")
sh = [s16[c]["bias_share_from_positive_forecast_rows"] / s16[c]["bias_median"] for c in OR]
chk("OR II ~90% of bias in positive-forecast rows", 0.89 <= min(sh) and max(sh) <= 0.93, f"{min(sh):.2f}-{max(sh):.2f}")
lo, hi = rng([abs(s16[c]["bias_trailing_mean_same_window"]) for c in OR])
chk("OR II trailing-mean bias -0.08 to -0.13", round(lo, 2) == 0.08 and round(hi, 2) == 0.13, f"{lo:.3f}-{hi:.3f}")
chk("mean/median ratio ~2.0 (OR II) vs 1.2-1.3 (M5)", abs(s16[OR[0]]["demand_weighted_mean_over_median_of_positive_days"] - 2.0) < 0.02 and all(1.2 <= s16[c]["demand_weighted_mean_over_median_of_positive_days"] <= 1.3 for c in M5))
lo, hi = rng([s4[c]["demand_share_top_decile_series"] for c in M5])
chk("M5 top-10% series hold 47-52% of demand", round(100 * lo) == 47 and round(100 * hi) == 52, f"{lo:.3f}-{hi:.3f}")
chk("OR II top-10% series hold 35% of demand", round(100 * s4[OR[0]]["demand_share_top_decile_series"]) == 35)
chk("ranking reverses at item-week in all six cells", all(s4[c]["model"]["item_week_wape"] < s4[c]["matched_median_reference"]["item_week_wape"] for c in ALL))
chk("median wins only at item-day (model worse there, better at the other 3 levels) in all six", all(s4[c]["model"]["pooled_wape"] > s4[c]["matched_median_reference"]["pooled_wape"] and all(s4[c]["model"][k] < s4[c]["matched_median_reference"][k] for k in ("item_week_wape", "subset_week_aggregate_wape", "subset_day_aggregate_wape")) for c in ALL))
chk("M5 median aggregate WAPE exceeds |bias| by only 0.008", all(abs(s4[c]["matched_median_reference"]["aggregate_minus_abs_bias"] - 0.008) < 0.0005 for c in M5), str([round(s4[c]["matched_median_reference"]["aggregate_minus_abs_bias"], 4) for c in M5]))
chk("CA_1 H28: 0.306 vs 0.299", round(s4[M5[0]]["matched_median_reference"]["subset_day_aggregate_wape"], 3) == 0.306 and round(s4[M5[0]]["matched_median_reference"]["abs_relative_bias"], 3) == 0.299)
z = [s5[c]["model"]["coverage_on_zero_demand_rows"] for c in M5]
p = [s5[c]["model"]["coverage_on_positive_demand_rows"] for c in M5]
chk("M5 zero-demand rows covered 89-94%", round(100 * min(z)) == 89 and round(100 * max(z)) == 94, f"{min(z):.3f}-{max(z):.3f}")
chk("M5 positive-demand rows covered 60-67%", round(100 * min(p)) == 60 and round(100 * max(p)) == 67, f"{min(p):.3f}-{max(p):.3f}")
chk("OR II positive-demand rows covered 79%", all(round(100 * s5[c]["model"]["coverage_on_positive_demand_rows"]) == 79 for c in OR))
zs = [s5[c]["model"]["share_zero_demand_rows"] for c in M5]
chk("M5 zero-demand rows are 54-63% of rows", round(100 * min(zs)) == 54 and round(100 * max(zs)) == 63, f"{min(zs):.3f}-{max(zs):.3f}")
fr = [s5[c]["model"]["by_frequency_segment"]["frequent"] for c in ALL]
chk("frequent series coverage 0.66-0.78", round(min(fr), 2) == 0.66 and round(max(fr), 2) == 0.78, f"{min(fr):.3f}-{max(fr):.3f}")
sim = s3["simulation"]
cv = [sim[k]["coverage_95"]["pigeonhole"] for k in sim]
so = [sim[k]["coverage_95"]["series_only"] for k in sim]
chk("simulation: crossed covers 90-93%, series-only 25-58%", round(100 * min(cv)) == 90 and round(100 * max(cv)) == 93 and round(100 * min(so)) == 25 and round(100 * max(so)) == 58, f"{cv} {so}")
eff = [s3["cells"][c]["dependence"]["effective_independent_cells_approx"] / s3["cells"][c]["dependence"]["cells"] for c in ALL]
chk("effective cells: 1/5-1/6 (M5) and 1/7-1/8 (OR II)", 1 / 6.7 <= min(eff[:4]) and max(eff[:4]) <= 1 / 4.9 and 1 / 8.1 <= min(eff[4:]) and max(eff[4:]) <= 1 / 6.9, f"M5 {min(eff[:4]):.3f}-{max(eff[:4]):.3f}; OR {min(eff[4:]):.3f}-{max(eff[4:]):.3f}")
d = s6["dependence"]
chk("S2 overlap: 4951 customers in both; 94% of B; label corr 0.40; 54%/51% already at first training cutoff", d["customers_in_both"] == 4951 and round(100 * d["share_of_B_test_customers_also_in_A_test"]) == 94 and round(d["label_correlation_A_vs_B_on_common_customers"], 2) == 0.40
    and round(100 * d["share_of_A_test_customers_already_present_at_first_A_train_cutoff"]) == 54 and round(100 * d["share_of_B_test_customers_already_present_at_first_B_train_cutoff"]) == 51)
B = s6["origins"]["B"]["calibration"]
chk("S2 oracle shift -0.80 lowers Platt ECE 0.126 -> 0.019 at B", round(B["oracle_intercept_shift_logit"], 2) == -0.80 and round(B["ece10_test_platt"], 3) == 0.126 and round(B["ece10_test_platt_after_oracle_intercept_shift"], 3) == 0.019)
print(f"\n{sum(res)}/{len(res)} statements verified")
sys.exit(0 if all(res) else 1)
