import sys
import shutil

print("Python executable:", sys.executable)
print("Python version:", sys.version)

packages = [
    "sklearn", "xgboost", "lightgbm", "catboost", "scipy", "statsmodels",
    "pandas", "numpy", "matplotlib", "seaborn", "fastapi", "sqlalchemy",
    "pydantic", "pytest", "networkx"
]

print("\n--- Package Verification ---", flush=True)
for pkg in packages:
    try:
        mod = __import__(pkg)
        ver = getattr(mod, "__version__", "unknown")
        print(f"  {pkg:15s}: OK (version {ver})", flush=True)
    except ImportError as e:
        print(f"  {pkg:15s}: NOT INSTALLED ({e})", flush=True)
