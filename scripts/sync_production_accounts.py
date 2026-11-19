"""Root wrapper to run sync_production_accounts.py from the project root.

Usage:
    python scripts/sync_production_accounts.py
"""
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
backend_dir = root / "backend"
backend_sync = backend_dir / "scripts" / "sync_production_accounts.py"

if __name__ == "__main__":
    venv_py = backend_dir / ".venv" / "Scripts" / "python.exe"
    py = str(venv_py) if venv_py.exists() else sys.executable
    ret = subprocess.run([py, str(backend_sync), *sys.argv[1:]], cwd=str(backend_dir))
    sys.exit(ret.returncode)
