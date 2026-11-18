import sys
from pathlib import Path

# Ensure backend and root are on sys.path
backend_dir = Path(__file__).resolve().parent.parent
root_dir = backend_dir.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from app.db.session import SessionLocal
from app.services.model_registry_service import sync_from_file_registry
from app.models.ml_model import MLModel

db = SessionLocal()
try:
    synced = sync_from_file_registry(db)
    print(f"Synced {len(synced)} models.")
    for m in db.query(MLModel).all():
        print(f"Model: {m.model_name} v{m.version} status={m.status} metrics={list(m.metrics_json.keys()) if m.metrics_json else None}")
finally:
    db.close()
