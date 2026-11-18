from pathlib import Path

root = Path("d:/Capstone Project")

keywords = [
    "market_benchmarks",
    "MarketBenchmark",
    "prediction_evaluations",
    "PredictionEvaluation",
    "seed_benchmarks",
    "evaluation_console_service",
    "ml_benchmark_service",
    "research_overview_service",
]

for pyfile in root.rglob("*.py"):
    if any(x in pyfile.parts for x in ["node_modules", ".venv", ".git"]):
        continue
    try:
        content = pyfile.read_text(encoding="utf-8", errors="ignore")
        for kw in keywords:
            if kw in content:
                print(f"[{kw}] in {pyfile.relative_to(root)}")
    except Exception:
        pass

