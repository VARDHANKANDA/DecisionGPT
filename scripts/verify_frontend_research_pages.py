import urllib.request
import urllib.error

pages = [
    "/research",
    "/research/ml-benchmark",
    "/research/evaluation",
    "/research/models",
    "/research/datasets",
    "/research/experiments",
    "/research/agent-evaluation",
    "/research/digital-twin-evaluation",
    "/research/causal-evaluation",
    "/research/ablation",
    "/research/model-comparison",
    "/research/model-performance",
    "/research/llm-evaluation",
    "/research/training",
    "/research/validation",
    "/research/risk-calibration",
    "/research/export",
    "/research/limitations",
]

print("=== VERIFYING FRONTEND RESEARCH PAGES ON LOCALHOST:3000 ===")
for p in pages:
    url = f"http://localhost:3000{p}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req) as resp:
            content = resp.read()
            print(f"[{resp.status}] {p:35} Length: {len(content):6} bytes")
    except urllib.error.HTTPError as e:
        print(f"[{e.code}] {p:35} ERROR: {e.reason}")
    except Exception as e:
        print(f"[ERR] {p:35} ERROR: {e}")

