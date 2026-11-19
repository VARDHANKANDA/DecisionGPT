# WINDOW_USE_AUDIT — have the proposed evaluation windows been used before?

Audit date 2026-10-22, before any v2 validation or test outcome for W2/W3 was read. "A date being earlier does not make it unseen": this audit therefore asks, for each activity in the repository that touched M5 or Online Retail II (OR II), **which days and which entities it scored or used**.

Windows (0-based day index; M5 T = 1,941, OR II T = 739). Scored span = three validation + six test blocks.

| window | M5 scored span (days / dates) | OR II scored span |
|---|---|---|
| W1 | 1,689–1,940 (2015-09-14 → 2016-05-22) | 487–738 (2011-04-02 → 2011-12-09) |
| W2 | 1,437–1,688 (2015-01-05 → 2015-09-13) | 235–486 (2010-07-24 → 2011-04-01) |
| W3 | 1,185–1,436 (2014-04-28 → 2015-01-04) | infeasible (too little history) |

## 1. Exposure by activity (what was found in the repository)

| activity | what it touched | W1 | W2 | W3 |
|---|---|---|---|---|
| Historical benchmark `experiments/ml_benchmark_v1` f1 (M5 CA_1 350-series subset) | validation origins d_1830/1858/1886 and test d_1914–1941 (`config.json`) | **scored** (inside W1 test blocks) | not scored | not scored |
| Historical f2 (OR II top-100 SKUs and total revenue) | last 28 days test, 3 validation blocks before | **scored** | not scored | — |
| `forecast_study_v1` (this project) | all W1 validation and test blocks; confirmatory, ablations, E1, S2 | **scored, repeatedly** | training rows only (target days 1,015–1,940 for the latest origins) | training rows only |
| `forecast_study_v1` segment statistics | ADI/CV² and volume terciles from the 365 days before the first W1 validation block (days 1,324–1,688) | — | descriptive summary only | partly (days 1,324–1,436) |
| `experiments/real_world_validation_v1` (OR II **total daily units**, all products, own-history backtest of the product's forecast methods; `bfs.MAX_ORIGINS = 12`, weekly origins, horizons 7/14/28) | the last 12 weekly origins ⇒ target days about T−105 … T−1 | **scored (aggregate level)** | not scored | — |
| Retired Training Center benchmark (`scripts/run_external_benchmarks.py --retired`, `external-m5-forecasting-benchmark`) | 40 M5 series (FOODS_3_090-type items across all nine stores) with a chronological 70/15/15 split of the 1,941 days (`chronological_split`): train ≤ day 1,357, validation 1,358–1,648, test 1,649–1,940; naive/linear/XGBoost | scored (test, other series) | validation region and the last 40 days of W2 as **test**, **for 40 other series** | validation region for days 1,358–1,436, **other series** |
| Retired Training Center benchmark on the repository's retired UCI Online Retail forecasting file (its exact relationship to Online Retail II was not verified) | 70/15/15 chronological split of the daily data | if the same calendar: test region | if the same calendar: training region | — |
| `ml/benchmark` p1 price identification | within-item fixed effects over days 0–1,912 (in-sample regression), then counterfactual at the last window | in-sample | in-sample regression only | in-sample regression only |
| Classification studies c1/S2 (Online Retail II customers) | customer inactivity labels with cutoffs between 2010-06-01 and 2011-09-10 | yes | uses transactions of W2's dates to build **customer** labels (a different target) | — |

## 2. Entity-level check (do the 350-series / 100-SKU sets overlap with anything that was scored?)

* The retired 40-series M5 benchmark has **no series in common** with the CA_1, TX_1 or WI_1 samples used here (ID comparison run during this audit: 0 shared series for CA_1, TX_1 and WI_1; its single WI_1 series, `FOODS_3_226_WI_1`, is not in the WI_1 sample).
* **WI_1 was never used by any forecasting experiment** in the repository (no code, result or document refers to it other than the raw files and that single series in the retired copy): for WI_1, even the original W1 window is fresh at the entity level.
* The OR II top-100 list is **re-selected for each window** from revenue before that window's first validation block (v1's list is reproduced exactly for W1; the W2 list is derived independently; both are checked by a unit test that recomputes the list from raw transactions).

## 3. Classification of each evaluation set for the confirmatory plan

| evaluation set | status | role in the plan |
|---|---|---|
| **W2 — M5 CA_1, TX_1, WI_1** | Targets of the evaluated entities were never scored as forecast targets by any experiment or used for any method decision; the *period* was used as training data, in descriptive statistics, and in a retired benchmark on disjoint series. | **Confirmatory** (primary), with this exposure disclosed. |
| **W2 — OR II** | Targets of the evaluated SKUs never scored; the daily **total** of all products was not scored in W2 either (the real-world validation covered only the last ~105 days); the period was training data in the retired UCI benchmark and the source of customer labels in the classification studies. Shorter training history (235–459 days). | **Confirmatory** (primary), flagged as the weakest cell (short history, one prior Christmas season at most). |
| **W3 — M5** | As W2; its validation region overlapped the retired benchmark's validation region on other series. | **Replication** (descriptive; sign-consistency), not part of the confirmatory Holm families. |
| **W1 — WI_1** | Fresh store at the final period; the final-period days were scored for other stores and series. | **Replication** (descriptive): entity-fresh but period-exposed. |
| **W1 — CA_1, TX_1, OR II** | Scored repeatedly (v1, E1, ablations, S2 sensitivity, the audit). | **Non-independent re-evaluation** of the new models for continuity with v1; never described as confirmatory. |

## 4. Residual exposure and how it is handled

1. **Design information from W1.** The candidate list (median-objective configurations) was suggested by the post-hoc W1 follow-up and by the audit; the confirmatory plan therefore does **not** claim to be blind to the earlier findings.
2. **Period-level knowledge.** Public M5 results and the author team's familiarity with the M5 dataset cannot be removed; no W2/W3 entity-level outcome was used for any choice.
3. **No W2/W3 result will be read before the freeze:** validation-stage and test-stage outputs for W2/W3/WI_1 are produced only after `FREEZE.json` is written (the pre-freeze dry runs use the already-scored OR II W1 validation blocks only).
4. **If a reviewer judges the exposure above too great,** W2/W3 results should be re-labelled replication; the plan's decision rules and reporting do not change.
