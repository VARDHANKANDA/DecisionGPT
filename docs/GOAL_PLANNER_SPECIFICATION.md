# DecisionGPT — Goal Planner Specification

## 1. Purpose

Convert a natural-language business objective into a validated structured goal.

## 2. Supported Initial Goals

- increase_revenue
- increase_profit
- increase_sales
- reduce_churn
- improve_marketing_roi
- reduce_inventory_risk

## 3. Required Output

```json
{
  "objective": "increase_profit",
  "target_value": 15,
  "target_unit": "percent",
  "primary_kpi": "profit",
  "time_horizon_months": 3,
  "constraints": [],
  "source_text": "Increase profit by 15% in three months."
}
```

## 4. Validation

Reject or request clarification when:
- no measurable target exists;
- required KPI is unavailable;
- time horizon is missing for a simulation request;
- target is outside supported ranges.

## 5. LLM Boundary

The LLM may parse the user's sentence.

It must not invent current KPI values.

Current values are retrieved from analytics/database services.

## 6. Schema

Use Pydantic validation before the goal enters the decision pipeline.
