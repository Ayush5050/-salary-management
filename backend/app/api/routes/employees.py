"""Employee endpoints.

Routes are thin on purpose: parse, delegate, serialise. Every rule about what a
valid employee is lives in the domain and repository layers, so the same rules
apply to any future caller that is not HTTP.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import EmployeeFiltersDep, PaginationDep, SortDep
from app.db import get_session
from app.domain.compensation import Compensation
from app.domain.employee import EmployeeDraft
from app.repositories import employees as repository
from app.schemas import (
    EmployeeDetail,
    EmployeeListResponse,
    EmployeeRow,
    EmployeeWrite,
    PageMeta,
    StatusChange,
)

router = APIRouter(prefix="/employees", tags=["employees"])

SessionDep = Annotated[Session, Depends(get_session)]


def _to_draft(body: EmployeeWrite) -> EmployeeDraft:
    return EmployeeDraft(
        employee_code=body.employee_code,
        first_name=body.first_name,
        last_name=body.last_name,
        email=str(body.email),
        country_code=body.country_code.upper(),
        department=body.department,
        job_title=body.job_title,
        level=body.level,
        employment_type=body.employment_type,
        status=body.status,
        hire_date=body.hire_date,
        manager_id=body.manager_id,
        compensation=Compensation(
            base_salary_minor=body.base_salary_minor,
            bonus_minor=body.bonus_minor,
            currency_code=body.currency_code.upper(),
        ),
    )


@router.get("", response_model=EmployeeListResponse)
def list_employees(
    session: SessionDep,
    filters: EmployeeFiltersDep,
    pagination: PaginationDep,
    sort: SortDep,
) -> EmployeeListResponse:
    sort_field, direction = sort
    page = repository.list_employees(
        session, filters, sort_field, direction, pagination.page, pagination.page_size
    )
    return EmployeeListResponse(
        items=[EmployeeRow.of(employee) for employee in page.items],
        meta=PageMeta(
            total=page.total,
            page=page.page,
            page_size=page.page_size,
            total_pages=page.total_pages,
        ),
    )


@router.get("/{employee_id}", response_model=EmployeeDetail)
def get_employee(session: SessionDep, employee_id: int) -> EmployeeDetail:
    return EmployeeDetail.of(repository.get_employee(session, employee_id))


@router.post("", response_model=EmployeeDetail, status_code=status.HTTP_201_CREATED)
def create_employee(session: SessionDep, body: EmployeeWrite) -> EmployeeDetail:
    return EmployeeDetail.of(repository.create_employee(session, _to_draft(body)))


@router.put("/{employee_id}", response_model=EmployeeDetail)
def replace_employee(session: SessionDep, employee_id: int, body: EmployeeWrite) -> EmployeeDetail:
    return EmployeeDetail.of(repository.replace_employee(session, employee_id, _to_draft(body)))


@router.patch("/{employee_id}/status", response_model=EmployeeDetail)
def change_status(session: SessionDep, employee_id: int, body: StatusChange) -> EmployeeDetail:
    """Activate or deactivate.

    There is no DELETE. Compensation records are financial history, and a leaver
    still has to appear in last year's payroll totals.
    """
    return EmployeeDetail.of(repository.set_employee_status(session, employee_id, body.status))
