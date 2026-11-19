# PROPOSAL — adding ETS, ARIMA and Theta baselines on a fresh confirmatory window (NOT RUN)

Status: **proposal only.** No code was written for it, nothing was installed, no outcome was computed. Written 2026-10-22 after the v2 results were known; it therefore cannot be pre-registered "blind", and the author must decide whether to run it.

## 1. Are ETS / ARIMA / Theta necessary for a credible paper?

| consideration | assessment |
|---|---|
| Logical necessity for the paper's *stated* claim | **No.** The claim is limited to "the best of 31 prespecified simple baselines with matched information" and the manuscript says so (H1b caveat, Limitations). Adding models would not make that statement more or less true. |
| Likelihood that expert reviewers ask for them | **High at a forecasting venue (IJF), moderate-to-high at TMLR.** "Best simple baseline" is read by forecasters as including exponential smoothing and ARIMA-family models; the M5 report compares ML methods with statistical benchmarks (it reports its top-performing methods clearly better than those benchmarks on its own metric; pre-publication copy). Their absence is the most obvious gap in the design. |
| Expected effect on the conclusions | **Unknown; no evidence in this package.** The baseline set already contains the intermittent-demand family (Croston, SBA, TSB) and seasonal means/medians. ETS/ARIMA/Theta on daily, mostly-zero counts may be poorly suited, but that is a hypothesis, not a finding. They could narrow the item-day gain or leave it unchanged; either outcome is informative. |
| Cost | Moderate: per-series, per-block local fits (about 350 series × 9 blocks × 2 horizons per store per family) and a new package (statsmodels and/or statsforecast), whose installation was not authorised in this session. |
| Recommendation | **Run it if the target is IJF or any forecasting-methodology venue, or if the paper's headline is to be "beats the best baseline" without the qualifier.** If the paper is positioned as a scoped, endpoint-matching and negative-result-reversal note (TMLR), the present limitation statement may suffice, but expect the request. |

## 2. Is a fresh, untouched confirmatory window available? (checked in the repository and raw data, 2026-10-22)

* **Existing windows are all used.** W2 and W3 for CA_1, TX_1, WI_1 and Online Retail II W2 are the confirmatory/replication sets of this study; W1 is the v1 window. **Running new baselines on them would be a post-hoc extension and must be labelled "post-hoc sensitivity analysis on already-examined windows" — never "unseen" and never merged into a confirmatory family.**
* **M5 has 10 stores; only CA_1, TX_1, WI_1 were used here** (raw file check: CA_1–CA_4, TX_1–TX_3, WI_1–WI_3). Per `WINDOW_USE_AUDIT.md`, the only earlier scoring of other stores was the retired benchmark's 40 series (test region days 1,649–1,940, i.e. the W1 period), so **seven stores (CA_2, CA_3, CA_4, TX_2, TX_3, WI_2, WI_3) are entity-fresh for every window if the 40 retired-benchmark series are excluded.**
* **A fresh period exists for M5: W4 = offset 756 days** (truncate 756 trailing days; T′ = 1,185; validation + test span ≈ 2013-08-19 → 2014-04-27). Its target days were never scored for any entity in the repository (they were only training rows in W2/W3/W1 fits). History is sufficient (730-day training window plus features).
* **Online Retail II has no fresh window:** 739 days, W1/W2 used, W3 infeasible. It cannot be part of a new confirmatory family.
* **Caveat that cannot be removed:** the design is now informed by the v2 results, and period-level knowledge (public M5 results) exists. "Untouched" here means *no target value of the evaluated entity-period was scored or used for any decision*, not blind to the earlier findings.

## 3. Proposed design (to be frozen BEFORE any new data is read)

* **Confirmatory family:** the seven fresh stores × window **W4** (entity-fresh and period-fresh) × H ∈ {28, 7} = 14 cells; 350 department-stratified series per store drawn with a new seed fixed in the protocol, excluding the 40 retired-benchmark series. **Replication family:** the same seven stores × W2 (entity-fresh, period examined).
* **Models and baselines:** unchanged candidates and the 31 baselines, **plus six statistical baselines** — ETS (additive/multiplicative error and trend, damped trend, weekly seasonality, AICc selection within the training window, forecasts clipped at 0), ARIMA (seasonal period 7, stepwise AICc search with fixed order caps, clipped at 0) and Theta (seasonal period 7) — each in two information sets: *matched-or-stale* (fitted with history through o − H, forecasts for horizons H … H + 27, never fresher than the models) and *fresh* (fitted through o − 1). Package, version and options fixed in the freeze; fit failures fall back to the seasonal-naive forecast and are counted and reported per series.
* **Selection (validation only, per endpoint):** the best baseline of the expanded set (37) and the best of the original 31 are both recomputed from the three validation blocks; the models are selected as before.
* **Hypotheses and rules (unchanged):** H1/H1b/H2/H3 per cell; Holm within family; 2 % minimum improvement; ≥ 4 of 6 blocks; dual-method rule; paired crossed bootstrap B = 10,000 (item-day) and iid-week bootstrap with stationary secondary (subset-day). **Primary comparison = best matched baseline of the expanded set;** the comparison with the original 31 is reported alongside. Because the supplementary analysis showed the iid-week bootstrap ignores weekly autocorrelation, report the stationary-bootstrap and autocorrelation diagnostic for H3 in the main table (declared in advance; the decision rule itself does not change).
* **Pooling across stores (secondary, declared in advance):** random-effects meta-analysis of the seven store-level improvements per H, with a pre-freeze simulation of its coverage before use; if the simulation fails, only per-cell results are reported.
* **Reporting:** all cells and all baselines, including those where statistical models win; pass/fail is not conditioned on the result.
* **Freeze and timestamp:** new `FREEZE.json` (code, protocol, series-sampling seed, package versions); the authors should additionally deposit the protocol in a public time-stamped registry before the first W4 outcome is read.

## 4. Approvals and costs (nothing has been done)

1. Authorisation to install `statsmodels` and/or `statsforecast` (and `scipy` already present) in the project environment.
2. Compute: a pilot on validation blocks of one store to measure per-series fit time before committing; the full run is expected to be of the order of hours to tens of hours on this machine (4 cores) — to be measured, not assumed.
3. Author decisions: confirm the store list and W4, the primary comparison, and whether to pre-register publicly.

## 5. What would change the manuscript

* Models still beat the expanded baseline set at item-day on W4 → the item-day claim is strengthened and the limitation on statistical baselines is removed for these data.
* A statistical baseline matches or beats the model → the manuscript's headline must be restated; the endpoint-matching finding (bias and aggregation) is unaffected.
* Mixed or inconclusive → reported as such; no additional model search.
