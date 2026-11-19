# India Macroeconomic Context — RBI Policy Repo Rate  (`INDIA_PUBLIC_CONTEXT`)

**Status: ACTIVE for the repo rate.** CPI / WPI / GDP growth are documented as
**PENDING** (same rate-limited data.gov.in / MoSPI API as AGMARKNET) — not
fabricated.

| | |
|---|---|
| Source | Reserve Bank of India — Monetary Policy Committee (MPC) resolutions |
| URL | https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx |
| Geography | India (national monetary policy) |
| Licence | Government of India public information (attribution expected) |
| Date range | 2019-02 .. 2027-12 (monthly, forward-filled) |
| Category | `INDIA_PUBLIC_CONTEXT` — optional macro covariate, never SME-private |

## Method
`RBI_REPO_RATE_CHANGES` in `ml/preprocessing/india_macro_adapter.py` lists
`(effective_date, repo_rate_%)` taken verbatim from each published MPC
resolution. The monthly series is a forward-fill; `repo_rate_change` is the
month-over-month delta.

## File
- `processed/india_macro_context.csv` — `month, repo_rate_pct, repo_rate_change`.

## Build
`python scripts/build_external_datasets.py --only macro`.

## Limitations
- Only the policy repo rate is integrated so far.
- Forward-filled monthly.
- **Observational context only** — not causal evidence, not a forecasting target.
