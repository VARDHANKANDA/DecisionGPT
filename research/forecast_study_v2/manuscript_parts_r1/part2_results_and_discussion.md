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
