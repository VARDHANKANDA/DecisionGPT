# AUDIT_SUMMARY — independent scientific audit of `forecast_study_v1`

Audit date: 2026-10-22. Scope: the study, its results, its manuscript draft and its submission package. Full evidence is in the files listed at the end. **Independence caveat:** the audit was run by the same AI assistant that wrote the study, with separate code that imports nothing from the study; it is procedurally but not authorially independent (blocker A6). Nothing was changed, re-run, committed, uploaded or submitted; 543 protected files were hashed before and after (0 differences).

## Final verdict

# B. REVISE BEFORE SUBMISSION

**Justification.** The numbers are right and the study is reproducible from its stored files: every evaluation target equals the raw data, all 16 baselines re-implemented independently match on every row, 458 of 460 manuscript numbers recompute exactly (the other two are interval endpoints within bootstrap noise), and all twelve H1/H2 verdicts reproduce under an independent bootstrap and under a different variance method. The negative primary result is honestly reported. But the **contribution as written is not defensible**: its central finding is an instance of known theory that the manuscript largely does not cite, the primary comparison was close to determined by design, three claims (aggregation level, interval coverage, "pre-registered") are mis-characterised, one factual statement about M5 is wrong, and the M5 data terms conflict with the manuscript's "all predictions are provided". These are correctable, so the verdict is B, not C; they are numerous and substantive enough that it is not A.

## 1. Does the evidence support the central claim?

**The reported primary finding is supported as stated** (LightGBM/Tweedie did not beat a trailing 28-day median on pooled item-day WAPE in any of six cells: contradicted in three, inconclusive in three; rankings reverse at aggregate levels). What it **means** is narrower than the manuscript says:

* **Established (prior literature, verified at metadata/abstract level):** the optimal point forecast depends on the scoring function, and absolute error is minimised by a median (Gneiting 2011); the "best" point forecast depends on the error measure (Kolassa 2020); common error measures can rank forecasters wrongly on intermittent demand (Prestwich et al. 2014; Hyndman & Koehler 2006); boosted trees are strong on M5 (M5 article: LightGBM used by all of the top-50 teams).
* **Plausible interpretation supported by the audit data:** the aggregate-level reversal is mostly the baseline's level bias (aggregate WAPE exceeds |bias| by 0.008 for the median on M5), the ranking already reverses at item-week level in all six cells, and the learned model gains mainly on frequent/high-volume series (M5 CA_1 only).
* **Genuinely new (modest):** a quantification on three public datasets under a dependence-aware paired design with matched and fresh baselines, plus the conformal-coverage-by-zero/positive-demand finding. No new method or principle.

Of the four possible contributions in the brief, the defensible one is **(2) an analysis of how metrics and aggregation level change rankings for intermittent retail demand, presented as an empirical illustration**. (1) is the same finding stated more generally, (3) is only weakly supported (exploratory, one store), and (4) "a narrower finding" is what the evidence actually shows. As a methodological contribution it is **not sufficient by itself** for a forecasting research journal; it fits a correctness-first venue if narrowed, or a forecasting journal if the revision adds the matched-objective confirmatory arm and the positioning below.

## 2. Most important scientific findings

1. **The primary comparison was close to determined by design.** No candidate used an L1/quantile objective although pooled WAPE's Bayes-optimal forecast is a median; the matched-objective model exists only as the post-hoc exploratory run (E1), where it matches or beats the median baseline in pooled WAPE on 2 of 3 datasets (tie on TX_1; tie with the fresh baseline on M5) but loses the aggregate advantage on M5.
2. **The aggregation "reversal" is largely arithmetic and mis-described.** "Store-day" is a 350-series/100-SKU subset aggregate; item-week aggregation already reverses the ranking in all six cells; the median's aggregate WAPE is essentially its bias; the zero-forecast mechanism holds for M5 (54-69 % of rows) but not for Online Retail II (15-18 %; skewed order sizes).
3. **Interval coverage ~80 % hides conditional failure.** Zero-demand rows (54-63 % of M5 rows) are covered at 89-94 %; positive-demand rows only at 60-67 % (79 % on Online Retail II).
4. **Inference is sound but not conservative.** Independent two-way methods reproduce all intervals and verdicts; a simulation shows the crossed bootstrap covers about 90-93 % for a nominal 95 % (series-only: 25-58 %); one borderline cell (M5 CA_1 H=28; delta-method p = 0.052); printed Holm "< 0.001" is below the bootstrap's resolution.
5. **Pre-registration is internal, not blind.** Selection preceded test fits in every cell (0-2 s before the first test fit, after 27 validation fits), but the freeze is a local hash record, two smoke runs scored real test data before it, and the final M5 block had been seen in the historical benchmark.
6. **The inactivity study is weak evidence:** two origins share 94 % of customers; precision at fixed contact budgets differs from a recency rule by 0-2 points; the origin-A advantage is not distinguishable from zero in a half-customer check; calibration deterioration at origin B is explained by prevalence shift (oracle intercept shift: ECE 0.126 -> 0.019). The target is inactivity, not churn, and the manuscript says so.

## 3. Five most important blockers (ranked)

| # | Blocker | Type | What resolves it |
|---|---|---|---|
| 1 | **S1 - Novelty and design mismatch** (known theory largely uncited; no metric-matched candidate; headline presented as discovery) | scientific | Cite Gneiting 2011, Prestwich et al. 2014, Kolassa 2016/2020 (after reading); reframe as an empirical illustration; optionally a small pre-registered confirmatory arm with metric-matched objectives (needs approval) |
| 2 | **S2 - Aggregation-level finding mis-characterised** (subset not store; bias identity; item-week reversal; OR II mechanism wrong) | scientific | Rewrite Sections 10/17/21 with the four-level ladder and per-dataset mechanisms; rename the metric |
| 3 | **S3 - Interval claim hides zero-dominated coverage** | scientific | Report coverage separately for zero/positive demand and by segment; drop "near-nominal" |
| 4 | **A1 - M5 data terms** (non-commercial; no redistribution; IJF posts datasets; PLOS needs public data; abstract promises predictions) | administrative/legal | Do not publish M5-derived arrays; restructure the availability statement; seek written permission if sharing is wanted; Online Retail II is CC BY 4.0 |
| 5 | **S5/E1 - "Pre-registered" overclaim and undisclosed pre-freeze exposure; false statement that the last M5 block is the "official evaluation window"** (it is the public-leaderboard window; setting also differs from the competition) | scientific/editorial | Reword ("internally frozen, not externally registered"), disclose the exposures, correct the M5 sentence |

The complete list (S1-S6, E1-E8, A1-A6) with line references is in `BLOCKER_CHECKLIST.md`.

## 4. Checks: passed, failed, not performed

* **Passed:** targets vs raw data (6/6 cells); 16 baselines x 6 cells row-exact; no leakage in baselines (cutoffs precede targets; gaps 7/28 and 1..H); metric recomputation (458/460, 2 within noise); H1/H2 verdicts under two independent methods; Holm; segment labels from raw history; conformal coverage reproduced exactly; E1/ablation/segment numbers; inactivity labels, recency and customer sets from raw transactions; selection-before-test order; frozen-hash checks (20/20, 22 artifacts, manifest 94aa419c...); table/figure regeneration (byte-identical); fits equal stored predictions; 23 study unit tests; all 26 references' bibliographic data.
* **Failed / contradicted:** the M5 "official evaluation window" sentence (contradicted by the official data page); "store-day" terminology; "pre-registered" wording; Holm "< 0.001" precision; the single "zeros on most days" mechanism for Online Retail II; the abstract's unqualified L1 claim; one unsupported introductory generalisation.
* **Could not be performed / unverified:** model-fit re-execution; clean-environment reproduction; the customer-split sensitivity; the feature builder's leakage controls (beyond the study's own checks); full backend suite (1,760 passed/34 skipped is a historical report value); PLOS ONE fee; Guo et al. bin count; "Mondrian" attribution; page range of Prokhorenkova et al.; content of three cited secondary sources; independent human review.

## 5. Scientific vs editorial vs administrative

* **Scientific (change what the paper claims or tests):** S1-S6.
* **Editorial (wording, definitions, references, formatting):** E1-E8 (including the abstract length - 355 words vs PLOS ONE's 300 - and missing method details).
* **Administrative/legal:** A1-A6 (M5 terms, declarations incl. generative-AI use, reproducibility package, venue/fees, ethics statement, independence of review).

## 6. Is the main contribution defensible as written, and is another experiment justified?

* **As written: no.** It overstates novelty and generalises beyond three datasets; its mechanism and interval statements need correction. **After the corrections above, a narrowed empirical-illustration paper is defensible.**
* **Another confirmatory experiment: one small one is justified, none else.** A pre-registered arm in which the model's objective matches the metric (L1/quantile candidates selected on validation, plus a mean-optimal aggregate metric), on the same cells, would turn a design-determined result into evidence about when learned models add value. Estimated cost: roughly the E1 runtime per M5 cell (about 40-60 minutes in total on this machine) plus a new frozen plan. It must **not** be started without your approval and must not be used to relabel E1. More seeds are a cheaper, also useful, addition. No broader model search is recommended.

## 7. Smallest realistic path to submission readiness

1. **Decide** whether to add the matched-objective confirmatory arm (approval needed). If not, reframe explicitly as an empirical illustration.
2. **Revise the manuscript** (after your approval): positioning and references (S1, E5); aggregation section (S2); interval section (S3); wording and disclosure of pre-registration status (S5); M5 sentence and terminology (E1, E2); Holm reporting and simulation note (S6); abstract (E3); methods omissions (E4); move the inactivity study to an appendix (S4).
3. **Resolve data rights** (A1): written position on M5-derived arrays; availability statement; dataset citations.
4. **Authors complete the declarations** (A2, A5) and choose the venue after checking the unknown fees/limits (A4); TMLR is the best fit for the narrowed paper, IJF only if the novelty gap is closed (see `VENUE_READINESS.md`).
5. **Reproducibility package** (A3): requirements file, portable runner, freeze-verification script, one clean-environment run (approval needed), archive without M5 arrays.
6. **Human independent review** of the key conclusions and of `audit_v1/*.py` (A6).

## Files (all in `research/forecast_study_v1/audit_v1/`)

`AUDIT_SUMMARY.md` (this file), `METRIC_RECOMPUTATION.csv` (460 comparisons), `STATISTICAL_AUDIT.md`, `PREREGISTRATION_AND_DEVIATIONS.md`, `CLAIM_EVIDENCE_MATRIX.csv` (54 claims: 32 verified, 18 partially supported, 2 unverifiable, 1 unsupported, 1 contradicted), `REFERENCE_AND_DATA_RIGHTS_AUDIT.csv` (45 rows), `REPRODUCIBILITY_AUDIT.md`, `VENUE_READINESS.md`, `BLOCKER_CHECKLIST.md`, `AUDIT_LOG.md`, plus `FORECAST_DESIGN_AND_AGGREGATION_AUDIT.md` (sections 6-9 of the brief), the audit code (`ind_core.py`, `step*.py`), `work/` (intermediate JSON) and the two hash snapshots.
