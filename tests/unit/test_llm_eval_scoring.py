"""Scoring rules of the POS LLM evaluation (research/llm_evaluation/scoring.py). No LLM involved."""
from datetime import date

import pytest

from research.llm_evaluation.scoring import (
    direction,
    extract_dates,
    extract_numbers,
    find_entities,
    is_refusal,
    score_answer,
    strip_dates,
)


def T(atype, tol, **kw):
    base = {"task_id": "X01", "expected_answer_type": atype, "tolerance": tol, "signed_change": False, "ranking_k": None, "candidate_entities": None}
    base.update(kw)
    return base


CUR = {"type": "relative", "value": 0.005, "min_abs": 1.0}
EXACT = {"type": "absolute", "value": 0.0}
PP = {"type": "absolute_pp", "value": 0.5}
CAT = {"type": "normalized_first_mention"}


class TestNumberExtraction:
    def test_indian_grouping_and_rupee_prefix(self):
        assert extract_numbers("Your sales were ₹14,59,082.91 in total") == [1459082.91]
        assert extract_numbers("Rs. 1,86,000") == [186000.0]

    def test_lakh_crore_k_multipliers(self):
        assert extract_numbers("about 14.59 lakh") == pytest.approx([1459000.0])
        assert extract_numbers("1.2 crore") == [12_000_000.0]
        assert extract_numbers("roughly 50k units") == [50_000.0]

    def test_dates_and_years_are_not_numbers(self):
        assert extract_numbers("In January 2025 you sold 4,556 units on 20 March 2025 and 2025-03-30") == [4556.0]
        assert extract_numbers("from 1 to 15 March sales rose 0.8%") == [0.8]

    def test_kg_is_not_a_thousand_multiplier(self):
        assert extract_numbers("sold 28 kg") == [28.0]

    def test_negative_sign(self):
        assert extract_numbers("a change of -4.94%") == [-4.94]


class TestDatesEntitiesRefusal:
    def test_date_formats(self):
        for text in ("30 March 2025", "March 30, 2025", "30/03/2025", "2025-03-30", "30th March"):
            assert extract_dates(text) == [date(2025, 3, 30)], text

    def test_entity_order_and_longest_match(self):
        cands = ["BIG ONION", "ONION", "EGG", "MILK"]
        assert find_entities("MILK then big onion, finally egg", cands) == ["MILK", "BIG ONION", "EGG"]
        assert find_entities("big onion", cands) == ["BIG ONION"]  # not also ONION

    def test_refusal_patterns(self):
        assert is_refusal("I don't have enough data to answer that reliably.")
        assert not is_refusal("Total sales were ₹1,459,083.")

    def test_direction(self):
        assert direction("sales fell by 4.9%") == "down"
        assert direction("sales were up 8.8%") == "up"
        assert direction("the change was 8.8%") is None


class TestNumericScoring:
    def test_currency_within_relative_tolerance(self):
        t = T("currency", CUR)
        assert score_answer(t, 1459082.91, "Total sales were ₹14,59,100.")["correct"]
        assert not score_answer(t, 1459082.91, "Total sales were ₹14,00,000.")["correct"]

    def test_currency_lakh_rounding_is_accepted(self):
        assert score_answer(T("currency", CUR), 1459082.91, "About 14.59 lakh rupees.")["correct"]

    def test_exact_number_has_no_slack(self):
        t = T("exact_number", EXACT)
        assert score_answer(t, 47651, "You sold 47,651 units.")["correct"]
        assert not score_answer(t, 47651, "You sold 47,652 units.")["correct"]

    def test_year_in_answer_is_not_mistaken_for_the_value(self):
        res = score_answer(T("exact_number", EXACT), 2025, "In 2025 you sold 100 units.")
        assert not res["correct"] and res["outcome"] == "numerically_incorrect"

    def test_signed_change_requires_direction(self):
        t = T("percentage", PP, signed_change=True)
        assert score_answer(t, -4.9424, "Sales fell by 4.9% compared with January.")["correct"]
        wrong = score_answer(t, -4.9424, "Sales rose by 4.9% compared with January.")
        assert wrong["outcome"] == "correct_number_wrong_interpretation" and not wrong["correct"]
        missing = score_answer(t, -4.9424, "The change was 4.9%.")
        assert missing["outcome"] == "partially_correct"

    def test_percentage_tolerance_is_half_a_point(self):
        t = T("percentage", PP)
        assert score_answer(t, 4.0384, "About 4.3% of sales.")["correct"]
        assert not score_answer(t, 4.0384, "About 5.0% of sales.")["correct"]

    def test_refusal_is_unable_to_answer_not_numeric_error(self):
        res = score_answer(T("currency", CUR), 100.0, "I don't have enough data to answer that reliably.")
        assert res["outcome"] == "unable_to_answer" and not res["correct"]

    def test_wrong_number_is_numerically_incorrect(self):
        assert score_answer(T("currency", CUR), 1000.0, "It was ₹5,000.")["outcome"] == "numerically_incorrect"

    def test_system_error_is_tool_failure(self):
        res = score_answer(T("currency", CUR), 1.0, None, system_error="HTTP 500")
        assert res["outcome"] == "tool_data_access_failure"

    def test_empty_answer_is_invalid(self):
        res = score_answer(T("currency", CUR), 1.0, "  ")
        assert res["outcome"] == "other" and res["invalid_answer"]

    def test_number_free_nonrefusal_is_invalid_answer(self):
        res = score_answer(T("currency", CUR), 1.0, "Sales were great.")
        assert res["outcome"] == "other" and res["invalid_answer"]

    def test_first_number_metric_is_recorded(self):
        res = score_answer(T("currency", CUR), 1000.0, "You sold 5 items worth ₹1,000.")
        assert res["correct"] and res["first_number_correct"] is False and res["n_numbers"] == 2


class TestEntityAndRankingScoring:
    def test_categorical_first_mention(self):
        t = T("categorical", CAT, candidate_entities=["Monday", "Tuesday", "Sunday"])
        assert score_answer(t, "Monday", "Monday is your strongest day, Sunday the weakest.")["correct"]
        wrong = score_answer(t, "Monday", "Sunday is weakest; Monday is strongest.")
        assert not wrong["correct"] and wrong["truth_mentioned"] and wrong["outcome"] == "partially_correct"

    def test_ranking_exact_order(self):
        t = T("ranking", {"type": "ordered_list"}, ranking_k=3)
        prods = ["EGG", "BIG ONION", "MILK", "SNACKS"]
        assert score_answer(t, ["EGG", "BIG ONION", "MILK"], "Top 3: EGG, BIG ONION and MILK.", view_products=prods)["correct"]
        res = score_answer(t, ["EGG", "BIG ONION", "MILK"], "EGG, MILK, BIG ONION", view_products=prods)
        assert not res["correct"] and res["outcome"] == "partially_correct" and res["overlap_at_k"] == 1.0 and res["top1_correct"]

    def test_ranking_wrong_set(self):
        t = T("ranking", {"type": "ordered_list"}, ranking_k=1)
        res = score_answer(t, ["EGG"], "SNACKS sold the most.", view_products=["EGG", "SNACKS"])
        assert res["outcome"] == "numerically_incorrect" and not res["top1_correct"]

    def test_date_scoring(self):
        t = T("date", CAT)
        assert score_answer(t, "2025-03-30", "Your best day was 30 March 2025 with ₹85,772.")["correct"]
        assert not score_answer(t, "2025-03-30", "Your best day was 29 March 2025.")["correct"]

    def test_gst_slab_scoring(self):
        t = T("categorical", CAT, task_id="E04", candidate_entities=["0%", "5%", "18%"])
        assert score_answer(t, "0%", "The 0% GST slab brought in the most sales.")["correct"]
        assert not score_answer(t, "0%", "The 5% GST slab brought in the most sales.")["correct"]


def test_strip_dates_keeps_other_numbers():
    assert "4556" in strip_dates("On 20 March 2025 you sold 4556 units")
