**Table R3-2. Validation-stage margins between the selected model and its runner-up (W2, mean over three validation blocks)**

| cell | item-day: selected | item-day: runner-up | relative validation margin | margin between best and second-best matched baseline | subset-day: selected | subset-day: runner-up | relative validation margin |
|---|---|---|---|---|---|---|---|
| CA_1 H28 | absolute error | 0.5 quantile | 0.38 % | 0.83 % | Tweedie 1.1 | Tweedie 1.5 | 0.29 % |
| CA_1 H7 | absolute error | 0.5 quantile | 0.47 % | 0.66 % | Tweedie 1.1 | Tweedie 1.5 | 4.63 % |
| TX_1 H28 | absolute error | absolute error (small) | 0.11 % | 0.22 % | Tweedie 1.1 | squared error | 1.91 % |
| TX_1 H7 | absolute error | 0.5 quantile | 0.54 % | 0.73 % | Tweedie 1.1 | Tweedie 1.5 | 3.07 % |
| WI_1 H28 | absolute error | 0.5 quantile | 0.83 % | 0.44 % | squared error | Tweedie 1.1 | 3.79 % |
| WI_1 H7 | absolute error | 0.5 quantile | 0.22 % | 0.21 % | squared error | Tweedie 1.1 | 2.91 % |
| Online Retail II H28 | absolute error (small) | 0.5 quantile | 0.41 % | 4.20 % | Tweedie 1.1 | Tweedie 1.5 | 2.71 % |
| Online Retail II H7 | absolute error (small) | 0.5 quantile | 0.37 % | 4.85 % | Tweedie 1.1 | Tweedie 1.5 | 2.45 % |

*Source: `quality_gate/results/audit_sensitivity.json` (B), from the stored validation tables of `selection.json`.*
