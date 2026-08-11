# DecisionGPT — Multi-Agent Decision Engine Specification

## 1. Purpose

Evaluate candidate strategies from multiple specialised business perspectives.

## 2. Agents

### Business Analyst
Focuses on:
- sales;
- demand;
- growth;
- customer/business performance.

### Financial Advisor
Focuses on:
- revenue;
- cost;
- margin;
- profit;
- ROI.

### Risk Manager
Focuses on:
- downside;
- uncertainty;
- operational risk;
- customer impact.

### Strategy Optimizer
Focuses on:
- goal alignment;
- quantitative outcomes;
- agent disagreement;
- risk-adjusted selection.

## 3. Workflow

```text
Goal
 |
 v
Candidate Strategies
 |
 v
Digital Twin
 |
 +--> Business Analyst
 +--> Financial Advisor
 +--> Risk Manager
 |
 v
Strategy Optimizer
 |
 v
Recommendation
```

## 4. Debate

Round 1: independent evaluation.

Round 2: structured peer information.

Round 3: optimizer resolves conflicts.

Do not implement unrestricted conversations in the first release.

## 5. Agent Contract

Each agent returns validated JSON.

Example:

```json
{
  "strategy_id": "S001",
  "agent": "risk_manager",
  "score": 0.72,
  "key_points": [],
  "risks": [],
  "assumptions": []
}
```

## 6. Numerical Integrity

Agents must not invent:
- forecasts;
- revenue;
- profit;
- causal effects;
- confidence.

They consume structured outputs from analytical services.

## 7. Optimizer

The optimizer should consider:
- goal benefit;
- risk;
- uncertainty;
- constraints.

A simple documented score may be:

`strategy_score = normalized_goal_benefit - normalized_risk_penalty`

Fix the scoring formula before final experiments.

## 8. Final Output

```json
{
  "selected_strategy_id": "S001",
  "expected_outcome": {},
  "risk_level": "medium",
  "confidence": 0.0,
  "reasoning": "",
  "alternatives": []
}
```

Confidence must come from an actual documented method.

## 9. Safety

Agents recommend only. They never execute transactions or business actions.
