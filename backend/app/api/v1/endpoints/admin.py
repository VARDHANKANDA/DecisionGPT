"""Administrative Dashboard & System Controls (Phase 7 - RBAC).

Exclusively accessible by users holding the ROLE_ADMIN ('admin') role.
Provides:
  - User management (list users, activate/deactivate accounts)
  - Application-level system monitoring & resource counts
  - System settings and configuration audit
"""
from __future__ import annotations

import platform
import sys
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.core.config import get_settings
from app.db.session import get_db
from app.models.business import Business
from app.models.customer import Customer
from app.models.inventory import InventoryRecord
from app.models.memory import BusinessMemory
from app.models.ml_model import MLModel
from app.models.product import Product
from app.models.sale import Sale
from app.models.user import ROLES, User

router = APIRouter(prefix="/admin", tags=["admin"])


class AdminUserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    full_name: str | None
    role: str
    is_active: bool
    created_at: datetime
    token_version: int


class UserStatusUpdate(BaseModel):
    is_active: bool


class SystemMonitoringOut(BaseModel):
    status: str
    timestamp: str
    system_info: dict[str, Any]
    counts: dict[str, Any]
    users_by_role: dict[str, int]
    configuration: dict[str, Any]


@router.get("/users", response_model=list[AdminUserOut])
def list_users(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> list[User]:
    """List all registered users across the platform."""
    return db.query(User).order_by(User.created_at.desc()).all()


@router.patch("/users/{user_id}/status", response_model=AdminUserOut)
def update_user_status(
    user_id: str,
    payload: UserStatusUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> User:
    """Activate or deactivate a user account. Deactivating increments token_version to invalidate active sessions."""
    target_user = db.get(User, user_id)
    if target_user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    
    # Prevent admin from deactivating their own account
    if target_user.id == admin.id and not payload.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Administrators cannot deactivate their own account.",
        )

    target_user.is_active = payload.is_active
    target_user.token_version = int(target_user.token_version or 0) + 1
    db.commit()
    db.refresh(target_user)
    return target_user


@router.get("/monitoring", response_model=SystemMonitoringOut)
def get_system_monitoring(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> dict[str, Any]:
    """Application-level monitoring, resource stats, and operational health metrics."""
    settings = get_settings()

    # User breakdown by role
    users_by_role: dict[str, int] = {r: 0 for r in ROLES}
    role_counts = db.query(User.role, func.count(User.id)).group_by(User.role).all()
    for role_name, cnt in role_counts:
        users_by_role[role_name] = cnt

    # System counts
    total_users = sum(users_by_role.values())
    active_users = db.query(User).filter(User.is_active.is_(True)).count()
    total_businesses = db.query(Business).count()
    total_products = db.query(Product).count()
    total_customers = db.query(Customer).count()
    total_sales = db.query(Sale).count()
    total_inventory = db.query(InventoryRecord).count()
    total_memories = db.query(BusinessMemory).count()
    total_models = db.query(MLModel).count()
    active_models = db.query(MLModel).filter(MLModel.status == "active").count()

    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "system_info": {
            "python_version": sys.version.split()[0],
            "platform": platform.platform(),
            "database_type": "sqlite" if settings.database_url.startswith("sqlite") else "postgres",
            "server_mode": "production" if not settings.auth_enabled else "authenticated_saas",
        },
        "counts": {
            "total_users": total_users,
            "active_users": active_users,
            "businesses": total_businesses,
            "products": total_products,
            "customers": total_customers,
            "sales_transactions": total_sales,
            "inventory_items": total_inventory,
            "business_memories": total_memories,
            "registered_models": total_models,
            "active_models": active_models,
        },
        "users_by_role": users_by_role,
        "configuration": {
            "auth_enabled": settings.auth_enabled,
            "research_console_enabled": settings.research_console_enabled,
            "rate_limiting_enabled": settings.rate_limit_enabled,
            "analytics_explain_enabled": settings.analytics_explain_enabled,
            "cors_origins": getattr(settings, "cors_origins", [settings.frontend_origin]),
            "app_environment": settings.environment,
        },
    }


@router.get("/settings")
def get_system_settings(
    admin: User = Depends(require_admin),
) -> dict[str, Any]:
    """Retrieve system configuration parameters safe for administrator inspection."""
    settings = get_settings()
    return {
        "environment": settings.environment,
        "auth_enabled": settings.auth_enabled,
        "research_console_enabled": settings.research_console_enabled,
        "rate_limiting_enabled": settings.rate_limit_enabled,
        "analytics_explain_enabled": settings.analytics_explain_enabled,
        "cors_origins": getattr(settings, "cors_origins", [settings.frontend_origin]),
        "jwt_algorithm": "HS256",
        "access_token_expire_minutes": settings.jwt_ttl_seconds // 60,
        "role_hierarchy": {
            "admin": ["administrative_controls", "user_management", "system_monitoring", "research_console"],
            "researcher": ["research_console", "model_evaluations", "dataset_registry", "reproducibility"],
            "sme": ["business_os", "analytics_chat", "what_if_simulation", "voice_interface", "decision_support"],
        },
    }
