"""Writes quality_gate/SCIENTIFIC_ISSUES.csv (issue register of the R3 quality gate). Resolutions are updated by editing this file and re-running it."""
import csv
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "SCIENTIFIC_ISSUES.csv"
COLS = ["id", "severity", "category", "finding", "evidence", "affected_claims", "type", "recommended_action", "status_or_resolution"]
ROWS = [
    ("SI-01", "major", "design / selection",
     "Validation margins between the selected median-type model and its runner-up are tiny (0.02-1.1 % relative validation WAPE; typically LightGBM absolute error vs the 0.5-quantile objective). The selected configuration is nearly a coin flip within the median-type class; with three validation blocks the choice carries selection noise that the test intervals do not include.",
     "quality_gate/results/audit_sensitivity.json (B_selection_margins); E2: quality_gate/results/e2_selection_robustness.json (if run)", "'absolute-error LightGBM beats ...' (abstract, H1, conclusions)", "design limitation (not a coding bug)",
     "Describe the finding as a property of the median-type class; report E2 (all eight candidates on the W2 test blocks, exploratory) and the validation margins; do not present the single selected configuration as uniquely best.", "OPEN until E2 is reported in R3"),
    ("SI-02", "major", "utility / metric",
     "The item-day advantage is specific to (near-)symmetric absolute error: under pinball loss at tau = 0.7, 0.8, 0.9 the improvement shrinks, is non-significant in most cells and negative in several cells at tau = 0.9. No cost data exist; a WAPE improvement does not establish decision utility.",
     "quality_gate/results/audit_sensitivity.json (C_pinball_exploratory)", "item-day improvement as evidence of usefulness; practical reading", "scientific scope limitation", "Report as exploratory sensitivity; state that the gain is not shown for asymmetric / service-oriented loss.", "Added to R3 (exploratory table)"),
    ("SI-03", "major", "missing competitors",
     "No ETS / ARIMA / Theta (or neural / probabilistic) competitors in v2; 'best simple baseline' can be misread as 'best forecasting method'.",
     "PROPOSAL_STATISTICAL_BASELINES.md; manuscript Limitations", "scope of the headline claim", "design limitation",
     "Run a separately versioned fresh-window study (v3) with ETS / ARIMA / Theta; keep the v2 claim limited to the prespecified baseline set.", "See EXPERIMENT_DECISION.md and forecast_study_v3_fresh_stats"),
    ("SI-04", "major", "reporting",
     "H1b (vs baselines with fresher information) is inconclusive at H = 28 in all four datasets (point estimates -1.4 % ... +2.2 %); 'beats the best simple baseline' holds only for same-information baselines.",
     "analysis_W2.json (H1b); Table 2", "headline claim", "reporting prominence", "Make the H1b result prominent in the title/abstract/introduction (R3).", "Done in R3"),
    ("SI-05", "moderate", "inference",
     "The dual-method rule gives limited corroboration for the item-day endpoint: the crossed bootstrap and the cluster-robust delta method both treat weeks as independent clusters and use the same cell-total array, so they fail together under weekly dependence. Weekly differences are positively autocorrelated in several cells (lag-1 up to +0.65; AR(1) effective weeks as low as ~5 of 24).",
     "quality_gate/results/audit_sensitivity.json (A_weekly_dependence)", "H1 / H2 verdicts, interval widths", "design limitation",
     "Sensitivity analysis with a stationary-block week bootstrap (frozen rule applied): no H1 or H2 verdict changes in any of 22 cells. Report; do not claim that the dual-method rule removes uncertainty.", "Resolved as a sensitivity analysis (verdicts unchanged)"),
    ("SI-06", "moderate", "inference", "H3 (aggregate endpoint) rests on 24 weekly blocks; the iid-week bootstrap ignores autocorrelation; TX_1 H28 is a boundary case (primary Holm 0.0514, secondary 0.0433).",
     "SUPPLEMENTARY_H3_RESOLUTION.md", "H3 counts", "design limitation", "Keep the frozen verdict (inconclusive); describe H3 as weakly supported.", "Resolved in the R2 supplementary calculation; carried into R3"),
    ("SI-07", "moderate", "metric choice",
     "Kolassa (2016) argues that MAD, MASE and wMAPE are inherently unsuitable for evaluating count-data forecasts; the primary endpoint (pooled WAPE = wMAPE) is of that type and rewards low forecasts on sparse series. The bias findings illustrate this.",
     "Kolassa 2016 abstract (IDEAS/RePEc); AGGREGATION_ANALYSIS.md", "interpretation of item-day gains", "scientific disagreement with a prespecified metric choice", "Cite and discuss (Related work, Limitations); no proper-score / probabilistic evaluation exists.", "Added to R3"),
    ("SI-08", "moderate", "sampling",
     "The v2 M5 eligibility rule (first sale <= d_1100) is window-independent: valid for W1-W3 (validation starts >= d_1185) but would use information from inside the validation/test span for an earlier window (W4 starts at d_933). It also excludes products launched after d_1100.",
     "ml/benchmark/datasets.py (load_m5_subset); data.py", "external validity; design of any new window", "design limitation", "State in Limitations; v3 uses a window-specific cut-off (day 848).", "Handled in v3 protocol"),
    ("SI-09", "moderate", "wording", "'Absolute-error LightGBM' and 'best simple baseline' overstate specificity (see SI-01, SI-03).", "MANUSCRIPT_R2.md abstract, sections 9 and 12", "claims", "reporting",
     "Reword to 'a median-type (absolute-error or 0.5-quantile) LightGBM' and 'the best of 31 prespecified simple baselines'.", "Done in R3"),
    ("SI-10", "minor", "exposure",
     "W2/W3 'never scored' is accurate for the evaluated series, but a price-identification regression (ml/benchmark p1) used targets over days 0-1912 in-sample and the periods served as training rows; 'untouched' would be too strong.",
     "WINDOW_USE_AUDIT.md", "'confirmatory' label", "documentation", "Keep 'not scored' / 'period-exposed' wording.", "Already disclosed; kept"),
    ("SI-11", "minor", "multiplicity", "Holm is applied within each hypothesis family across eight cells; the four families (H1, H1b, H2, H3) are not corrected against each other; only H1 is primary.",
     "analysis.py (analyse_window)", "p-value interpretation", "design limitation", "State in Methods that only H1 is primary and the other families are secondary.", "Added to R3"),
    ("SI-12", "minor", "reproducibility", "Only 1 of 22 cells had been reproduced in a clean environment (R2).", "FINAL_VERIFICATION_REPORT.md", "reproducibility claims", "coverage gap",
     "Reproduce all 22 cells in a fresh environment into scratch directories and compare (E1).", "See REPRODUCIBILITY_REPORT.md"),
    ("SI-13", "minor", "independence", "Study, verifier, supplementary analysis and manuscript were produced by the same AI assistant; the file name verify_independent.py may suggest independence.",
     "FINAL_VERIFICATION_REPORT.md", "verification claims", "process limitation", "Use 'second code path, same author' wording everywhere; recommend external replication.", "Wording enforced in R3"),
    ("SI-14", "info", "references", "One overstatement found and corrected earlier (M5 LightGBM prevalence). Kolassa 2016 and Kourentzes 2014 abstracts and Hyndman & Koehler full text now seen; Kolassa 2020 and the published M5 article not read.",
     "REFERENCE_CLAIM_CHECK.csv", "related-work statements", "documentation", "See REFERENCE_AND_RIGHTS_AUDIT.md", "Done"),
    ("SI-15", "info", "code audit",
     "No coding bug or leakage found in the audited paths: window arithmetic, eligibility masks (units sold on days without a price = 0, verified), baseline cut-offs, feature shifts (lag / rolling features shifted by H), training-row bounds, validation-only selection, selection-before-test ordering; headline point estimates recomputed from predictions.npz agree with analysis_*.json to 2e-16 in all 22 cells.",
     "quality_gate/results/audit_sensitivity.json (D_recomputation); source review", "all point estimates", "audit result", "none", "Closed"),
]

if __name__ == "__main__":
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(COLS)
        w.writerows(ROWS)
    print(len(ROWS), "issues ->", OUT)
