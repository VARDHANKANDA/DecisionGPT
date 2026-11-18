"""Decision responses through the API with authentication: acceptance is not execution, contradictions are refused, retries are safe,
history is append-only and another business cannot reach the decision."""
from datetime import date

import pytest

from app.services import model_registry_service
from tests.api.test_platform_api import P, _owner, auth_on  # noqa: F401  (auth_on is a fixture)
from tests.integration.test_analytics import _seed_rich_business
from tests.integration.test_decisions import _create_goal


@pytest.fixture()
def world(client, db_session, auth_on):  # noqa: F811
    model_registry_service.sync_from_file_registry(db_session)
    a, ha = _owner(client, "da@example.com", "Alpha")
    b, hb = _owner(client, "db@example.com", "Beta")
    _seed_rich_business(client, a, headers=ha)
    gid = client.post(f"{P}/{a}/goals", json={"text": "Increase revenue by 10% in 2 months"}, headers=ha).json()["id"]
    d = client.post(f"{P}/{a}/decisions/analyze", json={"goal_id": gid}, headers=ha)
    assert d.status_code == 200, d.text
    return client, (a, ha), (b, hb), d.json()["id"]


def _resp(client, a, ha, did, **body):
    return client.post(f"{P}/{a}/tracking/decisions/{did}/response", json=body, headers=ha)


def test_acceptance_is_recorded_without_implying_execution(world):
    client, (a, ha), _, did = world
    r = _resp(client, a, ha, did, response="accepted")
    assert r.status_code == 200, r.text
    assert r.json()["response"] == "accepted" and r.json()["action_status"] == "unknown"
    listing = client.get(f"{P}/{a}/tracking/decisions", headers=ha).json()["decisions"]
    cur = {x["decision_id"]: x["current"] for x in listing}[did]
    assert cur["response"] == "accepted" and cur["action_status"] == "unknown" and cur["seq"] == 1
    rep = client.get(f"{P}/{a}/tracking/report", headers=ha).json()
    assert rep["decisions"]["latest_response"]["accepted"] == 1 and rep["decisions"]["executed_confirmed"] == 0


def test_execution_needs_an_explicit_date_and_cannot_be_recorded_for_a_rejection(world):
    client, (a, ha), _, did = world
    assert _resp(client, a, ha, did, response="accepted", action_status="executed").status_code == 422          # no start date
    ok = _resp(client, a, ha, did, response="accepted", action_status="executed", action_start=date.today().isoformat())
    assert ok.status_code == 200 and ok.json()["action_status"] == "executed" and ok.json()["seq"] == 1
    # changing to a rejection while the action is recorded as executed is contradictory and refused
    bad = _resp(client, a, ha, did, response="rejected")
    assert bad.status_code == 422 and "cannot be recorded as executed" in bad.json()["error"]["message"]
    fix = _resp(client, a, ha, did, response="rejected", action_status="not_executed")
    assert fix.status_code == 200 and fix.json()["seq"] == 2                    # a correction is a new revision
    hist = client.get(f"{P}/{a}/tracking/decisions/{did}", headers=ha).json()["history"]
    assert [(h["response"], h["action_status"]) for h in hist] == [("accepted", "executed"), ("rejected", "not_executed")]


def test_a_retry_or_double_click_cannot_create_a_second_identical_or_contradictory_revision(world):
    client, (a, ha), _, did = world
    assert _resp(client, a, ha, did, response="deferred", action_status="not_executed").status_code == 200
    again = _resp(client, a, ha, did, response="deferred", action_status="not_executed")
    assert again.status_code == 422 and "already recorded" in again.json()["error"]["message"]
    assert len(client.get(f"{P}/{a}/tracking/decisions/{did}", headers=ha).json()["history"]) == 1


def test_modified_needs_a_description_and_deferral_cannot_be_executed(world):
    client, (a, ha), _, did = world
    assert _resp(client, a, ha, did, response="modified").status_code == 422
    assert _resp(client, a, ha, did, response="deferred", action_status="executed", action_start=date.today().isoformat()).status_code == 422
    ok = _resp(client, a, ha, did, response="modified", modified_action={"description": "price +3% instead of +5%"})
    assert ok.status_code == 200 and ok.json()["modified_action"] == {"description": "price +3% instead of +5%"}
    assert ok.json()["action_status"] == "unknown"                              # modified is not recorded as executing the original


def test_another_business_cannot_read_or_write_the_decision(world):
    client, (a, ha), (b, hb), did = world
    assert client.post(f"{P}/{a}/tracking/decisions/{did}/response", json={"response": "accepted"}).status_code == 401
    assert client.post(f"{P}/{a}/tracking/decisions/{did}/response", json={"response": "accepted"}, headers=hb).status_code in (403, 404)
    assert client.post(f"{P}/{b}/tracking/decisions/{did}/response", json={"response": "accepted"}, headers=hb).status_code == 404   # id of A's decision
    assert client.get(f"{P}/{b}/tracking/decisions/{did}", headers=hb).status_code == 404
    assert client.get(f"{P}/{b}/tracking/decisions", headers=hb).json() == {"decisions": []}
    assert client.get(f"{P}/{a}/tracking/decisions/{did}", headers=ha).json()["history"] == []     # nothing was written by the attempts


def test_response_bodies_are_strict(world):
    client, (a, ha), _, did = world
    for bad in ({"response": "approved"}, {"action_status": "done"}, {"surprise": 1}, {"action_start": "yesterday"},
                {"evaluation_design": "magic"}, {"known_changes": ["x"] * 21}):
        assert _resp(client, a, ha, did, **bad).status_code == 422, bad


def test_changing_to_a_rejection_does_not_keep_the_dates_of_an_earlier_execution(world):
    client, (a, ha), _, did = world
    assert _resp(client, a, ha, did, response="accepted", action_status="executed", action_start=date.today().isoformat()).status_code == 200
    r = _resp(client, a, ha, did, response="rejected", action_status="not_executed")
    assert r.status_code == 200 and r.json()["action_start"] is None and r.json()["action_taken"] is None
    # an explicit start date on something that was not carried out is contradictory
    bad = _resp(client, a, ha, did, response="deferred", action_status="not_executed", action_start=date.today().isoformat())
    assert bad.status_code == 422 and "can only be recorded for an action that was carried out" in bad.json()["error"]["message"]

