"""India macroeconomic context -> DecisionGPT context features.

Category: INDIA_PUBLIC_CONTEXT. Optional external context - never mixed with
SME-private data, never used to invent a value.

Currently integrated (small, high-signal, verifiable):
  * RBI policy repo rate - the headline lending-rate anchor. Change points
    are taken verbatim from the Reserve Bank of India's published Monetary
    Policy Committee (MPC) resolutions
    (https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx). Each entry
    is (effective_date, repo_rate_pct); the monthly series is a forward-fill.

Pending (documented, not fabricated): CPI / WPI inflation and GDP growth are
available from MoSPI / data.gov.in but, like the AGMARKNET pull, are behind a
rate-limited public API. See docs/INDIAN_DATASET_CATALOG.md.
"""
from __future__ import annotations

from datetime import date

import pandas as pd

# (effective_date, repo_rate_%) - RBI MPC resolutions. Source recorded above
# and in data/external/india_context/macro/metadata.md.
RBI_REPO_RATE_CHANGES: list[tuple[str, float]] = [
    ("2019-02-07", 6.25),
    ("2019-04-04", 6.00),
    ("2019-06-06", 5.75),
    ("2019-08-07", 5.40),
    ("2019-10-04", 5.15),
    ("2020-03-27", 4.40),
    ("2020-05-22", 4.00),
    ("2022-05-04", 4.40),
    ("2022-06-08", 4.90),
    ("2022-08-05", 5.40),
    ("2022-09-30", 5.90),
    ("2022-12-07", 6.25),
    ("2023-02-08", 6.50),
    ("2024-06-07", 6.50),
    ("2025-02-07", 6.25),
    ("2025-04-09", 6.00),
    ("2025-06-06", 5.50),
]

START = date(2019, 1, 1)
END = date(2027, 12, 31)


def build_repo_rate_monthly(as_of: date | None = None) -> pd.DataFrame:
    """Monthly ``month, repo_rate_pct`` series, forward-filled from the
    published change points. Deterministic."""
    end = pd.Timestamp(as_of or END).to_period("M").to_timestamp("M")
    months = pd.period_range(START, end, freq="M").to_timestamp()

    changes = pd.DataFrame(RBI_REPO_RATE_CHANGES, columns=["effective_date", "repo_rate_pct"])
    changes["effective_date"] = pd.to_datetime(changes["effective_date"])
    changes = changes.sort_values("effective_date")

    rates = []
    for m in months:
        applicable = changes[changes["effective_date"] <= m + pd.offsets.MonthEnd(0)]
        rates.append(float(applicable["repo_rate_pct"].iloc[-1]) if len(applicable) else None)

    out = pd.DataFrame({"month": months.strftime("%Y-%m-%d"), "repo_rate_pct": rates})
    out = out.dropna(subset=["repo_rate_pct"]).reset_index(drop=True)
    out["repo_rate_change"] = out["repo_rate_pct"].diff().fillna(0.0).round(2)
    return out


def build_context() -> pd.DataFrame:
    """The single committed macro-context table (currently just repo rate;
    extend here as more series are legitimately sourced)."""
    return build_repo_rate_monthly()
