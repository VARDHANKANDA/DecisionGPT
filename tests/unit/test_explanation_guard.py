"""The deterministic guard around the optional model restatement (``analytics_answer_service``). Pure functions, no provider, no
network, no database. Each test names the failure mode the guard exists for: the OpenAI smoke run showed restatements that repeated the
verified fact and the caveat almost word for word."""
import pytest

from app.services import analytics_answer_service as aas

RANK = ["For February 2025, ranked by sales (highest first): 1. RED ONION (₹3,180), 2. BIG ONION (₹2,950), 3. MILK (₹2,100), 4. EGG (₹600)."]
NOTE = "This is based on the sales recorded in your uploaded data."
NOTES = [NOTE]
COVERAGE = ["Your data covers 1 January 2025 to 15 February 2025, so this period is only partly covered."]
CMP = ["Sales in February 2025 were ₹13,86,969, compared with ₹14,59,083 in January 2025 — 4.94% lower (a difference of ₹72,114)."]
QUESTION = "What were my top 4 products by sales in February 2025?"


def check(text, facts=RANK, notes=NOTES, question=QUESTION):
    return aas.validate_explanation(text, facts, notes, question)


# ------------------------------------------------------------------ 1. exact duplicate sentences
def test_a_sentence_repeated_inside_the_explanation_is_rejected():
    assert check("RED ONION led, ahead of BIG ONION. RED ONION led, ahead of BIG ONION.") == (False, "duplicate_sentence")


def test_an_explanation_that_is_a_verified_fact_or_caveat_verbatim_is_rejected():
    assert check(RANK[0]) == (False, "duplicate_of_verified_sentence")
    assert check(NOTE) == (False, "duplicate_of_verified_sentence")
    assert check(NOTE.upper().rstrip(".")) == (False, "duplicate_of_verified_sentence")  # case and final punctuation are normalised away


# ------------------------------------------------------------------ 2. near-identical answer and explanation
@pytest.mark.parametrize("text", [
    "For February 2025 the ranking by sales, highest first, is 1. RED ONION (₹3,180), 2. BIG ONION (₹2,950), 3. MILK (₹2,100) and 4. EGG (₹600).",
    "February 2025, ranked by sales (highest first): RED ONION (₹3,180), BIG ONION (₹2,950), MILK (₹2,100), EGG (₹600).",
    "Ranked by sales for February 2025 (highest first): 1. RED ONION (₹3,180), 2. BIG ONION (₹2,950), 3. MILK (₹2,100), 4. EGG (₹600). Based on the sales recorded in your uploaded data.",
])
def test_a_reworded_copy_of_the_verified_answer_is_rejected(text):
    ok, why = check(text)
    assert not ok and why in {"restates_verified_sentence", "restates_verified_answer", "duplicate_of_verified_sentence", "too_many_sentences"}


def test_the_observed_smoke_run_pattern_is_rejected_on_a_total():
    facts = ["Your total sales for February 2025 were ₹13,86,969."]
    notes = ["This is based on the sales recorded in your uploaded data."]
    for text in ("Your total sales for February 2025 were ₹13,86,969, based on the sales recorded in your uploaded data.",
                 "Total sales for February 2025 came to ₹13,86,969.",
                 "Sales were ₹13,86,969 in February 2025."):
        ok, _why = aas.validate_explanation(text, facts, notes, "What were my sales in February 2025?")
        assert not ok


# ------------------------------------------------------------------ 3. repeated numerical facts
def test_repeating_verified_numbers_without_new_context_is_rejected():
    ok, why = check("RED ONION made ₹3,180 and BIG ONION made ₹2,950.")
    assert not ok and why in {"adds_no_new_context", "restates_verified_sentence"}


# ------------------------------------------------------------------ 4. a changed number
@pytest.mark.parametrize("text", [
    "RED ONION led with ₹3,810, ahead of BIG ONION.",        # transposed digits
    "RED ONION led, ahead of BIG ONION by ₹230.",            # a derived number the engine never produced
    "RED ONION led with about 3.2 thousand.",                # a re-expressed number
])
def test_an_explanation_that_changes_or_adds_a_number_is_rejected(text):
    assert check(text) == (False, "number_not_in_verified_facts")


def test_a_changed_percentage_is_rejected_on_a_comparison():
    assert check("February was 4.95% lower, a shortfall against January.", CMP, NOTES) == (False, "number_not_in_verified_facts")


# ------------------------------------------------------------------ 5. unsupported claims
@pytest.mark.parametrize("text,why", [
    ("RED ONION led because shoppers prefer it.", "causal_claim"),
    ("RED ONION led, which explains the shortfall elsewhere.", "causal_claim"),
    ("You should stock more RED ONION.", "advice"),
    ("RED ONION will probably lead again in March.", "speculative_claim"),
    ("RED ONION led, a strong result.", "evaluative_claim"),
    ("RED ONION led, ahead of BIG ONION, during Diwali.", "unsupported_date_or_name"),
    ("RED ONION led, ahead of BIG ONION, in March.", "unsupported_date_or_name"),
    ("Customers prefer RED ONION over BIG ONION.", "unsupported_term"),       # a new factual assertion with no number or cause word
    ("RED ONION led and the shop ran out of MILK.", "unsupported_term"),
])
def test_an_explanation_with_an_unsupported_claim_is_rejected(text, why):
    assert check(text) == (False, why)


def test_an_explanation_that_contradicts_the_verified_direction_is_rejected():
    assert check("February was higher than January, a gain of 4.94%.", CMP, NOTES) == (False, "contradicts_verified_direction")


# ------------------------------------------------------------------ 6. caveats
def test_an_explanation_may_not_widen_what_a_caveat_limits():
    ok, why = check("RED ONION led for the whole month, ahead of BIG ONION.", RANK, COVERAGE)
    assert (ok, why) == (False, "unsupported_completeness_claim")


def test_the_caveat_is_never_displaced_by_a_restatement():
    exp = aas.Explanation(interpretation="RED ONION led, ahead of BIG ONION.", source="openai")
    answer = aas.assemble(RANK, COVERAGE, exp)
    assert aas.preserves_verified_text(answer, RANK, COVERAGE)
    assert answer.index(RANK[0]) < answer.index(exp.interpretation) < answer.index(COVERAGE[0])  # fact, restatement, caveat
    assert not aas.preserves_verified_text(RANK[0] + " RED ONION led.", RANK, COVERAGE)


# ------------------------------------------------------------------ 7. a valid explanation with useful, supported context
@pytest.mark.parametrize("text", [
    "RED ONION led, ahead of BIG ONION, with EGG last of the four.",
    "RED ONION came first and EGG last; MILK sat between BIG ONION and EGG.",
])
def test_a_supported_explanation_that_adds_ranking_context_is_accepted(text):
    assert check(text) == (True, "ok")


def test_the_accepted_explanation_is_shown_between_fact_and_caveat():
    text = "RED ONION led, ahead of BIG ONION, with EGG last of the four."
    assert check(text) == (True, "ok")
    answer = aas.assemble(RANK, NOTES, aas.Explanation(interpretation=text, source="openai"))
    assert answer == f"{RANK[0]} {text} {NOTE}"


# ------------------------------------------------------------------ 8. empty or malformed output
@pytest.mark.parametrize("text,why", [
    (None, "empty"), ("", "empty"), ("   \n ", "empty"),
    ([], "non_text"), ({"text": "RED ONION led."}, "non_text"), (42, "non_text"),
    ("NONE", "no_additional_context"), ("none.", "no_additional_context"), ("N/A", "no_additional_context"),
    ('{"explanation": "RED ONION led"}', "malformed"), ("[1, 2]", "malformed"), ("```RED ONION led```", "malformed"),
    ("...", "malformed"), ("RED ONION\x00led", "malformed"),
    ("<b>RED ONION</b> led", "markup_or_link"), ("See https://example.com", "markup_or_link"),
    ("RED ONION led. " * 40, "too_long"),
])
def test_empty_or_malformed_output_is_never_shown(text, why):
    assert check(text) == (False, why)


def test_more_than_two_sentences_is_rejected():
    assert check("RED ONION led. BIG ONION followed. MILK came third.") == (False, "too_many_sentences")


# ------------------------------------------------------------------ the request itself
def test_a_short_single_sentence_answer_needs_no_explanation_request():
    assert aas.explanation_needed(["Your total sales for February 2025 were ₹13,86,969."], NOTES) is False
    assert aas.explanation_needed(CMP, NOTES, n_rows=2) is False
    assert aas.explanation_needed(RANK, NOTES, no_data=True) is False
    assert aas.explanation_needed([], NOTES) is False


def test_a_multi_row_list_may_get_one():
    assert aas.explanation_needed(RANK, NOTES, n_rows=4) is True
    assert aas.explanation_needed(["x" * 300], NOTES) is True
    assert aas.explanation_needed(["One.", "Two."], NOTES) is True
