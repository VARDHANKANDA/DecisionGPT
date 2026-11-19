## 17. Discussion

**What the evidence supports.** On three public retail collections, a validation-selected gradient-boosting forecaster did not beat the best simple baseline in item-day pooled WAPE, once that baseline was chosen on validation data and the interval respected dependence across series and weeks. The loss is small on M5 CA_1 and Online Retail II (−2.6 % to −3.7 %, mostly inconclusive) and large on M5 TX_1 (−11 %). The same model was far better at the store-day aggregate level and on RMSE. The best method therefore depends on which loss one cares about: item-day absolute error rewards forecasts near the conditional median — zero for most sparse series — whereas stock, staffing and revenue planning at store level rewards unbiased totals. The L1 refit illustrates the trade-off: a model that wins item-day WAPE gives up aggregate accuracy and carries a strong negative bias.

**Why this matters for practice.** Reporting a single pooled WAPE against seasonal naive — the common comparison — would have shown the boosted models winning (seasonal naive WAPE was 0.89 on M5 CA_1 H=28, against 0.74 for the model), whereas the strongest simple baseline reverses the sign. The strength of the reference and the scoring level are therefore first-order design decisions, not details.

**Relation to prior work.** The strength of boosted trees on M5-type data [Januschowski et al., 2022; Bojer & Meldgaard, 2021] is not contradicted: the model beat most baselines and won at the aggregate level and in RMSE. What is added is a measurement of how much of that advantage depends on the baseline and metric under dependence-aware inference, in the spirit of the evaluation guidance of Hewamalage et al. [2023] and Kolassa [2020]. Spiliotis et al. [2022] report ML gains on SKU demand; our result is a boundary condition for such claims, not a refutation, since the data, the metric and the baseline sets differ.

**Interpretation limits.** (a) The conformal result concerns marginal coverage only. (b) The ablations measure association with forecast error in one store at one horizon; they do not show that price affects demand (nor that it does not). (c) The segment pattern replicated in one of two M5 stores and in none of the Online Retail II samples. (d) The classification label is inactivity, and its calibration result shows only that prevalence shift can invalidate a validation-fitted calibrator.

**What would change the conclusion.** A median-targeting (or quantile) model selected on validation WAPE from the start; a probabilistic baseline for intervals; larger or different datasets; tuned neural or foundation models [Ansari et al., 2024] (not evaluated); or a decision-relevant loss (inventory cost) instead of WAPE.

## 18. Verification and reproducibility

A separate script that does not import the study's metric or inference code recomputed the pooled WAPE, bias, aggregate WAPE and by-block WAPE of the selected model and baselines from the stored predictions of each cell and checked arrays, row uniqueness, window ordering, selection-before-test file order, and the argmin selection rules: 24/24 checks passed in each of the six cells and 19/19 in each of four ablation runs. The repository's earlier benchmark was audited first: its stored metrics were recomputed from stored predictions (maximum difference 5.2 × 10⁻¹⁰) and four historical runs were re-executed into a new directory (c2 and f2 identical; f1 identical on 266 shared numbers; c1 differing in two numbers by at most 1.5 × 10⁻⁵). Twenty-three unit tests cover the leak-free baselines, metric policies, bootstrap and conformal behaviour. The plan and code were hashed before the first confirmatory run, and every deviation (including the post-hoc E1 and the replaced customer-disjoint design) is logged in the plan. Details: `REPRODUCIBILITY.md`.

## 19. Limitations and threats to validity

*Construct validity.* WAPE favours median-type forecasts on sparse data; the 2 % minimum-relevant-gain threshold is a declared but arbitrary choice; the classification label is a proxy.
*Internal validity.* One random seed per model and one machine; seed variance was not estimated. A small hyper-parameter grid (≤ 2 variants per family) was used; stronger tuning could narrow the gap. Matched baselines use the same information staleness as the models, fresh baselines use more recent information — both are reported, but the choice of the "primary" reference is itself data-dependent (made on validation data).
*Statistical conclusion validity.* The crossed bootstrap is an approximation to two-way dependence, checked with the stationary bootstrap; the Diebold–Mariano test is exploratory on short aggregate series; the p-values of exactly 0 from 2000 draws are reported as "< 0.001". Six confirmatory tests were adjusted; exploratory results were not and are labelled.
*External validity.* Two Walmart stores (350-series subsets) and one UK wholesaler's top 100 SKUs; retail only; all public. No data from Indian SMEs or any real customer is used, and no conclusion should be transferred to them. M5 CA_1 and TX_1 are not independent samples of retail practice.
*Post-hoc analysis.* E1 was designed after seeing the confirmatory results; it is hypothesis-generating.
*Not evaluated.* Deep or foundation models, probabilistic forecasters, hierarchical reconciliation, promotion data, inventory-cost metrics, the M5 competition metric, other horizons, seed variance.

## 20. Declarations (to be completed by the authors)

* **Authors and affiliations:** not provided. **Corresponding author:** not provided.
* **Funding:** none stated in the project materials; the authors must declare it.
* **Competing interests:** none stated; the authors must declare it.
* **Author contributions (CRediT):** to be assigned by the authors.
* **Ethics:** only public, secondary, non-interventional data are used; no ethics approval is claimed or needed to be claimed by this draft — the authors and venue decide.
* **Data availability:** M5 (Makridakis et al., Kaggle competition data) and Online Retail II (UCI repository) are public; their licence terms must be confirmed by the authors before redistribution (recorded in `inventory/experiment_inventory.json`; the raw files are not redistributed here). Stored predictions, selections and analysis outputs are in `research/forecast_study_v1/results/`.
* **Code availability:** `research/forecast_study_v1/` (hashes in `FREEZE.json`).
* **Use of generative AI:** the study code, analysis scripts and this draft were prepared with an AI coding assistant (Claude) under the project owner's direction. Venues such as Elsevier journals require a declaration of generative-AI use in manuscript preparation; the authors must review all text and make the declaration.

## 21. Conclusion

For intermittent retail demand, whether a boosted-tree forecaster beats simple baselines is not settled by the model: against the strongest validation-selected baseline and with dependence-aware uncertainty, the pre-specified comparison on item-day pooled WAPE was not supported in any of six cells, while the same models were three times better at the store-day level on M5. The choice of baseline strength, metric and aggregation level should be reported and justified before claims of superiority are made. Within the learned model, calendar and history-statistic features carried the measurable gain; price features did not. On an inactivity proxy label, a learned classifier modestly out-discriminated a recency rule, and a validation-fitted calibrator failed when prevalence shifted.

## 22. References (verified records only; see `LITERATURE_REVIEW.md` for verification marks)

* Angelopoulos, A. N., & Bates, S. (2023). Conformal prediction: A gentle introduction. *Foundations and Trends in Machine Learning*, 16(4), 494–591. doi:10.1561/2200000101
* Ansari, A. F., et al. (2024). Chronos: Learning the language of time series. *Transactions on Machine Learning Research*; arXiv:2403.07815.
* Bergmeir, C., & Benítez, J. M. (2012). On the use of cross-validation for time series predictor evaluation. *Information Sciences*, 191, 192–213. doi:10.1016/j.ins.2011.12.028
* Bojer, C. S., & Meldgaard, J. P. (2021). Kaggle forecasting competitions: An overlooked learning opportunity. *International Journal of Forecasting*, 37(2), 587–603. doi:10.1016/j.ijforecast.2020.07.007
* Chen, T., & Guestrin, C. (2016). XGBoost: A scalable tree boosting system. *Proc. KDD '16*. doi:10.1145/2939672.2939785
* Croston, J. D. (1972). Forecasting and stock control for intermittent demands. *Journal of the Operational Research Society*, 23(3), 289–303. doi:10.1057/jors.1972.50
* Damato, S., Rubattu, N., Azzimonti, D., & Corani, G. (2026). Intermittent time series forecasting: local vs global models. arXiv:2601.14031 (preprint, not peer reviewed when read).
* Diebold, F. X., & Mariano, R. S. (1995). Comparing predictive accuracy. *Journal of Business & Economic Statistics*, 13(3), 253–263. doi:10.1080/07350015.1995.10524599
* Fildes, R., Ma, S., & Kolassa, S. (2022). Retail forecasting: Research and practice. *International Journal of Forecasting*, 38(4), 1283–1318. doi:10.1016/j.ijforecast.2019.06.004
* Gibbs, I., & Candès, E. (2021). Adaptive conformal inference under distribution shift. *Advances in Neural Information Processing Systems*, 34. arXiv:2106.00170
* Guo, C., Pleiss, G., Sun, Y., & Weinberger, K. Q. (2017). On calibration of modern neural networks. *Proc. 34th ICML*, PMLR 70, 1321–1330.
* Hewamalage, H., Ackermann, K., & Bergmeir, C. (2023). Forecast evaluation for data scientists: common pitfalls and best practices. *Data Mining and Knowledge Discovery*, 37(2), 788–832. doi:10.1007/s10618-022-00894-5
* Holm, S. (1979). A simple sequentially rejective multiple test procedure. *Scandinavian Journal of Statistics*, 6(2), 65–70.
* Hyndman, R. J., & Koehler, A. B. (2006). Another look at measures of forecast accuracy. *International Journal of Forecasting*, 22(4), 679–688. doi:10.1016/j.ijforecast.2006.03.001
* Januschowski, T., Wang, Y., Torkkola, K., Erkkilä, T., Hasson, H., & Gasthaus, J. (2022). Forecasting with trees. *International Journal of Forecasting*, 38(4), 1473–1481. doi:10.1016/j.ijforecast.2021.10.004
* Ke, G., et al. (2017). LightGBM: A highly efficient gradient boosting decision tree. *Advances in Neural Information Processing Systems*, 30.
* Kolassa, S. (2020). Why the "best" point forecast depends on the error or accuracy measure. *International Journal of Forecasting*, 36(1), 208–211. doi:10.1016/j.ijforecast.2019.02.017
* Künsch, H. R. (1989). The jackknife and the bootstrap for general stationary observations. *The Annals of Statistics*, 17(3), 1217–1241. doi:10.1214/aos/1176347265
* Makridakis, S., Spiliotis, E., & Assimakopoulos, V. (2022a). M5 accuracy competition: Results, findings, and conclusions. *International Journal of Forecasting*, 38(4), 1346–1364. doi:10.1016/j.ijforecast.2021.11.013
* Politis, D. N., & Romano, J. P. (1994). The stationary bootstrap. *Journal of the American Statistical Association*, 89(428), 1303–1313. doi:10.1080/01621459.1994.10476870
* Prokhorenkova, L., et al. (2018). CatBoost: unbiased boosting with categorical features. *Advances in Neural Information Processing Systems*, 31, 6638–6648.
* Saito, T., & Rehmsmeier, M. (2015). The precision-recall plot is more informative than the ROC plot when evaluating binary classifiers on imbalanced datasets. *PLOS ONE*, 10(3), e0118432. doi:10.1371/journal.pone.0118432
* Spiliotis, E., Makridakis, S., Semenoglou, A.-A., & Assimakopoulos, V. (2022). Comparison of statistical and machine learning methods for daily SKU demand forecasting. *Operational Research*, 22(3), 3037–3061. doi:10.1007/s12351-020-00605-2
* Syntetos, A. A., & Boylan, J. E. (2005). The accuracy of intermittent demand estimates. *International Journal of Forecasting*, 21(2), 303–314. doi:10.1016/j.ijforecast.2004.10.001
* Tashman, L. J. (2000). Out-of-sample tests of forecasting accuracy: an analysis and review. *International Journal of Forecasting*, 16(4), 437–450. doi:10.1016/S0169-2070(00)00065-0
* Teunter, R. H., Syntetos, A. A., & Babai, M. Z. (2011). Intermittent demand: Linking forecasting to inventory obsolescence. *European Journal of Operational Research*, 214(3), 606–615. doi:10.1016/j.ejor.2011.05.018

*Datasets:* M5 Accuracy competition data (Walmart); Online Retail II, UCI Machine Learning Repository (donor citation, licence and access terms to be confirmed by the authors; see Section 20).

**Appendices (separate files in this directory):** A. `EXPERIMENT_PLAN.md` (pre-registration and deviations log); B. `results/TABLES.md` (all generated tables incl. segments, conformal coverage, leave-one-out, S2 details); C. `EVIDENCE_CLAIM_MATRIX.md`; D. `REPRODUCIBILITY.md`; E. `RESEARCH_AUDIT.md`, `LITERATURE_REVIEW.md`; F. figures `manuscript/figures/fig1–4.svg` (forest plot of H1/H2; pooled vs aggregate WAPE; segment plot; conformal coverage by origin).
