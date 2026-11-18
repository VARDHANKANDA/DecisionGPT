# DecisionGPT — Business Digital Twin Specification

## 1. Purpose

The Business Digital Twin is a simplified computational model of the business used to estimate the effect of controlled strategies.

It is not a claim of a perfect real-world replica.

## 2. State

Initial state variables:
- sales
- revenue
- customers
- average_price
- marketing_spend
- inventory
- profit
- churn_rate
- conversion_rate

## 3. Supported Actions

- price_change
- marketing_change
- inventory_change

Keep the initial action space controlled.

## 4. Strategy

A strategy contains one or more actions.

```json
{
  "strategy_id": "S001",
  "actions": [
    {"type": "marketing_change", "value": 5}
  ]
}
```

## 5. Simulation

```text
Current State
     +
Action
     |
     v
Predictive Models + Causal Structure
     |
     v
Simulated Future State
```

## 6. Mathematical Form

`S(t+1) = F(S(t), A(t), X(t))`

Where:
- S is business state;
- A is action;
- X is contextual information;
- F is the implemented transition function.

## 7. Candidate Strategy Grid

Initial configurable ranges may include:
- marketing: -10%, -5%, 0%, +5%, +10%;
- price: -5%, 0%, +5%;
- inventory: -10%, 0%, +10%.

Avoid combinatorial explosion.

## 8. Output

Return:
- expected revenue;
- expected profit;
- expected sales;
- customer impact;
- churn if available;
- uncertainty;
- risk;
- model versions;
- causal graph version;
- assumptions.

## 9. Uncertainty

Use a documented method such as:
- prediction intervals;
- bootstrap;
- ensembles;
- calibrated uncertainty.

Never invent confidence values.

## 10. Validation

Compare simulated and observed outcomes when intervention-like data exists.

Otherwise label results as model-based counterfactual estimates.

## 11. Logging

Record every simulation input, action, output, assumption, model version, graph version and timestamp.
