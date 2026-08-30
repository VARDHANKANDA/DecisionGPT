# Real Indian SME Participant Checklist

One copy per **decision record**. If any box cannot be ticked, do **not**
import the record (see `docs/REAL_INDIAN_SME_DATA_QUALITY_PROTOCOL.md`).

Anonymised business ID: `____________`   Decision reference: `____________`

## Before the decision

```
[ ] SME eligibility confirmed (genuine, operating in India, real records)
[ ] Informed consent completed via the approved process
[ ] Provenance recorded (source_type, collection_method, collection_date, consent status)
[ ] Anonymised business ID created (opaque token; no name / contact)
[ ] Business type recorded
[ ] State (and district) recorded
[ ] Historical business data available for the decision type
[ ] Decision type is one DecisionGPT supports
        (price_increase / price_decrease / marketing_increase / marketing_decrease / inventory_decision)
[ ] Baseline period defined (same period basis that "actual" will use)
[ ] DecisionGPT prediction generated
[ ] Prediction timestamp recorded
[ ] Predicted revenue recorded  (and predicted units / profit where available)
[ ] Predicted risk and confidence recorded
[ ] Prediction horizon chosen and recorded (7 / 14 / 30 / 60 / 90 days)
[ ] The actual outcome does NOT exist yet / is NOT known
```

## At implementation

```
[ ] Strategy accepted / rejected / partly implemented — recorded
[ ] Implementation date recorded (if implemented)
[ ] The strategy actually implemented recorded (may differ from the recommendation)
[ ] Any deviations from the recommended strategy documented
```

## At the outcome horizon

```
[ ] Outcome date recorded (>= decision date; window matches the stated horizon)
[ ] Actual revenue recorded (same period basis as baseline)
[ ] Actual units recorded where available
[ ] Actual profit recorded where available
[ ] Actual marketing spend recorded where applicable
[ ] Actual inventory measure recorded where applicable
[ ] Outcome status recorded (achieved / partially_achieved / not_achieved / inconclusive)
[ ] Contextual events / deviations documented as POSSIBLE CONFOUNDERS, not corrected
        (festival period · unusual promotion · supply disruption · competitor change ·
         weather event · stockout · unexpected demand change)
```

## Import & verification

```
[ ] Example / template rows removed from the file
[ ] Ran: python scripts/import_real_sme_outcomes.py <file>.csv|json
[ ] Row shows "imported"; no PII / duplicate / horizon / leakage rejection
[ ] Research → Digital Twin Evaluation → Real Indian SME Outcomes shows the new count
[ ] n_businesses = distinct businesses (NOT decision count)
[ ] If n_outcomes < 5 → Table 2 still NOT READY, statistical_inference = DESCRIPTIVE ONLY
```
