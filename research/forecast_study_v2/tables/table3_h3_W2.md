**Table 3. Subset-day endpoint, window W2 (confirmatory): subset-day-selected model versus the best matched baseline**

| cell | model | best matched baseline | WAPE baseline / model | improvement [95 % CI] | frozen Holm p primary / secondary | blocks won | verdict (frozen rule) | supplementary converged Holm p primary / secondary |
|---|---|---|---|---|---|---|---|---|
| CA_1 H28 | Tweedie 1.1 | weekday mean 4 | 0.114 / 0.088 | +22.7 % [+14.6, +30.6] | 0.002 / 0.002 | 6/6 | supported | <0.001 / <0.001 |
| CA_1 H7 | Tweedie 1.1 | weekday mean 8 | 0.104 / 0.084 | +18.7 % [+9.5, +28.5] | 0.002 / 0.002 | 6/6 | supported | <0.001 / <0.001 |
| TX_1 H28 | Tweedie 1.1 | weekday mean 8 | 0.117 / 0.099 | +14.8 % [+2.5, +26.7] | 0.071 / 0.048 | 4/6 | inconclusive | 0.051 / 0.043 |
| TX_1 H7 | Tweedie 1.1 | weekday mean 4 | 0.123 / 0.094 | +23.8 % [+13.9, +33.1] | 0.002 / 0.002 | 6/6 | supported | <0.001 / <0.001 |
| WI_1 H28 | squared error | weekday mean 8 | 0.100 / 0.092 | +7.8 % [−0.5, +15.7] | 0.205 / 0.269 | 5/6 | inconclusive | 0.215 / 0.259 |
| WI_1 H7 | squared error | weekday mean 8 | 0.099 / 0.087 | +11.4 % [+3.6, +18.3] | 0.035 / 0.002 | 6/6 | supported | 0.029 / 0.001 |
| Online Retail II H28 | Tweedie 1.1 | weekday mean 8 | 0.511 / 0.482 | +5.8 % [−5.5, +16.2] | 0.582 / 0.405 | 4/6 | inconclusive | 0.596 / 0.403 |
| Online Retail II H7 | Tweedie 1.1 | weekday mean 8 | 0.456 / 0.458 | −0.5 % [−13.3, +8.4] | 0.939 / 0.934 | 2/6 | inconclusive | 0.938 / 0.927 |

*Source: `results/analysis/analysis_W2.json` (H3); `results/supplementary/h3_convergence.json`; CSV: `tables/table3_h3_W2.csv`.*
