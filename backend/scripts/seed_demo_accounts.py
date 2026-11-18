"""Development helper — seed (or refresh) the THREE DEMO USER ACCOUNTS (Phase 7 - RBAC).

Creates or safely updates the 3 standard demo roles:
  1. Admin (ROLE_ADMIN = 'admin')
     - Access to administrative dashboard, user management, system monitoring & research console.
     - Email: admin@decisiongpt.local
     - Password: AdminPass@2026!
  2. Research User (ROLE_RESEARCHER = 'researcher')
     - Access to research dashboard, model metrics, evaluations & benchmarks.
     - Email: researcher@decisiongpt.local
     - Password: ResearchPass@2026!
  3. Standard User (ROLE_SME = 'sme')
     - Access to SME Business OS workspace, decision support, what-if simulations & voice interface.
     - Email: demo@decisiongpt.local
     - Password: DemoUser@2026!
     - Owns the demonstration business with 180 days of realistic synthetic data.

Usage:
    python backend/scripts/seed_demo_accounts.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Add backend and root to sys.path
backend_dir = Path(__file__).resolve().parents[1]
root_dir = backend_dir.parent
sys.path.insert(0, str(backend_dir))
sys.path.insert(0, str(root_dir))

from app.core.security import hash_password
from app.db.session import Base, engine, SessionLocal
import app.models  # populate metadata
from app.models.business import Business
from app.models.user import ROLE_ADMIN, ROLE_RESEARCHER, ROLE_SME, User
from app.services import assistant_service, demo_business_service

STARTER_QUESTIONS = [
    "Which products sold the most last month?",
    "What is improving and what is getting worse?",
    "Which customers are most valuable?",
]

ACCOUNTS = [
    {
        "role": ROLE_ADMIN,
        "email": "admin@decisiongpt.local",
        "password": os.environ.get("DEMO_ADMIN_PASSWORD", "AdminPass@2026!"),
        "full_name": "System Administrator",
    },
    {
        "role": ROLE_RESEARCHER,
        "email": "researcher@decisiongpt.local",
        "password": os.environ.get("DEMO_RESEARCHER_PASSWORD", "ResearchPass@2026!"),
        "full_name": "Platform Researcher",
    },
    {
        "role": ROLE_SME,
        "email": "demo@decisiongpt.local",
        "password": os.environ.get("DEMO_USER_PASSWORD", "DemoUser@2026!"),
        "full_name": "SME Business User",
    },
]


def seed_accounts() -> dict[str, dict[str, str]]:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    results = {}
    try:
        for acc in ACCOUNTS:
            email = acc["email"].strip().lower()
            role = acc["role"]
            plain_pwd = acc["password"]
            full_name = acc["full_name"]

            user = db.query(User).filter(User.email == email).first()
            if user is None:
                user = User(
                    email=email,
                    password_hash=hash_password(plain_pwd),
                    full_name=full_name,
                    role=role,
                    is_active=True,
                )
                db.add(user)
                db.commit()
                db.refresh(user)
                action = "created"
            else:
                user.password_hash = hash_password(plain_pwd)
                user.role = role
                user.is_active = True
                user.full_name = full_name
                user.token_version = int(user.token_version or 0) + 1
                db.commit()
                db.refresh(user)
                action = "refreshed"

            # For SME standard user: ensure demo business exists and is owned by this user
            business_id = None
            if role == ROLE_SME:
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
                        except Exception as exc:
                            print(f"  (skipped starter question {q!r}: {exc})")
                    print(f"  -> Demo business created and populated (ID: {business.id})")
                else:
                    business_id = business.id
                    print(f"  -> Existing demo business linked (ID: {business.id})")

            results[role] = {
                "email": user.email,
                "password": plain_pwd,
                "role": user.role,
                "full_name": user.full_name or "",
                "user_id": str(user.id),
                "business_id": str(business_id) if business_id else "",
                "action": action,
            }
            print(f"[{action.upper()}] Role: {role:10} | Email: {email:30} | Name: {full_name}")

        return results
    finally:
        db.close()


def main() -> int:
    print("=" * 70)
    print("Seeding DecisionGPT Three Demo User Accounts (Phase 7 - RBAC)")
    print("=" * 70)
    results = seed_accounts()
    print("=" * 70)
    print("All 3 demo accounts ready for local development / evaluation:")
    for role, data in results.items():
        print(f"  • {role.upper()}:")
        print(f"      Username: {data['email']}")
        print(f"      Password: {data['password']}")
        print(f"      Role:     {data['role']}")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
