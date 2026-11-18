"""Wrapper to run backend seed script from the project root.

Usage:
    python scripts/seed_demo_accounts.py
"""
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
backend_dir = root / "backend"
backend_seed = backend_dir / "scripts" / "seed_demo_accounts.py"

if __name__ == "__main__":
    venv_py = backend_dir / ".venv" / "Scripts" / "python.exe"
    py = str(venv_py) if venv_py.exists() else sys.executable
    ret = subprocess.run([py, str(backend_seed)], cwd=str(backend_dir))
    sys.exit(ret.returncode)
