# STATISTICAL_AUDIT

Independent review of the study's inference, 2026-10-22. All numbers below were computed by audit code that does not import the study's code (`audit_v1/ind_core.py`, `step3_inference.py`). Author-reported values come from `results/*/analysis.json` and `CONFIRMATORY_SUMMARY.json`.

## 1. Unit of analysis and design

* **Statistic.** Relative WAPE improvement theta = 1 - sum|e_model| / sum|e_ref| over all (series, day) rows of the six 28-day test blocks. It is a ratio of sums: large-volume series dominate it.
* **Paired structure.** Model and baseline are scored on the *same* (series, day) rows (verified: identical row sets, S x 168 rows per cell), and the bootstrap resamples the paired (series, week) cell totals of both methods together. The pairing is correct at the unit that is resampled.
* **Resampling unit.** A bootstrap draw selects S series with replacement and, independently, W = 24 seven-day target blocks with replacement and recomputes the ratio on the selected sub-grid (a two-way "pigeonhole" resampling). Series are not independent (shared store calendar, events, shocks); weeks are not independent across the six retraining blocks (training windows of 730 days overlap heavily across origins).
* **What the design assumes.** Row and column effects are exchangeable, and interaction noise is independent across cells. The week dimension has only 24 units from 6 retraining blocks; autocorrelation of weekly differentials was small (lag-1 between -0.35 and 0.20, Table C) but is estimated from 24 points.

## 2. Independent recomputation of the confirmatory tests (H1)

Estimates, intervals and decisions were recomputed with (a) an independent re-implementation of the crossed bootstrap (B = 4000, different seed), (b) a different method, the delta-method (linearised) variance of theta with **two-way cluster-robust** (series and week) covariance, and (c) one-way bootstraps. Percent units; positive = model better.

| cell | estimate % | study crossed CI | independent crossed CI | two-way cluster-robust (delta) CI | series-only CI | week-only CI | study Holm p | independent Holm p | verdict (study) | verdict (independent, bootstrap / delta) |
|---|---|---|---|---|---|---|---|---|---|---|
| M5 CA_1, H=28 | -2.6 | [-5.8, +0.3] | [-5.9, +0.1] | [-5.3, +0.0] | [-5.2, -0.3] | [-4.0, -1.3] | 0.207 | 0.184 | INCONCLUSIVE | INCONCLUSIVE / INCONCLUSIVE |
| M5 CA_1, H=7 | -3.7 | [-6.4, -1.1] | [-6.3, -1.1] | [-5.9, -1.4] | [-5.7, -1.8] | [-5.1, -2.3] | 0.016 | 0.016 | CONTRADICTED | CONTRADICTED / CONTRADICTED |
| M5 TX_1, H=28 | -11.4 | [-14.8, -8.2] | [-14.9, -8.2] | [-14.1, -8.6] | [-14.5, -8.7] | [-12.5, -10.3] | 0.000 | 0.000 | CONTRADICTED | CONTRADICTED / CONTRADICTED |
| M5 TX_1, H=7 | -11.1 | [-14.3, -8.1] | [-14.2, -8.1] | [-13.7, -8.5] | [-13.9, -8.6] | [-12.3, -9.8] | 0.000 | 0.000 | CONTRADICTED | CONTRADICTED / CONTRADICTED |
| OR II, H=28 | -3.7 | [-10.4, +1.8] | [-10.3, +2.0] | [-9.1, +1.8] | [-8.0, +0.2] | [-8.5, +0.1] | 0.366 | 0.407 | INCONCLUSIVE | INCONCLUSIVE / INCONCLUSIVE |
| OR II, H=7 | -3.0 | [-8.4, +1.7] | [-8.6, +1.8] | [-7.6, +1.5] | [-6.5, +0.1] | [-6.8, +0.4] | 0.366 | 0.407 | INCONCLUSIVE | INCONCLUSIVE / INCONCLUSIVE |

**Result.** Point estimates agree to the last printed digit. Interval endpoints agree with the study's within Monte-Carlo error (largest endpoint difference over all 12 H1/H2 intervals: 0.26 percentage points). The frozen decision rule gives the same verdict in all six cells under the independent bootstrap **and** under the delta method. The Holm-adjusted p-values agree (differences are Monte-Carlo noise).

**H2 (best baseline of any information set):**

| cell | estimate % | study verdict | independent verdict (bootstrap / delta) | independent Holm p |
|---|---|---|---|---|
| M5 CA_1, H=28 | -6.8 | CONTRADICTED | CONTRADICTED / CONTRADICTED | 0.0000 |
| M5 CA_1, H=7 | -4.6 | CONTRADICTED | CONTRADICTED / CONTRADICTED | 0.0015 |
| M5 TX_1, H=28 | -15.0 | CONTRADICTED | CONTRADICTED / CONTRADICTED | 0.0000 |
| M5 TX_1, H=7 | -12.2 | CONTRADICTED | CONTRADICTED / CONTRADICTED | 0.0000 |
| OR II, H=28 | -3.7 | INCONCLUSIVE | INCONCLUSIVE / INCONCLUSIVE | 0.4070 |
| OR II, H=7 | -2.9 | INCONCLUSIVE | INCONCLUSIVE / INCONCLUSIVE | 0.4070 |

H2 for M5 is contradicted in four cells and inconclusive on Online Retail II in both methods, as the manuscript says. On Online Retail II H=28 the best baseline overall is the matched one, so H1 and H2 are the same test there (the H2 family therefore contains one duplicated comparison).

**Borderline case.** M5 CA_1 H=28 (estimate -2.6 %): the crossed interval just includes zero (study p = 0.069; independent bootstrap p = 0.062; delta method p = 0.052, interval upper limit +0.03 %). The one-way (series-only and week-only) intervals both exclude zero, so the "inconclusive" label depends on using the crossed design. The label is correct under the frozen rule, but it is not a robust "no difference": treat it as "negative and close to the boundary".

## 3. Dependence structure and effective sample size

| cell | series x week cells | effective independent cells (approx.) | design effect on the s.e. (two-way / naive iid) | lag-1 autocorrelation of weekly differential | pigeonhole s.e. / delta-method s.e. |
|---|---|---|---|---|---|
| M5 CA_1, H=28 | 8400 | 1300 | 2.5 | 0.02 | 1.13 |
| M5 CA_1, H=7 | 8400 | 1387 | 2.5 | -0.35 | 1.15 |
| M5 TX_1, H=28 | 8400 | 1666 | 2.2 | 0.03 | 1.21 |
| M5 TX_1, H=7 | 8400 | 1502 | 2.4 | 0.19 | 1.18 |
| OR II, H=28 | 2400 | 322 | 2.7 | 0.20 | 1.13 |
| OR II, H=7 | 2400 | 333 | 2.7 | 0.03 | 1.16 |

The series-level clustering is strong (the variance of series means is several times the within-cell variance), so the effective number of independent cells is about one sixth of the nominal one on M5 and about one seventh on Online Retail II. A naive i.i.d.-cells interval would be 2.2-2.7 times too narrow. The pre-registered crossed bootstrap accounts for this; a series-only interval (the historical benchmark's design) does not account for common week effects and the independent simulation below shows how badly it can fail.

## 4. Does a bootstrap that passes unit tests have the right coverage? (simulation)

I simulated cell totals with known two-way dependence (series effects, week-level shocks that hit the model and the baseline differently, cell noise), with the true improvement equal to 0, and counted how often each 95 % interval contained the truth.

| simulation (S=300 series, W=24 week blocks, true improvement 0) | crossed (pigeonhole) bootstrap | series-only bootstrap | two-way delta method |
|---|---|---|---|
| week-level shock sd 0.15: empirical coverage of the nominal 95% interval (300 replications) | 0.930 | 0.577 | 0.910 |
| week-level shock sd 0.15: mean interval width | 0.137 | 0.058 | 0.134 |
| week-level shock sd 0.40: empirical coverage of the nominal 95% interval (300 replications) | 0.903 | 0.247 | 0.903 |
| week-level shock sd 0.40: mean interval width | 0.322 | 0.059 | 0.323 |

* The **series-only** interval, used by the historical benchmark, covers only 25-58 % of the time when a week-level shock is present. The crossed design is therefore necessary.
* The **crossed bootstrap is not conservative here: it under-covers mildly (0.90-0.93)** with 24 week blocks; it is as accurate as the delta-method interval. The study's description of it as an approximation is accurate, but readers should not assume the intervals are conservative. The simulation is a stylised check of the method, not of the study's data.
* The "inconclusive" results are therefore not an artefact of an over-wide interval; if anything the intervals may be slightly too narrow.

## 5. Multiplicity and the family of tests

* The confirmatory H1 family (six tests, one per dataset-horizon cell) and the separate H2 family were fixed in `EXPERIMENT_PLAN.md` section 5 before the runs. Holm is applied to the correct family and the arithmetic reproduces (see table).
* **p-value resolution.** The bootstrap p-values come from 2000 draws, so the smallest non-zero value is 0.0005 and a raw "0" means p < 0.0005. After Holm (multiplier up to 6) the adjusted p-value is only known to be < 0.003 - not "< 0.001" as printed in Table 1 and in the ablation table of the manuscript (independent Holm p at the floor: 0.002). The conclusions are unaffected (the delta-method p-values are far smaller), but the printed bound is not supported by the procedure. Write "< 0.003", or use a larger B or the analytic p-values.
* The "contradicted" outcome is defined by the 95 % interval lying below zero and is not multiplicity-adjusted, whereas "supported" requires a Holm-adjusted p < 0.05. This asymmetry is in the frozen rule; it did not change any label here (all three contradicted cells have Holm p <= 0.016), but it should be stated.
* Segment (8 segment definitions x up to 6 cells), ablation and DM analyses are exploratory and unadjusted, as labelled.
* S2 (classification): Holm over 2 origins x 2 metrics = 4 tests; independent Holm p = 0.002 (A ROC), 0.002 (B ROC), 0.002 (B PR), 0.024 (A PR). The two origins are not independent (Section 7), so Holm's validity (no independence needed) holds but the *evidence* is closer to one replication with partially overlapping customers than to two.

## 6. Decision rules and hypothesis outcomes (frozen rules, independent numbers)

| hypothesis | outcome |
|---|---|
| H1 (6 tests) | contradicted: M5 CA_1 H=7, M5 TX_1 H=28, M5 TX_1 H=7; inconclusive: M5 CA_1 H=28, OR II H=28, OR II H=7; **supported: none** |
| H2 (6 tests) | contradicted: four M5 cells; inconclusive: both OR II cells; supported: none |
| C (classification; ROC-AUC and PR-AUC at both origins) | supported under the frozen rule (independent Holm p <= 0.024); effect sizes small and origins dependent (see PRE-REG and AUDIT_SUMMARY) |
| H3, H4, H6, H5, H7 | descriptive/exploratory as labelled; numerical values reproduce |

The 2 % minimum relevant gain and the block-win criteria were never decisive (H1 was not supported on the interval criterion alone).

## 7. Other threats to the inference

1. **Training windows overlap across the six origins** (730-day span, 28-day step): forecast errors in different blocks share training data and are positively dependent through the fitted model. The week-block resampling treats blocks as exchangeable; this is not modelled. Effect on the *model* side only; the baselines have no fitted parameters.
2. **Validation-selected reference baseline.** The reference is chosen on three validation blocks and then treated as fixed in the test; with 16 candidates the selection could favour a lucky baseline, but the same median baseline won in every cell, so the effect is small.
3. **One seed per model** and a small grid: seed variance of the learned model is not in the interval. A different seed could move the model's WAPE; the 3-11 % gaps seen in the M5 TX_1 cells are far larger than plausible seed noise, but the 2-4 % gaps are not.
4. **Metric-objective mismatch by design (see AUDIT_SUMMARY, blocker 1).** No candidate configuration used an L1/quantile objective although pooled WAPE's Bayes-optimal point forecast is a median. The statistical tests are valid for the question asked; the question is close to answering itself.
5. **Customer-level study:** one snapshot row per customer per origin, bootstrap over customers within an origin; across origins 94 % of origin B's test customers also appear at origin A (label correlation 0.40); about half of each test cohort already appears in the earliest training snapshot. Nothing here is a flaw in the arithmetic; it limits what "two origins" can show.

## 8. Language check

The manuscript does not call any result "superior" or "significant" without the interval, and it does not claim "no difference" for inconclusive cells. Remaining wording issues: (i) "pre-registered" (see PREREGISTRATION_AND_DEVIATIONS.md); (ii) "store-day aggregate" should read "aggregate over the 350-series (or 100-SKU) subset per day"; (iii) "Holm p < 0.001" as discussed; (iv) the abstract says L1 "lost the aggregate advantage", true on M5 only.
