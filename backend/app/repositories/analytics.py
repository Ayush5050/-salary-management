"""Compensation aggregates.

Every figure here is computed by the database. Loading 10,000 rows into Python
to sum them would work at this size and stop working at the next one, and it
would put the arithmetic somewhere the query planner cannot help.

Two aggregates need comment:

*   **Average** is deliberately *not* SQL ``AVG``. ``AVG`` returns a float, which
    reintroduces exactly the drift the integer representation exists to avoid.
    The total and the count come back as integers and the mean is taken in
    :mod:`app.domain.statistics`.

*   **Median** has no portable SQL function, so it is computed with window
    functions: rank every row within its group, then keep only the row (or two)
    straddling the midpoint. See :func:`_middle_rank_condition`.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from sqlalchemy import ColumnElement, Select, and_, case, func, literal, select
from sqlalchemy.orm import InstrumentedAttribute, Session

from app.domain.enums import BreakdownDimension
from app.domain.filters import EmployeeFilters
from app.domain.money import descale_fx, to_fx_scaled
from app.domain.salary_bands import SALARY_BANDS
from app.domain.statistics import arithmetic_mean, median_of_middle_values
from app.models import Employee
from app.repositories.filtering import filter_conditions

# A column expression, not a constant value: lower-case to match.
_total_comp = Employee.total_comp_usd_fx_scaled

type GroupColumn = ColumnElement[Any] | InstrumentedAttribute[Any]
"""A column to group by: either a mapped attribute or a constant expression."""

# Typed as Any because SQLAlchemy's column generics are invariant: the
# department and level columns carry enum types, not plain str.
_DIMENSION_COLUMNS: dict[BreakdownDimension, InstrumentedAttribute[Any]] = {
    BreakdownDimension.COUNTRY: Employee.country_code,
    BreakdownDimension.DEPARTMENT: Employee.department,
    BreakdownDimension.LEVEL: Employee.level,
}


@dataclass(frozen=True, slots=True)
class CompensationStats:
    """Total annual compensation for a set of employees, in USD minor units.

    Every field but ``headcount`` and ``total_usd_minor`` is ``None`` for an
    empty set — there is no median of nobody, and reporting zero would be
    indistinguishable from a real result.
    """

    headcount: int
    total_usd_minor: int
    average_usd_minor: int | None
    median_usd_minor: int | None
    min_usd_minor: int | None
    max_usd_minor: int | None

    @classmethod
    def empty(cls) -> "CompensationStats":
        return cls(
            headcount=0,
            total_usd_minor=0,
            average_usd_minor=None,
            median_usd_minor=None,
            min_usd_minor=None,
            max_usd_minor=None,
        )


@dataclass(frozen=True, slots=True)
class BreakdownRow:
    """One group of a dimensional breakdown. ``key`` is the raw column value;
    human labels are attached by the API layer from reference data."""

    key: str
    stats: CompensationStats


@dataclass(frozen=True, slots=True)
class BandCount:
    label: str
    lower_usd_minor: int
    upper_usd_minor: int | None
    headcount: int


def _middle_rank_condition(
    rank: ColumnElement[int], group_size: ColumnElement[int]
) -> ColumnElement[bool]:
    """Select the one or two ranked rows that straddle a group's midpoint.

    The ranks wanted are ``(n+1)//2`` and ``(n+2)//2`` — the same row twice when
    ``n`` is odd, two adjacent rows when it is even. Expressed directly that
    needs integer division, whose behaviour varies between database backends.

    Multiplying it out removes the division entirely. ``r == (n+1)//2`` holds
    exactly when ``2r <= n+1 <= 2r+1``, and ``r == (n+2)//2`` when
    ``2r <= n+2 <= 2r+1``; the union of those two ranges simplifies to
    ``2r - 2 <= n <= 2r``. That is pure integer comparison, identical on every
    backend. ``tests/test_analytics.py`` pins it against a reference median over
    groups of both parities.
    """
    return and_(group_size <= 2 * rank, group_size >= 2 * rank - 2)


def _median_by_group(
    session: Session,
    conditions: Sequence[ColumnElement[bool]],
    group_column: GroupColumn,
) -> dict[Any, int | None]:
    ranked = (
        select(
            group_column.label("group_key"),
            _total_comp.label("value"),
            func.row_number().over(partition_by=group_column, order_by=_total_comp).label("rank"),
            func.count().over(partition_by=group_column).label("group_size"),
        )
        .where(*conditions)
        .subquery()
    )

    midpoint_rows = (
        select(
            ranked.c.group_key,
            func.sum(ranked.c.value).label("middle_total"),
            func.count().label("middle_count"),
        )
        .where(_middle_rank_condition(ranked.c.rank, ranked.c.group_size))
        .group_by(ranked.c.group_key)
    )

    return {
        group_key: median_of_middle_values(int(middle_total), int(middle_count))
        for group_key, middle_total, middle_count in session.execute(midpoint_rows)
    }


def _aggregate_query(
    conditions: Sequence[ColumnElement[bool]],
    group_column: GroupColumn,
) -> Select[tuple[Any, int, int, int, int]]:
    return (
        select(
            group_column.label("group_key"),
            func.count().label("headcount"),
            func.sum(_total_comp).label("total"),
            func.min(_total_comp).label("minimum"),
            func.max(_total_comp).label("maximum"),
        )
        .where(*conditions)
        .group_by(group_column)
    )


def _build_stats(
    headcount: int, total: int, minimum: int, maximum: int, median: int | None
) -> CompensationStats:
    total_usd_minor = descale_fx(int(total))
    return CompensationStats(
        headcount=headcount,
        total_usd_minor=total_usd_minor,
        average_usd_minor=arithmetic_mean(total_usd_minor, headcount),
        median_usd_minor=None if median is None else descale_fx(median),
        min_usd_minor=descale_fx(int(minimum)),
        max_usd_minor=descale_fx(int(maximum)),
    )


def compensation_summary(session: Session, filters: EmployeeFilters) -> CompensationStats:
    """Headline figures for the whole filtered selection."""
    conditions = filter_conditions(filters)
    # A constant group column keeps this on the same code path as a dimensional
    # breakdown, rather than maintaining a second, subtly different query.
    overall = literal(1)

    rows = session.execute(_aggregate_query(conditions, overall)).all()
    if not rows:
        return CompensationStats.empty()

    _, headcount, total, minimum, maximum = rows[0]
    medians = _median_by_group(session, conditions, overall)
    return _build_stats(headcount, total, minimum, maximum, medians.get(1))


def compensation_breakdown(
    session: Session, filters: EmployeeFilters, dimension: BreakdownDimension
) -> list[BreakdownRow]:
    """Per-group figures, ordered by total spend so the largest cost leads."""
    conditions = filter_conditions(filters)
    group_column = _DIMENSION_COLUMNS[dimension]

    medians = _median_by_group(session, conditions, group_column)
    rows = session.execute(_aggregate_query(conditions, group_column)).all()

    breakdown = [
        BreakdownRow(
            key=str(group_key),
            stats=_build_stats(headcount, total, minimum, maximum, medians.get(group_key)),
        )
        for group_key, headcount, total, minimum, maximum in rows
    ]
    return sorted(breakdown, key=lambda row: row.stats.total_usd_minor, reverse=True)


def salary_distribution(session: Session, filters: EmployeeFilters) -> list[BandCount]:
    """Headcount per salary band, including bands nobody falls into.

    Empty bands are kept so the histogram's axis is stable as filters change; a
    chart that silently drops its empty buckets misrepresents the shape of the
    distribution.
    """
    # Bands are contiguous and ascending, so the first CASE arm whose upper bound
    # exceeds the value is the right one, and the final band is the catch-all.
    band_arms: list[tuple[ColumnElement[bool], str]] = []
    for band in SALARY_BANDS:
        if band.upper_usd_minor is None:
            continue
        upper_bound = to_fx_scaled(band.upper_usd_minor)
        band_arms.append((_total_comp < upper_bound, band.label))
    band_label = case(*band_arms, else_=SALARY_BANDS[-1].label)

    counted = session.execute(
        select(band_label.label("band"), func.count().label("headcount"))
        .where(*filter_conditions(filters))
        .group_by(band_label)
    ).all()
    headcount_by_label = {label: headcount for label, headcount in counted}

    return [
        BandCount(
            label=band.label,
            lower_usd_minor=band.lower_usd_minor,
            upper_usd_minor=band.upper_usd_minor,
            headcount=headcount_by_label.get(band.label, 0),
        )
        for band in SALARY_BANDS
    ]
