# PREREGISTRATION_AND_DEVIATIONS

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

* **Frozen before the confirmatory runs:** yes (plan text above the deviations log and 14 code/test file hashes match `FREEZE.json` today: plan-text hash match = True; files changed since the freeze: EXPERIMENT_PLAN.md (the plan changed only in its deviations log); added after the freeze: `exploratory_l1.py`, `s2_customer_disjoint.py`, `make_report.py`, `run_all.sh`, all disclosed or reporting-only).
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
* The audit changed no protected file: the SHA-256 of 543 protected files was recorded before the audit and compared after it (AUDIT_LOG.md).
