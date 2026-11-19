# FINAL_VERIFICATION_REPORT — forecast_study_v2

Date 2026-10-22. **Verifier = the same AI assistant (Claude, via Claude Code) that wrote the study code, analysis and manuscript.** Everything below is therefore internal verification. It is not independent external validation and must not be described as such.

## 1. What was verified, and how

| layer | what | result |
|---|---|---|
| Unit tests (`tests/unit/test_forecast_study_v2.py`) | window ordering, leak-freedom of 16 baseline estimators under both information sets (future perturbation), metric identities, objective semantics (L1/quantile → median, L2 → mean), clipping, inference helpers, Online Retail II SKU list recomputed from raw, truncation | 17 passed (project venv) and 17 passed (fresh venv) |
| Frozen files | `freeze verify` | 24 files unchanged (checked 2026-10-22, after all analysis) |
| Targets | rebuilt from raw files (`tools/independent_targets_check.py`) | match stored targets |
| Independent recomputation (`verify_independent.py`; imports nothing from the study) | targets from raw, all 31 baselines row by row, WAPE/subset-day/bias metrics, improvements, own pigeonhole bootstrap (B = 4,000) and two-way cluster-robust interval, Holm, verdicts, validation-only selection re-derivation, selection-before-test file ordering, hashes | W2 98/98, W3 72/72, W1 98/98 checks passed; 0 frozen files changed; point estimates identical in 88/88 comparisons; 87/88 verdicts agree |
| The one disagreement | W2, M5 TX_1, H = 28, H3 (study INCONCLUSIVE, independent primary SUPPORTED) | resolved by the supplementary calculation (`SUPPLEMENTARY_H3_RESOLUTION.md`): with 3 × 10^6 bootstrap draws the primary Holm p is 0.0514 and the secondary 0.0433, so the frozen dual-method rule still gives INCONCLUSIVE; the independent code's SUPPORTED was Monte-Carlo noise at B = 4,000; all 22 H3 verdicts are unchanged |
| Inference methods | pre-freeze simulation on synthetic dependence structures (`simulation.py`) | worst-case coverage error 0.050 (crossed bootstrap), 0.057 (iid-week) — the simulation code was not independently re-run |
| Perturbation / leakage | feature histories unchanged when the future is overwritten (recorded in every `selection.json`); baseline future-perturbation unit tests | all passed |
| Protected artifacts | SHA-256 inventory at start and end (`protection/protected_start.json`, `protected_final.json`): v1 study, `experiments/`, historical benchmark code, raw M5 / UCI files | 761 files, **0 differences** |
| Clean-environment reproduction (partial) | fresh Python 3.12.0 venv, pinned `requirements.txt` (identical resolved versions); one full cell re-run (Online Retail II, W2, H = 7: validation, test, extra seeds) into a scratch directory | selection and all 35 method summaries identical (max abs. difference 0); the other 21 cells were not re-run |
| Backend suite | `pytest tests -x` (project venv) | exit code 0, no failures (§5) |
| Tables and figures | generated from stored files by `report.py` / `report_extra.py`; manuscript numbers were compared by hand to those files and several corrected during drafting (Table 3 was regenerated from the JSON after a discrepancy was found) | no known remaining mismatch; **human spot-check still needed** |

## 2. Things found and fixed during verification

* A working note gave 136 compared verdicts; the verification files contain 88 (corrected in all documents).
* Several descriptive statements in `STATISTICAL_ANALYSIS.md` and Table 3 were checked against `analysis_*.json` and corrected (H2 range, model counts, method-disagreement cells, Holm range).
* A draft sentence said primary/secondary disagreements also occurred in H1b; the stored analyses show they occur only in H3 (W2 TX_1 H28; W3 CA_1 H7 and WI_1 H7), and the sentence was corrected.

## 3. What was not verified

* Independence: no second human or system reviewed the design, code or text.
* The pre-freeze simulation and `report.py` figures were not independently re-implemented; figures were not visually reviewed by a human.
* 21 of 22 cells were not re-run in a clean environment; no other OS or CPU count was tried; the raw data were not re-downloaded.
* References: Crossref metadata for 29 DOI entries was machine-compared; titles and claims were not re-read against the full text of every source (abstract-level for most); Koenker & Bassett page range and the Ke et al. author list need a human check.
* Data-licence interpretation (Kaggle M5 rules) is the assistant's reading, not legal advice.

## 4. Human review still required

1. Read `MANUSCRIPT_FINAL_DRAFT.md` and `CLAIM_EVIDENCE_MATRIX.csv`; decide whether the framing (incremental empirical contribution) is acceptable.
2. TX_1 H28 H3 is a documented boundary case (confirmed INCONCLUSIVE by the converged calculation); no rule or stored result was changed.
3. Check references against originals; confirm licence terms; complete authorship, funding, competing-interest, ethics and generative-AI declarations.
4. Apply a venue template, embed the figures, and decide on additional baselines (ETS/ARIMA/Theta) or models that reviewers are likely to request.
5. Optional: an external replication of the pipeline by someone who did not write it.

## 5. Backend suite

The full repository suite was run twice in the project venv. First run (`pytest tests -x`): exit code 0, pass count not captured. Second run (after manuscript R2, full output captured): **1777 passed, 34 skipped, 0 failed**. This study did not modify the backend; only `tests/unit/test_forecast_study_v2.py` was added under `tests/`.

## 6. Final quality gate (second pass, 2026-10-22, after manuscript R2)

| item | result |
|---|---|
| Supplementary H3 precision check | `supplementary_h3.py`: 3 × 10^6 draws per method per cell, all 22 H3 cells; frozen verdicts unchanged; TX_1 H28 primary Holm 0.0514 / secondary 0.0433 → INCONCLUSIVE confirmed (`SUPPLEMENTARY_H3_RESOLUTION.md`) |
| Manuscript R2 numeric check | `tools/check_numbers.py`: 49/49 (headline numbers recomputed from artifacts; tables embedded verbatim; stale phrases absent) |
| Reference re-check against sources | Found and corrected one overstatement: the M5 report (pre-publication copy) says most examined methods and almost all top-50 methods with a description used LightGBM, not "all of the top 50". Koenker & Bassett pages 33–50 confirmed; Ke et al. authors confirmed (NeurIPS page); Damato et al. authors confirmed (arXiv API). Claim-level status in `REFERENCE_CLAIM_CHECK.csv`; Kolassa 2016/2020 and Kourentzes 2014 abstracts could not be retrieved (topic citations only); the published M5 article was not accessible (403) |
| Data terms | Kaggle M5 rules text re-read from the live page; UCI Online Retail II page re-read (`DATA_RIGHTS_AUDIT.md` §2b) |
| Venue instructions | TMLR (author guide, editorial policies, acceptance criteria) and PLOS ONE (data availability, AI policy) read; IJF guide and PLOS fee page unreachable (403) — marked not verified in `VENUE_COMPARISON.md` |
| Protected files | second snapshot `protection/protected_final_r2.json`: 761 files, 0 differences from `protected_start.json`; `experiments/experiment_manifest.json` sha256 `94aa419c703b1bab…` unchanged |
| Freeze | `freeze verify`: 24 files unchanged (after all post-freeze additions, which are all outside the hash list and are logged in `DEVIATIONS.md`) |
| Figures | regenerated as SVG/PNG/PDF by `report.py` (re-running the analysis reproduced identical stored values: TX_1 H28 H3 p 0.0177982, Holm 0.0712 / 0.0480); Figures 1–3 inspected as PNG images (legible, axes and legends correct) |
| Review PDF | built with pandoc + xelatex; not a venue layout; some wide tables overflow; not inspected page by page |
| Full repository suite | 1777 passed, 34 skipped, 0 failed (33 min 1 s; exit code 0) |
| What did NOT happen | no external validation; no full clean-room reproduction (1 of 22 cells); statistical baselines not run; no submission, upload or contact |
