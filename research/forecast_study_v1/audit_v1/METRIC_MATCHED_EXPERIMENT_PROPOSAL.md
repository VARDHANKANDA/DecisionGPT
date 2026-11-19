# METRIC_MATCHED_EXPERIMENT_PROPOSAL (MM1)

**Status: PROPOSAL ONLY. Nothing in this document has been implemented or run.** It needs your explicit written approval before any code is written for it, and a separate approval at the freeze gate before any test window is scored. It is **separate from the original study** (`forecast_study_v1`): different directory, different plan, different hypotheses. It does not change the original hypotheses, and it is not and will not be called "pre-registered" in the original study's sense: if frozen as described below it would be *pre-specified and internally frozen*, and *pre-registered* only if the authors additionally register it publicly (their decision; nothing is uploaded here).

Date: 2026-10-22. Basis: `AUDIT_SUMMARY.md` blocker S1; `STATISTICAL_AUDIT.md`; `FORECAST_DESIGN_AND_AGGREGATION_AUDIT.md`; measured fit times from the original runs and the post-hoc follow-up (E1).

## 1. Research question and hypotheses

**Question.** In the original study a validation-selected, mean-targeting boosted model lost to a trailing 28-day median in pooled item-day WAPE. Pooled WAPE is minimised by a conditional median [Gneiting, 2011], and no candidate used a median-type objective. **Does that objective mismatch plausibly explain the original deficit?** Equivalently: when the model's objective matches the metric, and everything else about the evaluation is held fixed, does the deficit disappear?

**Primary hypothesis (HM-P), per H = 28 cell.** A boosted forecaster with a median-type objective (candidate configurations in Section 3, selected on validation WAPE only) has **lower pooled item-day WAPE than the best-validation matched-information baseline** on held-out windows. Two-sided test; estimand: relative improvement (WAPE_baseline − WAPE_model)/WAPE_baseline.

**Mechanism hypothesis (HM-S), per cell.** The same median-objective model has lower pooled item-day WAPE than the **original-study model configuration** (LightGBM with the Tweedie objective, selected in all six original cells) refit on the same windows with the same features, training spans and seed — i.e. the difference isolates the objective.

**Explanation criterion (EC; pre-specified, per cell).** "Objective mismatch plausibly explains the original deficit" is declared for a cell if **both** (i) HM-S is supported (improvement ≥ 2 %, 95 % interval excluding 0, Holm p < 0.05) **and** (ii) the median-objective model is *not inferior* to the best matched baseline: the lower 95 % bound of its improvement over that baseline is > −2 % (the same 2 % margin as the original minimum relevant difference). If (i) holds but (ii) fails with the upper 95 % bound below 0, the mismatch explains part of the deficit but the baseline remains better. If (i) fails, the mismatch explanation is not supported. Anything else is inconclusive.

## 2. Why this objective for this metric

Pooled item-day WAPE is Σ|ŷ − y| / Σy with a denominator that does not depend on the forecast, so minimising it is minimising total absolute error; the Bayes-optimal point forecast for absolute error is the conditional median, and absolute error is strictly consistent for it (and for no other functional) [Gneiting, 2011; Kolassa, 2020]. Boosted trees with an L1 (absolute-error) objective estimate that median directly. The comparison therefore removes the known mismatch without changing the metric. The proposal deliberately does **not** change the metric to suit the mean model, and it keeps the aggregated metrics as descriptive endpoints: a median-objective model is expected to be biased low at aggregate level (the post-hoc follow-up found bias −0.37 to −0.49), so a win here would not make it the "better" forecaster for decisions about totals.

## 3. Design

**Model arm B (new).** Gradient-boosted trees with an absolute-error objective, predictions clipped at zero, three candidates selected on validation WAPE only (mirrors the original selection rule):
* `lgbm_l1_a`: LightGBM, objective `l1`, the same hyper-parameters as the original LightGBM variants otherwise (500 trees, learning rate 0.05, 31 leaves, min child samples 40, subsample 0.8, column sample 0.8) — the configuration used in the post-hoc follow-up;
* `lgbm_l1_b`: as above with 15 leaves and min child samples 100 (a smoother variant for sparse series);
* `xgb_l1`: XGBoost, objective `reg:absoluteerror`, the original depth-6 settings otherwise.
CatBoost with an absolute-error loss is excluded for cost (measured about 137 s per fit on M5 versus about 10 s for LightGBM); this is a stated limitation.

**Comparator arm A′ (refit).** LightGBM, Tweedie objective, the original settings, **fixed** (no selection; it was the validation-selected primary model in all six original cells), refit on the new windows.

**Baselines C.** The same 16 baselines (8 estimators × matched/fresh information), recomputed on the same rows; the best-validation matched baseline and the best-validation baseline of any information set are chosen on the new windows' validation blocks.

**Features, training spans, seed.** Identical to the original study: the repository's historical direct-feature builder, minimum lag H, training rows with target day in [o − 730, o − 1], seed 42 (two further seeds, 43 and 44, for the selected configuration only, reported descriptively).

**Datasets, horizons, windows.**
* **Tier 1 (the minimum comparison that can answer the question):** the three H = 28 cells — M5 CA_1, M5 TX_1, Online Retail II top-100 SKUs — evaluated on **new, never-scored windows (W2)**.
* **Tier 2 (recommended extension, secondary):** the three H = 7 cells on W2, and all six cells on the **original windows (W1)** as a replication that is explicitly **not independent** (those test days have been scored and examined repeatedly).
* **W2 definition.** Truncate each dataset at T′ = T − 252 days (M5: T′ = 1,689, so all data from day d_1689 on are discarded before anything is built; Online Retail II: T′ = 487). On the truncated data apply the original protocol unchanged: six consecutive 28-day test blocks covering the last 168 days of the truncated series (M5: days 1,521–1,688), three validation blocks immediately before them (M5: 1,437–1,520), forecasts for each block from a model refit at that block's start. W2 ends one day before the original study's first validation block, so W2 never overlaps the original validation or test days. W2 days were used only as *training* targets for later origins in the original study; they were never scored.
* **Limitation of W2.** It covers an earlier period, with a shorter training history (especially Online Retail II: about 235–459 days of history at the W2 origins, versus about 487–711 in the original); non-stationarity and the shorter history are limitations, not a reason to prefer W1.
* **Origins, blocks.** Per cell: six retraining blocks (28 target days), 24 weekly blocks, identical rows for all methods.

**Leakage prevention.** (1) Arrays are truncated to T′ before any feature, baseline, segment or scale is computed, and a unit test asserts no computed quantity depends on a perturbed value at or after T′. (2) The original future-perturbation check (features unchanged when everything after a cutoff is overwritten) runs at four cutoffs per cell. (3) Matched and fresh baselines use only history up to their cutoff (the same code the audit verified row by row). (4) Selection uses validation blocks only and is written to disk, with its hash, before any test block is fitted; the test-stage script refuses to start unless the freeze record verifies. (5) The new experiment never reads original-study test predictions except, in Tier 2 on W1, to reuse the stored original Tweedie predictions as A′ (read-only, hash-checked).

## 4. Metrics, effect size, uncertainty, multiplicity

* **Primary metric:** pooled item-day WAPE (as in the original study). **Effect size:** relative improvement (WAPE_ref − WAPE_new)/WAPE_ref, pooled over the six test blocks; minimum relevant difference 2 % (unchanged).
* **Uncertainty:** paired crossed series × week-block bootstrap, **B = 10,000** (resolution 10⁻⁴, so adjusted p-values are reported as exact bounds), fixed seed; an independently implemented two-way cluster-robust delta-method interval as a pre-specified cross-check; the original simulation result (the crossed interval covers about 90–93 % for a nominal 95 %) is acknowledged in the reporting.
* **Multiplicity:** three families, Holm within each: (F1) HM-P over the Tier 1 cells (3 tests; 6 if Tier 2 W2 H = 7 cells are added); (F2) HM-S likewise; (F3) none — all other comparisons (aggregated metrics, bias, RMSE, RMSE vs baselines, segment views, seed sensitivity, W1 replication) are **descriptive** and unadjusted.
* **Decision rule for HM-P per cell** (same as the original H1): *supported* if Holm p < 0.05, the 95 % interval excludes 0, the gain is ≥ 2 % and the model wins ≥ 4 of 6 test blocks; *contradicted* if the interval lies entirely below 0; otherwise *inconclusive*.
* **Descriptive endpoints always reported:** item-week and subset-day WAPE, relative bias, RMSE and MAE of arms A′, B and the matched baseline; zero-forecast share; the aggregation ladder.

**Expected precision (from the post-hoc follow-up on the original windows).** Half-widths of 95 % intervals for the L1 model vs the matched baseline were about 1.4 percentage points (M5 CA_1), 2.4 (M5 TX_1) and 1.9 (Online Retail II). Effects of about 3 % or more should be resolvable; an effect near 1 % (as seen on M5 TX_1) would very likely be inconclusive. This limit is stated in advance.

## 5. Compute, runtime and failure conditions

Measured on this machine (4 cores, 7.7 GB, CPU only) in the original runs: LightGBM about 10 s per fit on an M5 cell, XGBoost about 13 s, Online Retail II fits about 2–4 s.

| Scope | Fits (approx.) | Estimated wall-clock |
|---|---|---|
| Tier 1: 3 H = 28 cells on W2 (validation 9 candidate-fits + 6 selected + 6 A′ + 12 seed refits per cell) | about 33 per cell | **about 15–25 minutes** |
| Tier 2a: 3 H = 7 cells on W2 | about 33 per cell | about 15–25 minutes |
| Tier 2b: 6 cells on W1 (selection redone on the original validation blocks; A′ reused read-only) | about 27 per cell | about 30–40 minutes |
| Independent verification and analysis | — | about 10 minutes |
| **Total (Tier 1 + Tier 2)** | | **about 1.5–2 hours; budget cap 3 hours** |

Disk: below 100 MB; no network; no API calls. **Failure / stop conditions (pre-specified):** any leakage check or truncation test fails; any NaN/negative prediction after clipping is not zero-bounded; the freeze verification fails at the test gate; wall-clock exceeds twice the estimate for a tier; the independent verification has any failed check; the raw data are missing. On a stop condition the run halts, the state is reported, and nothing is rerun with modified settings without a logged deviation and your approval.

## 6. Freezing before test evaluation

1. **G0 – approval of this proposal** (you), including the tier scope.
2. **G1 – implementation** in a **new directory `research/metric_matched_v1/`** (code, unit tests, plan `MM1_PLAN.md`). The original study directory, its plan, freeze, predictions and results are read-only and untouched. No test window is scored in this gate.
3. **G2 – validation-only dry run:** the pipeline is exercised only on the validation blocks of W2 (a mode that cannot compute test metrics); outputs are checked for runtime, determinism and leakage tests. This is the only contact with data before the freeze, and its scope is logged.
4. **G3 – freeze:** write `MM1_FREEZE.json` containing UTC time, git head, SHA-256 of the plan, code, tests and configuration, library versions and the exact window definitions; you review it. Optionally, you may register the plan publicly (OSF or similar) **before** G4 to turn "internally frozen" into "pre-registered"; this proposal does not do that.
5. **G4 – stage 1 (validation and selection)** writes `selection.json` and its hash; **stage 2 (test)** starts only after the script verifies the freeze hashes and that `selection.json` is older than any test fit; a plan deviation after G3 is allowed only by an append-only dated entry.
6. **G5 – independent verification** with a separate script that imports nothing from the new code (as in the audit), then **G6 – report**.

## 7. Reporting under each outcome

The report will contain the full result table for every cell, the descriptive aggregation ladder, the bias and the interval summaries, whatever the result. It will state that W2 is the confirmatory window and W1 a non-independent replication, and will repeat the disclosures of the original study (internal freeze, prior exposure to W1, AI-assisted authorship).

| Outcome | Reporting and conclusion allowed |
|---|---|
| **Median-objective model wins** (HM-P supported, EC met) in some or all Tier 1 cells | "In these datasets and windows, the original item-day deficit disappears when the model's objective matches the metric, which is consistent with objective mismatch explaining it." Report in the same breath that aggregate WAPE and bias are worse than for the mean-targeting model, so the model is not 'better' in general; give the number of cells; do not generalise beyond the tested families, datasets and window. |
| **Median-objective model loses** (HM-P contradicted, or EC unmet with HM-S supported) | "Matching the objective did not close the gap to a trailing 28-day median on these data; the deficit is not (only) an objective mismatch; baseline strength on sparse daily demand is a sufficient explanation." No further tuning or additional models are added to rescue the result; negative results are reported in full. |
| **Inconclusive** (intervals include 0 and the non-inferiority margin) | Report effect sizes and intervals; say that the experiment could not distinguish equivalence from a small difference (as expected near 1 %); do not call it 'no effect'. A larger or longer experiment would need a new plan. |
| **Mixed across cells** | Report each cell with its own verdict; no pooled claim stronger than the weakest cell; discuss data differences (Online Retail II is less sparse, has less W2 history). |
| **HM-S not supported** (objective does not change the result) | Report that the objective effect seen post hoc on W1 did not reproduce on W2; treat the post-hoc follow-up as unreplicated. |

## 8. What the experiment can and cannot support

**Can:** whether, for LightGBM/XGBoost with an absolute-error objective, the item-day pooled-WAPE deficit against a trailing 28-day median is removed on earlier, never-scored windows of the same three datasets; the size of the objective effect with a paired, dependence-aware interval; the trade-off at aggregate level; a replication check on W1 (non-independent).

**Cannot:** that machine-learning models in general beat or fail to beat simple baselines; results for other datasets, other families (CatBoost, neural, foundation, statistical ETS/ARIMA), other horizons, other metrics (e.g. scaled-error or probabilistic metrics) or other populations (including Indian SMEs); causal statements about features; that the model is better for stock, staffing or revenue decisions (which depend on totals, not item-day absolute error); that the original study's primary H1 result was wrong (it stands as reported); or that the new result is 'pre-registered' in the public sense. Because the windows are earlier in the same series and the author team has seen the original and post-hoc results, the confirmation is **not blind** to the earlier findings.

## 9. Open decisions for you

1. Approve **Tier 1 only** (about 20 minutes) or **Tier 1 + Tier 2** (about 1.5–2 hours; recommended).
2. Approve **W2 (earlier, never-scored windows) as the confirmatory window**, with W1 as a non-independent replication (recommended), or require W1 only (weaker, because W1 has been seen repeatedly).
3. Approve the candidate set (LightGBM L1 ×2, XGBoost absolute error; CatBoost excluded for cost) or name additions with their runtime cost.
4. Decide whether to **register the plan publicly** before the test gate (your action; none is taken here).
5. Approve creating `research/metric_matched_v1/` and the approval gates above.

No code for MM1 exists yet and no data have been touched for it.
