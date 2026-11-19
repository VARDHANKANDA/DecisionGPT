import sys
from pathlib import Path

# Add backend to sys.path
backend_path = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_path))

from app.db.session import Base
import app.models  # noqa: F401

print(f"Total tables in metadata: {len(Base.metadata.sorted_tables)}")
for idx, t in enumerate(Base.metadata.sorted_tables, 1):
    fks = [f"{fk.parent.name} -> {fk.column.table.name}" for fk in t.foreign_keys]
    fk_str = f"({', '.join(fks)})" if fks else "(no FKs)"
    print(f"{idx:2d}. {t.name:32s} {fk_str}")

