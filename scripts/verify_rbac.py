import json
import urllib.error
import urllib.request


def test_login(email, password):
    req = urllib.request.Request(
        "http://127.0.0.1:8000/api/v1/auth/login",
        data=json.dumps({"email": email, "password": password}).encode(),
        headers={"Content-Type": "application/json"},
    )
    res = urllib.request.urlopen(req)
    data = json.loads(res.read())
    return data["access_token"], data["user"]


def test_get(url, token):
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        res = urllib.request.urlopen(req)
        return res.status, json.loads(res.read())
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


print("=" * 60)
print("TESTING DECISIONGPT DEMO LOGINS & RBAC PERMISSIONS")
print("=" * 60)

# 1. Admin
tok_a, u_a = test_login("admin@decisiongpt.local", "AdminPass@2026!")
s_a_adm, _ = test_get("http://127.0.0.1:8000/api/v1/admin/monitoring", tok_a)
s_a_res, _ = test_get("http://127.0.0.1:8000/api/v1/research/models", tok_a)
print(f"ADMIN USER:")
print(f"  Role: {u_a['role']} | Email: {u_a['email']}")
print(f"  GET /api/v1/admin/monitoring -> HTTP {s_a_adm} (Success)")
print(f"  GET /api/v1/research/models   -> HTTP {s_a_res} (Success)")
assert s_a_adm == 200, f"Expected 200 for admin on monitoring, got {s_a_adm}"
assert s_a_res == 200, f"Expected 200 for admin on research, got {s_a_res}"

# 2. Researcher
tok_r, u_r = test_login("researcher@decisiongpt.local", "ResearchPass@2026!")
s_r_adm, _ = test_get("http://127.0.0.1:8000/api/v1/admin/monitoring", tok_r)
s_r_res, _ = test_get("http://127.0.0.1:8000/api/v1/research/models", tok_r)
print(f"\nRESEARCHER USER:")
print(f"  Role: {u_r['role']} | Email: {u_r['email']}")
print(f"  GET /api/v1/admin/monitoring -> HTTP {s_r_adm} (Correctly Blocked: 403 Forbidden)")
print(f"  GET /api/v1/research/models   -> HTTP {s_r_res} (Success: 200 OK)")
assert s_r_adm == 403, f"Expected 403 for researcher on admin, got {s_r_adm}"
assert s_r_res == 200, f"Expected 200 for researcher on research, got {s_r_res}"

# 3. SME
tok_s, u_s = test_login("demo@decisiongpt.local", "DemoUser@2026!")
s_s_adm, _ = test_get("http://127.0.0.1:8000/api/v1/admin/monitoring", tok_s)
s_s_res, _ = test_get("http://127.0.0.1:8000/api/v1/research/models", tok_s)
s_s_biz, _ = test_get("http://127.0.0.1:8000/api/v1/businesses/mine", tok_s)
print(f"\nSME BUSINESS USER:")
print(f"  Role: {u_s['role']} | Email: {u_s['email']}")
print(f"  GET /api/v1/admin/monitoring    -> HTTP {s_s_adm} (Correctly Blocked: 403 Forbidden)")
print(f"  GET /api/v1/research/models      -> HTTP {s_s_res} (Correctly Blocked: 403 Forbidden)")
print(f"  GET /api/v1/businesses/mine      -> HTTP {s_s_biz} (Success: 200 OK)")
assert s_s_adm == 403, f"Expected 403 for SME on admin, got {s_s_adm}"
assert s_s_res == 403, f"Expected 403 for SME on research, got {s_s_res}"
assert s_s_biz == 200, f"Expected 200 for SME on business, got {s_s_biz}"

print("\n" + "=" * 60)
print("ALL 3 DEMO ROLES & ACCESS BOUNDARIES 100% VERIFIED!")
print("=" * 60)
