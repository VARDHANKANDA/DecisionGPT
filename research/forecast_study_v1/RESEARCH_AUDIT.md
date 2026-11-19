# Research audit: what the existing ML evidence supports (Stage A)

Study directory: `research/forecast_study_v1/` (new; nothing under `experiments/`, `models/` or `data/` is modified by this study).
Machine-readable companions: `inventory/experiment_inventory.json`, `inventory/artifact_fingerprints.json`, `audit/recompute_report.json`.
Repository state when audited: git `41c1d14` plus a large uncommitted working tree (see `inventory/experiment_inventory.json`, `working_tree_modified_paths`).

## 1. Scope and relation to earlier research directions

* `research/archive/` retired the earlier multi-agent R1-R5 programme; `research/ACTIVE_RESEARCH_PROGRAM.md` defines an LLM-evaluation programme that is **blocked** (no
  LLM provider, no real SME data). This study is a **separate, self-contained forecasting/classification evaluation track**. It does not replace or edit either.
* None of the findings here is evidence about DecisionGPT improving SME decisions. There is no real business-outcome data in the repository (0 outcome observations,
  0 stored business validation runs in the development database), so research direction D of the brief (decision-support reliability) is **not supported by evidence**
  and is not pursued.

## 2. Inventory (11 experiments; details in the JSON)

| ID | Experiment | Evidence class | Test sample | Stored predictions | Status |
|---|---|---|---|---|---|
| E1 | M5 CA_1, 350 series, direct H=28, 1 origin | public real | 9,800 points | yes | reproduced from predictions (max abs diff 5.2e-10) |
| E2 | Online Retail II revenue (1 series) and top-20 SKUs, H=28, 1 origin | public real | 28 / 560 | yes | reproduced from predictions (max abs diff 0.0) |
| E3 | Online Retail II 90-day **inactivity** classifiers | real, **proxy label** | 5,256 customers | no | rerun into a new directory (see section 5) |
| E4 | Synthetic platform churn | **synthetic label** | 1,200 | no | rerun into a new directory |
| E5 | Price-response identification | association only | n/a | no | not a prediction benchmark |
| E6 | Recompute of earlier baselines | n/a | n/a | n/a | max abs diff 0.0 (software versions differ from the originals) |
| E7 | Indian POS register, 1-day-ahead revenue, 5 models | real, provenance unverified | **12 days** | no | recomputed by E6 |
| E8 | Synthetic platform units, 5 models | synthetic | 4,280 | no | recomputed by E6 |
| E9 | Own-history backtests on 3 real public series | real | 14-112 points per horizon | no | stored as is |
| E10 | Registered naive/linear/XGBoost and churn models | synthetic | n/a | no | metrics read from manifests |
| E11 | Business-specific forecast / customer-score validation | none stored | n/a | n/a | services exist and are tested; **no real run exists** |

## 3. Findings about the existing evidence

Each finding states what was checked and what it implies for a defensible claim.

**A1. Single forecast origin (E1, E2).** Both forecast benchmarks score one 28-day window (days 1914-1941 of M5; the last 28 days of Online Retail II). Every
number is conditional on that window; seasonal level, promotions and holiday timing can move rankings. *Implication:* no claim about model ranking is defensible
from E1/E2 alone; a multi-origin design is required.

**A2. Uncertainty ignores dependence.** The stored paired comparisons resample **series only** (2,000 draws). Series in one store share calendar days, events,
SNAP days and store-level shocks, and each series has strong weekly seasonality, so the cluster bootstrap understates uncertainty. *Implication:* the stored CIs
may be too narrow; the new study uses a crossed series x time-block bootstrap (see `EXPERIMENT_PLAN.md`).

**A3. The strength of the baseline decides the headline.** On E1 (per-series WAPE, test window): seasonal naive (lag 28) 0.869, same-weekday mean of 4 weeks 0.740,
best learned model (CatBoost) 0.698, best ensemble 0.697. Against seasonal naive the learned models look 20% better; against the same-weekday baseline the best
single model is 5.6% better (MAE relative to the best baseline: +5.6% for the validation-selected CatBoost). *Implication:* any "ML beats baseline" statement must
name the baseline, and the strongest simple baseline must be the reference.

**A4. Aggregation level reverses the ordering (E1).** At the store-day aggregate level the same-weekday baseline has WAPE 0.067, lower than **every** learned model
(0.070-0.096; seasonal naive 0.109) and ensemble (0.076-0.078); per-series, the order is the opposite. Per-series WAPE (about 0.70) and aggregate WAPE (about 0.07) are different
quantities and must not be compared. *Implication:* report both, and state which question each answers (item-level replenishment vs store-level planning).

**A5. Very small test sets (E7, E9).** E7 has 12 test days and every model, including the baseline, has negative R2 (worse than predicting the test mean).
E9 has 14-112 correlated points per horizon. *Implication:* these cannot support a model ranking; they are descriptive. A minimum-evidence rule is adopted in the plan
(at least 30 series and 6 forecast origins for confirmatory learned-model comparisons).

**A6. Registered models are trained on synthetic data (E10).** `platform-forecasting-v1` and `platform-churn-v1` come from `scripts/generate_platform_data.py`. The
churn label is generated by a logistic mechanism from recency and tenure, which are also features, so ROC-AUC 0.79 measures recovery of the generator, not customer
behaviour. The manifests record MAE/RMSE/MAPE (forecast) and precision/recall/F1 at the default 0.5 cut-off plus ROC-AUC (churn); no PR-AUC, calibration, confusion
matrix, sample count, baseline MAE or zero-actual count was recorded. *Implication:* no claim about real customers or SMEs follows from E10.

**A7. Proxy label and entity overlap (E3).** The Online Retail II source has no churn field; the label is "no invoice in the 90 days after a cutoff". Training,
validation and test snapshots are temporally ordered (checked by `check_temporal_integrity`) but **the same customers appear in several snapshots**, so the split is
temporal, not group-disjoint. Predictions were not stored, so E3's metrics could not be recomputed independently without a rerun. *Implication:* claims are limited
to inactivity ranking on one retailer; a customer-unseen sensitivity analysis is added (`EXPERIMENT_PLAN.md`, S2).

**A8. Hyperparameter search is tiny and fixed.** Two variants per family (one for linear), selected on three consecutive 28-day validation windows. This is leakage-
safe but weak; differences between boosted-tree families (within about 0.8 WAPE points on E1) are inside any reasonable noise. *Implication:* do not rank the
boosted families; treat them as an equivalence class unless a paired test separates them.

**A9. Dataset licences and provenance.** Online Retail II and Online Retail: CC BY 4.0 (UCI page). M5 copy: Zenodo record 12636070; the licence label (CC BY 4.0) was set
by the uploader and was **not** verified against the competition rules. Indian POS register: Kaggle upload, CC BY-NC-SA 4.0, authenticity inferred, uploader gives
no store name. Indian e-commerce (Benroshan): CC0, provenance unverified, about 500 orders. *Implication:* the manuscript must state these caveats; the POS and
Benroshan sets are too short for global learned-model comparisons and are used only descriptively.

**A10. Leakage review of the historical feature builder.** `ml/benchmark/features.py` builds direct-horizon features whose history inputs end at the forecast origin
(`t - H`); calendar, event, SNAP and selling price are published in advance. `assert_no_future_leakage` perturbs the future and checks the history features are unchanged
(it is run in this study at every origin). One design choice deserves disclosure: training and scoring keep only rows where the item has a selling price on the target
day (i.e. the item is on sale). Assortment is known in advance, so this is not leakage, but it changes the population (items before launch are excluded).

**A11. Model-comparison and real-world-validation results are consistent with their code but are not rigorous evidence.** E7/E8 select the model by cross-validated
RMSE (test unused: good) but E7 has 12 test points; E9 uses a few overlapping origins and says so. Neither is a customer business.

**A12. Historical artifacts are intact.** 31 artifacts (the benchmark runs, model-comparison runs, real-world validation result, model registry index, dataset registry
and the frozen experiment manifest) were fingerprinted (`inventory/artifact_fingerprints.json`); the 20 hashes in `experiments/ml_benchmark_v1/HISTORICAL_HASHES.json`
match; the manifest sha256 `94aa419c...` is unchanged. A superseded run (`c2_20261015T073608Z_4598ea68`, wrong feature set) is kept and not used.

## 4. Independent verification already done

`audit/recompute_from_predictions.py` recomputes MAE, RMSE, WAPE, relative bias, zero share, aggregate-day MAE/WAPE, median-series WAPE and RMSSE (with an
independent RMSSE scale built from history strictly before the test window) from the stored prediction arrays and compares every stored metric:

* E1: 15 prediction arrays (12 methods and 3 ensembles) x 13 metrics, **max |difference| 5.2e-10**; the targets in the stored arrays equal the raw M5 values at those
  cells; the 28 test days are exactly the last 28 days of the file.
* E2: 2 tasks x 12 methods, **max |difference| 0.0** (RMSSE not recomputed: it needs the per-series history, which is not stored with the predictions).

## 5. Reproduction of the historical runs (regeneration, not recomputation)

`audit/rerun_historical.py` re-executes the historical runner for `c1`, `c2`, `f2`, `f1` with its output root redirected to
`audit/reruns/` (the frozen directory is never written). The comparison of regenerated against stored results is reported in `REPRODUCIBILITY.md` once the runs finish.
Software versions at rerun time are recorded in each rerun's `metadata.json`; the historical runs record python 3.12.0, numpy 2.5.2, pandas 3.0.5, scikit-learn 1.9.0,
xgboost 3.4.0, lightgbm 4.7.0, catboost 1.2.10.

## 6. Recommended research claim

The evidence supports only a **modest, empirical, protocol-focused contribution**, not a methodological innovation:

> On sparse daily retail demand, the apparent advantage of global gradient-boosted forecasters depends strongly on (i) which baseline is the reference, (ii) the
> aggregation level of the metric, (iii) the forecast origin, and (iv) how uncertainty is estimated. We evaluate this with a leakage-checked rolling-origin protocol,
> a dependence-aware paired bootstrap, an intermittent-demand baseline family and split-conformal intervals, on two M5 stores and one real retailer.

This is not claimed to be novel in method. Comparable evaluation-methodology work exists (see `LITERATURE_REVIEW.md`); any contribution is the combination of a strong
simple-baseline reference, a crossed series x time dependence-aware interval, per-segment reporting and a pre-registered, fully reproducible protocol on public data.
If the confirmatory results do not separate the learned models from the best simple baseline, that is the finding and it will be reported as such.

## 7. What is not supported and will not be claimed

* Anything about Indian SMEs, real customers' churn, business impact or decision quality.
* Calibrated churn probabilities (all scores are rankings; the label is a proxy or synthetic).
* A ranking among the boosted-tree families, or a benefit from ensembles, unless a pre-registered paired test supports it.
* Accuracy percentages: MAE, RMSE, WAPE and RMSSE are error measures.
