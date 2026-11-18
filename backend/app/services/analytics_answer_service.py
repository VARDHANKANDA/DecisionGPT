"""Answer composition for the analytics path.

The answer is built from the verified result (``query_presenter.facts`` / ``notes``): the FACT first, then the assumptions and caveats.
The AI model may add ONE short restatement of those verified facts, but only if it passes ``validate_explanation``. Every check below is
deterministic (regular expressions, normalised sentences, token overlap against the facts the analytics engine produced); no model is
asked whether another model's text is repetitive or safe. A rejected, empty or failed explanation is simply omitted and the
deterministic text stands, so no figure a user reads ever originates from the model and no caveat can be displaced by it.

What an explanation must NOT do (each is a reason code returned by ``validate_explanation``):

* be empty, non-text, structured markup/JSON, or say "NONE" (the model's way of saying the answer is already complete);
* repeat a sentence (itself, or a verified fact / caveat), or restate one verified sentence in near-identical words;
* add no new context at all (only words and numbers that are already in the facts);
* introduce a number, a causal claim, advice or a forecast, an evaluative judgement, a name/month/weekday that is not in the facts, or
  contradict the direction of a verified change;
* claim completeness ("the whole month") that the verified caveats do not state.

``explanation_needed`` additionally skips the request altogether when the deterministic answer is already one short, clear sentence.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any


@dataclass
class Explanation:
    """The audit shape of the explanation step. ``source`` is ``"template"`` unless a model restatement passed validation."""

    interpretation: str | None = None
    suggestion: str | None = None
    source: str = "template"


_NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")
_CAUSAL = re.compile(r"\b(because|caused?|causing|due to|driven by|result of|results? in|leads? to|led to|thanks to|as a result|owing to|reason|explains?|explained by|contribut\w+)\b", re.I)
_ADVICE = re.compile(r"\b(should|recommend\w*|you could|you might|consider|try to|i suggest|we suggest|make sure|need to|ought to|worth)\b", re.I)
_SPECULATION = re.compile(r"\b(likely|unlikely|probably|perhaps|possibly|maybe|might|could|expected?|forecast\w*|predict\w*|will|going to|trend\w*|seasonal\w*|festiv\w*|holiday|promotion\w*|campaign\w*|competitor\w*)\b", re.I)
_EVALUATIVE = re.compile(r"\b(good|great|excellent|bad|poor|strong|weak|healthy|worrying|concerning|impressive|disappointing|slightly|significantly|"
                         r"dramatic\w*|sharp\w*|steep\w*|huge|massive|tiny|modest|solid|robust|remarkable|notabl\w+|best|worst)\b", re.I)
_COMPLETENESS = re.compile(r"\b(complete|completely|entire|entirely|whole|full|fully|all|every|always|never)\b", re.I)
_UP = re.compile(r"\b(higher|increase\w*|up|rose|rise|risen|grew|grow\w*|gain\w*|more|above|improv\w+)\b", re.I)
_DOWN = re.compile(r"\b(lower|decrease\w*|down|fell|fall\w*|dropp?\w*|declin\w+|less|fewer|below|reduc\w+)\b", re.I)
_MONTHS = ("january february march april may june july august september october november december "
           "jan feb mar apr jun jul aug sep sept oct nov dec monday tuesday wednesday thursday friday saturday sunday").split()
_CAPITAL_MID = re.compile(r"(?<![.!?]\s)(?<!^)\b([A-Z][a-zA-Z]{2,})\b")
_SENTENCE_SPLIT = re.compile(r"(?<!\d\.)(?<=[.!?])\s+")  # not after a list number such as "1. RED ONION"
_NON_TEXT = re.compile(r"^[\W_]+$")
_JSONISH = re.compile(r"^\s*[\[{]|^\s*```|\"\s*:\s*")
_NO_CONTEXT = {"none", "n/a", "na", "no explanation", "nothing to add", "no additional context", "null", "nil", "empty"}

_STOP = frozenset("""a an the of in on at to for from by with and or is are was were be been being it its this that these those your you yours
my our their there here as than then so also just only into over under about which who whom what when while where how
based record records recorded data uploaded sales sale""".split())
# words that read as new content but carry none (a restatement dressed up)
_FILLER = frozenset("amount figure figures result results number numbers value values overall summary key main headline shows show showed "
                    "total totals stands came comes made make makes comes works out".split())

# Words a restatement may add that carry no claim of their own: ordering, comparison, quantity and sentence structure.
_NEUTRAL = frozenset("""led lead leads leading leader lag lags lagged ahead behind trail trails trailed follow follows followed following ranked rank
ranks ranking top bottom first second third fourth fifth sixth last next final remaining rest other others both each either neither
one two three four five six seven eight nine ten single pair pairs together combined combine combines same similar equal equals
higher lower highest lowest more most less least fewer larger smaller bigger greater above below over under than compared compare
comparison difference differ differs gap between among across within against versus rose fell grew dropped declined increase increased
decrease decreased up down change changed unchanged flat leading lies sits sit sat stands came comes goes
but while whereas although though however still yet also only even just about around roughly nearly almost
put puts made make makes take takes took bring brings brought give gives gave show shows showed get gets got has have had
period month week day days weeks months quarter year years product products item items order orders unit units customer customers
percent percentage share part whole portion""".split())

MAX_EXPLANATION_CHARS = 400
MAX_EXPLANATION_SENTENCES = 2
MAX_CLEAR_FACT_CHARS = 200  # a single verified sentence up to this length is already clear: no explanation is requested
MIN_ROWS_FOR_EXPLANATION = 3  # a ranking of at least this many items may get a restatement; a total or a two-way comparison never does
NEAR_DUPLICATE_CONTAINMENT = 0.8  # share of an explanation sentence's content words found in ONE verified sentence
NEAR_DUPLICATE_RATIO = 0.85  # character-level similarity of normalised sentences


def _numbers(text: str) -> set[str]:
    out = set()
    for m in _NUM.findall(text):
        t = m.replace(",", "").rstrip(".")
        if t:
            out.add(t.lstrip("0") or "0")
    return out


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE_SPLIT.split(text.strip()) if s and s.strip()]


def _norm(text: str) -> str:
    """Case-folded text with number formatting removed (13,86,969 -> 1386969), currency/punctuation dropped, whitespace collapsed."""
    t = re.sub(r"(?<=\d),(?=\d)", "", text.casefold())
    t = re.sub(r"₹|\b(?:rs|inr|rupees?)\b\.?", " ", t)
    return re.sub(r"[^a-z0-9.%]+", " ", t).replace(". ", " ").strip(" .")


def _content_words(text: str) -> list[str]:
    out = []
    for w in _norm(text).split():
        w = w.strip(".")
        if not w or w in _STOP:
            continue
        out.append(w[:-1] if len(w) > 3 and w.endswith("s") and not w.endswith("ss") else w)  # crude plural fold
    return out


def _containment(words: list[str], reference: list[str]) -> float:
    return (sum(1 for w in words if w in set(reference)) / len(words)) if words else 1.0


def _verified_sentences(facts: list[str], notes: list[str]) -> list[str]:
    return [s for block in (*facts, *notes) for s in _sentences(block)]


def explanation_needed(facts: list[str], notes: list[str] | None = None, *, no_data: bool = False, n_rows: int = 0) -> bool:
    """False when the deterministic answer is already clear and a model restatement could only repeat it: a result with no data, or a
    single short verified sentence over fewer than ``MIN_ROWS_FOR_EXPLANATION`` rows. The request is then never sent (no provider
    call, no cost). Only a list of several items (or an unusually long sentence) is worth a plain-language lead."""
    if no_data or not facts:
        return False
    return n_rows >= MIN_ROWS_FOR_EXPLANATION or len(facts) > 1 or len(facts[0].strip()) > MAX_CLEAR_FACT_CHARS


def validate_explanation(text: Any, facts: list[str], notes: list[str], question: str | None = None) -> tuple[bool, str]:
    """(ok, reason). Strict on purpose: when in doubt the deterministic template is used. ``question`` (the user's own words) widens the
    vocabulary an explanation may reuse; it is never a source of numbers."""
    if text is None:
        return False, "empty"
    if not isinstance(text, str):
        return False, "non_text"
    t = text.strip()
    if not t:
        return False, "empty"
    if t.casefold().strip(" .!\"'") in _NO_CONTEXT:
        return False, "no_additional_context"
    if len(t) > MAX_EXPLANATION_CHARS:
        return False, "too_long"
    if _NON_TEXT.match(t) or _JSONISH.search(t) or re.search(r"[\x00-\x08\x0b-\x1f\x7f]", t):
        return False, "malformed"
    if re.search(r"[<>`]|https?://|\[.+\]\(.+\)", t):
        return False, "markup_or_link"
    if _CAUSAL.search(t):
        return False, "causal_claim"
    if _ADVICE.search(t):
        return False, "advice"
    verified_text = " ".join(facts) + " " + " ".join(notes)
    allowed = _numbers(verified_text)
    if _numbers(t) - allowed:
        return False, "number_not_in_verified_facts"

    # ---- repetition (deterministic; sentence level) --------------------------------------------------------------
    sents = _sentences(t)
    if len(sents) > MAX_EXPLANATION_SENTENCES:
        return False, "too_many_sentences"
    normed = [_norm(s) for s in sents]
    verified = _verified_sentences(facts, notes)
    vnorm = [_norm(s) for s in verified]
    if len(set(normed)) < len(normed):
        return False, "duplicate_sentence"
    if any(n and n in vnorm for n in normed):
        return False, "duplicate_of_verified_sentence"
    vwords = [_content_words(s) for s in verified]
    for s, n in zip(sents, normed):
        w = _content_words(s)
        if any(_containment(w, ref) >= NEAR_DUPLICATE_CONTAINMENT for ref in vwords if ref) or \
                any(SequenceMatcher(None, n, v).ratio() >= NEAR_DUPLICATE_RATIO for v in vnorm if v):
            return False, "restates_verified_sentence"
    if SequenceMatcher(None, _norm(t), _norm(" ".join(facts))).ratio() >= 0.8:
        return False, "restates_verified_answer"

    # ---- unsupported content -------------------------------------------------------------------------------------
    if _SPECULATION.search(t):
        return False, "speculative_claim"
    if _EVALUATIVE.search(t):
        return False, "evaluative_claim"
    verified_vocab = {w for ws in vwords for w in ws}
    vlow = verified_text.casefold()
    for m in _COMPLETENESS.finditer(t):
        if not re.search(rf"\b{re.escape(m.group(0).casefold())}\b", vlow):
            return False, "unsupported_completeness_claim"  # a caveat says what the data covers; the model may not widen it
    for name in _MONTHS:
        if re.search(rf"\b{name}\b", t, re.I) and not re.search(rf"\b{name}\b", vlow):
            return False, "unsupported_date_or_name"
    for m in _CAPITAL_MID.finditer(t):
        if m.group(1).casefold() not in vlow and m.group(1).casefold() not in {"rupees"}:
            return False, "unsupported_date_or_name"
    if _UP.search(t) and not _DOWN.search(t) and _DOWN.search(verified_text) and not _UP.search(verified_text):
        return False, "contradicts_verified_direction"
    if _DOWN.search(t) and not _UP.search(t) and _UP.search(verified_text) and not _DOWN.search(verified_text):
        return False, "contradicts_verified_direction"

    # ---- must add something, and only something supported ------------------------------------------------------
    qvocab = set(_content_words(question)) if question else set()
    novel = [w for w in _content_words(t) if w not in verified_vocab and w not in qvocab and w not in _FILLER and not re.fullmatch(r"[\d.%]+", w)]
    if not novel:
        return False, "adds_no_new_context"
    # New words may only be neutral structure (rank, comparison, quantity). Any other new word would assert a fact the engine did not
    # produce ("customers prefer ...", "stock ran low"), and cannot be checked deterministically, so the template is used instead.
    if any(w not in _NEUTRAL for w in novel):
        return False, "unsupported_term"
    return True, "ok"


def preserves_verified_text(answer: str, facts: list[str], notes: list[str]) -> bool:
    """Every verified fact and caveat sentence is present, verbatim, in the answer that will be shown."""
    return all(s.strip() in answer for s in (*facts, *notes) if s and s.strip())


def assemble(facts: list[str], notes: list[str], exp: Explanation | None = None) -> str:
    """FACT, then the (validated) restatement if any, then assumptions/caveats - one plain paragraph."""
    parts = list(facts)
    if exp is not None and exp.interpretation:
        parts.append(exp.interpretation)
    parts.extend(notes)
    if exp is not None and exp.suggestion:
        parts.append(exp.suggestion)
    return " ".join(p.strip() for p in parts if p and p.strip())
