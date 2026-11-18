# DecisionGPT — Dynamic Causal Graph Specification

## 1. Purpose

Represent directional business relationships and their evidence to support intervention reasoning and explanation.

## 2. Initial Hypothesis Graph

```text
Marketing Spend -> Website Traffic -> Conversion Rate -> Orders -> Revenue -> Profit
Price -> Demand -> Sales -> Revenue -> Profit
Customer Experience -> Retention -> Repeat Purchases -> Revenue
Inventory -> Availability -> Sales
```

These are domain hypotheses, not automatically proven causal facts.

## 3. Evidence Labels

Each edge must be:
- ASSUMED
- OBSERVATIONAL
- DATA_SUPPORTED
- CAUSALLY_VALIDATED

## 4. Edge Schema

```json
{
  "source": "marketing_spend",
  "target": "website_traffic",
  "direction": "positive",
  "strength": 0.62,
  "confidence": 0.80,
  "evidence_type": "data_supported",
  "time_lag": 1
}
```

The numbers are examples only and must not be hard-coded as research results.

## 5. Dynamic Graph

Estimate relationships over time only when enough data exists.

Store graph version and timestamp.

## 6. Methods

Prototype priority:
1. domain-informed graph;
2. statistical relationship estimation;
3. one selected causal method suitable for the available data.

Possible research methods:
- Granger causality for suitable time series;
- PC algorithm;
- NOTEARS;
- structural causal models.

Do not implement all methods.

## 7. Intervention

Represent supported interventions conceptually as:

`do(variable = value)`

The resulting effect must be computed by analytical/simulation components, not by the LLM.

## 8. LLM Boundary

LLM may explain the graph.

LLM may not invent graph edges or causal effects.

## 9. Validation

Use:
- synthetic data with known causal structure;
- historical/quasi-experimental evidence where appropriate.

## 10. Research Comparison

Compare the system with and without the causal layer.

## 11. Limitations

Document:
- hidden confounders;
- omitted variables;
- limited samples;
- non-stationarity;
- incorrect assumptions.
