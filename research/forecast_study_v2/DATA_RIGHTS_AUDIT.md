# DATA_RIGHTS_AUDIT — forecast_study_v2

Read from the datasets' own pages on 2026-10-22; no legal advice. Decisions requiring the rights holders or the authors are listed in §3.

## 1. Terms

| dataset | terms (source) | consequence |
|---|---|---|
| **M5 Forecasting – Accuracy** (Kaggle) | Competition rules (read in full for the data clause): "DATA ACCESS AND USE: Competition Use, Academic, Non-Commercial Use"; "You may access and use the Competition Data for non-commercial purposes only, including ... for academic research and education"; "You agree not to transmit, duplicate, publish, redistribute or otherwise provide or make available the Competition Data to any party not participating in the Competition." The data page requires signing in and accepting the rules. The GitHub `Mcompetitions/M5-methods` page states no licence. | Academic non-commercial analysis: allowed. **Public release of the data, or of arrays that contain actual M5 sales (the stored `predictions.npz` hold the targets `y`), is not allowed without permission.** |
| **Online Retail II** (UCI) | CC BY 4.0; donor Daqing Chen; DOI 10.24432/C5CG6D; recommended citation Chen, D. (2012). | Redistribution of the data and derived arrays is permitted with attribution. |

## 2. What may be shared (proposal; not performed)

| artifact | M5-derived | Online Retail II-derived |
|---|---|---|
| code, configs, protocol, hashes, selection records | yes | yes |
| aggregate result tables, metric values, figures | yes (derived statistics; confirm with the rights holder if in doubt) | yes |
| per-row predictions with actuals (`predictions.npz`) | **no** (contains M5 sales) | yes, with attribution |
| forecasts alone (without actuals) | uncertain (reconstructable only with the licensed data) — ask | yes |
| raw or processed M5 files | **no** | yes (CC BY) |
| retrieval instructions and scripts | yes | yes |

## 2b. Re-verification (2026-10-22, second pass)

* **M5:** the live Kaggle rules page (rendered in the built-in browser) was read again. Section 7 "Competition Data", A "Data Access and Use": "You may access and use the Competition Data for non-commercial purposes only, including for participating in the Competition and on Kaggle.com forums, and for academic research and education." B "Data Security": "You agree not to transmit, duplicate, publish, redistribute or otherwise provide or make available the Competition Data to any party not participating in the Competition." The rules say nothing about derived forecasts or aggregate statistics. **Conclusion unchanged: the data and any file containing M5 sales are not to be redistributed; forecasts-only and aggregate statistics are treated as not cleared unless the rights holder agrees.** The manuscript's Sections 4 and 13 follow this wording.
* **Online Retail II:** the live UCI page (read 2026-10-22) states CC BY 4.0, DOI 10.24432/C5CG6D, creator Daqing Chen (donated 2019), 1,067,371 instances, suggested citation Chen (2012); no further restrictions.
* This is a reading of published terms, not legal advice.

## 3. Open decisions (require the authors / the rights holder)

1. Written clarification from the rights holder (University of Nicosia / Kaggle) whether forecasts or aggregate series derived from M5 may be shared in a repository; until then share only code, hashes and aggregate results for M5.
2. Venue data policies: IJF posts datasets of published papers on its site; PLOS ONE requires public deposit or a documented third-party restriction; TMLR does not require data. The data-availability statement must describe the M5 restriction and the access route (Kaggle account + rules).
3. Institutional ethics/data-protection statement: the study uses public, secondary, non-interventional data; Online Retail II contains pseudonymous customer IDs but no customer-level data are used in this study.
4. Repository licence for the code: the authors choose; third-party package licences (LightGBM, XGBoost, scikit-learn, pandas, numpy, scipy) are permissive but were not audited here.
