**Table 2. Item-day endpoint, window W2 (confirmatory): item-day-selected model (absolute-error LightGBM in all cells) versus the best matched baseline**

| cell | best matched baseline | WAPE baseline / model | improvement [95 % CI] | Holm p | blocks won | H1 | H1b: vs best any-information baseline | H2: vs original Tweedie 1.1 model |
|---|---|---|---|---|---|---|---|---|
| CA_1 H28 | trailing median 56 | 0.775 / 0.739 | +4.6 % [+2.3, +7.1] | 0.0016 | 6/6 | supported | inconclusive (−1.4 %) | supported (+8.2 %) |
| CA_1 H7 | trailing median 14 | 0.714 / 0.686 | +4.0 % [+2.3, +6.0] | 0.0016 | 6/6 | supported | supported (+2.5 %) | supported (+8.0 %) |
| TX_1 H28 | trailing median 56 | 0.774 / 0.755 | +2.5 % [+1.0, +4.1] | 0.0036 | 6/6 | supported | inconclusive (+0.8 %) | supported (+10.5 %) |
| TX_1 H7 | trailing median 91 | 0.752 / 0.718 | +4.5 % [+2.5, +6.8] | 0.0016 | 6/6 | supported | supported (+3.8 %) | supported (+10.8 %) |
| WI_1 H28 | trailing median 56 | 0.783 / 0.757 | +3.3 % [+1.6, +5.3] | 0.0018 | 6/6 | supported | inconclusive (+0.9 %) | supported (+7.9 %) |
| WI_1 H7 | trailing median 91 | 0.753 / 0.708 | +6.0 % [+3.4, +9.0] | 0.0016 | 6/6 | supported | supported (+3.2 %) | supported (+8.2 %) |
| Online Retail II H28 | weekday median 8 | 0.931 / 0.877 | +5.8 % [+2.7, +9.5] | 0.0016 | 6/6 | supported | inconclusive (+2.2 %) | supported (+16.7 %) |
| Online Retail II H7 | weekday median 8 | 0.871 / 0.836 | +4.0 % [+1.5, +7.0] | 0.0036 | 5/6 | supported | supported (+4.0 %) | supported (+16.8 %) |

*Source: `results/analysis/analysis_W2.json` (H1, H1b, H2); CSV: `tables/table2_h1_W2.csv`.*
