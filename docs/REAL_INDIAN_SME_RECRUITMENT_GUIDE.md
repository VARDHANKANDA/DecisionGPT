# Recruiting Indian SMEs for DecisionGPT Real-World Validation — Research Team Guide

For the **research team**, not developers. It explains who to recruit, who is
eligible, which decisions to prioritise, and how a genuine decision → prediction
→ implementation → outcome record enters the pipeline.

Companion docs:
`docs/REAL_INDIAN_SME_VALIDATION_METHODOLOGY.md` (paper methodology),
`docs/REAL_SME_DATA_COLLECTION_GUIDE.md` (SME-facing),
`docs/REAL_INDIAN_SME_DATA_DICTIONARY.md` (fields),
`docs/REAL_INDIAN_SME_DATA_QUALITY_PROTOCOL.md` (record scoring),
`docs/REAL_WORLD_VALIDATION_ROADMAP.md` (phases),
`docs/templates/*` (checklist, researcher form, participant instructions,
consent/provenance, collection schedule, import template).

---

## 1. Why this stage exists

Everything to date is **synthetic or external-benchmark** evidence. The one
thing missing is: *a genuine Indian SME made a real DecisionGPT-supported
decision, and we recorded what actually happened.* That is what this stage
collects. Current state: `REAL_INDIAN_SME_OUTCOME = 0`.

## 2. Who should participate

Genuine Indian SMEs across **multiple business categories**:

| Category | Typical supported decisions |
|---|---|
| Retail (apparel, electronics, grocery, general) | price ±, marketing ±, inventory reorder ± |
| E-commerce / D2C | price ±, marketing ±, campaign allocation |
| Restaurant / food service | price ±, marketing ± |
| Wholesale / distribution | price ±, inventory allocation ± |
| Small manufacturing | inventory / reorder ± |
| Services (with priced offerings & records) | price ±, marketing ± |

**Initial target: 5–10 businesses.** Prefer several categories and several
states, but **do not fabricate diversity** — if two apparel retailers in one
state participate, that is what the report says.

> This is a small feasibility sample. It is **not** statistically
> representative of Indian SMEs, and no report may claim it is.

## 3. Participant eligibility

**Include** a business that:

- operates in India (a real, currently-trading business);
- keeps enough records to support one of the supported decision types (a
  baseline revenue figure, and units and/or a cost basis where the decision
  needs it);
- participates **voluntarily** and completes informed consent through the
  approved research process (`docs/templates/real_sme_consent_and_provenance.md`);
- can report the **actual** outcome after the chosen horizon
  (7 / 14 / 30 / 60 / 90 days);
- agrees to **anonymised** research use of aggregate figures.

**Exclude**:

- fabricated, test, or demo "businesses";
- synthetic data or public-dataset rows dressed up as a participant;
- a business whose provenance / consent cannot be established;
- any record that would require personal or customer-identifying data;
- a decision whose outcome occurred **before** the DecisionGPT recommendation,
  or where the actual outcome cannot be separated from the decision period;
- a decision the business would not have made anyway (see §5).

**Do not** make legal or compliance claims. Route all consent / privacy
language to appropriate institutional / legal review first.

## 4. Which decisions to prioritise

Only decision types DecisionGPT already simulates. The decision must be a
**genuine, business-relevant** choice the SME was going to make regardless of
the study.

| Family | Examples (the SME's real choice) |
|---|---|
| **Price** | raise a product line's price by 5 % / 10 %; cut price by 5 % |
| **Marketing** | increase or decrease marketing spend; shift campaign allocation |
| **Inventory** | increase / decrease reorder quantity; change inventory allocation |

Do **not** ask an SME to make a change purely for the study, or push a specific
recommendation. The researcher records what DecisionGPT recommends and whether
the SME **accepted, rejected, or partly implemented** it — all three are valid
data.

## 5. Data-collection workflow (end to end)

```
Recruit SME  (category, state; genuine operating business)
   │
   ▼
Consent + provenance  (approved form; kept OUTSIDE the repo/DB)
   │
   ▼
Anonymise business  (SME picks an opaque code, e.g. SME-A1)
   │
   ▼
Collect historical business data  (baseline period defined; enough for the decision type)
   │
   ▼
DecisionGPT analyses the data
   │
   ▼
Prediction recorded  (predicted revenue / units / profit / risk / confidence)
Decision recommended (strategy, e.g. "Price +5%")
   │  ── the actual outcome does NOT exist yet and must never be entered here ──
   ▼
SME accepts / rejects / part-implements
   │
   ▼
If implemented → record the implementation date + the strategy actually applied + any deviations
   │
   ▼
Wait the predefined horizon  (7 / 14 / 30 / 60 / 90 days)
   │
   ▼
Collect the ACTUAL outcome  (actual revenue / units / profit for the SAME horizon)
   │
   ▼
Validate the record  (docs/REAL_INDIAN_SME_DATA_QUALITY_PROTOCOL.md → VALID / REQUIRES_REVIEW / REJECTED)
   │
   ▼
Import:  python scripts/import_real_sme_outcomes.py <file>.csv|json
   │  (India-only, anonymisation, consent, supported decision type, horizon,
   │   horizon↔window consistency, decision-before-outcome, PII rejection,
   │   duplicate rejection — all enforced by the importer)
   ▼
DecisionOutcome (source_type = real_indian_sme)
   │
   ▼
PredictionEvaluation  (predicted_change vs actual_change, per target, computed independently)
   │
   ▼
Digital Twin evaluation  →  Research → Digital Twin Evaluation → Real Indian SME Outcomes
```

**Leakage rule (non-negotiable):** the actual outcome must not be available to
DecisionGPT — or entered into any prediction field — when the original
prediction / decision is generated. The importer rejects an outcome dated on or
before the decision, and rejects an outcome window that does not match the
stated horizon.

## 6. Reaching the milestones

- **5 genuine matched outcomes** → Table 2 auto-enables
  (`REAL_INDIAN_SME_OUTCOME` only). Below 5: `Table 2 = NOT READY`.
- The first analysis is **descriptive only** — report `n_businesses`,
  `n_decisions`, `n_outcomes`, decisions per business, category, state, horizon
  distribution. Ten decisions from one SME is **one** business, not ten.
- Record **contextual events** that could confound an outcome (festival period,
  unusual promotion, supply disruption, competitor move, weather, stockout,
  demand spike) as *possible confounders* — never silently correct for them.

## 7. What this stage does NOT do

- No new synthetic experiment, no additional public/Kaggle dataset, no λ tuning,
  no risk-formula change, no R3 promotion. Production stays **R0 / D0**.
- Real-LLM validation stays **BLOCKED** until a provider is genuinely
  configured (`docs/REAL_LLM_VALIDATION_PROTOCOL.md`).
- No record is inserted into the repository. The templates are collection
  scaffolding; genuine participant data lives only in the working DB after a
  clean import.
