# FINAL_HUMAN_REVIEW_PACKAGE — forecast_study_v2

Prepared 2026-10-22. Nothing has been committed, submitted, uploaded or published; no restricted data or sales-bearing predictions are included or should be shared. The study, its verification, the supplementary analysis and the manuscript were produced by one AI assistant (Claude, via Claude Code) under the project owner's direction; **no external or independent validation has taken place.** This package is meant to let an independent forecasting researcher find errors, not to certify the work.

## 1. What to read, in this order

| # | file | what it is |
|---|---|---|
| 1 | `MANUSCRIPT_R2.md` (+ `build/MANUSCRIPT_R2_review_copy.pdf`, not a venue layout) | current manuscript: abstract, methods, results (confirmatory / replication / descriptive / exploratory / supplementary labelled), discussion, limitations, verification, conclusions, placeholders for declarations |
| 2 | `EXPERIMENT_PROTOCOL.md`, `FREEZE.json`, `DEVIATIONS.md` | the frozen protocol (hash-frozen 2026-10-22T08:15:19Z, before any W2/W3/WI_1 outcome; internal, not public) and every change after it |
| 3 | `tables/*.md|csv`, `METRIC_RESULTS.csv`, `MODEL_COMPARISON.csv`, `results/TABLES.md` | all result tables, generated from stored artifacts |
| 4 | `figures/fig1_forest`, `fig2_aggregation_ladder_W2`, `fig3_endpoint_dependence` (`.svg/.png/.pdf`) | figures |
| 5 | `STATISTICAL_ANALYSIS.md`, `AGGREGATION_ANALYSIS.md`, `UNCERTAINTY_ANALYSIS.md`, `SUPPLEMENTARY_H3_RESOLUTION.md` | statistics, aggregation, inference design, boundary-cell precision check |
| 6 | `CLAIM_EVIDENCE_MATRIX.csv`, `REFERENCE_CLAIM_CHECK.csv`, `REFERENCE_AUDIT.csv`, `RELATED_WORK_MATRIX.csv`, `LITERATURE_REVIEW.md` | claims → evidence; references → what was actually checked |
| 7 | `WINDOW_USE_AUDIT.md`, `LEAKAGE_AUDIT.md`, `DATA_AUDIT.md`, `DATA_RIGHTS_AUDIT.md` | data, window exposure, leakage, licences |
| 8 | `FINAL_VERIFICATION_REPORT.md`, `REPRODUCIBILITY.md` | what was verified and how |
| 9 | `PROPOSAL_STATISTICAL_BASELINES.md`, `VENUE_COMPARISON.md`, `SUBMISSION_CHECKLIST.md`, `submission_prep/` | unrun proposal; venue facts; remaining steps |

## 2. Headline results (all from the stored tables)

* **Confirmatory (W2, 8 cells, item-day):** the validation-selected absolute-error LightGBM beats the best same-information baseline in 8/8 cells, median +4.3 % (+2.5 … +6.0 %), Holm p ≤ 0.004, ≥ 5/6 blocks won; beats the original Tweedie 1.1 model in 8/8 cells (+7.9 … +16.8 %); against baselines with fresher information (H1b) supported only at H = 7 (4/8 overall).
* **Replication:** H1 improvement positive in 22/22 cells over W2, W3, W1 (supported 20); W3 6/6; W1 6/8 (TX_1 H28 and H7 inconclusive); only WI_1 on W1 is a fresh replication.
* **Aggregate endpoint (H3):** a different, mean-type model is selected; improvement over the best baseline positive in 7/8 W2 cells, supported in 4/8; the item-day winner (relative bias −0.29 … −0.39 on M5) loses to simple baselines on subset-day WAPE (CA_1 H28: 0.346 vs 0.114).
* **Boundary cell:** W2 TX_1 H28 H3 stays *inconclusive* after a converged supplementary calculation (primary Holm 0.0514, secondary 0.0433); all 22 H3 verdicts unchanged.
* **Not evaluated:** ETS, ARIMA, Theta, neural and probabilistic models, decision costs, other retailers.

## 3. Reproduction commands (repository root; `PYTHONPATH=.`; M5 raw data must be obtained from Kaggle under its rules)

```bash
python -m pytest tests/unit/test_forecast_study_v2.py -q
python -m research.forecast_study_v2.freeze verify
python -m research.forecast_study_v2.tools.data_audit
python -m research.forecast_study_v2.tools.independent_targets_check
PY=python bash research/forecast_study_v2/run_v2.sh validation      # ~1 h; refuses to move on if the freeze does not verify
PY=python bash research/forecast_study_v2/run_v2.sh test            # ~1.5 h
python -m research.forecast_study_v2.report
python -m research.forecast_study_v2.report_extra
python research/forecast_study_v2/verify_independent.py W2 W3 W1
python -m research.forecast_study_v2.supplementary_h3               # ~6 min
python research/forecast_study_v2/tools/build_tables.py
python research/forecast_study_v2/tools/assemble_manuscript_r2.py
python research/forecast_study_v2/tools/check_numbers.py
```

Do not re-run the validation/test stages into the existing `results/` without moving it aside first (the pipeline refuses on a changed configuration hash). A fresh-environment replication of one cell is described in `REPRODUCIBILITY.md` §6.

## 4. Verification status (actual, as of this package)

| check | result |
|---|---|
| Study unit tests (17) | pass, project venv; pass, fresh venv with identical pinned versions (`--noconftest`) |
| Full repository suite `pytest tests` (project venv) | `pytest tests` (project venv, run 2026-10-22 after all study work): **1777 passed, 34 skipped, 0 failed**, 1866 warnings, 33 min 1 s, exit code 0 (full output captured in the session scratchpad) |
| `freeze verify` | 24 frozen files unchanged |
| Protected files (v1 study, `experiments/`, historical benchmark code, raw M5/UCI files) | 761 files hashed at start and again at the end: **0 differences**; `experiments/experiment_manifest.json` sha256 `94aa419c703b1bab…` unchanged |
| Second code path (`verify_independent.py`) | W2 98/98, W3 72/72, W1 98/98; point estimates identical in 88/88; 87/88 verdicts agree; the one difference resolved by the supplementary calculation (frozen verdict confirmed) |
| Manuscript numeric check (`tools/check_numbers.py`) | 49/49; all tables embedded verbatim from generated files |
| Clean-environment reproduction | **partial:** one cell (Online Retail II, W2, H = 7) re-run in a fresh venv, 35/35 method summaries identical; 21 cells not re-run; no other OS/CPU tested |
| External / independent validation | **none** |

## 5. Unresolved scientific questions

1. **Missing competitors.** Is "best of 31 simple baselines" an acceptable standard without ETS/ARIMA/Theta? (`PROPOSAL_STATISTICAL_BASELINES.md`; a fresh window exists for M5: seven unused stores × W4.)
2. **What does an item-day WAPE gain mean** for a model with relative bias −0.29 … −0.39 and 29–49 % zero forecasts? No decision-loss, service-level or pinball evaluation exists.
3. **H1b at H = 28.** Fresher baselines match the model; is the matched-information framing the right one for the claim?
4. **Dependence.** The iid-week bootstrap ignores weekly autocorrelation (lag-1 +0.36 in the boundary cell); is the dual-method rule an adequate remedy? The pigeonhole bootstrap's coverage was checked only on synthetic designs.
5. **Exposure.** W2/W3 targets were never scored for the evaluated entities, but the design followed the v1 results; is "confirmatory" fair, or should W2 be called a strong replication?
6. **Selection effects.** One validation-selected model per endpoint from eight candidates; are three validation blocks enough to avoid noise-driven choices (e.g. the W1 quantile-vs-L1 switches)?
7. **Generalisation.** Three M5 stores of one retailer and one UK wholesaler; Online Retail II has a short W2 history and no W3.
8. **Mechanism.** The explanation (median-type objective → low forecasts → good item-day WAPE, poor aggregate WAPE) is descriptive; no counterfactual (e.g. bias-corrected median model) was run.

## 6. Specific questions for an independent forecasting researcher

* Is the endpoint definition (pooled item-day WAPE over rows with a listed price; subset-day WAPE on summed demand of a 350-series subset) defensible, and is the "subset" aggregate a meaningful aggregate?
* Does the direct, global, minimum-lag-H set-up with block-wise refit and 730-day training window constitute a fair model implementation relative to M5 practice (recursive/non-recursive, hierarchy-aware, store/department models)?
* Are the 31 baselines and their two information sets fairly constructed (especially "matched" vs "fresh" at H = 28) and the validation-based baseline selection leakage-free?
* Is the 2 % minimum improvement, the ≥ 4/6-block rule and the dual-method rule a reasonable decision framework, and are the Holm families (eight cells, per hypothesis) appropriate?
* Does the crossed (series × 7-day block) bootstrap capture the dependence in the data, and is treating cell totals as exchangeable acceptable?
* Do the statements in the Introduction and Related Work match the cited sources (see `REFERENCE_CLAIM_CHECK.csv`; Kolassa 2016/2020 and Kourentzes 2014 were not read beyond metadata)?
* Is the contribution (quantified endpoint dependence under a frozen protocol; reversal of the v1 negative result) sufficient for the intended venue, given that the theory is established?
* Can the pipeline be re-run from the raw data by someone other than its author, and do the 21 un-re-run cells reproduce?

## 7. Items only the authors can complete

Author names, affiliations and contributions; funding; competing interests; ethics confirmation; the venue's AI-use and data-availability statements; licence confirmation with the M5 rights holder if forecasts are to be shared; the venue template and anonymisation; the decision on running the statistical-baseline proposal; any submission or payment.

## 8. Final verdict

**READY FOR INDEPENDENT HUMAN REVIEW — not ready for submission.** The central claims are scoped to what the stored evidence supports, every number in the manuscript is traceable to a generated artifact (49/49 checks), unfavourable and inconclusive results are retained, and the one verification disagreement was resolved without changing any rule or stored result. It is *not* an acceptance-grade or externally validated result: statistical (ETS/ARIMA/Theta), neural and probabilistic competitors are absent, verification was same-agent, only 1 of 22 cells was reproduced in a fresh environment, several references were checked only at abstract or metadata level, and author declarations, the venue template and the licence confirmation remain for the authors.
