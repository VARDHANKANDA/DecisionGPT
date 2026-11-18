# Data Directory — DecisionGPT Data Architecture

This directory houses the foundational synthetic starter and platform demo datasets for DecisionGPT.

```
data/
└── platform/                     # Controlled starter & demo datasets
    ├── forecasting/              # Platform forecasting series
    ├── churn/                    # Platform customer churn series
    └── {marketing,pricing,inventory,causal,benchmarks}/
```

## Data Isolation & Architecture Principles

DecisionGPT strictly enforces data isolation and privacy boundaries:

1. **SME-Owned Operational Data (Private)**:
   - Private business records (transactions, inventory, customer events) are **never** committed to version control.
   - SME data resides in the relational database (`backend/app/models/`), strictly scoped by `business_id`.
   - File uploads (CSV/Parquet) are validated via `data_ingestion_service` and transformed into canonical schemas (`backend/app/services/canonical_schema.py`).

2. **Platform Synthetic Datasets (`data/platform/`)**:
   - Deterministic synthetic data generated via `scripts/generate_platform_data.py`.
   - Used to verify system integrity, provide out-of-the-box demo capabilities, and power causal graph simulations when external data has not yet been connected.
   - Includes `.gitkeep` markers for runtime cache directories.

3. **Runtime Upload Boundaries**:
   - User-uploaded CSV files during active sessions are stored in git-ignored locations and isolated per tenant.
