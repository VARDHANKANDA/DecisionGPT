# DEVIATIONS — forecast_study_v2

Append-only. Each entry has a UTC date/time, what changed, why, and whether any confirmatory outcome had been read. The plan and code are frozen by `FREEZE.json`; changes after the freeze appear here.

## Pre-freeze activity log (not deviations; recorded for transparency)

| UTC | activity | outcome data read? |
|---|---|---|
| 2026-10-22 07:49 | Protection snapshot of v1, experiments, raw data, historical benchmark code (`protection/protected_start.json`) | no |
| 2026-10-22 | Window-use audit: grep of the repository, reading of earlier experiments' windows and split rules; discovered prior exposure (`WINDOW_USE_AUDIT.md`) | no (reading configurations and earlier stored results only) |
| 2026-10-22 | Unit tests written and run (17 pass), including real-data truncation tests | targets only |
| 2026-10-22 | Dry run of the validation stage on Online Retail II **W1** validation blocks (already-scored period): confirmed mechanics, SKU list equals v1's, zero baseline WAPE = 1 | W1 validation (already seen); no W2/W3/WI_1 data read |
| 2026-10-22 | Data audit and independent target rebuild for all dataset-windows | targets only |
| 2026-10-22 | Inference simulation on synthetic data fixed PRIMARY_ITEM_DAY = crossed bootstrap and PRIMARY_SUBSET_DAY = iid week bootstrap by the stated rule; dual-method rule added after the simulation showed both methods mildly liberal | no real outcomes |
| 2026-10-22 | Literature review and reference audit | no |
| 2026-10-22 | Dry run of the **test stage and the analysis code** on Online Retail II **W1** (already-scored period, never confirmatory) with the freeze check bypassed in that single dry-run process only; found one metadata bug (reading a not-yet-existing `FREEZE.json`), fixed; all outputs of the dry run were deleted before the freeze | W1 test (already seen); no W2/W3/WI_1 data read |

## Post-freeze entries

*(none at freeze)*

| UTC | change | reason | outcome data read? |
|---|---|---|---|
| 2026-10-22 08:2x | Added `verify_independent.py` (independent verification layer; imports nothing from the study) after the freeze | verification code must not influence results; it does not generate or alter any result. It is not in `FREEZE.json`'s hash list (the file did not exist at the freeze) | no (written while the validation stage ran; no result had been produced yet) |
| 2026-10-22 | Added `report.py` (tables, figures, CSV export), `requirements.txt` and `environment_freeze.txt` after the freeze (they did not exist at the freeze; not in the hash list) | reporting and environment recording only; `report.py` reads stored analysis files and calls the frozen `analysis.analyse_window`; it changes no result | after validation and test stages had run, yes (reporting) |
| 2026-10-22 | Added `report_extra.py` (verdict counts per window, design effects, replication summary) | descriptive summaries for the manuscript; reads stored files only | yes (reporting) |
| 2026-10-22 | **Verification observation, no change made.** `verify_independent.py` completed (W2 98/98, W3 72/72, W1 98/98 cell-level checks passed; 0 frozen files changed). One compared verdict differs: W2, M5 TX_1 H=28, H3 — study final INCONCLUSIVE (primary Holm p 0.071, secondary Holm p 0.048, dual-method rule), independent primary SUPPORTED. Cause: fixed-seed Monte-Carlo noise of the iid-week bootstrap (frozen seed gives p = 0.0178; 30 other seeds give mean 0.0129, SD 0.0017; B = 400,000 gives 0.0125; independent code B = 4,000 gives 0.0115). | the frozen seed, B and rule are kept; the cell is reported as boundary-sensitive. (Superseded by the supplementary entry below: the converged calculation confirms INCONCLUSIVE and the 5/8 alternative is withdrawn.) A post-hoc seed or B change would be a forking-path decision | yes |
| 2026-10-22 | Note on the verifier's comparison: `verify_independent.py` compares the study's final (dual-method) verdict with the independent *primary-method* verdict, so a primary/secondary disagreement can show up as a "disagreement"; all other compared verdicts (87 of 88, including all H1, H1b and H2) agree; point estimates of the improvements agree exactly | clarification | yes |
| 2026-10-22 | **Supplementary calculation (post-hoc, separate from the confirmatory results).** `supplementary_h3.py` recomputed the two prespecified H3 methods with B = 1,000,000 × 3 new seeds for all 22 H3 cells, added an exact sign-flip test and weekly-dependence diagnostics, and applied the unchanged frozen rule. Result: W2 TX_1 H28 H3 stays INCONCLUSIVE (primary Holm 0.0514, secondary 0.0433, methods disagree); all 22 H3 verdicts unchanged. Outputs: `SUPPLEMENTARY_H3_RESOLUTION.md`, `results/supplementary/h3_convergence.json` | resolve the verification disagreement with a precise calculation without changing any rule or stored result | yes |
