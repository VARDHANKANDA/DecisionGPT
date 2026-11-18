"""Outcome tracking (docs/BUSINESS_OUTCOME_TRACKING.md).

Beside ``decisions`` (the recommendation record, reused as is), never over it:

* ``TrackedExpectation``   what was expected, as it was when it was expected (a forecast snapshot, a decision's figure, an owner's plan)
* ``DecisionResponse``     append-only: what the owner did with a recommendation; the latest row is the current state
* ``OutcomeObservation``   append-only revisions of what was observed; a correction adds a row, nothing is overwritten

Unknown stays NULL / 'unknown': an unrecorded value is never 0 and a displayed or accepted recommendation is never 'executed'.
"""
from datetime import date

from sqlalchemy import JSON, event, Boolean, Date, ForeignKey, Index, Integer, Numeric, String, Text, text
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.db.types import GUID
from app.models.common import BusinessScopedMixin, TimestampMixin, UUIDPKMixin

SOURCE_KINDS = ("forecast", "decision", "owner_plan")
METRICS = {"units_sold": "units", "revenue": "INR", "orders": "orders", "marketing_spend": "INR"}
SCOPE_BUSINESS_TOTAL = "business_total"
RESPONSES = ("pending", "accepted", "rejected", "modified", "deferred")
ACTION_STATUSES = ("unknown", "not_executed", "partially_executed", "executed")
DESIGNS = ("none", "before_after", "matched_control", "randomized")
OBS_STATUSES = ("pending", "incomplete", "observed", "invalid")
OBS_SOURCES = ("owner_entered", "derived_from_sales", "derived_from_marketing")
PROVENANCE = ("owner_entered", "derived_from_uploaded_data", "demo_synthetic")


class TrackedExpectation(UUIDPKMixin, BusinessScopedMixin, TimestampMixin, Base):
    __tablename__ = "tracked_expectations"
    __table_args__ = (
        # one saved snapshot per business and forecast fingerprint: two simultaneous saves of the same forecast cannot both insert
        Index("uq_tracked_expectations_forecast_fingerprint", "business_id", "fingerprint", unique=True,
              sqlite_where=text("fingerprint IS NOT NULL"), postgresql_where=text("fingerprint IS NOT NULL")),
    )

    source_kind: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    fingerprint: Mapped[str | None] = mapped_column(String(64))           # forecast snapshots only; identifies the forecast that was shown
    decision_id: Mapped[str | None] = mapped_column(GUID(), ForeignKey("decisions.id", ondelete="CASCADE"), index=True)
    question: Mapped[str | None] = mapped_column(Text)
    metric: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    unit: Mapped[str] = mapped_column(String(20), nullable=False)
    scope: Mapped[str] = mapped_column(String(30), nullable=False, default=SCOPE_BUSINESS_TOTAL)
    window_start: Mapped[date] = mapped_column(Date, nullable=False)
    window_end: Mapped[date] = mapped_column(Date, nullable=False)
    horizon_days: Mapped[int] = mapped_column(Integer, nullable=False)
    data_cutoff: Mapped[date | None] = mapped_column(Date)
    expected_value: Mapped[float | None] = mapped_column(Numeric(18, 4))
    points_json: Mapped[list | None] = mapped_column(JSON)
    interval_reliable: Mapped[bool | None] = mapped_column(Boolean)
    interval_method: Mapped[str | None] = mapped_column(String(80))
    method: Mapped[str | None] = mapped_column(String(80))
    model_name: Mapped[str | None] = mapped_column(String(100))
    model_version: Mapped[str | None] = mapped_column(String(50))
    basis: Mapped[str | None] = mapped_column(String(40))
    config_json: Mapped[dict | None] = mapped_column(JSON)
    reference_json: Mapped[dict | None] = mapped_column(JSON)
    assumptions_json: Mapped[list | None] = mapped_column(JSON)
    limitations_json: Mapped[list | None] = mapped_column(JSON)
    comparable_to_actuals: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    comparability_reason: Mapped[str | None] = mapped_column(Text)
    input_sha256: Mapped[str | None] = mapped_column(String(64))
    provenance: Mapped[str] = mapped_column(String(30), nullable=False, default="derived_from_uploaded_data")


class DecisionResponse(UUIDPKMixin, BusinessScopedMixin, TimestampMixin, Base):
    __tablename__ = "decision_responses"
    __table_args__ = (Index("uq_decision_responses_decision_seq", "decision_id", "seq", unique=True),)   # a unique INDEX, as migration 0012 creates it

    decision_id: Mapped[str] = mapped_column(GUID(), ForeignKey("decisions.id", ondelete="CASCADE"), nullable=False, index=True)
    seq: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    response: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    action_status: Mapped[str] = mapped_column(String(24), nullable=False, default="unknown")
    action_taken_json: Mapped[dict | None] = mapped_column(JSON)
    modified_action_json: Mapped[dict | None] = mapped_column(JSON)
    action_start: Mapped[date | None] = mapped_column(Date)
    action_end: Mapped[date | None] = mapped_column(Date)
    known_changes_json: Mapped[list | None] = mapped_column(JSON)
    evaluation_design: Mapped[str] = mapped_column(String(20), nullable=False, default="none")
    follow_up_date: Mapped[date | None] = mapped_column(Date)
    note: Mapped[str | None] = mapped_column(Text)
    recorded_by: Mapped[str | None] = mapped_column(String(120))


class OutcomeObservation(UUIDPKMixin, BusinessScopedMixin, TimestampMixin, Base):
    __tablename__ = "outcome_observations"
    __table_args__ = (
        # at most one CURRENT observation per expectation, metric and window: a retry or double click cannot create two
        Index("uq_outcome_observations_current_window", "expectation_id", "metric", "window_start", "window_end", unique=True,
              sqlite_where=text("is_current = 1"), postgresql_where=text("is_current")),
    )

    expectation_id: Mapped[str] = mapped_column(GUID(), ForeignKey("tracked_expectations.id", ondelete="CASCADE"), nullable=False, index=True)
    metric: Mapped[str] = mapped_column(String(30), nullable=False)
    unit: Mapped[str] = mapped_column(String(20), nullable=False)
    scope: Mapped[str] = mapped_column(String(30), nullable=False, default=SCOPE_BUSINESS_TOTAL)
    window_start: Mapped[date] = mapped_column(Date, nullable=False)
    window_end: Mapped[date] = mapped_column(Date, nullable=False)
    value: Mapped[float | None] = mapped_column(Numeric(18, 4))
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    unavailable_reason: Mapped[str | None] = mapped_column(Text)
    covered_until: Mapped[date | None] = mapped_column(Date)
    coverage_days: Mapped[int | None] = mapped_column(Integer)
    window_days: Mapped[int] = mapped_column(Integer, nullable=False)
    source: Mapped[str] = mapped_column(String(30), nullable=False)
    provenance: Mapped[str] = mapped_column(String(30), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    supersedes_id: Mapped[str | None] = mapped_column(GUID())
    revision_reason: Mapped[str | None] = mapped_column(Text)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    note: Mapped[str | None] = mapped_column(Text)
    recorded_by: Mapped[str | None] = mapped_column(String(120))


# ------------------------------------------------------------------------------------------------ immutability (service-level guarantee)
class ImmutableRecordError(RuntimeError):
    """An attempt to change a record that is append-only. Not reachable from the API; it guards the service layer and any future caller."""


# columns that may still change after insert: only the 'current' flag of an observation (a correction flips it on the OLD revision)
_MUTABLE = {TrackedExpectation: set(), DecisionResponse: set(), OutcomeObservation: {"is_current"}}


def _guard_update(mapper, connection, target):
    allowed = _MUTABLE[type(target)]
    changed = [a.key for a in sa_inspect(target).attrs if a.history.has_changes() and a.key not in allowed]
    if changed:
        raise ImmutableRecordError(
            f"{type(target).__name__} is append-only: {', '.join(sorted(changed))} cannot be changed after it was saved "
            "(record a new revision instead)."
        )


def _guard_delete(mapper, connection, target):
    raise ImmutableRecordError(f"{type(target).__name__} is append-only and cannot be deleted through the application.")


for _cls in (TrackedExpectation, DecisionResponse, OutcomeObservation):
    event.listen(_cls, "before_update", _guard_update)
    event.listen(_cls, "before_delete", _guard_delete)

