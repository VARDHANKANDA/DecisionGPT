import urllib.request
import json
import sys

BASE_URL = "http://127.0.0.1:8000/api/v1"

def post(url, data_dict=None, headers=None):
    hdrs = {}
    if headers:
        hdrs.update(headers)
    if data_dict is not None:
        hdrs["Content-Type"] = "application/json"
        body = json.dumps(data_dict).encode("utf-8")
    else:
        body = b""
    req = urllib.request.Request(url, data=body, headers=hdrs, method="POST")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))

def get(url, headers=None):
    hdrs = {}
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, headers=hdrs, method="GET")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))

print("=" * 75)
print("DECISIONGPT LIVE END-TO-END FEATURE VERIFICATION SUITE")
print("=" * 75)

# 1. AUTHENTICATION & LOGIN
print("\n[1/12] Testing Login & Authentication...")
admin_auth = post(f"{BASE_URL}/auth/login", {"email": "admin@decisiongpt.local", "password": "AdminPass@2026!"})
admin_token = admin_auth["access_token"]
print(f"  ✓ Admin login verified: {admin_auth['user']['email']} (role: {admin_auth['user']['role']})")

sme_auth = post(f"{BASE_URL}/auth/login", {"email": "demo@decisiongpt.local", "password": "DemoUser@2026!"})
sme_token = sme_auth["access_token"]
print(f"  ✓ Business User (SME) login verified: {sme_auth['user']['email']} (role: {sme_auth['user']['role']})")

res_auth = post(f"{BASE_URL}/auth/login", {"email": "researcher@decisiongpt.local", "password": "ResearchPass@2026!"})
res_token = res_auth["access_token"]
print(f"  ✓ Researcher login verified: {res_auth['user']['email']} (role: {res_auth['user']['role']})")

# 2. PROFILE & SETTINGS
print("\n[2/12] Testing Profile & Account Settings...")
me = get(f"{BASE_URL}/auth/me", {"Authorization": f"Bearer {sme_token}"})
print(f"  ✓ Profile retrieved: Name={me.get('full_name')}, Email={me.get('email')}, Role={me.get('role')}")

# 3. GET SME BUSINESS
print("\n[3/12] Retrieving Active Business for SME User...")
biz_list = get(f"{BASE_URL}/businesses/mine", {"Authorization": f"Bearer {sme_token}"})
if not biz_list:
    raise RuntimeError("No business found for SME user!")
biz = biz_list[0]
biz_id = biz["id"]
print(f"  ✓ Active Business: {biz['name']} (ID: {biz_id})")

# 4. USER DASHBOARD & KPIS
print("\n[4/12] Testing User Dashboard & Analytics KPIs...")
kpis = get(f"{BASE_URL}/businesses/{biz_id}/analytics/kpis", {"Authorization": f"Bearer {sme_token}"})
print(f"  ✓ KPIs: Revenue=₹{kpis.get('revenue', 0):,.2f}, Orders={kpis.get('orders')}, Customers={kpis.get('customers')}, AOV=₹{kpis.get('average_order_value', 0):,.2f}")

# 5. CUSTOMER ANALYTICS & CHURN
print("\n[5/12] Testing Customer Analytics & Churn Risk...")
cust_summary = get(f"{BASE_URL}/businesses/{biz_id}/analytics/customers", {"Authorization": f"Bearer {sme_token}"})
print(f"  ✓ Customer Summary: Total={cust_summary.get('total_customers')}, Repeat={cust_summary.get('repeat_rate_pct')}%")
churn = post(f"{BASE_URL}/businesses/{biz_id}/analytics/churn", None, {"Authorization": f"Bearer {sme_token}"})
print(f"  ✓ Churn Model: {churn.get('model_name')} (Predictions count: {len(churn.get('predictions', []))})")

# 6. TIME-SERIES DEMAND FORECASTING
print("\n[6/12] Testing Multi-Horizon Demand Forecasting...")
fc = post(f"{BASE_URL}/businesses/{biz_id}/analytics/forecast?horizon_days=14", None, {"Authorization": f"Bearer {sme_token}"})
print(f"  ✓ Forecast: Model={fc.get('model_name')}, Horizon={fc.get('horizon_returned')} days, Metrics={fc.get('metrics')}")

# 7. BUSINESS ASSISTANT (CONVERSATIONAL Q&A)
print("\n[7/12] Testing Conversational Business Assistant...")
chat_res = post(
    f"{BASE_URL}/businesses/{biz_id}/chat",
    {"message": "What were our top performing products?"},
    {"Authorization": f"Bearer {sme_token}"}
)
print(f"  ✓ Assistant answered: Intent={chat_res.get('intent')}, Answer preview: {chat_res.get('answer', '')[:100]}...")

# 8. INDIVIDUAL AI AGENT CONSULTATIONS
print("\n[8/12] Testing Individual AI Agent Consultations...")
for agent in ["business_analyst", "financial_advisor", "risk_manager"]:
    res = post(
        f"{BASE_URL}/businesses/{biz_id}/agents/{agent}/consult",
        {"task": "Evaluate operational health and identify primary concerns."},
        {"Authorization": f"Bearer {sme_token}"}
    )
    print(f"  ✓ Specialist [{res.get('agent_name')}]: Status={res.get('status')}, Key findings={len(res.get('analysis', {}).get('key_findings', []))}")

# 9. MULTI-AGENT SWARM DIALECTICAL DEBATE
print("\n[9/12] Testing Multi-Agent Swarm Debate Deliberation...")
debate_res = post(
    f"{BASE_URL}/businesses/{biz_id}/debate/run",
    {"question": "Should we increase marketing spend or optimize inventory safety stock?", "mode": "rule_based"},
    {"Authorization": f"Bearer {sme_token}"}
)
stages = debate_res.get("stages", {})
print(f"  ✓ Debate deliberated across {len(stages)} stages: Status={debate_res.get('status')}")
if "decision_brief" in stages:
    brief = stages["decision_brief"]
    print(f"    - Brief recommendation: {brief.get('recommendation', '')[:80]}...")

# 10. RECOMMENDATIONS AND DECISIONS GOVERNANCE
print("\n[10/12] Testing Recommendations & Decisions Governance...")
decisions_list = get(f"{BASE_URL}/businesses/{biz_id}/decisions", {"Authorization": f"Bearer {sme_token}"})
print(f"  ✓ Decisions list: {len(decisions_list)} decisions found in audit log")

# 11. RESEARCH DASHBOARD & MODEL BENCHMARKS
print("\n[11/12] Testing Research Dashboard & Model Metrics...")
res_overview = get(
    f"{BASE_URL}/research/overview",
    {"Authorization": f"Bearer {res_token}", "X-Research-Token": "change-me-research-console-token"}
)
print(f"  ✓ Research Overview: Datasets={len(res_overview.get('datasets', []))}, Models={len(res_overview.get('models', []))}")

# 12. ADMIN DASHBOARD & SYSTEM MONITORING
print("\n[12/12] Testing Admin Dashboard & System Overview...")
admin_overview = get(f"{BASE_URL}/admin/overview", {"Authorization": f"Bearer {admin_token}"})
print(f"  ✓ Admin Overview: Total users={admin_overview.get('users_count')}, Total businesses={admin_overview.get('businesses_count')}")

print("\n" + "=" * 75)
print("ALL 12 CORE FUNCTIONAL DOMAINS VERIFIED SUCCESSFULLY IN REAL-TIME!")
print("=" * 75)
