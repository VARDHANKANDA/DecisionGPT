# DecisionGPT — API Specification

**Base path:** `/api/v1`

## 1. Health

`GET /health`

Returns application and dependency health.

## 2. Business

`POST /businesses`
Create business.

`GET /businesses/{business_id}`
Retrieve business.

`PATCH /businesses/{business_id}`
Update business.

## 3. Data

`POST /businesses/{business_id}/data/upload`
Upload CSV/XLSX.

`GET /businesses/{business_id}/data/jobs/{job_id}`
Get ingestion status.

`POST /businesses/{business_id}/data/mapping`
Confirm column mapping.

`GET /businesses/{business_id}/data/summary`
Get data quality summary.

## 4. Analytics

`POST /businesses/{business_id}/analytics/forecast`

`POST /businesses/{business_id}/analytics/churn`

`GET /businesses/{business_id}/analytics/kpis`

## 5. Goals

`POST /businesses/{business_id}/goals`

`GET /businesses/{business_id}/goals`

`GET /businesses/{business_id}/goals/{goal_id}`

## 6. Causal Graph

`POST /businesses/{business_id}/causal-graph/build`

`GET /businesses/{business_id}/causal-graph`

## 7. Digital Twin

`POST /businesses/{business_id}/digital-twin/simulate`

Request:

```json
{
  "goal_id": "G001",
  "actions": [
    {"type": "marketing_change", "value": 5}
  ]
}
```

`GET /businesses/{business_id}/digital-twin/simulations/{simulation_id}`

## 8. Decision

`POST /businesses/{business_id}/decisions/analyze`

Request contains:
- goal ID;
- candidate strategies;
- simulation references.

`GET /businesses/{business_id}/decisions`

`GET /businesses/{business_id}/decisions/{decision_id}`

## 9. Outcomes

`POST /businesses/{business_id}/decisions/{decision_id}/outcome`

Stores actual outcome for research feedback.

## 10. Chat

`POST /businesses/{business_id}/chat`

The response must cite the internal data/context used by the answer.

## 11. Error Contract

```json
{
  "error": {
    "code": "INSUFFICIENT_DATA",
    "message": "Not enough historical observations for this forecast.",
    "details": {}
  }
}
```

## 12. API Rules

- Validate all input.
- Authorize business access.
- Never expose internal secrets.
- Use consistent error codes.
- Use request IDs for traceability.
