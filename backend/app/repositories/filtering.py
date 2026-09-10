"""Translation of the shared filter model into SQL predicates.

This module is the *only* place :class:`~app.domain.filters.EmployeeFilters`
becomes SQL. The employee list and every dashboard aggregate call
:func:`filter_conditions`, which is what makes the product guarantee mechanical
rather than aspirational: a KPI and the list behind it cannot disagree, because
they are the same ``WHERE`` clause.
"""

from sqlalchemy import ColumnElement, or_

from app.domain.filters import EmployeeFilters
from app.domain.money import to_fx_scaled
from app.models import Employee

_SEARCHABLE_COLUMNS = (
    Employee.first_name,
    Employee.last_name,
    Employee.email,
    Employee.employee_code,
    Employee.job_title,
)


def _search_conditions(search: str) -> list[ColumnElement[bool]]:
    """One condition per whitespace-separated token, each matching any column.

    Tokens are combined conjunctively so that "ada engineer" narrows rather than
    widens — typing more should never return more results. Within a token the
    match is disjunctive across columns, so the HR Manager does not have to know
    which field holds what they remember.

    The leading-wildcard ``LIKE`` cannot use an index and therefore scans. At
    10,000 rows that costs single-digit milliseconds, which is the right trade
    for not maintaining a search index; ``docs/performance.md`` records the
    measurement and the FTS5 path if the population grows an order of magnitude.
    """
    conditions: list[ColumnElement[bool]] = []
    for token in search.split():
        pattern = f"%{token}%"
        conditions.append(or_(*(column.ilike(pattern) for column in _SEARCHABLE_COLUMNS)))
    return conditions


def filter_conditions(filters: EmployeeFilters) -> list[ColumnElement[bool]]:
    """Build the ``WHERE`` clauses for a selection.

    Returned as a list to be splatted into ``.where(*conditions)``; an empty list
    means "the whole population", which is exactly what an untouched filter
    panel should mean.
    """
    conditions: list[ColumnElement[bool]] = []

    if filters.search is not None and filters.search.strip():
        conditions.extend(_search_conditions(filters.search.strip()))
    if filters.countries:
        conditions.append(Employee.country_code.in_(filters.countries))
    if filters.departments:
        conditions.append(Employee.department.in_(filters.departments))
    if filters.levels:
        conditions.append(Employee.level.in_(filters.levels))
    if filters.employment_types:
        conditions.append(Employee.employment_type.in_(filters.employment_types))
    if filters.statuses:
        conditions.append(Employee.status.in_(filters.statuses))

    # Compensation bounds arrive as plain USD minor units and are lifted into the
    # FX-scaled space the indexed column stores, so the comparison stays on the
    # index rather than transforming the column.
    if filters.min_total_comp_usd_minor is not None:
        conditions.append(
            Employee.total_comp_usd_fx_scaled >= to_fx_scaled(filters.min_total_comp_usd_minor)
        )
    if filters.max_total_comp_usd_minor is not None:
        conditions.append(
            Employee.total_comp_usd_fx_scaled <= to_fx_scaled(filters.max_total_comp_usd_minor)
        )

    return conditions
