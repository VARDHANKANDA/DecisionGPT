# forecast_study_v2 — endpoint-matched evaluation of boosted models vs simple baselines (daily retail demand)

Status 2026-10-22: **analysis complete; manuscript R2 complete; final human-review package assembled (`FINAL_HUMAN_REVIEW_PACKAGE.md`).** Nothing has been committed, submitted, uploaded or published. The v1 study (`../forecast_study_v1/`), `experiments/` and the raw data are untouched (hash snapshots in `protection/`).

## Read first

| file | content |
|---|---|
| `FINAL_HUMAN_REVIEW_PACKAGE.md` | **start here**: what to review, commands, open questions |
| `MANUSCRIPT_R2.md` | current manuscript (tables generated from artifacts; figures embedded); `MANUSCRIPT_FINAL_DRAFT.md` is the superseded first draft |
| `SUPPLEMENTARY_H3_RESOLUTION.md`, `PROPOSAL_STATISTICAL_BASELINES.md` | boundary-cell precision check; unrun proposal for ETS/ARIMA/Theta on a fresh window |
| `FINAL_VERIFICATION_REPORT.md` | what was verified, how, by whom, and what was not |
| `CLAIM_EVIDENCE_MATRIX.csv` | each claim → evidence → status → caveat |
| `EXPERIMENT_PROTOCOL.md`, `FREEZE.json`, `DEVIATIONS.md` | the frozen plan and every change after it |
| `STATISTICAL_ANALYSIS.md`, `AGGREGATION_ANALYSIS.md`, `UNCERTAINTY_ANALYSIS.md` | results and inference |
| `METRIC_RESULTS.csv`, `MODEL_COMPARISON.csv`, `results/TABLES.md`, `results/SUMMARY_EXTRA.md`, `figures/` | tables and figures (generated) |
| `DATA_AUDIT.md`, `LEAKAGE_AUDIT.md`, `WINDOW_USE_AUDIT.md`, `DATA_RIGHTS_AUDIT.md` | data, leakage, window exposure, licences |
| `LITERATURE_REVIEW.md`, `RELATED_WORK_MATRIX.csv`, `REFERENCE_AUDIT.csv` | literature and reference verification |
| `VENUE_COMPARISON.md`, `SUBMISSION_CHECKLIST.md` | venue options; what remains for the author |
| `REPRODUCIBILITY.md` | how to rerun; what was and was not reproduced |

## One-paragraph result

On a confirmatory window that no experiment had scored, a validation-selected absolute-error LightGBM beat the best same-information simple baseline on pooled item-day WAPE in all 8 dataset–horizon cells (median +4.3 %, +2.5 … +6.0 %), positive in 22/22 cells across three windows (supported in 20), and beat the earlier Tweedie model in every cell; the advantage over baselines that see more recent data is not established at H = 28. On the aggregate endpoint the selected models are mean-type, the item-day winner (relative bias −0.29 … −0.39) loses to simple baselines, and the aggregate improvement is supported in 4/8 cells. The v1 negative result therefore changes sign when objective and endpoint are matched; the contribution is an empirical quantification of established theory, not a new method.

## Restrictions

* M5 data: Kaggle competition rules (non-commercial/academic, no redistribution). `results/**/predictions.npz` and `fits/*.npy` contain or reproduce actual sales — **do not publish them**.
* Online Retail II: CC BY 4.0 (cite Chen, 2012).
* AI-assisted: study code, verification code and manuscript were produced with an AI assistant; the verification is not external.
