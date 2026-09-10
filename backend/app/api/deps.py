"""Shared request dependencies.

The filter dependency is the HTTP-side half of the shared filter model: it
parses query parameters once, and both the employee routes and the analytics
routes depend on it. A dashboard request and a list request carrying the same
query string therefore produce the same :class:`EmployeeFilters`, which is what
keeps the two views reconciled.

FastAPI signals optional query parameters through default values, so the
defaults below are framework-mandated rather than a matter of style.
"""

from typing import Annotated
from urllib.parse import urlencode

from fastapi import Depends, HTTPException, Query, status

from app.config import Settings, get_settings
from app.domain.enums import (
    Department,
    EmployeeSortField,
    EmploymentStatus,
    EmploymentType,
    Level,
    SortDirection,
)
from app.domain.filters import EmployeeFilters


def get_employee_filters(
    search: Annotated[str | None, Query(max_length=200)] = None,
    country: Annotated[list[str] | None, Query()] = None,
    department: Annotated[list[Department] | None, Query()] = None,
    level: Annotated[list[Level] | None, Query()] = None,
    employment_type: Annotated[list[EmploymentType] | None, Query()] = None,
    employment_status: Annotated[list[EmploymentStatus] | None, Query(alias="status")] = None,
    min_total_comp_usd_minor: Annotated[int | None, Query(ge=0)] = None,
    max_total_comp_usd_minor: Annotated[int | None, Query(ge=0)] = None,
) -> EmployeeFilters:
    try:
        return EmployeeFilters(
            search=search,
            countries=tuple(country or ()),
            departments=tuple(department or ()),
            levels=tuple(level or ()),
            employment_types=tuple(employment_type or ()),
            statuses=tuple(employment_status or ()),
            min_total_comp_usd_minor=min_total_comp_usd_minor,
            max_total_comp_usd_minor=max_total_comp_usd_minor,
        )
    except ValueError as error:
        # An inverted compensation range is a malformed request, not a server
        # fault, and the domain message already names both bounds.
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(error)) from error


EmployeeFiltersDep = Annotated[EmployeeFilters, Depends(get_employee_filters)]


def filters_to_query_string(filters: EmployeeFilters) -> str:
    """The inverse of :func:`get_employee_filters`.

    Lets the question endpoint hand back a query string the client can navigate
    to, so an answered question lands on exactly the same filtered view a person
    would have built by hand. Kept beside the parser deliberately: the two are
    inverses, and a round-trip test asserts it.
    """
    params: list[tuple[str, str]] = []

    if filters.search is not None:
        params.append(("search", filters.search))
    params.extend(("country", country) for country in filters.countries)
    params.extend(("department", department.value) for department in filters.departments)
    params.extend(("level", level.value) for level in filters.levels)
    params.extend(("employment_type", kind.value) for kind in filters.employment_types)
    params.extend(("status", status_value.value) for status_value in filters.statuses)

    if filters.min_total_comp_usd_minor is not None:
        params.append(("min_total_comp_usd_minor", str(filters.min_total_comp_usd_minor)))
    if filters.max_total_comp_usd_minor is not None:
        params.append(("max_total_comp_usd_minor", str(filters.max_total_comp_usd_minor)))

    return urlencode(params)


class Pagination:
    """Validated page coordinates.

    ``page_size`` is capped by configuration: without a ceiling a client could
    ask for all 10,000 rows at once and defeat the pagination the read path is
    designed around.
    """

    def __init__(
        self,
        settings: Annotated[Settings, Depends(get_settings)],
        page: Annotated[int, Query(ge=1)] = 1,
        page_size: Annotated[int, Query(ge=1)] = 50,
    ) -> None:
        if page_size > settings.max_page_size:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"page_size {page_size} exceeds the maximum of {settings.max_page_size}",
            )
        self.page = page
        self.page_size = page_size


PaginationDep = Annotated[Pagination, Depends(Pagination)]


def get_sort(
    sort: Annotated[EmployeeSortField, Query()] = EmployeeSortField.NAME,
    direction: Annotated[SortDirection, Query()] = SortDirection.ASC,
) -> tuple[EmployeeSortField, SortDirection]:
    return sort, direction


SortDep = Annotated[tuple[EmployeeSortField, SortDirection], Depends(get_sort)]
