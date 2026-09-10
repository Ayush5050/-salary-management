"""The write-side representation of an employee.

A plain domain value that carries everything needed to create or replace a
record. It exists so the repositories depend on neither Pydantic nor FastAPI:
the HTTP layer validates a request into one of these, and the persistence layer
consumes it. That keeps the compensation rules reachable from a future CSV
importer or scheduled job without dragging a web framework along.
"""

from dataclasses import dataclass
from datetime import date

from app.domain.compensation import Compensation
from app.domain.enums import Department, EmploymentStatus, EmploymentType, Level


@dataclass(frozen=True, slots=True)
class EmployeeDraft:
    employee_code: str
    first_name: str
    last_name: str
    email: str
    country_code: str
    department: Department
    job_title: str
    level: Level
    employment_type: EmploymentType
    status: EmploymentStatus
    hire_date: date
    manager_id: int | None
    compensation: Compensation

    def __post_init__(self) -> None:
        if not self.first_name.strip() or not self.last_name.strip():
            raise ValueError("employee must have a first and last name")
        if not self.employee_code.strip():
            raise ValueError("employee must have an employee code")
