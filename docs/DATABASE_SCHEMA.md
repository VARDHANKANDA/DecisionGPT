# DecisionGPT — Database Schema

**Database:** PostgreSQL

## 1. Core Tables

### businesses
`id, name, industry, business_type, business_size, country, currency, description, created_at, updated_at`

### products
`id, business_id, external_product_id, name, category, unit_cost, selling_price, stock_quantity, created_at, updated_at`

### customers
`id, business_id, external_customer_id, segment, first_purchase_date, last_purchase_date, purchase_frequency, monetary_value, churn_probability, created_at`

### sales
`id, business_id, customer_id, product_id, sale_date, quantity, unit_price, discount, revenue, created_at`

### marketing_campaigns
`id, business_id, campaign_date, channel, campaign_name, spend, impressions, clicks, conversions, attributed_revenue, created_at`

### inventory
`id, business_id, product_id, date, stock_level, reorder_level, created_at`

### goals
`id, business_id, objective, target_value, target_unit, primary_kpi, time_horizon, constraints_json, status, created_at, updated_at`

### forecasts
`id, business_id, model_id, forecast_type, forecast_date, predicted_value, lower_bound, upper_bound, created_at`

### models
`id, model_name, model_type, version, dataset_version, feature_version, parameters_json, metrics_json, model_path, created_at`

### strategies
`id, business_id, goal_id, strategy_name, description, actions_json, created_at`

### digital_twin_states
`id, business_id, goal_id, state_json, created_at`

### digital_twin_simulations
`id, business_id, goal_id, strategy_id, input_state_json, actions_json, output_state_json, risk_score, model_version, graph_version, assumptions_json, created_at`

### causal_graphs
`id, business_id, version, graph_json, method, evidence_summary, created_at`

### causal_edges
`id, causal_graph_id, source_node, target_node, relationship, strength, confidence, evidence_type, time_lag`

### agent_runs
`id, business_id, decision_id, agent_name, model_name, prompt_version, input_json, output_json, created_at`

### agent_evaluations
`id, strategy_id, agent_name, evaluation_json, score, model_name, prompt_version, created_at`

### decisions
`id, business_id, goal_id, selected_strategy_id, expected_outcome_json, risk_level, confidence, reasoning, causal_graph_version, created_at`

### decision_outcomes
`id, decision_id, actual_outcome_json, goal_achieved, goal_achievement_score, recorded_at`

### business_memory
`id, business_id, memory_type, content, metadata_json, created_at`

### market_benchmarks
`id, industry, business_size, metric, period, median_value, lower_quartile, upper_quartile, source, source_url, evidence_level, created_at`

### experiment_runs
`id, experiment_name, experiment_type, dataset_version, model_version, configuration_json, metrics_json, result_path, created_at`

## 2. Rules

Every business-owned record must be scoped by `business_id`.

Use foreign keys and indexes.

Use migrations.

Do not store API keys.

Avoid unnecessary PII.

## 3. Research Traceability

```text
Decision
 -> Goal
 -> Strategy
 -> Digital Twin Simulation
 -> Causal Graph Version
 -> Agent Evaluations
 -> Model Versions
 -> Explanation
```
