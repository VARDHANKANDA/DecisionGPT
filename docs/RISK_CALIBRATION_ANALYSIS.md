# Extrapolation-Risk Formula — Diagnostic & Calibration Pre-Registration

Companion to `docs/RISK_MANAGER_CALIBRATION_REPORT.md`. This document is the
**pre-registration**: it fixes the mathematics, the worked example, the
degeneracy hypothesis, the three calibration variants and the R3 selection
criterion **before** the calibration experiment is run.

## 1. The production formula (`digital_twin_service._risk_from_extrapolation`)

```python
def _risk_from_extrapolation(history, scenario):
    overshoot = 0.0
    for feature, value in scenario.items():
        lo, hi = history.get(feature, (value, value))
        span = max(hi - lo, 1e-9)
        if value < lo:
            overshoot = max(overshoot, (lo - value) / span)
        elif value > hi:
            overshoot = max(overshoot, (value - hi) / span)
    risk_score = round(min(overshoot, 1.0), 4)
    # < 0.15 LOW ; < 0.5 MODERATE ; else HIGH
```

Inputs (built in `simulate_strategy`):
- `history` — `{"price": (min, max), "marketing_spend": (min, max)}` from the
  business's own 90-day daily series.
- `scenario` — `{"price": scenario_price, "marketing_spend": scenario_marketing_spend}`,
  the post-action inputs actually fed to the forecasting model.

| Question | Answer (from the implementation) |
|---|---|
| How is the historical range/span computed? | `span = hi - lo` = observed `max − min` of that feature's daily series, floored at `1e-9`. |
| How is zero / near-zero variance handled? | Only by the `1e-9` floor. If `hi == lo` (constant feature) `span = 1e-9`, so **any** `value ≠ lo` yields `overshoot = |value − lo| / 1e-9 → ∞`, clipped to `1.0`. |
| How is distance-outside-range computed? | Only the part strictly outside `[lo, hi]` counts: `(lo − value)` if below, `(value − hi)` if above. Movement *within* the observed range contributes `0`. |
| How is the score bounded? | `min(overshoot, 1.0)`; lower bound `0` by construction. |
| Do price / marketing / inventory share the logic? | Price and `marketing_spend` do. **Inventory is not in the `scenario` dict** — an inventory change never contributes to this risk term (it only affects the fulfilment cap). |
| What does the score represent? | **Extrapolation *distance*** beyond the training range, expressed in units of the observed range width. Not a probability, not prediction-interval uncertainty (that is the separate `uncertainty_penalty` inside `risk_manager.evaluate`). |

The Risk Manager then maps it to a 0–1 safety score:
`RM = clamp01(1 − risk_score − uncertainty_penalty − inventory_penalty − causal_penalty)`,
and the optimizer applies `final_score = (BA+FA)/2 − (1 − RM)`.

## 2. The zero / low-variance degeneracy

Normalising by `max − min` makes the metric scale-free but **explodes as the
denominator → 0**. The synthetic research businesses set price to
`selling_price` on non-promo days and `promo_price` on every 10th day, so the
*only* price variation in history is the promotional discount. The observed
range is therefore narrow and one-directional (`[promo_price, selling_price]`),
and its width — the *promo depth* — becomes the yardstick for how far a price
**increase** is "extrapolating". A business that ran deeper promos would get a
*lower* risk score for the same price rise, which is backwards.

### Worked example (S01: `selling_price = 600`, `promo_price = 540`)

`history["price"]` = 81 days at 600 + 9 days at 540 → `lo = 540, hi = 600, span = 60`.
`baseline_price = 600` (last day is non-promo).

| Action | scenario price | overshoot = (price − 600) / 60 | R0 risk | Band |
|---|---:|---:|---:|---|
| Price −5% | 570 | inside `[540, 600]` → 0 | 0.00 | LOW |
| Price +5% | 630 | 30 / 60 | **0.50** | HIGH |
| Price +10% | 660 | 60 / 60 | **1.00** | HIGH |

A **5 % price increase** — an ordinary business lever — is scored maximally or
near-maximally risky, purely because the historical price series happened to
vary by only 10 %. Confirmed at suite scale by the Risk Manager diagnostic:
mean R0 risk `Price +5%` ≈ 0.68, `Price +10%` ≈ 0.98; 0 / 390
`RISK_SCORE_MISMATCH` (the Risk Manager is faithful — the *formula* is the
issue).

### Constant-history stress test

`history["price"] = [100, 100, 100, 100, 100]` → `span = 1e-9`:

| Action | R0 risk |
|---|---:|
| Price +5% (105) | **1.0** (HIGH) |
| Price +10% (110) | **1.0** (HIGH) |
| Price −5% (95) | **1.0** (HIGH) |

Every move is "catastrophic", and **the ordering is destroyed** — a 5 % move is
indistinguishable from a 10 % move.

## 3. Calibration variants (pre-specified — no parameter search)

### R0 — current production formula. Unchanged. `risk_formula_version = extrapolation_range_v1`.

### R1 — robust historical scale. `risk_formula_version = extrapolation_robust_v1`.

Identical overshoot / clip / banding; only the normaliser changes:

```
scale = max( hi - lo,
             1.4826 * MAD(series),          # robust σ estimate (Hampel)
             REL_FLOOR * |median(series)| )  # scale-aware floor, REL_FLOOR = 0.15
```

Rationale, term by term:
- `hi - lo` is kept so a genuinely wide history is **unaffected** (the floor
  can only *raise* the denominator, never lower it → never inflates risk).
- `1.4826 · MAD` is the standard robust standard-deviation estimator; non-zero
  whenever ≤ 50 % of observations are identical, and outlier-resistant.
- `REL_FLOOR · |median|` is the floor that governs a *degenerate* history. It
  is **not a constant** — it scales with the business. `REL_FLOOR = 0.15` is
  pre-specified and motivated: *a price / marketing move of 15 % off the
  historical median is the unit of extrapolation distance when the history is
  otherwise flat.* 15 % is a common "materially large" business-change
  threshold. It is **not** tuned to any outcome.

Predicted behaviour (verified before the run):

| History | +5% | +10% | −5% |
|---|---|---|---|
| constant `[100]×5` | R0 1.00 → **R1 0.33** | R0 1.00 → **R1 0.67** | R0 1.00 → **R1 0.33** |
| low-var `[99,100,101,100,100]` | R0 1.00 → **R1 0.27** | R0 1.00 → **R1 0.60** | R0 1.00 → **R1 0.27** |
| normal-var `[95,100,105,100,98]` | R0 0.00 → R1 0.00 | R0 0.50 → **R1 0.33** | R0 0.00 → R1 0.00 |

R1 removes the "any move = infinite risk" pathology, **keeps monotonicity**
(+10 % always ≥ +5 %), keeps symmetric ±5 % risk, and barely touches the
normal-variance case.

### R2 — bounded risk contribution. R0 risk score unchanged; the optimizer term becomes `− λ·(1 − RM)`.

Pre-specified `λ ∈ {0.25, 0.50, 0.75}`. No continuous search. Motivation:
the production `λ = 1` lets a single strategy's risk penalty move `final_score`
by a full 1.0 — larger than the entire `(BA+FA)/2` growth term's realistic
range. `λ < 1` keeps the brake but stops it from dominating.

### R3 — combined. R1 robust risk **+** the λ chosen by the criterion below.

**R3 λ selection criterion — fixed before the run (task §12).** Among
`λ ∈ {0.25, 0.50, 0.75}`, take the **smallest** λ whose `R2-λ` run:
1. does not reduce mean risk-adjusted score below D0 (R0), **and**
2. keeps mean confidence ≥ `0.60 × D0`'s mean confidence (no D1-style collapse).

If no λ qualifies, R3 uses the documented fallback midpoint **λ = 0.50**.
This criterion is objective, computable, and deliberately **not** based on goal
achievement.

## 4. What is held fixed

The Digital Twin's predicted units / revenue / profit, the candidate set, the
agent growth scores (BA / FA), the causal evidence, the scenario generation and
the seeds are **identical** across all variants. Only *risk estimation* (R1) and
*risk contribution weight* (R2 λ) change, so any difference in outcome is
cleanly attributable to Risk Manager calibration.

## 5. Pre-specified success criteria (task §12)

A calibration variant is **PROMISING** only if it satisfies all of:
1. improves goal achievement over D0;
2. does not eliminate risk ordering (Spearman ρ between raw extrapolation
   distance and risk score ≥ 0.3);
3. no `Price +10%` scored safer than `Price +5%` (monotonicity violations = 0);
4. improves or preserves risk-adjusted performance vs D0;
5. avoids the D1 confidence collapse (mean confidence ≥ 0.60 × D0);
6. remains interpretable (one documented formula / weight);
7. no scenario-specific tuning (one global parameter set).

**PARTIALLY PROMISING** = criteria 1–3 hold and ≥ 5 / 7 pass.
Otherwise **NO SATISFACTORY CALIBRATION** — a valid research outcome.

No variant is promoted regardless of verdict; production stays R0 / D0.
