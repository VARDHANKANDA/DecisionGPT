from datetime import datetime

from sqlalchemy import JSON, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.common import TimestampMixin, UUIDPKMixin

# Lifecycle statuses (docs/PRD.md §17 "Model Registry"):
#   experimental -> just trained, not used by the production pipeline
#   active       -> the deployed model for its model_name (exactly one)
#   archived     -> superseded
STATUS_EXPERIMENTAL = "experimental"
STATUS_ACTIVE = "active"
STATUS_ARCHIVED = "archived"


class MLModel(UUIDPKMixin, TimestampMixin, Base):
    """Model registry entry. Not business-scoped — models are trained on
    platform/research data and shared across all businesses at inference time."""

    __tablename__ = "models"

    model_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    model_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    dataset_version: Mapped[str] = mapped_column(String(50), nullable=False)
    feature_version: Mapped[str] = mapped_column(String(50), nullable=False)
    parameters_json: Mapped[dict] = mapped_column(JSON, default=dict)
    metrics_json: Mapped[dict] = mapped_column(JSON, default=dict)
    model_path: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="registered", index=True)

    # Research-platform provenance (nullable so file-registry-synced rows load).
    task: Mapped[str | None] = mapped_column(String(40))
    features_json: Mapped[list | None] = mapped_column(JSON)
    training_run_id: Mapped[str | None] = mapped_column(String(36))
    source: Mapped[str | None] = mapped_column(String(40))  # cli | training_center
    promoted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
