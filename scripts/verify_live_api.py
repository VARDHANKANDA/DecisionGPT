import urllib.request
import json

accounts = [
    ("admin@decisiongpt.local", "AdminPass@2026!"),
    ("demo@decisiongpt.local", "DemoUser@2026!"),
    ("researcher@decisiongpt.local", "ResearchPass@2026!")
]

print("=== VERIFYING AUTHENTICATION & LOGIN FOR ALL 3 DEMO ROLES ===")
tokens = {}
for email, pwd in accounts:
    data = json.dumps({"email": email, "password": pwd}).encode("utf-8")
    req = urllib.request.Request(
        "http://127.0.0.1:8000/api/v1/auth/login",
        data=data,
        headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            role = body["user"]["role"]
            email_out = body["user"]["email"]
            token = body["access_token"]
            tokens[role] = token
            print(f"  [OK] Role: {role:<12} | Email: {email_out:<30} | Token len: {len(token)}")
    except Exception as e:
        print(f"  [FAIL] Email: {email} | Error: {e}")

print("\n=== VERIFYING PROTECTED ENDPOINTS WITH DEMO BEARER TOKENS ===")
# 1. /auth/me for admin
if "admin" in tokens:
    req = urllib.request.Request(
        "http://127.0.0.1:8000/api/v1/auth/me",
        headers={"Authorization": f"Bearer {tokens['admin']}"}
    )
    with urllib.request.urlopen(req) as resp:
        me_admin = json.loads(resp.read().decode("utf-8"))
        print(f"  [OK] /auth/me (admin): verified as {me_admin['role']} ({me_admin['email']})")

# 2. /businesses/mine for sme demo user
if "sme" in tokens:
    req = urllib.request.Request(
        "http://127.0.0.1:8000/api/v1/businesses/mine",
        headers={"Authorization": f"Bearer {tokens['sme']}"}
    )
    with urllib.request.urlopen(req) as resp:
        businesses = json.loads(resp.read().decode("utf-8"))
        print(f"  [OK] /businesses/mine (sme): found {len(businesses)} business(es)")
        for b in businesses:
            print(f"       - Name: {b['name']} | ID: {b['id']} | Currency: {b.get('currency', 'INR')}")

# 3. /research/overview for researcher
if "researcher" in tokens:
    req = urllib.request.Request(
        "http://127.0.0.1:8000/api/v1/research/overview",
        headers={"Authorization": f"Bearer {tokens['researcher']}", "X-Research-Token": "change-me-research-console-token"}
    )
    try:
        with urllib.request.urlopen(req) as resp:
            overview = json.loads(resp.read().decode("utf-8"))
            print(f"  [OK] /research/overview (researcher): status={overview.get('status', 'ok')}")
    except Exception as e:
        print(f"  [NOTE] /research/overview: {e}")
