"""Credit protection: no automated test, and no offline configuration, can send a paid provider request, even when a real key exists in
``backend/.env``. Every provider call here is either a spy replacing ``OpenAIClient._request`` or is stopped by the network block in
``tests/conftest.py``. Nothing reaches the network; the key values used are dummies."""
import json
from pathlib import Path

import pytest

from app.core.config import Settings, get_settings
from app.services import analytics_chat_service
from app.services.analytics_interpreter_service import QUESTIONS
from app.services.openai_client import OpenAIClient
from research.llm_evaluation.mock_llm import _openai_object, _response, _typed_answers
from tests.analytics_llm_support import make_business, seed_sales

DUMMY = "test-key-NOT-A-REAL-KEY-provider-isolation-0123456789"
REPO = Path(__file__).resolve().parents[2]


def classification(**query):
    interp = {"route": "calculate", "query": {"operation": "aggregate", "metric": "revenue", **query}}
    wire = {k: q.payload() for k, q in QUESTIONS.items()}
    return _response(json.dumps(_openai_object(_typed_answers(interp, wire, None))), (900, 90), model="gpt-4.1-mini-2025-04-14")


@pytest.fixture()
def spy(monkeypatch):
    """A configured key (dummy) and a counter on the single request seam."""
    monkeypatch.setattr(get_settings(), "openai_api_key", DUMMY)
    calls = []

    def seam(client, payload):
        client.last_attempts += 1
        calls.append(payload)
        return classification()

    monkeypatch.setattr(OpenAIClient, "_request", lambda client, payload: seam(client, payload))
    return calls


@pytest.fixture()
def shop(db_session):
    bid = make_business(db_session, "Isolation Shop")
    seed_sales(db_session, bid)
    return bid


# ------------------------------------------------------------------ the suite cannot reach the network or the real key
def test_the_suite_pins_the_key_off_and_the_model_to_a_default():
    s = get_settings()
    assert s.openai_api_key is None and s.llm_enabled is False and s.analytics_llm_active is False
    assert s.openai_model == "gpt-4.1-mini"  # not whatever a developer's backend/.env says


def test_a_real_client_with_a_key_set_cannot_leave_the_machine_in_tests(monkeypatch):
    """No seam is patched: the SDK builds its real httpx client. The conftest transport block must stop the request, so the call
    returns a labelled failure instead of a response (and, with a real key, instead of a paid request)."""
    monkeypatch.setattr(get_settings(), "openai_api_key", DUMMY)
    monkeypatch.setattr(get_settings(), "openai_max_retries", 0)
    res = OpenAIClient().decide("What were my sales in February 2025?", QUESTIONS)
    assert res.ok is False and res.error in {"network_error", "provider_error", "timeout"}
    assert res.answers == {}


def test_the_network_block_is_active_for_plain_httpx_too():
    import httpx

    with pytest.raises(RuntimeError, match="outbound network access is blocked"):
        httpx.Client().get("https://api.openai.com/v1/models")


# ------------------------------------------------------------------ the kill switches send nothing
def test_classification_switch_off_sends_no_request_even_with_a_key(shop, spy, db_session, monkeypatch):
    monkeypatch.setattr(get_settings(), "analytics_llm_enabled", False)
    out = analytics_chat_service.try_answer(db_session, shop, "What were my sales in February 2025?")
    assert out.response is None and out.fallback_reason == "disabled"
    assert spy == []


def test_explanation_switch_off_sends_classification_only(shop, spy, db_session, monkeypatch):
    monkeypatch.setattr(get_settings(), "analytics_explain_enabled", False)
    out = analytics_chat_service.try_answer(db_session, shop, "What were my top 4 products by sales in February 2025?")
    assert out.response is not None and out.response.path == "llm_analytics"
    assert len(spy) == 1 and out.audit["explanation_skipped"] == "disabled" and "explanation_call" not in out.audit


def test_both_switches_off_send_nothing(shop, spy, db_session, monkeypatch):
    monkeypatch.setattr(get_settings(), "analytics_llm_enabled", False)
    monkeypatch.setattr(get_settings(), "analytics_explain_enabled", False)
    assert analytics_chat_service.try_answer(db_session, shop, "Which products sold the most?").response is None
    assert spy == []


# ------------------------------------------------------------------ the loader: what an "empty" variable does (the 2026-10-15 incident)
def test_a_removed_variable_falls_back_to_the_env_file_key_which_is_how_the_incident_happened(tmp_path, monkeypatch):
    """PowerShell `$env:OPENAI_API_KEY=''` REMOVES the variable. With no process variable the file's key is used."""
    env = tmp_path / "backend.env"
    env.write_text(f"OPENAI_API_KEY={DUMMY}\n", encoding="utf-8")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert Settings(_env_file=env).llm_enabled is True


def test_an_empty_but_present_process_variable_disables_ai_but_is_not_relied_on(tmp_path, monkeypatch):
    env = tmp_path / "backend.env"
    env.write_text(f"OPENAI_API_KEY={DUMMY}\n", encoding="utf-8")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    assert Settings(_env_file=env).llm_enabled is False  # true for a real empty value, but a shell may delete it instead


def test_the_kill_switch_is_what_the_offline_launch_configuration_relies_on(tmp_path, monkeypatch):
    env = tmp_path / "backend.env"
    env.write_text(f"OPENAI_API_KEY={DUMMY}\n", encoding="utf-8")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("ANALYTICS_LLM_ENABLED", "false")
    monkeypatch.setenv("ANALYTICS_EXPLAIN_ENABLED", "false")
    s = Settings(_env_file=env)
    assert s.llm_enabled is True  # the key is still loaded...
    assert s.analytics_llm_active is False and s.analytics_explain_enabled is False  # ...but the chat path will not use it


def test_the_offline_launch_configuration_uses_the_kill_switches_and_a_dead_base_url():
    cfg = json.loads((REPO / ".claude" / "launch.json").read_text(encoding="utf-8"))
    offline = next(c for c in cfg["configurations"] if c["name"] == "backend-offline")
    command = " ".join(offline["runtimeArgs"])
    assert "ANALYTICS_LLM_ENABLED='false'" in command and "ANALYTICS_EXPLAIN_ENABLED='false'" in command
    assert "OPENAI_BASE_URL='http://127.0.0.1:9/v1'" in command
    # process-wide network block: every non-local http(s) request goes to a closed local proxy, so no client or endpoint can reach out
    for var in ("HTTPS_PROXY", "HTTP_PROXY", "ALL_PROXY"):
        assert f"$env:{var}='http://127.0.0.1:9'" in command
    assert "$env:NO_PROXY='127.0.0.1,localhost'" in command
    assert "OPENAI_API_KEY=''" not in command  # the empty-assignment idiom does not disable anything on Windows
