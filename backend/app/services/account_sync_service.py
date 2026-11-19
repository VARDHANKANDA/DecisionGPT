"""Sync and ensure institutional demo user accounts exist in the database.

Preserves exact user IDs, roles, and Argon2id password hashes from the canonical records.
Idempotent: will never overwrite an existing user or reset an existing password.
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.core.security import verify_password
from app.models.business import Business
from app.models.user import User
from app.services import demo_business_service

logger = logging.getLogger(__name__)

CANONICAL_DEMO_ACCOUNTS = {
    'admin@decisiongpt.local': {
        'id': 'feb86009-24df-4829-8944-bbf229c72d44',
        'email': 'admin@decisiongpt.local',
        'role': 'admin',
        'full_name': 'System Administrator',
        'is_active': True,
        'token_version': 1,
        'password_hash': '$argon2id$v=19$m=65536,t=3,p=4$0g/7A/5ocbYD7E6wpJBlFA$HaHhpZoiezBVaAxo+5aiJO0lIlcpW9qdp+/gzUgc+L0',
    },
    'demo@decisiongpt.local': {
        'id': 'b9856c35-4ea0-4d50-b10c-b22e65702450',
        'email': 'demo@decisiongpt.local',
        'role': 'sme',
        'full_name': 'SME Business User',
        'is_active': True,
        'token_version': 1,
        'password_hash': '$argon2id$v=19$m=65536,t=3,p=4$5fSLU4hmTmsI5meFBjukQQ$GTVmH0K7x7rOa5qeSgXv16Q99YlK/fkIzQG78RSY7JQ',
    },
    'researcher@decisiongpt.local': {
        'id': 'a83f66be-dc82-48ec-bdf6-b79c2fa9d455',
        'email': 'researcher@decisiongpt.local',
        'role': 'researcher',
        'full_name': 'Platform Researcher',
        'is_active': True,
        'token_version': 1,
        'password_hash': '$argon2id$v=19$m=65536,t=3,p=4$ze4A96Z7BHTpc2Va4RbdIA$Se8ugGVAmvHzDbiLfAjbHk4KggiAsEOIUl0MIbN8Ezo',
    },
}

DEMO_BUSINESS_ID = "e41940d9-7083-45b1-8799-da21b39e13e7"


def sync_production_demo_accounts(db: Session) -> dict[str, dict[str, Any]]:
    """Ensure all three canonical institutional demo accounts exist in the database.

    Guarantees:
    - Preserves exact User UUIDs
    - Preserves exact Roles ('admin', 'researcher', 'sme')
    - Preserves exact Argon2id password hashes (so existing passwords verify without change)
    - Strictly idempotent: if a user already exists with that email or id, it is NEVER overwritten
    - For 'demo@decisiongpt.local': ensures the demo business ('Saanjh Handloom Co. (Demo)') exists
      and is linked to the demo user.
    """
    results: dict[str, dict[str, Any]] = {}

    for email, data in CANONICAL_DEMO_ACCOUNTS.items():
        user = db.query(User).filter((User.email == email) | (User.id == data["id"])).first()
        if user is None:
            user = User(
                id=data["id"],
                email=data["email"],
                password_hash=data["password_hash"],
                full_name=data["full_name"],
                role=data["role"],
                is_active=data["is_active"],
                token_version=data["token_version"],
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            action = "created"
            logger.info("Synchronized missing canonical demo user: %s (role: %s, id: %s)", email, user.role, user.id)
        else:
            action = "already_exists"
            logger.debug("Canonical demo user already exists: %s (role: %s, id: %s)", email, user.role, user.id)

        # For SME demo user, ensure demo business exists and is linked
        biz_id_str = ""
        if data["role"] == "sme":
            biz = (
                db.query(Business)
                .filter(
                    (Business.id == DEMO_BUSINESS_ID)
                    | ((Business.owner_user_id == user.id) & (Business.name == demo_business_service.DEMO_BUSINESS_NAME))
                )
                .first()
            )
            if biz is None:
                try:
                    new_biz_id = demo_business_service.create_demo_business(db, seed=7)
                    biz = db.get(Business, new_biz_id)
                    biz.owner_user_id = user.id
                    db.commit()
                    db.refresh(biz)
                    biz_id_str = str(biz.id)
                    logger.info("Initialized demo business %s for user %s", biz_id_str, email)
                except Exception as exc:
                    logger.warning("Could not initialize full demo business for %s: %s", email, exc)
            else:
                if biz.owner_user_id != user.id:
                    biz.owner_user_id = user.id
                    db.commit()
                biz_id_str = str(biz.id)

        results[email] = {
            "email": user.email,
            "role": user.role,
            "user_id": str(user.id),
            "full_name": user.full_name or "",
            "action": action,
            "business_id": biz_id_str,
        }

    return results


def verify_demo_account_credentials(db: Session, passwords: dict[str, str]) -> dict[str, bool]:
    """Verify that the supplied passwords match the stored hashes for each demo account."""
    status: dict[str, bool] = {}
    for email, plain_pwd in passwords.items():
        user = db.query(User).filter(User.email == email).first()
        if not user or not user.password_hash:
            status[email] = False
        else:
            status[email] = verify_password(plain_pwd, user.password_hash)
    return status
