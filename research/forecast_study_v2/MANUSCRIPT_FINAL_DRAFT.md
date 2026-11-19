> **SUPERSEDED (2026-10-22).** This first draft (R1) is kept unchanged below for the record. Use `MANUSCRIPT_R2.md`. Corrections made in R2: the M5 LightGBM statement ("all of the top 50") was an overstatement — the M5 report says most examined methods and almost all of the top-50 methods with a description used LightGBM; the "alternative count 5/8" for the subset-day endpoint was Monte-Carlo noise and is withdrawn (`SUPPLEMENTARY_H3_RESOLUTION.md`); the zero-forecast range on M5 is 29–49 %, not 28–49 %; v1's audit is described as internal, not independent; tables are now generated from stored artifacts.

# Does a boosted model beat the best simple baseline? Endpoint-matched evaluation of daily retail demand forecasts on public data

*Working title. Draft for author review — not submitted. Author names, affiliations and declarations: [AUTHOR TO COMPLETE].*

## Abstract

**Background.** A previous study in this project found that a LightGBM model with a Tweedie objective did not beat a trailing 28-day median on pooled item-day weighted absolute percentage error (WAPE) for daily retail demand, while winning after demand was aggregated. Forecasting theory attributes such reversals to the scoring function (absolute error rewards the conditional median, squared error the mean), but the size of the effect, and whether the earlier negative result survives a candidate set that includes median-type objectives, had not been measured under a stricter protocol.
**Methods.** Direct 7- and 28-day-ahead forecasts of daily units were evaluated on three M5 stores (350/350/349 department-stratified series) and the 100 largest-revenue SKUs of Online Retail II, in six rolling 28-day test blocks after three validation blocks, on a confirmatory window that no experiment had scored (W2) and on replication windows (W3, W1). Eight boosted-tree or ridge candidates and 31 simple baselines (16 estimators × matched and fresh information) were compared. Selection was made on validation data for the endpoint being reported (item-day or subset-day WAPE); the protocol was hash-frozen before any confirmatory outcome was read. Inference used a paired crossed bootstrap over series and weeks (secondary: two-way cluster-robust interval), Holm correction, a 2 % minimum improvement and a dual-method rule.
**Results.** On the confirmatory window the validation-selected absolute-error LightGBM beat the best same-information baseline on item-day WAPE in all 8 dataset–horizon cells (median +4.3 %, range +2.5 % to +6.0 %), and the improvement was positive in all 22 cells over three windows (supported in 20). It beat the earlier Tweedie model in every cell (+7.9 % to +16.8 %). Against baselines that see up to 28 days more recent data the advantage was not established at the 28-day horizon. On the aggregate (subset-day) endpoint the selected models were mean-type (Tweedie or squared error); the item-day winner, with a relative bias of −0.29 to −0.39, lost to simple baselines (subset-day WAPE 0.35 against 0.11 for CA_1, 28 days), and the improvement of the aggregate-selected model over the best baseline was supported in 4 of 8 cells (point estimates positive in 7 of 8).
**Conclusions.** For these samples the earlier negative result changes sign when the objective and the evaluation endpoint are matched, with modest gains at item-day and endpoint-dependent rankings. The finding is an empirical quantification of established theory on four public data sets, not a new method, and it does not extend to other retailers, to richer baselines or models, or to decision costs.

**Keywords:** demand forecasting; intermittent demand; gradient boosting; scoring functions; forecast evaluation; aggregation; reproducibility.

## 1. Introduction

Boosted trees are strong forecasters of retail demand: in the M5 accuracy competition LightGBM was used by all of the top 50 teams [Makridakis et al., 2022], and tree-based methods outperformed other approaches there [Januschowski et al., 2022]; reviews of Kaggle forecasting competitions, whose data are typically intermittent, report that gradient-boosted trees and neural networks are strong [Bojer & Meldgaard, 2021]. Yet strong aggregate results do not settle whether a learned model beats a *well-chosen simple baseline* on a given error measure. Forecasting theory is explicit that the optimal point forecast depends on the scoring function: squared error is minimised by the conditional mean, absolute error by the conditional median [Gneiting, 2011; Kolassa, 2020; Koenker & Bassett, 1978]. For sparse daily demand, absolute-error-type measures can therefore reward forecasts near zero and rank methods differently from measures of totals [Hyndman & Koehler, 2006; Prestwich et al., 2014; Kolassa, 2016; Kourentzes, 2014], and aggregating demand over time or items changes the problem [Nikolopoulos et al., 2011; Athanasopoulos et al., 2017].

A previous study in this project (the "v1 study") found that a LightGBM model with a Tweedie objective did not beat a trailing 28-day median in pooled item-day WAPE on two M5 stores and one retail dataset, while winning after demand was summed over days. An independent audit of that study showed that the contrast was largely the baseline's level bias, that no candidate model targeted a median, and that the evaluation windows had been examined repeatedly. The present study asks the question again under a stricter design.

**Research question.** Under model selection fixed on validation data *for the endpoint being reported*, and on evaluation windows that no experiment had scored, does a boosted model beat the best simple baseline; by how much, with what uncertainty; does the answer change between the item-day and the aggregated endpoint; does the v1 negative result survive when median-type objectives are in the candidate set; and does the answer replicate across stores, horizons and windows?

## 2. Related work and what is already known

The relationship between loss function and optimal forecast [Gneiting, 2011; Kolassa, 2020], the unreliability of conventional error measures for intermittent and low-count demand [Hyndman & Koehler, 2006; Prestwich et al., 2014; Kolassa, 2016; Kourentzes, 2014], temporal and cross-sectional aggregation [Nikolopoulos et al., 2011; Athanasopoulos et al., 2017; Hyndman et al., 2011; Spiliotis et al., 2021], and the strength of boosted trees on M5-type data [Makridakis et al., 2022; Januschowski et al., 2022; Bojer & Meldgaard, 2021; Spiliotis et al., 2022] are established. Evidence that machine-learning methods do not automatically beat statistical ones also exists [Makridakis et al., 2018; Makridakis et al., 2020], and retail forecasting has its own practice and measurement issues [Fildes et al., 2022]. Evaluation guidance is given by Hewamalage et al. [2023]. A preprint compares local and global models for intermittent series [Damato et al., 2026].

In the sources read for this study (a bounded literature review, not a systematic one), I did not find a report that combines endpoint-matched validation selection, never-scored windows chosen under a written freeze, a large prespecified baseline set, and paired two-way dependence-aware intervals for a boosted model on public retail data. That is an absence in what was read, not proof of absence. The expected direction of the main effect follows from theory; the study measures its size and location.

## 3. Contributions and scope

*Contributions (incremental and empirical).* (i) Magnitudes of the item-day and aggregate differences between validation-selected boosted models and the best of 31 simple baselines on four public datasets, two horizons and replication windows, under a frozen protocol; (ii) a test of whether the v1 negative result survives a candidate set that includes median-type objectives; (iii) a decomposition of the baseline's level bias; (iv) a pre-freeze simulation of the interval methods and a dual-method decision rule; (v) a documented package with frozen protocol, pinned environment and deterministic settings (a fresh-environment reproduction has not been performed). *Not contributions:* a new model, metric or principle; any claim about Indian SMEs or other populations; causal effects; customer churn; predictive intervals.

## 4. Data and data rights

M5 [Makridakis et al., 2022; Kaggle competition data]: daily unit sales for 350 (CA_1, TX_1) and 349 (WI_1) department-stratified random series per store, drawn among series whose first sale falls on or before day d_1100 (products launched later are excluded; seed 20261015). Online Retail II [Chen, 2012; CC BY 4.0]: the 100 SKUs with the largest revenue before the first validation block of each window, daily gross units after documented cleaning (cancellations, non-positive quantity or price, non-product codes and 33,666 exact duplicate lines removed; returns excluded). M5 items are evaluated on days with a listed selling price (days without a listing carry zero demand by construction; verified); this eligibility rule is an assumption about ex-ante knowledge. **Rights:** M5 data are restricted to non-commercial and academic use and may not be redistributed; stored predictions that contain M5 sales are therefore not released (Section 13).

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

All numbers below are read from the stored analysis files (`results/analysis/analysis_*.json`; generated tables in `results/TABLES.md`, `METRIC_RESULTS.csv`, `MODEL_COMPARISON.csv`) and were recomputed by an independent code path (Section 11). Improvements are relative reductions in WAPE pooled over the six test blocks, (E_ref − E_model)/E_ref; intervals are 95 % percentile intervals from the crossed bootstrap (item-day) or the iid-week bootstrap (subset-day); "Holm p" is adjusted within the eight confirmatory cells of the window.

### 8.1 Design as executed

**Table 1. Windows and samples** (M5 scored spans are validation plus test periods; from `DATA_AUDIT.md`).

| window | role | datasets | validation + test span | series per dataset | rows per cell |
|---|---|---|---|---|---|
| W2 | **confirmatory** | M5 CA_1, TX_1, WI_1; Online Retail II | M5: 2015-01-05 → 2015-09-13; Online Retail II: 2010-07-24 → 2011-04-01 | 350 / 350 / 349 / 100 | 58,800 / 58,800 / 58,632 / 16,800 |
| W3 | independent replication | M5 CA_1, TX_1, WI_1 (not feasible for Online Retail II) | 2014-04-28 → 2015-01-04 | 350 / 350 / 349 | as W2 |
| W1 | replication for WI_1 (fresh); non-independent re-evaluation for CA_1, TX_1, Online Retail II | all four | M5: 2015-09-14 → 2016-05-22; Online Retail II: 2011-04-02 → 2011-12-09 | as W2 | as W2 |

Each cell is a dataset × horizon (H = 28 or 7); a window therefore has eight cells (six for W3). Zero shares among test rows were 0.53–0.65 for M5 and 0.32–0.40 for Online Retail II.

### 8.2 Model selection on validation data

For the item-day endpoint the absolute-error LightGBM was selected in all eight W2 cells (31-leaf configuration on M5, the 15-leaf / minimum-child-100 configuration on Online Retail II). For the subset-day endpoint the Tweedie (p = 1.1) model was selected in six W2 cells and the squared-error model in the two WI_1 cells; the absolute-error and quantile models were never selected for the aggregate endpoint. In W1 the 0.5-quantile model replaced the absolute-error model in two cells (CA_1 H28, TX_1 H7). The best validation baseline for item-day was a trailing or weekday median (trailing 14–91 days; weekday median of 8 weeks on Online Retail II); for subset-day it was a weekday mean (4 or 8 weeks). No cell selected the all-zero forecast.

### 8.3 Confirmatory results (W2)

**Table 2. H1 — item-day WAPE, item-day-selected model vs best matched baseline (W2).**

| cell | baseline | WAPE baseline / model | improvement [95 % CI] | Holm p | blocks won | H1b (vs best any-information baseline) | H2 (vs original Tweedie p = 1.1 model) |
|---|---|---|---|---|---|---|---|
| CA_1 H28 | trailing median 56 | 0.775 / 0.739 | +4.6 % [+2.3, +7.1] | 0.002 | 6/6 | inconclusive (−1.4 %) | supported (+8.2 %) |
| CA_1 H7 | trailing median 14 | 0.714 / 0.686 | +4.0 % [+2.3, +6.0] | 0.002 | 6/6 | supported (+2.5 %) | supported (+8.0 %) |
| TX_1 H28 | trailing median 56 | 0.774 / 0.755 | +2.5 % [+1.0, +4.1] | 0.004 | 6/6 | inconclusive (+0.8 %) | supported (+10.5 %) |
| TX_1 H7 | trailing median 91 | 0.752 / 0.718 | +4.5 % [+2.5, +6.8] | 0.002 | 6/6 | supported (+3.8 %) | supported (+10.8 %) |
| WI_1 H28 | trailing median 56 | 0.783 / 0.757 | +3.3 % [+1.6, +5.3] | 0.002 | 6/6 | inconclusive (+0.9 %) | supported (+7.9 %) |
| WI_1 H7 | trailing median 91 | 0.753 / 0.708 | +6.0 % [+3.4, +9.0] | 0.002 | 6/6 | supported (+3.2 %) | supported (+8.2 %) |
| Online Retail II H28 | weekday median 8 | 0.931 / 0.877 | +5.8 % [+2.7, +9.5] | 0.002 | 6/6 | inconclusive (+2.2 %) | supported (+16.7 %) |
| Online Retail II H7 | weekday median 8 | 0.871 / 0.836 | +4.0 % [+1.5, +7.0] | 0.004 | 5/6 | supported (+4.0 %) | supported (+16.8 %) |

H1 is supported in 8 of 8 cells under the prespecified rule (Holm p < 0.05, interval excluding zero, improvement ≥ 2 %, ≥ 4 of 6 blocks, and agreement of the secondary method). The median improvement is +4.3 % (range +2.5 … +6.0 %). H2: the item-day-selected model improves on the original Tweedie model in 8 of 8 cells (+7.9 … +16.8 %). H1b — against baselines that are re-estimated at block starts and therefore see up to 28 days more data than the model — is supported in the four H = 7 cells and inconclusive in the four H = 28 cells; the claim of Table 2 is therefore limited to baselines with the same information as the model.

**Table 3. H3 — subset-day WAPE, subset-day-selected model vs best matched baseline (W2).**

| cell | model | best matched baseline | WAPE baseline / model | improvement [95 % CI] | Holm p primary / secondary | blocks won | verdict |
|---|---|---|---|---|---|---|---|
| CA_1 H28 | Tweedie 1.1 | weekday mean 4 | 0.114 / 0.088 | +22.7 % [+14.6, +30.6] | 0.002 / 0.002 | 6/6 | supported |
| CA_1 H7 | Tweedie 1.1 | weekday mean 8 | 0.104 / 0.084 | +18.7 % [+9.5, +28.5] | 0.002 / 0.002 | 6/6 | supported |
| TX_1 H28 | Tweedie 1.1 | weekday mean 8 | 0.117 / 0.099 | +14.8 % [+2.5, +26.7] | 0.071 / 0.048 | 4/6 | inconclusive (methods disagree; boundary-sensitive, Section 11) |
| TX_1 H7 | Tweedie 1.1 | weekday mean 4 | 0.123 / 0.094 | +23.8 % [+13.9, +33.1] | 0.002 / 0.002 | 6/6 | supported |
| WI_1 H28 | squared error | weekday mean 8 | 0.100 / 0.092 | +7.8 % [−0.5, +15.7] | 0.205 / 0.269 | 5/6 | inconclusive |
| WI_1 H7 | squared error | weekday mean 8 | 0.099 / 0.087 | +11.4 % [+3.6, +18.3] | 0.035 / 0.002 | 6/6 | supported |
| Online Retail II H28 | Tweedie 1.1 | weekday mean 8 | 0.511 / 0.482 | +5.8 % [−5.5, +16.2] | 0.582 / 0.405 | 4/6 | inconclusive |
| Online Retail II H7 | Tweedie 1.1 | weekday mean 8 | 0.456 / 0.458 | −0.5 % [−13.3, +8.4] | 0.939 / 0.934 | 2/6 | inconclusive |

H3 is supported in 4 of 8 cells and inconclusive in 4; no cell is contradicted. Point estimates are positive in 7 of 8 cells (median +13.1 %). The intervals are wide (for instance CA_1 H7: +9.5 … +28.5 %) because only 24 weekly blocks are available at this endpoint. The independent re-implementation would count TX_1 H28 as supported (5 of 8); this is a Monte-Carlo effect of the fixed bootstrap seed on a cell at the decision boundary (Section 11).


### 8.4 Replication windows

**Table 4. Replication summary** (verdict counts: supported / contradicted / inconclusive; each window with its own Holm adjustment).

| window | cells | H1 | H1b | H2 | H3 | median H1 improvement (range) |
|---|---|---|---|---|---|---|
| W2 (confirmatory) | 8 | 8/0/0 | 4/0/4 | 8/0/0 | 4/0/4 | +4.3 % (+2.5 … +6.0) |
| W3 (M5, independent) | 6 | 6/0/0 | 3/0/3 | 6/0/0 | 4/0/2 | +4.5 % (+2.2 … +6.2) |
| W1 (all four; only WI_1 is fresh) | 8 | 6/0/2 | 3/0/5 | 8/0/0 | 4/0/4 | +3.2 % (+1.1 … +4.5) |

The H1 improvement is positive in all 22 cells of the three windows. In W3 it is supported in all six cells. In W1 two cells are inconclusive (TX_1 H28: +1.1 %, 3/6 blocks won, interval includes zero; TX_1 H7: +1.9 %, below the 2 % threshold). The two WI_1 cells of W1 (the fresh store, +3.8 % and +4.5 %) are supported. W1 results for CA_1, TX_1 and Online Retail II are not independent evidence (Section 5).

### 8.5 Seed sensitivity

Refitting the item-day model with seeds 43 and 44 in W2 changes the H1 improvement by at most 0.4 percentage points (per cell 0.09–0.40 pp); the lowest of the three seeds is ≥ 2.3 % in every cell. Seed variation is not included in the confidence intervals.

### 8.6 Aggregation and bias (the endpoint dependence)

**Table 5. Item-day versus subset-day WAPE and bias, W2, H = 28 (the H = 7 cells show the same pattern, `AGGREGATION_ANALYSIS.md`).**

| cell | method | item-day | subset-day | relative bias |
|---|---|---|---|---|
| CA_1 | absolute-error model (item-day winner) | **0.739** | 0.346 | −0.346 |
| | best item-day baseline (trailing median 56) | 0.775 | 0.295 | −0.293 |
| | Tweedie 1.1 model (subset-day winner) | 0.806 | **0.088** | +0.001 |
| | best subset-day baseline (weekday mean 4) | 0.849 | 0.114 | −0.007 |
| TX_1 | absolute-error model | **0.755** | 0.394 | −0.394 |
| | Tweedie 1.1 model | 0.843 | **0.099** | −0.021 |
| WI_1 | absolute-error model | **0.757** | 0.331 | −0.331 |
| | squared-error model | 0.831 | **0.092** | +0.020 |
| Online Retail II | absolute-error model | **0.877** | 0.573 | −0.384 |
| | Tweedie 1.1 model | 1.053 | **0.482** | +0.085 |

The model that wins the item-day endpoint is strongly downward-biased (relative bias −0.29 … −0.39 on M5; it forecasts zero for 28–49 % of M5 rows against 53–70 % for the best baseline). Because subset-day WAPE is at least the absolute relative bias (with equality on M5 for the item-day model), the same model loses to simple baselines on the aggregate endpoint (CA_1 H28: 0.346 against 0.114 for the best subset-day baseline), and the winners of the two endpoints differ in all eight cells. The original reference model (Tweedie 1.1) has bias near zero and loses to the best baseline on the item-day endpoint (CA_1 H28: 0.806 against 0.775).

### 8.7 Exploratory segment results (not confirmatory)

Gains of the item-day model are concentrated in frequently selling and high-volume series (CA_1 H28: frequent series +8.1 % [+3.5, +12.7], n = 46; intermittent or sparse +2.5 % [+0.5, +4.7], n = 304; volume terciles +6.3 % [+3.1, +9.7] high, +1.5 % and +1.0 % low and mid with intervals that include zero). These intervals do not account for multiplicity and are descriptive; pooled WAPE is dominated by high-volume series.

## 9. Discussion

**What the study adds.** The negative v1 result was largely an objective–metric mismatch plus baseline-level bias, not evidence that boosted models cannot beat simple baselines: when absolute-error objectives are available and selection is made on the same endpoint, the learned model beats the best same-information baseline on the item-day endpoint by a modest 2.5–6 % in every confirmatory cell and in the replication windows, while Tweedie / squared-error models win the aggregate endpoint by larger margins but with less certainty. Both findings are what the scoring-function theory predicts [Gneiting, 2011; Kolassa, 2020]; the contribution is their quantification under a pre-specified protocol with dependence-aware intervals on public retail data, and the demonstration that the answer to "does the learned model beat a simple baseline?" can flip with the endpoint.

**What the study does not show.** (i) That the item-day gain is useful: it comes from a model that forecasts zero more often and has large negative bias; whether that is desirable depends on the decision loss, which was not evaluated. (ii) That learned models beat baselines that know more recent data at H = 28 (H1b). (iii) That any model is "best" — the candidate set is small (eight configurations from LightGBM, XGBoost and ridge regression), tuning is limited, and statistical models (ETS, ARIMA, Theta), global neural models and probabilistic forecasts are not included. (iv) Generality beyond three stores of one retailer and one UK wholesaler. (v) Causal explanations: the interpretation in terms of bias and zero forecasts is supported by descriptive decomposition, not by an intervention.

**Relationship to the literature.** Tree-based models were strong in M5 [Makridakis et al., 2022; Januschowski et al., 2022]; the evidence that absolute-error measures reward low forecasts on intermittent demand is long established [Hyndman & Koehler, 2006; Prestwich et al., 2014; Kolassa, 2016]. The present results are consistent with both and add the effect sizes for a matched-information comparison with a large baseline set.

**Practical reading (cautious).** The endpoint should be chosen before models are compared and should reflect the decision. If the decision depends on totals (replenishment of a store's weekly volume), a mean-type objective and an aggregate metric are appropriate; if item-day accuracy in the absolute-error sense is wanted, a median-type objective helps, with the bias that implies. No cost, service-level or profit analysis was done.

## 10. Limitations and threats to validity

* **Internal freeze, not public pre-registration.** The protocol was hashed before any W2/W3/WI_1 outcome was read, but the hash is not externally timestamped and the design was set with knowledge of the v1 results and an audit of them.
* **Window exposure.** W2 and W3 were not scored for these entities before; their calendar *periods* were used in a retired benchmark on other M5 series (documented). W1 for CA_1, TX_1 and Online Retail II is non-independent. Online Retail II has no W3 and a short W2 history (487 days).
* **Small candidate set and limited tuning.** Eight configurations, hyper-parameters shared across them; a stronger tuned model might change magnitudes. Statistical forecasting packages were not installed and not evaluated.
* **Sampling.** 350/349 department-stratified series per M5 store (series launched after d_1100 excluded) and the 100 largest-revenue Online Retail II SKUs; results describe these samples. The eligibility rule (days with a listed price) is an assumption about what a forecaster knows.
* **Dependence and inference.** Intervals are percentile or t-based and mildly liberal in simulation (worst-case coverage ≈ 0.90–0.95); 24 weekly blocks limit the aggregate endpoint; model errors across blocks are correlated through overlapping training windows (not modelled); one seed per primary model.
* **Metric choice.** WAPE and its aggregate version are the prespecified endpoints; scaled, probabilistic, cost-based or service-level criteria are not evaluated. Item-day WAPE rewards forecasts near the conditional median on sparse series.
* **Dual-method rule.** It converts method disagreement into "inconclusive" and is conservative for H3 (one W2 cell, two W3 cells). The count of supported H3 cells depends on this rule and on Monte-Carlo noise near the boundary.
* **Same-agent development and verification.** The study, the verification code and this manuscript were produced by one AI assistant under the direction of the author; the verification is therefore an internal consistency and re-implementation check, not independent external validation (Section 11).
* **Data rights.** M5 predictions contain actual sales and are not released.

## 11. Verification

Unit tests (17) cover leak-freedom of all 16 baseline estimators, metric identities, objective semantics, window arithmetic and inference helpers. A second code path, `verify_independent.py`, which imports nothing from the study, recomputed targets from the raw files, all 31 baselines row by row, metrics, improvements, bootstrap and cluster-robust intervals (own implementation; B = 4,000 for the bootstrap), Holm adjustments and verdicts, the validation-only selection, and the file ordering of selection before test fits: 98/98 checks passed in W2, 72/72 in W3, 98/98 in W1, and the frozen files were unchanged. Of 88 verdict comparisons, 87 agree. The exception, W2 TX_1 H28 H3, is the Monte-Carlo effect described in Section 8.3: the frozen-seed iid-week bootstrap (B = 10,000) gave p = 0.0178, thirty other seeds gave a mean of 0.0129 (SD 0.0017), and B = 400,000 gave 0.0125; the frozen verdict is reported and the alternative count disclosed. This verification was designed and run by the same AI assistant that wrote the study code; it is not external validation. Items that still need a human: confirming the data-licence reading, checking the reference list against the original sources, reviewing the interpretation of the cells at the decision boundary, and an optional external replication.

## 12. Conclusions

In the confirmatory window, an absolute-error LightGBM selected on validation item-day WAPE beat the best simple baseline with the same information in all eight dataset–horizon cells (median +4.3 %, range +2.5 … +6.0 %), the result was positive in all 22 cells across three windows and supported in 20 of them, and it beat the earlier Tweedie reference in every cell. Against baselines that see more recent data (H = 28) the advantage is not established. On the aggregate endpoint a different (mean-type) model is selected, the item-day winner loses to simple baselines because of its level bias, and the evidence for improvement over the best baseline is supported in four of eight cells. The take-home message is endpoint-matching: the same dataset and the same models give opposite answers depending on the metric, and claims of "beats the baseline" are only meaningful relative to the endpoint, the information set and the baseline's level bias.

## 13. Reproducibility, data and code availability

Code, frozen protocol, configuration and result tables are in `research/forecast_study_v2/` (see `REPRODUCIBILITY.md`). Raw M5 data must be obtained from Kaggle under the competition rules; Online Retail II is available from the UCI repository (CC BY 4.0). Stored model predictions contain M5 sales and are not released. A fresh-environment reproduction has not been performed (see `FINAL_VERIFICATION_REPORT.md`).

## 14. Declarations (to be completed by the author)

* **Author contributions / authorship:** [AUTHOR TO COMPLETE]
* **Funding:** [AUTHOR TO COMPLETE]
* **Competing interests:** [AUTHOR TO COMPLETE]
* **Ethics:** no human or personal data were collected; Online Retail II contains anonymised transaction data from a UK retailer (licence CC BY 4.0). [AUTHOR TO CONFIRM]
* **Use of generative AI:** The experimental code, analysis, verification code and the drafting of this manuscript were produced with the assistance of an AI model (Anthropic Claude, via Claude Code) under the author's direction. The author must review all content, take responsibility for it, and complete the venue's declaration form. [AUTHOR TO COMPLETE]
* **Data availability:** as in Section 13; M5 data cannot be redistributed.
* **Pre-registration:** none (internal timestamped freeze only).

## References

*Metadata from Crossref (checked 2026-10-22; see `REFERENCE_AUDIT.csv`). Entries marked "verify" must be checked by the author against the original source.*

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

Ke, G., Meng, Q., Finley, T., Wang, T., Chen, W., Ma, W., Ye, Q., & Liu, T.-Y. (2017). LightGBM: A highly efficient gradient boosting decision tree. *Advances in Neural Information Processing Systems*, 30.  [authors and title per NeurIPS proceedings page; verify before submission]

Koenker, R., & Bassett, G. (1978). Regression Quantiles. *Econometrica*, 46, 33-50 [the registry lists only the start page; verify]. https://doi.org/10.2307/1913643

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
