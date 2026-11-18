"""Local-dev-only helper: create all tables in a SQLite file so the API can
be run and clicked through without Docker/Postgres. Production always uses
Alembic migrations against Postgres (see docs/DEPLOYMENT.md) — this script
is not part of that path.

Usage:
    DATABASE_URL=sqlite:///./dev.db python scripts/dev_bootstrap_sqlite.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine  # noqa: E402

import app.models  # noqa: F401,E402
from app.core.config import get_settings  # noqa: E402
from app.db.session import Base  # noqa: E402


def main() -> None:
    settings = get_settings()
    if not settings.database_url.startswith("sqlite"):
        raise SystemExit(f"Refusing to run: DATABASE_URL is not sqlite ({settings.database_url}).")
    engine = create_engine(settings.database_url)
    Base.metadata.create_all(engine)
    print(f"Created {len(Base.metadata.tables)} tables at {settings.database_url}")


if __name__ == "__main__":
    main()
