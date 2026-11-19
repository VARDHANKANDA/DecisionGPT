# PREREGISTRATION_DRAFT (not submitted)

**Status.** A draft prepared for a possible public registration (e.g. OSF or AsPredicted). **Nothing has been uploaded or registered.** The only existing record is the *internal* timestamped hash freeze `FREEZE.json`. If the authors register this draft **before** the confirmatory test stage is run, the study can be described as *pre-registered*; otherwise it must be described as *pre-specified and internally frozen*. Registering after the outcomes exist is not pre-registration.

**Instructions for the authors (not performed here).** 1) Review `EXPERIMENT_PROTOCOL.md` and this draft. 2) Create the registration on the chosen registry and attach `EXPERIMENT_PROTOCOL.md`, `WINDOW_USE_AUDIT.md` and `FREEZE.json` (hash list). 3) Record the registry's time stamp in `DEVIATIONS.md`. 4) Only then run stage `test` (`run_v2.sh test`). Do not register data that the dataset terms forbid redistributing (M5); the registration needs descriptions and hashes, not data.

## 1. Study information
Title (working): *Item-day and aggregated forecast error of boosted models and simple baselines on retail demand: an endpoint-matched evaluation on unscored windows.* Authors: to be completed by the authors. Description: a quantitative comparison of validation-selected gradient-boosting direct forecasters with 31 prespecified simple baselines on M5 (CA_1, TX_1, WI_1) and Online Retail II.

## 2. Hypotheses
H1, H1b, H2, H3 as in `EXPERIMENT_PROTOCOL.md` §2 (two-sided, per cell, 8 confirmatory cells). H4 descriptive.

## 3. Design plan
Observational secondary data; no intervention. Rolling-origin evaluation: six 28-day test blocks per window, three validation blocks before them; confirmatory window W2 (trailing 252–420 days removed before anything is built); replications W3 and W1.

## 4. Sampling plan
Existing public data. Entities: 350/350/349 department-stratified random series per M5 store (seed 20261015, first sale ≤ d_1100); 100 top-revenue SKUs for Online Retail II per window. No further data collection. Data already observed by the authors: W1 (extensively); W2/W3 entity targets were not scored by any experiment (`WINDOW_USE_AUDIT.md`).

## 5. Variables
Outcome: daily units. Predictors for the learned models: lagged demand, rolling statistics, calendar, listed price (M5), static identifiers. Methods compared: 8 candidate models and 31 baselines (`EXPERIMENT_PROTOCOL.md` §5–6).

## 6. Analysis plan
Endpoints, estimands, inference (crossed bootstrap B = 10,000 with a two-way cluster-robust secondary method; week-block bootstrap for the aggregate endpoint), Holm families, decision rules (SUPPORTED / CONTRADICTED / INCONCLUSIVE), dual-method rule, replication criteria, exploratory analyses: `EXPERIMENT_PROTOCOL.md` §3, §7–9.

## 7. Other
Known limitations: the authors' prior knowledge of v1 and audit results; period-level exposure of W2/W3; shared entities across windows; no statistical-model families beyond the baselines; CatBoost excluded; price-listing eligibility assumption. AI assistance: code, analysis and drafting were produced with an AI coding assistant; the authors are responsible for all content.
