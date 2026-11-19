# STATISTICAL_ANALYSIS — forecast_study_v2

All numbers are read from `results/analysis/analysis_{W2,W3,W1}.json`, `results/TABLES.md`, `results/SUMMARY_EXTRA.md` and `results/verification/independent_verification_*.json`. Inference methods and decision rules are those of `EXPERIMENT_PROTOCOL.md` and `UNCERTAINTY_ANALYSIS.md` (frozen 2026-10-22T08:15:19Z); nothing in this file changes them.

## 1. Confirmatory family (window W2, eight cells)

| Hypothesis | Comparison | Supported / contradicted / inconclusive (final, dual-method rule) |
|---|---|---|
| H1 (primary) | item-day-selected model vs best matched baseline, item-day WAPE | **8 / 0 / 0** |
| H1b | the same vs the best baseline of *any* information set (fresh baselines at H = 28 know up to 28 days more than the model) | 4 / 0 / 4 |
| H2 | the same model vs the original Tweedie (p = 1.1) model, refit on W2 | 8 / 0 / 0 |
| H3 | subset-day-selected model vs best matched baseline, subset-day WAPE | 4 / 0 / 4 |

H1 relative improvements (pooled over six test blocks; crossed-bootstrap 95 % CI; Holm p within the family): CA_1 H28 +4.6 % [+2.3, +7.1]; CA_1 H7 +4.0 % [+2.3, +6.0]; TX_1 H28 +2.5 % [+1.0, +4.1]; TX_1 H7 +4.5 % [+2.5, +6.8]; WI_1 H28 +3.3 % [+1.6, +5.3]; WI_1 H7 +6.0 % [+3.4, +9.0]; Online Retail II H28 +5.8 % [+2.7, +9.5]; H7 +4.0 % [+1.5, +7.0]. Median +4.3 %, range +2.5…+6.0 %. Holm p between 0.0016 and 0.0036 (the smallest attainable raw p with B = 10,000 is 0.0002 and its Holm value over eight cells is 0.0016, so these p-values are bounded below by the resolution of the bootstrap and are not exact). The model won all six blocks in seven cells and five of six in Online Retail II H7. **In ordinary language: the item-day-selected median-type LightGBM beats the best simple baseline on the item-day endpoint in every confirmatory cell, by a few percent of the baseline's error; the 2 % threshold is met in all cells but TX_1 H28 (+2.5 %) is close to it.**

H1b is inconclusive at H = 28 in all four datasets, because the best "fresh" baseline (re-estimated at the start of each block, 1–28 days more recent than the model's information) is as good as the model (improvements −1.4 % … +2.2 %). H1b is supported at H = 7 in all four datasets. This is a real limitation: the claim "beats the best simple baseline" holds for equal information; at H = 28 it does not extend to baselines that see more recent data.

H2: the item-day-selected model beats the original Tweedie model in all eight cells (+7.9 … +16.8 %, median +9.4 %). The original v1 conclusion — "the learned model does not beat a trailing median" — therefore changes in direction when median-type objectives are included; it was an objective-selection effect and the v1 reference configuration itself is still worse than the best baseline in item-day WAPE (e.g. CA_1 H28: reference 0.806 vs best matched baseline 0.775 vs selected model 0.739).

H3: the subset-day-selected model (a mean-type model: Tweedie 1.1 in six cells, squared error in the two WI_1 cells) has a positive point estimate on subset-day WAPE in 7 of 8 cells (+5.8 … +23.8 %; median +13.1 %; Online Retail II H7 −0.5 %), but the final verdict is supported in 4/8 cells and inconclusive in 4/8 (TX_1 H28, WI_1 H28, Online Retail II H28 and H7). No cell is contradicted by the interval criterion.

## 2. Replication windows (descriptive; own Holm adjustment; not pooled with W2)

| Window | cells | H1 s/c/i | H1b | H2 | H3 | median H1 | H1 range |
|---|---|---|---|---|---|---|---|
| W3 (M5 only, never-scored period, independent of W2) | 6 | 6/0/0 | 3/0/3 | 6/0/0 | 4/0/2 | +4.5 % | +2.2 … +6.2 % |
| W1 (all four; M5 WI_1 fresh store; CA_1, TX_1, Online Retail II re-evaluated) | 8 | 6/0/2 | 3/0/5 | 8/0/0 | 4/0/4 | +3.2 % | +1.1 … +4.5 % |

The sign of the H1 improvement is positive in 8/8 (W2), 6/6 (W3) and 8/8 (W1) cells. In W1 the two inconclusive H1 cells are TX_1 H28 (+1.1 %, 3/6 blocks won, CI crosses 0) and TX_1 H7 (+1.9 %, below the 2 % threshold although the interval excludes zero). The item-day-selected model in W1 is the 0.5-quantile model in two cells rather than the absolute-error model; this reflects the validation-only selection, not a post-hoc choice. W1 for CA_1, TX_1 and Online Retail II is **not independent** (those periods were scored in v1 and the audit) and is reported as a re-evaluation only; only WI_1 on W1 is a fresh replication.

## 3. Effect size, uncertainty and the effective sample

Effects are reported as relative improvement in WAPE with 95 % intervals, not as p-values alone. The two-way design effect on the standard error is 1.5–2.5 (largest for Online Retail II with 100 series), i.e. a naive i.i.d. treatment of the 8,400 series-week cells (350 series × 24 weeks) would understate the standard error by that factor; the approximate number of effective independent cells is 2,300–4,000 for M5 and 400–610 for Online Retail II (`results/SUMMARY_EXTRA.md`). Both inference methods are mildly liberal in the pre-freeze simulation (worst-case coverage 0.90, Type-I error up to ~0.10 at nominal 0.05), which is why the 2 % minimum-improvement and blocks-won criteria and the dual-method rule were added; p-values just below 0.05 should be read with that in mind.

## 4. Agreement of the two inference methods

The primary and secondary methods gave the same verdict for every H1, H1b and H2 cell in all three windows. Disagreements, resolved to INCONCLUSIVE by the frozen rule, occurred only for H3: W2 TX_1 H28 (primary Holm p 0.071, secondary 0.048), W3 CA_1 H7 and W3 WI_1 H7. See `MODEL_COMPARISON.csv` (`methods_agree`).

## 5. Seed sensitivity (W2, item-day-selected model, seeds 42 / 43 / 44)

Refits with three seeds change the H1 improvement by at most **0.40 percentage points** (range per cell 0.09–0.40 pp), far smaller than the effects and than the 2 % threshold; the minimum over seeds is ≥ 2 % in every cell (TX_1 H28: 2.30–2.53 %). Seed sensitivity is not part of the confidence intervals (the intervals do not include training randomness).

## 6. Independent recomputation and the one boundary disagreement (resolved by a supplementary calculation)

`verify_independent.py` (separate code, imports nothing from the study) recomputed every target, baseline forecast, metric, improvement, interval and Holm-adjusted verdict: **W2 98/98, W3 72/72, W1 98/98 cell-level checks passed**; point estimates of the improvement agree exactly in all 88 comparisons (maximum absolute difference 0.0). One of the 88 compared verdicts, W2 TX_1 H28 H3, differs: the study's final verdict is INCONCLUSIVE, the independent code's primary-method verdict is SUPPORTED.

**Supplementary precision check** (`supplementary_h3.py`, `SUPPLEMENTARY_H3_RESOLUTION.md`, `results/supplementary/h3_convergence.json`; post-hoc, does not replace any stored result, applies the unchanged frozen rule). The two prespecified H3 methods were recomputed with B = 1,000,000 per seed and three new seeds, and the exact sign-flip randomisation test (all 2^24 sign patterns) and dependence diagnostics were added.

| quantity (W2, TX_1, H = 28, H3) | frozen run (B = 10,000) | independent code (B = 4,000) | converged (3 × 10^6 draws) |
|---|---|---|---|
| primary (iid-week) raw p | 0.0178 | 0.0115 | **0.0129** (seed SD 0.0002) |
| primary Holm p (8 cells) | 0.0712 | 0.0460 | **0.0514** |
| secondary (stationary) raw p | 0.0120 | – | 0.0108 (seed SD < 0.0001) |
| secondary Holm p | 0.0480 | – | **0.0433** |
| verdict, frozen dual-method rule | INCONCLUSIVE | SUPPORTED (primary only) | **INCONCLUSIVE** (primary Holm > 0.05, secondary < 0.05: methods disagree) |

* **Monte-Carlo uncertainty.** The frozen-seed raw p (0.0178) was a high draw (standard error at B = 10,000 ≈ 0.0017; converged value 0.0129); the independent code's Holm p (0.046) was a low draw at B = 4,000. Neither is a bias in the implementation: thirty alternative seeds of the study's own function at B = 10,000 average 0.0129 (SD 0.0017).
* **Converged decision.** With Monte-Carlo error removed (seed SD 0.0002) the primary method's Holm p is 0.0514, just above the 0.05 threshold, and the secondary method's is 0.0433, just below; the methods still disagree and the frozen rule gives INCONCLUSIVE. The frozen verdict is **confirmed**, not overturned. All 22 H3 verdicts of the three windows are unchanged under the converged calculation (4/8, 4/6, 4/8 supported); the independent code's "supported" for this cell and the corresponding alternative count (5/8) were Monte-Carlo noise at B = 4,000 and are withdrawn.
* **Dependence and effective sample.** The 24 weekly differences (|total error| of baseline minus model) have a positive lag-1 autocorrelation of +0.36 in this cell (AR(1) effective sample ≈ 11.3 of 24 weeks; other W2 cells: −0.35 … +0.06, effective 21–50 weeks, or2 H7 +0.32 / 12.3). The iid-week bootstrap ignores that dependence and is therefore liberal in this cell; the stationary bootstrap (secondary) allows for it. In this cell the model was better in 15 of 24 weeks; the exact sign-flip test (a different statistic, the mean weekly difference) gives p = 0.034 unadjusted. The cell is a boundary case and should be described as "suggestive, not established".
* **Decision rule.** Not changed: SUPPORTED needs Holm p < 0.05 for the primary method *and* the same verdict from the secondary method with its own Holm adjustment.

## 7. What the statistics do not show

* They apply to the 350/349/100 series sampled per dataset and to the periods tested; generalisation to other stores, categories, years or retailers is not tested (four datasets, one retail sector, M5 is one US retailer).
* WAPE (a ratio of sums) is dominated by high-volume series; segment-level results (`exploratory`) show that the gain is concentrated in frequent / high-volume series (CA_1 H28: frequent +8.1 % [3.5, 12.7], intermittent +2.5 % [0.5, 4.7], low-volume −1.5…+4.0 %, mid-volume +1.0 % with intervals including zero). These are exploratory descriptions.
* An improvement in item-day WAPE by a model that is strongly biased downward (relative bias −0.29 … −0.39, 29–49 % zero forecasts on M5) is an improvement in *that metric*, not evidence of better demand estimation; see `AGGREGATION_ANALYSIS.md`.
