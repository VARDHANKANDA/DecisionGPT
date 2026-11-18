"""Development helper — create (or promote) a research/admin account.

Admin accounts are NOT created through the public sign-up UI (that always makes
a normal SME account). Use this script for local development so an authorised
person can reach the Research Console through the normal signed-in session.

    # from the backend/ directory, with the same DATABASE_URL the app uses:
    DATABASE_URL=sqlite:///./dev.db python scripts/create_admin.py \
        --email admin@example.com --password "a-strong-password" --name "Research Admin"

If the email already exists the account is promoted to the admin role and its
password is reset to the value provided.
"""
from __future__ import annotations

import argparse
import getpass
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.security import check_password_policy, hash_password  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.models.user import ROLE_ADMIN, User  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Create or promote a research/admin user.")
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", default=None, help="avoid: prefer the prompt or the ADMIN_PASSWORD environment variable")
    parser.add_argument("--name", default="Research Admin")
    args = parser.parse_args()

    email = args.email.strip().lower()
    args.password = args.password or os.environ.get("ADMIN_PASSWORD") or getpass.getpass("Password: ")
    try:
        check_password_policy(args.password, email=email)
    except ValueError as exc:
        parser.error(str(exc))
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if user is None:
            user = User(
                email=email,
                password_hash=hash_password(args.password),
                full_name=args.name,
                role=ROLE_ADMIN,
                is_active=True,
            )
            db.add(user)
            action = "created"
        else:
            user.password_hash = hash_password(args.password)
            user.role = ROLE_ADMIN
            user.is_active = True
            user.token_version = int(user.token_version or 0) + 1      # ends every session the account already holds
            action = "promoted"
        db.commit()
        db.refresh(user)
        print(f"admin account {action}: {user.email}  (role={user.role}, id={user.id})")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
