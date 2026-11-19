from datetime import datetime

from sqlalchemy import JSON, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.db.types import SafeJSON
from app.models.common import TimestampMixin, UUIDPKMixin

# Lifecycle statuses (docs/PRD.md §17 "Model Registry"):
#   experimental -> just trained, not used by the production pipeline
#   active       -> the deployed model for its model_name (exactly one)
#   archived     -> superseded
#   candidate    -> registered from the file registry, NOT used for inference until validated and promoted
#   validated    -> passed the automated promotion checks; still not used until a person promotes it
#   rejected     -> failed the checks (kept for the record)
STATUS_EXPERIMENTAL = "experimental"
STATUS_CANDIDATE = "candidate"
STATUS_VALIDATED = "validated"
STATUS_REJECTED = "rejected"
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
    parameters_json: Mapped[dict] = mapped_column(SafeJSON, default=dict)
    metrics_json: Mapped[dict] = mapped_column(SafeJSON, default=dict)
    model_path: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="registered", index=True)

    # Research-platform provenance (nullable so file-registry-synced rows load).
    task: Mapped[str | None] = mapped_column(String(40))
    features_json: Mapped[list | None] = mapped_column(SafeJSON)
    training_run_id: Mapped[str | None] = mapped_column(String(36))
    source: Mapped[str | None] = mapped_column(String(40))  # cli | training_center
    promoted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Lifecycle detail: run metadata from the training sidecar, the latest validation result, the feature contract version.
    lifecycle_json: Mapped[dict | None] = mapped_column(SafeJSON)

    @property
    def validation_status(self) -> str:
        """What the lifecycle can honestly say: 'validated' / 'rejected' only after the automated checks ran; a version activated by the
        first-version bootstrap, or trained before validation existed, is 'not_validated' - never presented as newly validated."""
        v = (self.lifecycle_json or {}).get("validation")
        if isinstance(v, dict) and "passed" in v:
            return "validated" if v["passed"] else "rejected"
        promo = (self.lifecycle_json or {}).get("promotion") or {}
        if self.status == STATUS_ACTIVE and promo.get("by") == "system:sync":
            return "not_validated_bootstrap"
        return "not_validated"

    @property
    def applicability(self) -> dict:
        from app.services import model_applicability_service  # lazy: services import this module

        return model_applicability_service.describe(self)


class ModelLifecycleEvent(UUIDPKMixin, TimestampMixin, Base):
    """Append-only log of everything that changed a model's state: who or what did it, when, why, and the checks behind it."""

    __tablename__ = "model_lifecycle_events"

    seq: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)  # strictly increasing: a deterministic event order
    model_id: Mapped[str | None] = mapped_column(String(36), index=True)
    model_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    event: Mapped[str] = mapped_column(String(40), nullable=False, index=True)  # registered|validated|validation_failed|promoted|rolled_back|archived|bootstrap_activation
    from_status: Mapped[str | None] = mapped_column(String(30))
    to_status: Mapped[str | None] = mapped_column(String(30))
    actor: Mapped[str] = mapped_column(String(120), nullable=False)  # a user id/email, "system:sync", "system:validation"
    reason: Mapped[str | None] = mapped_column(String(500))
    details_json: Mapped[dict | None] = mapped_column(SafeJSON)
