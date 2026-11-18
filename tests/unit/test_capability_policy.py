"""Capability policy: a question about data the records do not hold is answered with one honest statement of what is missing, and a
clarification is asked only when the answer would then be available. Mocked decisions only; no provider, no network."""
import pytest

from app.models.customer import Customer
from app.models.product import Product
from app.models.sale import Sale
from app.services import analytics_interpreter_service as ai
from tests.analytics_llm_support import FakeLLM, decision

CATALOGUE = ["BIG ONION", "RED ONION", "MILK", "EGG"]


# ------------------------------------------------------------------ the policy is general and based on the schema, not on one task
@pytest.mark.parametrize("question,key", [
    ("How much GST did I collect last month?", "gst_or_tax"),
    ("How much of my sales between January and March 2025 came from items with 5% GST?", "gst_or_tax"),
    ("What is my total tax liability for 2025?", "gst_or_tax"),
    ("Show sales including IGST", "gst_or_tax"),
    ("Which region sold the most in February?", "region"),
    ("Sales by city please", "region"),
    ("How much came in through UPI?", "payment_mode"),
    ("What was my payment method split?", "payment_mode"),
    ("Which marketing channel brought the most sales?", "marketing_channel"),
])
def test_questions_that_need_data_the_records_do_not_hold_are_detected(question, key):
    assert ai.detect_unavailable_attribute(question, CATALOGUE) == key


@pytest.mark.parametrize("question", [
    "What were my sales in February 2025?",
    "What were the top 3 products by quantity in February?",
    "How did March compare with February?",
    "What share of my sales came from MILK and EGG?",
    "Which weekday had the most sales?",
    "How many different products did I sell in January?",
])
def test_supported_questions_are_not_flagged(question):
    assert ai.detect_unavailable_attribute(question, CATALOGUE) is None


def test_a_product_whose_name_contains_the_word_is_a_product_not_the_attribute():
    assert ai.detect_unavailable_attribute("What were sales of Tax Free Salt in February?", ["Tax Free Salt", "MILK"]) is None
    assert ai.detect_unavailable_attribute("What were sales of Tax Free Salt including GST?", ["Tax Free Salt"]) == "gst_or_tax"


def test_the_table_stays_truthful_to_the_data_model():
    """Every attribute listed as unavailable must still have no column in the records. When a column is added, this fails: remove the
    entry and teach the engine to use it, instead of refusing a question the data could answer."""
    columns = {c.name.lower() for m in (Sale, Product, Customer) for c in m.__table__.columns}
    hints = {"gst_or_tax": ("gst", "tax"), "region": ("region", "city", "location", "pincode", "zip"),
             "payment_mode": ("payment", "upi"), "marketing_channel": ("channel", "campaign")}
    assert set(hints) == set(ai.UNAVAILABLE_ATTRIBUTES)
    for key, words in hints.items():
        assert not [c for c in columns if any(w in c for w in words)], f"{key} now has a column; update the capability table"


# ------------------------------------------------------------------ through the interpreter
def interpret(question, **kw):
    fake = FakeLLM({question: decision(**kw)})
    return fake, ai.interpret(fake, question, None, None, {}, CATALOGUE)


@pytest.mark.parametrize("route,extra", [
    ("calculate", {"operation": "share_of_total", "named_products": 0.9}),   # the path that used to ask "Which product do you mean?"
    ("calculate", {"operation": "aggregate"}),
    ("clarify", {"clarify_about": "product"}),
])
def test_a_gst_question_is_refused_not_clarified_whatever_route_the_model_chose(route, extra):
    q = "How much of my sales between January and March 2025 came from items with 5% GST?"
    fake, out = interpret(q, route=route, **extra)
    it = out.interpretation
    assert it is not None and it.route == "unsupported" and it.unsupported_reason == "missing_field"
    assert it.unsupported_item == "GST or tax information" and it.query is None and it.clarification_question is None
    assert out.decisions["extracted"]["capability_check"] == {"unavailable_attribute": "gst_or_tax", "model_route": route}
    assert len(fake.calls) == 1


def test_an_ambiguous_question_the_data_can_answer_is_still_clarified():
    q = "What share of my sales came from it?"
    _, out = interpret(q, route="calculate", operation="share_of_total", named_products=0.9)
    assert out.interpretation.route == "clarification" and out.interpretation.clarification_question == ai.CLARIFY_TEXT["product"]
    q = "How are my sales?"
    _, out = interpret(q, route="clarify", clarify_about="period")
    assert out.interpretation.route == "clarification" and out.interpretation.clarification_question == ai.CLARIFY_TEXT["period"]


def test_a_supported_question_is_unchanged_by_the_policy():
    q = "What were my sales in February 2025?"
    _, out = interpret(q, route="calculate", operation="aggregate", metric="revenue")
    assert out.interpretation.route == "analytics_query" and out.interpretation.query.metric == "revenue"
    assert "capability_check" not in out.decisions["extracted"]


def test_the_models_own_missing_data_decision_is_still_honoured():
    q = "How many items are left on the shelf?"
    _, out = interpret(q, route="missing_data", missing_item="stock")
    assert out.interpretation.route == "unsupported" and out.interpretation.unsupported_item == "stock level information"
