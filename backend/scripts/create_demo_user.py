"""Development helper — create (or refresh) the DEMO ACCOUNT.

The demo account is a normal business ("sme") login that owns the synthetic
demonstration business from `demo_business_service` (180 days of products,
customers, sales, marketing and stock). Everything in it is generated, labeled
"Demo" / "Synthetic demonstration data", and is never real business data.

    # from the backend/ directory, with the same DATABASE_URL the app uses:
    DATABASE_URL=sqlite:///./dev.db python scripts/create_demo_user.py \
        --email demo@decisiongpt.local --password "a-demo-password"

Safe to re-run: if the account already owns a demo business nothing is
duplicated; its password is simply reset to the value provided.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.core.security import hash_password  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.models.business import Business  # noqa: E402
from app.models.memory import BusinessMemory  # noqa: E402
from app.models.user import ROLE_SME, User  # noqa: E402
from app.services import assistant_service, demo_business_service  # noqa: E402

# Real questions answered by the real assistant from the demo data, so "My Reports"
# starts with genuine saved answers. Nothing here is hand-written output.
STARTER_QUESTIONS = [
    "Which products sold the most last month?",
    "What is improving and what is getting worse?",
    "Which customers are most valuable?",
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Create or refresh the demo account.")
    parser.add_argument("--email", default="demo@decisiongpt.local")
    parser.add_argument("--password", required=True)
    parser.add_argument("--name", default="Demo Account")
    parser.add_argument(
        "--reset-answers",
        action="store_true",
        help="delete the demo business's saved answers and re-ask the starter questions",
    )
    args = parser.parse_args()
    if len(args.password) < 8:
        parser.error("password must be at least 8 characters")

    email = args.email.strip().lower()
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if user is None:
            user = User(email=email, password_hash=hash_password(args.password), full_name=args.name,
                        role=ROLE_SME, is_active=True)
            db.add(user)
            db.commit()
            db.refresh(user)
            action = "created"
        else:
            user.password_hash = hash_password(args.password)
            user.is_active = True
            db.commit()
            action = "refreshed"

        business = (
            db.query(Business)
            .filter(Business.owner_user_id == user.id, Business.name == demo_business_service.DEMO_BUSINESS_NAME)
            .first()
        )
        if business is None:
            business_id = demo_business_service.create_demo_business(db)
            business = db.get(Business, business_id)
            business.owner_user_id = user.id
            db.commit()
            for q in STARTER_QUESTIONS:
                try:
                    assistant_service.answer_question(db, business.id, q)
                except Exception as exc:  # a question that can't be answered is simply not saved
                    print(f"  (skipped starter question {q!r}: {exc})")
            print("demo business created with sample data")
        elif args.reset_answers:
            deleted = (
                db.query(BusinessMemory)
                .filter(BusinessMemory.business_id == business.id, BusinessMemory.memory_type == "chat")
                .delete()
            )
            db.commit()
            for q in STARTER_QUESTIONS:
                try:
                    assistant_service.answer_question(db, business.id, q)
                except Exception as exc:
                    print(f"  (skipped starter question {q!r}: {exc})")
            print(f"demo saved answers reset ({deleted} removed, {len(STARTER_QUESTIONS)} re-asked)")
        print(f"demo account {action}: {user.email}  (role={user.role}, business={business.id})")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
