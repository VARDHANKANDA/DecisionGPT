import sqlite3
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.session import Base
from app.models.user import User
from app.services.account_sync_service import (
    CANONICAL_DEMO_ACCOUNTS,
    sync_production_demo_accounts,
    verify_demo_account_credentials,
)

PASSWORDS = {
    "admin@decisiongpt.local": "AdminPass@2026!",
    "researcher@decisiongpt.local": "ResearchPass@2026!",
    "demo@decisiongpt.local": "DemoUser@2026!",
}


@pytest.fixture
def clean_db(tmp_path):
    db_file = tmp_path / "test_sync.db"
    engine = create_engine(f"sqlite:///{db_file.as_posix()}")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def test_sync_production_demo_accounts_creates_all_three(clean_db):
    # Verify initial state is empty
    assert clean_db.query(User).count() == 0

    # Run sync
    results = sync_production_demo_accounts(clean_db)

    # Verify all 3 returned
    assert len(results) == 3
    for email, expected in CANONICAL_DEMO_ACCOUNTS.items():
        assert email in results
        assert results[email]["action"] == "created"
        assert results[email]["role"] == expected["role"]
        assert results[email]["user_id"] == expected["id"]

        # Verify DB row
        db_user = clean_db.query(User).filter(User.email == email).first()
        assert db_user is not None
        assert str(db_user.id) == expected["id"]
        assert db_user.role == expected["role"]
        assert db_user.is_active is True

    # Verify passwords verify successfully with Argon2id
    verifications = verify_demo_account_credentials(clean_db, PASSWORDS)
    assert all(verifications.values()), verifications


def test_sync_production_demo_accounts_is_idempotent(clean_db):
    # First sync
    sync_production_demo_accounts(clean_db)
    assert clean_db.query(User).count() == 3

    # Second sync
    second_results = sync_production_demo_accounts(clean_db)
    assert clean_db.query(User).count() == 3

    for email in CANONICAL_DEMO_ACCOUNTS:
        assert second_results[email]["action"] == "already_exists"

    # Verify credentials still match
    verifications = verify_demo_account_credentials(clean_db, PASSWORDS)
    assert all(verifications.values()), verifications
