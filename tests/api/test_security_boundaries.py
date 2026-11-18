"""Security boundaries over real HTTP with authentication on: registration cannot create an administrator, sign-in is needed before anything is
created, a missing business and someone else's business are indistinguishable, every route is classified (so a new route cannot silently skip
authorization), and nested objects cannot be reached through a foreign parent. Synthetic fixtures only."""
import re
import uuid

import pytest

from app.main import app as fastapi_app
from app.services import model_registry_service
from tests.admin_support import admin_token
from tests.api.test_platform_api import P, _owner, auth_on  # noqa: F401  (auth_on is a fixture)
from tests.integration.test_analytics import _seed_rich_business

BIZ = re.compile(r"^/api/v1/businesses/\{business_id\}")
# Routes that are public by design, or that need a signed-in user but no business. Everything else must be business-scoped or research-gated.
# (logout is public by design: it ends the presented session if the token is genuine and answers 204 either way, so it reveals nothing)
PUBLIC = {("GET", "/"), ("GET", "/api/v1/health"), ("POST", "/api/v1/auth/register"), ("POST", "/api/v1/auth/login"), ("POST", "/api/v1/auth/logout")}
SIGNED_IN = {("GET", "/api/v1/auth/me"), ("POST", "/api/v1/businesses"), ("POST", "/api/v1/businesses/demo"), ("GET", "/api/v1/businesses/mine"),
             ("POST", "/api/v1/auth/logout-all"), ("POST", "/api/v1/auth/change-password")}


def routes():
    out = []
    for path, ops in fastapi_app.openapi()["paths"].items():
        for method in ops:
            if method in ("get", "post", "put", "patch", "delete"):
                out.append((method.upper(), path))
    return out


def fill(path: str, business_id: str) -> str:
    return re.sub(r"\{[^}]+\}", lambda m: business_id if m.group(0) == "{business_id}" else str(uuid.uuid4()), path)


# ------------------------------------------------------------------ sign-up and creation
def test_public_sign_up_cannot_create_an_administrator(client, auth_on):
    r = client.post("/api/v1/auth/register", json={"email": "evil@example.com", "password": "orange-river-4271", "role": "admin"})
    assert r.status_code == 403 and "Only business accounts" in r.json()["error"]["message"]
    assert client.post("/api/v1/auth/login", json={"email": "evil@example.com", "password": "orange-river-4271"}).status_code == 401   # nothing was created
    ok = client.post("/api/v1/auth/register", json={"email": "ok@example.com", "password": "orange-river-4271"})
    assert ok.status_code == 201 and ok.json()["user"]["role"] == "sme"
    tok = ok.json()["access_token"]
    assert client.get("/api/v1/research/overview", headers={"Authorization": f"Bearer {tok}"}).status_code == 403


def test_an_administrator_created_out_of_band_can_still_reach_research(client, db_session, auth_on):
    tok = admin_token(client, db_session, "ops@example.com")
    assert client.get("/api/v1/research/overview", headers={"Authorization": f"Bearer {tok}"}).status_code == 200


def test_nothing_is_created_before_sign_in(client, db_session, auth_on):
    from app.models.business import Business

    body = {"name": "Anon", "industry": "retail", "business_type": "D2C", "business_size": "small"}
    assert client.post("/api/v1/businesses", json=body).status_code == 401
    assert client.post("/api/v1/businesses/demo").status_code == 401
    assert db_session.query(Business).count() == 0                                           # no row, no demo history generated
    assert client.get("/api/v1/businesses/mine").json() == []                              # documented: empty when not signed in
    tok = client.post("/api/v1/auth/register", json={"email": "own@example.com", "password": "orange-river-4271"}).json()["access_token"]
    r = client.post("/api/v1/businesses", json=body, headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 201


def test_local_development_without_authentication_still_works(client):
    body = {"name": "Local", "industry": "retail", "business_type": "D2C", "business_size": "small"}
    assert client.post("/api/v1/businesses", json=body).status_code == 201                  # the documented local-only mode


# ------------------------------------------------------------------ one answer for "missing" and "not yours"
def test_a_missing_business_and_someone_elses_business_are_indistinguishable(client, auth_on):
    a, ha = _owner(client, "ua@example.com", "Alpha Secret Name")
    b, hb = _owner(client, "ub@example.com", "Beta")
    ghost = str(uuid.uuid4())
    for path in ("/kpis?period_days=30", "/tracking/report", "/goals", "/data/summary"):
        foreign = client.get(f"{P}/{a}{path}", headers=hb)
        missing = client.get(f"{P}/{ghost}{path}", headers=hb)
        assert foreign.status_code == missing.status_code == 404, path
        assert foreign.json()["error"]["code"] == missing.json()["error"]["code"] == "NOT_FOUND"
        assert foreign.json()["error"]["message"] == missing.json()["error"]["message"] == "Business not found."
        assert a not in foreign.text and "Alpha Secret Name" not in foreign.text
        anon_foreign, anon_missing = client.get(f"{P}/{a}{path}"), client.get(f"{P}/{ghost}{path}")
        assert anon_foreign.status_code == anon_missing.status_code == 401                 # an anonymous caller learns nothing about existence
        assert anon_foreign.json()["error"]["message"] == anon_missing.json()["error"]["message"]
    for r in (client.get(f"{P}/{a}", headers=hb), client.patch(f"{P}/{a}", json={"name": "x"}, headers=hb)):
        assert r.status_code == 404 and "Alpha Secret Name" not in r.text
    assert client.get(f"{P}/{a}", headers=ha).json()["name"] == "Alpha Secret Name"       # the owner is unaffected


def test_the_owner_cannot_change_the_owner_of_a_business(client, auth_on):
    a, ha = _owner(client, "uo@example.com", "Own")
    b, hb = _owner(client, "up@example.com", "Other")
    r = client.patch(f"{P}/{a}", json={"owner_user_id": "x"}, headers=ha)
    assert client.get(f"{P}/{a}", headers=hb).status_code == 404 and client.get(f"{P}/{a}", headers=ha).status_code == 200
    assert r.status_code in (200, 422)


# ------------------------------------------------------------------ every route is classified (new routes cannot skip authorization)
def test_every_route_is_public_signed_in_research_or_business_scoped(client, auth_on):
    unclassified = [(m, p) for m, p in routes()
                    if (m, p) not in PUBLIC and (m, p) not in SIGNED_IN and not BIZ.match(p) and not p.startswith("/api/v1/research")]
    assert not unclassified, (
        f"{unclassified} are not covered by any guard. Business data routes must live under /businesses/{{business_id}} (guarded by "
        "verify_business_access), administrator routes under /research; add a deliberately public route to PUBLIC with a reason."
    )


def test_every_business_route_demands_a_token_and_hides_other_businesses(client, auth_on):
    a, ha = _owner(client, "ca@example.com", "Cov A")
    b, hb = _owner(client, "cb@example.com", "Cov B")
    biz_routes = [(m, p) for m, p in routes() if BIZ.match(p)]
    assert len(biz_routes) >= 90                                          # the inventory is real, not empty
    for m, p in biz_routes:
        url = fill(p, a)
        kw = {"json": {}} if m != "GET" else {}
        no_token = client.request(m, url, **kw)
        assert no_token.status_code == 401, (m, p, no_token.status_code)
        foreign = client.request(m, url, headers=hb, **kw)
        assert foreign.status_code == 404 and foreign.json()["error"]["message"] == "Business not found.", (m, p, foreign.status_code)
        assert "Cov A" not in foreign.text, (m, p)


def test_every_research_route_demands_an_administrator(client, auth_on):
    sme = client.post("/api/v1/auth/register", json={"email": "r@example.com", "password": "orange-river-4271"}).json()["access_token"]
    research = [(m, p) for m, p in routes() if p.startswith("/api/v1/research")]
    assert len(research) >= 40
    for m, p in research:
        kw = {"json": {}} if m != "GET" else {}
        assert client.request(m, fill(p, str(uuid.uuid4())), **kw).status_code == 403, (m, p)
        assert client.request(m, fill(p, str(uuid.uuid4())), headers={"Authorization": f"Bearer {sme}"}, **kw).status_code == 403, (m, p)


def test_the_static_research_token_is_compared_in_constant_time():
    import inspect

    from app.api import deps

    src = inspect.getsource(deps.require_research_access)
    assert "compare_digest" in src and "x_research_token ==" not in src


# ------------------------------------------------------------------ nested objects through a foreign parent
@pytest.fixture()
def nested(client, db_session, auth_on):
    model_registry_service.sync_from_file_registry(db_session)
    a, ha = _owner(client, "na@example.com", "Nested A Secret")
    b, hb = _owner(client, "nb@example.com", "Nested B")
    _seed_rich_business(client, a, headers=ha)
    ids = {"business": a}

    def post(path, body=None):
        r = client.post(f"{P}/{a}{path}", json=body if body is not None else {}, headers=ha)
        assert r.status_code in (200, 201), (path, r.status_code, r.text[:200])
        return r.json()

    ids["goal_id"] = post("/goals", {"text": "Increase revenue by 10% in 2 months"})["id"]
    ids["decision_id"] = post("/decisions/analyze", {"goal_id": ids["goal_id"]})["id"]
    ids["simulation_id"] = post("/digital-twin/simulate", {"actions": [{"type": "marketing_change", "value": 10}]})["id"]
    ids["job_id"] = client.get(f"{P}/{a}/data/uploads", headers=ha).json()[0]["id"]
    rows = client.get(f"{P}/{a}/data/tables/sales?limit=1", headers=ha).json()
    ids["row_id"] = (rows.get("rows") or rows.get("items") or [{}])[0].get("id")
    client.get(f"{P}/{a}/data/profile/sales?record=true", headers=ha)
    hist = client.get(f"{P}/{a}/data/prep-history", headers=ha).json()
    items = hist.get("runs", hist) if isinstance(hist, dict) else hist
    ids["run_id"] = items[0]["id"] if items else None
    types = client.get(f"{P}/{a}/reports/types", headers=ha).json()
    first = (types.get("types") or types)[0]
    ids["report_id"] = post("/reports", {"report_type": first["key"] if isinstance(first, dict) else first})["id"]
    client.post(f"{P}/{a}/alerts/evaluate", headers=ha)
    alerts = client.get(f"{P}/{a}/alerts?status=active", headers=ha).json()
    alerts = alerts.get("alerts", alerts) if isinstance(alerts, dict) else alerts
    ids["alert_id"] = alerts[0]["id"] if alerts else None
    ids["causal_run"] = post("/causal/analyze", {"method": "association", "outcome": "revenue", "treatment": "marketing_spend"})["id"]
    ids["counterfactual_run"] = post("/counterfactual/run", {"mode": "deterministic_scenario", "lever": "price_change_pct", "change_pct": 5})["id"]
    ids["debate_run"] = post("/debate/run", {"question": "Should I raise prices?", "anchor": "latest"})["id"]
    ids["validation_run"] = post("/validation/forecast/run", {"horizons": [7]})["id"]
    mem = client.get(f"{P}/{a}/memory", headers=ha).json()
    ids["memory_id"] = mem[0]["id"] if mem else None
    plan = post("/tracking/expectations", {"metric": "units_sold", "unit": "units", "expected_value": 4242,
                                           "window_start": "2026-01-08", "window_end": "2026-01-14"})
    ids["expectation_id"] = plan["id"]
    ids["observation_id"] = post(f"/tracking/expectations/{plan['id']}/observations",
                                 {"metric": "units_sold", "unit": "units", "status": "observed", "value": 31337})["id"]
    return client, (a, ha), (b, hb), ids


# route template (without the business prefix) -> (method, body, id key used in place of the foreign id, params)
EXERCISED = {
    "/data/jobs/{job_id}": ("GET", None, "job_id"),
    "/data/tables/{table_type}/rows/{row_id}#PATCH": ("PATCH", {"changes": {"quantity": 1}}, "row_id"),
    "/data/tables/{table_type}/rows/{row_id}#DELETE": ("DELETE", None, "row_id"),
    "/goals/{goal_id}": ("GET", None, "goal_id"),
    "/digital-twin/simulations/{simulation_id}": ("GET", None, "simulation_id"),
    "/decisions/{decision_id}": ("GET", None, "decision_id"),
    "/decisions/{decision_id}/explanation": ("GET", None, "decision_id"),
    "/decisions/{decision_id}/trace": ("GET", None, "decision_id"),
    "/decisions/{decision_id}/outcome#POST": ("POST", {"actual_outcome": {"revenue": 1}}, "decision_id"),
    "/decisions/{decision_id}/outcome#GET": ("GET", None, "decision_id"),
    "/data/runs/{run_id}/revert": ("POST", None, "run_id"),
    "/data/prep-history/{run_id}": ("GET", None, "run_id"),
    "/alerts/{alert_id}/status": ("POST", {"status": "read"}, "alert_id"),
    "/reports/{report_id}#GET": ("GET", None, "report_id"),
    "/reports/{report_id}#DELETE": ("DELETE", None, "report_id"),
    "/causal/runs/{run_id}": ("GET", None, "causal_run"),
    "/counterfactual/runs/{run_id}": ("GET", None, "counterfactual_run"),
    "/debate/runs/{run_id}": ("GET", None, "debate_run"),
    "/explain/answer/{memory_id}": ("GET", None, "memory_id"),
    "/validation/runs/{run_id}": ("GET", None, "validation_run"),
    "/tracking/expectations/{expectation_id}#GET": ("GET", None, "expectation_id"),
    "/tracking/expectations/{expectation_id}/observations": ("POST", {"metric": "units_sold", "unit": "units", "status": "observed", "value": 1}, "expectation_id"),
    "/tracking/observations/{observation_id}/correction": ("POST", {"reason": "not mine", "value": 1}, "observation_id"),
    "/tracking/expectations/{expectation_id}/observations/from-data": ("POST", None, "expectation_id"),
    "/tracking/decisions/{decision_id}/response": ("POST", {"response": "accepted"}, "decision_id"),
    "/tracking/decisions/{decision_id}#GET": ("GET", None, "decision_id"),
}
# keyed by a name or table type, not an object id: scoped only by the business in the path, so they are covered by the content test below
NAME_KEYED = {
    "/data/tables/{table_type}", "/data/tables/{table_type}/rows", "/data/profile/{table}", "/data/preview/{table}", "/data/cleaning/{table}",
    "/kpis/{key}/trend", "/kpis/{key}/target", "/alerts/rules/{rule_key}", "/explain/kpi/{key}",
}


def _template(method, path):
    t = BIZ.sub("", path)
    return t, f"{t}#{method}"


def test_every_nested_route_is_exercised_or_deliberately_name_keyed():
    nested = [(m, BIZ.sub("", p)) for m, p in routes() if BIZ.match(p) and re.search(r"\{(?!business_id)[^}]+\}", BIZ.sub("", p))]
    unknown = []
    for m, t in nested:
        if t in NAME_KEYED or t in EXERCISED or f"{t}#{m}" in EXERCISED:
            continue
        unknown.append((m, t))
    assert not unknown, f"nested routes with no cross-tenant test and not marked name-keyed: {unknown}"
    assert sum(1 for _ in nested) >= 37


def test_foreign_object_ids_are_not_found_through_another_owners_business(nested):
    client, (a, ha), (b, hb), ids = nested
    markers = ("Nested A Secret", "4242", "31337", a)
    checked = 0
    for key, (method, body, idkey) in EXERCISED.items():
        obj = ids.get(idkey)
        if obj is None:
            continue                                                  # no such object could be produced for this business (e.g. no alert raised)
        tpl = key.split("#")[0]
        url = f"{P}/{b}" + re.sub(r"\{table_type\}", "sales", re.sub(r"\{(row_id|job_id|goal_id|simulation_id|decision_id|run_id|alert_id|report_id|memory_id|expectation_id|observation_id)\}", obj, tpl))
        kw = {"json": body} if body is not None else {}
        r = client.request(method, url, headers=hb, **kw)
        assert r.status_code == 404, (key, r.status_code, r.text[:160])
        for m in markers:
            assert str(m) not in r.text, (key, m)
        checked += 1
    assert checked >= 20, checked                                      # most families were really exercised
    # nothing of A changed
    assert client.get(f"{P}/{a}/tracking/expectations/{ids['expectation_id']}", headers=ha).json()["observations"][0]["value"] == 31337.0
    assert client.get(f"{P}/{a}/goals/{ids['goal_id']}", headers=ha).status_code == 200


def test_name_keyed_routes_show_another_owner_none_of_the_data(nested):
    client, (a, ha), (b, hb), ids = nested
    mine = client.get(f"{P}/{a}/data/tables/sales?limit=5", headers=ha).json()
    theirs = client.get(f"{P}/{b}/data/tables/sales?limit=5", headers=hb).json()
    assert (mine.get("total") or mine.get("total_rows") or 1) > 0
    assert (theirs.get("total") or theirs.get("total_rows") or 0) == 0
    assert client.get(f"{P}/{b}/kpis/revenue/trend", headers=hb).json() != client.get(f"{P}/{a}/kpis/revenue/trend", headers=ha).json()
    assert client.delete(f"{P}/{b}/data/tables/sales", headers=hb).status_code in (200, 204)       # clearing B's table is scoped to B
    after = client.get(f"{P}/{a}/data/tables/sales?limit=5", headers=ha).json()
    assert (after.get("total") or after.get("total_rows")) == (mine.get("total") or mine.get("total_rows"))
