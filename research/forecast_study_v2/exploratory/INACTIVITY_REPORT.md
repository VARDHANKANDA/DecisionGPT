# Customer-inactivity thread — exploratory record (separate from the forecasting paper)

**Decision.** The customer-inactivity classification study is **not part of the forecasting paper** of forecast_study_v2. Reasons (all from the independent audit of v1, `../forecast_study_v1/audit_v1/`): its evidence is weak and partly redundant, and it answers a different question with a proxy label.

## What it is

Target: **inactivity** of customers of one UK wholesaler — no invoice in the 90 days after a cutoff for customers seen before it. It is **not** verified churn: there is no contractual relationship, no churn definition and no intervention.

## What was verified (audit; labels rebuilt from raw transactions)

* Labels, recency scores and customer sets equal the stored ones at both origins (test cutoffs 2011-06-12 and 2011-09-10).
* ROC-AUC/PR-AUC of the best classifier vs a recency baseline: +0.028 / +0.010 (origin A) and +0.037 / +0.020 (origin B); independent Holm p ≤ 0.024; calibration separate from discrimination.

## Why it is not a confirmatory or main-paper result

1. The two origins are not independent: 4,951 customers (94 % of origin B's test customers) appear in both test snapshots; their labels correlate at 0.40; about half of each test cohort already appears in the earliest training snapshot (repeated measures).
2. A random 50/50 customer split removed the origin-A advantage (ROC-AUC +0.011 [−0.006, +0.028]); origin B held (+0.041 [0.030, 0.053]); that run was not independently re-executed.
3. Practical value is small: precision among customers flagged at fixed contact budgets differs from the recency rule by about 0–2 percentage points; at origin A recency was better in the top 10 %.
4. Calibration deterioration at origin B is explained by prevalence shift (validation 0.677 vs test 0.565): an oracle intercept shift lowers the Platt ECE from 0.126 to 0.019 (diagnostic using test labels).
5. No claim about retention, revenue or business impact is possible without intervention evidence.

## Status and what a defensible study would need

Retained as a transparent exploratory record (v1 results are unchanged). A separate future study would need an independent customer cohort, a defensible churn or inactivity definition with a sensitivity analysis over window length, chronological validation with customer-disjoint evaluation, comparison against recency and RFM baselines, precision at contact budgets with uncertainty, and an analysis of prevalence shift. It is not run here.
