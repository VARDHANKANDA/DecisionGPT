# DecisionGPT — Frontend Specification

## 1. Technology

Recommended:
- Next.js
- React
- TypeScript
- Tailwind CSS
- Recharts
- React Query/TanStack Query

## 2. Pages

### `/`
Landing page.

### `/onboarding`
Business setup.

### `/dashboard`
Business KPI dashboard.

### `/data`
Upload and data quality.

### `/goals`
Create and manage goals.

### `/decision`
Run strategic analysis.

### `/simulation`
Compare Digital Twin strategies.

### `/causal-graph`
Visualise the evidence-labelled causal graph.

### `/history`
Decision and outcome history.

### `/chat`
AI business assistant.

## 3. Dashboard

Show:
- revenue;
- sales;
- profit;
- customers;
- conversion;
- marketing ROI;
- forecast;
- active goal;
- latest recommendation.

## 4. Decision Page

Show:

1. Goal
2. Current situation
3. Candidate strategies
4. Simulation comparison
5. Agent evaluations
6. Selected strategy
7. Risk
8. Uncertainty
9. Explanation
10. Assumptions

## 5. Causal Graph

Nodes and edges should be interactive.

Edge evidence must be visible.

Example:
`DATA_SUPPORTED`

Do not visually imply that an assumed edge is proven.

## 6. UX Rules

- Use INR formatting by default.
- Never show unexplained confidence percentages.
- Clearly label estimates.
- Clearly distinguish historical facts from predictions.
- Show insufficient-data states.
- Avoid overwhelming the user with raw agent conversations.

## 7. Responsive Design

The prototype should work on:
- desktop;
- tablet;
- mobile browser.

## 8. Accessibility

Use:
- semantic HTML;
- keyboard navigation;
- readable contrast;
- labels for charts;
- accessible error messages.
