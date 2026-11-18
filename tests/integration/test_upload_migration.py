"""Migration 0016 (identity and storage key of the original upload) on a disposable SQLite file: existing jobs survive with empty values and the
downgrade is clean. The same migration runs on PostgreSQL in tests/postgres (alembic check equals models)."""
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _alembic(db: Path, *args: str):
    env = {**os.environ, "DATABASE_URL": f"sqlite:///{db.as_posix()}", "PYTHONPATH": f"{ROOT / 'backend'}{os.pathsep}{ROOT}", "MIGRATION_DATABASE_URL": ""}
    r = subprocess.run([sys.executable, "-m", "alembic", *args], cwd=ROOT / "backend", env=env, capture_output=True, text=True, timeout=600)
    assert r.returncode == 0, r.stderr[-800:]


def test_0016_adds_nullable_columns_keeps_existing_jobs_and_downgrades_cleanly(tmp_path):
    db = tmp_path / "m.db"
    _alembic(db, "upgrade", "0015")
    con = sqlite3.connect(db)
    con.execute("INSERT INTO businesses (id, created_at, updated_at, name, industry, business_type, business_size, country, currency) "
                "VALUES ('b1','2026-01-01','2026-01-01','B','retail','D2C','small','IN','INR')")
    con.execute("INSERT INTO data_ingestion_jobs (id, created_at, updated_at, business_id, filename, status, detected_types_json, mapping_json, summary_json) "
                "VALUES ('j1','2026-01-01','2026-01-01','b1','old.csv','completed','[]','{}','{}')")
    con.commit()
    con.close()
    _alembic(db, "upgrade", "0016")
    con = sqlite3.connect(db)
    cols = [r[1] for r in con.execute("PRAGMA table_info(data_ingestion_jobs)")]
    assert {"file_sha256", "file_size", "storage_key"} <= set(cols)
    assert con.execute("SELECT file_sha256, file_size, storage_key, status FROM data_ingestion_jobs WHERE id='j1'").fetchone() == (None, None, None, "completed")
    assert any(r[1] == "ix_data_ingestion_jobs_file_sha256" for r in con.execute("PRAGMA index_list(data_ingestion_jobs)"))
    con.close()
    _alembic(db, "downgrade", "0015")
    con = sqlite3.connect(db)
    assert not ({"file_sha256", "file_size", "storage_key"} & {r[1] for r in con.execute("PRAGMA table_info(data_ingestion_jobs)")})
    assert con.execute("SELECT filename FROM data_ingestion_jobs").fetchone() == ("old.csv",)
    con.close()
    _alembic(db, "upgrade", "head")
