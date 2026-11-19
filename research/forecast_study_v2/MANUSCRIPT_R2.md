# Does a boosted model beat the best simple baseline? Endpoint-matched evaluation of daily retail demand forecasts on public data

*Working title. Draft for author review — not submitted. Author names, affiliations and declarations: [AUTHOR TO COMPLETE].*

## Abstract

**Background.** A previous study in this project found that a LightGBM model with a Tweedie objective did not beat a trailing 28-day median on pooled item-day weighted absolute percentage error (WAPE) for daily retail demand, while winning after demand was aggregated. Forecasting theory attributes such reversals to the scoring function (absolute error rewards the conditional median, squared error the mean), but the size of the effect, and whether the earlier negative result survives a candidate set that includes median-type objectives, had not been measured under a stricter protocol.
**Methods.** Direct 7- and 28-day-ahead forecasts of daily units were evaluated on three M5 stores (350/350/349 department-stratified series) and the 100 largest-revenue SKUs of Online Retail II, in six rolling 28-day test blocks after three validation blocks, on a confirmatory window that no experiment had scored (W2) and on replication windows (W3, W1). Eight boosted-tree or ridge candidates and 31 simple baselines (16 estimators × matched and fresh information) were compared. Selection was made on validation data for the endpoint being reported (item-day or subset-day WAPE); the protocol was hash-frozen before any confirmatory outcome was read. Inference used a paired crossed bootstrap over series and weeks (secondary: two-way cluster-robust interval), Holm correction, a 2 % minimum improvement and a dual-method rule.
**Results.** On the confirmatory window the validation-selected absolute-error LightGBM beat the best same-information baseline on item-day WAPE in all 8 dataset–horizon cells (median +4.3 %, range +2.5 % to +6.0 %), and the improvement was positive in all 22 cells over three windows (supported in 20). It beat the earlier Tweedie model in every cell (+7.9 % to +16.8 %). Against baselines that see up to 28 days more recent data the advantage was not established at the 28-day horizon. On the aggregate (subset-day) endpoint the selected models were mean-type (Tweedie or squared error); the item-day winner, with a relative bias of −0.29 to −0.39, lost to simple baselines (subset-day WAPE 0.35 against 0.11 for CA_1, 28 days), and the improvement of the aggregate-selected model over the best baseline was supported in 4 of 8 cells (point estimates positive in 7 of 8; one boundary cell was re-examined with a supplementary calculation that left every verdict unchanged).
**Conclusions.** For these samples the earlier negative result changes sign when the objective and the evaluation endpoint are matched, with modest gains at item-day and endpoint-dependent rankings. The finding is an empirical quantification of established theory on four public data sets, not a new method. Statistical (ETS, ARIMA, Theta), neural and probabilistic competitors were not evaluated, and the result does not extend to other retailers or to decision costs. The verification was internal (one AI assistant wrote the study and its checks).

**Keywords:** demand forecasting; intermittent demand; gradient boosting; scoring functions; forecast evaluation; aggregation; reproducibility.

## 1. Introduction

Boosted trees are strong forecasters of retail demand: in the M5 accuracy competition most of the examined methods, and almost all of the top-50 methods for which a description was available, were LightGBM-based [Makridakis et al., 2022], and tree-based methods outperformed other approaches there [Januschowski et al., 2022]; reviews of Kaggle forecasting competitions, whose data are typically intermittent, report that gradient-boosted trees and neural networks are strong [Bojer & Meldgaard, 2021]. Yet strong aggregate results do not settle whether a learned model beats a *well-chosen simple baseline* on a given error measure. Forecasting theory is explicit that the optimal point forecast depends on the scoring function: squared error is minimised by the conditional mean, absolute error by the conditional median [Gneiting, 2011; Kolassa, 2020; Koenker & Bassett, 1978]. For sparse daily demand, whose conditional median is often zero, absolute-error measures therefore reward low forecasts (a consequence of the result just cited, not a finding of this study); conventional accuracy measures can also rank forecasters of intermittent demand incorrectly or be degenerate [Prestwich et al., 2014; Hyndman & Koehler, 2006], and the evaluation and optimisation of intermittent-demand forecasts has its own literature [Kolassa, 2016; Kourentzes, 2014]. Aggregating demand over time or items changes the forecasting problem [Nikolopoulos et al., 2011; Athanasopoulos et al., 2017].

A previous study in this project (the "v1 study") found that a LightGBM model with a Tweedie objective did not beat a trailing 28-day median in pooled item-day WAPE on two M5 stores and one retail dataset, while winning after demand was summed over days. An internal audit of that study (carried out by the same AI assistant, so not independent) showed that the contrast was largely the baseline's level bias, that no candidate model targeted a median, and that the evaluation windows had been examined repeatedly. The present study asks the question again under a stricter design.

**Research question.** Under model selection fixed on validation data *for the endpoint being reported*, and on evaluation windows that no experiment had scored, does a boosted model beat the best simple baseline; by how much, with what uncertainty; does the answer change between the item-day and the aggregated endpoint; does the v1 negative result survive when median-type objectives are in the candidate set; and does the answer replicate across stores, horizons and windows?

## 2. Related work and what is already known

The relationship between loss function and optimal forecast [Gneiting, 2011; Kolassa, 2020], the unreliability of conventional error measures for intermittent and low-count demand [Hyndman & Koehler, 2006; Prestwich et al., 2014; Kolassa, 2016; Kourentzes, 2014], temporal and cross-sectional aggregation [Nikolopoulos et al., 2011; Athanasopoulos et al., 2017; Hyndman et al., 2011; Spiliotis et al., 2021], and the strength of boosted trees on M5-type data [Makridakis et al., 2022; Januschowski et al., 2022; Bojer & Meldgaard, 2021; Spiliotis et al., 2022] are established. Evidence that machine-learning methods do not automatically beat statistical ones also exists [Makridakis et al., 2018; Makridakis et al., 2020], and retail forecasting has its own practice and measurement issues [Fildes et al., 2022]. Evaluation guidance is given by Hewamalage et al. [2023]. A preprint compares local and global models for intermittent series [Damato et al., 2026].

In the sources read for this study (a bounded literature review, not a systematic one), I did not find a report that combines endpoint-matched validation selection, never-scored windows chosen under a written freeze, a large prespecified baseline set, and paired two-way dependence-aware intervals for a boosted model on public retail data. That is an absence in what was read, not proof of absence. The expected direction of the main effect follows from theory; the study measures its size and location.

## 3. Contributions and scope

*Contributions (incremental and empirical).* (i) Magnitudes of the item-day and aggregate differences between validation-selected boosted models and the best of 31 simple baselines on four public datasets, two horizons and replication windows, under a frozen protocol; (ii) a test of whether the v1 negative result survives a candidate set that includes median-type objectives; (iii) a decomposition of the baseline's level bias; (iv) a pre-freeze simulation of the interval methods and a dual-method decision rule; (v) a documented package with frozen protocol, pinned environment and deterministic settings (a fresh-environment reproduction has not been performed). *Not contributions:* a new model, metric or principle; any claim about Indian SMEs or other populations; causal effects; customer churn; predictive intervals.

## 4. Data and data rights

M5 [Makridakis et al., 2022; Kaggle competition data]: daily unit sales for 350 (CA_1, TX_1) and 349 (WI_1) department-stratified random series per store, drawn among series whose first sale falls on or before day d_1100 (products launched later are excluded; seed 20261015). Online Retail II [Chen, 2012; CC BY 4.0]: the 100 SKUs with the largest revenue before the first validation block of each window, daily gross units after documented cleaning (cancellations, non-positive quantity or price, non-product codes and 33,666 exact duplicate lines removed; returns excluded). M5 items are evaluated on days with a listed selling price (days without a listing carry zero demand by construction; verified); this eligibility rule is an assumption about ex-ante knowledge. **Rights:** the M5 competition rules (read 2026-10-22) permit use of the Competition Data "for non-commercial purposes only, including … for academic research and education" and prohibit transmitting, duplicating, publishing or redistributing it to anyone not participating in the competition; this study uses it for academic research only, and neither the data nor any array that contains M5 sales (stored predictions include the actual values) is released (Section 13). Whether forecasts alone may be shared is not stated in the rules and is treated as not permitted unless the rights holder agrees.

## 5. Windows and protocol

A window is defined by the number of trailing days removed *before anything is built*: W1 (0), W2 (252), W3 (504). On the truncated series the last 168 days form six consecutive 28-day test blocks and the preceding 84 days three validation blocks. **W2 (all four datasets) is the confirmatory window**; W3 (M5) and W1 for the fresh store WI_1 are replications; W1 for CA_1, TX_1 and Online Retail II is a non-independent re-evaluation (those periods were scored repeatedly). Exposure of every window to earlier experiments, including a retired benchmark that used the W2/W3 *periods* on 40 other M5 series, is documented (`WINDOW_USE_AUDIT.md`); no evaluated entity's W2/W3 target was scored before. The design was fixed with knowledge of the v1 results and the audit.

*Forecasting task.* Direct forecasts of daily units for a minimum lag H ∈ {28, 7} days: target day t uses sales history up to t − H plus calendar and (M5) listed-price information of day t; a global model is refit for each block on rows whose target day lies in [o − 730, o − 1] (o = block start). This is **not** the M5 competition setting. Predictions are clipped at zero.

*Freeze.* The protocol, code and tests were hashed on 2026-10-22 (08:15:19Z) before any W2/W3/WI_1 validation or test outcome was read (`FREEZE.json`); this is an **internal** freeze, not a public pre-registration. Pre-freeze activity (unit tests, a dry run on already-scored Online Retail II W1 data, a simulation on synthetic data, literature review) is logged in `DEVIATIONS.md`.

## 6. Models and baselines

*Candidates* (shared base hyper-parameters: 500 trees (XGBoost 400), learning rate 0.05, 31 leaves, subsample 0.8, column sample 0.8): LightGBM [Ke et al., 2017; gradient boosting: Friedman, 2001] with Tweedie objective (variance power 1.1, the v1 reference; and 1.5), squared error, absolute error (two variants: 31 leaves; 15 leaves with min. child 100), quantile objective at 0.5, XGBoost [Chen & Guestrin, 2016] with absolute error, and ridge regression. Target functionals: squared error and Tweedie (log link) estimate conditional means; absolute error and the 0.5 quantile estimate the conditional median. CatBoost was excluded for cost; statistical models beyond the baselines (ETS/ARIMA/Theta) are not evaluated because the corresponding packages were not installed and installing them was not authorised.

*Selection.* For each endpoint the candidate with the lowest mean validation WAPE of that endpoint (item-day or subset-day) over the three validation blocks is selected, ties by name; selection is written to disk before any test block is fitted. Test fits are made only for the two selected models and the reference model (seeds 43 and 44 additionally for the item-day model on W2).

*Baselines (31).* Sixteen estimators — naive, seasonal naive, weekday mean and median (4 and 8 weeks), trailing mean (28, 91 days), trailing median (14, 28, 56, 91), Croston [Croston, 1972], Croston-SBA [Syntetos & Boylan, 2005], TSB [Teunter et al., 2011] and an all-zero forecast — each with **matched** information (history up to t − H, exactly the models' information) and **fresh** information (re-estimated at the start of each block or week; 1 to H days old). Baselines are not tuned beyond the choice among these prespecified variants; the best is selected on validation data for the same endpoint.

## 7. Endpoints and statistical analysis

*Endpoints.* Primary: pooled **item-day WAPE** = Σ|ŷ − y| / Σy over eligible (series, day) rows. Aggregate: **subset-day WAPE** = Σ_d |Σ_s (ŷ − y)| / Σ_d Σ_s y (demand of the selected subset summed per day before scoring; not a store total). Descriptive: item-week and subset-week WAPE, relative bias, MAE, RMSE, share of zero forecasts. Subset-day WAPE is at least |relative bias|. The estimand is the relative improvement (E_ref − E_model)/E_ref pooled over the six test blocks; the minimum relevant improvement is 2 %.

*Hypotheses.* H1 (primary): the item-day-selected model beats the best matched baseline on item-day WAPE. H1b: the same against the best baseline of any information set. H2: the same model beats the v1 reference model (Tweedie 1.1, refit on the same window). H3: the subset-day-selected model beats the best matched baseline on subset-day WAPE. H4 (descriptive): endpoint dependence.

*Inference.* Item-day endpoints: paired crossed bootstrap over series and 7-day blocks (B = 10,000; primary) and a two-way cluster-robust delta-method interval with a t(G − 1) reference [Cameron et al., 2011] (secondary); the crossed bootstrap is the pigeonhole bootstrap of Owen [2007] and Owen & Eckles [2012]. Aggregate endpoint: bootstrap over 7-day blocks of daily totals (iid weeks primary; stationary block bootstrap [Politis & Romano, 1994] secondary; Diebold–Mariano-type tests [Diebold & Mariano, 1995] are an alternative that was not used). The primary methods were fixed by a pre-freeze simulation (worst-case coverage error 0.050 for the crossed bootstrap, 0.057 for the iid-week bootstrap; both mildly liberal; the v1 series-only design collapses). Holm correction within each family across the eight W2 cells. **Decision per cell:** supported iff Holm p < 0.05, the interval excludes 0, improvement ≥ 2 % and the model wins ≥ 4 of 6 blocks; contradicted iff the interval lies below 0; otherwise inconclusive. **Dual-method rule:** a verdict stands only if the secondary method gives the same verdict; otherwise it is inconclusive. Replication sets are analysed descriptively with their own Holm adjustment and are not pooled with the confirmatory family.

## 8. Results

Every table in this section is generated from the stored analysis files by `tools/build_tables.py` (source files are named under each table); figures are generated by `report.py`. Improvements are relative reductions in WAPE pooled over the six test blocks, (E_ref − E_model)/E_ref. Intervals are 95 % percentile intervals from the crossed bootstrap (item-day) or the iid-week bootstrap (subset-day). "Holm p" is adjusted within the eight confirmatory cells of the window. **Labels used throughout:** *confirmatory* = window W2 with the frozen rules; *replication* = W3, and W1 for the fresh store WI_1; *non-independent re-evaluation* = W1 for CA_1, TX_1 and Online Retail II; *descriptive* = prespecified summaries without a test; *exploratory* = post-hoc or uncontrolled for multiplicity; *supplementary* = post-hoc calculations added after the results were known, which do not replace any frozen result.

### 8.1 Design as executed

**Table 1. Windows and samples** (validation + test spans from `DATA_AUDIT.md`; rows = series × 168 test days).

| window | role | datasets | validation + test span | series per dataset | rows per cell |
|---|---|---|---|---|---|
| W2 | **confirmatory** | M5 CA_1, TX_1, WI_1; Online Retail II | M5: 2015-01-05 → 2015-09-13; Online Retail II: 2010-07-24 → 2011-04-01 | 350 / 350 / 349 / 100 | 58,800 / 58,800 / 58,632 / 16,800 |
| W3 | replication (independent window) | M5 CA_1, TX_1, WI_1 (not feasible for Online Retail II) | 2014-04-28 → 2015-01-04 | 350 / 350 / 349 | as W2 |
| W1 | replication for WI_1 (fresh store); non-independent re-evaluation for CA_1, TX_1, Online Retail II | all four | M5: 2015-09-14 → 2016-05-22; Online Retail II: 2011-04-02 → 2011-12-09 | as W2 | as W2 |

Each cell is a dataset × horizon (H = 28 or 7); W2 and W1 have eight cells, W3 six. Zero shares among test rows were 0.53–0.65 for M5 and 0.32–0.40 for Online Retail II (`DATA_AUDIT.md`).

### 8.2 Model selection on validation data

For the item-day endpoint the absolute-error LightGBM was selected in all eight W2 cells (31-leaf configuration on M5, the 15-leaf / minimum-child-100 configuration on Online Retail II). For the subset-day endpoint the Tweedie (p = 1.1) model was selected in six W2 cells and the squared-error model in the two WI_1 cells; the absolute-error and quantile models were never selected for the aggregate endpoint in any window. In W1 the 0.5-quantile model replaced the absolute-error model in two cells (CA_1 H28, TX_1 H7). The best validation baseline for item-day was a trailing or weekday median (trailing 14–91 days; weekday median of 8 weeks on Online Retail II); for subset-day it was a weekday mean (4 or 8 weeks). No cell selected the all-zero forecast.

### 8.3 Confirmatory results (window W2)

**Table 2. Item-day endpoint, window W2 (confirmatory): item-day-selected model (absolute-error LightGBM in all cells) versus the best matched baseline**

| cell | best matched baseline | WAPE baseline / model | improvement [95 % CI] | Holm p | blocks won | H1 | H1b: vs best any-information baseline | H2: vs original Tweedie 1.1 model |
|---|---|---|---|---|---|---|---|---|
| CA_1 H28 | trailing median 56 | 0.775 / 0.739 | +4.6 % [+2.3, +7.1] | 0.0016 | 6/6 | supported | inconclusive (−1.4 %) | supported (+8.2 %) |
| CA_1 H7 | trailing median 14 | 0.714 / 0.686 | +4.0 % [+2.3, +6.0] | 0.0016 | 6/6 | supported | supported (+2.5 %) | supported (+8.0 %) |
| TX_1 H28 | trailing median 56 | 0.774 / 0.755 | +2.5 % [+1.0, +4.1] | 0.0036 | 6/6 | supported | inconclusive (+0.8 %) | supported (+10.5 %) |
| TX_1 H7 | trailing median 91 | 0.752 / 0.718 | +4.5 % [+2.5, +6.8] | 0.0016 | 6/6 | supported | supported (+3.8 %) | supported (+10.8 %) |
| WI_1 H28 | trailing median 56 | 0.783 / 0.757 | +3.3 % [+1.6, +5.3] | 0.0018 | 6/6 | supported | inconclusive (+0.9 %) | supported (+7.9 %) |
| WI_1 H7 | trailing median 91 | 0.753 / 0.708 | +6.0 % [+3.4, +9.0] | 0.0016 | 6/6 | supported | supported (+3.2 %) | supported (+8.2 %) |
| Online Retail II H28 | weekday median 8 | 0.931 / 0.877 | +5.8 % [+2.7, +9.5] | 0.0016 | 6/6 | supported | inconclusive (+2.2 %) | supported (+16.7 %) |
| Online Retail II H7 | weekday median 8 | 0.871 / 0.836 | +4.0 % [+1.5, +7.0] | 0.0036 | 5/6 | supported | supported (+4.0 %) | supported (+16.8 %) |

*Source: `results/analysis/analysis_W2.json` (H1, H1b, H2); CSV: `tables/table2_h1_W2.csv`.*

H1 (item-day, model vs best matched baseline) is supported in 8 of 8 cells under the frozen rule (Holm p < 0.05, interval excluding zero, improvement ≥ 2 %, ≥ 4 of 6 blocks won, and the same verdict from the secondary method). The median improvement is +4.3 % (range +2.5 % … +6.0 %); the model won all six blocks in seven cells and five of six in Online Retail II H7. The lowest Holm p-values equal the resolution of the bootstrap (B = 10,000) and are bounds, not exact values. The smallest effect (TX_1 H28, +2.5 %) is close to the 2 % threshold. H2 (objective effect): the item-day-selected model improves on the original Tweedie 1.1 model in 8 of 8 cells (+7.9 % … +16.8 %). H1b — against baselines that are re-estimated at block starts and therefore see up to 28 days more data than the model — is supported in the four H = 7 cells and inconclusive in the four H = 28 cells (point estimates −1.4 % … +2.2 %); **the statement "the learned model beats the best simple baseline" is therefore established for baselines with the same information as the model, not for baselines with fresher information at H = 28.**

**Table 3. Subset-day endpoint, window W2 (confirmatory): subset-day-selected model versus the best matched baseline**

| cell | model | best matched baseline | WAPE baseline / model | improvement [95 % CI] | frozen Holm p primary / secondary | blocks won | verdict (frozen rule) | supplementary converged Holm p primary / secondary |
|---|---|---|---|---|---|---|---|---|
| CA_1 H28 | Tweedie 1.1 | weekday mean 4 | 0.114 / 0.088 | +22.7 % [+14.6, +30.6] | 0.002 / 0.002 | 6/6 | supported | <0.001 / <0.001 |
| CA_1 H7 | Tweedie 1.1 | weekday mean 8 | 0.104 / 0.084 | +18.7 % [+9.5, +28.5] | 0.002 / 0.002 | 6/6 | supported | <0.001 / <0.001 |
| TX_1 H28 | Tweedie 1.1 | weekday mean 8 | 0.117 / 0.099 | +14.8 % [+2.5, +26.7] | 0.071 / 0.048 | 4/6 | inconclusive | 0.051 / 0.043 |
| TX_1 H7 | Tweedie 1.1 | weekday mean 4 | 0.123 / 0.094 | +23.8 % [+13.9, +33.1] | 0.002 / 0.002 | 6/6 | supported | <0.001 / <0.001 |
| WI_1 H28 | squared error | weekday mean 8 | 0.100 / 0.092 | +7.8 % [−0.5, +15.7] | 0.205 / 0.269 | 5/6 | inconclusive | 0.215 / 0.259 |
| WI_1 H7 | squared error | weekday mean 8 | 0.099 / 0.087 | +11.4 % [+3.6, +18.3] | 0.035 / 0.002 | 6/6 | supported | 0.029 / 0.001 |
| Online Retail II H28 | Tweedie 1.1 | weekday mean 8 | 0.511 / 0.482 | +5.8 % [−5.5, +16.2] | 0.582 / 0.405 | 4/6 | inconclusive | 0.596 / 0.403 |
| Online Retail II H7 | Tweedie 1.1 | weekday mean 8 | 0.456 / 0.458 | −0.5 % [−13.3, +8.4] | 0.939 / 0.934 | 2/6 | inconclusive | 0.938 / 0.927 |

*Source: `results/analysis/analysis_W2.json` (H3); `results/supplementary/h3_convergence.json`; CSV: `tables/table3_h3_W2.csv`.*

H3 (subset-day, model vs best matched baseline) is supported in 4 of 8 cells and inconclusive in 4; no cell is contradicted. Point estimates are positive in 7 of 8 cells (median +13.1 %; Online Retail II H7 −0.5 %). The intervals are wide because the aggregate endpoint has only 24 weekly blocks. TX_1 H28 is a boundary case examined in Section 8.5; its frozen verdict (inconclusive) is confirmed.

### 8.4 Replication windows

**Table 4. Verdict counts (supported / contradicted / inconclusive) by window; each window has its own Holm adjustment**

| window | cells | H1 s/c/i | H1b s/c/i | H2 s/c/i | H3 s/c/i | median H1 improvement (range) | H1 improvement > 0 |
|---|---|---|---|---|---|---|---|
| W2 (confirmatory) | 8 | 8/0/0 | 4/0/4 | 8/0/0 | 4/0/4 | +4.3 % (+2.5 % … +6.0 %) | 8/8 |
| W3 (M5, independent replication) | 6 | 6/0/0 | 3/0/3 | 6/0/0 | 4/0/2 | +4.5 % (+2.2 % … +6.2 %) | 6/6 |
| W1 (WI_1 fresh store; CA_1, TX_1, Online Retail II non-independent) | 8 | 6/0/2 | 3/0/5 | 8/0/0 | 4/0/4 | +3.2 % (+1.1 % … +4.5 %) | 8/8 |

*Source: `results/summary_extra.json` (from `analysis_*.json`); CSV: `tables/table4_replication.csv`.*

The H1 improvement is positive in all 22 cells of the three windows (supported in 20). In W3 it is supported in all six cells. In W1 two cells are inconclusive: TX_1 H28 (+1.1 %, 3/6 blocks won, interval includes zero) and TX_1 H7 (+1.9 %, below the 2 % threshold although the interval excludes zero); the two WI_1 cells of W1 (the fresh store) are supported. H3 is supported in 4 of 6 cells in W3 and in 4 of 8 in W1. Per-cell results are in Table A1 (Appendix) and Figure 1. W1 results for CA_1, TX_1 and Online Retail II are not independent evidence (Section 5).

![Figure 1. Relative improvement in WAPE with 95 % intervals (crossed bootstrap for H1 and H2, iid-week bootstrap for H3), by window (blue W2 confirmatory, orange W3 replication, grey W1; only WI_1 is a fresh replication in W1). Dotted line: 2 % minimum improvement. Source: `results/analysis/analysis_*.json`, generated by `report.py`.](figures/fig1_forest.png)

*Figure 1. Relative improvement in WAPE with 95 % intervals (crossed bootstrap for H1 and H2, iid-week bootstrap for H3), by window (blue W2 confirmatory, orange W3 replication, grey W1; only WI_1 is a fresh replication in W1). Dotted line: 2 % minimum improvement. Source: `results/analysis/analysis_*.json`, generated by `report.py`.*

### 8.5 Supplementary precision check of the boundary cell (TX_1, H = 28, subset-day)

The separate re-implementation (a second code path, B = 4,000) classified this cell as supported whereas the frozen analysis (B = 10,000, fixed seed) classified it as inconclusive because the two prespecified methods disagreed. **This section is supplementary: it was added after the results were known, uses the same two prespecified methods and the unchanged decision rule, and does not replace the frozen result.**

**Table 6. W2, TX_1, H = 28, subset-day (H3): frozen result and supplementary convergence check**

| quantity | frozen run (B = 10,000) | supplementary (3 × 10^6 draws) |
|---|---|---|
| raw p, primary (iid-week bootstrap) | 0.0178 | 0.0129 (seed SD 0.0002) |
| raw p, secondary (stationary bootstrap) | 0.0120 | 0.0108 (seed SD 0.0000) |
| Holm p, primary | 0.0712 | 0.0514 |
| Holm p, secondary | 0.0480 | 0.0433 |
| verdict under the frozen dual-method rule | inconclusive | inconclusive |
| exact sign-flip test (unadjusted p; different statistic) | – | 0.0339 |
| weeks in which the model has the smaller absolute total error | – | 15/24 |
| lag-1 autocorrelation of the weekly differences / AR(1) effective weeks | – | +0.36 / 11.3 |

*Source: `results/analysis/analysis_W2.json`; `results/supplementary/h3_convergence.json`; CSV: `tables/table6_tx1_h28_h3.csv`.*

With 3 × 10^6 draws per method (three new seeds) Monte-Carlo error is negligible (seed SD ≤ 0.0002). The primary method's Holm p is 0.0514 and the secondary method's 0.0433: the methods still disagree and the frozen rule gives *inconclusive*. The frozen verdict is confirmed, and the second code path's *supported* was Monte-Carlo noise at B = 4,000. All 22 H3 verdicts of the three windows are unchanged under the converged calculation (`SUPPLEMENTARY_H3_RESOLUTION.md`). The weekly differences in this cell are positively autocorrelated (lag-1 +0.36; AR(1) effective sample ≈ 11 of 24 weeks), which the iid-week bootstrap ignores; the cell is best described as suggestive, not established.

### 8.6 Seed sensitivity (W2, descriptive)

Refitting the item-day model with seeds 43 and 44 changes the H1 improvement by at most 0.4 percentage points (per cell 0.09–0.40 pp; Table A2); the lowest of the three seeds is ≥ 2.3 % in every cell. Seed variation is not included in the intervals.

### 8.7 Aggregation and bias (descriptive, prespecified H4)

**Table 5. Aggregation ladder and bias, window W2, all cells**

| cell | method | item-day WAPE | item-week WAPE | subset-week WAPE | subset-day WAPE | relative bias | share of zero forecasts |
|---|---|---|---|---|---|---|---|
| CA_1 H28 | absolute-error model (item-day winner) | 0.739 | 0.518 | 0.346 | 0.346 | −0.346 | 0.29 |
| CA_1 H28 | best item-day baseline | 0.775 | 0.560 | 0.293 | 0.295 | −0.293 | 0.57 |
| CA_1 H28 | Tweedie 1.1 model (subset-day winner) | 0.806 | 0.441 | 0.046 | 0.088 | +0.001 | 0.00 |
| CA_1 H28 | best subset-day baseline | 0.849 | 0.454 | 0.074 | 0.114 | −0.007 | 0.24 |
| CA_1 H7 | absolute-error model (item-day winner) | 0.686 | 0.429 | 0.287 | 0.287 | −0.287 | 0.29 |
| CA_1 H7 | best item-day baseline | 0.714 | 0.448 | 0.232 | 0.242 | −0.232 | 0.53 |
| CA_1 H7 | Tweedie 1.1 model (subset-day winner) | 0.745 | 0.368 | 0.045 | 0.084 | −0.004 | 0.00 |
| CA_1 H7 | best subset-day baseline | 0.792 | 0.405 | 0.068 | 0.104 | −0.006 | 0.13 |
| TX_1 H28 | absolute-error model (item-day winner) | 0.755 | 0.558 | 0.394 | 0.394 | −0.394 | 0.49 |
| TX_1 H28 | best item-day baseline | 0.774 | 0.573 | 0.330 | 0.332 | −0.330 | 0.68 |
| TX_1 H28 | Tweedie 1.1 model (subset-day winner) | 0.843 | 0.464 | 0.060 | 0.099 | −0.021 | 0.00 |
| TX_1 H28 | best subset-day baseline | 0.881 | 0.490 | 0.074 | 0.117 | +0.010 | 0.19 |
| TX_1 H7 | absolute-error model (item-day winner) | 0.718 | 0.487 | 0.360 | 0.360 | −0.360 | 0.48 |
| TX_1 H7 | best item-day baseline | 0.752 | 0.552 | 0.346 | 0.347 | −0.346 | 0.70 |
| TX_1 H7 | Tweedie 1.1 model (subset-day winner) | 0.805 | 0.406 | 0.054 | 0.094 | −0.019 | 0.00 |
| TX_1 H7 | best subset-day baseline | 0.862 | 0.428 | 0.071 | 0.123 | +0.005 | 0.32 |
| WI_1 H28 | absolute-error model (item-day winner) | 0.757 | 0.505 | 0.331 | 0.331 | −0.331 | 0.35 |
| WI_1 H28 | best item-day baseline | 0.783 | 0.534 | 0.289 | 0.290 | −0.289 | 0.59 |
| WI_1 H28 | squared error model (subset-day winner) | 0.831 | 0.433 | 0.047 | 0.092 | +0.020 | 0.00 |
| WI_1 H28 | best subset-day baseline | 0.855 | 0.450 | 0.052 | 0.100 | +0.003 | 0.17 |
| WI_1 H7 | absolute-error model (item-day winner) | 0.708 | 0.427 | 0.307 | 0.307 | −0.307 | 0.38 |
| WI_1 H7 | best item-day baseline | 0.753 | 0.502 | 0.298 | 0.298 | −0.298 | 0.60 |
| WI_1 H7 | squared error model (subset-day winner) | 0.784 | 0.370 | 0.043 | 0.087 | +0.005 | 0.00 |
| WI_1 H7 | best subset-day baseline | 0.822 | 0.400 | 0.045 | 0.099 | +0.000 | 0.17 |
| Online Retail II H28 | absolute-error model (item-day winner) | 0.877 | 0.662 | 0.515 | 0.573 | −0.384 | 0.07 |
| Online Retail II H28 | best item-day baseline | 0.931 | 0.691 | 0.500 | 0.572 | −0.329 | 0.29 |
| Online Retail II H28 | Tweedie 1.1 model (subset-day winner) | 1.053 | 0.706 | 0.312 | 0.482 | +0.085 | 0.00 |
| Online Retail II H28 | best subset-day baseline | 1.135 | 0.765 | 0.402 | 0.511 | +0.115 | 0.20 |
| Online Retail II H7 | absolute-error model (item-day winner) | 0.836 | 0.606 | 0.490 | 0.534 | −0.390 | 0.03 |
| Online Retail II H7 | best item-day baseline | 0.871 | 0.618 | 0.483 | 0.541 | −0.361 | 0.29 |
| Online Retail II H7 | Tweedie 1.1 model (subset-day winner) | 1.005 | 0.649 | 0.305 | 0.458 | +0.059 | 0.00 |
| Online Retail II H7 | best subset-day baseline | 1.057 | 0.665 | 0.292 | 0.456 | +0.068 | 0.20 |

*Source: `results/analysis/analysis_W2.json` (`ladder`); CSV: `tables/table5_ladder_W2.csv`.*

The model that wins the item-day endpoint is strongly downward-biased (relative bias −0.29 … −0.39 on M5; it forecasts zero for 29–49 % of M5 rows against 53–70 % for the best item-day baseline). Because subset-day WAPE is at least the absolute relative bias (with equality for this model on M5), the same model loses to simple baselines on the aggregate endpoint (for example CA_1 H28: 0.346 against 0.114 for the best subset-day baseline), and the models selected for the two endpoints differ in all eight cells. The original reference model (Tweedie 1.1) has bias near zero and loses to the best baseline on the item-day endpoint (CA_1 H28: 0.806 against 0.775).

![Figure 2. Aggregation ladder, window W2: WAPE of the item-day-selected model and of the best matched item-day baseline at four aggregation levels. Source: `results/analysis/analysis_W2.json` (`ladder`); Table 5 gives all values including the subset-day-selected models.](figures/fig2_aggregation_ladder_W2.png)

*Figure 2. Aggregation ladder, window W2: WAPE of the item-day-selected model and of the best matched item-day baseline at four aggregation levels. Source: `results/analysis/analysis_W2.json` (`ladder`); Table 5 gives all values including the subset-day-selected models.*

![Figure 3. Item-day improvement (H1) against subset-day improvement (H3) per cell and window. These are different models: the item-day and subset-day winners are selected separately. Source: `results/analysis/analysis_*.json`.](figures/fig3_endpoint_dependence.png)

*Figure 3. Item-day improvement (H1) against subset-day improvement (H3) per cell and window. These are different models: the item-day and subset-day winners are selected separately. Source: `results/analysis/analysis_*.json`.*

### 8.8 Exploratory results

Gains of the item-day model are concentrated in frequently selling and high-volume series (Table A3, W2; for example CA_1 H28: frequent series +8.1 % [+3.5, +12.7], n = 46; intermittent or sparse +2.5 % [+0.5, +4.7], n = 304; low and mid volume terciles with intervals that include zero). These segment intervals (B = 2,000) are not corrected for multiplicity and are descriptive. The design effect of the crossed series × week structure on the standard error is 1.5–2.5 (Table A4).

## 9. Discussion

**What the study adds.** The negative v1 result was largely an objective–metric mismatch plus baseline-level bias, not evidence that boosted models cannot beat simple baselines: when an absolute-error objective is in the candidate set and selection is made on the same endpoint, the learned model beats the best same-information baseline on the item-day endpoint by a modest 2.5–6.0 % in every confirmatory cell and in the replication windows, while Tweedie / squared-error models win the aggregate endpoint by larger margins that are less certain (supported in 4 of 8 W2 cells). Both findings follow from scoring-function theory [Gneiting, 2011; Kolassa, 2020]; the contribution is their quantification under a frozen protocol with dependence-aware intervals on public retail data, and the demonstration that the answer to "does the learned model beat a simple baseline?" can flip with the endpoint.

**What the study does not show.** (i) That the item-day gain is useful: it comes from a model that forecasts zero more often and has large negative bias; whether that is desirable depends on a decision loss that was not evaluated. (ii) That learned models beat baselines with fresher information at H = 28 (H1b). (iii) That any model is best: the candidate set is small (eight configurations from LightGBM, XGBoost and ridge regression), tuning is limited, and statistical models (ETS, ARIMA, Theta), neural networks and probabilistic forecasts were not evaluated; Section 10 and `PROPOSAL_STATISTICAL_BASELINES.md` explain why this matters and how it could be addressed on a fresh window. (iv) Generality beyond three stores of one retailer and one UK wholesaler. (v) Causal explanations: the interpretation in terms of bias and zero forecasts rests on a descriptive decomposition, not an intervention.

**Relationship to the literature.** Tree-based models were prevalent among top M5 methods and outperformed other approaches there [Makridakis et al., 2022; Januschowski et al., 2022]; the M5 report also finds the top-performing methods clearly better than its statistical benchmarks on its own (hierarchical) metric. The inconsistency of conventional measures on intermittent demand is documented [Prestwich et al., 2014; Hyndman & Koehler, 2006]. The present results are consistent with both and add effect sizes for a matched-information comparison against a large baseline set, with no claim that M5-style evaluation (recursive, hierarchical, with price and calendar covariates and a weighted scaled metric) is reproduced.

**Practical reading (cautious).** The endpoint should be chosen before models are compared and should reflect the decision. If the decision depends on totals (for example weekly store volume), a mean-type objective and an aggregate metric are appropriate; if item-day accuracy in the absolute-error sense is wanted, a median-type objective helps, with the bias that implies. No cost, service-level or profit analysis was done.

## 10. Limitations and threats to validity

* **Internal freeze, not public pre-registration.** The protocol was hashed before any W2/W3/WI_1 outcome was read, but the hash is not externally timestamped and the design was set with knowledge of the v1 results and an internal audit of them.
* **Window exposure.** W2 and W3 targets of the evaluated entities were not scored before; their calendar *periods* were used as training data and in a retired benchmark on other M5 series (documented). W1 for CA_1, TX_1 and Online Retail II is non-independent. Online Retail II has no W3 and a short W2 history (487 days).
* **Baselines and models.** 31 prespecified simple baselines and eight model configurations with shared hyper-parameters. **ETS, ARIMA, Theta, global neural models and probabilistic or quantile-loss evaluations are absent**; statistical-model packages were not installed and installing them was not authorised. Readers who consider these necessary for the claim "beats the best simple baseline" should treat the present result as limited to the stated baseline set; a separate, fresh-window proposal exists but was not run.
* **Sampling.** 350/349 department-stratified series per M5 store (series launched after d_1100 excluded) and the 100 largest-revenue Online Retail II SKUs; results describe these samples. The eligibility rule (days with a listed price) is an assumption about what a forecaster knows.
* **Dependence and inference.** Intervals are percentile or t-based and mildly liberal in simulation (worst-case coverage ≈ 0.90–0.95 at nominal 0.95); the aggregate endpoint has 24 weekly blocks; the iid-week bootstrap ignores weekly autocorrelation (visible in TX_1 H28); model errors across blocks are correlated through overlapping training windows (not modelled); one seed per primary model, seed variation reported separately.
* **Metric choice.** WAPE and its aggregate version are the prespecified endpoints; scaled, probabilistic, cost-based or service-level criteria were not evaluated. Item-day WAPE rewards forecasts near the conditional median on sparse series.
* **Dual-method rule.** It converts method disagreement into *inconclusive*, which is conservative for H3 (one W2 cell, two W3 cells); the supplementary check shows the verdict counts do not change when Monte-Carlo error is removed.
* **Same-agent development and verification.** The study code, the verification code, the supplementary analysis and this manuscript were produced by one AI assistant under the author's direction. The verification is an internal consistency and re-implementation check, not independent external validation (Section 11).
* **Data rights.** M5 data and any array containing M5 sales are not released.

## 11. Verification

Unit tests (17) cover leak-freedom of all 16 baseline estimators under both information sets, metric identities, objective semantics, window arithmetic, the Online Retail II SKU list and the inference helpers; they pass in the project environment and in a fresh environment with identical pinned versions. A second code path (`verify_independent.py`), which imports nothing from the study, recomputed targets from the raw files, all 31 baselines row by row, metrics, improvements, bootstrap and cluster-robust intervals (own implementation, B = 4,000), Holm adjustments and verdicts, the validation-only selection and the ordering of selection before test fits: 98/98 checks passed in W2, 72/72 in W3 and 98/98 in W1; the frozen files were unchanged and point estimates were identical in 88 of 88 comparisons. Of the 88 verdict comparisons 87 agree; the exception (W2 TX_1 H28, H3) is resolved in Section 8.5. One complete cell (Online Retail II, W2, H = 7) was re-run from scratch in a fresh environment with identical pinned versions and reproduced all 35 stored method summaries exactly (maximum absolute difference 0); the other 21 cells were not re-run. The same AI assistant designed and ran all of this; **it is not external validation**. A human reviewer should in particular check the data-licence reading, the reference list against original sources, the interpretation of the boundary cell, and, ideally, replicate the pipeline independently.

## 12. Conclusions

In the confirmatory window, an absolute-error LightGBM selected on validation item-day WAPE beat the best simple baseline with the same information in all eight dataset–horizon cells (median +4.3 %, range +2.5 … +6.0 %); the improvement was positive in all 22 cells of three windows (supported in 20) and the model beat the earlier Tweedie reference in every cell. Against baselines with fresher information at H = 28 the advantage is not established, and statistical, neural and probabilistic competitors were not evaluated. On the aggregate endpoint a different, mean-type model is selected; the item-day winner loses to simple baselines because of its level bias, and the improvement of the aggregate-selected model over the best baseline is supported in four of eight confirmatory cells (positive in seven), with the TX_1 H28 cell a documented boundary case. The take-home message is endpoint-matching: the same data and models give opposite answers depending on the metric, so a claim that a model beats a baseline is meaningful only relative to the endpoint, the information set, the baseline set and the baseline's level bias.

## 13. Reproducibility, data and code availability

Code, frozen protocol, configuration, result tables and figures are in `research/forecast_study_v2/` (commands in `REPRODUCIBILITY.md`). Raw M5 data must be obtained from Kaggle under the competition rules (account and acceptance of the rules required); Online Retail II is available from the UCI repository (CC BY 4.0, doi:10.24432/C5CG6D). Stored per-row predictions contain M5 sales and are not released; aggregate tables, figures, code, configuration and hashes can be shared. One cell was reproduced exactly in a fresh environment; a full clean-room reproduction has not been performed (`FINAL_VERIFICATION_REPORT.md`).

## 14. Declarations (to be completed by the authors)

* **Author names, affiliations, contributions:** [AUTHORS TO COMPLETE]
* **Funding:** [AUTHORS TO COMPLETE]
* **Competing interests:** [AUTHORS TO COMPLETE]
* **Ethics:** the study uses public, secondary, non-interventional data; Online Retail II contains pseudonymous customer identifiers but no customer-level data were analysed. [AUTHORS TO CONFIRM and, if required, obtain institutional confirmation]
* **Use of generative AI:** [AUTHORS TO COMPLETE.] Factual note for the authors: the experimental code, analysis and verification code, the supplementary analysis and the drafting of this manuscript were produced with an AI model (Anthropic Claude, via Claude Code) under the author's direction; the authors must review all content, take responsibility for it and comply with the venue's AI-use policy.
* **Data availability:** as in Section 13; M5 data cannot be redistributed.
* **Pre-registration:** none (internal timestamped freeze only).

## Appendix A. Supplementary tables

**Table A1. Replication windows W3 and W1: item-day (H1) and subset-day (H3) results**

| window | cell | item-day model | best matched baseline | WAPE baseline / model | H1 improvement [95 % CI] | Holm p | blocks won | H1 | H3 (improvement) |
|---|---|---|---|---|---|---|---|---|---|
| W3 | CA_1 H28 | absolute error | trailing median 91 | 0.771 / 0.732 | +5.0 % [+2.9, +7.5] | 0.0012 | 6/6 | supported | supported (+21.1 %) |
| W3 | CA_1 H7 | absolute error | trailing median 14 | 0.734 / 0.689 | +6.2 % [+4.5, +8.0] | 0.0012 | 6/6 | supported | inconclusive (+16.0 %) |
| W3 | TX_1 H28 | absolute error | trailing median 91 | 0.793 / 0.776 | +2.2 % [+0.2, +4.1] | 0.0284 | 5/6 | supported | supported (+18.0 %) |
| W3 | TX_1 H7 | absolute error | trailing median 28 | 0.758 / 0.726 | +4.1 % [+2.4, +6.0] | 0.0012 | 6/6 | supported | supported (+19.1 %) |
| W3 | WI_1 H28 | absolute error | trailing median 56 | 0.800 / 0.764 | +4.5 % [+2.7, +6.2] | 0.0012 | 6/6 | supported | supported (+13.5 %) |
| W3 | WI_1 H7 | absolute error | trailing median 28 | 0.751 / 0.717 | +4.5 % [+3.1, +6.0] | 0.0012 | 6/6 | supported | inconclusive (+11.7 %) |
| W1 | CA_1 H28 | 0.5 quantile | trailing median 28 | 0.724 / 0.708 | +2.3 % [+0.7, +3.9] | 0.0152 | 6/6 | supported | inconclusive (+12.2 %) |
| W1 | CA_1 H7 | absolute error | trailing median 14 | 0.691 / 0.661 | +4.3 % [+2.9, +5.8] | 0.0016 | 6/6 | supported | supported (+18.4 %) |
| W1 | TX_1 H28 | absolute error | trailing median 56 | 0.752 / 0.743 | +1.1 % [−1.0, +3.2] | 0.2848 | 3/6 | inconclusive | inconclusive (+8.3 %) |
| W1 | TX_1 H7 | 0.5 quantile | trailing median 28 | 0.710 / 0.697 | +1.9 % [+0.6, +3.3] | 0.0138 | 6/6 | inconclusive | inconclusive (+12.7 %) |
| W1 | WI_1 H28 | absolute error | trailing median 56 | 0.753 / 0.725 | +3.8 % [+2.3, +5.4] | 0.0016 | 6/6 | supported | supported (+13.5 %) |
| W1 | WI_1 H7 | absolute error | trailing median 28 | 0.724 / 0.691 | +4.5 % [+2.9, +6.2] | 0.0016 | 6/6 | supported | supported (+16.4 %) |
| W1 | Online Retail II H28 | absolute error (small) | weekday median 8 | 0.817 / 0.790 | +3.3 % [+1.7, +5.1] | 0.0016 | 6/6 | supported | supported (+12.0 %) |
| W1 | Online Retail II H7 | absolute error | weekday median 8 | 0.787 / 0.763 | +3.1 % [+1.3, +5.0] | 0.0056 | 6/6 | supported | inconclusive (+4.9 %) |

*Source: `results/analysis/analysis_W3.json`, `analysis_W1.json`; CSV: `tables/tableA1_replication_H1.csv`.*

**Table A2. Seed sensitivity of the W2 item-day improvement (H1)**

| cell | seed 42 (frozen primary) | seed 43 | seed 44 | range |
|---|---|---|---|---|
| CA_1 H28 | +4.58 % | +4.38 % | +4.57 % | 0.20 pp |
| CA_1 H7 | +3.95 % | +4.25 % | +4.20 % | 0.30 pp |
| TX_1 H28 | +2.53 % | +2.37 % | +2.30 % | 0.23 pp |
| TX_1 H7 | +4.54 % | +4.53 % | +4.41 % | 0.12 pp |
| WI_1 H28 | +3.33 % | +3.53 % | +3.73 % | 0.40 pp |
| WI_1 H7 | +6.02 % | +6.07 % | +6.11 % | 0.09 pp |
| Online Retail II H28 | +5.81 % | +5.62 % | +5.95 % | 0.33 pp |
| Online Retail II H7 | +4.02 % | +4.17 % | +3.81 % | 0.37 pp |

*Source: `results/analysis/analysis_W2.json` (`seed_sensitivity`); CSV: `tables/tableA2_seeds.csv`.*

**Table A3 (exploratory). Segment results, window W2**

| cell | segment | series | item-day improvement vs matched baseline [95 % CI] |
|---|---|---|---|
| CA_1 H28 | frequency=frequent | 46 | +8.1 % [+3.5, +12.7] |
| CA_1 H28 | frequency=intermittent_or_sparse | 304 | +2.5 % [+0.5, +4.7] |
| CA_1 H28 | volume=high | 117 | +6.3 % [+3.1, +9.7] |
| CA_1 H28 | volume=low | 117 | +1.5 % [−0.7, +4.0] |
| CA_1 H28 | volume=mid | 116 | +1.0 % [−1.1, +3.2] |
| CA_1 H7 | frequency=frequent | 46 | +6.5 % [+2.9, +11.1] |
| CA_1 H7 | frequency=intermittent_or_sparse | 304 | +2.6 % [+1.3, +3.9] |
| CA_1 H7 | volume=high | 117 | +5.0 % [+2.7, +7.8] |
| CA_1 H7 | volume=low | 117 | +2.9 % [+1.2, +4.8] |
| CA_1 H7 | volume=mid | 116 | +1.7 % [+0.2, +3.1] |
| TX_1 H28 | frequency=frequent | 33 | +4.4 % [+0.7, +8.4] |
| TX_1 H28 | frequency=intermittent_or_sparse | 317 | +1.8 % [+0.3, +3.3] |
| TX_1 H28 | volume=high | 117 | +2.6 % [+0.6, +4.8] |
| TX_1 H28 | volume=low | 117 | +0.9 % [−1.1, +3.1] |
| TX_1 H28 | volume=mid | 116 | +2.9 % [+1.2, +4.9] |
| TX_1 H7 | frequency=frequent | 33 | +6.9 % [+1.9, +12.4] |
| TX_1 H7 | frequency=intermittent_or_sparse | 317 | +3.7 % [+1.7, +5.9] |
| TX_1 H7 | volume=high | 117 | +5.8 % [+3.2, +8.8] |
| TX_1 H7 | volume=low | 117 | +0.7 % [−1.7, +3.2] |
| TX_1 H7 | volume=mid | 116 | +2.0 % [+0.0, +4.2] |
| WI_1 H28 | frequency=frequent | 41 | +4.9 % [+0.4, +10.1] |
| WI_1 H28 | frequency=intermittent_or_sparse | 308 | +2.6 % [+1.0, +4.3] |
| WI_1 H28 | volume=high | 116 | +4.4 % [+2.0, +7.1] |
| WI_1 H28 | volume=low | 117 | +0.5 % [−1.5, +2.8] |
| WI_1 H28 | volume=mid | 116 | +1.3 % [−0.9, +3.6] |
| WI_1 H7 | frequency=frequent | 41 | +9.7 % [+3.2, +18.0] |
| WI_1 H7 | frequency=intermittent_or_sparse | 308 | +4.4 % [+2.4, +6.6] |
| WI_1 H7 | volume=high | 116 | +8.5 % [+4.8, +12.5] |
| WI_1 H7 | volume=low | 117 | −0.5 % [−2.5, +2.0] |
| WI_1 H7 | volume=mid | 116 | +1.8 % [−0.8, +4.6] |
| Online Retail II H28 | frequency=intermittent_or_sparse | 83 | +6.1 % [+2.4, +10.5] |
| Online Retail II H28 | volume=high | 33 | +5.9 % [+2.5, +9.3] |
| Online Retail II H28 | volume=low | 34 | +5.9 % [−3.0, +14.0] |
| Online Retail II H28 | volume=mid | 33 | +5.7 % [−0.0, +12.4] |
| Online Retail II H7 | frequency=intermittent_or_sparse | 83 | +4.5 % [+1.8, +7.8] |
| Online Retail II H7 | volume=high | 33 | +3.7 % [+1.0, +6.8] |
| Online Retail II H7 | volume=low | 34 | +5.0 % [−0.3, +10.9] |
| Online Retail II H7 | volume=mid | 33 | +4.4 % [+1.1, +9.5] |

*Source: `results/analysis/analysis_W2.json` (`segments_exploratory`; B = 2,000, no multiplicity control); CSV: `tables/tableA3_segments.csv`.*

**Table A4. Design effect of the crossed series × week structure (H1 comparison, W2)**

| cell | series | weekly blocks | series-week cells | design effect on the s.e. | approx. effective independent cells |
|---|---|---|---|---|---|
| CA_1 H28 | 350 | 24 | 8400 | 1.9 | 2321 |
| CA_1 H7 | 350 | 24 | 8400 | 1.7 | 2800 |
| TX_1 H28 | 350 | 24 | 8400 | 1.5 | 3668 |
| TX_1 H7 | 350 | 24 | 8400 | 1.8 | 2558 |
| WI_1 H28 | 349 | 24 | 8376 | 1.5 | 3980 |
| WI_1 H7 | 349 | 24 | 8376 | 1.7 | 2856 |
| Online Retail II H28 | 100 | 24 | 2400 | 2.5 | 397 |
| Online Retail II H7 | 100 | 24 | 2400 | 2.0 | 610 |

*Source: `results/summary_extra.json` (`design_effects_W2`); CSV: `tables/tableA4_design_effect.csv`.*

## References

*Bibliographic metadata from Crossref (29 DOI entries; `REFERENCE_AUDIT.csv`); Ke et al. checked on the NeurIPS proceedings page, Damato et al. on the arXiv API, Chen (2012) on the UCI page; Koenker & Bassett pages checked on the Econometric Society page (2026-10-22). Claim-level support is in `REFERENCE_CLAIM_CHECK.csv`: most claims were checked against abstracts only; the M5 report was read in a pre-publication copy.*

Athanasopoulos, G., Hyndman, R.J., Kourentzes, N., & Petropoulos, F. (2017). Forecasting with temporal hierarchies. *European Journal of Operational Research*, 262, 60-74. https://doi.org/10.1016/j.ejor.2017.02.046

Bojer, C.S., & Meldgaard, J.P. (2021). Kaggle forecasting competitions: An overlooked learning opportunity. *International Journal of Forecasting*, 37, 587-603. https://doi.org/10.1016/j.ijforecast.2020.07.007

Cameron, A.C., Gelbach, J.B., & Miller, D.L. (2011). Robust Inference With Multiway Clustering. *Journal of Business & Economic Statistics*, 29, 238-249. https://doi.org/10.1198/jbes.2010.07136

Chen, D. (2012). Online Retail II [Dataset]. UCI Machine Learning Repository. https://doi.org/10.24432/C5CG6D  (CC BY 4.0).

Chen, T., & Guestrin, C. (2016). XGBoost: A scalable tree boosting system. *Proceedings of the 22nd ACM SIGKDD International Conference on Knowledge Discovery and Data Mining*, 785-794. https://doi.org/10.1145/2939672.2939785

Croston, J.D. (1972). Forecasting and Stock Control for Intermittent Demands. *Journal of the Operational Research Society*, 23, 289-303. https://doi.org/10.1057/jors.1972.50

Damato, S., Rubattu, N., Azzimonti, D., & Corani, G. (2026). Intermittent time series forecasting: local vs global models. arXiv:2601.14031 (preprint; authors and title per the arXiv API, 2026-10-22).

Diebold, F.X., & Mariano, R.S. (1995). Comparing Predictive Accuracy. *Journal of Business & Economic Statistics*, 13, 253-263. https://doi.org/10.1080/07350015.1995.10524599

Fildes, R., Ma, S., & Kolassa, S. (2022). Retail forecasting: Research and practice. *International Journal of Forecasting*, 38, 1283-1318. https://doi.org/10.1016/j.ijforecast.2019.06.004

Friedman, J.H. (2001). Greedy function approximation: A gradient boosting machine. *The Annals of Statistics*, 29, 1189-1232. https://doi.org/10.1214/aos/1013203451

Gneiting, T. (2011). Making and Evaluating Point Forecasts. *Journal of the American Statistical Association*, 106, 746-762. https://doi.org/10.1198/jasa.2011.r10138

Hewamalage, H., Ackermann, K., & Bergmeir, C. (2023). Forecast evaluation for data scientists: common pitfalls and best practices. *Data Mining and Knowledge Discovery*, 37, 788-832. https://doi.org/10.1007/s10618-022-00894-5

Hyndman, R.J., & Koehler, A.B. (2006). Another look at measures of forecast accuracy. *International Journal of Forecasting*, 22, 679-688. https://doi.org/10.1016/j.ijforecast.2006.03.001

Hyndman, R.J., Ahmed, R.A., Athanasopoulos, G., & Shang, H.L. (2011). Optimal combination forecasts for hierarchical time series. *Computational Statistics & Data Analysis*, 55, 2579-2589. https://doi.org/10.1016/j.csda.2011.03.006

Januschowski, T., Wang, Y., Torkkola, K., Erkkilä, T., Hasson, H., & Gasthaus, J. (2022). Forecasting with trees. *International Journal of Forecasting*, 38, 1473-1481. https://doi.org/10.1016/j.ijforecast.2021.10.004

Ke, G., Meng, Q., Finley, T., Wang, T., Chen, W., Ma, W., Ye, Q., & Liu, T.-Y. (2017). LightGBM: A highly efficient gradient boosting decision tree. *Advances in Neural Information Processing Systems*, 30 (authors and title checked on the NeurIPS proceedings page, 2026-10-22).

Koenker, R., & Bassett, G. (1978). Regression Quantiles. *Econometrica*, 46, 33-50. https://doi.org/10.2307/1913643

Kolassa, S. (2016). Evaluating predictive count data distributions in retail sales forecasting. *International Journal of Forecasting*, 32, 788-803. https://doi.org/10.1016/j.ijforecast.2015.12.004

Kolassa, S. (2020). Why the “best” point forecast depends on the error or accuracy measure. *International Journal of Forecasting*, 36, 208-211. https://doi.org/10.1016/j.ijforecast.2019.02.017

Kourentzes, N. (2014). On intermittent demand model optimisation and selection. *International Journal of Production Economics*, 156, 180-190. https://doi.org/10.1016/j.ijpe.2014.06.007

Makridakis, S., Spiliotis, E., & Assimakopoulos, V. (2018). Statistical and Machine Learning forecasting methods: Concerns and ways forward. *PLOS ONE*, 13, e0194889. https://doi.org/10.1371/journal.pone.0194889

Makridakis, S., Spiliotis, E., & Assimakopoulos, V. (2020). The M4 Competition: 100,000 time series and 61 forecasting methods. *International Journal of Forecasting*, 36, 54-74. https://doi.org/10.1016/j.ijforecast.2019.04.014

Makridakis, S., Spiliotis, E., & Assimakopoulos, V. (2022). M5 accuracy competition: Results, findings, and conclusions. *International Journal of Forecasting*, 38, 1346-1364. https://doi.org/10.1016/j.ijforecast.2021.11.013

Nikolopoulos, K., Syntetos, A.A., Boylan, J.E., Petropoulos, F., & Assimakopoulos, V. (2011). An aggregate–disaggregate intermittent demand approach (ADIDA) to forecasting: an empirical proposition and analysis. *Journal of the Operational Research Society*, 62, 544-554. https://doi.org/10.1057/jors.2010.32

Owen, A.B. (2007). The pigeonhole bootstrap. *The Annals of Applied Statistics*, 1, 386-411. https://doi.org/10.1214/07-AOAS122

Owen, A.B., & Eckles, D. (2012). Bootstrapping data arrays of arbitrary order. *The Annals of Applied Statistics*, 6, 895-927. https://doi.org/10.1214/12-AOAS547

Politis, D.N., & Romano, J.P. (1994). The Stationary Bootstrap. *Journal of the American Statistical Association*, 89, 1303-1313. https://doi.org/10.1080/01621459.1994.10476870

Prestwich, S., Rossi, R., Armagan Tarim, S., & Hnich, B. (2014). Mean-based error measures for intermittent demand forecasting. *International Journal of Production Research*, 52, 6782-6791. https://doi.org/10.1080/00207543.2014.917771

Spiliotis, E., Abolghasemi, M., Hyndman, R.J., Petropoulos, F., & Assimakopoulos, V. (2021). Hierarchical forecast reconciliation with machine learning. *Applied Soft Computing*, 112, 107756. https://doi.org/10.1016/j.asoc.2021.107756

Spiliotis, E., Makridakis, S., Semenoglou, A.A., & Assimakopoulos, V. (2022). Comparison of statistical and machine learning methods for daily SKU demand forecasting. *Operational Research*, 22, 3037-3061. https://doi.org/10.1007/s12351-020-00605-2

Syntetos, A.A., & Boylan, J.E. (2005). The accuracy of intermittent demand estimates. *International Journal of Forecasting*, 21, 303-314. https://doi.org/10.1016/j.ijforecast.2004.10.001

Teunter, R.H., Syntetos, A.A., & Zied Babai, M. (2011). Intermittent demand: Linking forecasting to inventory obsolescence. *European Journal of Operational Research*, 214, 606-615. https://doi.org/10.1016/j.ejor.2011.05.018
