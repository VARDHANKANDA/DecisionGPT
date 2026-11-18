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
    print("=== TESTING COMPLETE RESEARCH CONSOLE API LIVE ===")
    
    # Login as researcher
    s, auth_data = req("POST", "/auth/login", {"email": "researcher@decisiongpt.local", "password": "ResearchPass@2026!"})
    print(f"Login as Researcher: [{s}]")
    assert s == 200, f"Login failed: {auth_data}"
    token = auth_data["access_token"]
    
    endpoints = [
        ("Overview", "/research/overview"),
        ("Summary", "/research/summary"),
        ("Models", "/research/models"),
        ("Datasets", "/research/datasets"),
        ("Experiments", "/research/experiments"),
        ("Training Runs", "/research/training/runs"),
        ("Evaluation Overview", "/research/evaluation"),
        ("Model Performance", "/research/model-performance"),
        ("ML Benchmark", "/research/ml-benchmark"),
        ("Model Comparison", "/research/model-comparison"),
        ("Agent Evaluation", "/research/agent-evaluation"),
        ("Architecture Evaluation", "/research/architecture-evaluation"),
        ("Causal Evaluation", "/research/causal-evaluation"),
        ("Causal Assessment", "/research/causal-assessment"),
        ("Digital Twin Evaluation", "/research/digital-twin-evaluation"),
        ("Risk Assessment", "/research/risk-assessment"),
        ("LLM Evaluation", "/research/llm-evaluation"),
        ("Paper Results", "/research/paper-results"),
        ("Validation", "/research/validation"),
    ]
    
    passed = 0
    failed = 0
    for name, ep in endpoints:
        s, data = req("GET", ep, token=token)
        summary = ""
        if isinstance(data, dict):
            summary = f"keys: {list(data.keys())[:5]}"
            if "runs" in data:
                summary += f", runs count: {len(data['runs'])}"
            if "total" in data:
                summary += f", total: {data['total']}"
            if "datasets" in data:
                summary += f", datasets: {len(data['datasets'])}"
            if "models" in data:
                summary += f", models: {len(data['models'])}"
        elif isinstance(data, list):
            summary = f"list items: {len(data)}"
            
        print(f"[{s}] {name:25} ({ep:35}): {summary}")
        if s == 200:
            passed += 1
        else:
            failed += 1
            print(f"    ERROR DETAILS: {data}")
            
    print(f"\nRESULTS: {passed} PASSED, {failed} FAILED out of {len(endpoints)} research endpoints.")

if __name__ == "__main__":
    main()
