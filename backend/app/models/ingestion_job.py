from sqlalchemy import JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.common import BusinessScopedMixin, TimestampMixin, UUIDPKMixin, UpdatedAtMixin


class DataIngestionJob(UUIDPKMixin, BusinessScopedMixin, TimestampMixin, UpdatedAtMixin, Base):
    """Tracks one upload's parse -> map -> validate -> store pipeline
    (docs/API_SPECIFICATION.md §3 GET .../data/jobs/{job_id}).

    Not in the original docs/DATABASE_SCHEMA.md table list — added because
    the documented job-status endpoint needs somewhere to persist status.
    Processing itself runs synchronously within the upload request (see
    docs/BACKEND_SPECIFICATION.md §6 "keep the initial queue implementation
    simple"); this table exists so the status can still be polled/reviewed
    afterward, and so a job needing mapping confirmation can be resumed.
    """

    __tablename__ = "data_ingestion_jobs"

    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    detected_types_json: Mapped[list] = mapped_column(JSON, default=list)
    mapping_json: Mapped[dict] = mapped_column(JSON, default=dict)
    summary_json: Mapped[dict] = mapped_column(JSON, default=dict)
    error_message: Mapped[str | None] = mapped_column(Text)
