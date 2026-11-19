# SUPPLEMENTARY_H3_RESOLUTION — precision check of the subset-day (H3) inference

Post-hoc and **supplementary**. The frozen results (`results/analysis/analysis_*.json`) are unchanged and remain the reported outcome. Here the two prespecified H3 methods (iid-week bootstrap = primary; stationary bootstrap with mean block 3 weeks = secondary) are recomputed with B = 1,000,000 per seed (3 seeds, new seeds), the frozen decision rule (`analysis.verdict`, dual-method rule, Holm within the family of the window) is applied unchanged to the converged p-values and intervals, and an exact sign-flip test and dependence diagnostics are added.

## Window W2

| cell | improvement | frozen: p iid / p stat. | frozen verdict | converged: p iid (seed SD) / p stat. (seed SD) | converged Holm iid / stat. | converged verdict (frozen rule) | exact sign-flip p | weeks model better | lag-1 autocorr. | AR(1) effective weeks |
|---|---|---|---|---|---|---|---|---|---|---|
| m5_ca1_H28 | +22.7% | 0.0002 / 0.0002 | SUPPORTED | 0.0000 (0.0000) / 0.0000 (0.0000) | 0.0000 / 0.0000 | SUPPORTED | 0.0000 | 19/24 | +0.06 | 21.2 |
| m5_ca1_H7 | +18.7% | 0.0002 / 0.0002 | SUPPORTED | 0.0000 (0.0000) / 0.0000 (0.0000) | 0.0001 / 0.0000 | SUPPORTED | 0.0009 | 16/24 | -0.07 | 27.4 |
| m5_tx1_H28 | +14.8% | 0.0178 / 0.0120 | INCONCLUSIVE | 0.0129 (0.0002) / 0.0108 (0.0000) | 0.0514 / 0.0433 | INCONCLUSIVE | 0.0339 | 15/24 | +0.36 | 11.3 |
| m5_tx1_H7 | +23.8% | 0.0002 / 0.0002 | SUPPORTED | 0.0000 (0.0000) / 0.0000 (0.0000) | 0.0000 / 0.0000 | SUPPORTED | 0.0001 | 20/24 | +0.06 | 21.3 |
| m5_wi1_H28 | +7.8% | 0.0682 / 0.0896 | INCONCLUSIVE | 0.0716 (0.0000) / 0.0863 (0.0002) | 0.2148 / 0.2589 | INCONCLUSIVE | 0.0933 | 13/24 | +0.01 | 23.4 |
| m5_wi1_H7 | +11.4% | 0.0070 / 0.0002 | SUPPORTED | 0.0059 (0.0001) / 0.0001 (0.0000) | 0.0293 / 0.0005 | SUPPORTED | 0.0134 | 16/24 | -0.35 | 49.9 |
| or2_H28 | +5.8% | 0.2912 / 0.2026 | INCONCLUSIVE | 0.2981 (0.0007) / 0.2013 (0.0007) | 0.5962 / 0.4027 | INCONCLUSIVE | 0.3211 | 13/24 | -0.27 | 41.9 |
| or2_H7 | -0.5% | 0.9393 / 0.9335 | INCONCLUSIVE | 0.9380 (0.0004) / 0.9272 (0.0007) | 0.9380 / 0.9272 | INCONCLUSIVE | 0.9322 | 13/24 | +0.32 | 12.3 |

## Window W3

| cell | improvement | frozen: p iid / p stat. | frozen verdict | converged: p iid (seed SD) / p stat. (seed SD) | converged Holm iid / stat. | converged verdict (frozen rule) | exact sign-flip p | weeks model better | lag-1 autocorr. | AR(1) effective weeks |
|---|---|---|---|---|---|---|---|---|---|---|
| m5_ca1_H28 | +21.1% | 0.0022 / 0.0004 | SUPPORTED | 0.0012 (0.0000) / 0.0001 (0.0000) | 0.0073 / 0.0007 | SUPPORTED | 0.0060 | 15/24 | +0.10 | 19.7 |
| m5_ca1_H7 | +16.0% | 0.0346 / 0.0058 | INCONCLUSIVE | 0.0319 (0.0002) / 0.0039 (0.0001) | 0.0618 / 0.0078 | INCONCLUSIVE | 0.0479 | 15/24 | -0.05 | 26.7 |
| m5_tx1_H28 | +18.0% | 0.0088 / 0.0032 | SUPPORTED | 0.0088 (0.0000) / 0.0023 (0.0001) | 0.0263 / 0.0069 | SUPPORTED | 0.0165 | 17/24 | -0.02 | 24.8 |
| m5_tx1_H7 | +19.1% | 0.0016 / 0.0002 | SUPPORTED | 0.0025 (0.0000) / 0.0001 (0.0000) | 0.0123 / 0.0004 | SUPPORTED | 0.0084 | 17/24 | +0.00 | 23.8 |
| m5_wi1_H28 | +13.5% | 0.0044 / 0.0008 | SUPPORTED | 0.0035 (0.0000) / 0.0003 (0.0000) | 0.0141 / 0.0010 | SUPPORTED | 0.0087 | 17/24 | -0.03 | 25.7 |
| m5_wi1_H7 | +11.7% | 0.0288 / 0.0116 | INCONCLUSIVE | 0.0309 (0.0003) / 0.0115 (0.0001) | 0.0618 / 0.0115 | INCONCLUSIVE | 0.0469 | 18/24 | -0.10 | 29.1 |

## Window W1

| cell | improvement | frozen: p iid / p stat. | frozen verdict | converged: p iid (seed SD) / p stat. (seed SD) | converged Holm iid / stat. | converged verdict (frozen rule) | exact sign-flip p | weeks model better | lag-1 autocorr. | AR(1) effective weeks |
|---|---|---|---|---|---|---|---|---|---|---|
| m5_ca1_H28 | +12.2% | 0.1508 / 0.0944 | INCONCLUSIVE | 0.1430 (0.0005) / 0.1015 (0.0005) | 0.4290 / 0.3045 | INCONCLUSIVE | 0.1749 | 14/24 | -0.01 | 24.3 |
| m5_ca1_H7 | +18.4% | 0.0002 / 0.0002 | SUPPORTED | 0.0001 (0.0000) / 0.0000 (0.0000) | 0.0009 / 0.0000 | SUPPORTED | 0.0015 | 19/24 | -0.33 | 47.1 |
| m5_tx1_H28 | +8.3% | 0.2534 / 0.3190 | INCONCLUSIVE | 0.2485 (0.0005) / 0.3089 (0.0004) | 0.4290 / 0.3184 | INCONCLUSIVE | 0.2686 | 15/24 | +0.20 | 16.0 |
| m5_tx1_H7 | +12.7% | 0.0604 / 0.0390 | INCONCLUSIVE | 0.0570 (0.0001) / 0.0367 (0.0004) | 0.2281 / 0.1468 | INCONCLUSIVE | 0.0684 | 19/24 | +0.00 | 24.0 |
| m5_wi1_H28 | +13.5% | 0.0008 / 0.0008 | SUPPORTED | 0.0009 (0.0000) / 0.0002 (0.0000) | 0.0052 / 0.0015 | SUPPORTED | 0.0022 | 20/24 | +0.12 | 19.0 |
| m5_wi1_H7 | +16.4% | 0.0004 / 0.0004 | SUPPORTED | 0.0003 (0.0000) / 0.0001 (0.0000) | 0.0018 / 0.0006 | SUPPORTED | 0.0011 | 22/24 | +0.06 | 21.5 |
| or2_H28 | +12.0% | 0.0054 / 0.0012 | SUPPORTED | 0.0037 (0.0001) / 0.0009 (0.0000) | 0.0184 / 0.0047 | SUPPORTED | 0.0110 | 16/24 | +0.02 | 23.1 |
| or2_H7 | +4.9% | 0.2206 / 0.1646 | INCONCLUSIVE | 0.2025 (0.0007) / 0.1592 (0.0001) | 0.4290 / 0.3184 | INCONCLUSIVE | 0.2230 | 15/24 | +0.04 | 22.2 |

