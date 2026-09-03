# RISK MANAGER GENERALIZATION REPORT

Experiment `risk_manager_real_data_validation` id `70617412`. Dataset:
Benroshan `external-india-ecommerce-v1` (`INDIA_REAL_BUSINESS`, provenance
unverified). Sections 1–6 and the hypotheses / success criteria were fixed
**before** the validation ran.

**Verdict: PROMISING BUT NOT VALIDATED.** On real Indian e-commerce price data,
R0 and R1 produce **identical** extrapolation-risk scores on all 184 test rows
across 23 sub-series — the zero-variance pathology R3 fixes **does not occur**
on this data, so R3's central benefit is *unconfirmed* here. Nothing regressed
(risk ordering, extreme-extrapolation penalisation and — in the SIMULATED
decision comparison — risk-adjusted score and confidence are all preserved).
Real-LLM validation is **BLOCKED** (no provider configured). Production stays
R0.

> **Authoritative current state (updated for paper preparation, 2026-09-03).**
> The sign-off block near the end ("all 15 prior experiment IDs preserved",
> "285 passed", "alembic `0001<->0006`") is a **point-in-time snapshot** from the
> task that added `70617412`; it was never back-updated and nothing about the
> `70617412` result changed. Current authoritative state: **16 frozen
> experiments**, Alembic head **0007**, backend suite **319 passed, 1 skipped**,
> `experiment_manifest.json` sha256 `94aa419c…`. Production stays **R0 / D0**;
> R3 remains **PROMISING — NOT PROMOTED**; real-LLM evaluation remains
> **BLOCKED**. The internal criteria-checklist verdict value
> `"VALIDATED FOR CONTROLLED PRODUCTION TEST"` (produced only if all 7 core
> criteria **and** the real-LLM criterion pass) is **not reachable** in the
> current state and must never be quoted in the paper as production, scientific,
> or real-world validation.

## 1. Research question

Does **R3** (robust extrapolation-risk scale `extrapolation_robust_v1` +
optimizer risk-penalty weight `λ = 0.25`) remain useful when evaluated on
**real Indian business data** and — separately — when the strategy-ranking
layer uses a **real LLM** rather than template-mode agent scores?

This is an **external-validation** study, not another optimization round. No λ
is re-tuned, no threshold is changed, no scenario is added, the Risk Manager is
not modified. If R3 fails outside the synthetic regime, that negative result
stands.

## 2. Motivation from the synthetic calibration

`risk_manager_calibration` (`b8516eef`) established, **on the synthetic suite
only**:
- R0's `_risk_from_extrapolation` has a zero / near-zero-variance pathology
  (constant price history → every move, including a price cut, scores risk 1.0;
  `+5 %` indistinguishable from `+10 %`).
- R1's robust scale removes that pathology while preserving monotone risk
  ordering (Spearman ρ 0.969, 0 violations).
- R3 (R1 + λ = 0.25) improved mean goal achievement 0.084 → 0.168
  (Wilcoxon p = 0.025, 5 / 60 non-zero pairs) and mean risk-adjusted score
  −2 614.8 → +40.5, without a confidence collapse.
- **Verdict: PROMISING.** R3 was *not* promoted — the synthetic suite
  deliberately contains the low-variance regime that exposed the pathology, so
  the result may not generalize.

## 3. Data used

| Role | Dataset | Category | Provenance |
|---|---|---|---|
| Primary validation target | **India E-Commerce Orders (Benroshan)**, `external-india-ecommerce-v1` | `INDIA_REAL_BUSINESS` | **UNVERIFIED** (uploader: "received from my University, original author unknown"). CC0. |
| Contextual covariates | India festival calendar, RBI repo rate | `INDIA_PUBLIC_CONTEXT` | real, pinned libraries |
| Agricultural price | AGMARKNET | `INDIA_AGRICULTURAL_PRICE` | `DATA_PENDING` — no `DATA_GOV_IN_API_KEY` → **SKIPPED** (not fabricated / substituted) |

Benroshan structure: **1 business, 500 orders / 1 500 line items, 2018-04-01 …
2019-03-31 (12 months), 3 categories** (Clothing 949 / Electronics 308 /
Furniture 243 lines), 19 states. Fields present: order id/date, customer name,
state, city, category, sub-category, quantity, `Amount` (line revenue), profit,
monthly per-category target. **Absent (never invented): unit price, discount,
marketing spend, inventory, customer id, churn.** `price` is a **derived implied
unit price** = daily (or monthly) revenue ÷ units, per the committed adapter
`ml/preprocessing/india_ecommerce_adapter.py` (seed 42).

## 4. Data provenance and limitations

- **One business, provenance unverified.** Results are a
  feasibility / generalization probe on this single Indian e-commerce dataset —
  **not** representative of Indian SMEs generally, and **not** a
  population-level claim.
- `price` is a *derived* implied unit price (a revenue/units ratio over a mixed
  furniture+clothing+electronics basket), not an observed list price. It is
  noisier than a real SKU price would be.
- No marketing / inventory data → the strategy generator legitimately produces
  **price-only** candidates for a revenue goal (`Price −5 / −3 / −10 / +5 /
  +10 %`). This is faithful to the dataset, not a restriction we imposed.
- **No real intervention outcomes exist** (`DecisionOutcome` count = 0). Every
  decision in Part B is a **SIMULATED DECISION**.
- Forecasting model: the active registry model is trained on synthetic platform
  data; run on Benroshan-derived features it is out-of-domain. **Forecast
  accuracy and decision quality are reported separately** (§8) and the decision
  numbers are feasibility signals, not validated real-world outcomes.

## 5. Validation protocol

New experiment **`risk_manager_real_data_validation`** (new id; all prior
experiments frozen and untouched). Four parts:

### Part A — Risk-regime partition + calibration (primary)

Real price sub-series are built from the **one** Benroshan raw file by the
adapter's own documented transform (revenue ÷ units), grouped three ways — all
groupings use the dataset's own `category` / `sub_category` fields, nothing is
fabricated:

1. **daily implied price** for {Total, Clothing, Electronics, Furniture};
2. **monthly implied price** (12 points) for {Total, Clothing, Electronics,
   Furniture};
3. **monthly implied price** for every sub-category with ≥ 6 months and ≥ 40
   line items.

**Pre-registered regime classifier** — robust coefficient of variation
`rCV = 1.4826 · MAD(series) / |median(series)|` (outlier-resistant; matches R1's
own scale construction):

| `rCV` | regime |
|---|---|
| `< 0.15` | `LOW_VARIANCE` |
| `0.15 ≤ rCV < 0.40` | `MODERATE_VARIANCE` |
| `≥ 0.40` | `HIGH_VARIANCE` |

Thresholds fixed **before** running. For each sub-series record
`price_variance_regime, historical_price_scale (rCV), historical_price_min,
historical_price_max, historical_price_median`.

For each sub-series compute **R0 risk** and **R1 risk** (= R3 risk) for, off the
last observed price:
`Price −5 %`, `Price +5 %`, `Price +10 %` (legitimate candidates), plus
`Price +25 %`, `Price +50 %`, `Price +100 %` as **explicit extreme-extrapolation
probes** (verify R1 still returns HIGH risk for genuinely extreme moves — it
must not simply flatten everything to low risk).

Per regime and overall: Spearman ρ between **raw natural-unit extrapolation
distance** (₹ beyond the observed [min, max]) and the risk score;
monotonicity-violation count (`risk(+10 %) < risk(+5 %)` strictly); share of
extreme-probe rows still scored `≥ 0.5` (HIGH).

### Part B — R0 vs R1 vs R2-0.25 vs R3 decision comparison (SIMULATED)

Materialize the Benroshan `IEC_TOTAL` daily series as an ephemeral research
`Business` (1 product; `unit_cost` = dataset's median implied unit cost
`(revenue − profit) / units`; no marketing / inventory rows — faithful).
Chronological by construction: `forecast_service.run_recursive_forecast` only
ever consumes past points; an explicit leakage assertion checks that no
feature row uses a date ≥ the forecast origin. Run `analyze_goal` once per
variant for an `increase_revenue` goal (documented target, 2-month horizon).
Record per variant: selected strategy, goal achievement, risk-adjusted score,
confidence, and the full per-strategy risk path. **Every decision is labelled
`SIMULATED DECISION`.**

Fairness: all four variants run on the *same* materialized business, same
candidate set, same Digital Twin predictions (only `risk_score` differs), same
agent growth scores, same goal, same seed. Only the risk formulation and
`λ` differ.

### Part C — Real-LLM validation

Check `settings.llm_enabled` (`llm_provider` **and** `llm_api_key` **and**
`llm_model`). If a provider is genuinely configured, run
`risk_manager_real_llm_validation` (R0 + real LLM vs R3 + real LLM, same model /
prompt / candidates / data / seed). Otherwise report
`REAL_LLM_VALIDATION = BLOCKED` and do not compare template-mode against
real-LLM.

### Part D — DecisionOutcome validation

If ≥ 5 matched predicted/actual `DecisionOutcome` records exist, run the
existing Digital Twin evaluation. Otherwise `Table 2` stays `NOT READY`; no
outcomes are manufactured.

## 6. Fairness controls

For every sub-series / business, all compared variants receive identical
business data, historical observations, candidate set, Digital Twin
predictions, agent inputs, scenario, seed, goal and available features. Only
**risk formulation** and **risk-penalty λ** differ. For R3 specifically: robust
extrapolation scale + `λ = 0.25`, nothing else.

## 7. Risk-regime analysis

**23 real price sub-series** built from the one Benroshan raw file by the
adapter's own `revenue ÷ units` transform, grouped by the dataset's own
category / sub-category fields: daily + monthly implied price for {Total,
Clothing, Electronics, Furniture} and monthly for 15 sub-categories.

Robust-CV regime classification (`rCV = 1.4826·MAD/|median|`; thresholds
`< 0.15` / `< 0.40` fixed before the run):

| Regime | count | examples (rCV) |
|---|---:|---|
| `LOW_VARIANCE` | 3 | Clothing monthly 0.129, Electronics monthly 0.116, Total monthly 0.129 |
| `MODERATE_VARIANCE` | 11 | Furniture monthly 0.313, Furnishings 0.195, Skirt 0.210, Saree 0.350 |
| `HIGH_VARIANCE` | 9 | all four daily series (0.63–0.94), Chairs 0.596, Kurti 0.653, Phones 0.537 |

Risk for `Price −5 / −3 / −10 / +5 / +10 %` (legit) plus `+25 / +50 / +100 %`
(extreme probes), off the last observed price, per sub-series:

| Metric | R0 | R1 (= R3) |
|---|---:|---:|
| Spearman ρ (raw ₹ extrapolation distance vs risk), overall | **0.989** | **0.989** |
| Monotonicity violations (`risk(+10%) < risk(+5%)`), overall | **0** | **0** |
| `r0_equals_r1_all_rows` (all 184 rows) | — | **TRUE** |
| `r1_never_below_r0` | — | **TRUE** |
| Mean risk, legit moves (all regimes) | 0.005 | 0.005 |
| Extreme probes that leave the observed range | 45 / 69 | — |
| …of those, still scored ≥ 0.15 under R1 | — | **82 %** (LOW 100 %, MOD 77 %, HIGH 82 %) |

Per regime: 0 monotonicity violations and `r0 == r1` in **every** regime
(LOW ρ 0.999, MODERATE ρ 0.987, HIGH ρ 0.992).

**Why R0 == R1 on real data.** A real implied-price series — even a
`LOW_VARIANCE` one by rCV — still spans a wide absolute range (Clothing monthly
₹21–56, Electronics monthly ₹97–169). So (a) the R0 denominator
`max(hi−lo, 1e-9)` is never near zero — `hi−lo` is tens of rupees, not a sliver;
(b) modest moves (±5 %, +10 %, +25 %) stay *inside* `[min, max]` → risk 0.0
under both formulas; (c) when a move does exit the range, R1's robust scale
`max(hi−lo, 1.4826·MAD, 0.15·|median|)` is dominated by `hi−lo` every time, so
the R1 denominator equals the R0 denominator. **The zero-variance pathology is
a property of the synthetic promo-only scenario construction, not of real
Indian implied-price data.**

## 8. R0 vs R3 results

### Forecasting accuracy (separate from decision quality — frozen Experiment 1a)

Benroshan daily total units, 51 test days: MAE naive 19.92 / linear 18.47 /
**xgboost 15.27**; RMSE 31.25 / 28.51 / **23.89**. MAPE omitted (zero-sales
days). This is a *forecasting* result and says nothing about decision quality.

### Decision comparison (SIMULATED)

Materialised business: Benroshan `IEC_TOTAL` daily frame — 1 business, 1 product,
307 sale days over 12 months (2018-04-01 … 2019-03-31), implied unit cost ₹34.0
`(revenue − profit)/units` median, median implied price ₹58.97. No marketing /
inventory (faithful). **Leakage check: PASS** — history last date =
forecast origin = 2019-03-31; no Sale row post-dates the origin.

`increase_revenue` goal (documented +10 % target, 2-month horizon). Candidates:
price-only (`Price −10 / −5 / −3 / +5 / +10 %`) — no marketing data.

| Variant | Selected strategy | Goal ach. | Risk-adjusted | Confidence | Selected DT-risk | Changed vs R0 |
|---|---|---:|---:|---:|---:|---:|
| **R0** | `Price +10%` | 1.00 | 5 848.25 | 0.161 | 0.00 | — |
| R1 | `Price +10%` | 1.00 | 5 848.25 | 0.161 | 0.00 | no |
| R2-0.25 | `Price +10%` | 1.00 | 5 848.25 | 0.161 | 0.00 | no |
| **R3** | `Price +10%` | 1.00 | 5 848.25 | 0.161 | 0.00 | no |
| D1 (reference) | `Price +10%` | 1.00 | 5 848.25 | 0.161 | 0.00 | no |

**Every variant makes the identical decision.** The Benroshan total price range
is so wide (₹3–454) that even `Price +10%` extrapolates zero → DT-risk 0.0 → RM
safety ≈ 1.0 → the risk-penalty term is already ≈ 0, so bounding it (R2/R3) or
removing it (D1) changes nothing. The R0-vs-R3 distinction **collapses on real
data** because there is no risk penalty to bound.

`goal_achievement = 1.00` is a **SIMULATED** artefact — the out-of-domain
forecasting model projects a large revenue lift for a +10 % price rise with no
volume penalty. It is **not** a validated real-world decision outcome.
`n_businesses = 1`, `n_observations = 307`, `n_time_periods = 12 months`,
`n_products = 1` → **NO INFERENTIAL TEST** (days are not independent
businesses).

## 9. Risk calibration analysis

- **R1's robust scale is inert on this real data.** `hi − lo` dominates the
  `max(…)` normaliser on every one of the 23 sub-series, so R1's denominator
  equals R0's and the risk scores are byte-identical (`r0_equals_r1_all_rows =
  TRUE`, 184 / 184 rows).
- **R1 does not flatten risk.** Among the 45 extreme probes that genuinely
  leave the observed range, 82 % still score ≥ 0.15 under R1, and R1 never
  scores *below* R0 anywhere (`r1_never_below_r0 = TRUE`). The `+100 %` probe on
  Clothing monthly scores 0.78 (HIGH) under both.
- **The λ = 0.25 bound (R2 / R3) is inert on this real data** because the
  Digital Twin already assigns the selected `Price +10%` a risk score of 0.0 —
  there is no penalty for λ to scale.

## 10. Real-LLM validation

**`REAL_LLM_VALIDATION = BLOCKED`.** `settings.llm_enabled = False` —
`llm_provider = ""`, `llm_model = ""` (only an unused `llm_api_key` is present).
No provider was invented, hard-coded or bypassed. Template-mode agent scores are
**not** treated as real-LLM evidence. **H6 is NOT TESTABLE.** A configured
provider would enable `risk_manager_real_llm_validation` (R0 + real LLM vs
R3 + real LLM, same model / prompt / candidates / data / seed).

## 11. DecisionOutcome validation

**`INSUFFICIENT`.** `DecisionOutcome` records = 0, matched
`PredictionEvaluation` = 0 (< 5). **Table 2 remains `NOT READY`.** No outcomes
were manufactured.

## 12. Statistical analysis

`n_businesses = 1`, `n_products = 1`, `n_observations = 307` (sale days),
`n_time_periods = 12` months. The rows are not independent businesses, so
per the protocol: **NO INFERENTIAL TEST** on the decision comparison. Part A is
descriptive (Spearman ρ, violation counts) across 23 real sub-series and 184
strategy rows; ρ and violation counts are reported as-is, not as population
estimates. The synthetic-suite Wilcoxon result (R3 − R0: p = 0.025, 5 / 60
non-zero pairs) is **not** re-used as real-data evidence.

## 13. Hypothesis results

Pre-registered hypotheses (fixed before examining validation results):

| | Hypothesis |
|---|---|
| **H1** | R3 reduces pathological risk inflation in low-variance histories. |
| **H2** | R3 preserves monotone risk ordering on realistic historical variation. |
| **H3** | R3 improves risk-adjusted decision quality relative to R0. |
| **H4** | R3 does not systematically eliminate risk penalties (extreme extrapolation still penalised). |
| **H5** | R3 generalizes beyond the synthetic low-variance regime (result not dependent on one regime). |
| **H6** | If real-LLM validation is available, R3's benefit survives replacing template-mode scores with real-LLM reasoning. |

| Hypothesis | Result | Basis |
|---|---|---|
| **H1** — low-variance pathology reduced | **NOT ASSESSABLE** | R0 shows *no* low-variance inflation on this real data (mean R0 legit-move risk in the LOW regime = 0.0). A real implied-price series still spans a wide `min…max`, so the R0 denominator never collapses. There is no pathology here for R1 to fix. |
| **H2** — ordering preserved on realistic variation | **SUPPORTED** | Spearman ρ 0.989 overall (identical R0/R1); 0 monotonicity violations in every regime. |
| **H3** — risk-adjusted not worse than R0 (SIMULATED) | **SUPPORTED** | R3 risk-adjusted 5 848.25 = R0 = R2-0.25. Identical (SIMULATED decision; no real outcome). |
| **H4** — extreme extrapolation still penalised | **SUPPORTED** | 82 % of out-of-range extreme probes stay ≥ 0.15 under R1; `r1_never_below_r0 = TRUE`; `+100 %` probe still HIGH. |
| **H5** — generalizes beyond one regime | **SUPPORTED (regime-robust), but R3 has no measurable effect on real data** | Real data spans 3 regimes; ordering and non-inflation hold in all. "Generalizes" here means *R3 does not break* outside the synthetic regime — **not** that R3 helps. `r0_equals_r1_all_rows = TRUE`. |
| **H6** — survives a real LLM | **NOT TESTABLE** | Real-LLM validation BLOCKED — no provider configured. |

## 14. External validation verdict

**Success criteria — R3 is "externally validated" only if all hold:**
1. pathological low-variance risk inflation is reduced;
2. risk ordering remains monotonic;
3. R3 does not systematically assign low risk to extreme extrapolation;
4. risk-adjusted quality is not worse than R0;
5. confidence does not collapse;
6. the result is not dependent on a single synthetic regime;
7. the result is reproducible;
8. if real-LLM validation is performed, the improvement survives the LLM layer.

| # | Criterion | Met? |
|---|---|:--:|
| 1 | pathological low-variance risk inflation is reduced | **NO** — not *present* on this real data, so R3's central benefit is **unconfirmed** |
| 2 | risk ordering remains monotonic | ✓ (ρ 0.989, 0 violations) |
| 3 | R3 does not systematically assign low risk to extreme extrapolation | ✓ (82 % of out-of-range extremes ≥ 0.15; never below R0) |
| 4 | risk-adjusted quality not worse than R0 | ✓ (identical, SIMULATED) |
| 5 | confidence does not collapse | ✓ (0.161 = R0) |
| 6 | result not dependent on a single synthetic regime | ✓ (3 real regimes; behaviour holds in all) |
| 7 | reproducible | ✓ (deterministic; committed data; fixed seed) |
| 8 | improvement survives the real LLM | **NOT TESTED** — BLOCKED |

**Nothing regressed on real data** (criteria 2–7 all hold). But the criterion
that matters most — that R3's calibration *benefit* is real outside the
synthetic regime — is **not confirmed**, because the pathology R3 targets does
not occur in this real Indian dataset, and criterion 8 is untested.

### EXTERNAL VALIDATION VERDICT: **PROMISING BUT NOT VALIDATED**

## 15. Production recommendation

**Do not promote R3. Production stays R0 / D0.**

- R3 is a **principled fix for a real defect** that was demonstrated on the
  synthetic suite (zero/low-variance denominator collapse). On the one real
  Indian dataset available it is **inert** — identical risk scores, identical
  decisions — because that dataset's implied-price series are wide enough that
  the R0 denominator never collapses.
- R3 is **safe** on real data: it never raised risk pathologically, never
  lowered it below R0, preserved monotone ordering, and preserved confidence.
  So keeping R3 available as an opt-in `PipelineOptions.risk_model` carries no
  downside on data like this.
- **Before any production calibration**, the outstanding evidence is: (a) a
  dataset — real or a faithfully-degenerate synthetic proxy of a real
  low-variance SME (e.g. a fixed-price subscription business, a regulated-price
  product) — where R0's pathology actually bites; (b) a **real-LLM** run
  (currently BLOCKED) to check the λ = 0.25 bound with separated agent growth
  scores; (c) ≥ 5 real `DecisionOutcome` records to ground decision quality.
- Recommended next step: **hold**. Do not add scenarios or retune. Revisit only
  when (a)/(b)/(c) become available.

## 16. Paper interpretation

**Established** (safe to state):
- R0 exhibits a zero / near-zero-variance extrapolation-risk pathology.
- R3 reduces that pathology on the synthetic calibration suite.
- R3 preserved monotonic risk ordering on that suite.

**To be validated** (this study's subject — see the verdict):
- R3 generalizes to real Indian SME / business data.
- R3 improves real-world decision quality.
- R3 remains effective with a real LLM.

The paper must **not** state "R3 is proven superior". The accurate statement is:
*"R3 corrects a demonstrated zero/low-variance extrapolation-risk pathology on
the synthetic calibration suite. On the one real Indian e-commerce dataset
available, that pathology did not arise, so R3's benefit could not be confirmed
externally; R3 did not regress any risk-calibration property there. Real-LLM and
real-outcome validation remain outstanding."*

## 17. Reproducibility

- Experiment `risk_manager_real_data_validation` id `70617412`; dataset
  `external-india-ecommerce-v1` (committed processed + raw CSVs, CC0).
- Code: `app/services/risk_manager_generalization_service.py` — Part A reads
  `data/external/india_ecommerce/raw` via `ml/preprocessing/india_ecommerce_adapter`
  (seed 42); Part B materialises `IEC_TOTAL` as an ephemeral `Business` and runs
  `decision_service.analyze_goal` with `PipelineOptions(risk_model=…,
  risk_penalty_lambda=…)`. Deterministic (LLM template mode, fixed forecasting
  registry).
- Regime classifier: robust CV `1.4826·MAD/|median|`, thresholds `0.15` / `0.40`
  (pre-registered in §5).
- All 15 prior experiment IDs unchanged; `70617412` is additive. Production
  defaults unchanged (`risk_model=None`, `risk_penalty_lambda=1.0`).

---

## GENERALIZATION VALIDATION SUMMARY

```
Synthetic calibration result:   R3 = PROMISING

Indian real-data validation:    PROMISING BUT NOT VALIDATED
                                (R0 == R1 on all 184 real test rows / 23 sub-series;
                                 the zero-variance pathology R3 fixes does not occur
                                 on real Indian implied-price data; nothing regressed)

Real-LLM validation:            BLOCKED  (no LLM provider configured)

DecisionOutcome validation:     INSUFFICIENT  (0 records; Table 2 NOT READY)

R0:
goal achievement:   1.00  (SIMULATED)
risk-adjusted:       5848.25  (SIMULATED)
confidence:          0.161

R3:
goal achievement:   1.00  (SIMULATED — identical to R0)
risk-adjusted:       5848.25  (identical to R0)
confidence:          0.161  (identical to R0)

Risk ordering (real data, 23 sub-series, 184 rows):
Spearman rho:            0.989  (identical for R0 and R1)
monotonicity violations: 0  (every regime)

H1  (low-variance pathology reduced):        NOT SUPPORTED  (NOT ASSESSABLE — pathology absent on real data)
H2  (ordering preserved, realistic variation): SUPPORTED
H3  (risk-adjusted not worse, SIMULATED):     SUPPORTED
H4  (extreme extrapolation still penalised):  SUPPORTED
H5  (generalizes beyond one regime):          SUPPORTED  (regime-robust; R3 has no measurable effect on real data)
H6  (survives real LLM):                      NOT TESTABLE  (BLOCKED)

FINAL VERDICT:  PROMISING BUT NOT VALIDATED

Production architecture changed:   NO   (additive PipelineOptions.risk_model / .risk_penalty_lambda,
                                        defaults None / 1.0; no variant promoted)
Production models changed:          NO
Production default:                 R0
Previous experiments changed:       NO   (all 15 prior experiment IDs preserved)
New experiment IDs:                 70617412  (risk_manager_real_data_validation v1)

Tests:  [point-in-time snapshot — see the authoritative box at the top of this file]
Backend:   pytest -q — 285 passed, 1 skipped   (current authoritative: 319 passed, 1 skipped)
Frontend:  npm run build compiled (tsc clean) ; npm run lint 0 errors
E2E:       scripts/audit_e2e.py — no assertion failures ; alembic round-trip clean, no schema change
           (round-trip target was 0001<->0006 at the time; current head is 0007)
```
