# Evidence-to-claim matrix (forecast_study_v1)

Every sentence of the manuscript that states a result maps to a row here. "Artifact" files are under `research/forecast_study_v1/`. Strength: **A** = pre-registered confirmatory result, independently verified; **B** = pre-registered descriptive; **C** = exploratory / post-hoc (hypothesis-generating); **D** = a limitation or non-claim.

| # | Claim in the manuscript | Strength | Artifact(s) | Verified by | Caveat that must stay with the claim |
|---|---|---|---|---|---|
| 1 | The learned model did not beat the best matched-information baseline in pooled WAPE in any of 6 cells (3 contradicted, 3 inconclusive) | A | `results/CONFIRMATORY_SUMMARY.md`, `results/fs1_*/analysis.json` | `verify_cell` 24/24 per cell | Holds for these 3 datasets, a 350-series subset each, one seed, small grid; the primary model is a Tweedie-objective LightGBM |
| 2 | The same holds against the best baseline of any information set (4 contradicted, 2 inconclusive) | A | same | same | On Online Retail II H=28 H1 = H2 (same reference) |
| 3 | The sign never changes when one origin block is dropped | B | `analysis.json: leave_one_origin_out_…`, TABLES T6 | recomputed in `verify_cell` for the headline | Six blocks only |
| 4 | Item-day pooled WAPE and store-day aggregate WAPE give opposite winners in all 6 cells | B | TABLES T1/T3, `analysis.json: table` | `verify_cell` recomputes both for model and references | The best-by-aggregate method is a boosted model, not necessarily the primary model |
| 5 | The trailing-median baseline under-forecasts (bias −0.28 to −0.58) | B | TABLES T1 | `verify_cell` (bias) | Bias is for the matched reference |
| 6 | Crossed bootstrap intervals are 21–47 % wider than series-only | B | TABLES T2 | bootstrap code unit-tested (`tests/unit/test_forecast_study.py`) | Two-way independent resampling is an approximation |
| 7 | Calendar and history-statistics features help; price and identifiers not distinguishable from zero (M5 CA_1, H=28) | C | `results/ABLATIONS_fs1_m5_ca1_H28.json`, TABLES H5 | `verify_cell` 19/19 on each ablation run; features removed checked from `config.json` | Single store and horizon; no re-tuning; not a statement on price effects |
| 8 | Model advantage on frequent/smooth/high-volume series (M5 CA_1) | C | TABLES T4 | segment definitions use pre-validation history only (unit test) | Not replicated on M5 TX_1 or Online Retail II |
| 9 | Conformal 80 % intervals cover 79.3–81.0 % overall | B | TABLES T5 | coverage recomputable from stored predictions | Marginal only; frequent series under-covered (0.66–0.78) |
| 10 | An L1-objective refit matches or beats the median baseline in pooled WAPE but loses the aggregate advantage | C (post-hoc) | `results/E1_l1_*.json` | rows aligned to main run by (series, day) | Designed after seeing results; H=28 only; no validation selection |
| 11 | Classifier beats recency baseline in ROC-AUC/PR-AUC at both origins | A | `results/s2_online_retail_inactivity/results.json`, TABLES S2c | metrics from stored predictions | Proxy label; PR-AUC gain at origin A small (+0.010) |
| 12 | Origin-A classification advantage is fragile to customer sub-sampling | C | `results/S2_customer_disjoint.json` | — | Half the data; replacement design logged as a deviation |
| 13 | Validation-fitted Platt calibration worsened calibration under prevalence shift (origin B) | B | TABLES S2a | metrics recomputable | Single shift episode; not generalised |
| 14 | One-threshold accuracy exceeds majority-class accuracy but is prevalence-dominated | B | TABLES S2b | — | Not used for conclusions |
| 15 | Selection was fixed before test fits | A | `selection.json` mtimes vs `fits/test_*.npy`, `FREEZE.json` | `verify_cell` check | File timestamps are evidence, not cryptographic proof |
| 16 | Historical benchmark metrics reproduce | A | `audit/rerun_comparison.json`, `audit/recompute_report.json` | independent code | c1 differs in 2 numbers ≤ 1.5e-5 |
| 17 | **Not claimed:** generalisation to Indian SMEs, causal effects of price, churn prediction, superiority of any model, inference about deep/foundation models | D | — | — | Explicitly excluded in §1 and §19 |

## Claims the evidence does NOT license (do not write these)

* "Gradient boosting is worse than simple baselines" — only: on item-day pooled WAPE against a median baseline, in these data.
* "The model is more accurate" — error metrics are not accuracy; say which error and at which level.
* "Price features are useless" — only: removing them did not measurably change WAPE in one store.
* "Customers churn after 90 days of inactivity" — the label is an operational proxy.
* "Validated for SMEs / deployment-ready" — no real SME data were used.
