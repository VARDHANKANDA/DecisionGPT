from datetime import date

from sqlalchemy import Date, Numeric
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.common import BusinessScopedMixin, TimestampMixin, UUIDPKMixin


class FinanceRecord(UUIDPKMixin, BusinessScopedMixin, TimestampMixin, Base):
    """One period (usually a month) of SME financials. Every metric is
    optional — DecisionGPT only computes a derived ratio when its source
    fields are present (no fabricated values). See
    docs/INDIAN_SME_DATA_ARCHITECTURE.md.
    """

    __tablename__ = "finance_records"

    period_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    revenue: Mapped[float | None] = mapped_column(Numeric(18, 2))
    cogs: Mapped[float | None] = mapped_column(Numeric(18, 2))
    gross_profit: Mapped[float | None] = mapped_column(Numeric(18, 2))
    operating_expenses: Mapped[float | None] = mapped_column(Numeric(18, 2))
    net_profit: Mapped[float | None] = mapped_column(Numeric(18, 2))
    cash_balance: Mapped[float | None] = mapped_column(Numeric(18, 2))
    accounts_receivable: Mapped[float | None] = mapped_column(Numeric(18, 2))
    accounts_payable: Mapped[float | None] = mapped_column(Numeric(18, 2))
    inventory_value: Mapped[float | None] = mapped_column(Numeric(18, 2))
    loan_amount: Mapped[float | None] = mapped_column(Numeric(18, 2))
    interest_rate: Mapped[float | None] = mapped_column(Numeric(8, 4))
    emi: Mapped[float | None] = mapped_column(Numeric(18, 2))
