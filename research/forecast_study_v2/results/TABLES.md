# Generated tables (report.py)

## Window W2

| cell | model (item-day) | best matched baseline | WAPE base / model | H1 improvement [95% CI] | Holm p | blocks won | verdict H1 | H1b | H2 | H3 verdict (subset-day improvement) |
|---|---|---|---|---|---|---|---|---|---|---|
| M5 CA_1, H=28 | lgbm_l1 | matched__trailing_median56 | 0.775 / 0.739 | +4.6% [+2.3, +7.1] | 0.002 | 6/6 | SUPPORTED | INCONCLUSIVE | SUPPORTED | SUPPORTED (+22.7%) |
| M5 CA_1, H=7 | lgbm_l1 | matched__trailing_median14 | 0.714 / 0.686 | +4.0% [+2.3, +6.0] | 0.002 | 6/6 | SUPPORTED | SUPPORTED | SUPPORTED | SUPPORTED (+18.7%) |
| M5 TX_1, H=28 | lgbm_l1 | matched__trailing_median56 | 0.774 / 0.755 | +2.5% [+1.0, +4.1] | 0.004 | 6/6 | SUPPORTED | INCONCLUSIVE | SUPPORTED | INCONCLUSIVE (+14.8%) |
| M5 TX_1, H=7 | lgbm_l1 | matched__trailing_median91 | 0.752 / 0.718 | +4.5% [+2.5, +6.8] | 0.002 | 6/6 | SUPPORTED | SUPPORTED | SUPPORTED | SUPPORTED (+23.8%) |
| M5 WI_1, H=28 | lgbm_l1 | matched__trailing_median56 | 0.783 / 0.757 | +3.3% [+1.6, +5.3] | 0.002 | 6/6 | SUPPORTED | INCONCLUSIVE | SUPPORTED | INCONCLUSIVE (+7.8%) |
| M5 WI_1, H=7 | lgbm_l1 | matched__trailing_median91 | 0.753 / 0.708 | +6.0% [+3.4, +9.0] | 0.002 | 6/6 | SUPPORTED | SUPPORTED | SUPPORTED | SUPPORTED (+11.4%) |
| Online Retail II, H=28 | lgbm_l1_small | matched__weekday_median8 | 0.931 / 0.877 | +5.8% [+2.7, +9.5] | 0.002 | 6/6 | SUPPORTED | INCONCLUSIVE | SUPPORTED | INCONCLUSIVE (+5.8%) |
| Online Retail II, H=7 | lgbm_l1_small | matched__weekday_median8 | 0.871 / 0.836 | +4.0% [+1.5, +7.0] | 0.004 | 5/6 | SUPPORTED | SUPPORTED | SUPPORTED | INCONCLUSIVE (-0.5%) |

## Window W3

| cell | model (item-day) | best matched baseline | WAPE base / model | H1 improvement [95% CI] | Holm p | blocks won | verdict H1 | H1b | H2 | H3 verdict (subset-day improvement) |
|---|---|---|---|---|---|---|---|---|---|---|
| M5 CA_1, H=28 | lgbm_l1 | matched__trailing_median91 | 0.771 / 0.732 | +5.0% [+2.9, +7.5] | 0.001 | 6/6 | SUPPORTED | INCONCLUSIVE | SUPPORTED | SUPPORTED (+21.1%) |
| M5 CA_1, H=7 | lgbm_l1 | matched__trailing_median14 | 0.734 / 0.689 | +6.2% [+4.5, +8.0] | 0.001 | 6/6 | SUPPORTED | SUPPORTED | SUPPORTED | INCONCLUSIVE (+16.0%) |
| M5 TX_1, H=28 | lgbm_l1 | matched__trailing_median91 | 0.793 / 0.776 | +2.2% [+0.2, +4.1] | 0.028 | 5/6 | SUPPORTED | INCONCLUSIVE | SUPPORTED | SUPPORTED (+18.0%) |
| M5 TX_1, H=7 | lgbm_l1 | matched__trailing_median28 | 0.758 / 0.726 | +4.1% [+2.4, +6.0] | 0.001 | 6/6 | SUPPORTED | SUPPORTED | SUPPORTED | SUPPORTED (+19.1%) |
| M5 WI_1, H=28 | lgbm_l1 | matched__trailing_median56 | 0.800 / 0.764 | +4.5% [+2.7, +6.2] | 0.001 | 6/6 | SUPPORTED | INCONCLUSIVE | SUPPORTED | SUPPORTED (+13.5%) |
| M5 WI_1, H=7 | lgbm_l1 | matched__trailing_median28 | 0.751 / 0.717 | +4.5% [+3.1, +6.0] | 0.001 | 6/6 | SUPPORTED | SUPPORTED | SUPPORTED | INCONCLUSIVE (+11.7%) |

## Window W1

| cell | model (item-day) | best matched baseline | WAPE base / model | H1 improvement [95% CI] | Holm p | blocks won | verdict H1 | H1b | H2 | H3 verdict (subset-day improvement) |
|---|---|---|---|---|---|---|---|---|---|---|
| M5 CA_1, H=28 | lgbm_quantile50 | matched__trailing_median28 | 0.724 / 0.708 | +2.3% [+0.7, +3.9] | 0.015 | 6/6 | SUPPORTED | INCONCLUSIVE | SUPPORTED | INCONCLUSIVE (+12.2%) |
| M5 CA_1, H=7 | lgbm_l1 | matched__trailing_median14 | 0.691 / 0.661 | +4.3% [+2.9, +5.8] | 0.002 | 6/6 | SUPPORTED | SUPPORTED | SUPPORTED | SUPPORTED (+18.4%) |
| M5 TX_1, H=28 | lgbm_l1 | matched__trailing_median56 | 0.752 / 0.743 | +1.1% [-1.0, +3.2] | 0.285 | 3/6 | INCONCLUSIVE | INCONCLUSIVE | SUPPORTED | INCONCLUSIVE (+8.3%) |
| M5 TX_1, H=7 | lgbm_quantile50 | matched__trailing_median28 | 0.710 / 0.697 | +1.9% [+0.6, +3.3] | 0.014 | 6/6 | INCONCLUSIVE | INCONCLUSIVE | SUPPORTED | INCONCLUSIVE (+12.7%) |
| M5 WI_1, H=28 | lgbm_l1 | matched__trailing_median56 | 0.753 / 0.725 | +3.8% [+2.3, +5.4] | 0.002 | 6/6 | SUPPORTED | INCONCLUSIVE | SUPPORTED | SUPPORTED (+13.5%) |
| M5 WI_1, H=7 | lgbm_l1 | matched__trailing_median28 | 0.724 / 0.691 | +4.5% [+2.9, +6.2] | 0.002 | 6/6 | SUPPORTED | SUPPORTED | SUPPORTED | SUPPORTED (+16.4%) |
| Online Retail II, H=28 | lgbm_l1_small | matched__weekday_median8 | 0.817 / 0.790 | +3.3% [+1.7, +5.1] | 0.002 | 6/6 | SUPPORTED | INCONCLUSIVE | SUPPORTED | SUPPORTED (+12.0%) |
| Online Retail II, H=7 | lgbm_l1 | matched__weekday_median8 | 0.787 / 0.763 | +3.1% [+1.3, +5.0] | 0.006 | 6/6 | SUPPORTED | SUPPORTED | SUPPORTED | INCONCLUSIVE (+4.9%) |
