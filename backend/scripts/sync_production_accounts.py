"""CLI utility to safely and idempotently synchronize the 3 institutional demo user accounts.

Works against any target PostgreSQL (e.g. Neon) or SQLite database configured in DATABASE_URL.
Preserves original User IDs, roles, and Argon2id password hashes without exposing secrets.

Usage:
    python backend/scripts/sync_production_accounts.py
    DATABASE_URL="postgresql+psycopg://..." python backend/scripts/sync_production_accounts.py
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Add backend and root to sys.path
backend_dir = Path(__file__).resolve().parents[1]
root_dir = backend_dir.parent
sys.path.insert(0, str(backend_dir))
sys.path.insert(0, str(root_dir))

from app.db.session import Base, SessionLocal, engine
import app.models  # noqa: F401
from app.services.account_sync_service import (
    CANONICAL_DEMO_ACCOUNTS,
    sync_production_demo_accounts,
    verify_demo_account_credentials,
)

import os

DEMO_PASSWORDS = {
    "admin@decisiongpt.local": os.environ.get("DEMO_ADMIN_PASSWORD", "AdminPass@2026!"),
    "researcher@decisiongpt.local": os.environ.get("DEMO_RESEARCHER_PASSWORD", "ResearchPass@2026!"),
    "demo@decisiongpt.local": os.environ.get("DEMO_SME_PASSWORD", "DemoUser@2026!"),
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Synchronize DecisionGPT canonical demo accounts.")
    parser.add_argument("--verify-only", action="store_true", help="Only verify existing accounts without inserting.")
    args = parser.parse_args()

    print("=" * 80)
    print("DecisionGPT — Production Demo Accounts Synchronization")
    print("=" * 80)

    db = SessionLocal()
    try:
        if not args.verify_only:
            print("1. Running idempotent synchronization...")
            results = sync_production_demo_accounts(db)
        else:
            results = {}

        print("2. Verifying account credentials...")
        verifications = verify_demo_account_credentials(db, DEMO_PASSWORDS)

        print("\n" + "=" * 80)
        print(f"{'Email':<32} {'Role':<12} {'Action':<16} {'Password':<10} {'User ID'}")
        print("-" * 80)

        all_ok = True
        for email, expected in CANONICAL_DEMO_ACCOUNTS.items():
            sync_info = results.get(email, {})
            action = sync_info.get("action", "verified")
            user_id = sync_info.get("user_id", expected["id"])
            role = expected["role"]
            v_status = "PASS" if verifications.get(email) else "FAIL"
            if v_status != "PASS":
                all_ok = False

            print(f"{email:<32} {role:<12} {action:<16} {v_status:<10} {user_id}")

        print("=" * 80)
        if all_ok:
            print("SUCCESS: All three canonical accounts are present and verified.")
            return 0
        else:
            print("WARNING: One or more accounts failed password verification.")
            return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
