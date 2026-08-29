# Indian SME Data Architecture

How data flows into DecisionGPT for an **Indian SME**. This is a *layered
strategy on top of the existing architecture* — not a redesign. Every module
named here (Dataset Registry, Training Center, Model Registry, Digital Twin,
Dynamic Causal Graph, Multi-Agent Engine, Business Memory, Research Dashboard)
is the one already implemented.

```
                         INDIAN SME
   ┌───────────────┬────────┴────────┬───────────────┐
   ▼               ▼                 ▼               ▼
 BUSINESS        SALES            CUSTOMER        FINANCE / PRICING
 PROFILE           │                 │               │
   └───────────────┴────────┬────────┴───────────────┘
                            ▼
                     SME BUSINESS DATA  (private, per-business)
                            │
             ┌──────────────┴──────────────┐
             ▼                             ▼
       CAPABILITY DETECTION        INDIAN PUBLIC CONTEXT
   (what features are unlocked)    (festivals, macro, AGMARKNET price)
             │                             │
             └──────────────┬──────────────┘
                            ▼
                       DECISIONGPT
   Prediction models · Dynamic Causal Graph · Digital Twin
                            ▼
                  Multi-Agent Debate → Strategy Optimizer
                            ▼
                     Recommendation → SME ACTION
                            ▼
                       ACTUAL OUTCOME
                    ┌───────┴────────┐
                    ▼                ▼
               Evaluation      Business Memory
                    └───────┬────────┘
                            ▼
                     Future Decisions
```

---

## 1. Three data categories — never silently mixed

| Category | What | Used for | Registry label |
|---|---|---|---|
| **SME-owned operational data** | The SME's own sales / customers / products / inventory / finance / marketing / profile. Private, per `business_id`. | The actual SME recommendations. | *(not in the research registry — it is business data)* |
| **Indian public data** | Government / public datasets: festival calendar, RBI macro, AGMARKNET agri prices, (future) UDYAM / ASUSE / ASI population context. | Context, benchmarking, research validation. **Never** treated as one SME's transaction history. | `INDIA_PUBLIC_CONTEXT`, `INDIA_AGRICULTURAL_PRICE` |
| **Controlled synthetic data** | The bundled `data/platform/**` datasets. | Reproducible architecture / causal / Digital-Twin / multi-agent / ablation evaluation with known ground truth. | `SYNTHETIC_CONTROLLED` |

Every dataset carries provenance metadata. The Research Dashboard shows the
category on every card; the paper reports each result under its category and
never averages across them.

---

## 2. SME-owned operational data — the primary source

Uploaded through the **existing** ingestion pipeline
(`data_ingestion_service`): *Upload → parse → detect sheet → map columns to a
canonical type → validate → data-quality report → confirm → store*. The SME may
use any column names; `canonical_schema.py` + `column_mapping.py` suggest the
mapping and ask for confirmation only when a required field is ambiguous.

### Tier 1 — core (implemented)

| Layer | Canonical type | Required | Key optional fields | Lands in |
|---|---|---|---|---|
| **Business profile** | `business_profile` | *(none — 1 row)* | state, district, city, enterprise_type, organisation_type, major_activity, nic_code, registration_date | `businesses` columns (+ `business_age_years` derived) |
| **Sales** | `sales` | sale_date, quantity, unit_price | customer_id, product_id, discount, revenue | `sales` |
| **Customer** | `customers` | external_customer_id | segment, first/last_purchase_date, purchase_frequency, monetary_value | `customers` |
| **Products** | `products` | external_product_id, name, selling_price | category, unit_cost, stock_quantity | `products` |
| **Finance** | `finance` | period_date | revenue, cogs, gross_profit, operating_expenses, net_profit, cash_balance, accounts_receivable/payable, inventory_value, loan_amount, interest_rate, emi | `finance_records` (migration 0006) |
| **Pricing** | *(derived from `sales`)* | — | uses sale_date, unit_price, discount, quantity, revenue + `products.unit_cost` | — |
| **Decision history / outcomes** | *(existing)* | — | `decisions`, `decision_outcomes`, `prediction_evaluations`, `business_memory` | — |

### Tier 2 — important, optional (implemented as optional uploads / context)

| Layer | Canonical type | Status |
|---|---|---|
| Marketing | `marketing_campaigns` | optional upload (`marketing_campaigns` table) |
| Inventory | `inventory` | optional upload (`inventory` table) |
| Indian festivals | *(public context)* | `data/external/india_context/festivals/` |
| Macro context | *(public context)* | `data/external/india_context/macro/` (RBI repo rate) |

### Tier 3 — future extension points (documented, **no fabricated data**)

Supplier, HR, Competitor, Weather, Customer Reviews / NLP, UPI context,
Geographic enrichment. Canonical shapes are described in
`docs/INDIAN_DATASET_CATALOG.md`. Until a real source and a real use case
exist, DecisionGPT says *"this recommendation cannot use supplier risk because
supplier data has not been provided"* rather than inventing a value.

---

## 3. Capability detection

`capability_service.get_capabilities(db, business_id)` maps *what data the SME
has actually provided* → *which DecisionGPT features are available*, and for the
rest, *exactly what to upload*. Exposed at

```
GET /api/v1/businesses/{business_id}/data/capabilities
```

Example response shape:

```json
{
  "business_id": "…",
  "data_summary": {"sales": 812, "finance_records": 0, "business_profile_set": true, …},
  "capabilities": [
    {"feature": "Demand / sales forecasting", "enabled": true,  "reason": "Available.", "requires": []},
    {"feature": "Marketing optimization",     "enabled": false, "reason": "Upload marketing campaign data (spend + outcomes) to enable.", "requires": ["marketing campaign data (spend + outcomes)"]}
  ]
}
```

This is what the onboarding UI uses to show `✓ Sales analysis` /
`○ Marketing optimization — Upload marketing data to enable`. **Missing data
never produces a fabricated value** — it produces a disabled capability with a
reason.

---

## 4. Data-awareness of the analytical modules

None of these were redesigned — they read `data_summary` / the capability map
and degrade gracefully:

- **Digital Twin** — price / profit scenarios run on `sales` + `products`;
  marketing-mix scenarios only when `marketing_campaigns` exists; inventory
  scenarios only when `inventory` exists. No fabricated business variables.
- **Dynamic Causal Graph** — the `price → quantity → revenue → profit` path is
  data-supported from `sales`; the `marketing_spend → customers → sales` path is
  only added as data-supported when marketing data is present. Evidence levels
  (`ASSUMED` / `OBSERVATIONAL` / `DATA_SUPPORTED` / `CAUSALLY_VALIDATED`) are
  unchanged; nothing is auto-upgraded to `CAUSALLY_VALIDATED`.
- **Multi-Agent Engine** — the Business Analyst / Financial Advisor / Risk
  Manager / Strategy Optimizer receive only the variables the SME's data
  supports. The Risk Manager explicitly names missing evidence
  (e.g. *"Marketing ROI cannot be assessed — campaign spend not provided"*).
- **Business context conditioning** — `businesses.state / industry /
  enterprise_type / business_age_years` condition the recommendation narrative.

---

## 5. Data-layer directory structure

```
data/
├── platform/                     # SYNTHETIC_CONTROLLED (unchanged)
│   ├── forecasting/  churn/  causal/  …
├── external/
│   ├── india_agmarknet/          # INDIA_AGRICULTURAL_PRICE (DATA_PENDING raw pull)
│   ├── india_context/
│   │   ├── festivals/            # INDIA_PUBLIC_CONTEXT (holidays lib)
│   │   └── macro/                # INDIA_PUBLIC_CONTEXT (RBI repo rate)
│   └── _retired_non_indian/      # M5 / UCI / Myanmar — retired, reproducibility only
└── README.md
```

See `docs/INDIAN_DATASET_CATALOG.md` for the full per-dataset catalog and
`docs/FINAL_DATASET_INVENTORY.md` for the status table.
