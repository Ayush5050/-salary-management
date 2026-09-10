"""Persistence model.

Three tables: ``currencies`` (with the FX rate used for reporting), ``countries``
(the operating locations, each with a default pay currency), and ``employees``.

The one non-obvious column is :attr:`Employee.total_comp_usd_fx_scaled`. It is
derived from the employee's own salary and their currency's rate, and it is
stored rather than computed on read. See :mod:`app.domain.compensation` for the
single place that maintains it, and ``docs/adr/0004-denormalised-usd-total.md``
for the reasoning.
"""

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    MetaData,
    String,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.domain.enums import Department, EmploymentStatus, EmploymentType, Level

# Explicit naming keeps index and constraint names stable and readable in
# migrations and in EXPLAIN output, instead of leaving them to the backend.
_NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=_NAMING_CONVENTION)


class Currency(Base):
    """A pay currency and the rate used to report it in USD."""

    __tablename__ = "currencies"

    code: Mapped[str] = mapped_column(String(3), primary_key=True)
    name: Mapped[str] = mapped_column(String(60), nullable=False)
    symbol: Mapped[str] = mapped_column(String(4), nullable=False)

    usd_rate_scaled: Mapped[int] = mapped_column(BigInteger, nullable=False)
    """USD per one unit of this currency, scaled by ``money.FX_SCALE``."""

    rate_as_of: Mapped[date] = mapped_column(Date, nullable=False)
    """The date this rate was captured.

    A single current rate per currency is enough for the confirmed scope.
    Reporting against historical rates would make this a separate
    ``fx_rates`` table keyed by (currency, as_of); the column is kept here so
    that a report always states which rate produced it.
    """

    __table_args__ = (CheckConstraint("usd_rate_scaled > 0", name="rate_positive"),)


class Country(Base):
    """An operating location. ISO 3166-1 alpha-2 keyed."""

    __tablename__ = "countries"

    code: Mapped[str] = mapped_column(String(2), primary_key=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    region: Mapped[str] = mapped_column(String(40), nullable=False)

    default_currency_code: Mapped[str] = mapped_column(
        String(3), ForeignKey("currencies.code"), nullable=False
    )
    """Prefilled when creating an employee, but not binding.

    An employee's pay currency is a separate fact from where they work — a
    contractor in Germany may be paid in USD — so the employee carries its own
    currency column rather than inheriting this one.
    """

    default_currency: Mapped[Currency] = relationship(lazy="joined")


class Employee(Base):
    __tablename__ = "employees"

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_code: Mapped[str] = mapped_column(String(16), nullable=False, unique=True)

    first_name: Mapped[str] = mapped_column(String(80), nullable=False)
    last_name: Mapped[str] = mapped_column(String(80), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)

    country_code: Mapped[str] = mapped_column(
        String(2), ForeignKey("countries.code"), nullable=False
    )
    department: Mapped[Department] = mapped_column(String(24), nullable=False)
    job_title: Mapped[str] = mapped_column(String(120), nullable=False)
    level: Mapped[Level] = mapped_column(String(2), nullable=False)
    employment_type: Mapped[EmploymentType] = mapped_column(String(16), nullable=False)
    status: Mapped[EmploymentStatus] = mapped_column(String(8), nullable=False)
    hire_date: Mapped[date] = mapped_column(Date, nullable=False)

    manager_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id"), nullable=True)

    currency_code: Mapped[str] = mapped_column(
        String(3), ForeignKey("currencies.code"), nullable=False
    )
    base_salary_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    bonus_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)

    total_comp_usd_fx_scaled: Mapped[int] = mapped_column(BigInteger, nullable=False)
    """``(base_salary_minor + bonus_minor) * currency.usd_rate_scaled``.

    Derived and stored so that sorting and range-filtering by USD compensation
    can use an index. Computing it on read would mean joining ``currencies`` and
    multiplying before every comparison, which no index can serve — the database
    would scan and sort all 10,000 rows for every page of the employee list.

    Kept in FX-scaled space rather than plain USD minor units so that ``SUM``
    over the column stays exact; see :mod:`app.domain.money`.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    currency: Mapped[Currency] = relationship(lazy="joined")
    country: Mapped[Country] = relationship(lazy="joined")
    manager: Mapped["Employee | None"] = relationship(remote_side=[id], lazy="raise")
    """Loaded explicitly, never implicitly.

    ``lazy="raise"`` turns an accidental access during list serialisation into a
    loud error instead of one silent query per row — the classic N+1 that only
    shows up once the list is long enough to matter. The detail endpoint asks
    for it with ``selectinload``.
    """

    __table_args__ = (
        CheckConstraint("base_salary_minor >= 0", name="base_salary_non_negative"),
        CheckConstraint("bonus_minor >= 0", name="bonus_non_negative"),
        # Single-column indexes back each individual facet of the filter model.
        Index("ix_employees_country_code", "country_code"),
        Index("ix_employees_department", "department"),
        Index("ix_employees_level", "level"),
        Index("ix_employees_status", "status"),
        Index("ix_employees_employment_type", "employment_type"),
        Index("ix_employees_hire_date", "hire_date"),
        Index("ix_employees_manager_id", "manager_id"),
        # Sorting by compensation is the dashboard's most common ordering, and
        # the range filter uses the same column.
        Index("ix_employees_total_comp_usd_fx_scaled", "total_comp_usd_fx_scaled"),
        # Name sort is (last, first), so a composite index serves it in one pass.
        Index("ix_employees_last_name_first_name", "last_name", "first_name"),
        # The dashboard's default posture is "active employees, grouped by a
        # dimension". Leading with status lets these composites serve both the
        # filter and the grouping without a separate sort step.
        Index("ix_employees_status_department", "status", "department"),
        Index("ix_employees_status_country_code", "status", "country_code"),
        Index("ix_employees_status_level", "status", "level"),
    )
