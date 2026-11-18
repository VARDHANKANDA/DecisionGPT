"""Operator account recovery - reset a password and/or deactivate or reactivate an account. Every session the account holds is ended.

    # from the backend/ directory, with the DATABASE_URL the application uses (the new password is prompted for, or set NEW_PASSWORD):
    python scripts/reset_password.py --email owner@example.com
    python scripts/reset_password.py --email owner@example.com --deactivate      # block the account (no password change)
    python scripts/reset_password.py --email owner@example.com --activate

There is no self-service reset: it would need a verified email channel the product does not have. Verify who is asking before using this.
The new password must satisfy the same policy as sign-up.
"""
from __future__ import annotations

import argparse
import getpass
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.errors import AppError  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.services import auth_service  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Reset a password and/or (de)activate an account.")
    parser.add_argument("--email", required=True)
    state = parser.add_mutually_exclusive_group()
    state.add_argument("--deactivate", action="store_true")
    state.add_argument("--activate", action="store_true")
    args = parser.parse_args()

    password = None
    if not args.deactivate:                                  # a deactivation needs no new password
        password = os.environ.get("NEW_PASSWORD") or getpass.getpass("New password: ")
    active = False if args.deactivate else (True if args.activate else None)
    db = SessionLocal()
    try:
        user = auth_service.operator_reset(db, args.email, new_password=password, active=active)
    except AppError as exc:
        print(f"not changed: {exc.message}", file=sys.stderr)
        return 1
    finally:
        db.close()
    print(f"account updated: {user.email}  (active={user.is_active}); all sessions ended")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
