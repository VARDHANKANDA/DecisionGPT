"""Step 12: claim-evidence matrix. Each claim is located in MANUSCRIPT.md by an anchor string (section and line are computed, not typed)."""
import csv
import re
from pathlib import Path

AUD = Path(__file__).parent
MS = (AUD.parent / "manuscript" / "MANUSCRIPT.md").read_text(encoding="utf-8").splitlines()
V, P, U, C, N = "verified", "partially supported", "unsupported", "contradicted", "unverifiable"

# (anchor, claim (concise), artifact / primary source, independent verification method, verdict, required correction or qualification)
CLAIMS = [
    ("pre-registered (plan and code hashed", "Study was pre-registered (plan and code hashed before any confirmatory run)", "FREEZE.json; EXPERIMENT_PLAN.md; file mtimes; session transcript", "Hash recomputation (plan text above deviation log unchanged; code hashes unchanged); chronology from mtimes and transcript timestamps", P,
     "Hashing before the confirmatory runs is verified, but this is an internal freeze, not an externally time-stamped registration; two quick smoke runs scored real test data (ridge, M5 CA_1 block 1773; S2 both origins) before the freeze. Say 'pre-specified and internally frozen' and disclose."),
    ("six-origin evaluation", "'Six-origin evaluation' ... horizons of 7 and 28 days", "results/*/config.json", "Read windows from config; recompute block membership of every row", P,
     "Verified: 6 retraining blocks of 28 days per cell (24 weekly blocks). But for H=7/28 the 'horizon' is the minimum feature lag: every target day is forecast from data >= H days old; for H=7 forecast origins are daily. Define 'origin', 'block' and 'horizon' explicitly; do not call the six blocks 'forecast origins' without that definition."),
    ("16 simple baselines", "16 simple baselines (8 estimators x matched or fresher information)", "results/*/predictions.npz", "Independent re-implementation of all 16 baselines from raw data with explicit slicing (step1)", V, "None (note: Croston/TSB initialisation conventions are defined only by the study code)."),
    ("All methods were scored on identical rows", "All methods were scored on identical rows", "predictions.npz", "Row count = series x 168 days in all 6 cells; unique (series, day) pairs; equal length of all method arrays", V, "None."),
    ("crossed series", "Confirmatory estimand: relative pooled-WAPE change vs best validation baseline; crossed bootstrap; Holm over six tests", "EXPERIMENT_PLAN.md s5; analyze.py", "Formula recomputed independently; independent bootstrap + two-way cluster-robust delta method reproduce estimates, CIs and verdicts", V, "Report that the crossed bootstrap is an approximation (simulated coverage 0.90-0.93 for a nominal 0.95 with 24 week blocks)."),
    ("contradicted in three", "H1 contradicted in three cells (-3.7% to -11.4%; Holm p <= 0.016), inconclusive in three (-2.6% to -3.7%)", "CONFIRMATORY_SUMMARY.md", "Independent decisions under the frozen rule: identical for all 6 cells under bootstrap and under the delta method", V, "Holm p printed as '<0.001' for TX_1/other cells exceeds the resolution of a 2000-draw bootstrap (min raw p 0.0005, x up to 6 under Holm): write '<0.003' or use an analytic/larger-B p-value."),
    ("always a trailing 28-day median", "The best baseline was always a trailing 28-day median", "selection.json (all cells)", "Read selection files; recompute pooled WAPE ranking of all 21 methods", V, "None. Note the choice is made on validation WAPE, itself a median-favouring metric."),
    ("relative bias −0.28 to −0.58", "Median baseline 'forecasts close to zero for sparse series (relative bias -0.28 to -0.58)'", "TABLES T1; audit step4", "Bias recomputed; share of exactly-zero forecasts by cell and segment", P,
     "Bias range verified. 'Close to zero' is true for M5 (zero forecasts on 55-69% of rows, 30-42% of positive-demand rows) but not for Online Retail II (15-18% zero forecasts): its -0.55...-0.58 bias comes from right-skewed demand (median << mean), not zero forecasts."),
    ("0.08–0.11 on M5", "Store-day aggregate WAPE 0.08-0.11 (model) vs 0.29-0.35 (median) on M5", "TABLES T1", "Recomputed from stored predictions; identity aggregate WAPE >= |relative bias| checked", P,
     "Numbers verified. 'Store-day' is wrong: the aggregate is over the 350-series (M5) or 100-SKU (OR II) subset, not the store. The reversal is largely arithmetic: the median's aggregate WAPE exceeds its |bias| by only 0.008 on M5, and the ranking already reverses at item-week level in all six cells."),
    ("post-hoc refit with an L1 objective", "Post-hoc L1 refit matched or beat the median baseline in pooled WAPE but lost the aggregate advantage", "results/E1_l1_*.json", "Independent recomputation of E1 metrics and CIs (step8)", P,
     "Numbers verified and correctly labelled post hoc. Qualify: vs the matched baseline it won on 2 of 3 datasets (TX_1 tie); vs the best (fresh) baseline it only tied on M5; the aggregate advantage was lost on M5 but not on Online Retail II (0.523 vs 0.730)."),
    ("Calendar and history-statistic features helped", "Calendar and history-statistic features helped (+2.6%, +3.5% when removed); price and identifiers did not measurably", "ABLATIONS_fs1_m5_ca1_H28.json", "Independent recomputation of the four ablations (step8); features removed checked in config files", P,
     "Verified for M5 CA_1, H=28 only and exploratory; the abstract omits both qualifiers. Holm p '<0.001' is below bootstrap resolution (independent Holm p = 0.002 at the floor)."),
    ("covered 79–81 % overall but under-covered frequent series", "80% conformal intervals covered 79-81% overall but under-covered frequent series", "TABLES T5; audit step5", "Independent Mondrian conformal implementation; coverage by block, segment, zero/positive demand", P,
     "Verified numerically, but the marginal coverage is carried by zero-demand rows: coverage on zero-demand rows 85-94%, on positive-demand rows 60-67% on M5 (79% on Online Retail II). Report coverage separately for zero and positive demand; do not present 'near-nominal' coverage as calibration."),
    ("ROC-AUC at both origins (+0.028, +0.037)", "Best classifier beat a recency baseline in ROC-AUC at both origins (+0.028, +0.037)", "results/s2_online_retail_inactivity", "Labels and recency re-derived from raw transactions; AUC/AP, paired customer bootstrap and Holm recomputed", P,
     "Numbers verified. The two origins share 94% of test customers (label correlation 0.40), so they are not independent replications; the PR-AUC gain at origin A is +0.010 and the customer-split check at A is not significant; practical gain at fixed contact budgets is 0-2 points of precision."),
    ("calibrator fitted on validation worsened calibration", "A calibrator fitted on validation worsened calibration when prevalence shifted", "TABLES S2a; audit step6", "Mean predictions vs prevalence; diagnostic intercept shift using test labels", V,
     "Verified: at origin B an oracle intercept shift of -0.80 logits reduces Platt ECE from 0.126 to 0.019, consistent with prevalence shift (diagnostic only)."),
    ("decided by the choice of metric, aggregation level and baseline strength at least as much as by the model", "Metric, aggregation level and baseline strength decide 'beats the baseline' at least as much as the model does", "-", "No variance decomposition was run; 3 datasets, one model family selected; known from theory (Gneiting 2011; Kolassa 2020)", P,
     "Replace by a descriptive statement scoped to these data; 'at least as much as the model' is not quantified. Cite the loss-function literature and present the result as an empirical illustration, not a discovery."),
    ("All code, predictions and verification scripts are provided", "All code, predictions and verification scripts are provided", "research/forecast_study_v1/", "File inventory", P,
     "Present in the local repository only; not public. Stored predictions embed actual M5 sales values, whose terms (Kaggle rules) forbid redistribution: do not publish predictions.npz with actuals without permission."),
    ("tree-based methods dominated the top of the M5 accuracy competition", "Tree-based methods dominated the top of the M5 accuracy competition", "Makridakis et al. 2022a (article body); Januschowski et al. 2022", "Read the M5 article page: LightGBM used by all top-50 teams", V, "None."),
    ("Yet applied comparisons often still report one forecast origin", "Applied comparisons often report one origin, a weak reference, and series-only bootstrap", "-", "No citation or survey in the manuscript", U, "Add evidence (e.g. count in a sample of studies) or soften to 'can'."),
    ("Kolassa [2020] shows that", "Kolassa shows the best point forecast depends on the error measure - the mechanism behind our central finding", "Kolassa 2020 (page read)", "Source text read: expected value minimises MSE; quantiles minimise other measures", V,
     "Supported, and it undermines novelty: the central finding is an instance of the known result (also Gneiting 2011; Prestwich et al. 2014). Reposition the contribution."),
    ("deterministic rule of the historical benchmark", "350 series per store drawn by the historical deterministic rule", "ml/benchmark/datasets.py", "Read the loader; independent targets equal raw CSV", P,
     "The rule includes an eligibility filter (first sale on or before day 1100, i.e. products launched later are excluded) and department stratification; the manuscript omits both. Add them."),
    ("exactly the official evaluation window", "The last test block is exactly the official evaluation window (d_1914-d_1941)", "Kaggle M5 data page; M5 rules", "Official page: sales_train_evaluation.csv d_1-d_1941, 'labels used for the Public leaderboard'", C,
     "d_1914-d_1941 are the public-leaderboard (validation-phase) labels, not the final evaluation window. In addition each day here is forecast from data >= H days old, unlike the competition setup. Correct the sentence and state that results are not comparable to M5 competition scores."),
    ("100 SKUs with the largest revenue before the first validation block", "Online Retail II: 100 top-revenue SKUs before the first validation block", "metadata.json series_ids", "Independent cleaning of the raw CSV and re-derivation of the SKU list (identical)", V, "Document the cleaning rules (cancellations, non-positive quantity/price, non-product codes, 33,666 exact-duplicate lines dropped) in the manuscript."),
    ("six consecutive 28-day test blocks", "Six 28-day test blocks cover the last 168 days; three validation blocks precede them without overlap", "config.json windows", "Read windows; confirmed day ranges and ordering", V, "None."),
    ("Selection before test", "Selection written to disk before any test block is fitted; verifier checks modification times", "selection.json; fits/*.npy mtimes", "selection.json mtime precedes the first test fit by 0-2 s in all 6 cells and follows all 27 validation fits", P, "Verified; timestamps are mutable and this is not external evidence. Also state that cells ran sequentially and results of earlier cells were visible before later cells' (automated) selection."),
    ("Ridge, HistGradientBoosting, XGBoost", "Five model families, two small variants each (CatBoost one)", "config.json families", "Read config of each cell", V, "State explicitly that no candidate used an L1/quantile objective (the metric's Bayes-optimal functional is the median)."),
    ("Primary: pooled WAPE", "WAPE definition and metric policies; no MAPE", "metrics.py; audit_core", "Independent definition: sum|e| / sum y; undefined handling", V, "None."),
    ("mean per-series RMSSE", "Secondary metrics include mean per-series RMSSE and per-series summaries", "results.json", "Searched the manuscript results", P, "RMSSE and per-series summaries are listed in Methods but never reported; report them or remove them."),
    ("The estimand is the relative WAPE improvement", "Estimand = (WAPE_ref - WAPE_model)/WAPE_ref pooled over blocks", "analyze.py; plan", "Formula implemented independently; signs in tables/figures/prose consistent", V, "None."),
    ("A result is called *supported* only if", "Frozen decision rule for H1", "EXPERIMENT_PLAN.md s5", "Rule applied independently to independently computed intervals", V, "State that 'contradicted' (CI entirely below 0) is not multiplicity-adjusted."),
    ("calibrated on the validation predictions of the same method", "Conformal intervals calibrated on validation predictions, evaluated on test", "predictions.npz val_* arrays", "Independent implementation reproduces coverage exactly in all 6 cells", P,
     "Procedure verified; but calibration residuals come from earlier origins (not exchangeable with test under drift) and bins are by predicted size: only marginal coverage can be claimed. The term 'Mondrian' conformal is, to my knowledge, due to Vovk and co-authors (NOT verified in this audit): check the attribution before submission."),
    ("Two rolling origins", "Classification: two rolling origins with chronologically earlier training/validation snapshots", "run_classification_study.py; raw data", "Label windows checked against raw data; labels/recency/customer sets equal raw-derived values at both origins", V, "Describe the customer overlap between origins and between training and test snapshots (94% / about 50%)."),
    ("Table 1.", "Table 1: WAPE of baseline and model, improvement, blocks won", "METRIC_RECOMPUTATION.csv", "All values recomputed from stored predictions", V, "None."),
    ("H1 was **not supported in any", "H1 not supported in any of the six cells", "CONFIRMATORY_SUMMARY.md", "Independent verdicts identical", V, "None."),
    ("all 36 leave-one-origin-out estimates are negative", "All 36 leave-one-origin-out estimates are negative", "analysis.json", "Recomputed", V, "None."),
    ("Table 2.", "Table 2: pooled vs aggregate WAPE, bias, RMSE, MAE per cell", "METRIC_RECOMPUTATION.csv", "All values recomputed", V, "Rename 'store-day aggregate'."),
    ("a trailing median of a sparse series is zero on most days", "A trailing median of a sparse series is zero on most days, giving low item-day absolute error while under-forecasting totals by 28-58%", "audit step4", "Zero-forecast share by dataset and segment", P, "True of sparse M5 series; for Online Retail II the under-forecast comes from skewness. Restate per dataset."),
    ("Pooled WAPE is minimised by a conditional median", "Pooled WAPE is minimised by a conditional median [Kolassa, 2020]", "Gneiting 2011; Kolassa 2020", "Theory; Gneiting's result also verified at abstract level", V, "Cite Gneiting (2011) as the primary source."),
    ("best method by pooled WAPE was a trailing median in all six cells", "Best by pooled WAPE a trailing median in all six; best by aggregate WAPE a boosted model in all six", "audit step11", "Ranked all 21 methods per cell from stored predictions", V, "None."),
    ("Kendall τ between −0.06 and 0.38", "Kendall tau between pooled and aggregate rankings -0.06 to 0.38, significant only on Online Retail II", "audit step11", "Recomputed with scipy on independently computed metrics", V, "None."),
    ("The crossed series × week-block interval was 21–47 % wider", "Crossed intervals 21-47% wider than series-only; agree with stationary bootstrap", "TABLES T2; audit step3", "Independent bootstraps: ratio 1.2-1.5", V, "Add the simulation evidence that series-only intervals badly under-cover (0.25-0.58 vs 0.95 nominal) and crossed ones slightly under-cover (0.90-0.93)."),
    ("On M5 CA_1 the model improved on the matched baseline for frequent", "Segment results on M5 CA_1 (frequent +6.3%, intermittent -8.0%, high volume +4.8%, low volume -35.0%) and non-replication on TX_1", "TABLES T4", "Independent segment labels from raw history (identical) and independent segment bootstraps", V, "Exploratory; 8 segment x 6 cell comparisons unadjusted."),
    ("not evidenced as useful for reducing forecast error", "The model's price coefficients are consequently not evidenced as useful for reducing forecast error", "ablation", "-", P, "Tree models have no price 'coefficients'; say 'price features'."),
    ("With the median objective the model matches or beats", "E1 table and interpretation; no single configuration wins both scores", "E1 files", "Recomputed", V, "Keep the post-hoc label in every mention, including the abstract."),
    ("Mondrian split-conformal 80 % intervals calibrated on validation predictions", "Conformal coverage values 0.793-0.810; per-origin 0.775-0.824; frequent 0.66-0.78; intermittent 0.81-0.82; baselines 0.83-0.87 (M5) / 0.77-0.79 (OR II)", "TABLES T5", "Independent implementation", P, "Numbers verified; add zero vs positive demand coverage (see abstract claim)."),
    ("*Confirmatory comparison (C).*", "Classifier beats recency baseline in ROC-AUC and PR-AUC at both origins (Holm)", "S2 results", "Independent bootstrap and Holm (A PR-AUC p = 0.024)", V, "State dependence between origins."),
    ("differed by at most 0.009", "Four classifiers' test ROC-AUCs differ by at most 0.009", "audit step11", "AUC recomputed for all four from stored scores (0.0089, 0.0046)", V, "None."),
    ("*One-threshold metrics.*", "Accuracy 0.762/0.691 vs majority 0.677/0.565; recall 0.955/0.966; precision 0.757/0.653; F1-optimal threshold flags nearly everyone", "audit step6", "Recomputed from stored scores; flagged share 85.5%/83.5%", V, "None."),
    ("*Customer-disjoint sensitivity.*", "Customer-split check: origin B holds; origin A not distinguishable from zero", "S2_customer_disjoint.json", "Not independently re-executed (requires refits); stored values consistent with main run", N, "Mark 'not independently verified'. The split preserves chronology (earlier cutoffs) and separates customers randomly; test sample halves."),
    ("Reporting a single pooled WAPE against seasonal naive", "A single pooled WAPE against seasonal naive would show boosted models winning (0.89 vs 0.74)", "TABLES", "0.894 vs 0.743 recomputed", P, "Numbers verified; 'the common comparison' is an unsupported generalisation."),
    ("same model was far better at the store-day aggregate level and on RMSE", "Model far better at aggregate level and on RMSE", "Table 2", "Recomputed", V, "Rename 'store-day'; RMSE advantage is small on M5 TX_1 (2.07 vs 2.13)."),
    ("24/24 checks passed in each of the six cells", "Study's own verification: 24/24 (6 cells), 19/19 (4 ablations); 23 unit tests", "results/*/verification.json", "Read verification.json; independent audit supersedes it", V, "The study's verifier shares authorship with the study; present the independent audit result instead or as well."),
    ("Twenty-three unit tests", "23 unit tests cover leak-free baselines, metrics, bootstrap, conformal", "tests/unit/test_forecast_study.py", "Study tests re-run during the audit: 23 passed", V, "State explicitly that unit tests establish software correctness, not scientific validity."),
    ("*External validity.*", "External validity limited to two Walmart stores and one UK wholesaler", "-", "-", V, "Adequate; add the missing limitations listed in STATISTICAL_AUDIT.md and BLOCKER_CHECKLIST.md."),
    ("@REPRO", "Backend suite 1760 passed / 34 skipped (stated in REPRODUCIBILITY.md section 6, not in the manuscript)", "REPRODUCIBILITY.md", "Not rerun in this audit", N, "Historical report value; not part of the study's scientific evidence."),
]


def locate(anchor):
    if anchor == "@REPRO":
        return None
    hits = [i for i, l in enumerate(MS) if anchor in l]
    return hits[0] + 1 if hits else None


def section_of(line):
    sec = ""
    for l in MS[:line]:
        if l.startswith("## "):
            sec = l[3:].strip()
    return sec


rows, missing = [], []
for a, claim, art, method, verdict, fix in CLAIMS:
    ln = locate(a)
    if ln is None and a != "@REPRO":
        missing.append(a)
    rows.append({"claim": claim, "manuscript_section": section_of(ln) if ln else ("(REPRODUCIBILITY.md; not in manuscript)" if a == "@REPRO" else "NOT FOUND"), "manuscript_line": ln or "", "supporting_artifact_or_source": art, "independent_verification_method": method, "verdict": verdict, "required_correction_or_qualification": fix})
with open(AUD / "CLAIM_EVIDENCE_MATRIX.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0]))
    w.writeheader()
    w.writerows(rows)
from collections import Counter
print(len(rows), "claims;", Counter(r["verdict"] for r in rows), "| anchors not found:", missing)
