"""Question interpreter: natural-language question -> validated ``Interpretation`` (OpenAI classification + deterministic extraction).

The model answers a fixed set of *classification fields* (route, operation, metric, statistic, grouping, direction, whether named
products are mentioned, ...) through a strict JSON schema, in ONE request per question. It cannot return dates, product names or
numbers that the application would trust. The work is therefore split:

* **The model decides the categorical parts** of the request: what kind of message this is (calculate / clarify / causal / missing
  data / other tool) and which operation, metric, statistic and grouping applies, each with a self-reported confidence.
* **Deterministic code extracts the values**: periods (dates), product names (matched only against the business's own catalogue),
  limits and weekdays come from the question text by rules, then the closed ``Interpretation`` schema is assembled and strictly
  validated. The model never sees product names or data, only the question text.
* A decision below ``MIN_CONFIDENCE``, a refusal, an error or an invalid assembly makes the caller fall back to the standard
  assistant and says so; nothing here falls back to another provider.
"""
from __future__ import annotations

import calendar
import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from pydantic import ValidationError

from app.schemas.analytics_query import Interpretation
from app.services.openai_client import Choice, DecisionResult, Noul

MAX_QUESTION_CHARS = 1000
MIN_CONFIDENCE = 0.5  # a typed decision below this is not used; the legacy router answers and the reason is recorded

# ------------------------------------------------------------------------------------------------ typed questions (fixed)
QUESTIONS: dict[str, Any] = {
    "route": Choice(
        "What does the business owner's message ask for?",
        {
            "calculate": "a number, ranking, comparison or share that can be calculated from the owner's own recorded SALES (totals, units, orders, products, days, weekdays, periods)",
            "clarify": "too ambiguous to answer, because two reasonable readings would give different answers",
            "causal": "asks WHY something changed, or what caused or drove a change",
            "missing_data": "needs data that is not part of sales records: tax or GST rate, region, payment mode, stock levels, marketing channel, customer discounts",
            "out_of_scope": "is not about the owner's business data at all",
            "other_tool": "asks for a forecast or prediction, customer churn, best customers, whether to change price or marketing, what to focus on, or why a recommendation was made",
        },
    ),
    "operation": Choice(
        "Which kind of calculation does the question ask for?",
        {
            "aggregate": "one number: a total, a count or an average",
            "ranking": "which / top / highest / lowest / best / worst / most / least item, product, day, week, month or weekday",
            "compare_periods": "how one period compares with another, or the percentage change between two periods",
            "share_of_total": "what share or percentage of the total came from named products",
        },
    ),
    "metric": Choice(
        "What is being measured?",
        {
            "revenue": "sales value, sales, amount, income, how much was sold in rupees",
            "units": "units, quantity, pieces, how many were sold",
            "orders": "number of orders, sales records or transactions",
            "distinct_products": "how many different products were sold",
            "customers": "number of customers",
            "profit": "profit or margin",
        },
    ),
    "statistic": Choice(
        "Is a total asked for, or an average?",
        {
            "total": "a total or sum (the default)",
            "mean_per_active_day": "an average on a day that had sales ('on an average day that I had sales')",
            "mean_per_calendar_day": "an average per day over the whole period, counting days without sales",
        },
    ),
    "group_by": Choice(
        "For a ranking: what are the candidates grouped by?",
        {
            "none": "this is not a ranking",
            "product": "individual products",
            "category": "product categories",
            "weekday": "day of the week (Monday..Sunday)",
            "day": "individual calendar days",
            "week": "calendar weeks",
            "month": "calendar months",
        },
    ),
    "direction": Choice(
        "For a ranking: which end is wanted?",
        {"desc": "highest, most, top, best, biggest", "asc": "lowest, least, weakest, worst, smallest, bottom"},
    ),
    "named_products": Noul("Does the question refer to one or more specific, named products (not products in general)?"),
    "include_empty_days": Noul("Does the owner explicitly ask to count days that had no sales at all?"),
    "clarify_about": Choice(
        "If the question were ambiguous, what is unclear?",
        {"period": "which time period", "measure": "what to measure", "product": "which product", "other": "something else"},
    ),
    "missing_item": Choice(
        "If the question needs data that is not in sales records, which kind?",
        {
            "gst_or_tax": "GST or tax rate or amount",
            "region": "region, city or location",
            "payment_mode": "payment method",
            "stock": "stock or inventory levels",
            "marketing_channel": "marketing channel or campaign",
            "discount": "discounts",
            "other": "something else",
        },
    ),
}

MISSING_ITEM_LABEL = {
    "gst_or_tax": "GST or tax information",
    "region": "region or location information",
    "payment_mode": "payment method information",
    "stock": "stock level information",
    "marketing_channel": "marketing channel information",
    "discount": "discount details",
    "other": "that information",
}
# Capability policy. Attributes a question can mention that neither the data model (Sale / Product / Customer) nor the query engine
# supports, so no clarification (which product? which period?) can make the question answerable. A mention is deterministic, matched
# on the question text with this business's own product names masked out (a product called "Discount Pack" is a product, not a
# discount). ``tests/unit/test_capability_policy.py`` asserts these attributes still have no column in the data model: when one is
# added, remove it from this table and teach the engine to use it. Discounts (``Sale.discount``) and stock levels
# (``Product.stock_quantity``) are deliberately absent: the data model has those columns, so this deterministic check must not claim
# they do not exist; the model's own ``missing_data`` route still handles them.
UNAVAILABLE_ATTRIBUTES: dict[str, re.Pattern[str]] = {
    "gst_or_tax": re.compile(r"\b(?:gst|igst|cgst|sgst|vat|hsn|tax|taxes|taxed|taxable|tax[- ](?:inclusive|exclusive|slab|rate)s?)\b", re.I),
    "region": re.compile(r"\b(?:region|regions|regional|city|cities|pin ?code|zip(?: ?code)?|location|locations|geograph\w+)\b", re.I),
    "payment_mode": re.compile(r"\b(?:payment (?:mode|method|type)s?|upi|cash on delivery|cod|credit card|debit card|net ?banking|wallet payments?)\b", re.I),
    "marketing_channel": re.compile(r"\b(?:marketing channels?|sales channels?|campaigns?|ad spend|advertis\w+|social media|instagram|facebook|google ads)\b", re.I),
}


def detect_unavailable_attribute(question: str, catalogue: list[str] | tuple[str, ...] = ()) -> str | None:
    """The key of the first attribute in ``UNAVAILABLE_ATTRIBUTES`` the question refers to, or None. Names from ``catalogue`` are masked
    first so a product whose name contains one of these words is not mistaken for the attribute."""
    text = f" {question} "
    for name in sorted({n for n in catalogue if n and n.strip()}, key=len, reverse=True):
        text = re.sub(rf"(?<!\w){re.escape(name.strip())}(?!\w)", " ", text, flags=re.I)
    for key, pattern in UNAVAILABLE_ATTRIBUTES.items():
        if pattern.search(text):
            return key
    return None


CLARIFY_TEXT = {
    "period": "Which time period do you mean — for example a month, a date range or the last 30 days?",
    "measure": "What would you like to know — sales value, units sold or number of orders?",
    "product": "Which product do you mean?",
    "other": "Could you tell me a little more about what you'd like to know?",
}


@dataclass
class InterpretOutcome:
    interpretation: Interpretation | None = None
    error: str | None = None  # not_configured | timeout | provider_error | malformed_output | invalid_request | low_confidence | ...
    validation_errors: list[str] = field(default_factory=list)
    raw_keys: list[str] = field(default_factory=list)
    call: dict[str, Any] = field(default_factory=dict)
    decisions: dict[str, Any] = field(default_factory=dict)  # what the model decided (labels + confidence) and what code extracted


_CTRL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")


def clean_question(question: str) -> str:
    return _CTRL.sub(" ", question).strip()


# ------------------------------------------------------------------------------------------------ deterministic extraction
_MONTHS = {
    "january": 1, "jan": 1, "february": 2, "feb": 2, "march": 3, "mar": 3, "april": 4, "apr": 4, "may": 5, "june": 6, "jun": 6,
    "july": 7, "jul": 7, "august": 8, "aug": 8, "september": 9, "sept": 9, "sep": 9, "october": 10, "oct": 10,
    "november": 11, "nov": 11, "december": 12, "dec": 12,
}
_M = r"(?:january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|jun|jul|aug|sept|sep|oct|nov|dec)"
_SEP = r"(?:to|until|through|thru|and|-|–|—)"
_NUMWORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
             "eleven": 11, "twelve": 12, "fifteen": 15, "twenty": 20, "thirty": 30}
_NUM = r"(?:\d{1,4}|" + "|".join(_NUMWORDS) + r")"
_WEEKDAYS = {"monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3, "friday": 4, "saturday": 5, "sunday": 6}
_STOP = set("""a an the of for in on at to from by with and or is are was were be been do did does have has had my our your i me we you it its
this that these those what which who whom how much many more most less least top bottom best worst highest lowest total totals sales sale sold sell
selling units unit quantity quantities number product products item items day days week weeks month months year years period between during
compare compared comparison change changed percentage percent share revenue amount average per each any all every different distinct than then
last first previous past recent current overall ever show tell give list rank name day""".split())


def _int(x: str | None) -> int | None:
    if x is None:
        return None
    x = x.lower()
    return _NUMWORDS.get(x) if x in _NUMWORDS else int(x)


def _month_ok(word: str, followed_by_year: bool, before: str) -> bool:
    """'may' (and 'mar', 'sep' ...) are only a month when the context says so."""
    if word.lower() != "may":
        return True
    if followed_by_year:
        return True
    return bool(re.search(r"(?:\bin|\bof|\bduring|\bfor|\bfrom|\bto|\band|\bsince|\bthrough|\bbetween|\bwith|\bthan|\bagainst|\bvs\.?)\s*$", before.lower()))


@dataclass
class _Mention:
    start: int
    end: int
    spec: dict
    kind: str = ""  # "month" | "range" | "day" | "quarter" | "year" | "relative" | "trailing" | "all_time"
    year_given: bool = True


def _abs(y: int, m: int, d: int, y2: int | None = None, m2: int | None = None, d2: int | None = None) -> dict | None:
    try:
        s = date(y, m, d)
        e = date(y2 if y2 is not None else y, m2 if m2 is not None else m, d2 if d2 is not None else d)
    except ValueError:
        return None
    if s > e:
        return None
    return {"kind": "absolute", "start": s.isoformat(), "end": e.isoformat()}


def extract_periods(question: str) -> list[_Mention]:
    """Every period the question mentions, in order of appearance, as DateSpec dicts (no reference date needed: relative periods stay
    relative and are resolved later by the query engine against the clock)."""
    text = question
    low = text.lower()
    mask = list(low)  # consumed characters are blanked so a later, weaker pattern cannot re-read them
    out: list[_Mention] = []

    def take(m: re.Match, spec: dict | None, kind: str, year_given: bool = True) -> None:
        if spec is None:  # a date-shaped phrase that is not a real date (31 February, 15 to 1 March): never reinterpret it
            spec = {"_invalid": True}
        out.append(_Mention(m.start(), m.end(), spec, kind, year_given))
        for i in range(m.start(), m.end()):
            mask[i] = " "

    def cur() -> str:
        return "".join(mask)

    # ISO date
    for m in re.finditer(r"\b(\d{4})-(\d{2})-(\d{2})\b", cur()):
        take(m, _abs(int(m[1]), int(m[2]), int(m[3])), "day")
    # 14/02/2025 (day first)
    for m in re.finditer(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b", cur()):
        take(m, _abs(int(m[3]), int(m[2]), int(m[1])), "day")
    # 1 to 15 March 2025
    for m in re.finditer(rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s*{_SEP}\s*(\d{{1,2}})(?:st|nd|rd|th)?\s+({_M})(?:\s*,?\s*(\d{{4}}))?\b", cur()):
        mon = _MONTHS[m[3]]
        y = int(m[4]) if m[4] else None
        take(m, _abs(y, mon, int(m[1]), None, None, int(m[2])) if y else {"_day_range": (int(m[1]), int(m[2]), mon)}, "range", y is not None)
    # January to March 2025 / January 2025 to March 2025
    for m in re.finditer(rf"\b({_M})(?:\s*,?\s*(\d{{4}}))?\s*{_SEP}\s*({_M})(?:\s*,?\s*(\d{{4}}))?\b", cur()):
        m1, m2 = _MONTHS[m[1]], _MONTHS[m[3]]
        if m1 == 5 and not _month_ok(m[1], bool(m[2]), cur()[: m.start()]):
            continue
        y1, y2 = (int(m[2]) if m[2] else None), (int(m[4]) if m[4] else None)
        if y1 is None and y2 is not None:
            y1 = y2 if m1 <= m2 else y2 - 1
        if y2 is None and y1 is not None:
            y2 = y1 if m1 <= m2 else y1 + 1
        if y1 is None or y2 is None:
            take(m, {"_month_range": (m1, m2)}, "range", False)
        else:
            last = calendar.monthrange(y2, m2)[1]
            take(m, _abs(y1, m1, 1, y2, m2, last), "range")
    # 14 February 2025 / February 14, 2025
    for m in re.finditer(rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+({_M})\b(?:\s*,?\s*(\d{{4}}))?", cur()):
        y = int(m[3]) if m[3] else None
        take(m, _abs(y, _MONTHS[m[2]], int(m[1])) if y else {"_day": (int(m[1]), _MONTHS[m[2]])}, "day", y is not None)
    for m in re.finditer(rf"\b({_M})\s+(\d{{1,2}})(?:st|nd|rd|th)?\b(?:\s*,?\s*(\d{{4}}))?", cur()):
        y = int(m[3]) if m[3] else None
        take(m, _abs(y, _MONTHS[m[1]], int(m[2])) if y else {"_day": (int(m[2]), _MONTHS[m[1]])}, "day", y is not None)
    # quarters
    for m in re.finditer(r"\bq([1-4])\b(?:\s*,?\s*(?:of\s+)?(\d{4}))?", cur()):
        take(m, {"kind": "calendar", "unit": "quarter", **({"year": int(m[2])} if m[2] else {}), "quarter": int(m[1])}, "quarter", bool(m[2]))
    for m in re.finditer(r"\b(first|second|third|fourth)\s+quarter\b(?:\s+(?:of\s+)?(\d{4}))?", cur()):
        q = {"first": 1, "second": 2, "third": 3, "fourth": 4}[m[1]]
        take(m, {"kind": "calendar", "unit": "quarter", **({"year": int(m[2])} if m[2] else {}), "quarter": q}, "quarter", bool(m[2]))
    # trailing: last 30 days / past 2 weeks / previous 3 months
    for m in re.finditer(rf"\b(?:last|past|previous|recent|latest)\s+({_NUM})\s+(day|week|month)s?\b", cur()):
        n = _int(m[1])
        if n and 1 <= n <= 3650:
            take(m, {"kind": "trailing", "count": n, "unit": m[2]}, "trailing")
    # relative calendar units
    for m in re.finditer(r"\b(this|current|last|previous|prior)\s+(month|week|quarter|year)\b", cur()):
        off = 0 if m[1] in ("this", "current") else -1
        take(m, {"kind": "calendar", "unit": m[2], "offset": off}, "relative", False)
    for m in re.finditer(r"\b(yesterday|today)\b", cur()):
        take(m, {"kind": "calendar", "unit": "day", "offset": -1 if m[1] == "yesterday" else 0}, "relative", False)
    # month (with optional year)
    for m in re.finditer(rf"\b({_M})\b(?:\s*,?\s*(\d{{4}}))?", cur()):
        if not _month_ok(m[1], bool(m[2]), cur()[: m.start()]):
            continue
        mon = _MONTHS[m[1]]
        if m[2]:
            take(m, {"kind": "calendar", "unit": "month", "year": int(m[2]), "month": mon}, "month")
        else:
            take(m, {"kind": "calendar", "unit": "month", "month": mon}, "month", False)
    # a bare year
    for m in re.finditer(r"\b(19\d{2}|20\d{2})\b", cur()):
        take(m, {"kind": "calendar", "unit": "year", "year": int(m[1])}, "year")
    # all time
    for m in re.finditer(r"\b(?:all[- ]time|since i started|since the beginning|ever|overall|in total over time)\b", cur()):
        take(m, {"kind": "all_time"}, "all_time", False)

    out.sort(key=lambda x: x.start)
    # inherit a missing year from the nearest explicit year in the question
    explicit = [(x.start, x.spec) for x in out if x.spec.get("year") is not None or str(x.spec.get("start", ""))[:4].isdigit()]
    years = []
    for _pos, sp in explicit:
        y = sp.get("year") if sp.get("year") is not None else int(str(sp["start"])[:4])
        years.append((_pos, y))
    for x in out:
        sp = x.spec
        year = None
        if years:
            year = min(years, key=lambda t: (abs(t[0] - x.start), t[0]))[1]
        if "_day_range" in sp and year:
            a, b, mon = sp["_day_range"]
            x.spec = _abs(year, mon, a, None, None, b) or sp
        elif "_month_range" in sp and year:
            m1, m2 = sp["_month_range"]
            x.spec = _abs(year, m1, 1, year if m1 <= m2 else year + 1, m2, calendar.monthrange(year if m1 <= m2 else year + 1, m2)[1]) or sp
        elif "_day" in sp and year:
            d, mon = sp["_day"]
            x.spec = _abs(year, mon, d) or sp
        elif sp.get("kind") == "calendar" and sp.get("unit") in ("month", "quarter") and sp.get("year") is None and sp.get("offset") is None and year:
            x.spec = {**sp, "year": year}
    return [x for x in out if not any(k.startswith("_") and k != "_invalid" for k in x.spec)]


_BASELINE_CUE = re.compile(r"(?:compared?\s+(?:with|to|against)|comparison\s+(?:with|to)|versus|vs\.?|than|relative\s+to)\s*$")


def _previous(spec: dict) -> dict | None:
    """The period immediately before ``spec`` where that is well defined (a calendar month / quarter / year or a relative unit)."""
    if spec.get("kind") != "calendar":
        return None
    unit = spec["unit"]
    if spec.get("offset") is not None:
        return {**spec, "offset": spec["offset"] - 1}
    if unit == "month" and spec.get("month"):
        y, m = spec.get("year"), spec["month"]
        if y is None:
            return {"kind": "calendar", "unit": "month", "month": 12 if m == 1 else m - 1}
        return {"kind": "calendar", "unit": "month", "year": y - 1 if m == 1 else y, "month": 12 if m == 1 else m - 1}
    if unit == "quarter" and spec.get("quarter") and spec.get("year") is not None:
        q, y = spec["quarter"], spec["year"]
        return {"kind": "calendar", "unit": "quarter", "year": y - 1 if q == 1 else y, "quarter": 4 if q == 1 else q - 1}
    if unit == "year" and spec.get("year") is not None:
        return {"kind": "calendar", "unit": "year", "year": spec["year"] - 1}
    return None


def extract_weekdays(question: str) -> list[int]:
    return sorted({n for w, n in _WEEKDAYS.items() if re.search(rf"\b{w}s?\b", question.lower())})


def extract_limit(question: str) -> int | None:
    low = question.lower()
    m = re.search(rf"\b(?:top|bottom|best|worst|first|highest|lowest)\s+({_NUM})\b", low)
    if m:
        return _int(m[1])
    m = re.search(rf"\b({_NUM})\s+(?:best[- ]selling\s+|top\s+|most\s+|least\s+|highest\s+|lowest\s+)?(?:products?|items?|days?|weeks?|months?|categories|weekdays)\b", low)
    if m and not re.search(rf"\b{re.escape(m[1])}\s+months?\s+(?:from|between|of|ending)\b", low):
        return _int(m[1])
    return None


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.casefold()).strip()


def extract_products(question: str, catalogue: list[str], fuzzy: bool = True) -> list[str]:
    """Names of this business's own products that the question mentions. Whole-name matches first (longest first); with ``fuzzy``,
    otherwise single distinctive words that are part of a product name, which the engine resolves or reports as ambiguous."""
    nq = f" {_norm(question)} "
    found: list[tuple[int, str]] = []
    taken = nq
    for name in sorted({n for n in catalogue if n and _norm(n) and _norm(n) not in _STOP}, key=lambda n: -len(_norm(n))):
        pat = f" {_norm(name)} "
        pos = taken.find(pat)
        if pos >= 0:
            found.append((pos, name))
            taken = taken[:pos] + " " * len(pat) + taken[pos + len(pat):]
    if found or not fuzzy:
        return [n for _p, n in sorted(found)]
    vocab: set[str] = set()
    for n in catalogue:
        vocab.update(_norm(n).split())
    words = [w for w in _norm(question).split() if len(w) >= 3 and w not in _STOP and w not in _MONTHS and w not in _WEEKDAYS and not w.isdigit() and w.rstrip("s") not in _STOP]
    hits = []
    for w in words:
        if w in vocab:
            hits.append(w)
        elif w.endswith("s") and w[:-1] in vocab:
            hits.append(w[:-1])
    seen: list[str] = []
    for h in hits:
        if h not in seen:
            seen.append(h)
    return seen[:5]


# ------------------------------------------------------------------------------------------------ assembling the request
def _decisions_record(res: DecisionResult) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, a in res.answers.items():
        out[k] = {"value": round(a.value, 3) if isinstance(a.value, float) else a.value, "confidence": None if a.confidence is None else round(a.confidence, 3)}
    return out


def _build(res: DecisionResult, question: str, catalogue: list[str]) -> tuple[dict | None, dict[str, Any]]:
    """(Interpretation as a dict, extracted-hints record). Raises ValueError('low_confidence') when a used decision is not confident."""
    d = {k: a for k, a in res.answers.items()}

    def val(k: str, need_conf: bool = True) -> str:
        a = d[k]
        if need_conf and (a.confidence or 0.0) < MIN_CONFIDENCE:
            raise ValueError("low_confidence")
        return str(a.value)

    route = val("route")
    hints: dict[str, Any] = {"route": route}
    if route in ("calculate", "clarify"):
        # A question that depends on data this business model does not hold can never be answered by calculating or by clarifying a
        # product / period, so say what is missing instead of asking something that cannot help (and never estimate it).
        missing = detect_unavailable_attribute(question, catalogue)
        if missing:
            hints["capability_check"] = {"unavailable_attribute": missing, "model_route": route}
            return {"route": "unsupported", "unsupported_reason": "missing_field", "unsupported_item": MISSING_ITEM_LABEL[missing]}, hints
    if route == "other_tool":
        return {"route": "legacy"}, hints
    if route == "clarify":
        about = d["clarify_about"].value if d["clarify_about"].value in CLARIFY_TEXT else "other"
        return {"route": "clarification", "clarification_question": CLARIFY_TEXT[about]}, hints
    if route == "causal":
        return {"route": "unsupported", "unsupported_reason": "causal_attribution"}, hints
    if route == "out_of_scope":
        return {"route": "unsupported", "unsupported_reason": "out_of_scope"}, hints
    if route == "missing_data":
        item = MISSING_ITEM_LABEL.get(str(d["missing_item"].value), MISSING_ITEM_LABEL["other"])
        return {"route": "unsupported", "unsupported_reason": "missing_field", "unsupported_item": item}, hints

    operation, metric = val("operation"), val("metric")
    statistic = val("statistic") if operation == "aggregate" else "total"
    group_by = val("group_by") if operation == "ranking" else "none"
    direction = val("direction") if operation == "ranking" else "desc"
    named = (d["named_products"].value or 0.0) >= 0.5
    include_empty = (d["include_empty_days"].value or 0.0) >= 0.5
    periods = extract_periods(question)
    hints.update(operation=operation, metric=metric, periods=[p.spec for p in periods])
    if any("_invalid" in p.spec for p in periods):  # never guess a period from a date that does not exist
        return {"route": "clarification", "clarification_question": CLARIFY_TEXT["period"]}, hints

    q: dict[str, Any] = {"operation": operation, "metric": metric}
    if operation == "compare_periods":
        cue = [i for i, p in enumerate(periods) if _BASELINE_CUE.search(question.lower()[max(0, p.start - 25): p.start])]
        if len(periods) >= 2:
            if cue and cue[0] != 0:
                subj, base = 0, cue[0]
            elif cue:  # "compared with February, how did March do?" - the first mention is the baseline
                subj, base = 1, 0
            else:
                subj, base = 0, 1
            q["period"], q["comparison_period"] = periods[subj].spec, periods[base].spec
        elif len(periods) == 1 and _previous(periods[0].spec):
            q["period"], q["comparison_period"] = periods[0].spec, _previous(periods[0].spec)
        else:
            return {"route": "clarification", "clarification_question": CLARIFY_TEXT["period"]}, hints
    else:
        q["period"] = periods[0].spec if periods else {"kind": "all_time"}
    if operation == "aggregate":
        q["statistic"] = statistic
    if operation == "ranking":
        if group_by == "none":
            raise ValueError("invalid_request")
        q["group_by"] = group_by
        q["direction"] = direction
        limit = extract_limit(question)
        if limit is not None:
            q["limit"] = max(1, min(limit, 50))
        q["only_days_with_sales"] = not include_empty
    # an exact whole-name match is always honoured (a named product must never be silently dropped); looser word matching
    # is used only when the model says the question is about specific named products
    prods = extract_products(question, catalogue, fuzzy=named)
    if prods:
        hints["products"] = prods
        q["products"] = prods
        if operation == "ranking" and group_by == "product" and "limit" not in q and len(prods) > 1:
            q["limit"] = min(len(prods), 50)  # "which sold more, A or B?": show every product named, the winner first
    elif named or operation == "share_of_total":
        return {"route": "clarification", "clarification_question": CLARIFY_TEXT["product"]}, hints
    wd = extract_weekdays(question)
    if wd and not (operation == "ranking" and group_by == "weekday"):
        q["weekdays"] = wd
    return {"route": "analytics_query", "query": q}, hints


def interpret(llm: Any, question: str, reference: date, coverage: tuple[date, date] | None, optional_fields: dict[str, bool],
              products: list[str] | None = None) -> InterpretOutcome:
    """Run the typed interpreter and validate the assembled request. Never raises. ``reference``/``coverage``/``optional_fields`` are
    kept for call compatibility: dates are resolved later by the query engine, and none of them is sent to the model. Only the question
    text leaves the server."""
    res = llm.decide(question, QUESTIONS)
    out = InterpretOutcome(
        call={
            "latency_s": round(getattr(res, "latency_s", 0.0) or 0.0, 3),
            "provider": getattr(res, "provider", None),
            "model": getattr(res, "model", None),
            "response_model": getattr(res, "response_model", None),
            "usage": getattr(res, "usage", None),
            "attempts": getattr(res, "attempts", None),
            "error": getattr(res, "error", None),
        }
    )
    if not res.ok:
        out.error = res.error or "provider_error"
        return out
    out.raw_keys = sorted(res.answers.keys())
    out.decisions = {"ai": _decisions_record(res)}
    try:
        data, hints = _build(res, question, list(products or []))
        out.decisions["extracted"] = hints
    except ValueError as exc:
        out.error = str(exc) or "invalid_request"
        return out
    try:
        out.interpretation = Interpretation.model_validate(data)
    except ValidationError as exc:
        out.error = "invalid_request"
        out.validation_errors = [f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()][:8]
    return out
