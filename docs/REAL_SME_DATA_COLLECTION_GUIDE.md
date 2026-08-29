# Sharing a Real Decision Outcome with DecisionGPT — Guide for Indian SME Owners

Thank you for helping test whether DecisionGPT's advice matches what really
happens in a business. This guide is written for a **business owner or manager**,
not a software engineer.

You share **one short, anonymous summary per business decision** — a few numbers,
no names, no customer details, no bank details.

---

## 1. What is being checked

When you ask DecisionGPT a question like *"what if I raise the price of this
product by 5%?"*, it gives you a **prediction** — for example "revenue will go
up about ₹55,000 over the next month, with medium risk". We want to know:
**did the real result come close to that prediction?**

Your contribution lets researchers compare DecisionGPT's prediction against the
actual outcome you observed.

## 2. What you need to provide

For **one decision** you actually made:

| # | You tell us |
|---|---|
| 1 | **Business type** — e.g. "clothing retail", "grocery", "electronics wholesale" |
| 2 | **State / region** — e.g. "Maharashtra", "Karnataka" (district optional, coarse) |
| 3 | **When you made the decision** (the date) |
| 4 | **What the decision was** — one of: raise price / lower price / increase marketing / decrease marketing / an inventory decision |
| 5 | **Your goal** — e.g. "increase profit", "increase revenue", "sell more units" |
| 6 | **The strategy DecisionGPT recommended** — e.g. "Price +5%" |
| 7 | **The prediction horizon** — 7, 14, 30, 60 or 90 days |
| 8 | **Revenue before the decision** (a monthly or period figure) |
| 9 | **Predicted revenue** — what DecisionGPT told you to expect |
| 10 | **Actual revenue** — what you actually got over that same horizon |
| 11 | **Predicted risk & predicted confidence** — the two numbers (0–1) DecisionGPT showed |
| 12 | **The date you recorded the actual result** |
| 13 | **Outcome status** — did it work? `achieved` / `partially_achieved` / `not_achieved` / `inconclusive` |

**If you have them:** predicted vs actual **profit**, and predicted vs actual
**units / orders**. These are optional but very useful.

## 3. Why each item is needed

- **Business type, state** — so results can be grouped fairly (a grocer and a
  furniture shop behave differently).
- **Decision date + horizon + result date** — so a 30-day prediction is only
  ever compared with a 30-day actual, never a 90-day one.
- **Before / predicted / actual figures** — this is the actual comparison.
- **Risk & confidence** — to check whether "high confidence" predictions were
  actually more accurate.

## 4. What is NOT required — and NOT wanted

Please **do not** send any of the following. The import tool will reject a
record that contains them:

- Aadhaar number, PAN, GSTIN
- phone number, personal email
- customer names, customer phone numbers, customer IDs
- bank account or card numbers, IFSC codes
- your name or the owner's name
- a street address or pincode that identifies a person
- raw transaction exports, invoices, or customer lists

Aggregate period totals are enough. We never need line-item data.

## 5. How anonymity works

- You choose a short **made-up code** for your business, e.g. `SME-A1`,
  `SHOP-77`. That code is the only identifier stored. It is not linked to your
  name anywhere.
- The record is stored as *"Anonymised Indian SME [SME-A1]"* — business type,
  state and the numbers you provided, nothing else.
- Research outputs report **aggregates only** (e.g. "across 8 decisions, the
  average revenue error was X"). Individual businesses are never named.
- You may decline at any time and ask for your record to be removed.

## 6. How to prepare a decision record

**Option A — spreadsheet (easiest).** Open
`docs/templates/real_indian_sme_outcome_template.csv`. It has one **example row
marked "EXAMPLE / SYNTHETIC"** — delete that row. Add one row per real decision.

**Option B — JSON.** Use
`docs/templates/real_indian_sme_outcome_template.json` the same way.

Fill the columns described in §2. Leave optional columns blank if you don't have
them. Dates are `YYYY-MM-DD` (e.g. `2026-03-15`).

## 7. How to record the actual result

1. Make the decision and note the **decision date**.
2. Note the **prediction** DecisionGPT gave you (revenue, and profit / units if
   shown) and the **risk** and **confidence** numbers.
3. Wait the full horizon (7 / 14 / 30 / 60 / 90 days).
4. Look up the **actual** revenue (and profit / units) for that same period.
5. Record the **result date** and pick an **outcome status**.

The actual result must be measured **after** the decision — never estimated in
advance, never back-filled.

## 8. Recommended outcome horizons

| Horizon | Good for |
|---|---|
| **7 / 14 days** | fast-moving retail, quick promotions |
| **30 days** | most price / marketing decisions (recommended default) |
| **60 / 90 days** | slower categories (furniture, wholesale), structural changes |

Use only these five values, and use the **same** horizon for the prediction and
the actual.

## 9. Example workflow

> A clothing retailer (`SME-A1`, Maharashtra) asks DecisionGPT about raising the
> price of a product line by 5% to improve profit, over 30 days.
> DecisionGPT predicts: revenue ₹9.05 L (from ₹8.50 L), profit ₹1.96 L,
> risk 0.18, confidence 0.62.
> The retailer applies the change on **2026-01-06**.
> On **2026-02-05** they check the books: actual revenue ₹8.72 L, profit ₹1.81 L,
> units 4090 (predicted 4150). They mark the outcome `partially_achieved`.
> One row in the template captures all of this.

## 10. How the data is used in the research

- Predicted vs actual **revenue, profit and units** are compared **separately**
  (MAE / RMSE; percentage error only where it is mathematically valid).
- We report **how many businesses, how many decisions, how many outcomes**, the
  mix of decision types and horizons, and each individual prediction error.
- With only a handful of records the analysis is **descriptive only** — no
  statistical significance is claimed, and several decisions from one business
  are treated as one business, not many.
- A single result **never** proves that a price change *caused* a revenue
  change — the research is careful about that.
- Your records are kept strictly separate from DecisionGPT's synthetic test
  data and from public datasets.

---

*This is a research data-collection guide. Before collecting data from real
businesses at any scale, the project team should obtain appropriate
institutional / legal review (see `docs/templates/real_sme_consent_and_provenance.md`).*
