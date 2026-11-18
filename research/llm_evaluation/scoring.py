"""Deterministic scoring of free-text answers against ground truth. No LLM judge.

All rules are the ones written into tasks/tasks_v1.json ("scoring" and each task's "tolerance") BEFORE
any model ran. Do not tune this module after seeing results; if a scoring bug is found, record it as a
deviation and re-score ALL runs with the corrected code (never selectively).
"""
from __future__ import annotations

import calendar
import re
from datetime import date

SCORER_VERSION = "score-1.0"

OUTCOMES = (
    "correct",
    "numerically_incorrect",
    "correct_number_wrong_interpretation",
    "partially_correct",
    "unsupported_claim",  # never assigned automatically (needs human audit) — kept for the report taxonomy
    "unable_to_answer",
    "tool_data_access_failure",
    "other",
)

MONTHS = {m.lower(): i for i, m in enumerate(calendar.month_name) if m}
MONTHS.update({m.lower(): i for i, m in enumerate(calendar.month_abbr) if m})
_MON = "|".join(sorted(MONTHS, key=len, reverse=True))

_DATE_PATTERNS = [
    re.compile(r"\b(?P<y>20\d\d)-(?P<m>\d{1,2})-(?P<d>\d{1,2})\b"),
    re.compile(r"\b(?P<d>\d{1,2})[/\-.](?P<m>\d{1,2})[/\-.](?P<y>20\d\d)\b"),
    re.compile(rf"\b(?P<d>\d{{1,2}})(?:st|nd|rd|th)?\s*(?:of\s+)?(?P<mn>{_MON})\.?,?\s*(?P<y>20\d\d)?\b", re.I),
    re.compile(rf"\b(?P<mn>{_MON})\.?\s+(?P<d>\d{{1,2}})(?:st|nd|rd|th)?(?:,?\s*(?P<y>20\d\d))?\b", re.I),
]
_DATE_STRIP = [
    re.compile(r"\b20\d\d-\d{1,2}-\d{1,2}\b"),
    re.compile(r"\b\d{1,2}[/\-.]\d{1,2}[/\-.]20\d\d\b"),
    re.compile(rf"\b\d{{1,2}}(?:st|nd|rd|th)?\s*(?:-|–|to)\s*\d{{1,2}}(?:st|nd|rd|th)?\s*(?:of\s+)?(?:{_MON})\b(?:\.?,?\s*20\d\d)?", re.I),
    re.compile(rf"\b\d{{1,2}}(?:st|nd|rd|th)?\s*(?:of\s+)?(?:{_MON})\b(?:\.?,?\s*20\d\d)?", re.I),
    re.compile(rf"\b(?:{_MON})\b\.?,?\s*20\d\d\b", re.I),
    re.compile(rf"\b(?:{_MON})\b\.?\s*\d{{1,2}}(?!\d)(?:st|nd|rd|th)?(?:,?\s*20\d\d)?", re.I),
    re.compile(r"\b20\d\d\b"),
]

_NUM = re.compile(
    r"(?<![\w.,])(?P<neg>[-−])?\s?(?:₹|rs\.?|inr)?\s?(?P<num>\d{1,3}(?:,\d{2,3})+(?:\.\d+)?|\d+(?:\.\d+)?)(?:\s?(?P<mult>lakhs?|lacs?|crores?|cr\b|thousand|million|k\b|m\b|%))?",
    re.I,
)
_MULT = {"lakh": 1e5, "lakhs": 1e5, "lac": 1e5, "lacs": 1e5, "crore": 1e7, "crores": 1e7, "cr": 1e7,
         "thousand": 1e3, "million": 1e6, "k": 1e3, "m": 1e6}

_REFUSAL = re.compile(
    r"(i don'?t have enough|not enough (?:data|information|evidence)|insufficient (?:data|evidence)|unable to|cannot (?:answer|determine|find|calculate|compute)|"
    r"can'?t (?:answer|determine|find|calculate|compute)|i'?m sorry|i am sorry|no data (?:available|found)|could not (?:find|determine|calculate)|"
    r"try asking|not able to (?:answer|determine))",
    re.I,
)
_UP = re.compile(r"\b(up|higher|increase[ds]?|grew|grow(?:th|n)?|rose|rise[ns]?|more than|improv\w+|gain\w*|positive)\b", re.I)
_DOWN = re.compile(r"\b(down|lower|decrease[ds]?|fell|fall(?:s|en)?|drop(?:ped|s)?|declin\w+|less than|dip(?:ped)?|reduc\w+|negative|slump\w*)\b", re.I)


def normalize(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def strip_dates(text: str) -> str:
    out = text
    for p in _DATE_STRIP:
        out = p.sub(" ", out)
    return out


def extract_numbers(text: str, *, drop_dates: bool = True) -> list[float]:
    """Numbers in order of appearance, with lakh/crore/K/M multipliers applied. Dates/years are removed first."""
    t = strip_dates(text) if drop_dates else text
    out: list[float] = []
    for m in _NUM.finditer(t):
        raw = m.group("num").replace(",", "")
        try:
            v = float(raw)
        except ValueError:
            continue
        mult = (m.group("mult") or "").lower()
        if mult in _MULT:
            v *= _MULT[mult]
        if m.group("neg"):
            v = -v
        out.append(v)
    return out


def extract_dates(text: str) -> list[date]:
    found: list[tuple[int, date]] = []
    for pat in _DATE_PATTERNS:
        for m in pat.finditer(text):
            g = m.groupdict()
            try:
                d = int(g["d"])
                mo = int(g["m"]) if g.get("m") else MONTHS[g["mn"].lower().rstrip(".")]
                y = int(g["y"]) if g.get("y") else 2025  # all data is in 2025
                found.append((m.start(), date(y, mo, d)))
            except (ValueError, KeyError):
                continue
    found.sort(key=lambda x: x[0])
    seen, ordered = set(), []
    for _, d in found:
        if d not in seen:
            seen.add(d)
            ordered.append(d)
    return ordered


def find_entities(text: str, candidates: list[str]) -> list[str]:
    """Candidate entities in order of first mention (whole-word, normalised, longest match wins)."""
    hay = " " + normalize(text) + " "
    hits: list[tuple[int, int, str]] = []
    for c in candidates:
        n = normalize(c)
        if not n:
            continue
        needle = " " + n + " "
        i = hay.find(needle)
        if i >= 0:
            hits.append((i, -len(n), c))
    hits.sort()
    out, taken_spans = [], []
    for pos, neg_len, c in hits:
        span = (pos, pos - neg_len)
        if any(span[0] < e and s < span[1] for s, e in taken_spans):  # overlaps a longer/earlier match
            continue
        taken_spans.append(span)
        out.append(c)
    return out


def is_refusal(text: str) -> bool:
    return bool(_REFUSAL.search(text or ""))


def direction(text: str) -> str | None:
    up, down = bool(_UP.search(text)), bool(_DOWN.search(text))
    nums = extract_numbers(text, drop_dates=True)
    if any(n < 0 for n in nums) and not up:
        return "down"
    if up and not down:
        return "up"
    if down and not up:
        return "down"
    return None


def _within(value: float, truth: float, tol: dict) -> bool:
    t = tol["type"]
    if t == "absolute":
        return abs(value - truth) < 0.5 + tol.get("value", 0)
    if t == "relative":
        return abs(value - truth) <= max(tol["value"] * abs(truth), tol.get("min_abs", 0.0))
    if t == "absolute_pp":
        return abs(abs(value) - abs(truth)) <= tol["value"]
    raise ValueError(f"unknown numeric tolerance {t}")


def _result(task: dict, outcome: str, correct: bool, **extra) -> dict:
    assert outcome in OUTCOMES
    return {"task_id": task["task_id"], "outcome": outcome, "correct": correct, "scorer_version": SCORER_VERSION, **extra}


def score_answer(task: dict, truth, answer: str | None, *, system_error: str | None = None, view_products: list[str] | None = None) -> dict:
    """Score one answer. `truth` is the ground-truth 'answer' value for the task."""
    if system_error:
        return _result(task, "tool_data_access_failure", False, detail=system_error[:300])
    text = (answer or "").strip()
    if not text:
        return _result(task, "other", False, detail="empty answer", invalid_answer=True)

    atype = task["expected_answer_type"]
    tol = task["tolerance"]

    if atype in ("currency", "exact_number", "number", "percentage"):
        nums = extract_numbers(text)
        refusal = is_refusal(text)
        if not nums:
            return _result(task, "unable_to_answer" if refusal else "other", False,
                           detail="refusal" if refusal else "no number found", invalid_answer=not refusal, n_numbers=0)
        truth_f = float(truth)
        hit = [n for n in nums if _within(n, truth_f, tol)]
        nearest = min(nums, key=lambda n: abs(abs(n) - abs(truth_f)) if atype == "percentage" else abs(n - truth_f))
        base = {
            "n_numbers": len(nums),
            "first_number": nums[0],
            "first_number_correct": _within(nums[0], truth_f, tol),
            "nearest_number": nearest,
            "abs_error_first": abs(nums[0] - truth_f),
            "abs_error_nearest": abs(nearest - truth_f) if atype != "percentage" else abs(abs(nearest) - abs(truth_f)),
            "rel_error_first": (abs(nums[0] - truth_f) / abs(truth_f)) if truth_f else None,
            "rel_error_nearest": ((abs(nearest - truth_f) / abs(truth_f)) if truth_f else None) if atype != "percentage" else None,
        }
        if not hit:
            if refusal:
                return _result(task, "unable_to_answer", False, **base)
            return _result(task, "numerically_incorrect", False, **base)
        if task.get("signed_change"):
            want = "up" if truth_f > 0 else "down"
            got = direction(text)
            if got is None:
                return _result(task, "partially_correct", False, detail="magnitude right, direction not stated", **base)
            if got != want:
                return _result(task, "correct_number_wrong_interpretation", False, detail=f"direction {got}, truth {want}", **base)
        return _result(task, "correct", True, **base)

    if atype in ("categorical", "comparison", "date", "ranking"):
        k = task.get("ranking_k") or 1
        if atype == "date":
            found = extract_dates(text)
            truth_d = date.fromisoformat(str(truth))
            first_ok = bool(found) and found[0] == truth_d
            mention = truth_d in found
            base = {"entities_found": [d.isoformat() for d in found], "truth_mentioned": mention}
            if first_ok:
                return _result(task, "correct", True, **base)
            if not found:
                refusal = is_refusal(text)
                return _result(task, "unable_to_answer" if refusal else "other", False, detail="no date found", invalid_answer=not refusal, **base)
            return _result(task, "partially_correct" if mention else "numerically_incorrect", False, detail="first date is not the truth date", **base)

        if atype == "ranking":
            truth_list = list(truth)
            cands = view_products or truth_list
            found = find_entities(text, cands)
            pred = found[:k]
            base = {"entities_found": found[:8], "truth_mentioned": all(t in found for t in truth_list),
                    "top1_correct": bool(pred) and pred[0] == truth_list[0],
                    "overlap_at_k": len(set(pred) & set(truth_list)) / k}
            if pred == truth_list:
                return _result(task, "correct", True, **base)
            if not found:
                refusal = is_refusal(text)
                return _result(task, "unable_to_answer" if refusal else "other", False, detail="no product named", invalid_answer=not refusal, **base)
            return _result(task, "partially_correct" if base["overlap_at_k"] > 0 else "numerically_incorrect", False,
                           detail="wrong order or wrong set", **base)

        # categorical / comparison with a single expected entity
        cands = task.get("candidate_entities") or (view_products or [])
        found = find_entities(text, cands)
        if atype == "categorical" and task["task_id"].startswith("E"):  # GST slabs: match "18%" tokens
            nums = [f"{int(n)}%" for n in extract_numbers(text, drop_dates=True) if float(n).is_integer()]
            found = [n for n in nums if n in cands] or found
        truth_s = str(truth)
        base = {"entities_found": found[:6], "truth_mentioned": truth_s in found}
        if found and found[0] == truth_s:
            return _result(task, "correct", True, **base)
        if not found:
            refusal = is_refusal(text)
            return _result(task, "unable_to_answer" if refusal else "other", False, detail="no candidate entity named", invalid_answer=not refusal, **base)
        return _result(task, "partially_correct" if base["truth_mentioned"] else "numerically_incorrect", False,
                       detail="first named entity is not the truth", **base)

    raise ValueError(f"unknown answer type {atype}")
