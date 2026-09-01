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
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.security import hash_password  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.models.user import ROLE_ADMIN, User  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Create or promote a research/admin user.")
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--name", default="Research Admin")
    args = parser.parse_args()

    if len(args.password) < 8:
        parser.error("password must be at least 8 characters")

    email = args.email.strip().lower()
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
            action = "promoted"
        db.commit()
        db.refresh(user)
        print(f"admin account {action}: {user.email}  (role={user.role}, id={user.id})")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
