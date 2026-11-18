# DecisionGPT — Experimental Plan

## 1. Purpose

Evaluate whether the integrated DecisionGPT architecture improves strategic decision support.

## 2. Experiment A — Forecasting

Compare:
- naive baseline;
- statistical baseline;
- XGBoost.

Metrics:
- MAE;
- RMSE;
- MAPE.

## 3. Experiment B — Churn

Compare:
- Logistic Regression;
- Random Forest;
- XGBoost.

Metrics:
- Precision;
- Recall;
- F1;
- ROC-AUC.

## 4. Experiment C — Digital Twin

Compare simulated outcomes against observed outcomes where intervention-like data exists.

Metrics:
- MAE;
- RMSE;
- percentage error.

## 5. Experiment D — Decision Architecture

Compare:

A. Prediction only.

B. Prediction + Digital Twin.

C. Prediction + Digital Twin + single agent.

D. Full DecisionGPT.

Measure:
- goal achievement;
- expected benefit;
- risk-adjusted score;
- strategy quality.

## 6. Experiment E — Ablation

Remove:
- Digital Twin;
- Causal Graph;
- Multi-Agent Engine;
- Explainability;
- Memory.

## 7. Experiment F — Human Evaluation

If feasible, compare recommendations on:
- understanding;
- usefulness;
- trust;
- explanation quality.

## 8. Scenarios

1. Revenue decline.
2. Marketing budget optimization.
3. Pricing decision.
4. Inventory decision.

Use controlled synthetic scenarios when real intervention data is unavailable.

## 9. Reproducibility

Record:
- experiment ID;
- dataset version;
- model version;
- configuration;
- random seed;
- metrics;
- timestamp.

## 10. Results Policy

Do not predefine results.

Only actual experimental results may appear in the paper.
