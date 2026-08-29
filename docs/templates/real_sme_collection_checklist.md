# Real Indian SME Decision-Outcome — Collection Checklist

Complete this for **each decision record** before importing it. If any box
cannot be ticked, do **not** import the record.

```
[ ] The SME is genuinely located / operating in India
[ ] Participation is voluntary (consent form completed — real_sme_consent_and_provenance.md)
[ ] The business identity is anonymised (self-chosen code only; no name)
[ ] No PII in any field (no Aadhaar / PAN / GSTIN / phone / email / customer data /
        bank or card numbers / identifying address)
[ ] The decision genuinely existed BEFORE the outcome was recorded
[ ] The DecisionGPT prediction was generated BEFORE the actual outcome was known
[ ] The prediction horizon is recorded (7 / 14 / 30 / 60 / 90 days)
[ ] The actual outcome corresponds to the SAME horizon as the prediction
[ ] Revenue / profit / units definitions are documented and consistent
        (same period type, same accounting basis for baseline / predicted / actual)
[ ] The decision type is one DecisionGPT supports
        (price_increase / price_decrease / marketing_increase / marketing_decrease /
         inventory_decision)
[ ] The outcome figures are the SME's real observed values — nothing fabricated,
        estimated forward, or back-filled
[ ] source_type = real_indian_sme ; business_country = IN ;
        data_consent_status = consented ; anonymization_status = anonymized
[ ] collection_method and collection_date recorded
[ ] The example / template row has been deleted from the file
```

## Import & verification

```
[ ] Ran: DATABASE_URL=... python scripts/import_real_sme_outcomes.py <file>.csv|json
[ ] Every intended row shows "imported"; example rows show "SKIP";
        rejected rows list a clear reason
[ ] Research -> Digital Twin Evaluation -> Real Indian SME Outcomes shows the
        expected businesses / decisions / outcomes count
[ ] n_businesses reflects distinct businesses (NOT decision count)
[ ] If n_outcomes < 5 -> Table 2 still NOT READY, statistical_inference = DESCRIPTIVE ONLY
```
