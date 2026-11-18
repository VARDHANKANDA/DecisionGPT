import sys
from pathlib import Path
import json
import urllib.request
import urllib.error

API_URL = "http://127.0.0.1:8000/api/v1"

def req(method, endpoint, body=None, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    r = urllib.request.Request(f"{API_URL}{endpoint}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(r) as resp:
            content = resp.read().decode("utf-8")
            return resp.status, json.loads(content) if content else {}
    except urllib.error.HTTPError as e:
        err_content = e.read().decode("utf-8")
        try:
            return e.code, json.loads(err_content)
        except Exception:
            return e.code, err_content

def main():
    print("=== LIVE FULL-STACK ENDPOINT VERIFICATION ===")
    
    # 1. Health
    status, health = req("GET", "/health")
    print(f"1. Health Check: [{status}] {health}")
    assert status == 200, f"Health check failed: {health}"

    # 2. Authentication for all 3 roles
    roles = [
        ("Admin", "admin@decisiongpt.local", "AdminPass@2026!"),
        ("SME User", "demo@decisiongpt.local", "DemoUser@2026!"),
        ("Researcher", "researcher@decisiongpt.local", "ResearchPass@2026!"),
    ]
    tokens = {}
    for name, email, pwd in roles:
        s, data = req("POST", "/auth/login", {"email": email, "password": pwd})
        print(f"2. Auth {name}: [{s}] access_token present: {'access_token' in data}")
        assert s == 200, f"Auth failed for {name}: {data}"
        tokens[name] = data["access_token"]

    # 3. SME Business Profile & KPIs
    sme_token = tokens["SME User"]
    s, businesses = req("GET", "/businesses/mine", token=sme_token)
    print(f"3. SME Businesses: [{s}] Count: {len(businesses)}")
    assert s == 200 and len(businesses) > 0, "No business found for SME"
    biz = businesses[0]
    biz_id = biz["id"]
    print(f"   Using Business: '{biz['name']}' (ID: {biz_id})")

    # KPIs
    s, kpis = req("GET", f"/businesses/{biz_id}/analytics/kpis", token=sme_token)
    print(f"4. Analytics KPIs: [{s}] Revenue: ₹{kpis.get('revenue', 0):,.2f}, Orders: {kpis.get('orders', 0)}")
    assert s == 200

    # Churn Analytics
    s, churn = req("POST", f"/businesses/{biz_id}/analytics/churn", token=sme_token)
    print(f"5. Churn Analysis: [{s}] Model: {churn.get('model_name') if isinstance(churn, dict) else churn}")
    assert s == 200, f"Churn failed: {churn}"

    # Sales Forecasting
    s, forecast = req("POST", f"/businesses/{biz_id}/analytics/forecast?horizon_days=14", token=sme_token)
    print(f"6. Sales Forecast: [{s}] Model: {forecast.get('model_name') if isinstance(forecast, dict) else forecast}")
    assert s == 200, f"Forecast failed: {forecast}"

    # Business Assistant Chat
    chat_body = {"message": "What is our current monthly revenue and customer count?"}
    s, chat_res = req("POST", f"/businesses/{biz_id}/chat", body=chat_body, token=sme_token)
    print(f"7. Business Assistant: [{s}] Intent: {chat_res.get('intent', 'N/A') if isinstance(chat_res, dict) else 'N/A'}")
    assert s == 200, f"Assistant failed: {chat_res}"

    # Individual Agent Consult
    agent_body = {"task": "Review marketing ROI and CAC trends"}
    s, agent_res = req("POST", f"/businesses/{biz_id}/agents/marketing-advisor/consult", body=agent_body, token=sme_token)
    print(f"8. Agent Consult: [{s}] Result keys: {list(agent_res.keys()) if isinstance(agent_res, dict) else agent_res}")
    assert s == 200, f"Agent consult failed: {agent_res}"

    # Multi-Agent Debate
    debate_body = {"question": "Should we increase paid marketing spend by 20% next quarter?", "mode": "rule_based"}
    s, debate_res = req("POST", f"/businesses/{biz_id}/debate/run", body=debate_body, token=sme_token)
    print(f"9. Multi-Agent Debate: [{s}] Run ID: {debate_res.get('run_id') if isinstance(debate_res, dict) else 'N/A'}")
    assert s == 200, f"Debate run failed: {debate_res}"

    # Decisions list
    s, decisions = req("GET", f"/businesses/{biz_id}/decisions", token=sme_token)
    print(f"10. Decisions List: [{s}] Count: {len(decisions) if isinstance(decisions, list) else 'N/A'}")
    assert s == 200, f"Decisions list failed: {decisions}"

    # 11. Researcher Console
    res_token = tokens["Researcher"]
    s, res_overview = req("GET", "/research/overview", token=res_token)
    print(f"11. Research Console: [{s}] Status: {res_overview.get('status') if isinstance(res_overview, dict) else 'N/A'}")
    assert s == 200, f"Research overview failed: {res_overview}"

    # 12. Admin Dashboard Monitoring & Users
    admin_token = tokens["Admin"]
    s, admin_users = req("GET", "/admin/users", token=admin_token)
    print(f"12. Admin Users: [{s}] Total registered users: {len(admin_users) if isinstance(admin_users, list) else 'N/A'}")
    assert s == 200, f"Admin users failed: {admin_users}"

    s, admin_mon = req("GET", "/admin/monitoring", token=admin_token)
    print(f"    Admin Monitoring: [{s}] Status: {admin_mon.get('status') if isinstance(admin_mon, dict) else 'N/A'}, Roles: {admin_mon.get('users_by_role')}")
    assert s == 200, f"Admin monitoring failed: {admin_mon}"

    print("\nALL 12 CORE FUNCTIONAL TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    main()
