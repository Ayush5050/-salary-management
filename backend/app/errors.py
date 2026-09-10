"""Domain errors.

Named per failure so callers can distinguish them, and so the HTTP layer can map
each to the right status code in one place rather than inspecting messages.
Every message carries the offending value: a 409 that says "email already in
use" is far less useful at 2am than one that names the email and the employee
already holding it.
"""


class SalaryManagementError(Exception):
    """Base class, so the API can catch the family without catching everything."""


class EmployeeNotFoundError(SalaryManagementError):
    def __init__(self, employee_id: int) -> None:
        self.employee_id = employee_id
        super().__init__(f"no employee with id {employee_id}")


class DuplicateEmployeeFieldError(SalaryManagementError):
    def __init__(self, field: str, value: str, existing_employee_code: str) -> None:
        self.field = field
        self.value = value
        self.existing_employee_code = existing_employee_code
        super().__init__(f"{field} {value!r} is already used by employee {existing_employee_code}")


class UnknownReferenceError(SalaryManagementError):
    def __init__(self, reference: str, value: str) -> None:
        self.reference = reference
        self.value = value
        super().__init__(f"unknown {reference}: {value!r}")


class InvalidManagerError(SalaryManagementError):
    def __init__(self, reason: str, manager_id: int) -> None:
        self.reason = reason
        self.manager_id = manager_id
        super().__init__(f"invalid manager {manager_id}: {reason}")
