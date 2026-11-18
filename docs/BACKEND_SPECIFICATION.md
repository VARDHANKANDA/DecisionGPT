# DecisionGPT — Backend Specification

## 1. Technology

Recommended:
- Python 3.11+
- FastAPI
- Pydantic
- SQLAlchemy
- Alembic
- PostgreSQL
- Pandas
- Scikit-learn
- XGBoost
- SHAP

LLM provider should be abstracted behind a service interface.

## 2. Structure

```text
backend/
└── app/
    ├── main.py
    ├── api/
    ├── core/
    ├── db/
    ├── models/
    ├── schemas/
    ├── services/
    ├── analytics/
    ├── digital_twin/
    ├── causal/
    ├── agents/
    ├── explainability/
    └── memory/
```

## 3. Service Boundaries

### Data Service
File ingestion and validation.

### Analytics Service
Forecasting, churn, KPI calculations.

### Goal Service
Goal parsing and validation.

### Causal Service
Graph creation and graph queries.

### Digital Twin Service
Strategy simulation.

### Agent Service
Multi-agent evaluation.

### Decision Service
Orchestrates the complete decision workflow.

### Memory Service
Stores/retrieves business history.

## 4. Configuration

All secrets through environment variables.

## 5. Logging

Every major decision workflow gets:
- request ID;
- business ID;
- goal ID;
- decision ID;
- model versions;
- timestamps.

## 6. Background Work

Use background jobs for large uploads, training and experiments.

Keep the initial queue implementation simple.

## 7. Database

Use SQLAlchemy models and Alembic migrations.

## 8. Tests

Required:
- schema tests;
- service tests;
- API tests;
- Digital Twin tests;
- causal graph tests;
- strategy scoring tests;
- business isolation tests.
