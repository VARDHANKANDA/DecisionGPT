# AGGREGATION_ANALYSIS — does the conclusion depend on the endpoint?

Source: `results/analysis/analysis_W2.json` (`ladder`, `endpoint_dependence`), `results/SUMMARY_EXTRA.md`. Window W2 (confirmatory). "Subset" = the 350 / 349 / 100 series evaluated in each dataset, not a store total. All WAPE values are pooled over the six test blocks.

## 1. The ladder (W2, selected models, point estimates)

Columns: item-day, item-week, subset-week, subset-day WAPE; relative bias = (Σŷ − Σy)/Σy. "L1 model" is the item-day-selected model (absolute-error objective in all eight cells); "subset model" is the subset-day-selected model (Tweedie 1.1 or squared error); "base" is the best matched baseline *for that endpoint*.

| cell | method | item-day | item-week | subset-week | subset-day | rel. bias |
|---|---|---|---|---|---|---|
| CA_1 H28 | L1 model | **0.739** | 0.518 | 0.346 | 0.346 | −0.346 |
| | best item-day base (trailing median 56) | 0.775 | 0.560 | 0.293 | 0.295 | −0.293 |
| | subset model (Tweedie 1.1) | 0.806 | 0.441 | 0.046 | **0.088** | +0.001 |
| | best subset-day base (weekday mean 4) | 0.849 | 0.454 | 0.074 | 0.114 | −0.007 |
| TX_1 H28 | L1 model | **0.755** | 0.558 | 0.394 | 0.394 | −0.394 |
| | best item-day base | 0.774 | 0.573 | 0.330 | 0.332 | −0.330 |
| | subset model (Tweedie 1.1) | 0.843 | 0.464 | 0.060 | **0.099** | −0.021 |
| | best subset-day base | 0.881 | 0.490 | 0.074 | 0.117 | +0.010 |
| WI_1 H28 | L1 model | **0.757** | 0.505 | 0.331 | 0.331 | −0.331 |
| | best item-day base | 0.783 | 0.534 | 0.289 | 0.290 | −0.289 |
| | subset model (squared error) | 0.831 | 0.433 | 0.047 | **0.092** | +0.020 |
| | best subset-day base | 0.855 | 0.450 | 0.052 | 0.100 | +0.003 |
| Online Retail II H28 | L1 model | **0.877** | 0.662 | 0.515 | 0.573 | −0.384 |
| | best item-day base | 0.931 | 0.691 | 0.500 | 0.572 | −0.329 |
| | subset model (Tweedie 1.1) | 1.053 | 0.706 | 0.312 | **0.482** | +0.085 |
| | best subset-day base | 1.135 | 0.765 | 0.402 | 0.511 | +0.115 |

(The H = 7 cells show the same pattern; full values in `results/analysis/analysis_W2.json` and `METRIC_RESULTS.csv`.)

## 2. What the ladder shows

1. **The item-day winner is a strongly downward-biased forecaster.** On M5 the item-day-selected absolute-error model has relative bias −0.29 … −0.39 and forecasts zero for 29–49 % of rows (the best matched baseline: bias −0.23 … −0.35, zero for 53–70 %). This is what the theory predicts for a median-type target on mostly-zero daily demand; it is not a defect of the code.
2. **Subset-day WAPE ≥ |relative bias|, with equality for the item-day model on M5** (e.g. CA_1 H28: 0.346 = 0.346). So when demand is aggregated over items and days, a forecaster that is good at the item-day median is penalised by its own level bias and loses to mean-type models by a factor of 3–4 (0.35–0.39 vs 0.08–0.10 on M5).
3. **The ordering by endpoint reverses.** At item-day, the absolute-error model is best (0.739); the original Tweedie model is worse than the best baseline (0.806 vs 0.775 matched). At subset-day, the Tweedie / squared-error models are best (0.088) and the item-day winner is worse than its own baseline (0.346 vs 0.295). The same family can be the best or the worst forecaster depending on the endpoint; the endpoint is a design choice that has to match the decision the forecast supports.
4. **Item-week and subset-week are intermediate:** the mean-type models already win at item-week (0.441 vs 0.518 for CA_1 H28).
5. **Online Retail II** behaves differently: subset-day WAPE is high for every method (0.46–0.57) because daily totals over 100 SKUs are volatile and bulk orders are large; subset-day improvement is +5.8 % (H28, inconclusive) and −0.5 % (H7, inconclusive). The item-day model there is also biased downward (−0.38 … −0.39).

## 3. Does aggregation change the conclusions?

* **Yes for "which model".** The model selected for the item-day endpoint is not the model selected for the subset-day endpoint in any of the eight W2 cells; applying one model to the other's endpoint produces results worse than a simple baseline (the item-day model's subset-day WAPE exceeds that of a weekday-mean baseline in M5 cells: 0.346 vs 0.114).
* **No for "does a learned model beat a simple baseline once the baseline and the model target the same endpoint"** on the M5 and Online Retail II samples: supported at item-day in 8/8 cells (H1); at subset-day with positive point estimates in 7/8 cells (+5.8 … +23.8 %), supported in 4/8 after the dual-method rule (H3).
* The v1 headline ("the learned model does not beat a trailing median item-day but wins on aggregate") is explained by two things the ladder separates: the v1 reference was a mean-type model (cannot win item-day WAPE against a median-type baseline, 0.806 vs 0.775), and median-type baselines have a large level bias that becomes visible only after aggregation (best matched baselines here: −0.23 … −0.35 on M5 W2; the v1 baseline, a trailing 28-day median, is among the 31 baselines but was not the validation winner in these cells, so its bias is not tabulated here).

## 4. Interpretation limits

* These are descriptions of WAPE on specified subsets; they do not say which endpoint is "right". A retailer who orders by weekly total cares about subset-week; one who allocates stock to an item for each day cares about item-day or a service-level metric that was not evaluated here.
* Item-day WAPE of a median-type model rewards zero forecasts on sparse series; improvement in that metric is not evidence of better demand estimation, and the study does not evaluate service levels, stock-out costs or pinball losses.
* Segments (frequency, volume terciles, `results.json` → `segments`) are exploratory: gains concentrate in frequent / high-volume series (CA_1 H28: frequent series +8.1 % [3.5, 12.7], intermittent +2.5 % [0.5, 4.7]; volume terciles low / mid have intervals including zero).
* Four datasets from two sources; no claim beyond them.
