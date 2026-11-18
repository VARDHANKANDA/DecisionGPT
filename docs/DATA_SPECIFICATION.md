# DecisionGPT — Data Specification

## 1. Target

India; retail/e-commerce SMEs; primary demonstration Indian clothing D2C.

## 2. Supported Input

- CSV
- XLSX
- Manual business profile

## 3. Canonical Tables

### businesses
`id, name, industry, business_type, business_size, country, currency, description, created_at, updated_at`

### products
`id, business_id, external_product_id, name, category, unit_cost, selling_price, stock_quantity`

### customers
`id, business_id, external_customer_id, segment, first_purchase_date, last_purchase_date, purchase_frequency, monetary_value, churn_label`

### sales
`id, business_id, customer_id, product_id, sale_date, quantity, unit_price, discount, revenue`

### marketing_campaigns
`id, business_id, campaign_date, channel, spend, impressions, clicks, conversions, attributed_revenue`

### inventory
`id, business_id, product_id, date, stock_level, reorder_level`

## 4. Minimum Evidence

The application must calculate data sufficiency before enabling a model.

Forecasting should generally prefer 6–12 months of regular observations, but the actual threshold depends on frequency and completeness.

Churn requires repeat customer observations.

Digital Twin actions require enough historical evidence to estimate their effects.

If evidence is insufficient, the feature must be disabled or labelled low-evidence.

## 5. Preprocessing

1. Parse.
2. Normalize headers.
3. Infer types.
4. Validate dates.
5. Detect duplicates.
6. Analyse missingness.
7. Detect invalid values.
8. Map columns.
9. Create canonical tables.
10. Save preprocessing metadata.

## 6. Time-Series Rule

Use chronological train/validation/test splits.

Never leak future observations into earlier training data.

## 7. Privacy

Do not require names, email addresses, phone numbers or full addresses.

Use anonymized customer IDs.

## 8. Indian Context

Default:
`country = IN`
`currency = INR`

Tax, GST, festival and regional effects must be configurable data, not hard-coded assumptions.

## 9. Benchmark Schema

`industry, business_size, metric, period, median, lower_quartile, upper_quartile, source, source_url, evidence_level`

Benchmark data must be public, aggregated or licensed.

## 10. Dataset Documentation

For every research dataset record:
- source;
- license;
- date range;
- rows;
- columns;
- preprocessing;
- limitations.
