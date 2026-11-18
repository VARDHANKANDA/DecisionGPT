from datetime import datetime

from sqlalchemy import JSON, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.common import TimestampMixin, UUIDPKMixin, utcnow

# Lifecycle (docs/PRD.md §12 "Experiment Runner").
STATUS_PENDING = "pending"
STATUS_RUNNING = "running"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"


class ExperimentRun(UUIDPKMixin, TimestampMixin, Base):
    """Research/platform-only record. Never exposed to SME-facing endpoints."""

    __tablename__ = "experiment_runs"

    experiment_name: Mapped[str] = mapped_column(String(255), nullable=False)
    experiment_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    dataset_version: Mapped[str | None] = mapped_column(String(50))
    model_version: Mapped[str | None] = mapped_column(String(50))
    configuration_json: Mapped[dict] = mapped_column(JSON, default=dict)
    metrics_json: Mapped[dict] = mapped_column(JSON, default=dict)
    result_path: Mapped[str | None] = mapped_column(String(500))
    random_seed: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(30), default="completed", index=True)

    # Lifecycle detail (nullable so pre-existing rows load).
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)
    model_versions_json: Mapped[dict | None] = mapped_column(JSON)

    def mark_running(self) -> None:
        self.status = STATUS_RUNNING
        self.started_at = utcnow()

    def mark_completed(self) -> None:
        self.status = STATUS_COMPLETED
        self.completed_at = utcnow()

    def mark_failed(self, message: str) -> None:
        self.status = STATUS_FAILED
        self.completed_at = utcnow()
        self.error_message = message
