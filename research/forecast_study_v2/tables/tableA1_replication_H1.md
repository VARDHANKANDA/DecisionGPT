**Table A1. Replication windows W3 and W1: item-day (H1) and subset-day (H3) results**

| window | cell | item-day model | best matched baseline | WAPE baseline / model | H1 improvement [95 % CI] | Holm p | blocks won | H1 | H3 (improvement) |
|---|---|---|---|---|---|---|---|---|---|
| W3 | CA_1 H28 | absolute error | trailing median 91 | 0.771 / 0.732 | +5.0 % [+2.9, +7.5] | 0.0012 | 6/6 | supported | supported (+21.1 %) |
| W3 | CA_1 H7 | absolute error | trailing median 14 | 0.734 / 0.689 | +6.2 % [+4.5, +8.0] | 0.0012 | 6/6 | supported | inconclusive (+16.0 %) |
| W3 | TX_1 H28 | absolute error | trailing median 91 | 0.793 / 0.776 | +2.2 % [+0.2, +4.1] | 0.0284 | 5/6 | supported | supported (+18.0 %) |
| W3 | TX_1 H7 | absolute error | trailing median 28 | 0.758 / 0.726 | +4.1 % [+2.4, +6.0] | 0.0012 | 6/6 | supported | supported (+19.1 %) |
| W3 | WI_1 H28 | absolute error | trailing median 56 | 0.800 / 0.764 | +4.5 % [+2.7, +6.2] | 0.0012 | 6/6 | supported | supported (+13.5 %) |
| W3 | WI_1 H7 | absolute error | trailing median 28 | 0.751 / 0.717 | +4.5 % [+3.1, +6.0] | 0.0012 | 6/6 | supported | inconclusive (+11.7 %) |
| W1 | CA_1 H28 | 0.5 quantile | trailing median 28 | 0.724 / 0.708 | +2.3 % [+0.7, +3.9] | 0.0152 | 6/6 | supported | inconclusive (+12.2 %) |
| W1 | CA_1 H7 | absolute error | trailing median 14 | 0.691 / 0.661 | +4.3 % [+2.9, +5.8] | 0.0016 | 6/6 | supported | supported (+18.4 %) |
| W1 | TX_1 H28 | absolute error | trailing median 56 | 0.752 / 0.743 | +1.1 % [−1.0, +3.2] | 0.2848 | 3/6 | inconclusive | inconclusive (+8.3 %) |
| W1 | TX_1 H7 | 0.5 quantile | trailing median 28 | 0.710 / 0.697 | +1.9 % [+0.6, +3.3] | 0.0138 | 6/6 | inconclusive | inconclusive (+12.7 %) |
| W1 | WI_1 H28 | absolute error | trailing median 56 | 0.753 / 0.725 | +3.8 % [+2.3, +5.4] | 0.0016 | 6/6 | supported | supported (+13.5 %) |
| W1 | WI_1 H7 | absolute error | trailing median 28 | 0.724 / 0.691 | +4.5 % [+2.9, +6.2] | 0.0016 | 6/6 | supported | supported (+16.4 %) |
| W1 | Online Retail II H28 | absolute error (small) | weekday median 8 | 0.817 / 0.790 | +3.3 % [+1.7, +5.1] | 0.0016 | 6/6 | supported | supported (+12.0 %) |
| W1 | Online Retail II H7 | absolute error | weekday median 8 | 0.787 / 0.763 | +3.1 % [+1.3, +5.0] | 0.0056 | 6/6 | supported | inconclusive (+4.9 %) |

*Source: `results/analysis/analysis_W3.json`, `analysis_W1.json`; CSV: `tables/tableA1_replication_H1.csv`.*
