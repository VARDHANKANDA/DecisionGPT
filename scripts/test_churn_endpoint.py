import urllib.request
import urllib.error
import json

BASE_URL = "http://127.0.0.1:8000/api/v1"

req = urllib.request.Request(f"{BASE_URL}/auth/login", data=json.dumps({"email": "demo@decisiongpt.local", "password": "DemoUser@2026!"}).encode(), headers={"Content-Type": "application/json"}, method="POST")
with urllib.request.urlopen(req) as r:
    token = json.loads(r.read())["access_token"]

req = urllib.request.Request(f"{BASE_URL}/businesses/mine", headers={"Authorization": f"Bearer {token}"}, method="GET")
with urllib.request.urlopen(req) as r:
    biz_id = json.loads(r.read())[0]["id"]

req = urllib.request.Request(f"{BASE_URL}/businesses/{biz_id}/analytics/churn", data=b"", headers={"Authorization": f"Bearer {token}"}, method="POST")
try:
    with urllib.request.urlopen(req) as r:
        print("Success:", r.read().decode())
except urllib.error.HTTPError as e:
    print("Error code:", e.code)
    print("Error body:", e.read().decode())

