# DecisionGPT — Product Requirements Document

**Version:** 1.0 — Frozen Capstone Scope  
**Target Market:** India  
**Primary Users:** Indian SMEs, startups, D2C and retail/e-commerce businesses  
**Primary Demonstration:** Indian D2C clothing brand  
**Default Currency:** INR (₹)

## 1. Product Vision

DecisionGPT is a web-based AI decision-support platform that converts business data and business goals into explainable strategic recommendations.

The platform combines predictive analytics, a Business Digital Twin, causal reasoning, multi-agent evaluation and business memory.

## 2. Problem

Traditional BI mainly answers what happened and what may happen. DecisionGPT addresses the next question: what should the business consider doing, what may happen under alternative actions, why, and with what uncertainty?

## 3. Core User Journey

1. Create business.
2. Upload CSV/XLSX.
3. Validate and map data.
4. Build business context.
5. Enter a measurable goal.
6. Run analytics.
7. Generate candidate strategies.
8. Simulate strategies.
9. Analyse causal pathways.
10. Evaluate with specialist agents.
11. Select a risk-aware recommendation.
12. Explain it.
13. Save decision.
14. Later record actual outcome.

## 4. Core Modules

1. Business Onboarding
2. Data Ingestion & Validation
3. Business Knowledge Base
4. Goal Planner
5. AI Analytics Engine
6. Business Digital Twin
7. Dynamic Causal Graph
8. Multi-Agent Decision Engine
9. Explainable AI
10. Business Memory
11. AI Chat
12. Dashboard
13. Experiment Logging

## 5. Indian Market Context

The platform is designed for Indian businesses.

Use:
- INR as default currency;
- Indian benchmark sources where available;
- Indian retail/e-commerce data where available;
- configurable seasonality/calendar features.

Do not hard-code claims about GST, festivals, consumer behaviour or competitors. Such information must be represented as data with a source.

## 6. Functional Requirements

### FR-01 Business Onboarding
Create and edit business profile.

### FR-02 Data Upload
Accept CSV and XLSX.

### FR-03 Validation
Detect missing values, duplicates, invalid types and schema mismatches.

### FR-04 Mapping
Map uploaded columns to canonical fields and request confirmation for ambiguous mappings.

### FR-05 Analytics
Provide forecasting and churn prediction when sufficient data exists.

### FR-06 Goal Planner
Convert natural language to a validated structured goal.

### FR-07 Digital Twin
Simulate supported business actions.

### FR-08 Causal Graph
Maintain evidence-labelled business relationships.

### FR-09 Multi-Agent Decision
Evaluate candidate strategies through four specialist agents.

### FR-10 Explainability
Explain predictions and strategic recommendations.

### FR-11 Memory
Store goals, strategies, simulations, decisions and outcomes.

### FR-12 Chat
Answer questions using verified business context.

### FR-13 Dashboard
Display KPIs, forecasts, simulations, recommendations, risk and history.

### FR-14 Auditability
Make every recommendation traceable to its inputs and model versions.

## 7. Non-Functional Requirements

- Python/FastAPI backend.
- Next.js/React frontend.
- PostgreSQL.
- REST API.
- Docker Compose.
- Environment variables.
- Business data isolation.
- Structured logging.
- Tests.
- Reproducible experiments.

## 8. Out of Scope

- Automatic transactions.
- Automatic ad spending.
- Automatic price changes.
- Full ERP.
- Full e-commerce store.
- Mobile app.
- Voice interface.
- Private competitor-data acquisition.
- Production-scale cloud infrastructure.

## 9. Definition of Done

A user must be able to complete the entire workflow from onboarding to recommendation and later outcome recording from the web application.
