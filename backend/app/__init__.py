import sys
from pathlib import Path

_backend_dir = Path(__file__).resolve().parent.parent
_root_dir = _backend_dir.parent
for p in (_backend_dir, _root_dir):
    sp = str(p)
    if sp not in sys.path:
        sys.path.insert(0, sp)

