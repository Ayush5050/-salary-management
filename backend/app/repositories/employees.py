"""Employee reads and writes."""

from dataclasses import dataclass
from typing import Any

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.orm import InstrumentedAttribute, Session, selectinload

from app.domain.compensation import total_comp_usd_fx_scaled
from app.domain.employee import EmployeeDraft
from app.domain.enums import EmployeeSortField, EmploymentStatus, SortDirection
from app.domain.filters import EmployeeFilters
from app.errors import (
    DuplicateEmployeeFieldError,
    EmployeeNotFoundError,
    InvalidManagerError,
    UnknownReferenceError,
)
from app.models import Country, Currency, Employee
from app.repositories.filtering import filter_conditions

# SQLAlchemy's column generics are invariant, so a map spanning str, date,
# Department, Level and int columns cannot be typed more precisely than Any.
_SORT_COLUMNS: dict[EmployeeSortField, tuple[InstrumentedAttribute[Any], ...]] = {
    EmployeeSortField.NAME: (Employee.last_name, Employee.first_name),
    EmployeeSortField.HIRE_DATE: (Employee.hire_date,),
    EmployeeSortField.DEPARTMENT: (Employee.department,),
    EmployeeSortField.LEVEL: (Employee.level,),
    EmployeeSortField.COUNTRY: (Employee.country_code,),
    EmployeeSortField.TOTAL_COMP_USD: (Employee.total_comp_usd_fx_scaled,),
}


@dataclass(frozen=True, slots=True)
class EmployeePage:
    items: tuple[Employee, ...]
    total: int
    page: int
    page_size: int

    @property
    def total_pages(self) -> int:
        return -(-self.total // self.page_size) if self.page_size else 0


def _order_by(sort: EmployeeSortField, direction: SortDirection) -> list[ColumnElement[Any]]:
    """Ordering terms, always ending with a unique tiebreaker.

    Sorting by department alone leaves thousands of rows tied, and SQLite is free
    to return tied rows in any order between queries. Paging through such a sort
    would then show some employees twice and skip others entirely. Appending the
    primary key makes the total order deterministic, which is what pagination
    actually requires.
    """
    columns = _SORT_COLUMNS[sort]
    descending = direction is SortDirection.DESC
    terms: list[ColumnElement[Any]] = [
        column.desc() if descending else column.asc() for column in columns
    ]
    terms.append(Employee.id.desc() if descending else Employee.id.asc())
    return terms


def list_employees(
    session: Session,
    filters: EmployeeFilters,
    sort: EmployeeSortField,
    direction: SortDirection,
    page: int,
    page_size: int,
) -> EmployeePage:
    """One page of employees, plus the total the filter matches.

    The total is a separate ``COUNT`` rather than something derived from the
    page, because the UI needs to show "1–50 of 9,381" without fetching 9,381
    rows. Both queries share the same predicates via :func:`filter_conditions`.
    """
    if page < 1:
        raise ValueError(f"page must be 1 or greater, got {page}")
    if page_size < 1:
        raise ValueError(f"page size must be 1 or greater, got {page_size}")

    conditions = filter_conditions(filters)
    total = session.scalar(select(func.count()).select_from(Employee).where(*conditions))

    rows = session.scalars(
        select(Employee)
        .where(*conditions)
        .order_by(*_order_by(sort, direction))
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    return EmployeePage(items=tuple(rows), total=int(total or 0), page=page, page_size=page_size)


def get_employee(session: Session, employee_id: int) -> Employee:
    """Fetch one employee with their manager eagerly loaded."""
    employee = session.scalar(
        select(Employee).options(selectinload(Employee.manager)).where(Employee.id == employee_id)
    )
    if employee is None:
        raise EmployeeNotFoundError(employee_id)
    return employee


def _currency_rate(session: Session, currency_code: str) -> int:
    rate = session.scalar(select(Currency.usd_rate_scaled).where(Currency.code == currency_code))
    if rate is None:
        raise UnknownReferenceError("currency", currency_code)
    return rate


def _assert_country_exists(session: Session, country_code: str) -> None:
    if session.scalar(select(Country.code).where(Country.code == country_code)) is None:
        raise UnknownReferenceError("country", country_code)


def _assert_field_available(
    session: Session,
    field: str,
    column: InstrumentedAttribute[str],
    value: str,
    excluding_id: int | None,
) -> None:
    query = select(Employee.employee_code).where(column == value)
    if excluding_id is not None:
        query = query.where(Employee.id != excluding_id)
    existing_code = session.scalar(query)
    if existing_code is not None:
        raise DuplicateEmployeeFieldError(field, value, existing_code)


def _validate_manager(session: Session, manager_id: int, employee_id: int | None) -> None:
    """Reject managers that do not exist, are the employee themselves, or would
    close a reporting cycle.

    A cycle is not a theoretical concern: promoting someone above their old
    manager and re-pointing one record is enough to create one, and an org chart
    with a cycle makes any recursive traversal hang.
    """
    if session.scalar(select(Employee.id).where(Employee.id == manager_id)) is None:
        raise InvalidManagerError("no such employee", manager_id)
    if employee_id is not None and manager_id == employee_id:
        raise InvalidManagerError("an employee cannot manage themselves", manager_id)

    if employee_id is not None:
        seen: set[int] = {employee_id}
        current: int | None = manager_id
        while current is not None:
            if current in seen:
                raise InvalidManagerError("this would create a reporting cycle", manager_id)
            seen.add(current)
            current = session.scalar(select(Employee.manager_id).where(Employee.id == current))


def _apply_draft(session: Session, employee: Employee, draft: EmployeeDraft) -> None:
    """Copy a validated draft onto a row, recomputing the derived USD total.

    Both create and update funnel through here so the denormalised column is
    refreshed on every write that could invalidate it.
    """
    _assert_country_exists(session, draft.country_code)
    rate = _currency_rate(session, draft.compensation.currency_code)
    if draft.manager_id is not None:
        _validate_manager(session, draft.manager_id, employee.id)

    employee.employee_code = draft.employee_code
    employee.first_name = draft.first_name
    employee.last_name = draft.last_name
    employee.email = draft.email
    employee.country_code = draft.country_code
    employee.department = draft.department
    employee.job_title = draft.job_title
    employee.level = draft.level
    employee.employment_type = draft.employment_type
    employee.status = draft.status
    employee.hire_date = draft.hire_date
    employee.manager_id = draft.manager_id
    employee.currency_code = draft.compensation.currency_code
    employee.base_salary_minor = draft.compensation.base_salary_minor
    employee.bonus_minor = draft.compensation.bonus_minor
    employee.total_comp_usd_fx_scaled = total_comp_usd_fx_scaled(draft.compensation, rate)


def create_employee(session: Session, draft: EmployeeDraft) -> Employee:
    _assert_field_available(session, "email", Employee.email, draft.email, excluding_id=None)
    _assert_field_available(
        session, "employee code", Employee.employee_code, draft.employee_code, excluding_id=None
    )

    employee = Employee()
    _apply_draft(session, employee, draft)
    session.add(employee)
    session.commit()
    return get_employee(session, employee.id)


def replace_employee(session: Session, employee_id: int, draft: EmployeeDraft) -> Employee:
    """Full replacement of an employee record.

    Replacement rather than partial patching: the UI edits a whole form, and a
    full body makes concurrent edits obvious instead of silently interleaving
    field-by-field.
    """
    employee = get_employee(session, employee_id)
    _assert_field_available(session, "email", Employee.email, draft.email, excluding_id=employee_id)
    _assert_field_available(
        session,
        "employee code",
        Employee.employee_code,
        draft.employee_code,
        excluding_id=employee_id,
    )

    _apply_draft(session, employee, draft)
    session.commit()
    return get_employee(session, employee_id)


def set_employee_status(session: Session, employee_id: int, status: EmploymentStatus) -> Employee:
    """Activate or deactivate an employee.

    Compensation records are financial history, so leavers are deactivated and
    never deleted. There is deliberately no delete operation in this repository.
    """
    employee = get_employee(session, employee_id)
    employee.status = status
    session.commit()
    return get_employee(session, employee_id)
