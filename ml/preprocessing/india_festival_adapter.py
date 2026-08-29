"""India festival / holiday calendar -> DecisionGPT context features.

Source : the `holidays` Python library (MIT), a widely-used, maintained
         calendar that derives Indian national + state gazetted holidays
         (Republic Day, Independence Day, Diwali, Holi, Dussehra, Eid,
         Christmas, Pongal, Onam, Ganesh Chaturthi, ...). No dates are
         hand-entered here - they come from the library, and the source +
         version are recorded in the metadata.
Category: INDIA_PUBLIC_CONTEXT. Optional external context feature - never
         mixed with SME-private data and never used to invent a value.

Two deterministic outputs:
  * event table  -> one row per (date, festival), with festival_type and
    whether it is a national holiday, plus which of the sampled states
    observe it.
  * daily table  -> one row per calendar day in [START, END] with
    days_to_next_festival / days_since_last_festival, for joining onto a
    business's dated sales.
"""
from __future__ import annotations

from datetime import date

import pandas as pd

# National calendar + a sample of states covering the big regional festivals
# (Pongal-TN, Onam-KL, Ugadi/Ganesh Chaturthi-KA/MH, Durga Puja-WB, Navratri-GJ).
SAMPLE_SUBDIVS = ["TN", "KL", "KA", "MH", "WB", "GJ", "DL", "UP"]
START = date(2019, 1, 1)
END = date(2027, 12, 31)

_MAJOR = (
    "diwali", "deepavali", "holi", "dussehra", "dasara", "navratri", "pongal",
    "onam", "ugadi", "gudi padwa", "ganesh", "raksha", "janmashtami", "ram navami",
    "durga puja", "chhath", "baisakhi", "vaisakhi", "bihu", "lohri", "makar sankranti",
    "eid", "christmas", "guru nanak",
)
_NATIONAL = ("republic day", "independence day", "gandhi")


def _festival_type(name: str) -> str:
    low = name.lower()
    if any(k in low for k in _NATIONAL):
        return "national_civic"
    if any(k in low for k in ("eid", "ashura", "prophet", "ramadan", "muharram")):
        return "religious_islamic"
    if any(k in low for k in ("christmas", "good friday", "easter")):
        return "religious_christian"
    if "guru nanak" in low or "vaisakhi" in low or "baisakhi" in low:
        return "religious_sikh"
    if any(k in low for k in ("mahavira", "jain")):
        return "religious_jain"
    if any(k in low for k in ("buddha", "buddhist")):
        return "religious_buddhist"
    if any(k in low for k in _MAJOR):
        return "religious_hindu"
    return "other_holiday"


def build_events() -> pd.DataFrame:
    """One row per (date, festival). Deterministic - depends only on the
    `holidays` library version (recorded in metadata)."""
    import holidays

    years = list(range(START.year, END.year + 1))
    national = holidays.India(years=years, language="en_US")

    per_state: dict[str, set[date]] = {}
    for sub in SAMPLE_SUBDIVS:
        try:
            per_state[sub] = set(holidays.India(subdiv=sub, years=years, language="en_US").keys())
        except Exception:  # noqa: BLE001 - subdiv not supported in this lib version
            per_state[sub] = set()

    rows = []
    seen: dict[tuple[date, str], set[str]] = {}
    # national entries
    for d, name in national.items():
        seen.setdefault((d, name), set()).add("IN")
    # state-specific entries
    for sub in SAMPLE_SUBDIVS:
        try:
            sub_cal = holidays.India(subdiv=sub, years=years, language="en_US")
        except Exception:  # noqa: BLE001
            continue
        for d, name in sub_cal.items():
            seen.setdefault((d, name), set()).add(sub)

    for (d, name), states in sorted(seen.items()):
        if not (START <= d <= END):
            continue
        rows.append(
            {
                "date": d.isoformat(),
                "festival": name,
                "festival_type": _festival_type(name),
                "is_national_holiday": "IN" in states or d in national,
                "observed_in": ",".join(sorted(states)),
            }
        )
    return pd.DataFrame(rows).sort_values(["date", "festival"]).reset_index(drop=True)


def build_daily() -> pd.DataFrame:
    """One row per calendar day in [START, END] with distance-to-festival
    features (computed offline, deterministic)."""
    events = build_events()
    fest_dates = pd.to_datetime(sorted(events["date"].unique()))
    days = pd.date_range(START, END, freq="D")

    fest_ts = fest_dates.values.astype("datetime64[D]")
    out = pd.DataFrame({"date": days.strftime("%Y-%m-%d")})
    day_ts = days.values.astype("datetime64[D]")

    next_idx = fest_ts.searchsorted(day_ts, side="left")
    prev_idx = next_idx - 1
    days_to = []
    days_since = []
    for i, d in enumerate(day_ts):
        ni = next_idx[i]
        pi = prev_idx[i]
        days_to.append(int((fest_ts[ni] - d) / pd.Timedelta(days=1)) if ni < len(fest_ts) else -1)
        days_since.append(int((d - fest_ts[pi]) / pd.Timedelta(days=1)) if pi >= 0 else -1)
    out["is_festival"] = out["date"].isin(events["date"]).astype(int)
    out["days_to_next_festival"] = days_to
    out["days_since_last_festival"] = days_since
    return out
