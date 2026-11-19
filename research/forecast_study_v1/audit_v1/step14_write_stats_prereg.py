"""Step 14a: writes STATISTICAL_AUDIT.md and PREREGISTRATION_AND_DEVIATIONS.md (tables are generated from work/*.json)."""
import json
from pathlib import Path

AUD = Path(__file__).parent
W = AUD / "work"
s3, s7 = json.load(open(W / "step3.json", encoding="utf-8")), json.load(open(W / "step7.json", encoding="utf-8"))
CELLS = list(s3["cells"])
NAME = {"fs1_m5_ca1_H28": "M5 CA_1, H=28", "fs1_m5_ca1_H7": "M5 CA_1, H=7", "fs1_m5_tx1_H28": "M5 TX_1, H=28", "fs1_m5_tx1_H7": "M5 TX_1, H=7", "fs1_or2_top100_H28": "OR II, H=28", "fs1_or2_top100_H7": "OR II, H=7"}
pc = lambda x: f"{100 * x:+.1f}"  # noqa: E731
ci = lambda c: f"[{pc(c[0])}, {pc(c[1])}]"  # noqa: E731

# ------------------------------------------------------------------ STATISTICAL_AUDIT.md
tA = ["| cell | estimate % | study crossed CI | independent crossed CI | two-way cluster-robust (delta) CI | series-only CI | week-only CI | study Holm p | independent Holm p | verdict (study) | verdict (independent, bootstrap / delta) |", "|---|---|---|---|---|---|---|---|---|---|---|"]
for c in CELLS:
    h = s3["cells"][c]["H1"]
    hh = s3["holm"]["H1"][c]
    tA.append(f"| {NAME[c]} | {pc(h['point'])} | {ci(h['study_reported']['ci95'])} | {ci(h['pigeonhole_independent']['ci95'])} | {ci(h['cgm_twoway_delta']['ci95'])} | {ci(h['series_only_bootstrap']['ci95'])} | {ci(h['week_only_bootstrap']['ci95'])} | "
              f"{hh['study_holm_p']:.3f} | {hh['independent_holm_p']:.3f} | {hh['study_verdict']} | {hh['independent_verdict_bootstrap']} / {hh['independent_verdict_cgm']} |")
tH2 = ["| cell | estimate % | study verdict | independent verdict (bootstrap / delta) | independent Holm p |", "|---|---|---|---|---|"]
for c in CELLS:
    h = s3["cells"][c]["H2"]
    hh = s3["holm"]["H2"][c]
    tH2.append(f"| {NAME[c]} | {pc(h['point'])} | {hh['study_verdict']} | {hh['independent_verdict_bootstrap']} / {hh['independent_verdict_cgm']} | {hh['independent_holm_p']:.4f} |")
tD = ["| cell | series x week cells | effective independent cells (approx.) | design effect on the s.e. (two-way / naive iid) | lag-1 autocorrelation of weekly differential | pigeonhole s.e. / delta-method s.e. |", "|---|---|---|---|---|---|"]
for c in CELLS:
    d = s3["cells"][c]["dependence"]
    tD.append(f"| {NAME[c]} | {d['cells']} | {d['effective_independent_cells_approx']:.0f} | {d['design_effect_cgm_se_over_iid_se']:.1f} | {d['weekly_differential_lag1_autocorrelation']:.2f} | {s3['cells'][c]['H1']['ratio_pigeonhole_se_over_cgm_se']:.2f} |")
sim = s3["simulation"]
tS = ["| simulation (S=300 series, W=24 week blocks, true improvement 0) | crossed (pigeonhole) bootstrap | series-only bootstrap | two-way delta method |", "|---|---|---|---|"]
for k, lab in (("week_shock_0.15", "week-level shock sd 0.15"), ("week_shock_0.40", "week-level shock sd 0.40")):
    v = sim[k]
    tS.append(f"| {lab}: empirical coverage of the nominal 95% interval ({v['reps']} replications) | {v['coverage_95']['pigeonhole']:.3f} | {v['coverage_95']['series_only']:.3f} | {v['coverage_95']['cgm']:.3f} |")
    tS.append(f"| {lab}: mean interval width | {v['mean_width']['pigeonhole']:.3f} | {v['mean_width']['series_only']:.3f} | {v['mean_width']['cgm']:.3f} |")

STAT = f"""# STATISTICAL_AUDIT

Independent review of the study's inference, 2026-10-22. All numbers below were computed by audit code that does not import the study's code (`audit_v1/ind_core.py`, `step3_inference.py`). Author-reported values come from `results/*/analysis.json` and `CONFIRMATORY_SUMMARY.json`.

## 1. Unit of analysis and design

* **Statistic.** Relative WAPE improvement theta = 1 - sum|e_model| / sum|e_ref| over all (series, day) rows of the six 28-day test blocks. It is a ratio of sums: large-volume series dominate it.
* **Paired structure.** Model and baseline are scored on the *same* (series, day) rows (verified: identical row sets, S x 168 rows per cell), and the bootstrap resamples the paired (series, week) cell totals of both methods together. The pairing is correct at the unit that is resampled.
* **Resampling unit.** A bootstrap draw selects S series with replacement and, independently, W = 24 seven-day target blocks with replacement and recomputes the ratio on the selected sub-grid (a two-way "pigeonhole" resampling). Series are not independent (shared store calendar, events, shocks); weeks are not independent across the six retraining blocks (training windows of 730 days overlap heavily across origins).
* **What the design assumes.** Row and column effects are exchangeable, and interaction noise is independent across cells. The week dimension has only 24 units from 6 retraining blocks; autocorrelation of weekly differentials was small (lag-1 between -0.35 and 0.20, Table C) but is estimated from 24 points.

## 2. Independent recomputation of the confirmatory tests (H1)

Estimates, intervals and decisions were recomputed with (a) an independent re-implementation of the crossed bootstrap (B = 4000, different seed), (b) a different method, the delta-method (linearised) variance of theta with **two-way cluster-robust** (series and week) covariance, and (c) one-way bootstraps. Percent units; positive = model better.

{chr(10).join(tA)}

**Result.** Point estimates agree to the last printed digit. Interval endpoints agree with the study's within Monte-Carlo error (largest endpoint difference over all 12 H1/H2 intervals: 0.26 percentage points). The frozen decision rule gives the same verdict in all six cells under the independent bootstrap **and** under the delta method. The Holm-adjusted p-values agree (differences are Monte-Carlo noise).

**H2 (best baseline of any information set):**

{chr(10).join(tH2)}

H2 for M5 is contradicted in four cells and inconclusive on Online Retail II in both methods, as the manuscript says. On Online Retail II H=28 the best baseline overall is the matched one, so H1 and H2 are the same test there (the H2 family therefore contains one duplicated comparison).

**Borderline case.** M5 CA_1 H=28 (estimate -2.6 %): the crossed interval just includes zero (study p = 0.069; independent bootstrap p = 0.062; delta method p = 0.052, interval upper limit +0.03 %). The one-way (series-only and week-only) intervals both exclude zero, so the "inconclusive" label depends on using the crossed design. The label is correct under the frozen rule, but it is not a robust "no difference": treat it as "negative and close to the boundary".

## 3. Dependence structure and effective sample size

{chr(10).join(tD)}

The series-level clustering is strong (the variance of series means is several times the within-cell variance), so the effective number of independent cells is about one sixth of the nominal one on M5 and about one seventh on Online Retail II. A naive i.i.d.-cells interval would be 2.2-2.7 times too narrow. The pre-registered crossed bootstrap accounts for this; a series-only interval (the historical benchmark's design) does not account for common week effects and the independent simulation below shows how badly it can fail.

## 4. Does a bootstrap that passes unit tests have the right coverage? (simulation)

I simulated cell totals with known two-way dependence (series effects, week-level shocks that hit the model and the baseline differently, cell noise), with the true improvement equal to 0, and counted how often each 95 % interval contained the truth.

{chr(10).join(tS)}

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
"""
(AUD / "STATISTICAL_AUDIT.md").write_text(STAT, encoding="utf-8")

# ------------------------------------------------------------------ PREREGISTRATION_AND_DEVIATIONS.md
fz = json.load(open(AUD.parent / "FREEZE.json", encoding="utf-8"))
chg = [k.split("/")[-1] for k, v in s7["freeze_code_hash_status"].items() if v != "unchanged"]
PRE = f"""# PREREGISTRATION_AND_DEVIATIONS

Chronological audit of what was fixed when, 2026-10-22. Sources: `FREEZE.json`, file modification times of every artifact, the experiment run log (`run_all.log`, local time IST = UTC + 5:30), and the timestamps of the tool calls in the session transcript (UTC). **Limits:** file times are mutable; the transcript is the author's own record; there is no external registry entry, no git commit and no signed time-stamp (the study directory is untracked: `git log` for it is empty).

## 1. Chronology (UTC)

| time (UTC) | event | evidence |
|---|---|---|
| (earlier, 2026-10-15) | Frozen historical benchmark runs, including a single M5 CA_1 window d_1914-d_1941 and the Online Retail II inactivity task | `experiments/ml_benchmark_v1/` |
| 03:11:27 | `RESEARCH_AUDIT.md` written: the historical single-window results (e.g. seasonal naive 0.869, same-weekday mean 0.740, CatBoost 0.698 on M5 CA_1) were known to the author before the plan | transcript, file |
| 03:15:46-03:18:21 | `baselines.py`, `metrics.py`, `inference.py`, `protocol.py`, `run_forecast_study.py` written | file times |
| 03:22:21 | `EXPERIMENT_PLAN.md` first written (hypotheses H1-H7, decision rules) | transcript |
| 03:23:05 | `analyze.py` written | file time |
| **03:23:31** | **Quick smoke run of the runner on real data (ridge, one validation block, first test block 1773 of M5 CA_1)** - it scored a real test block | transcript tool call |
| **~03:24:19** | **Analysis and verification scripts run on that quick output; the author saw H1 estimate -13.7 % (ridge, one block) and conformal coverage before the freeze** | transcript |
| 03:24:37 | `verify_cell.py` key-lookup fixed | file time |
| 03:25:11 / 03:26:05 | Plan edited (S2 addendum; Platt/isotonic policy) | transcript |
| **03:26:09** | **Quick smoke run of the classification study (both origins' test snapshots scored; paired AUC differences printed)** | transcript |
| 03:29:10 | `ablation_report.py` syntax check | file time |
| **03:29:26-27** | **Freeze: `make_freeze.py` run, `frozen_utc` 2026-10-22T03:29:27Z, git head 41c1d14, SHA-256 of plan, 14 code/test files** | `FREEZE.json` |
| 03:29:36 | `run_all.sh` created and launched (first cell starts 08:59:38 IST) | log |
| 03:29:46-03:29:52 | Deviation note added to plan (run_all.sh, make_freeze.py); `plan_sha256_text_above_deviations_log` added to FREEZE | transcript |
| 03:42:23 / 03:42:24 | M5 CA_1 H=28: `selection.json` written; first test-block fit 1 s later | file times |
| 03:58:58 | First cell analysed: H1 inconclusive/contradicted pattern and the median/bias explanation became known; the remaining five cells had not yet been selected or fitted | transcript |
| 04:00:54 ... 04:59:46 | Cells 2-6 run sequentially (selection files written 0-2 s before the first test fit in each cell) | file times |
| 05:00:03 | Confirmatory summary (Holm over six tests) written | file time |
| 05:03:52 | Ablations (H5) complete | file time |
| **05:04:36-05:08:00** | **Post-hoc E1 (L1-objective refit) designed, written and run - after all six confirmatory cells were analysed; plan deviation note added at 05:04:38** | transcript, file times |
| 05:08:03 | S2 main run complete; its customer-disjoint block reports "unsupported" (vacuous design) | `results.json` |
| 05:08:38-05:09:23 | `s2_customer_disjoint.py` written, deviation logged (05:08:40), run | transcript |
| 05:10:23 | `make_report.py` (tables/figures) written and run | file time |
| 05:15:07 | Manuscript assembled | file time |

## 2. Does the evidence support "model selection was completed before test evaluation"?

**Yes, with caveats.** In every cell, `selection.json` was written 0-2 seconds before the first `fits/test_*.npy` and after all 27 validation fits (file times, table above); the runner code (`run_forecast_study.py`) writes the selection to disk before it constructs any test-block row; selection uses validation WAPE only (checked by the study's verifier and re-derivable from the validation numbers stored in `selection.json`). Caveats: (i) timestamps are mutable and self-generated; (ii) each cell's selection was automated by code frozen earlier, so no human choice could depend on test numbers - but cells 2-6 were selected after the results of cell 1 had been seen by the author; (iii) selection happens **inside** each run, so the claim is about the run's internal order, not about an independently witnessed sequence.

## 3. Is the study "pre-registered"?

* **Frozen before the confirmatory runs:** yes (plan text above the deviations log and 14 code/test file hashes match `FREEZE.json` today: plan-text hash match = {s7['plan_text_above_deviation_log_hash_matches_freeze']}; files changed since the freeze: {', '.join(chg)} (the plan changed only in its deviations log); added after the freeze: `exploratory_l1.py`, `s2_customer_disjoint.py`, `make_report.py`, `run_all.sh`, all disclosed or reporting-only).
* **Pre-registered in the usual sense (externally time-stamped, publicly registered):** **no.** The freeze is a local self-generated record. The manuscript's wording "pre-registered" overstates this; use "pre-specified and internally frozen before the confirmatory runs (hashes in FREEZE.json); not registered with an external registry".
* **Blind to the data:** **no.** (a) Two quick smoke runs scored real test data before the freeze (forecasting: ridge on the first M5 CA_1 test block; S2: both origins, with a printed AUC difference). The outputs were deleted but seen; no plan element changed afterwards except as logged. (b) The author already knew the historical single-window results on the same M5 CA_1 final block. (c) The study's primary-model family (mean-targeting objectives only) was fixed with that background.
* These do not invalidate the numbers, which are fully reproducible from the stored files, but they limit the weight of "pre-registered" and must be disclosed.

## 4. Deviations and post-hoc analyses (all in `EXPERIMENT_PLAN.md` section 11)

| item | declared? | audit judgement |
|---|---|---|
| `run_all.sh` / `make_freeze.py` added after the freeze (orchestration only) | yes | acceptable |
| **E1 post-hoc L1 refit** (conceived after the first cell's results at about 03:58Z and executed after all cells at 05:04Z) | yes, labelled post hoc, exploratory, not in H1/H2 | acceptable and correctly separated. The **idea** arose from the first cell's results (median baseline wins; bias) - state this in the paper. Do not promote it to confirmatory. |
| S2 customer-disjoint design found **vacuous** (every customer seen before a cutoff is in that cutoff's snapshot, so removing test customers leaves no training data) and replaced by a random 50/50 customer split | yes | acceptable; the original block still reports "unsupported" in `results.json` (kept, not overwritten) |
| Smoke-run exposure before the freeze (Section 3) | **not declared** in the plan | add to the plan's deviation/disclosure log (audit does not edit the frozen plan; recommended wording in BLOCKER_CHECKLIST) |
| `make_report.py` extended and the figure legend fixed after seeing results | partly (reporting-only) | presentation only; no analysis change |
| Terminology "origins/horizon/store-day" and the M5 window description | n/a | editorial/factual (BLOCKER_CHECKLIST) |

## 5. The customer-level sensitivity split: chronology and independence

* **Chronology preserved:** yes - the models, calibrators and the threshold use only earlier (training and validation) snapshots of G1 customers; the test snapshot (later cutoff) is scored on G2 customers.
* **Customer independence:** random 50/50 split of customers; no customer appears on both sides. Customers are not independent in time-varying effects (shared season/market), but that is the same at any split.
* **Limits:** half of the data in each role (train 5,085 / validation 2,291 / test 2,477 at origin A) widens the intervals; the origin-A advantage (ROC-AUC +0.011 [-0.006, +0.028]) is then indistinguishable from zero and the PR-AUC difference is -0.002; the origin-B result (+0.041 [0.030, 0.053]) holds. The sensitivity run was **not independently re-executed** in this audit (it requires refitting four models), so its numbers are author-reported, consistent with the main run.

## 6. Verification of hashes (exact results, repository commands)

* `python research/r4/audit/verify_historical_freeze.py` -> "OK - all 22 historical artifacts unchanged since freeze at 2026-09-23T22:45:00Z."
* All 20 files listed in `experiments/ml_benchmark_v1/HISTORICAL_HASHES.json` match; `HISTORICAL_HASHES.json` has the SHA-256 recorded in `FREEZE.json`.
* `experiments/experiment_manifest.json` SHA-256 = 94aa419c703b1babb465975463b26e55255755a7687ecbecadb6db4c4c15cbff (equals the repository's frozen value).
* Study files vs `FREEZE.json`: unchanged except `EXPERIMENT_PLAN.md`, whose text above the deviations log matches `plan_sha256_text_above_deviations_log`.
* The audit changed no protected file: the SHA-256 of {len(json.load(open(AUD / 'protected_snapshot_before.json')))} protected files was recorded before the audit and compared after it (AUDIT_LOG.md).
"""
(AUD / "PREREGISTRATION_AND_DEVIATIONS.md").write_text(PRE, encoding="utf-8")
print("wrote STATISTICAL_AUDIT.md, PREREGISTRATION_AND_DEVIATIONS.md")
