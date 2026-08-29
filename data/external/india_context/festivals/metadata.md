# India Festival & Holiday Calendar  (`INDIA_PUBLIC_CONTEXT`)

**Status: ACTIVE.** Generated offline from the MIT-licensed `holidays`
library (`holidays==0.103`) — dates come from the library, not hand-entry.

| | |
|---|---|
| Source | `holidays` Python library, India calendar (national + state gazetted holidays) |
| URL | https://github.com/vacanza/holidays |
| Geography | India (national + TN, KL, KA, MH, WB, GJ, DL, UP) |
| Licence | MIT (library); underlying facts are public government notifications |
| Date range | 2019-01-01 .. 2027-12-31 |
| Category | `INDIA_PUBLIC_CONTEXT` — optional exogenous context, never SME-private |

## Files
- `processed/india_festivals.csv` — one row per `(date, festival)`:
  `date, festival, festival_type, is_national_holiday, observed_in`.
- `processed/india_festival_daily.csv` — one row per calendar day:
  `date, is_festival, days_to_next_festival, days_since_last_festival`.

## Build
`python scripts/build_external_datasets.py --only festivals`
(adapter `ml/preprocessing/india_festival_adapter.py`).

## Limitations
- Future lunar-festival dates follow the library's projection — verify against
  the official gazette for far-future planning.
- 8-state sample, not all states.
- **Context only.** Never merge into SME-private data in a way that blurs
  provenance. Not a target; not causal evidence.
