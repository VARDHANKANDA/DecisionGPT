"""Step 15: writes FORECAST_DESIGN_AND_AGGREGATION_AUDIT.md (sections 6-9 of the audit brief) from work/*.json."""
import json
from pathlib import Path

AUD = Path(__file__).parent
W = AUD / "work"
s1, s4, s5, s6 = (json.load(open(W / f, encoding="utf-8")) for f in ("step1.json", "step4.json", "step5.json", "step6.json"))
CELLS = list(s4)
NAME = {"fs1_m5_ca1_H28": "M5 CA_1, H=28", "fs1_m5_ca1_H7": "M5 CA_1, H=7", "fs1_m5_tx1_H28": "M5 TX_1, H=28", "fs1_m5_tx1_H7": "M5 TX_1, H=7", "fs1_or2_top100_H28": "OR II, H=28", "fs1_or2_top100_H7": "OR II, H=7"}
f3 = lambda x: f"{x:.3f}"  # noqa: E731

lad = ["| cell | level | model | matched median reference | model better? |", "|---|---|---|---|---|"]
for c in CELLS:
    m, b = s4[c]["model"], s4[c]["matched_median_reference"]
    for lab, k in (("item-day (pooled WAPE)", "pooled_wape"), ("item-week (sum 7 days per series first)", "item_week_wape"), ("subset-week (sum all series and 7 days)", "subset_week_aggregate_wape"), ("subset-day (sum all series per day)", "subset_day_aggregate_wape")):
        lad.append(f"| {NAME[c]} | {lab} | {f3(m[k])} | {f3(b[k])} | {'yes' if m[k] < b[k] else 'no'} |")
bias = ["| cell | model |bias| | model agg. WAPE | reference |bias| | reference agg. WAPE | reference agg. WAPE minus |bias| | after a global scale correction (diagnostic): ref. pooled / ref. aggregate | same for model: pooled / aggregate |", "|---|---|---|---|---|---|---|---|"]
for c in CELLS:
    m, b = s4[c]["model"], s4[c]["matched_median_reference"]
    bias.append(f"| {NAME[c]} | {f3(m['abs_relative_bias'])} | {f3(m['subset_day_aggregate_wape'])} | {f3(b['abs_relative_bias'])} | {f3(b['subset_day_aggregate_wape'])} | {f3(b['aggregate_minus_abs_bias'])} | "
                f"{f3(b['after_global_scale_correction']['pooled_wape'])} / {f3(b['after_global_scale_correction']['subset_day_aggregate_wape'])} | {f3(m['after_global_scale_correction']['pooled_wape'])} / {f3(m['after_global_scale_correction']['subset_day_aggregate_wape'])} |")
zs = ["| cell | share of rows where the matched median forecasts exactly 0 | share of positive-demand rows with a zero forecast | share of all demand in rows with a zero forecast | zero-demand rows | top-10% series' share of demand |", "|---|---|---|---|---|---|"]
for c in CELLS:
    r = s4[c]
    zs.append(f"| {NAME[c]} | {f3(r['ref_forecast_exactly_zero_share_overall'])} | {f3(r['ref_zero_forecast_on_positive_demand_rows'])} | {f3(r['total_demand_in_rows_where_ref_forecasts_zero_share'])} | {f3(s1[c]['zero_share_of_targets'])} | {f3(r['demand_share_top_decile_series'])} |")
seg = ["| cell | segment | series | share of demand | contribution to the pooled-WAPE gap (positive = model better), WAPE points | model bias contribution | reference bias contribution | ref. zero-forecast share |", "|---|---|---|---|---|---|---|---|"]
for c in ("fs1_m5_ca1_H28", "fs1_m5_tx1_H28", "fs1_or2_top100_H28"):
    for k, v in s4[c]["segments"].items():
        if k.startswith(("frequency", "volume")):
            seg.append(f"| {NAME[c]} | {k} | {v['n_series']} | {f3(v['share_of_total_demand'])} | {v['contribution_to_pooled_wape_gap_(ref_minus_model)']:+.3f} | {v['model_bias_contribution']:+.3f} | {v['ref_bias_contribution']:+.3f} | {f3(v['ref_share_of_forecasts_exactly_zero'])} |")
cov = ["| cell | overall | zero-demand rows (share of rows) | positive-demand rows | frequent series | intermittent/sparse series | min-max over the six test blocks |", "|---|---|---|---|---|---|---|"]
for c in CELLS:
    e = s5[c]["model"]
    bl = list(e["coverage_by_block"].values())
    cov.append(f"| {NAME[c]} | {f3(e['coverage_overall'])} | {f3(e['coverage_on_zero_demand_rows'])} ({f3(e['share_zero_demand_rows'])}) | {f3(e['coverage_on_positive_demand_rows'])} | {f3(e['by_frequency_segment']['frequent'])} | {f3(e['by_frequency_segment']['intermittent_or_sparse'])} | {f3(min(bl))} - {f3(max(bl))} |")
pb = ["| origin | top 10% flagged: model / recency / prevalence | 20% | 30% | 50% |", "|---|---|---|---|---|"]
for o, r in s6["origins"].items():
    a = r["precision_at_budget"]
    pb.append(f"| {o} | " + " | ".join(f"{a[k]['model']:.3f} / {a[k]['recency']:.3f} / {a[k]['prevalence']:.3f}" for k in ("10%", "20%", "30%", "50%")) + " |")
assert all(s4[c]["matched_median_reference"]["after_global_scale_correction"]["pooled_wape"] > s4[c]["model"]["after_global_scale_correction"]["pooled_wape"] for c in CELLS)
A, B = s6["origins"]["A"], s6["origins"]["B"]
dep = s6["dependence"]

TXT = f"""# FORECAST_DESIGN_AND_AGGREGATION_AUDIT

Independent audit of the forecasting design, the aggregation-level finding, the interval claims and the customer-inactivity study (sections 6-9 of the audit brief). Numbers are from audit code that does not import the study's code (`step1`, `step4`, `step5`, `step6`).

## 1. Forecasting design

**Verified independently (all six cells).**
* Stored evaluation targets equal the raw data: M5 from `sales_train_evaluation.csv` (per-series, per-day), Online Retail II from an independent re-cleaning of the raw CSV; the 100-SKU list is identical to the stored one.
* Row sets: S x 168 rows per cell (58,800 / 58,800 / 16,800), unique (series, day) pairs, no missing or negative targets; the last test day is the last data day.
* **All 16 baselines** (8 estimators x matched/fresh) re-implemented from raw data with explicit slicing (`hist = y[series, :cutoff+1]`, so no future value is reachable) match the stored baselines on every row, in every cell. Matched baselines use data exactly H days old (minimum gap 7 / 28 days); fresh baselines use data 1 to H days old. Baselines therefore use only information available at their cutoff.
* Segment labels (ADI/CV^2, volume terciles) recomputed from raw history before the first validation block equal the stored labels.
* Study-recorded perturbation checks that features are unchanged when the future is overwritten passed at four cutoffs per cell (`results.json`); the feature builder itself was **not** independently re-audited (historical code; model prediction generation was not re-executed).

**Definitions the manuscript should state (currently missing or ambiguous).**
1. **"Horizon" and "origin".** H is the *minimum lag of the features*: every target day is forecast from information at least H days old. For H = 28 the first day of a block is forecast from data ending 28 days earlier (not from the data ending the day before the block); for H = 7 each target day has its own daily origin. The six "origins" are six **retraining blocks** (28 target days, 4 weekly sub-blocks; 24 weekly blocks per cell). This is a legitimate direct-forecast design, but it is **not** the M5 competition setting (28 days forecast from one origin with data to the origin), so results are not comparable to M5 scores.
2. **M5 test window.** The last block d_1914-d_1941 is described as "exactly the official evaluation window". The official Kaggle data page lists `sales_train_evaluation.csv` as d_1-d_1941, "labels used for the Public leaderboard"; the final evaluation period of the competition was a later 28-day window. Correct this sentence.
3. **M5 series selection.** 350 series per store were drawn with a department-stratified random rule restricted to series whose first sale is on or before day 1100 (series launched later are excluded) - not stated in the manuscript. The subset is therefore not a random sample of the store's series.
4. **Online Retail II cleaning.** Cancellations (invoice 'C'), non-positive quantity or price, non-product codes and **33,666 exact-duplicate lines** (3 %) are dropped; returns are excluded from demand; calendar-complete days including closed days are real zeros; customers without ID are kept for demand. The top-100 SKUs by revenue are high-volume items (top-10 % of series hold 35 % of demand) and are not typical intermittent demand (zero demand 32 %, zero-forecast share 15-18 %).
5. **Model training span and information.** Training rows are those whose target day lies in [o-730, o-1], validation uses 3 blocks, hyper-parameters come from a small grid (<= 2 variants per family), seed 42, software versions recorded (numpy 2.5.2, scikit-learn 1.9.0, lightgbm 4.7.0, xgboost 3.4.0, catboost 1.2.10, Python 3.12.0, Windows 11, 4 threads). **No candidate used an L1/quantile objective** (ridge, squared-error boosting, LightGBM l2/tweedie, CatBoost RMSE).
6. **Fairness of information and tuning.** Baselines are untuned (fixed smoothing 0.1, fixed windows) but 16 are searched on validation; models are searched over 9 configurations. This is comparable, and the manuscript's matched/fresh split makes the information treatment explicit. The learned model's disadvantage is the loss mismatch, not information.
7. **Generalisation.** Two Walmart stores (350-series subsets) and one UK wholesaler's top-100 SKUs. The manuscript's scope limits (Sections 19, 1) are appropriate; the abstract's closing sentence ("For intermittent retail demand, whether ...") generalises beyond them.

## 2. The aggregation-level finding

The reported reversal reproduces exactly from raw predictions, in every cell: the matched median baseline has the lower item-day pooled WAPE, the model has the lower aggregate WAPE. What produces it:

**Table 1. The same forecasts scored at four aggregation levels (WAPE; sums taken before scoring).**

{chr(10).join(lad)}

* The **ranking flips already at item-week level** in all six cells: summing seven days of a sparse series before scoring is enough to make the model better. Item-day pooled WAPE is the only level at which the baseline wins.
* The manuscript's "store-day" aggregate is an aggregate over the 350 (M5) or 100 (OR II) selected series, **not a store**. Rename it "subset-day".

**Table 2. Bias and the aggregate metric.** Aggregate WAPE = sum over days of |daily total error| / total demand, so it is at least |relative bias| (the identity held in every case). Diagnostic columns apply a single global scale factor (using test totals: a diagnostic, not a method).

{chr(10).join(bias)}

* On M5 the median baseline's aggregate WAPE exceeds its |bias| by only 0.008: its aggregate error **is** its level bias (it under-forecasts total demand by 28-34 %). The reversal at that level is therefore close to an arithmetic consequence of the bias, not a separate finding about forecast quality.
* After a global scale correction the median baseline's *pooled* WAPE rises above the model's in all six cells, i.e. the baseline's pooled-WAPE advantage is bought with the downward bias (a diagnostic using test totals; not a recommendation).

**Table 3. Where the zeros are.**

{chr(10).join(zs)}

* On M5 the trailing median forecasts exactly zero on 54-69 % of rows, including 30-42 % of rows with positive demand (which hold 17-24 % of all demand). This is a property of sparse daily series combined with a 28-day median (it needs more than 14 zero days); it is **not** a universal property of median forecasting, and frequent series have few zero forecasts (3-10 %).
* On Online Retail II the median forecasts zero on only 15-18 % of rows, yet its bias is -0.55 to -0.58: there the under-forecast comes from **right-skewed order sizes** (median << mean), not from zeros. The manuscript's single "mechanism" paragraph (Section 10) is correct for M5 and wrong for Online Retail II.
* The top-10 % of series hold 47-52 % (M5) and 35 % (OR II) of demand: pooled metrics are dominated by a few series, so the segment table below matters.

**Table 4. Contribution of segments to the pooled-WAPE gap (positive = model better).**

{chr(10).join(seg)}

* On M5 CA_1 the model gains on frequent and high-volume series (+0.017, +0.023 WAPE points) and loses on sparse and low-volume series (-0.036, -0.028; the 300 sparse series hold 53 % of demand). On M5 TX_1 it loses almost everywhere (sparse -0.090). On Online Retail II it is a near-tie on frequent series and loses on sparse/low-volume ones.

**What each metric answers, and what it hides.**
* *Item-day pooled WAPE* answers "how far off is my forecast for this product on this day, in units, summed over products" - the right question for per-item, per-day replenishment or picking decisions, where a missed unit and an excess unit are equally costly. It conceals bias (a forecast that is systematically too low can score well) and is dominated by high-volume series.
* *Aggregate (subset-day or item-week) WAPE* answers "do my totals over a day or week match demand" - the right question for staffing, budgeting or capacity. It conceals item-level errors that cancel in the sum, and for a biased method it is almost exactly the bias.
* Neither shows which model is "better" in general. The defensible statement is **descriptive**: for these datasets, item-day absolute error favours a zero-leaning median forecast, while any aggregation over days or items favours the learned model, and the difference is mostly bias. The manuscript should not imply a causal or universal statement, and should cite the theory that explains it (Gneiting 2011; Kolassa 2020; Prestwich et al. 2014).

## 3. Prediction intervals

The audit re-implemented the Mondrian split-conformal procedure (calibration = stored validation predictions of the same method; test = stored test predictions) and reproduced every study coverage value exactly.

**Table 5. Empirical coverage of the model's nominal 80 % intervals.**

{chr(10).join(cov)}

* Calibration and test data are separated correctly (validation blocks end before the first test day). The marginal coverage claim (0.79-0.81) is verified.
* **The marginal figure is carried by zero-demand rows.** On M5, 54-63 % of rows have zero demand and are covered at 89-94 %, because the lower bound is clipped at zero and the upper bound is positive; rows with positive demand are covered at only 60-67 % on M5 (79 % on Online Retail II). The manuscript reports marginal coverage plus a frequent/intermittent split (frequent 0.66-0.78) but not this split, which is the more informative one. Do not describe the result as "near-nominal" or "calibrated"; say that overall coverage is close to 80 % while conditional coverage is not.
* Exchangeability between calibration (earlier origins) and test is assumed, not shown; with trend or shift the guarantee is void, and there is no formal coverage guarantee under these dependence conditions. Only marginal empirical coverage can be claimed.
* Comparisons of widths between model and baselines are computed with the same procedure (consistent); baseline intervals over-cover on M5 (0.83-0.87) and under-cover on Online Retail II.

## 4. Customer-inactivity study

* **Label and windows verified from raw transactions** (independent cleaning, same rules): the test customer sets, the 90-day inactivity labels and the recency scores equal the stored ones at both origins (A: test cutoff 2011-06-12, B: 2011-09-10; label windows end at the next cutoff or inside the data). The target is **inactivity of customers of one UK wholesaler**, not churn, and the manuscript says so; keep it that way (no "verified churn", retention or business-impact claims).
* **Metrics reproduce:** ROC-AUC / PR-AUC (model, recency), paired customer bootstrap, Holm, ECE, the one-threshold confusion metrics. Independent Holm p: 0.002, 0.002, 0.002, 0.024.
* **Practical meaning is small.** Precision among the customers flagged at fixed contact budgets (model / recency / prevalence):

{chr(10).join(pb)}

At origin A the recency rule is as good or better in the top 10 % (0.958 vs 0.950); at origin B the model is ahead by 0.1 to 1.8 percentage points depending on the budget. The F1-optimal threshold chosen on validation flags 85.5 % (A) and 83.5 % (B) of customers (recall 0.955 / 0.966), i.e. close to "flag everyone"; its accuracy (0.762, 0.691) exceeds the majority-class accuracy (0.677, 0.565) but is dominated by prevalence.
* **Calibration deterioration is explained by prevalence shift.** At origin B the validation prevalence was 0.677 and the test prevalence 0.565; the mean Platt-calibrated prediction on test was {B['calibration']['mean_pred_test_platt']:.3f}. A diagnostic intercept shift (which uses the test labels and is therefore not a method) of {B['calibration']['oracle_intercept_shift_logit']:.2f} logits lowers the Platt ECE from {B['calibration']['ece10_test_platt']:.3f} to {B['calibration']['ece10_test_platt_after_oracle_intercept_shift']:.3f}; at origin A the shift is {A['calibration']['oracle_intercept_shift_logit']:.2f} and ECE is unchanged ({A['calibration']['ece10_test_platt']:.3f} vs {A['calibration']['ece10_test_platt_after_oracle_intercept_shift']:.3f}). The manuscript's distinction between ranking performance and probability calibration is correct and supported.
* **The two origins are not independent evidence.** {dep['customers_in_both']:,} customers are in both test snapshots ({100 * dep['share_of_B_test_customers_also_in_A_test']:.0f} % of origin B's test customers); their labels correlate at {dep['label_correlation_A_vs_B_on_common_customers']:.2f}; and about {100 * dep['share_of_A_test_customers_already_present_at_first_A_train_cutoff']:.0f} % of each test cohort already appears in the earliest training snapshot (repeated measures on the same customers with different features and labels). The reported "supported at both origins" is therefore closer to one study with partially overlapping customers.
* **Customer-split sensitivity:** with half of the customers, the origin-A advantage disappears (ROC-AUC +0.011 [-0.006, +0.028]) and the origin-B advantage persists (+0.041 [0.030, 0.053]); this run was not independently re-executed.
* **Recommendation:** the inactivity study adds a small, partly fragile result with a different data set and label; it dilutes the forecasting paper. Move it to a clearly labelled exploratory appendix or to a separate future study with an independent cohort, and add the practical-value table.
"""
(AUD / "FORECAST_DESIGN_AND_AGGREGATION_AUDIT.md").write_text(TXT, encoding="utf-8")
print("written", len(TXT.split()), "words")
