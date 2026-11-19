# EXPERIMENT_PROTOCOL — forecast_study_v2 (pre-specification; internally frozen by `FREEZE.json`)

Written 2026-10-22 before any W2, W3 or fresh-store validation or test outcome was read. **Status of this record:** an *internal*, timestamped hash freeze (`FREEZE.json`); it is **not** a public pre-registration (a registration draft is in `PREREGISTRATION_DRAFT.md`; nothing has been uploaded). Changes after the freeze are allowed only as dated entries in `DEVIATIONS.md`.

This study is **separate** from `forecast_study_v1` (whose plan, freeze, predictions and results are untouched) and was designed with knowledge of v1's results and of the independent audit (`WINDOW_USE_AUDIT.md` lists the exposure). It is not blind to those findings.

## 1. Research question

> Under a design that fixes model selection on validation data **for the endpoint being reported**, and evaluates on held-out windows that no experiment has scored, **does a boosted model beat the best simple baseline, how large is the difference, and how does the answer change between the item-day and the aggregated (subset-day) endpoint?**

Why this question after the literature review: the dependence of rankings on loss and aggregation is established theory (`LITERATURE_REVIEW.md` §4), so the study does not ask *whether* metrics matter. It asks *how large* the effect is for strong baselines on public data, *where* it comes from (level bias vs skill), and whether the original negative result (a Tweedie model losing item-day WAPE to a trailing median) survives when the candidate set includes median-type objectives and selection is endpoint-matched. The contribution is an incremental empirical one.

## 2. Hypotheses (per cell = dataset × minimum lag H; confirmatory cells = W2, Section 4)

* **H1 (primary).** The model selected on validation **item-day WAPE** has lower pooled item-day WAPE than the best-validation **matched-information** baseline.
* **H1b (secondary).** The same against the best-validation baseline of **any** information set (matched or fresh).
* **H2 (mechanism; objective effect).** The same model has lower pooled item-day WAPE than the **original reference model** (LightGBM, Tweedie variance power 1.1, the configuration selected in all six v1 cells) refit on the same window with the same features, training spans and seed.
* **H3 (aggregate endpoint).** The model selected on validation **subset-day WAPE** has lower subset-day WAPE than the best-validation matched baseline (selected on subset-day WAPE).
* **H4 (descriptive).** Whether the sign of the improvement differs between the item-day endpoint (H1) and the subset-day endpoint (H3) within a cell ("endpoint dependence").
* **Exploratory (labelled, unadjusted):** segment effects (frequency, volume), seed sensitivity, aggregation ladder, bias decomposition.

All tests two-sided. Directional expectations (from theory, stated for transparency, not used in decisions): H1/H2 favour median-type objectives; H3 favours mean-type objectives.

## 3. Estimands and endpoints

* **Item-day pooled WAPE** = Σ|ŷ − y| / Σy over all eligible (series, day) rows (primary).
* **Subset-day WAPE** = Σ_d |Σ_s (ŷ − y)| / Σ_d Σ_s y: demand of the whole selected subset summed per day before scoring (an aggregate over the 350 / 100 selected series, not over a store).
* Descriptive: item-week, subset-week, relative bias (positive = over-forecast), MAE, RMSE, share of zero forecasts.
* **Effect size** = relative improvement (E_ref − E_model)/E_ref of the endpoint error, pooled over the six test blocks of a window; positive = the model is better. **Minimum relevant improvement: 2 %.** Justification: it is the v1 value (comparability), it exceeds typical block-to-block noise in v1, and it will be compared with the measured seed-to-seed spread (Section 9); it is arbitrary and is not used to claim practical value beyond the observed uncertainty.

## 4. Data, entities and windows

Datasets (all public; rights in `DATA_RIGHTS_AUDIT.md`): M5 stores CA_1, TX_1, WI_1 (350 / 350 / 349 department-stratified random series per store among series with first sale on or before d_1100; seed 20261015) and Online Retail II (top-100 SKUs by revenue before the window's first validation block, re-selected per window). Windows are defined by trailing days removed **before anything is built** (`windows.py`): W1 (0), W2 (252), W3 (504); on the truncated series of length T′ the last 168 days form six 28-day test blocks and the preceding 84 days three validation blocks.

| evaluation set | role | cells |
|---|---|---|
| **W2 — CA_1, TX_1, WI_1, OR II** | **Confirmatory** (Holm families over 8 cells: 4 datasets × H ∈ {28, 7}) | 8 |
| W3 — CA_1, TX_1, WI_1 (OR II infeasible) | Replication (descriptive; same estimands) | 6 |
| W1 — WI_1 | Replication; entity-fresh store, period seen for other stores | 2 |
| W1 — CA_1, TX_1, OR II | Non-independent re-evaluation (continuity with v1) | 6 |

Exposure of each set is in `WINDOW_USE_AUDIT.md`. A date being earlier did not make a window unseen; W2/W3 targets of the evaluated entities were never scored, but their period was used as training data and in descriptive statistics, and this is disclosed.

**Eligible rows.** M5: the item has a listed selling price on the target day (days without a listing carry zero demand by construction: 0 units on unlisted days, verified) and ≥ 84 + H days of history precede the day; Online Retail II: ≥ 84 + H days of history. The same rows are used for every method; rows where any prespecified baseline is undefined are removed for all methods.

## 5. Forecasting task and models

**Task.** Direct H-day-ahead forecasts (H ∈ {28, 7}) of daily units, global model across series; the model for a block starting at day o is refit on rows whose **target day** lies in [o − 730, o − 1]; features of day t use sales history up to t − H plus calendar and (M5) listed price information for day t (known in advance); the feature builder is the repository's historical, leak-tested builder, run on the truncated series. Predictions are clipped at 0.

**Candidate models** (shared base hyper-parameters: 500 trees (XGBoost 400), learning rate 0.05, 31 leaves, subsample 0.8, column sample 0.8; `models.py` states each objective's target functional):
`lgbm_tweedie_p11` (the v1 reference), `lgbm_tweedie_p15`, `lgbm_l2`, `lgbm_l1`, `lgbm_l1_small` (15 leaves, min child 100), `lgbm_quantile50`, `xgb_l1` (`reg:absoluteerror`), `ridge_a100`.
CatBoost is excluded (≈ 137 s per fit versus ≈ 10 s). Statistical models beyond the baselines below (ETS/ARIMA/Theta) are not implemented because `statsmodels`/`statsforecast` are not installed and installing packages was not authorised; this is a stated limitation.

**Model selection (validation only).** For each endpoint, the candidate with the lowest mean over the three validation blocks of that endpoint's WAPE is selected (`model_item_day`, `model_subset_day`); ties by name. Selection is written to `selection.json` before any test block is fitted. Test fits are made **only** for `model_item_day`, `model_subset_day` and the reference model. For W2, `model_item_day` is also refit with seeds 43 and 44 (seed sensitivity, descriptive).

## 6. Baselines (prespecified; 31)

Sixteen estimators — naive, seasonal naive, weekday mean (4, 8 weeks), weekday median (4, 8), trailing mean (28, 91), trailing median (14, 28, 56, 91), Croston, Croston-SBA, TSB, all-zero — each under two information sets: **matched** (history up to t − H, exactly what the models see) and **fresh** (re-estimated at the block or week start, 1 to H days old); the all-zero forecast exists once (its WAPE is 1 by construction and anchors the scale). Baseline selection is by validation data only: `baseline_item_day_matched`/`_any` and `baseline_subset_day_matched`/`_any` (lowest mean validation WAPE of the endpoint). Baselines are not tuned beyond the choice among these prespecified variants (smoothing constants 0.1 fixed). Rationale for the set: the original study's best baseline was a trailing median, so median windows and weekday medians are included to test baseline strength; Croston/SBA/TSB are the standard intermittent estimators; the zero forecast is a sanity anchor. ADIDA-type temporal-aggregation baselines are omitted (alignment of buckets at every cutoff is not implemented) — a limitation.

## 7. Inference

* **Item-day endpoints (H1, H1b, H2):** paired **crossed bootstrap** over series and 7-day target blocks (B = 10,000) is the PRIMARY method; a **two-way cluster-robust delta-method** interval with a t(G − 1) reference (G = min(#series, #weeks)) is the SECONDARY method. Choice fixed by the pre-freeze simulation (`results/simulation_inference.json`, rule: smallest worst-case coverage error over the grid): crossed bootstrap worst-case error 0.050 vs 0.052 (delta, t) vs 0.073 (delta, normal) vs 0.757 (series-only); mean coverage 0.937 and Type-I error up to 0.10 at nominal 0.05 — **both methods are mildly liberal**.
* **Subset-day endpoint (H3):** bootstrap over 7-day blocks of daily totals (series are aggregated away); PRIMARY = iid weeks (simulation worst-case error 0.057, coverage 0.89–0.94), SECONDARY = stationary block bootstrap (mean block 3 weeks; worst-case 0.09). With 24 weekly blocks, aggregate-endpoint precision is limited and the daily totals are not independent.
* **Dual-method rule.** A verdict stands only if the secondary method, applied with the same rule and its own Holm adjustment, gives the same verdict; otherwise the verdict is INCONCLUSIVE and both are reported.
* **Multiplicity.** Holm within each family (H1, H1b, H2, H3) across the 8 confirmatory W2 cells. Replication sets (W3, W1) are analysed descriptively with their own Holm adjustment within the set and are not pooled with the confirmatory family.
* **Decision per cell** (identical for H1, H1b, H2, H3): **SUPPORTED** iff Holm p < 0.05, the 95 % interval excludes 0, improvement ≥ 2 % and the model wins ≥ 4 of the 6 test blocks on that endpoint; **CONTRADICTED** iff the 95 % interval lies entirely below 0 (not multiplicity-adjusted); otherwise **INCONCLUSIVE**. An inconclusive cell is never described as "no effect".
* **Effective sample.** The report states the number of series, weekly blocks and the approximate effective independent cells (variance-component design effect) per cell.

## 8. Replication criteria

A confirmatory verdict is called *replicated* in a replication set if the sign of the improvement agrees and the verdict is the same or one step weaker (SUPPORTED → INCONCLUSIVE). Non-replication is reported, never averaged away. A cross-cell summary reports counts (supported / contradicted / inconclusive of 8), not a pooled p-value.

## 9. Exploratory and sensitivity analyses (all labelled, unadjusted)

Aggregation ladder (item-day, item-week, subset-week, subset-day) for every selected model and the reference baselines; bias decomposition (zero-forecast rows vs positive-forecast rows; trailing mean vs median at the same window); segment effects (ADI/CV² frequency, volume terciles; ≥ 20 series); seed sensitivity (W2: seeds 42/43/44); the objective effect H2 on W1 and W3; checks that the selected model's rank does not depend on the validation endpoint. No feature ablation is planned: the v1 ablations answered that question (exploratory, one store).

## 10. Not part of the confirmatory plan

Predictive intervals (peripheral to the research question; the v1 findings and the audit are summarised in `UNCERTAINTY_ANALYSIS.md`, not re-evaluated); the customer-inactivity classification thread (separate exploratory report); deep, foundation and probabilistic models; hierarchical reconciliation; price-effect or causal claims.

## 11. Compute budget and stopping conditions

Estimated 1.3 h validation stage + 1.5 h test stage + 0.3 h analysis on this machine (4 cores, 7.7 GB); hard cap 8 hours wall-clock and 30 minutes per cell-window. Stop conditions: any leakage check fails; the freeze verification fails; any non-finite prediction; the independent verification has a failed check; the cap is exceeded. On stopping, outputs are preserved, the unfinished cells are reported, and test coverage is never silently reduced.

## 12. Gates and freeze procedure

G1 code and unit tests complete (no W2/W3/WI_1 data touched except targets-vs-raw rebuilds and descriptive data audits); G2 pre-freeze dry run on already-scored Online Retail II W1 validation blocks only; G3 **freeze** (`python -m research.forecast_study_v2.freeze create`: SHA-256 of protocol documents, code and tests); G4 validation stage for all cell-windows, producing `selection.json` per cell; G5 test stage (refuses to run unless the freeze verifies and `selection.json` exists; checks that selection preceded the first test fit); G6 analysis, independent verification (separate script, no imports from the study), reporting. The pre-freeze simulation and unit tests are logged in `DEVIATIONS.md` as pre-freeze activity.

## 12a. Interpretation rules fixed in advance

* A SUPPORTED H1 in a cell supports "the validation-selected boosted model beat the best matched baseline on item-day WAPE in that cell and window"; it does **not** support a claim about other data, objectives or metrics.
* If H1 is supported while H3 is not (or vice versa) in a cell, the report states that the winner depends on the endpoint; no single winner is declared.
* If the selected item-day model is the reference configuration in a cell, H2 is not applicable there and is reported as such.
* A conditional recommendation (which model for which task) is allowed only where the corresponding hypothesis family supports it in a majority of confirmatory cells **and** the replication sets do not contradict it.

## 13. Software and reproducibility settings

Python 3.12, LightGBM 4.7.0 (`deterministic=True`, `force_row_wise=True`), XGBoost 3.4.0, scikit-learn 1.9.0, numpy 2.5.2, pandas 3.0.5, scipy 1.18.0; seeds: model 42 (43, 44 for sensitivity), bootstrap 20261024, simulation 20261023, M5 series draw 20261015; thread count 4. Runs are checkpointed (`fits/*.npy`) and resume only when the configuration hash is unchanged.
