# DecisionGPT — AI Module Specification

## 1. Principle

Use the simplest reliable model that fits the dataset.

## 2. Goal Understanding

LLM + strict Pydantic schema validation.

## 3. Sales Forecasting

Baselines:
- naive;
- statistical/linear baseline.

Candidate model:
- XGBoost.

Optional advanced models are allowed only if experiments justify them.

Metrics:
- MAE;
- RMSE;
- MAPE.

## 4. Churn Prediction

Candidate models:
- Logistic Regression;
- Random Forest;
- XGBoost.

Metrics:
- Precision;
- Recall;
- F1;
- ROC-AUC.

Disable the feature when the dataset is insufficient.

## 5. Marketing Analytics

Calculate where supported:
- spend;
- conversions;
- CPA;
- attributed revenue;
- ROI.

## 6. Digital Twin

Reuse validated predictive components and causal structure rather than adding an unnecessary second ML stack.

## 7. Explainability

Use SHAP for compatible ML models.

Provide:
- global importance;
- local explanation;
- strategy rationale;
- supported counterfactual;
- uncertainty.

## 8. LLM Usage

Allowed:
- goal parsing;
- strategy language;
- agent reasoning;
- explanation;
- chat.

Not authoritative for:
- numerical calculations;
- forecasts;
- causal estimates;
- simulation outputs.

## 9. Model Registry

Store:
- model ID;
- model type;
- version;
- dataset version;
- feature version;
- parameters;
- metrics;
- artifact path;
- training timestamp.

## 10. Training Pipeline

```text
Raw Data
 -> Validation
 -> Preprocessing
 -> Feature Engineering
 -> Training
 -> Validation
 -> Test
 -> Registry
```

## 11. Inference

```text
Business Data
 -> Feature Pipeline
 -> Model
 -> Prediction
 -> Decision Pipeline
```

## 12. Reproducibility

Record random seeds, versions, configuration and metrics.

## 13. No Fabrication

If the model cannot reliably produce a result, return an explicit insufficient-evidence state.
