"""Business-OS endpoints: authentication, tenant isolation, strict request validation, confirmation gates, honest unconfigured states."""
from datetime import date

import pytest

from app.core.config import get_settings
from app.services import explain_service
from tests import platform_support as ps

P = "/api/v1/businesses"


@pytest.fixture()
def auth_on(monkeypatch):
    monkeypatch.setattr(get_settings(), "auth_enabled", True)


def _owner(client, email, name):
    token = client.post("/api/v1/auth/register", json={"email": email, "password": "orange-river-4271", "role": "sme", "full_name": "T"}).json()["access_token"]
    h = {"Authorization": f"Bearer {token}"}
    bid = client.post(P, json={"name": name, "industry": "retail", "business_type": "D2C", "business_size": "small"}, headers=h).json()["id"]
    return bid, h


@pytest.fixture()
def two_tenants(client, db_session, auth_on):
    a, ha = _owner(client, "a@example.com", "Alpha Co")
    b, hb = _owner(client, "b@example.com", "Beta Co")
    pids = ps.products(db_session, a)
    ps.two_period_sales(db_session, a, pids, date(2025, 3, 31), 2, 3)
    return client, (a, ha), (b, hb)


GETS = ["/kpis?anchor=latest", "/health-score?anchor=latest", "/alerts", "/alerts/rules", "/reports", "/reports/types", "/data/pipeline", "/data/prep-history",
        "/data/profile/sales", "/data/cleaning/sales", "/data/transform/options", "/causal/runs", "/counterfactual/runs", "/debate/runs", "/debate/status"]


@pytest.mark.parametrize("path", GETS)
def test_every_route_needs_a_valid_token_and_the_right_business(two_tenants, path):
    client, (a, ha), (b, hb) = two_tenants
    assert client.get(P + f"/{a}{path}").status_code == 401  # no token
    assert client.get(P + f"/{a}{path}", headers=hb).status_code in (403, 404)  # another owner's token
    assert client.get(P + f"/{a}{path}", headers=ha).status_code == 200


def test_other_tenants_data_never_appears(two_tenants):
    client, (a, ha), (b, hb) = two_tenants
    mine = client.get(P + f"/{a}/kpis?anchor=latest", headers=ha).json()
    theirs = client.get(P + f"/{b}/kpis?anchor=latest", headers=hb).json()
    rev = lambda d: next(k for k in d["kpis"] if k["key"] == "revenue")["value"]  # noqa: E731
    assert rev(mine) == 930.0 and (rev(theirs) in (0, 0.0, None))
    assert client.get(P + f"/{b}/data/profile/sales", headers=hb).json()["rows"] == 0


def test_a_saved_report_or_run_cannot_be_opened_through_another_business(two_tenants):
    client, (a, ha), (b, hb) = two_tenants
    rid = client.post(P + f"/{a}/reports", json={"report_type": "performance", "period_days": 30, "anchor": "latest"}, headers=ha).json()["id"]
    assert client.get(P + f"/{a}/reports/{rid}", headers=ha).status_code == 200
    assert client.get(P + f"/{b}/reports/{rid}", headers=hb).status_code == 404
    assert client.delete(P + f"/{b}/reports/{rid}", headers=hb).status_code == 404
    assert client.get(P + f"/{a}/reports/{rid}", headers=ha).status_code == 200  # still there
    run = client.post(P + f"/{a}/debate/run", json={"question": "How are sales?", "anchor": "latest"}, headers=ha).json()
    assert client.get(P + f"/{b}/debate/runs/{run['id']}", headers=hb).status_code == 404
    assert client.get(P + f"/{b}/debate/runs", headers=hb).json()["runs"] == []


@pytest.mark.parametrize(
    "method,path,body",
    [
        ("post", "/debate/run", {"question": "hi", "mode": "rule_based", "surprise": 1}),
        ("post", "/debate/run", {"question": "", "mode": "rule_based"}),
        ("post", "/debate/run", {"question": "x" * 501}),
        ("post", "/debate/run", {"question": "hi", "mode": "magic"}),
        ("post", "/reports", {"report_type": "performance", "extra": True}),
        ("post", "/data/cleaning/apply", {"proposal_id": "trim:sales:x", "oops": 1}),
        ("post", "/causal/analyze", {"method": "magic", "outcome": "revenue"}),
        ("put", "/kpis/revenue/target", {"value": 1, "direction": "up", "nope": 1}),
        ("post", "/alerts/zzz/status", {"status": "deleted"}),
    ],
)
def test_requests_are_strictly_validated(two_tenants, method, path, body):
    client, (a, ha), _ = two_tenants
    r = getattr(client, method)(P + f"/{a}{path}", json=body, headers=ha)
    assert r.status_code == 422, r.text


def test_cleaning_requires_explicit_confirmation(two_tenants, db_session):
    client, (a, ha), _ = two_tenants
    props = client.get(P + f"/{a}/data/cleaning/sales", headers=ha).json()["proposals"]
    if not props:  # clean data -> nothing to apply; the gate is exercised on a made-up id
        r = client.post(P + f"/{a}/data/cleaning/apply", json={"proposal_id": "dedupe:sales:x", "confirm": True}, headers=ha)
        assert r.status_code in (404, 422)
        return
    r = client.post(P + f"/{a}/data/cleaning/apply", json={"proposal_id": props[0]["id"], "confirm": False}, headers=ha)
    assert r.status_code == 422 and "confirm" in r.text.lower()


def test_unknown_table_and_kpi_are_rejected_not_guessed(two_tenants):
    client, (a, ha), _ = two_tenants
    assert client.get(P + f"/{a}/data/profile/not_a_table", headers=ha).status_code in (404, 422)
    assert client.get(P + f"/{a}/explain/kpi/not_a_kpi", headers=ha).status_code in (404, 422)
    assert client.put(P + f"/{a}/kpis/not_a_kpi/target", json={"value": 5, "direction": "higher", "period_days": 30}, headers=ha).status_code in (404, 422)


def test_kpi_target_roundtrip_and_status_rule(two_tenants):
    client, (a, ha), _ = two_tenants
    r = client.put(P + f"/{a}/kpis/revenue/target", json={"value": 500, "direction": "higher", "period_days": 30}, headers=ha)
    assert r.status_code == 200, r.text
    k = next(x for x in client.get(P + f"/{a}/kpis?anchor=latest", headers=ha).json()["kpis"] if x["key"] == "revenue")
    assert k["target"]["value"] == 500 and k["status"] == "met" and k["status_rule"]
    assert client.delete(P + f"/{a}/kpis/revenue/target", headers=ha).status_code == 204
    k2 = next(x for x in client.get(P + f"/{a}/kpis?anchor=latest", headers=ha).json()["kpis"] if x["key"] == "revenue")
    assert k2["target"] is None and k2["status"] == "no_target"


def test_alerts_check_is_on_demand_and_deduplicated(two_tenants):
    client, (a, ha), _ = two_tenants
    first = client.post(P + f"/{a}/alerts/evaluate?anchor=latest", headers=ha).json()
    second = client.post(P + f"/{a}/alerts/evaluate?anchor=latest", headers=ha).json()
    assert "does not monitor continuously" in first["monitoring_note"].lower()
    n1 = len(client.get(P + f"/{a}/alerts", headers=ha).json()["alerts"])
    assert first["created"] >= 1 and second["created"] == 0  # the second check re-confirms, it does not duplicate
    assert n1 == len(client.get(P + f"/{a}/alerts", headers=ha).json()["alerts"])


def test_debate_without_a_provider_is_honest_about_ai_mode(two_tenants):
    client, (a, ha), _ = two_tenants
    status = client.get(P + f"/{a}/debate/status", headers=ha).json()
    assert status["rule_based_available"] is True and status["ai_model_available"] is False and "not implemented" in status["ai_model_notice"]
    r = client.post(P + f"/{a}/debate/run", json={"question": "Should I raise prices?", "mode": "ai_model"}, headers=ha).json()
    assert r["status"] == "ai_model_unavailable" and "id" not in r
    assert client.get(P + f"/{a}/debate/runs", headers=ha).json()["runs"] == []
    ok = client.post(P + f"/{a}/debate/run", json={"question": "Should I raise prices?", "anchor": "latest"}, headers=ha).json()
    assert ok["status"] == "completed" and ok["no_automatic_action"] is True and "no AI model" in ok["label"]
    assert len(client.get(P + f"/{a}/debate/runs", headers=ha).json()["runs"]) == 1


def test_causal_and_counterfactual_endpoints_label_their_results(two_tenants, db_session):
    client, (a, ha), _ = two_tenants
    r = client.post(P + f"/{a}/causal/analyze", json={"method": "association", "outcome": "revenue", "treatment": "marketing_spend"}, headers=ha).json()
    assert r["classification"] in ("not_enough_data", "exploratory_association") and r["classification"] != "causal_estimate"
    c = client.post(P + f"/{a}/counterfactual/run", json={"mode": "deterministic_scenario", "lever": "price_change_pct", "change_pct": 10, "baseline_days": 30, "anchor": "latest"}, headers=ha)
    assert c.status_code in (200, 201) and c.json()["label"] == "Deterministic scenario calculation"


def test_explain_kpi_and_unknown_answer(two_tenants):
    client, (a, ha), (b, hb) = two_tenants
    e = client.get(P + f"/{a}/explain/kpi/revenue?anchor=latest", headers=ha).json()
    assert e["kind"] == "kpi" and e["result"]["value"] == 930.0 and e["rows_used"]["sales_rows"] > 0 and "no model" in e["method"].lower()
    assert client.get(P + f"/{a}/explain/answer/does-not-exist", headers=ha).status_code == 404


def test_explain_answer_distinguishes_router_from_llm_path(db_session):
    from app.models.memory import BusinessMemory

    bid = ps.business(db_session)
    other = ps.business(db_session, "Other")
    m = BusinessMemory(business_id=bid, memory_type="chat", content="q", metadata_json={"question": "How are sales?", "answer": "ok", "path": "legacy_router", "intent": "sales_summary"})
    db_session.add(m)
    db_session.commit()
    e = explain_service.explain_answer(db_session, bid, m.id)
    assert e["path"] == "legacy_router" and "No AI model wrote" in e["method"]
    with pytest.raises(Exception):
        explain_service.explain_answer(db_session, other, m.id)  # tenant isolation
