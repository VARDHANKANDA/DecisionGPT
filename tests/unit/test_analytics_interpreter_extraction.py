"""Deterministic value extraction of the Jev interpreter (periods, products, limits, weekdays) and request assembly.

Jev only supplies categorical decisions; these tests check that code turns the question text plus those decisions into exactly the
structured request that a competent interpreter produces for each of the 27 frozen research questions. The oracle is the
structured request recorded in ``research/llm_evaluation/mock_llm.py`` (written before any model ran). MOCKED DECISIONS ONLY: this
verifies the extractor and assembler, not Jev's classification accuracy.
"""
import json
from pathlib import Path

import pytest

from app.services import analytics_interpreter_service as I
from research.llm_evaluation.mock_llm import INTERPRETATIONS
from tests.analytics_llm_support import decision

SPEC = json.loads((Path(__file__).resolve().parents[2] / "research" / "llm_evaluation" / "tasks" / "tasks_v1.json").read_text(encoding="utf-8"))
TASKS = {t["task_id"]: t["natural_language_question"] for t in SPEC["tasks"]}
CATALOGUE = ["BIG ONION", "RED ONION", "MILK", "EGG", "SNACKS", "COCONUT OIL L", "CAD DAIRY MIL"]


def decisions_for(oracle: dict):
    """The typed decisions an accurate Jev would return for this intended request."""
    if oracle["route"] == "unsupported":
        return decision(route="missing_data", missing_item="gst_or_tax")
    q = oracle["query"]
    return decision(
        operation=q["operation"], metric=q["metric"], statistic=q.get("statistic", "total"), group_by=q.get("group_by", "none"),
        direction=q.get("direction", "desc"), named_products=0.95 if q.get("products") else 0.05,
    )


@pytest.mark.parametrize("task_id", sorted(INTERPRETATIONS))
def test_frozen_questions_are_assembled_into_the_expected_structured_request(task_id):
    question, oracle = TASKS[task_id], INTERPRETATIONS[task_id]
    data, _hints = I._build(decisions_for(oracle), question, CATALOGUE)
    if oracle["route"] == "unsupported":
        assert data["route"] == "unsupported" and data["unsupported_reason"] == "missing_field"
        return
    assert data["route"] == "analytics_query"
    got, want = dict(data["query"]), dict(oracle["query"])
    from app.schemas.analytics_query import AnalyticsQuery

    g, w = AnalyticsQuery.model_validate(got).model_dump(), AnalyticsQuery.model_validate(want).model_dump()
    for d in (g, w):  # an omitted limit means "the single best" in the engine, which is exactly what limit=1 asks for
        if d["operation"] == "ranking" and d["limit"] in (None, 1):
            d["limit"] = 1
    assert g == w


@pytest.mark.parametrize(
    "text,expected",
    [
        ("sales in February 2025", [{"kind": "calendar", "unit": "month", "year": 2025, "month": 2}]),
        ("sales in feb", [{"kind": "calendar", "unit": "month", "month": 2}]),
        ("from January to March 2025", [{"kind": "absolute", "start": "2025-01-01", "end": "2025-03-31"}]),
        ("between January and March 2025", [{"kind": "absolute", "start": "2025-01-01", "end": "2025-03-31"}]),
        ("1 to 15 March 2025", [{"kind": "absolute", "start": "2025-03-01", "end": "2025-03-15"}]),
        ("on 14 February 2025", [{"kind": "absolute", "start": "2025-02-14", "end": "2025-02-14"}]),
        ("on 2025-02-14", [{"kind": "absolute", "start": "2025-02-14", "end": "2025-02-14"}]),
        ("the last 30 days", [{"kind": "trailing", "count": 30, "unit": "day"}]),
        ("in the past two weeks", [{"kind": "trailing", "count": 2, "unit": "week"}]),
        ("last month", [{"kind": "calendar", "unit": "month", "offset": -1}]),
        ("this year", [{"kind": "calendar", "unit": "year", "offset": 0}]),
        ("in Q1 2025", [{"kind": "calendar", "unit": "quarter", "year": 2025, "quarter": 1}]),
        ("in 2024", [{"kind": "calendar", "unit": "year", "year": 2024}]),
        ("since I started", [{"kind": "all_time"}]),
        ("February 2025 vs January", [{"kind": "calendar", "unit": "month", "year": 2025, "month": 2}, {"kind": "calendar", "unit": "month", "year": 2025, "month": 1}]),
    ],
)
def test_period_extraction(text, expected):
    assert [m.spec for m in I.extract_periods(text)] == expected


def test_may_is_only_a_month_when_the_context_says_so():
    assert I.extract_periods("may I see my sales") == []
    assert [m.spec for m in I.extract_periods("sales in May 2025")] == [{"kind": "calendar", "unit": "month", "year": 2025, "month": 5}]
    assert [m.spec for m in I.extract_periods("sales in May")] == [{"kind": "calendar", "unit": "month", "month": 5}]


def test_impossible_dates_are_not_invented():
    for text in ("total sales on 31 February 2025", "total sales on 2025-13-45", "total sales from 15 to 1 March 2025"):
        assert [m.spec for m in I.extract_periods(text)] == [{"_invalid": True}]
        data, _ = I._build(decision(operation="aggregate", metric="revenue"), text, CATALOGUE)
        assert data["route"] == "clarification" and "time period" in data["clarification_question"]


def test_comparison_roles_and_derived_baseline():
    d = decision(operation="compare_periods", metric="revenue")
    data, _ = I._build(d, "How did March 2025 compare with February 2025?", CATALOGUE)
    q = data["query"]
    assert q["period"]["month"] == 3 and q["comparison_period"]["month"] == 2
    data, _ = I._build(d, "Compared with February 2025, how did March 2025 do?", CATALOGUE)
    assert data["query"]["period"]["month"] == 3 and data["query"]["comparison_period"]["month"] == 2
    data, _ = I._build(d, "By how much did sales change in March 2025?", CATALOGUE)  # one period: baseline is the previous month
    assert data["query"]["comparison_period"] == {"kind": "calendar", "unit": "month", "year": 2025, "month": 2}
    data, _ = I._build(d, "How did sales change in January 2025?", CATALOGUE)  # year boundary
    assert data["query"]["comparison_period"] == {"kind": "calendar", "unit": "month", "year": 2024, "month": 12}
    data, _ = I._build(d, "How did sales change in the last 30 days?", CATALOGUE)  # no well-defined baseline -> ask
    assert data["route"] == "clarification" and "time period" in data["clarification_question"]


def test_limits_weekdays_and_products():
    assert I.extract_limit("top 3 products by sales") == 3
    assert I.extract_limit("which three products sold the most") == 3
    assert I.extract_limit("the three months from January to March") is None
    assert I.extract_limit("which product sold the most") is None
    assert I.extract_weekdays("sales on Sundays and mondays") == [0, 6]
    assert I.extract_products("how many units of big onion and milk", CATALOGUE) == ["BIG ONION", "MILK"]
    assert I.extract_products("onion sales", CATALOGUE) == ["onion"]  # a distinctive word: the engine resolves or lists the candidates
    assert I.extract_products("onion sales", CATALOGUE, fuzzy=False) == []
    assert I.extract_products("sell more things", CATALOGUE) == []


def test_confidence_floor_and_unused_decisions_do_not_block():
    d = decision(operation="aggregate", metric="revenue")
    d.answers["group_by"].confidence = 0.1  # irrelevant for an aggregate, so it must not block
    data, _ = I._build(d, "total sales in February 2025", CATALOGUE)
    assert data["route"] == "analytics_query"
    d.answers["metric"].confidence = 0.2  # used, and below the floor
    with pytest.raises(ValueError, match="low_confidence"):
        I._build(d, "total sales in February 2025", CATALOGUE)


def test_assembled_requests_are_validated_by_the_closed_schema():
    from app.services.openai_client import DecisionResult

    class L:
        def decide(self, state, questions):
            return decision(operation="aggregate", metric="distinct_products", statistic="mean_per_active_day")

    out = I.interpret(L(), "average products per day", None, None, {}, CATALOGUE)
    assert out.interpretation is None and out.error == "invalid_request" and out.validation_errors

    class Down:
        def decide(self, state, questions):
            return DecisionResult(False, {}, "timeout")

    out = I.interpret(Down(), "x", None, None, {}, [])
    assert out.error == "timeout" and out.interpretation is None
