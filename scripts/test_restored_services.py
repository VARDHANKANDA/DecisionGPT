import sys
from pathlib import Path

backend_dir = Path("d:/Capstone Project/backend")
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))
root_dir = backend_dir.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from app.services import ml_benchmark_service, dataset_registry_service

print("=== TESTING ML BENCHMARK SERVICE ===")
res = ml_benchmark_service.latest_results()
print("Available:", res.get("available"))
print("Number of benchmark runs found:", len(res.get("runs", [])))
for r in res.get("runs", []):
    print(f"  Task: {r.get('task')} | Title: {r.get('title')}")

print("\n=== TESTING DATASET REGISTRY SERVICE ===")
datasets = dataset_registry_service.list_datasets()
print(f"Platform datasets found: {len(datasets)}")
for d in datasets:
    print(f"  Dataset: {d.domain:12} | {d.name:35} | {d.row_count} rows")

external = dataset_registry_service.list_external_datasets()
print(f"External catalog entries: {len(external)}")
for e in external:
    print(f"  External: {e.dataset_id:30} | {e.name:35} | {e.geography}")
