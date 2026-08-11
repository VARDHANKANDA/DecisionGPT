# DecisionGPT — Research Traceability

Every final recommendation must be traceable.

## Trace

```text
User Goal
  |
  v
Goal ID
  |
  v
Business State
  |
  v
Analytics Model Versions
  |
  v
Candidate Strategies
  |
  v
Digital Twin Simulations
  |
  v
Causal Graph Version
  |
  v
Agent Evaluations
  |
  v
Strategy Optimizer
  |
  v
Explanation
  |
  v
Decision Record
  |
  v
Actual Outcome
```

## Required Metadata

- business_id
- goal_id
- decision_id
- model_version
- graph_version
- strategy_id
- simulation_id
- agent run IDs
- prompt version
- timestamp

## Purpose

This enables:
- auditing;
- debugging;
- reproducibility;
- paper methodology;
- ablation analysis.
