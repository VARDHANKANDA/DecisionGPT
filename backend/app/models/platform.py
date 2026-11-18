"""Persistence for the business-operating-system features (migration 0008).

Every table is business-scoped (``BusinessScopedMixin``) and every query in the services filters on ``business_id``
(AGENTS.md "Data isolation"). Nothing here stores secrets or raw uploaded files.
"""
from datetime import date, datetime

from sqlalchemy import Boolean, Date, Index, text, DateTime, Float, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.db.types import SafeJSON
from app.models.common import BusinessScopedMixin, TimestampMixin, UUIDPKMixin, UpdatedAtMixin


class KpiTarget(UUIDPKMixin, BusinessScopedMixin, TimestampMixin, UpdatedAtMixin, Base):
    """An owner-configured target for one KPI. The status shown to the user is derived from this rule, never invented."""

    __tablename__ = "kpi_targets"
    __table_args__ = (UniqueConstraint("business_id", "kpi_key", name="uq_kpi_target_business_key"),)

    kpi_key: Mapped[str] = mapped_column(String(60), nullable=False)
    target_value: Mapped[float] = mapped_column(Float, nullable=False)
    direction: Mapped[str] = mapped_column(String(10), nullable=False, default="higher")  # higher | lower is better
    period_days: Mapped[int] = mapped_column(Integer, nullable=False, default=30)


class AlertRule(UUIDPKMixin, BusinessScopedMixin, TimestampMixin, UpdatedAtMixin, Base):
    """Per-business override of a built-in alert rule's threshold. Absent row = the documented default."""

    __tablename__ = "alert_rules"
    __table_args__ = (UniqueConstraint("business_id", "rule_key", name="uq_alert_rule_business_key"),)

    rule_key: Mapped[str] = mapped_column(String(60), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    threshold: Mapped[float | None] = mapped_column(Float)


_ACTIVE = text("status IN ('open', 'read')")


class Alert(UUIDPKMixin, BusinessScopedMixin, TimestampMixin, Base):
    __tablename__ = "alerts"
    # at most one ACTIVE alert per condition: a resolved/cleared one may be followed by a new occurrence later
    __table_args__ = (Index("uq_alert_active_dedupe", "business_id", "dedupe_key", unique=True, sqlite_where=_ACTIVE, postgresql_where=_ACTIVE),)

    rule_key: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    dedupe_key: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(10), nullable=False)  # low | medium | high
    status: Mapped[str] = mapped_column(String(12), nullable=False, default="open", index=True)  # open | read | resolved | cleared
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    metric_value: Mapped[float | None] = mapped_column(Float)
    threshold: Mapped[float | None] = mapped_column(Float)
    period_start: Mapped[date | None] = mapped_column(Date)
    period_end: Mapped[date | None] = mapped_column(Date)
    evidence_json: Mapped[dict] = mapped_column(SafeJSON, default=dict)
    suggested_action: Mapped[str | None] = mapped_column(Text)
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SavedReport(UUIDPKMixin, BusinessScopedMixin, TimestampMixin, Base):
    __tablename__ = "saved_reports"

    report_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    period_start: Mapped[date | None] = mapped_column(Date)
    period_end: Mapped[date | None] = mapped_column(Date)
    scope_json: Mapped[dict] = mapped_column(SafeJSON, default=dict)
    payload_json: Mapped[dict] = mapped_column(SafeJSON, default=dict)


class HealthSnapshot(UUIDPKMixin, BusinessScopedMixin, TimestampMixin, Base):
    __tablename__ = "health_snapshots"

    version: Mapped[str] = mapped_column(String(20), nullable=False)
    score: Mapped[float | None] = mapped_column(Float)  # None = no defensible composite
    period_days: Mapped[int] = mapped_column(Integer, nullable=False)
    available_weight: Mapped[float] = mapped_column(Float, nullable=False)
    payload_json: Mapped[dict] = mapped_column(SafeJSON, default=dict)


class DataPrepRun(UUIDPKMixin, BusinessScopedMixin, TimestampMixin, Base):
    """One profiling / cleaning / validation / transformation run (the data-quality history).

    ``undo_json`` holds what is needed to revert a consequential change (the removed rows or the old values), so an applied
    cleaning step can be reviewed and reverted. Source *files* are not retained; this is a row-level record, not full lineage.
    """

    __tablename__ = "data_prep_runs"

    stage: Mapped[str] = mapped_column(String(20), nullable=False, index=True)  # profile | clean | validate | transform
    table_type: Mapped[str | None] = mapped_column(String(40))
    operation: Mapped[str | None] = mapped_column(String(60))
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # completed | failed | applied | reverted
    summary_json: Mapped[dict] = mapped_column(SafeJSON, default=dict)
    undo_json: Mapped[dict | None] = mapped_column(SafeJSON)
    error_message: Mapped[str | None] = mapped_column(Text)


class AnalysisRun(UUIDPKMixin, BusinessScopedMixin, TimestampMixin, Base):
    """A saved causal / counterfactual / debate run. ``result_json`` is what the analysis actually produced."""

    __tablename__ = "analysis_runs"

    kind: Mapped[str] = mapped_column(String(20), nullable=False, index=True)  # causal | counterfactual | debate | forecast_eval | customer_eval
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # completed | failed
    mode: Mapped[str | None] = mapped_column(String(30))
    question: Mapped[str | None] = mapped_column(Text)
    params_json: Mapped[dict] = mapped_column(SafeJSON, default=dict)
    result_json: Mapped[dict] = mapped_column(SafeJSON, default=dict)
    error_message: Mapped[str | None] = mapped_column(Text)
