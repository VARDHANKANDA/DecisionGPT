import urllib.request
import urllib.error

routes = [
    "/",
    "/login",
    "/dashboard",
    "/admin",
    "/research",
    "/settings",
]

print("=== VERIFYING FRONTEND ROUTES ===")
for r in routes:
    url = f"http://localhost:3000{r}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req) as resp:
            content = resp.read().decode("utf-8", errors="ignore")
            title = ""
            if "<title>" in content:
                title = content.split("<title>")[1].split("</title>")[0]
            print(f"Frontend route {r:15}: [{resp.status}] Title: '{title.strip()}' (Bytes: {len(content)})")
    except urllib.error.HTTPError as e:
        print(f"Frontend route {r:15}: HTTP {e.code} - {e.reason}")
    except Exception as e:
        print(f"Frontend route {r:15}: Error {e}")

