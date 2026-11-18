# DecisionGPT — Testing Specification

## 1. Test Levels

### Unit
Test individual functions and services.

### Integration
Test database + service interactions.

### API
Test HTTP contracts.

### End-to-End
Test the complete business workflow.

## 2. Critical Tests

### Data
- valid CSV;
- invalid CSV;
- missing columns;
- duplicate rows;
- invalid dates.

### Goal
- valid goal;
- missing target;
- unsupported KPI.

### Forecast
- correct feature shape;
- no future leakage;
- output schema.

### Digital Twin
- action validation;
- deterministic simulation under fixed model;
- state conservation where appropriate;
- invalid action rejection.

### Causal
- graph schema;
- evidence labels;
- no fabricated edges;
- versioning.

### Agents
- schema validation;
- distinct roles;
- numerical values originate from tools.

### Security
- business A cannot access business B.

## 3. Research Tests

Every experiment must have:
- configuration;
- dataset version;
- random seed;
- metrics;
- saved result.

## 4. Acceptance Test

A complete E2E test should:

1. Create business.
2. Upload sample data.
3. Validate data.
4. Generate KPIs.
5. Create goal.
6. Forecast.
7. Build graph.
8. Simulate at least three strategies.
9. Run agents.
10. Generate recommendation.
11. Display explanation.
12. Save decision.
13. Record outcome.
