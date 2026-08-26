"""Research-platform models — datasets, dataset versions, training runs.

These tables are ADMIN/RESEARCHER-ONLY. They are never business-scoped and
must never be exposed through an SME-facing endpoint (AGENTS.md "Data
isolation"; docs/PRD.md §8 "Research Console — Scope").
"""
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.db.types import GUID
from app.models.common import TimestampMixin, UUIDPKMixin, utcnow


class ResearchDataset(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "research_datasets"

    dataset_id: Mapped[str] = mapped_column(String(120), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    domain: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    source: Mapped[str | None] = mapped_column(String(255))
    license: Mapped[str | None] = mapped_column(String(120))
    created_by: Mapped[str | None] = mapped_column(String(255))


class ResearchDatasetVersion(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "research_dataset_versions"

    dataset_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("research_datasets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    file_type: Mapped[str] = mapped_column(String(16), nullable=False)  # csv | xlsx | parquet
    storage_path: Mapped[str] = mapped_column(String(500), nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False)
    column_count: Mapped[int] = mapped_column(Integer, nullable=False)
    schema_json: Mapped[list] = mapped_column(JSON, default=list)  # [{"name","dtype"}]
    missing_summary_json: Mapped[dict] = mapped_column(JSON, default=dict)  # {col: n_missing}
    duplicates_summary_json: Mapped[dict] = mapped_column(JSON, default=dict)
    quality_report_json: Mapped[dict] = mapped_column(JSON, default=dict)
    validation_ok: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[str | None] = mapped_column(String(255))


class TrainingRun(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "training_runs"

    dataset_version_id: Mapped[str | None] = mapped_column(
        GUID(), ForeignKey("research_dataset_versions.id", ondelete="SET NULL")
    )
    platform_domain: Mapped[str | None] = mapped_column(String(60))
    dataset_version_label: Mapped[str | None] = mapped_column(String(120))
    task: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    model_type: Mapped[str] = mapped_column(String(60), nullable=False)
    features_json: Mapped[list] = mapped_column(JSON, default=list)
    target: Mapped[str | None] = mapped_column(String(60))
    parameters_json: Mapped[dict] = mapped_column(JSON, default=dict)
    random_seed: Mapped[int] = mapped_column(Integer, default=42)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    metrics_json: Mapped[dict] = mapped_column(JSON, default=dict)
    model_id: Mapped[str | None] = mapped_column(GUID(), ForeignKey("models.id", ondelete="SET NULL"))
    model_name: Mapped[str | None] = mapped_column(String(100))
    model_version: Mapped[str | None] = mapped_column(String(50))
    artifact_path: Mapped[str | None] = mapped_column(String(500))
    error_message: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str | None] = mapped_column(String(255))

    def mark_running(self) -> None:
        self.status = "running"
        self.started_at = utcnow()

    def mark_completed(self) -> None:
        self.status = "completed"
        self.completed_at = utcnow()

    def mark_failed(self, message: str) -> None:
        self.status = "failed"
        self.completed_at = utcnow()
        self.error_message = message
